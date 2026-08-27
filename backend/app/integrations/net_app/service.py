"""Входящая интеграция NET (приложение PARCEL → ERP).

Идемпотентный upsert заказа по external_ref. НИЧЕГО не пушим наружу (не дёргаем irsway_site).
"""
import uuid
import logging
from datetime import datetime, timezone, date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus, OrderCurrencyEnum
from app.models.business_type import BusinessType
from app.models.counterparty import Counterparty, CounterpartyType, CurrencyEnum
from app.models.company import Company
from app.models.user import User
from app.models.user_role import UserRoleEntry
from app.models.net_status_event import NetStatusEvent
from app.integrations.net_app.schemas import NetOrderIn, NetShipmentIn

RETAIL_CLIENT_CODE = "NET-RETAIL"
RETAIL_CLIENT_NAME = "NET (розничные посылки)"

log = logging.getLogger("net_inbound")

INTEGRATION_NAME = "net_inbound"

_LIFECYCLE_TO_STATUS = {
    "active": OrderStatus.active,
    "closed": OrderStatus.closed,
    "cancelled": OrderStatus.cancelled,
}


class NetUpsertError(Exception):
    """Штатная ошибка валидации (маппится в 422)."""


async def _get_company(db: AsyncSession) -> Company:
    company = (await db.execute(
        select(Company).where(Company.is_active == True).limit(1)
    )).scalar_one_or_none()
    if not company:
        raise NetUpsertError("no active company")
    return company


async def _get_system_user(db: AsyncSession) -> User:
    """Пользователь-владелец интеграционных заказов: первый админ, иначе любой активный."""
    admin = (await db.execute(
        select(User)
        .join(UserRoleEntry, UserRoleEntry.user_id == User.id)
        .where(UserRoleEntry.role == "admin", User.is_active == True, User.is_deleted == False)
        .limit(1)
    )).scalar_one_or_none()
    if admin:
        return admin
    any_user = (await db.execute(
        select(User).where(User.is_active == True, User.is_deleted == False).limit(1)
    )).scalar_one_or_none()
    if not any_user:
        raise NetUpsertError("no user to own integration orders")
    return any_user


async def _resolve_client(db: AsyncSession, payload: NetOrderIn, company: Company) -> Counterparty:
    c = payload.client
    code = (c.client_code or "").strip().upper() or None
    phone = (c.phone or "").strip() or None
    email = (c.email or "").strip() or None

    found = None
    if code:
        found = (await db.execute(
            select(Counterparty).where(Counterparty.code == code)
        )).scalars().first()
    if not found and phone:
        found = (await db.execute(
            select(Counterparty).where(Counterparty.contact_info["phone"].astext == phone)
        )).scalars().first()
    if not found and email:
        found = (await db.execute(
            select(Counterparty).where(Counterparty.contact_info["email"].astext == email)
        )).scalars().first()
    if found:
        return found

    contact: dict = {}
    if phone:
        contact["phone"] = phone
    if email:
        contact["email"] = email
    client = Counterparty(
        id=uuid.uuid4(),
        name=(c.name or c.client_code or "NET client"),
        code=code,
        type=CounterpartyType.client,
        default_currency=CurrencyEnum.CNY,
        contact_info=contact or None,
        is_active=True,
    )
    db.add(client)
    await db.flush()
    return client


def _apply_status(order: Order, payload: NetOrderIn, occurred_at: datetime):
    st = payload.status
    order.cargo_status = st.code
    order.cargo_status_label = st.label
    order.cargo_status_at = occurred_at
    mapped = _LIFECYCLE_TO_STATUS.get((st.lifecycle or "active").lower())
    if mapped:
        order.status = mapped


async def _add_event(db: AsyncSession, order: Order, payload: NetOrderIn, occurred_at: datetime):
    st = payload.status
    exists = (await db.execute(
        select(NetStatusEvent.id).where(
            NetStatusEvent.order_id == order.id,
            NetStatusEvent.code == st.code,
            NetStatusEvent.occurred_at == occurred_at,
        )
    )).scalar_one_or_none()
    if exists:
        return
    db.add(NetStatusEvent(
        id=uuid.uuid4(),
        order_id=order.id,
        code=st.code,
        label=st.label,
        lifecycle=st.lifecycle,
        occurred_at=occurred_at,
    ))


async def upsert_net_order(db: AsyncSession, payload: NetOrderIn) -> dict:
    """Идемпотентный upsert NET-заказа. Возвращает {ok, external_ref, order_number, created}."""
    external_ref = payload.external_ref.strip()
    occurred_at = payload.occurred_at or datetime.now(timezone.utc)

    # 1. business_type
    bt = (await db.execute(
        select(BusinessType).where(BusinessType.code == payload.business_type)
    )).scalar_one_or_none()
    if not bt:
        raise NetUpsertError(f"unknown business_type '{payload.business_type}'")

    # 2. существующий заказ?
    order = (await db.execute(
        select(Order).where(Order.external_ref == external_ref, Order.source == "net")
    )).scalar_one_or_none()

    if order is not None:
        _apply_status(order, payload, occurred_at)
        if payload.tracking_number:
            order.tracking_number = payload.tracking_number
        await db.flush()
        await _add_event(db, order, payload, occurred_at)
        await db.commit()
        return {"ok": True, "external_ref": external_ref,
                "order_number": order.order_number, "created": False}

    # 3. создать
    company = await _get_company(db)
    system_user = await _get_system_user(db)
    client = await _resolve_client(db, payload, company)

    order = Order(
        id=uuid.uuid4(),
        order_number=f"NET-{external_ref}",
        company_id=company.id,
        client_id=client.id,
        business_type_id=bt.id,
        manager_id=system_user.id,
        created_by=system_user.id,
        order_date=occurred_at.date(),
        status=OrderStatus.active,
        client_currency=OrderCurrencyEnum.CNY,
        total_sale_cny=Decimal("0"),
        total_cost_cny=Decimal("0"),
        notes=payload.description,
        tracking_number=payload.tracking_number,
        source="net",
        external_ref=external_ref,
        excluded_from_accounting=True,
    )
    _apply_status(order, payload, occurred_at)
    db.add(order)
    try:
        await db.flush()
    except IntegrityError:
        # гонка: заказ уже создан параллельным пушем — перезагрузим и обновим
        await db.rollback()
        order = (await db.execute(
            select(Order).where(Order.external_ref == external_ref, Order.source == "net")
        )).scalar_one_or_none()
        if order is None:
            raise NetUpsertError("upsert race, retry")
        _apply_status(order, payload, occurred_at)
        await db.flush()
        await _add_event(db, order, payload, occurred_at)
        await db.commit()
        return {"ok": True, "external_ref": external_ref,
                "order_number": order.order_number, "created": False}

    await _add_event(db, order, payload, occurred_at)
    await db.commit()
    return {"ok": True, "external_ref": external_ref,
            "order_number": order.order_number, "created": True}


# ── Агрегатная отправка (WH → ERP) ──────────────────────────────────────────────

async def _get_or_create_retail_client(db: AsyncSession) -> Counterparty:
    """Служебный контрагент NET-RETAIL для агрегатных заказов-отправок."""
    c = (await db.execute(
        select(Counterparty).where(Counterparty.code == RETAIL_CLIENT_CODE)
    )).scalars().first()
    if c:
        return c
    c = Counterparty(
        id=uuid.uuid4(),
        name=RETAIL_CLIENT_NAME,
        code=RETAIL_CLIENT_CODE,
        type=CounterpartyType.client,
        default_currency=CurrencyEnum.RUB,
        is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


def _shipment_notes(payload: NetShipmentIn) -> str:
    boxes_n = payload.boxes_count if payload.boxes_count is not None else len(payload.boxes)
    head = f"Отправка {payload.shipment_ref} · коробок: {boxes_n}"
    if payload.parcels_count is not None:
        head += f" · посылок: {payload.parcels_count}"
    if payload.total_weight_kg is not None:
        head += f" · вес: {payload.total_weight_kg} кг"
    lines = [head]
    if payload.destinations:
        lines.append("Города: " + ", ".join(payload.destinations))
    for b in payload.boxes:
        parts = [b.box_code or "?", b.city or "—"]
        if b.weight_kg is not None:
            parts.append(f"{b.weight_kg} кг")
        if b.parcels_count is not None:
            parts.append(f"{b.parcels_count} посылок")
        if b.paid_rub is not None:
            parts.append(f"{b.paid_rub} ₽")
        lines.append("— " + " · ".join(str(p) for p in parts))
    return "\n".join(lines)


async def upsert_net_shipment(db: AsyncSession, payload: NetShipmentIn) -> dict:
    """Идемпотентный upsert агрегатного заказа-отправки по shipment_ref.

    Один обычный логистический заказ (business_type=logistics), в учёте (деньги реальные).
    Наружу (irsway_site) не пушим.
    """
    ref = payload.shipment_ref.strip()
    created_at = payload.created_at or datetime.now(timezone.utc)
    revenue = Decimal(str(payload.total_paid_rub or 0)).quantize(Decimal("0.01"))
    notes = _shipment_notes(payload)

    bt = (await db.execute(
        select(BusinessType).where(BusinessType.code == "logistics")
    )).scalar_one_or_none()
    if not bt:
        raise NetUpsertError("business_type 'logistics' not found")

    order = (await db.execute(
        select(Order).where(Order.external_ref == ref, Order.source == "net")
    )).scalar_one_or_none()

    if order is not None:
        order.total_sale_cny = revenue
        order.notes = notes
        order.tracking_number = ref
        order.excluded_from_accounting = False
        await db.commit()
        return {"ok": True, "shipment_ref": ref,
                "erp_order_number": order.order_number, "created": False}

    company = await _get_company(db)
    system_user = await _get_system_user(db)
    client = await _get_or_create_retail_client(db)

    order = Order(
        id=uuid.uuid4(),
        order_number=f"NET-{ref}",
        company_id=company.id,
        client_id=client.id,
        business_type_id=bt.id,
        manager_id=system_user.id,
        created_by=system_user.id,
        order_date=created_at.date(),
        status=OrderStatus.active,
        client_currency=OrderCurrencyEnum.RUB,
        total_sale_cny=revenue,
        total_cost_cny=Decimal("0"),
        notes=notes,
        tracking_number=ref,
        source="net",
        external_ref=ref,
        excluded_from_accounting=False,
    )
    db.add(order)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        order = (await db.execute(
            select(Order).where(Order.external_ref == ref, Order.source == "net")
        )).scalar_one_or_none()
        if order is None:
            raise NetUpsertError("upsert race, retry")
        order.total_sale_cny = revenue
        order.notes = notes
        order.excluded_from_accounting = False
        await db.commit()
        return {"ok": True, "shipment_ref": ref,
                "erp_order_number": order.order_number, "created": False}

    await db.commit()
    return {"ok": True, "shipment_ref": ref,
            "erp_order_number": order.order_number, "created": True}
