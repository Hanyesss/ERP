import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.warehouse import Warehouse

router = APIRouter(prefix="/api/warehouses", tags=["warehouses"])

_WRITE_ROLES = ("accountant", "admin")


class WarehouseCreate(BaseModel):
    name: str
    name_cn: Optional[str] = None
    city: Optional[str] = None
    is_active: bool = True


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    name_cn: Optional[str] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None


class WarehouseResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    city: Optional[str] = None
    is_active: bool


@router.get("", response_model=list[WarehouseResponse])
async def list_warehouses(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.name)
    )).scalars().all()
    return [WarehouseResponse(id=w.id, name=w.name, name_cn=w.name_cn, city=w.city, is_active=w.is_active) for w in rows]


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    body: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_WRITE_ROLES)),
):
    wh = Warehouse(id=uuid.uuid4(), **body.model_dump())
    db.add(wh)
    await db.commit()
    return WarehouseResponse(id=wh.id, name=wh.name, name_cn=wh.name_cn, city=wh.city, is_active=wh.is_active)


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    body: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_WRITE_ROLES)),
):
    wh = (await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))).scalar_one_or_none()
    if not wh:
        raise HTTPException(404, "Warehouse not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(wh, field, value)
    await db.commit()
    return WarehouseResponse(id=wh.id, name=wh.name, name_cn=wh.name_cn, city=wh.city, is_active=wh.is_active)


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warehouse(
    warehouse_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_WRITE_ROLES)),
):
    wh = (await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))).scalar_one_or_none()
    if not wh:
        raise HTTPException(404, "Warehouse not found")
    wh.is_active = False
    await db.commit()
