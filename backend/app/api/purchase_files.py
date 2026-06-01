import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.purchase import Purchase
from app.models.purchase_file import PurchaseFile

router = APIRouter(prefix="/api/purchases", tags=["purchase-files"])

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _purchase_dir(purchase_id: uuid.UUID) -> Path:
    d = UPLOADS_DIR / "purchases" / str(purchase_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/{purchase_id}/files")
async def upload_purchase_file(
    purchase_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    purchase = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not purchase:
        raise HTTPException(404, "Purchase not found")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")

    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(422, f"Allowed: jpg, png, webp, pdf")

    ext = Path(file.filename or "file").suffix.lower() or ".bin"
    stored_name = f"{uuid.uuid4()}{ext}"
    dest = _purchase_dir(purchase_id) / stored_name
    dest.write_bytes(content)

    record = PurchaseFile(
        id=uuid.uuid4(),
        purchase_id=purchase_id,
        file_url=f"purchases/{purchase_id}/{stored_name}",
        file_name=file.filename or stored_name,
        file_size_bytes=len(content),
        mime_type=mime,
        uploaded_by=current_user.id,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {
        "id": str(record.id),
        "file_url": record.file_url,
        "file_name": record.file_name,
        "file_size_bytes": record.file_size_bytes,
        "mime_type": record.mime_type,
        "uploaded_by_name": current_user.full_name,
        "uploaded_at": record.uploaded_at.isoformat(),
    }


@router.get("/{purchase_id}/files")
async def list_purchase_files(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(PurchaseFile, User.full_name.label("uploader_name"))
        .join(User, PurchaseFile.uploaded_by == User.id)
        .where(PurchaseFile.purchase_id == purchase_id)
        .order_by(PurchaseFile.uploaded_at.desc())
    )).all()
    return [
        {
            "id": str(r[0].id),
            "file_url": r[0].file_url,
            "file_name": r[0].file_name,
            "file_size_bytes": r[0].file_size_bytes,
            "mime_type": r[0].mime_type,
            "uploaded_by_name": r[1],
            "uploaded_at": r[0].uploaded_at.isoformat(),
        }
        for r in rows
    ]


@router.delete("/{purchase_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_file(
    purchase_id: uuid.UUID,
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    record = (await db.execute(
        select(PurchaseFile).where(
            PurchaseFile.id == file_id, PurchaseFile.purchase_id == purchase_id
        )
    )).scalar_one_or_none()
    if not record:
        raise HTTPException(404, "File not found")

    file_path = UPLOADS_DIR / record.file_url
    if file_path.exists():
        file_path.unlink()

    await db.delete(record)
    await db.commit()
