import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import aliased

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
        "code": obj.code,
        "type": obj.type,
        "default_currency": obj.default_currency,
        "contact_info": obj.contact_info,
        "notes": obj.notes,
        "is_active": obj.is_active,
        "partner_id": str(obj.partner_id) if obj.partner_id else None,
    }


@router.get("", response_model=CounterpartyListResponse)
async def list_counterparties(
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    partner_id: Optional[uuid.UUID] = Query(None),
    trontok_linked: Optional[bool] = Query(None),
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
        if type == "partner":
            q = q.where(Counterparty.type == CounterpartyType.partner)
        else:
            q = q.where(or_(
                Counterparty.type == type,
                Counterparty.type == CounterpartyType.both,
            ))
    if partner_id:
        q = q.where(Counterparty.partner_id == partner_id)
    if trontok_linked is not None:
        q = q.where(Counterparty.trontok_linked == trontok_linked)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Counterparty.name).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    # Resolve partner names
    partner_ids = [cp.partner_id for cp in items if cp.partner_id]
    partner_names: dict[uuid.UUID, str] = {}
    if partner_ids:
        rows = (await db.execute(
            select(Counterparty.id, Counterparty.name).where(Counterparty.id.in_(partner_ids))
        )).all()
        partner_names = {r[0]: r[1] for r in rows}

    return CounterpartyListResponse(
        items=[
            CounterpartyResponse.from_obj(cp, partner_names.get(cp.partner_id) if cp.partner_id else None)
            for cp in items
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{cp_id}", response_model=CounterpartyResponse)
async def get_counterparty(
    cp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cp = await _get_or_404(db, cp_id)
    return CounterpartyResponse.from_obj(cp)


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
        code=body.code,
        type=body.type,
        default_currency=body.default_currency,
        contact_info=body.contact_info.model_dump() if body.contact_info else None,
        notes=body.notes,
        is_active=True,
        partner_id=body.partner_id,
    )
    db.add(cp)
    await db.flush()

    await write_audit(db, current_user.id, "counterparty", cp.id, AuditActionEnum.create,
                      {"new": _to_dict(cp)})
    await db.commit()
    await db.refresh(cp)
    return CounterpartyResponse.from_obj(cp)


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
    return CounterpartyResponse.from_obj(cp)


class SiteAccountBody(BaseModel):
    login: str
    password: str


class SiteCredentialsBody(BaseModel):
    current_login: str
    new_login: Optional[str] = None
    new_password: Optional[str] = None


@router.post("/{cp_id}/create-site-account")
async def create_site_account(
    cp_id: uuid.UUID,
    body: SiteAccountBody,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.integrations.irsway_site.service import get_active_client
    import asyncio

    cp = await _get_or_404(db, cp_id)
    client = await get_active_client(db)
    if client is None:
        raise HTTPException(422, "Интеграция с сайтом не настроена или отключена")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: client.create_client(
            username=body.login,
            password=body.password,
            full_name=cp.name,
            phone=cp.contact_info.get("phone") if isinstance(cp.contact_info, dict) else None,
            code=cp.code.upper() if cp.code else None,
        ),
    )
    if not result.ok:
        raise HTTPException(422, result.error or "Ошибка создания аккаунта на сайте")
    return {"ok": True, "user_id": result.user_id}


@router.post("/{cp_id}/link-site-account")
async def link_site_account(
    cp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Привязать client_code к существующему аккаунту на irsway.com (по номеру телефона)."""
    from app.integrations.irsway_site.service import get_active_client
    import asyncio

    cp = await _get_or_404(db, cp_id)
    if not cp.code:
        raise HTTPException(422, "У контрагента не задан код (code)")

    client = await get_active_client(db)
    if client is None:
        raise HTTPException(422, "Интеграция с сайтом не настроена или отключена")

    phone = cp.contact_info.get("phone") if isinstance(cp.contact_info, dict) else None

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: client.link_client(code=cp.code.upper()),
    )
    if not result.ok:
        raise HTTPException(422, result.error or "Не удалось привязать аккаунт")
    return {"ok": True, "user_id": result.user_id}


@router.patch("/{cp_id}/update-site-credentials")
async def update_site_credentials(
    cp_id: uuid.UUID,
    body: SiteCredentialsBody,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Сменить логин и/или пароль клиента на irsway.com."""
    from app.integrations.irsway_site.service import get_active_client
    import asyncio

    if not body.new_login and not body.new_password:
        raise HTTPException(422, "Укажите new_login и/или new_password")

    client = await get_active_client(db)
    if client is None:
        raise HTTPException(422, "Интеграция с сайтом не настроена или отключена")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: client.update_client_credentials(
            username=body.current_login,
            new_username=body.new_login or None,
            new_password=body.new_password or None,
        ),
    )
    if not result.ok:
        raise HTTPException(422, result.error or "Не удалось обновить данные")
    return {"ok": True, "username": result.user_id}


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
