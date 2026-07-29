import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, or_
from sqlalchemy.orm import aliased
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.core.deps import require_roles
from app.models.user import User
from app.models.purchase import Purchase, PurchasePaymentStatus
from app.models.purchase_item import PurchaseItem
from app.models.order_item import OrderItem
from app.models.order import Order
from app.models.counterparty import Counterparty, CounterpartyType
from app.models.company import Company
from app.models.payment import Payment
from app.models.purchase_payment_link import PurchasePaymentLink
from app.models.audit_log import AuditActionEnum
from app.schemas.purchase import (
    PurchaseCreate, PurchaseUpdate, PurchaseResponse, PurchaseItemResponse,
    PurchaseListItem, PurchaseListResponse,
)
from app.utils.audit import write_audit
from app.services.notifications import on_purchase_created, on_purchase_payment_requested

router = APIRouter(prefix="/api/purchases", tags=["purchases"])

_ALLOWED = ("manager", "purchaser", "accountant", "admin")


async def _get_default_company(db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.is_active == True).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(400, "No active company found")
    return company


async def _max_purchase_seq(db: AsyncSession, prefix: str) -> int:
    """Наибольший порядковый номер среди уже существующих закупок с данным префиксом.

    Считаем по МАКСИМУМУ суффикса, а не по COUNT: при пропусках в нумерации
    (например, закупка была удалена) count давал бы уже занятый номер и приводил
    к нарушению уникального ключа purchase_number.
    """
    numbers = (await db.execute(
        select(Purchase.purchase_number).where(Purchase.purchase_number.like(f"{prefix}%"))
    )).scalars().all()
    max_seq = 0
    for n in numbers:
        try:
            max_seq = max(max_seq, int(n.rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            continue
    return max_seq


async def _flush_purchase_with_retry(
    db: AsyncSession, purchase: Purchase, auto_number: bool, prefix: str
) -> None:
    """Флашит INSERT закупки, перегенерируя номер при гонке за purchase_number.

    Нарушение уникального ключа возникает именно на flush (INSERT), поэтому
    retry нужен здесь, а не вокруг commit. Каждая попытка — в savepoint, чтобы
    после отката сессия оставалась пригодной.
    """
    for _ in range(20):
        try:
            async with db.begin_nested():
                db.add(purchase)
                await db.flush()
            return
        except IntegrityError as exc:
            if not auto_number or "purchase_number" not in str(exc):
                raise
            purchase.purchase_number = f"{prefix}{await _max_purchase_seq(db, prefix) + 1:04d}"
    # Последняя попытка без перехвата — пусть ошибка всплывёт, если так и не удалось
    async with db.begin_nested():
        db.add(purchase)
        await db.flush()


async def _load_purchase(db: AsyncSession, purchase_id: uuid.UUID) -> PurchaseResponse:
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        raise HTTPException(404, "Purchase not found")

    supplier = (await db.execute(
        select(Counterparty).where(Counterparty.id == pur.supplier_id)
    )).scalar_one_or_none()

    items_stmt = (
        select(PurchaseItem, OrderItem.name.label("item_name"), Order.order_number, Order.id.label("order_id_col"))
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(PurchaseItem.purchase_id == purchase_id)
    )
    item_rows = (await db.execute(items_stmt)).all()

    items = [
        PurchaseItemResponse(
            id=r[0].id, order_item_id=r[0].order_item_id,
            order_item_name=r[1], order_number=r[2],
            quantity=r[0].quantity, cost_price=r[0].cost_price, cost_amount=r[0].cost_amount,
        )
        for r in item_rows
    ]

    paid_row = await db.execute(
        select(func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")))
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .where(PurchasePaymentLink.purchase_id == purchase_id, Payment.is_active == True)
    )
    paid_cny = paid_row.scalar_one() or Decimal("0")
    remaining_cny = max((pur.total_amount_cny or Decimal("0")) - paid_cny, Decimal("0"))

    # For logistics purchases: get order info directly from order_id
    linked_order_id = pur.order_id
    linked_order_number = None
    if linked_order_id:
        order_row = (await db.execute(
            select(Order.order_number).where(Order.id == linked_order_id)
        )).scalar_one_or_none()
        linked_order_number = order_row
    elif item_rows:
        # For trade purchases: order id and number come from the joined Order row
        linked_order_id = item_rows[0][3]
        linked_order_number = item_rows[0][2]

    # Resolve created_by name
    created_by_name = None
    if pur.created_by:
        cb_user = (await db.execute(
            select(User).where(User.id == pur.created_by)
        )).scalar_one_or_none()
        created_by_name = cb_user.full_name if cb_user else None

    payment_requested_by_name = None
    if pur.payment_requested_by:
        req_user = (await db.execute(
            select(User).where(User.id == pur.payment_requested_by)
        )).scalar_one_or_none()
        payment_requested_by_name = req_user.full_name if req_user else None

    return PurchaseResponse(
        id=pur.id, purchase_number=pur.purchase_number,
        supplier_id=pur.supplier_id, supplier_name=supplier.name if supplier else "",
        purchase_date=pur.purchase_date, currency=pur.currency,
        total_amount=pur.total_amount, rate_to_cny=pur.rate_to_cny,
        total_amount_cny=pur.total_amount_cny,
        payment_status=pur.payment_status,
        paid_amount_cny=paid_cny,
        remaining_amount_cny=remaining_cny,
        notes=pur.notes, created_at=pur.created_at,
        items=items,
        order_id=linked_order_id,
        order_number=linked_order_number,
        created_by_name=created_by_name,
        excluded_from_accounting=pur.excluded_from_accounting,
        payment_requested=pur.payment_requested,
        payment_requested_by_name=payment_requested_by_name,
        payment_requested_at=pur.payment_requested_at,
    )


async def _recalc_order_cost(db: AsyncSession, order_id: uuid.UUID) -> None:
    """Update order.total_cost_cny from purchase_items + direct logistics purchases."""
    items_cost = (await db.execute(
        select(func.sum(PurchaseItem.cost_amount))
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
        .where(OrderItem.order_id == order_id, Purchase.is_deleted == False)
    )).scalar_one() or Decimal("0")

    logistics_cost = (await db.execute(
        select(func.sum(Purchase.total_amount_cny))
        .where(Purchase.order_id == order_id, Purchase.is_deleted == False)
    )).scalar_one() or Decimal("0")

    total_cost = items_cost + logistics_cost
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order:
        order.total_cost_cny = total_cost


@router.get("", response_model=PurchaseListResponse)
async def list_purchases(
    search: Optional[str] = Query(None),
    supplier_id: Optional[uuid.UUID] = Query(None),
    payment_status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    order_id: Optional[uuid.UUID] = Query(None),
    business_type_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    paid_pur_sq = (
        select(
            PurchasePaymentLink.purchase_id,
            func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")).label("paid_cny"),
        )
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .where(Payment.is_active == True)
        .group_by(PurchasePaymentLink.purchase_id)
        .subquery()
    )

    # Correlated subquery: get order_number for trade purchases (via items → order_items → orders)
    trade_order_num_sq = (
        select(Order.order_number)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(PurchaseItem, PurchaseItem.order_item_id == OrderItem.id)
        .where(PurchaseItem.purchase_id == Purchase.id)
        .limit(1)
        .correlate(Purchase)
        .scalar_subquery()
    )

    trade_order_id_sq = (
        select(OrderItem.order_id)
        .join(PurchaseItem, PurchaseItem.order_item_id == OrderItem.id)
        .where(PurchaseItem.purchase_id == Purchase.id)
        .limit(1)
        .correlate(Purchase)
        .scalar_subquery()
    )

    DirectOrder = aliased(Order)

    stmt = (
        select(
            Purchase,
            Counterparty.name.label("supplier_name"),
            func.count(PurchaseItem.id).label("items_count"),
            func.max(func.coalesce(paid_pur_sq.c.paid_cny, Decimal("0"))).label("paid_cny"),
            func.coalesce(DirectOrder.order_number, trade_order_num_sq).label("order_number"),
            func.coalesce(Purchase.order_id, trade_order_id_sq).label("linked_order_id"),
        )
        .join(Counterparty, Purchase.supplier_id == Counterparty.id)
        .outerjoin(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
        .outerjoin(paid_pur_sq, Purchase.id == paid_pur_sq.c.purchase_id)
        .outerjoin(DirectOrder, Purchase.order_id == DirectOrder.id)
        .where(Purchase.is_deleted == False)
        .group_by(Purchase.id, Counterparty.name, DirectOrder.order_number)
    )

    if search:
        stmt = stmt.where(Purchase.purchase_number.ilike(f"%{search}%"))
    if supplier_id:
        stmt = stmt.where(Purchase.supplier_id == supplier_id)
    if payment_status:
        stmt = stmt.where(Purchase.payment_status == payment_status)
    if date_from:
        stmt = stmt.where(Purchase.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(Purchase.purchase_date <= date_to)
    if order_id:
        # Include logistics purchases (direct order_id) AND trade purchases (via items)
        trade_items_sq = (
            select(PurchaseItem.purchase_id)
            .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
            .where(OrderItem.order_id == order_id)
        )
        stmt = stmt.where(or_(Purchase.order_id == order_id, Purchase.id.in_(trade_items_sq)))
    if business_type_id:
        # Направление берётся у связанного заказа: напрямую (логистика) или через items (торговля)
        bt_orders_sq = select(Order.id).where(Order.business_type_id == business_type_id)
        bt_items_sq = (
            select(PurchaseItem.purchase_id)
            .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.business_type_id == business_type_id)
        )
        stmt = stmt.where(or_(Purchase.order_id.in_(bt_orders_sq), Purchase.id.in_(bt_items_sq)))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Purchase.purchase_date.desc(), Purchase.purchase_number.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    items = [
        PurchaseListItem(
            id=r[0].id, purchase_number=r[0].purchase_number,
            supplier_id=r[0].supplier_id, supplier_name=r.supplier_name,
            purchase_date=r[0].purchase_date, currency=r[0].currency,
            total_amount=r[0].total_amount, total_amount_cny=r[0].total_amount_cny,
            payment_status=r[0].payment_status, items_count=r.items_count,
            paid_amount_cny=r.paid_cny or Decimal("0"),
            order_id=r.linked_order_id,
            order_number=r.order_number,
            remaining_amount_cny=max(r[0].total_amount_cny - (r.paid_cny or Decimal("0")), Decimal("0")),
            excluded_from_accounting=r[0].excluded_from_accounting,
            payment_requested=r[0].payment_requested,
        )
        for r in rows
    ]

    page_total_cny = sum(r[0].total_amount_cny for r in rows) or Decimal("0")

    return PurchaseListResponse(
        items=items, total=total, page=page, page_size=page_size,
        page_total_cny=page_total_cny,
    )


@router.get("/next-number")
async def get_next_purchase_number(
    purchase_date: date = Query(alias="date"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    prefix = f"PUR-{purchase_date.strftime('%Y%m%d')}-"
    count = (await db.execute(
        select(func.count(Purchase.id)).where(Purchase.purchase_number.like(f"{prefix}%"))
    )).scalar_one()
    return {"purchase_number": f"{prefix}{count + 1:04d}"}


@router.get("/{purchase_id}", response_model=PurchaseResponse)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    return await _load_purchase(db, purchase_id)


@router.post("/{purchase_id}/request-payment", response_model=PurchaseResponse)
async def request_payment(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    from datetime import datetime, timezone
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        raise HTTPException(404, "Purchase not found")
    if pur.payment_status == PurchasePaymentStatus.paid:
        raise HTTPException(422, "Purchase is already fully paid")
    if pur.payment_requested:
        return await _load_purchase(db, purchase_id)

    supplier = (await db.execute(
        select(Counterparty).where(Counterparty.id == pur.supplier_id)
    )).scalar_one_or_none()

    pur.payment_requested = True
    pur.payment_requested_by = current_user.id
    pur.payment_requested_at = datetime.now(timezone.utc)
    await db.flush()

    await on_purchase_payment_requested(
        db, pur.id, pur.purchase_number,
        supplier.name if supplier else "",
        str(pur.total_amount_cny),
        current_user.id,
    )
    await db.commit()
    return await _load_purchase(db, purchase_id)


@router.post("", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    body: PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    company = await _get_default_company(db)

    supplier = (await db.execute(
        select(Counterparty).where(Counterparty.id == body.supplier_id)
    )).scalar_one_or_none()
    if not supplier or supplier.type not in (CounterpartyType.supplier, CounterpartyType.both):
        raise HTTPException(422, "Supplier must be counterparty of type 'supplier' or 'both'")

    # Auto-generate purchase number if not provided
    purchase_number = body.purchase_number
    _auto_number = not purchase_number
    prefix = f"PUR-{body.purchase_date.strftime('%Y%m%d')}-"
    if _auto_number:
        purchase_number = f"{prefix}{await _max_purchase_seq(db, prefix) + 1:04d}"

    rate = body.rate_to_cny
    affected_order_ids: set[uuid.UUID] = set()

    # ── Logistics mode: no items, direct order link + total amount ──────────────
    is_logistics = not body.items and body.order_id is not None

    if is_logistics:
        if not body.total_amount or body.total_amount <= 0:
            raise HTTPException(422, "total_amount is required for logistics purchase")
        order = (await db.execute(select(Order).where(Order.id == body.order_id))).scalar_one_or_none()
        if not order:
            raise HTTPException(422, "Order not found")

        total_amount = body.total_amount
        total_amount_cny = (total_amount * rate).quantize(Decimal("0.01"))

        purchase = Purchase(
            id=uuid.uuid4(),
            purchase_number=purchase_number,
            company_id=company.id,
            supplier_id=body.supplier_id,
            purchase_date=body.purchase_date,
            currency=body.currency,
            total_amount=total_amount.quantize(Decimal("0.01")),
            rate_to_cny=rate,
            total_amount_cny=total_amount_cny,
            payment_status=PurchasePaymentStatus.unpaid,
            order_id=body.order_id,
            notes=body.notes,
            created_by=current_user.id,
            excluded_from_accounting=body.excluded_from_accounting,
        )
        await _flush_purchase_with_retry(db, purchase, _auto_number, prefix)
        purchase_number = purchase.purchase_number
        affected_order_ids.add(body.order_id)

    else:
        # ── Trade/services mode: per-item purchases ─────────────────────────────
        validated_items = []

        for item_data in body.items:
            oi = (await db.execute(
                select(OrderItem).where(OrderItem.id == item_data.order_item_id)
            )).scalar_one_or_none()
            if not oi:
                raise HTTPException(422, f"OrderItem {item_data.order_item_id} not found")
            if oi.quantity is None:
                raise HTTPException(422, f"OrderItem {item_data.order_item_id} has no quantity")

            already = (await db.execute(
                select(func.sum(PurchaseItem.quantity))
                .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
                .where(PurchaseItem.order_item_id == item_data.order_item_id, Purchase.is_deleted == False)
            )).scalar_one() or Decimal("0")

            available = oi.quantity - already
            if item_data.quantity > available:
                raise HTTPException(
                    422,
                    f"Item '{oi.name}': requested {item_data.quantity}, available {available}"
                )

            validated_items.append((oi, item_data))
            affected_order_ids.add(oi.order_id)

        total_amount = sum(i.quantity * i.cost_price for _, i in validated_items) if validated_items else Decimal("0")
        total_amount_cny = (total_amount * rate).quantize(Decimal("0.01"))

        purchase = Purchase(
            id=uuid.uuid4(),
            purchase_number=purchase_number,
            company_id=company.id,
            supplier_id=body.supplier_id,
            purchase_date=body.purchase_date,
            currency=body.currency,
            total_amount=total_amount.quantize(Decimal("0.01")),
            rate_to_cny=rate,
            total_amount_cny=total_amount_cny,
            payment_status=PurchasePaymentStatus.unpaid,
            notes=body.notes,
            created_by=current_user.id,
            excluded_from_accounting=body.excluded_from_accounting,
        )
        await _flush_purchase_with_retry(db, purchase, _auto_number, prefix)
        purchase_number = purchase.purchase_number

        for oi, item_data in validated_items:
            cost_amount_cny = (item_data.quantity * item_data.cost_price * rate).quantize(Decimal("0.01"))
            db.add(PurchaseItem(
                id=uuid.uuid4(),
                purchase_id=purchase.id,
                order_item_id=item_data.order_item_id,
                quantity=item_data.quantity,
                cost_price=item_data.cost_price,
                cost_amount=cost_amount_cny,
            ))

        await db.flush()

    # Update total_cost_cny on affected orders
    for order_id in affected_order_ids:
        await _recalc_order_cost(db, order_id)

    await write_audit(db, current_user.id, "purchase", purchase.id, AuditActionEnum.create,
                      {"purchase_number": purchase_number, "total_cny": str(total_amount_cny)})
    # Notify manager of linked order about the new purchase
    if affected_order_ids:
        for oid in list(affected_order_ids)[:1]:
            order_obj = (await db.execute(select(Order).where(Order.id == oid))).scalar_one_or_none()
            if order_obj:
                await on_purchase_created(db, purchase.id, purchase_number, order_obj.manager_id)
    # Авто-создание плана платежа (ожидаемый исходящий поставщику)
    from app.services.payment_plans import create_plan_for_purchase
    await create_plan_for_purchase(db, purchase, current_user.id)
    # Уникальность purchase_number уже гарантирована на flush (savepoint-retry выше):
    # успешный INSERT держит блокировку индекса, поэтому commit коллизий не даёт.
    await db.commit()
    return await _load_purchase(db, purchase.id)


@router.patch("/{purchase_id}", response_model=PurchaseResponse)
async def update_purchase(
    purchase_id: uuid.UUID,
    body: PurchaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        raise HTTPException(404, "Purchase not found")
    if pur.payment_status == PurchasePaymentStatus.paid:
        raise HTTPException(422, "Cannot modify a fully paid purchase")

    update_data = body.model_dump(exclude_unset=True)
    items_data = update_data.pop("items", None)

    for field, value in update_data.items():
        setattr(pur, field, value)

    affected_order_ids: set[uuid.UUID] = set()

    if items_data is None and "rate_to_cny" in update_data:
        # Rate changed but items not sent — recalculate totals from existing items
        existing_items = (await db.execute(
            select(PurchaseItem).where(PurchaseItem.purchase_id == purchase_id)
        )).scalars().all()
        if existing_items:
            new_rate = Decimal(str(update_data["rate_to_cny"]))
            total = sum(Decimal(str(i.quantity)) * Decimal(str(i.cost_price)) for i in existing_items)
            pur.total_amount = total.quantize(Decimal("0.01"))
            pur.total_amount_cny = (total * new_rate).quantize(Decimal("0.01"))
            for i in existing_items:
                i.cost_amount = (Decimal(str(i.quantity)) * Decimal(str(i.cost_price)) * new_rate).quantize(Decimal("0.01"))
            existing_order_ids = (await db.execute(
                select(PurchaseItem, OrderItem.order_id)
                .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
                .where(PurchaseItem.purchase_id == purchase_id)
            )).all()
            for _, order_id in existing_order_ids:
                affected_order_ids.add(order_id)
            await db.flush()

    if items_data is not None:
        # Delete existing items, collect affected orders
        existing_pi = (await db.execute(
            select(PurchaseItem, OrderItem.order_id)
            .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
            .where(PurchaseItem.purchase_id == purchase_id)
        )).all()
        for _, order_id in existing_pi:
            affected_order_ids.add(order_id)

        await db.execute(delete(PurchaseItem).where(PurchaseItem.purchase_id == purchase_id))
        await db.flush()

        from app.schemas.purchase import PurchaseItemCreate
        validated_items = []
        for item_data in [PurchaseItemCreate(**i) if isinstance(i, dict) else i for i in items_data]:
            oi = (await db.execute(
                select(OrderItem).where(OrderItem.id == item_data.order_item_id)
            )).scalar_one_or_none()
            if not oi:
                raise HTTPException(422, f"OrderItem {item_data.order_item_id} not found")
            validated_items.append((oi, item_data))
            affected_order_ids.add(oi.order_id)

        rate = update_data.get("rate_to_cny", pur.rate_to_cny)
        total_amount = sum(i.quantity * i.cost_price for _, i in validated_items) if validated_items else Decimal("0")
        pur.total_amount = total_amount.quantize(Decimal("0.01"))
        pur.total_amount_cny = (total_amount * rate).quantize(Decimal("0.01"))

        for oi, item_data in validated_items:
            cost_amount_cny = (item_data.quantity * item_data.cost_price * rate).quantize(Decimal("0.01"))
            db.add(PurchaseItem(
                id=uuid.uuid4(),
                purchase_id=purchase_id,
                order_item_id=item_data.order_item_id,
                quantity=item_data.quantity,
                cost_price=item_data.cost_price,
                cost_amount=cost_amount_cny,
            ))

        await db.flush()

    # Логистическая закупка привязана к заказу напрямую — тоже пересчитываем
    if pur.order_id:
        affected_order_ids.add(pur.order_id)

    for order_id in affected_order_ids:
        await _recalc_order_cost(db, order_id)

    # Синхронизируем ожидаемую сумму плана платежа
    from app.services.payment_plans import sync_plan_for_purchase
    await db.flush()
    await sync_plan_for_purchase(db, pur)
    # Сумма закупки изменилась — пересчитываем привязки платежей и статус оплаты
    from app.api.payments import sync_allocations_for_purchase, _recalc_purchase_payment_status
    await sync_allocations_for_purchase(db, pur.id)
    await db.flush()
    await _recalc_purchase_payment_status(db, pur.id)

    await write_audit(db, current_user.id, "purchase", pur.id, AuditActionEnum.update,
                      {"purchase_number": pur.purchase_number})
    await db.commit()
    return await _load_purchase(db, pur.id)


@router.delete("/{purchase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        raise HTTPException(404, "Purchase not found")
    if pur.payment_status == PurchasePaymentStatus.paid:
        raise HTTPException(422, "Cannot delete a fully paid purchase")

    # Collect affected orders before soft-delete
    existing_pi = (await db.execute(
        select(PurchaseItem, OrderItem.order_id)
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .where(PurchaseItem.purchase_id == purchase_id)
    )).all()
    affected_order_ids = {row[1] for row in existing_pi}
    # Логистическая закупка связана с заказом напрямую (без items) — иначе
    # стоимость заказа не пересчитается и удалённая закупка останется в марже
    if pur.order_id:
        affected_order_ids.add(pur.order_id)

    pur.is_deleted = True
    # Физически удаляем purchase_items: иначе FK constraint блокирует
    # удаление order_item при редактировании заказа (is_deleted не снимает ссылку)
    await db.execute(delete(PurchaseItem).where(PurchaseItem.purchase_id == purchase_id))
    await db.flush()

    for order_id in affected_order_ids:
        await _recalc_order_cost(db, order_id)

    await write_audit(db, current_user.id, "purchase", pur.id, AuditActionEnum.delete,
                      {"purchase_number": pur.purchase_number})
    await db.commit()
