import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, not_, and_
from sqlalchemy.orm import aliased

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_item import OrderItem
from app.models.order_item_photo import OrderItemPhoto
from app.models.order_charge import OrderCharge
from app.models.counterparty import Counterparty, CounterpartyType
from app.models.business_type import BusinessType
from app.models.exchange_rate import ExchangeRate
from app.models.company import Company
from app.models.purchase_item import PurchaseItem
from app.models.purchase import Purchase
from app.models.payment import Payment
from app.models.payment_allocation import PaymentAllocation
from app.models.expense import Expense
from app.models.audit_log import AuditActionEnum
from app.models.warehouse import Warehouse
from app.schemas.order import (
    OrderCreate, OrderUpdate, OrderListItem, OrderListResponse,
    OrderChargeResponse, OrderItemResponseManager, OrderItemResponseFull,
    OrderItemPhotoResponse, OrderResponseManager, OrderResponseFull,
    PurchaseItemBrief, AvailableForPurchaseItem,
)
from app.utils.audit import write_audit
from app.integrations.irsway_site.service import sync_order_to_site
from app.services.notifications import notify_role, notify

router = APIRouter(prefix="/api/orders", tags=["orders"])

_PURCHASER_ROLES = ("purchaser", "accountant", "admin")
_ALL_EXCEPT_EMPLOYEE = ("manager", "purchaser", "accountant", "admin")


# ── helpers ───────────────────────────────────────────────────────────────────

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


async def _load_order_detail(
    db: AsyncSession, order_id: uuid.UUID, user: User
) -> Union[OrderResponseManager, OrderResponseFull]:
    is_manager_only = user.has_role("manager") and not user.has_role(*_PURCHASER_ROLES)

    ClientAlias = aliased(Counterparty)
    ManagerAlias = aliased(User)
    WarehouseAlias = aliased(Warehouse)

    stmt = (
        select(
            Order,
            ClientAlias.name.label("client_name"),
            ManagerAlias.full_name.label("manager_name"),
            BusinessType.name.label("business_type_name"),
            BusinessType.name_cn.label("business_type_name_cn"),
            BusinessType.code.label("business_type_code"),
            WarehouseAlias.name.label("warehouse_name"),
        )
        .join(ClientAlias, Order.client_id == ClientAlias.id)
        .join(ManagerAlias, Order.manager_id == ManagerAlias.id)
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .outerjoin(WarehouseAlias, Order.warehouse_id == WarehouseAlias.id)
        .where(Order.id == order_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(404, "Order not found")
    order = row[0]

    paid_row = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(PaymentAllocation.order_id == order_id, Payment.is_active == True)
    )
    paid_cny = paid_row.scalar_one() or Decimal("0")
    remaining_cny = max((order.total_sale_cny or Decimal("0")) - paid_cny, Decimal("0"))

    # client phone from contact_info
    client_row = (await db.execute(select(Counterparty).where(Counterparty.id == order.client_id))).scalar_one_or_none()
    client_phone = None
    if client_row and client_row.contact_info and isinstance(client_row.contact_info, dict):
        client_phone = client_row.contact_info.get("phone")

    # Items with preferred_supplier names
    PreferredAlias = aliased(Counterparty)
    items_stmt = (
        select(OrderItem, PreferredAlias.name.label("preferred_supplier_name"))
        .outerjoin(PreferredAlias, OrderItem.preferred_supplier_id == PreferredAlias.id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id)
    )
    item_rows = (await db.execute(items_stmt)).all()

    # Photos per order item
    item_ids = [r[0].id for r in item_rows]
    photos_by_item: dict[uuid.UUID, list] = {}
    if item_ids:
        photo_rows = (await db.execute(
            select(OrderItemPhoto)
            .where(OrderItemPhoto.order_item_id.in_(item_ids))
            .order_by(OrderItemPhoto.order_item_id, OrderItemPhoto.sort_order, OrderItemPhoto.uploaded_at)
        )).scalars().all()
        for ph in photo_rows:
            photos_by_item.setdefault(ph.order_item_id, []).append(
                OrderItemPhotoResponse(
                    id=ph.id, file_url=ph.file_url, file_name=ph.file_name,
                    file_size_bytes=ph.file_size_bytes, mime_type=ph.mime_type,
                    sort_order=ph.sort_order, uploaded_at=ph.uploaded_at,
                )
            )

    # Charges
    charge_rows = (await db.execute(
        select(OrderCharge).where(OrderCharge.order_id == order_id).order_by(OrderCharge.id)
    )).scalars().all()
    charges = [
        OrderChargeResponse(
            id=c.id, charge_type=c.charge_type, amount=c.amount, currency=c.currency,
            amount_cny=c.amount_cny, rate_to_cny=c.rate_to_cny, notes=c.notes,
        )
        for c in charge_rows
    ]

    if is_manager_only:
        items = [
            OrderItemResponseManager(
                id=r[0].id, name=r[0].name, name_cn=r[0].name_cn,
                model=r[0].model, specification=r[0].specification,
                quantity=r[0].quantity, unit=r[0].unit,
                preferred_supplier_id=r[0].preferred_supplier_id,
                preferred_supplier_name=r[1],
                sale_price=r[0].sale_price, sale_currency=r[0].sale_currency,
                sale_rate_to_cny=r[0].sale_rate_to_cny,
                weight_kg=r[0].weight_kg, volume_m3=r[0].volume_m3,
                density_kg_m3=r[0].density_kg_m3,
                price_per_kg=r[0].price_per_kg, price_per_kg_currency=r[0].price_per_kg_currency,
                cargo_value=r[0].cargo_value, cargo_value_currency=r[0].cargo_value_currency,
                places_count=r[0].places_count,
                photos=photos_by_item.get(r[0].id, []),
            )
            for r in item_rows
        ]
        return OrderResponseManager(
            id=order.id, order_number=order.order_number, order_date=order.order_date,
            client_id=order.client_id, client_name=row.client_name,
            client_phone=client_phone,
            business_type_id=order.business_type_id, business_type_name=row.business_type_name,
            business_type_name_cn=row.business_type_name_cn, business_type_code=row.business_type_code,
            manager_id=order.manager_id, manager_name=row.manager_name,
            status=order.status, client_currency=order.client_currency,
            total_sale_cny=order.total_sale_cny,
            payment_status=order.payment_status,
            paid_amount_cny=paid_cny,
            remaining_amount_cny=remaining_cny,
            notes=order.notes, recipient=order.recipient, destination=order.destination,
            arrival_date=order.arrival_date, tracking_number=order.tracking_number,
            warehouse_id=order.warehouse_id, warehouse_name=row.warehouse_name,
            created_at=order.created_at, items=items, charges=charges,
            external_shipment_id=order.external_shipment_id,
            external_shipment_number=order.external_shipment_number,
            external_invoice_url=order.external_invoice_url,
            external_tracking_url=order.external_tracking_url,
            sync_status=order.sync_status,
            sync_error=order.sync_error,
            synced_at=order.synced_at,
        )

    # Purchaser/accountant/admin — load purchase_items per order_item
    purchase_item_rows = []
    if item_ids:
        pi_stmt = (
            select(PurchaseItem, Purchase.purchase_number)
            .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
            .where(PurchaseItem.order_item_id.in_(item_ids), Purchase.is_deleted == False)
        )
        purchase_item_rows = (await db.execute(pi_stmt)).all()

    # Group purchase_items by order_item_id
    pi_by_item: dict[uuid.UUID, list] = {}
    for pi_row in purchase_item_rows:
        oi_id = pi_row[0].order_item_id
        pi_by_item.setdefault(oi_id, []).append(pi_row)

    items = [
        OrderItemResponseFull(
            id=r[0].id, name=r[0].name, name_cn=r[0].name_cn,
            model=r[0].model, specification=r[0].specification,
            quantity=r[0].quantity, unit=r[0].unit,
            preferred_supplier_id=r[0].preferred_supplier_id,
            preferred_supplier_name=r[1],
            sale_price=r[0].sale_price, sale_currency=r[0].sale_currency,
            sale_rate_to_cny=r[0].sale_rate_to_cny,
            weight_kg=r[0].weight_kg, volume_m3=r[0].volume_m3,
            density_kg_m3=r[0].density_kg_m3,
            price_per_kg=r[0].price_per_kg, price_per_kg_currency=r[0].price_per_kg_currency,
            cargo_value=r[0].cargo_value, cargo_value_currency=r[0].cargo_value_currency,
            places_count=r[0].places_count,
            purchased_quantity=sum(
                pi[0].quantity for pi in pi_by_item.get(r[0].id, [])
            ) or Decimal("0"),
            purchase_items=[
                PurchaseItemBrief(
                    id=pi[0].id, purchase_id=pi[0].purchase_id,
                    purchase_number=pi[1],
                    quantity=pi[0].quantity, cost_price=pi[0].cost_price,
                    cost_amount=pi[0].cost_amount,
                )
                for pi in pi_by_item.get(r[0].id, [])
            ],
            photos=photos_by_item.get(r[0].id, []),
        )
        for r in item_rows
    ]

    expenses_row = await db.execute(
        select(func.coalesce(func.sum(Expense.amount_cny), Decimal("0")))
        .where(
            Expense.order_id == order_id,
            Expense.is_active == True,
            not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
        )
    )
    expenses_cny = expenses_row.scalar_one() or Decimal("0")

    return OrderResponseFull(
        id=order.id, order_number=order.order_number, order_date=order.order_date,
        client_id=order.client_id, client_name=row.client_name,
        client_phone=client_phone,
        business_type_id=order.business_type_id, business_type_name=row.business_type_name,
        business_type_name_cn=row.business_type_name_cn, business_type_code=row.business_type_code,
        manager_id=order.manager_id, manager_name=row.manager_name,
        status=order.status, client_currency=order.client_currency,
        total_sale_cny=order.total_sale_cny, total_cost_cny=order.total_cost_cny,
        expenses_cny=expenses_cny,
        payment_status=order.payment_status, supplier_payment_status=order.supplier_payment_status,
        paid_amount_cny=paid_cny,
        remaining_amount_cny=remaining_cny,
        notes=order.notes, recipient=order.recipient, destination=order.destination,
        arrival_date=order.arrival_date, tracking_number=order.tracking_number,
        warehouse_id=order.warehouse_id, warehouse_name=row.warehouse_name,
        created_at=order.created_at, items=items, charges=charges,
        external_shipment_id=order.external_shipment_id,
        external_shipment_number=order.external_shipment_number,
        external_invoice_url=order.external_invoice_url,
        external_tracking_url=order.external_tracking_url,
        sync_status=order.sync_status,
        sync_error=order.sync_error,
        synced_at=order.synced_at,
    )


def _collect_currencies(items_data, charges_data) -> set[str]:
    needed: set[str] = set()
    for item in items_data:
        for field in (item.sale_currency, item.price_per_kg_currency, item.cargo_value_currency):
            if field and field != "CNY":
                needed.add(field)
    for charge in charges_data:
        if charge.currency and charge.currency != "CNY":
            needed.add(charge.currency)
    return needed


def _calc_trade_totals(items_data, rates: dict[str, Decimal]) -> Decimal:
    """Returns total_sale_cny only. Cost is now tracked via purchase_items."""
    total_sale = Decimal("0")
    for item in items_data:
        if item.quantity is None:
            continue
        sr = rates.get(item.sale_currency or "CNY", Decimal("1"))
        total_sale += (item.quantity * (item.sale_price or Decimal("0"))) * sr
    return total_sale.quantize(Decimal("0.01"))


def _calc_logistics_totals(items_data, charges_data, rates: dict[str, Decimal]) -> Decimal:
    total_sale = Decimal("0")
    for item in items_data:
        if item.weight_kg and item.price_per_kg:
            r = rates.get(item.price_per_kg_currency or "CNY", Decimal("1"))
            total_sale += item.weight_kg * item.price_per_kg * r
    for charge in charges_data:
        r = rates.get(charge.currency or "CNY", Decimal("1"))
        total_sale += charge.amount * r
    return total_sale.quantize(Decimal("0.01"))


async def _save_items_and_charges(
    db: AsyncSession, order_id: uuid.UUID, order_date: date,
    items_data, charges_data, is_logistics: bool,
) -> dict[str, Decimal]:
    rates = await _get_rates(db, order_date, _collect_currencies(items_data, charges_data))

    for item_data in items_data:
        density = None
        if item_data.weight_kg and item_data.volume_m3 and item_data.volume_m3 != 0:
            density = (item_data.weight_kg / item_data.volume_m3).quantize(Decimal("0.01"))

        db.add(OrderItem(
            id=uuid.uuid4(),
            order_id=order_id,
            name=item_data.name, name_cn=item_data.name_cn,
            model=getattr(item_data, "model", None) if not is_logistics else None,
            specification=getattr(item_data, "specification", None) if not is_logistics else None,
            quantity=item_data.quantity, unit=item_data.unit,
            preferred_supplier_id=item_data.preferred_supplier_id,
            sale_price=item_data.sale_price, sale_currency=item_data.sale_currency,
            sale_rate_to_cny=rates.get(item_data.sale_currency or "CNY", Decimal("1")) if item_data.sale_currency else None,
            weight_kg=item_data.weight_kg, volume_m3=item_data.volume_m3, density_kg_m3=density,
            price_per_kg=item_data.price_per_kg, price_per_kg_currency=item_data.price_per_kg_currency,
            cargo_value=item_data.cargo_value, cargo_value_currency=item_data.cargo_value_currency,
            places_count=item_data.places_count,
        ))

    for charge_data in charges_data:
        r = rates.get(charge_data.currency or "CNY", Decimal("1"))
        db.add(OrderCharge(
            id=uuid.uuid4(), order_id=order_id,
            charge_type=charge_data.charge_type, amount=charge_data.amount,
            currency=charge_data.currency,
            amount_cny=(charge_data.amount * r).quantize(Decimal("0.01")),
            rate_to_cny=r, notes=charge_data.notes,
        ))

    return rates


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/next-number")
async def get_next_number(
    order_date: date = Query(alias="date"),
    business_type_code: Optional[str] = Query(None),
    client_code: Optional[str] = Query(None),
    places_count: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALL_EXCEPT_EMPLOYEE)),
):
    ddmm = order_date.strftime("%d%m")
    if business_type_code == "logistics":
        code = client_code or "XXX"
        places = places_count or 0
        return {"order_number": f"IRS-{code}-{ddmm}-{places}"}
    else:
        yyyy = order_date.strftime("%Y")
        prefix = f"PI{yyyy}{ddmm}-"
        count = (await db.execute(
            select(func.count(Order.id)).where(Order.order_number.like(f"{prefix}%"))
        )).scalar_one()
        return {"order_number": f"{prefix}{count + 1}"}


@router.get("", response_model=OrderListResponse)
async def list_orders(
    search: Optional[str] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    business_type_id: Optional[uuid.UUID] = Query(None),
    order_status: Optional[str] = Query(None, alias="status"),
    manager_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    sync_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALL_EXCEPT_EMPLOYEE)),
):
    is_full = current_user.has_role(*_PURCHASER_ROLES)

    ClientAlias = aliased(Counterparty)
    ManagerAlias = aliased(User)

    paid_sq = (
        select(
            PaymentAllocation.order_id,
            func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")).label("paid_cny"),
        )
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(Payment.is_active == True)
        .group_by(PaymentAllocation.order_id)
        .subquery()
    )

    stmt = (
        select(
            Order.id, Order.order_number, Order.order_date, Order.status,
            Order.client_currency, Order.total_sale_cny, Order.total_cost_cny,
            Order.payment_status, Order.supplier_payment_status,
            Order.client_id, Order.business_type_id, Order.manager_id,
            Order.sync_status,
            ClientAlias.name.label("client_name"),
            ManagerAlias.full_name.label("manager_name"),
            BusinessType.name.label("business_type_name"),
            BusinessType.name_cn.label("business_type_name_cn"),
            BusinessType.code.label("business_type_code"),
            func.coalesce(paid_sq.c.paid_cny, Decimal("0")).label("paid_amount_cny"),
        )
        .join(ClientAlias, Order.client_id == ClientAlias.id)
        .join(ManagerAlias, Order.manager_id == ManagerAlias.id)
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .outerjoin(paid_sq, Order.id == paid_sq.c.order_id)
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
    if sync_status:
        stmt = stmt.where(Order.sync_status == sync_status)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Order.order_date.desc(), Order.order_number.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    items = [
        OrderListItem(
            id=r.id, order_number=r.order_number, order_date=r.order_date,
            client_id=r.client_id, client_name=r.client_name,
            business_type_id=r.business_type_id, business_type_name=r.business_type_name,
            business_type_name_cn=r.business_type_name_cn,
            business_type_code=r.business_type_code,
            manager_id=r.manager_id, manager_name=r.manager_name,
            status=r.status, client_currency=r.client_currency,
            total_sale_cny=r.total_sale_cny,
            total_cost_cny=r.total_cost_cny if is_full else None,
            payment_status=r.payment_status,
            supplier_payment_status=r.supplier_payment_status if is_full else None,
            paid_amount_cny=r.paid_amount_cny or Decimal("0"),
            remaining_amount_cny=max(r.total_sale_cny - (r.paid_amount_cny or Decimal("0")), Decimal("0")),
            sync_status=r.sync_status,
        )
        for r in rows
    ]

    page_sale = sum(r.total_sale_cny for r in rows) or Decimal("0")
    page_cost = (sum(r.total_cost_cny for r in rows) or Decimal("0")) if is_full else None

    return OrderListResponse(
        items=items, total=total, page=page, page_size=page_size,
        page_total_sale_cny=page_sale, page_total_cost_cny=page_cost,
    )


@router.get("/{order_id}/available-for-purchase", response_model=list[AvailableForPurchaseItem])
async def get_available_for_purchase(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_PURCHASER_ROLES)),
):
    """Returns order items with remaining quantity available to purchase."""
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    PreferredAlias = aliased(Counterparty)
    items_stmt = (
        select(OrderItem, PreferredAlias.name.label("preferred_supplier_name"))
        .outerjoin(PreferredAlias, OrderItem.preferred_supplier_id == PreferredAlias.id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id)
    )
    item_rows = (await db.execute(items_stmt)).all()

    item_ids = [r[0].id for r in item_rows]
    already_purchased: dict[uuid.UUID, Decimal] = {}
    if item_ids:
        pi_rows = (await db.execute(
            select(PurchaseItem.order_item_id, func.sum(PurchaseItem.quantity).label("total_qty"))
            .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
            .where(PurchaseItem.order_item_id.in_(item_ids), Purchase.is_deleted == False)
            .group_by(PurchaseItem.order_item_id)
        )).all()
        for row in pi_rows:
            already_purchased[row[0]] = row[1] or Decimal("0")

    result = []
    for r in item_rows:
        item = r[0]
        if item.quantity is None:
            continue
        purchased = already_purchased.get(item.id, Decimal("0"))
        available = max(item.quantity - purchased, Decimal("0"))
        result.append(AvailableForPurchaseItem(
            id=item.id, name=item.name, name_cn=item.name_cn,
            quantity=item.quantity, unit=item.unit,
            sale_price=item.sale_price, sale_currency=item.sale_currency,
            preferred_supplier_id=item.preferred_supplier_id,
            preferred_supplier_name=r[1],
            already_purchased=purchased,
            available_to_purchase=available,
        ))
    return result


@router.get("/{order_id}/history")
async def get_order_history(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALL_EXCEPT_EMPLOYEE)),
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
            "id": str(r[0].id), "action": r[0].action, "user_name": r[1],
            "changes": r[0].changes, "created_at": r[0].created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/{order_id}")
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALL_EXCEPT_EMPLOYEE)),
):
    return await _load_order_detail(db, order_id, current_user)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALL_EXCEPT_EMPLOYEE)),
):
    company = await _get_default_company(db)

    if (await db.execute(select(Order.id).where(Order.order_number == body.order_number))).scalar_one_or_none():
        raise HTTPException(409, f"Order number '{body.order_number}' already exists")

    client = (await db.execute(select(Counterparty).where(Counterparty.id == body.client_id))).scalar_one_or_none()
    if not client or client.type not in (CounterpartyType.client, CounterpartyType.both):
        raise HTTPException(422, "Client must be counterparty of type 'client' or 'both'")

    bt = (await db.execute(select(BusinessType).where(BusinessType.id == body.business_type_id))).scalar_one_or_none()
    is_logistics = bt and bt.code == "logistics"

    order = Order(
        id=uuid.uuid4(),
        order_number=body.order_number,
        company_id=company.id,
        client_id=body.client_id,
        business_type_id=body.business_type_id,
        manager_id=current_user.id,  # always the creator, ignoring any input
        order_date=body.order_date,
        status=OrderStatus.new,
        client_currency=body.client_currency,
        total_sale_cny=Decimal("0"),
        total_cost_cny=Decimal("0"),
        payment_status=PaymentStatus.unpaid,
        supplier_payment_status=PaymentStatus.unpaid,
        notes=body.notes,
        recipient=body.recipient or (client.name if is_logistics else None),
        destination=body.destination,
        arrival_date=body.arrival_date,
        tracking_number=body.tracking_number,
        warehouse_id=body.warehouse_id,
        created_by=current_user.id,
    )
    db.add(order)
    await db.flush()

    rates = await _save_items_and_charges(db, order.id, body.order_date, body.items, body.charges, is_logistics)
    await db.flush()

    if is_logistics:
        total_sale = _calc_logistics_totals(body.items, body.charges, rates)
    else:
        total_sale = _calc_trade_totals(body.items, rates)

    order.total_sale_cny = total_sale
    order.total_cost_cny = Decimal("0")

    await write_audit(db, current_user.id, "order", order.id, AuditActionEnum.create,
                      {"order_number": order.order_number, "total_sale_cny": str(total_sale)})
    # Notify: accountant and admin about new order (except the creator)
    body_notif = f"{order.order_number} · {client.name}"
    link_notif = f"/orders/{order.id}"
    for role in ("accountant", "admin"):
        await notify_role(db, role, "order_created", "order_created", body_notif, link_notif,
                          "order", order.id, exclude_user_id=current_user.id)
    # Notify purchaser about new trade order to buy goods
    if bt and bt.code == "trade":
        await notify_role(db, "purchaser", "order_created", "order_created", body_notif, link_notif,
                          "order", order.id)
    await db.commit()

    if is_logistics:
        try:
            await sync_order_to_site(order, db)
            await db.commit()
        except Exception:
            pass

    return await _load_order_detail(db, order.id, current_user)


@router.patch("/{order_id}")
async def update_order(
    order_id: uuid.UUID,
    body: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALL_EXCEPT_EMPLOYEE)),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == OrderStatus.closed and not current_user.has_role("admin"):
        raise HTTPException(403, "Only admin can modify a closed order")

    old_data = {"order_number": order.order_number, "status": order.status}
    update_data = body.model_dump(exclude_unset=True)

    bt_id = update_data.get("business_type_id", order.business_type_id)
    bt = (await db.execute(select(BusinessType).where(BusinessType.id == bt_id))).scalar_one_or_none()
    is_logistics = bt and bt.code == "logistics"

    items_data = update_data.pop("items", None)
    charges_data = update_data.pop("charges", None)

    if items_data is not None or charges_data is not None:
        await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
        await db.execute(delete(OrderCharge).where(OrderCharge.order_id == order_id))
        await db.flush()

        from app.schemas.order import OrderItemCreate, OrderChargeCreate
        items_list = [OrderItemCreate(**i) if isinstance(i, dict) else i for i in (items_data or [])]
        charges_list = [OrderChargeCreate(**c) if isinstance(c, dict) else c for c in (charges_data or [])]

        order_date = update_data.get("order_date", order.order_date)
        rates = await _save_items_and_charges(db, order_id, order_date, items_list, charges_list, is_logistics)
        await db.flush()

        if is_logistics:
            order.total_sale_cny = _calc_logistics_totals(items_list, charges_list, rates)
        else:
            order.total_sale_cny = _calc_trade_totals(items_list, rates)

    for field, value in update_data.items():
        setattr(order, field, value)

    await write_audit(db, current_user.id, "order", order.id, AuditActionEnum.update,
                      {"old": old_data, "total_sale_cny": str(order.total_sale_cny)})
    await db.commit()

    if is_logistics:
        try:
            await sync_order_to_site(order, db)
            await db.commit()
        except Exception:
            pass

    return await _load_order_detail(db, order.id, current_user)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALL_EXCEPT_EMPLOYEE)),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = OrderStatus.cancelled
    await write_audit(db, current_user.id, "order", order.id, AuditActionEnum.delete,
                      {"order_number": order.order_number})
    await db.commit()


@router.post("/{order_id}/close")
async def close_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALL_EXCEPT_EMPLOYEE)),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status not in (OrderStatus.new, OrderStatus.active):
        raise HTTPException(422, f"Cannot close order with status '{order.status}'")
    if not current_user.has_role("admin", "manager"):
        raise HTTPException(403, "Only admin or manager can close orders")
    order.status = OrderStatus.closed
    await write_audit(db, current_user.id, "order", order.id, AuditActionEnum.update, {"status": "closed"})
    await db.commit()
    return await _load_order_detail(db, order.id, current_user)
