import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.order_item import OrderItem
from app.models.order_item_photo import OrderItemPhoto
from app.models.audit_log import AuditActionEnum
from app.schemas.order import OrderItemPhotoResponse
from app.utils.audit import write_audit

router = APIRouter(prefix="/api/order-items", tags=["order-item-photos"])

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _item_dir(item_id: uuid.UUID) -> Path:
    d = UPLOADS_DIR / "order_items" / str(item_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _get_item_or_404(db: AsyncSession, item_id: uuid.UUID) -> OrderItem:
    item = (await db.execute(select(OrderItem).where(OrderItem.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Order item not found")
    return item


@router.get("/{item_id}/photos", response_model=list[OrderItemPhotoResponse])
async def list_photos(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await _get_item_or_404(db, item_id)
    photos = (await db.execute(
        select(OrderItemPhoto)
        .where(OrderItemPhoto.order_item_id == item_id)
        .order_by(OrderItemPhoto.sort_order, OrderItemPhoto.uploaded_at)
    )).scalars().all()
    return [
        OrderItemPhotoResponse(
            id=ph.id, file_url=ph.file_url, file_name=ph.file_name,
            file_size_bytes=ph.file_size_bytes, mime_type=ph.mime_type,
            sort_order=ph.sort_order, uploaded_at=ph.uploaded_at,
        )
        for ph in photos
    ]


@router.post("/{item_id}/photos", response_model=OrderItemPhotoResponse, status_code=201)
async def upload_photo(
    item_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_item_or_404(db, item_id)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")

    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(422, f"Only JPEG, PNG, WebP images allowed")

    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    ext = ext_map.get(mime, ".jpg")
    file_id = uuid.uuid4()
    filename = f"{file_id}{ext}"

    dest = _item_dir(item_id) / filename
    dest.write_bytes(content)

    photo = OrderItemPhoto(
        id=file_id,
        order_item_id=item_id,
        file_url=f"/api/order-items/{item_id}/photos/{file_id}/file",
        file_name=file.filename or filename,
        file_size_bytes=len(content),
        mime_type=mime,
        uploaded_by=current_user.id,
        sort_order=0,
    )
    db.add(photo)
    await write_audit(db, current_user.id, "order_item_photo", photo.id, AuditActionEnum.create,
                      {"item_id": str(item_id), "file_name": photo.file_name})
    await db.commit()
    await db.refresh(photo)
    return OrderItemPhotoResponse(
        id=photo.id, file_url=photo.file_url, file_name=photo.file_name,
        file_size_bytes=photo.file_size_bytes, mime_type=photo.mime_type,
        sort_order=photo.sort_order, uploaded_at=photo.uploaded_at,
    )


@router.get("/{item_id}/photos/{photo_id}/file")
async def serve_photo(
    item_id: uuid.UUID,
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    photo = (await db.execute(
        select(OrderItemPhoto).where(
            OrderItemPhoto.id == photo_id,
            OrderItemPhoto.order_item_id == item_id,
        )
    )).scalar_one_or_none()
    if not photo:
        raise HTTPException(404, "Photo not found")

    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    ext = ext_map.get(photo.mime_type or "", ".jpg")
    path = _item_dir(item_id) / f"{photo_id}{ext}"
    if not path.exists():
        raise HTTPException(404, "File not found on disk")
    return FileResponse(str(path), media_type=photo.mime_type or "image/jpeg")


@router.patch("/{item_id}/photos/{photo_id}", response_model=OrderItemPhotoResponse)
async def update_photo_order(
    item_id: uuid.UUID,
    photo_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    photo = (await db.execute(
        select(OrderItemPhoto).where(
            OrderItemPhoto.id == photo_id,
            OrderItemPhoto.order_item_id == item_id,
        )
    )).scalar_one_or_none()
    if not photo:
        raise HTTPException(404, "Photo not found")
    if "sort_order" in body:
        photo.sort_order = int(body["sort_order"])
    await db.commit()
    await db.refresh(photo)
    return OrderItemPhotoResponse(
        id=photo.id, file_url=photo.file_url, file_name=photo.file_name,
        file_size_bytes=photo.file_size_bytes, mime_type=photo.mime_type,
        sort_order=photo.sort_order, uploaded_at=photo.uploaded_at,
    )


@router.delete("/{item_id}/photos/{photo_id}", status_code=204)
async def delete_photo(
    item_id: uuid.UUID,
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    photo = (await db.execute(
        select(OrderItemPhoto).where(
            OrderItemPhoto.id == photo_id,
            OrderItemPhoto.order_item_id == item_id,
        )
    )).scalar_one_or_none()
    if not photo:
        raise HTTPException(404, "Photo not found")

    # Delete file from disk
    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    ext = ext_map.get(photo.mime_type or "", ".jpg")
    path = _item_dir(item_id) / f"{photo_id}{ext}"
    if path.exists():
        path.unlink()

    await write_audit(db, current_user.id, "order_item_photo", photo_id, AuditActionEnum.delete,
                      {"item_id": str(item_id)})
    await db.execute(sql_delete(OrderItemPhoto).where(OrderItemPhoto.id == photo_id))
    await db.commit()
