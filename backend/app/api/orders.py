import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_item import OrderItem
from app.models.counterparty import Counterparty, CounterpartyType
from app.models.business_type import BusinessType
from app.models.exchange_rate import ExchangeRate
from app.models.company import Company
from app.models.audit_log import AuditActionEnum
from app.schemas.order import (
    OrderCreate, OrderUpdate, OrderResponse, OrderListItem,
    OrderListResponse, OrderItemResponse,
)
from app.utils.audit import write_audit

router = APIRouter(prefix="/api/orders", tags=["orders"])


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_default_company(db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.is_active == True).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(400, "No active company found")
    return company


async def _get_rates(db: AsyncSession, order_date: date, currencies: set[str]) -> dict[str, Decimal]:
    rates: dict[str, Decimal] = {"CNY": Decimal("1")}
    missing = []
    for currency in currencies:
        if currency == "CNY":
            continue
        result = await db.execute(
            select(ExchangeRate)
            .where(ExchangeRate.currency == currency, ExchangeRate.rate_date == order_date)
        )
        rate = result.scalar_one_or_none()
        if not rate:
            missing.append(currency)
        else:
            rates[currency] = rate.rate_to_cny
    if missing:
        raise HTTPException(422, f"Exchange rates missing for {', '.join(missing)} on {order_date}")
    return rates


async def _load_order_detail(db: AsyncSession, order_id: uuid.UUID) -> OrderResponse:
    ClientAlias = aliased(Counterparty)
    ManagerAlias = aliased(User)

    stmt = (
        select(
            Order,
            ClientAlias.name.label("client_name"),
            ManagerAlias.full_name.label("manager_name"),
            BusinessType.name.label("business_type_name"),
            BusinessType.name_cn.label("business_type_name_cn"),
            BusinessType.code.label("business_type_code"),
        )
        .join(ClientAlias, Order.client_id == ClientAlias.id)
        .join(ManagerAlias, Order.manager_id == ManagerAlias.id)
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .where(Order.id == order_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(404, "Order not found")
    order = row[0]

    # Load items with supplier names
    items_stmt = (
        select(OrderItem, Counterparty.name.label("supplier_name"))
        .outerjoin(Counterparty, OrderItem.supplier_id == Counterparty.id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id)
    )
    item_rows = (await db.execute(items_stmt)).all()
    items = [
        OrderItemResponse(
            id=r[0].id,
            name=r[0].name,
            name_cn=r[0].name_cn,
            quantity=r[0].quantity,
            unit=r[0].unit,
            cost_price=r[0].cost_price,
            cost_currency=r[0].cost_currency,
            supplier_id=r[0].supplier_id,
            supplier_name=r[1],
            sale_price=r[0].sale_price,
            sale_currency=r[0].sale_currency,
            sale_rate_to_cny=r[0].sale_rate_to_cny,
            cost_rate_to_cny=r[0].cost_rate_to_cny,
        )
        for r in item_rows
    ]

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        order_date=order.order_date,
        client_id=order.client_id,
        client_name=row.client_name,
        business_type_id=order.business_type_id,
        business_type_name=row.business_type_name,
        business_type_name_cn=row.business_type_name_cn,
        business_type_code=row.business_type_code,
        manager_id=order.manager_id,
        manager_name=row.manager_name,
        status=order.status,
        client_currency=order.client_currency,
        total_sale_cny=order.total_sale_cny,
        total_cost_cny=order.total_cost_cny,
        payment_status=order.payment_status,
        supplier_payment_status=order.supplier_payment_status,
        notes=order.notes,
        created_at=order.created_at,
        items=items,
    )


def _calc_totals(items_data, rates: dict[str, Decimal]) -> tuple[Decimal, Decimal]:
    total_sale = Decimal("0")
    total_cost = Decimal("0")
    for item in items_data:
        sr = rates.get(item.sale_currency, Decimal("1"))
        cr = rates.get(item.cost_currency, Decimal("1"))
        total_sale += item.quantity * item.sale_price * sr
        total_cost += item.quantity * item.cost_price * cr
    return total_sale.quantize(Decimal("0.01")), total_cost.quantize(Decimal("0.01"))


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/next-number")
async def get_next_number(
    order_date: date = Query(alias="date"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    prefix = f"ORD-{order_date.strftime('%Y%m%d')}-"
    count = (await db.execute(
        select(func.count(Order.id)).where(Order.order_number.like(f"{prefix}%"))
    )).scalar_one()
    return {"order_number": f"{prefix}{count + 1:04d}"}


@router.get("", response_model=OrderListResponse)
async def list_orders(
    search: Optional[str] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    business_type_id: Optional[uuid.UUID] = Query(None),
    order_status: Optional[str] = Query(None, alias="status"),
    manager_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ClientAlias = aliased(Counterparty)
    ManagerAlias = aliased(User)

    stmt = (
        select(
            Order.id, Order.order_number, Order.order_date, Order.status,
            Order.client_currency, Order.total_sale_cny, Order.total_cost_cny,
            Order.payment_status, Order.supplier_payment_status,
            Order.client_id, Order.business_type_id, Order.manager_id,
            ClientAlias.name.label("client_name"),
            ManagerAlias.full_name.label("manager_name"),
            BusinessType.name.label("business_type_name"),
            BusinessType.code.label("business_type_code"),
        )
        .join(ClientAlias, Order.client_id == ClientAlias.id)
        .join(ManagerAlias, Order.manager_id == ManagerAlias.id)
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .where(Order.status != OrderStatus.cancelled)
    )

    if search:
        stmt = stmt.where(Order.order_number.ilike(f"%{search}%"))
    if client_id:
        stmt = stmt.where(Order.client_id == client_id)
    if business_type_id:
        stmt = stmt.where(Order.business_type_id == business_type_id)
    if order_status:
        stmt = stmt.where(Order.status == order_status)
    if manager_id:
        stmt = stmt.where(Order.manager_id == manager_id)
    if date_from:
        stmt = stmt.where(Order.order_date >= date_from)
    if date_to:
        stmt = stmt.where(Order.order_date <= date_to)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    stmt = stmt.order_by(Order.order_date.desc(), Order.order_number.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    items = [
        OrderListItem(
            id=r.id, order_number=r.order_number, order_date=r.order_date,
            client_id=r.client_id, client_name=r.client_name,
            business_type_id=r.business_type_id, business_type_name=r.business_type_name,
            business_type_code=r.business_type_code,
            manager_id=r.manager_id, manager_name=r.manager_name,
            status=r.status, client_currency=r.client_currency,
            total_sale_cny=r.total_sale_cny, total_cost_cny=r.total_cost_cny,
            payment_status=r.payment_status,
            supplier_payment_status=r.supplier_payment_status,
        )
        for r in rows
    ]

    page_sale = sum(r.total_sale_cny for r in rows) or Decimal("0")
    page_cost = sum(r.total_cost_cny for r in rows) or Decimal("0")

    return OrderListResponse(
        items=items, total=total, page=page, page_size=page_size,
        page_total_sale_cny=page_sale, page_total_cost_cny=page_cost,
    )


@router.get("/{order_id}/history")
async def get_order_history(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.models.audit_log import AuditLog
    result = await db.execute(
        select(AuditLog, User.full_name.label("user_name"))
        .join(User, AuditLog.user_id == User.id)
        .where(AuditLog.entity_type == "order", AuditLog.entity_id == order_id)
        .order_by(AuditLog.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(r[0].id),
            "action": r[0].action,
            "user_name": r[1],
            "changes": r[0].changes,
            "created_at": r[0].created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await _load_order_detail(db, order_id)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = await _get_default_company(db)

    # Validate uniqueness
    if (await db.execute(select(Order.id).where(Order.order_number == body.order_number))).scalar_one_or_none():
        raise HTTPException(409, f"Order number '{body.order_number}' already exists")

    # Validate client
    client_result = await db.execute(select(Counterparty).where(Counterparty.id == body.client_id))
    client = client_result.scalar_one_or_none()
    if not client or client.type not in (CounterpartyType.client, CounterpartyType.both):
        raise HTTPException(422, "Client must be a counterparty of type 'client' or 'both'")

    # Collect currencies for exchange rate lookup
    needed_currencies = {item.sale_currency for item in body.items if item.sale_currency != "CNY"}
    needed_currencies |= {item.cost_currency for item in body.items if item.cost_currency != "CNY"}
    rates = await _get_rates(db, body.order_date, needed_currencies)

    total_sale, total_cost = _calc_totals(body.items, rates)

    order = Order(
        id=uuid.uuid4(),
        order_number=body.order_number,
        company_id=company.id,
        client_id=body.client_id,
        business_type_id=body.business_type_id,
        manager_id=body.manager_id,
        order_date=body.order_date,
        status=OrderStatus.new,
        client_currency=body.client_currency,
        total_sale_cny=total_sale,
        total_cost_cny=total_cost,
        payment_status=PaymentStatus.unpaid,
        supplier_payment_status=PaymentStatus.unpaid,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(order)
    await db.flush()

    for item_data in body.items:
        db.add(OrderItem(
            id=uuid.uuid4(),
            order_id=order.id,
            name=item_data.name,
            name_cn=item_data.name_cn,
            quantity=item_data.quantity,
            unit=item_data.unit,
            cost_price=item_data.cost_price,
            cost_currency=item_data.cost_currency,
            supplier_id=item_data.supplier_id,
            sale_price=item_data.sale_price,
            sale_currency=item_data.sale_currency,
            sale_rate_to_cny=rates.get(item_data.sale_currency, Decimal("1")),
            cost_rate_to_cny=rates.get(item_data.cost_currency, Decimal("1")),
        ))

    await write_audit(db, current_user.id, "order", order.id, AuditActionEnum.create,
                      {"order_number": order.order_number, "total_sale_cny": str(total_sale)})
    await db.commit()
    return await _load_order_detail(db, order.id)


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: uuid.UUID,
    body: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == OrderStatus.closed and current_user.role != UserRole.admin:
        raise HTTPException(403, "Only admin can modify a closed order")

    old_data = {"order_number": order.order_number, "status": order.status}
    update_data = body.model_dump(exclude_unset=True)

    if "items" in update_data:
        items_data = update_data.pop("items") or []
        # Delete existing items
        existing = (await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))).scalars().all()
        for item in existing:
            await db.delete(item)
        await db.flush()

        # Determine order_date for rate lookup
        order_date = update_data.get("order_date", order.order_date)
        needed_currencies = {i["sale_currency"] for i in items_data if i.get("sale_currency", "CNY") != "CNY"}
        needed_currencies |= {i["cost_currency"] for i in items_data if i.get("cost_currency", "CNY") != "CNY"}
        rates = await _get_rates(db, order_date, needed_currencies)

        for item_data in items_data:
            from app.schemas.order import OrderItemCreate
            item = OrderItemCreate(**item_data) if isinstance(item_data, dict) else item_data
            db.add(OrderItem(
                id=uuid.uuid4(),
                order_id=order_id,
                name=item.name, name_cn=item.name_cn,
                quantity=item.quantity, unit=item.unit,
                cost_price=item.cost_price, cost_currency=item.cost_currency,
                supplier_id=item.supplier_id,
                sale_price=item.sale_price, sale_currency=item.sale_currency,
                sale_rate_to_cny=rates.get(item.sale_currency, Decimal("1")),
                cost_rate_to_cny=rates.get(item.cost_currency, Decimal("1")),
            ))

        await db.flush()
        # Recalculate totals
        new_items = (await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))).scalars().all()
        total_sale = sum(i.quantity * i.sale_price * i.sale_rate_to_cny for i in new_items)
        total_cost = sum(i.quantity * i.cost_price * i.cost_rate_to_cny for i in new_items)
        order.total_sale_cny = Decimal(str(total_sale)).quantize(Decimal("0.01"))
        order.total_cost_cny = Decimal(str(total_cost)).quantize(Decimal("0.01"))

    for field, value in update_data.items():
        setattr(order, field, value)

    await write_audit(db, current_user.id, "order", order.id, AuditActionEnum.update,
                      {"old": old_data, "total_sale_cny": str(order.total_sale_cny)})
    await db.commit()
    return await _load_order_detail(db, order.id)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = OrderStatus.cancelled
    await write_audit(db, current_user.id, "order", order.id, AuditActionEnum.delete,
                      {"order_number": order.order_number})
    await db.commit()


@router.post("/{order_id}/close", response_model=OrderResponse)
async def close_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status not in (OrderStatus.new, OrderStatus.active):
        raise HTTPException(422, f"Cannot close order with status '{order.status}'")
    if current_user.role not in (UserRole.admin, UserRole.manager):
        raise HTTPException(403, "Only admin or manager can close orders")

    order.status = OrderStatus.closed
    await write_audit(db, current_user.id, "order", order.id, AuditActionEnum.update,
                      {"status": "closed"})
    await db.commit()
    return await _load_order_detail(db, order.id)
