import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.counterparty import Counterparty, CounterpartyType
from app.models.audit_log import AuditActionEnum
from app.schemas.counterparty import (
    CounterpartyCreate, CounterpartyUpdate,
    CounterpartyResponse, CounterpartyListResponse,
)
from app.utils.audit import write_audit

router = APIRouter(prefix="/api/counterparties", tags=["counterparties"])


def _to_dict(obj: Counterparty) -> dict:
    return {
        "id": str(obj.id),
        "name": obj.name,
        "name_cn": obj.name_cn,
        "type": obj.type,
        "default_currency": obj.default_currency,
        "contact_info": obj.contact_info,
        "notes": obj.notes,
        "is_active": obj.is_active,
    }


@router.get("", response_model=CounterpartyListResponse)
async def list_counterparties(
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Counterparty).where(Counterparty.is_active == True)

    if search:
        q = q.where(or_(
            Counterparty.name.ilike(f"%{search}%"),
            Counterparty.name_cn.ilike(f"%{search}%"),
        ))
    if type and type != "all":
        q = q.where(or_(
            Counterparty.type == type,
            Counterparty.type == CounterpartyType.both,
        ))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Counterparty.name).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    return CounterpartyListResponse(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/{cp_id}", response_model=CounterpartyResponse)
async def get_counterparty(
    cp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cp = await _get_or_404(db, cp_id)
    return cp


@router.post("", response_model=CounterpartyResponse, status_code=status.HTTP_201_CREATED)
async def create_counterparty(
    body: CounterpartyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cp = Counterparty(
        id=uuid.uuid4(),
        name=body.name,
        name_cn=body.name_cn,
        type=body.type,
        default_currency=body.default_currency,
        contact_info=body.contact_info.model_dump() if body.contact_info else None,
        notes=body.notes,
        is_active=True,
    )
    db.add(cp)
    await db.flush()
    await write_audit(db, current_user.id, "counterparty", cp.id, AuditActionEnum.create,
                      {"new": _to_dict(cp)})
    await db.commit()
    await db.refresh(cp)
    return cp


@router.patch("/{cp_id}", response_model=CounterpartyResponse)
async def update_counterparty(
    cp_id: uuid.UUID,
    body: CounterpartyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cp = await _get_or_404(db, cp_id)
    old = _to_dict(cp)

    update_data = body.model_dump(exclude_unset=True)
    if "contact_info" in update_data and update_data["contact_info"] is not None:
        update_data["contact_info"] = update_data["contact_info"].model_dump() if hasattr(update_data["contact_info"], "model_dump") else update_data["contact_info"]
    for field, value in update_data.items():
        setattr(cp, field, value)

    await write_audit(db, current_user.id, "counterparty", cp.id, AuditActionEnum.update,
                      {"old": old, "new": _to_dict(cp)})
    await db.commit()
    await db.refresh(cp)
    return cp


@router.delete("/{cp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_counterparty(
    cp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cp = await _get_or_404(db, cp_id)
    old = _to_dict(cp)
    cp.is_active = False
    await write_audit(db, current_user.id, "counterparty", cp.id, AuditActionEnum.delete,
                      {"old": old})
    await db.commit()


async def _get_or_404(db: AsyncSession, cp_id: uuid.UUID) -> Counterparty:
    result = await db.execute(select(Counterparty).where(Counterparty.id == cp_id))
    cp = result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    return cp
