import uuid
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.order_file import OrderFile, FileTypeEnum
from app.models.audit_log import AuditActionEnum
from app.utils.audit import write_audit

router = APIRouter(prefix="/api/orders", tags=["order-files"])

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _order_dir(order_id: uuid.UUID) -> Path:
    d = UPLOADS_DIR / "orders" / str(order_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/{order_id}/files")
async def upload_file(
    order_id: uuid.UUID,
    file: UploadFile,
    file_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    # Validate file type enum value
    try:
        ft = FileTypeEnum(file_type)
    except ValueError:
        raise HTTPException(422, f"Invalid file_type '{file_type}'. Choose: {[e.value for e in FileTypeEnum]}")

    # Read and validate
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")

    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(422, f"File type not allowed: {mime}")

    # Store with UUID name to avoid collisions / encoding issues
    ext = Path(file.filename or "file").suffix.lower() or ".bin"
    stored_name = f"{uuid.uuid4()}{ext}"
    dest = _order_dir(order_id) / stored_name

    dest.write_bytes(content)

    relative_url = f"orders/{order_id}/{stored_name}"

    record = OrderFile(
        id=uuid.uuid4(),
        order_id=order_id,
        file_url=relative_url,
        file_name=file.filename or stored_name,
        file_type=ft,
        file_size_bytes=len(content),
        mime_type=mime,
        uploaded_by=current_user.id,
    )
    db.add(record)
    await write_audit(db, current_user.id, "order_file", record.id, AuditActionEnum.create,
                      {"order_id": str(order_id), "file_name": record.file_name, "file_type": file_type})
    await db.commit()
    await db.refresh(record)

    return {
        "id": str(record.id),
        "order_id": str(order_id),
        "file_url": record.file_url,
        "file_name": record.file_name,
        "file_type": record.file_type,
        "file_size_bytes": record.file_size_bytes,
        "mime_type": record.mime_type,
        "uploaded_by": str(record.uploaded_by),
        "uploaded_by_name": current_user.full_name,
        "uploaded_at": record.uploaded_at.isoformat(),
    }


@router.get("/{order_id}/files")
async def list_files(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    result = await db.execute(
        select(OrderFile, User.full_name.label("uploader_name"))
        .join(User, OrderFile.uploaded_by == User.id)
        .where(OrderFile.order_id == order_id)
        .order_by(OrderFile.uploaded_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(r[0].id),
            "order_id": str(order_id),
            "file_url": r[0].file_url,
            "file_name": r[0].file_name,
            "file_type": r[0].file_type,
            "file_size_bytes": r[0].file_size_bytes,
            "mime_type": r[0].mime_type,
            "uploaded_by": str(r[0].uploaded_by),
            "uploaded_by_name": r[1],
            "uploaded_at": r[0].uploaded_at.isoformat(),
        }
        for r in rows
    ]


@router.delete("/{order_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    order_id: uuid.UUID,
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = (await db.execute(
        select(OrderFile).where(OrderFile.id == file_id, OrderFile.order_id == order_id)
    )).scalar_one_or_none()
    if not record:
        raise HTTPException(404, "File not found")

    # Delete physical file
    file_path = UPLOADS_DIR / record.file_url
    if file_path.exists():
        file_path.unlink()

    await write_audit(db, current_user.id, "order_file", file_id, AuditActionEnum.delete,
                      {"order_id": str(order_id), "file_name": record.file_name})
    await db.delete(record)
    await db.commit()


# Auth-protected static file serving
files_router = APIRouter(tags=["files"])


@files_router.get("/files/{path:path}")
async def serve_file(
    path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Resolve and security-check the path
    requested = (UPLOADS_DIR / path).resolve()
    if not str(requested).startswith(str(UPLOADS_DIR.resolve())):
        raise HTTPException(404)
    if not requested.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(requested))
