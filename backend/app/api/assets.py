import uuid
from pathlib import Path
from datetime import date as date_type
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.asset import Asset

router = APIRouter(prefix="/api/assets", tags=["assets"])

_VIEW_ROLES = require_roles("admin", "manager")
_EDIT_ROLES = require_roles("admin")

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _asset_upload_path(asset_id: uuid.UUID) -> Path:
    d = UPLOADS_DIR / "assets" / str(asset_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


class AssetCreate(BaseModel):
    name: str
    quantity: Decimal
    price: Decimal
    account: Optional[str] = None
    purchase_date: Optional[date_type] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    account: Optional[str] = None
    purchase_date: Optional[date_type] = None


class AssetResponse(BaseModel):
    id: uuid.UUID
    name: str
    image_path: Optional[str] = None
    quantity: Decimal
    price: Decimal
    total: Decimal
    account: Optional[str] = None
    purchase_date: Optional[date_type] = None
    created_by_name: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[AssetResponse])
async def list_assets(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_VIEW_ROLES),
):
    assets = (await db.execute(
        select(Asset).where(Asset.is_deleted == False).order_by(Asset.created_at.desc())
    )).scalars().all()

    user_ids = {a.created_by for a in assets}
    users_map = {}
    if user_ids:
        users_res = await db.execute(select(User).where(User.id.in_(user_ids)))
        users_map = {u.id: u.full_name for u in users_res.scalars().all()}

    return [
        AssetResponse(
            id=a.id,
            name=a.name,
            image_path=a.image_path,
            quantity=a.quantity,
            price=a.price,
            total=a.quantity * a.price,
            account=a.account,
            purchase_date=a.purchase_date,
            created_by_name=users_map.get(a.created_by, ""),
        )
        for a in assets
    ]


@router.post("", response_model=AssetResponse)
async def create_asset(
    body: AssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_EDIT_ROLES),
):
    asset = Asset(
        id=uuid.uuid4(),
        name=body.name,
        quantity=body.quantity,
        price=body.price,
        account=body.account,
        purchase_date=body.purchase_date,
        created_by=current_user.id,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return AssetResponse(
        id=asset.id,
        name=asset.name,
        image_path=asset.image_path,
        quantity=asset.quantity,
        price=asset.price,
        total=asset.quantity * asset.price,
        account=asset.account,
        purchase_date=asset.purchase_date,
        created_by_name=current_user.full_name,
    )


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_EDIT_ROLES),
):
    asset = (await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.is_deleted == False)
    )).scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")

    if body.name is not None:
        asset.name = body.name
    if body.quantity is not None:
        asset.quantity = body.quantity
    if body.price is not None:
        asset.price = body.price
    if body.account is not None:
        asset.account = body.account
    if body.purchase_date is not None:
        asset.purchase_date = body.purchase_date

    await db.commit()
    await db.refresh(asset)

    creator = (await db.execute(select(User).where(User.id == asset.created_by))).scalar_one_or_none()
    return AssetResponse(
        id=asset.id,
        name=asset.name,
        image_path=asset.image_path,
        quantity=asset.quantity,
        price=asset.price,
        total=asset.quantity * asset.price,
        account=asset.account,
        purchase_date=asset.purchase_date,
        created_by_name=creator.full_name if creator else "",
    )


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_EDIT_ROLES),
):
    asset = (await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.is_deleted == False)
    )).scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.is_deleted = True
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/{asset_id}/image")
async def upload_asset_image(
    asset_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_EDIT_ROLES),
):
    asset = (await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.is_deleted == False)
    )).scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")

    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(422, "Allowed: jpg, png, webp")

    ext = Path(file.filename or "image").suffix.lower() or ".jpg"
    stored_name = f"image{ext}"
    dest = _asset_upload_path(asset_id) / stored_name
    dest.write_bytes(content)

    asset.image_path = f"assets/{asset_id}/{stored_name}"
    await db.commit()
    return {"image_path": asset.image_path}


@router.get("/{asset_id}/image")
async def get_asset_image(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    asset = (await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.is_deleted == False)
    )).scalar_one_or_none()
    if not asset or not asset.image_path:
        raise HTTPException(404, "Image not found")

    file_path = UPLOADS_DIR / asset.image_path
    if not file_path.exists():
        raise HTTPException(404, "Image file not found")

    return FileResponse(str(file_path))
