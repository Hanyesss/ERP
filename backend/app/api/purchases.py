import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, or_
from sqlalchemy.orm import aliased

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
from app.services.notifications import on_purchase_created

router = APIRouter(prefix="/api/purchases", tags=["purchases"])

_ALLOWED = ("purchaser", "accountant", "admin")


async def _get_default_company(db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.is_active == True).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(400, "No active company found")
    return company


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
        select(PurchaseItem, OrderItem.name.label("item_name"), Order.order_number)
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
        # For trade purchases: get order number from first item
        linked_order_id = item_rows[0][0].order_id if hasattr(item_rows[0][0], "order_id") else None
        # Already have order_number in items
        linked_order_number = item_rows[0][2] if item_rows else None

    # Resolve created_by name
    created_by_name = None
    if pur.created_by:
        cb_user = (await db.execute(
            select(User).where(User.id == pur.created_by)
        )).scalar_one_or_none()
        created_by_name = cb_user.full_name if cb_user else None

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
    if not purchase_number:
        prefix = f"PUR-{body.purchase_date.strftime('%Y%m%d')}-"
        count = (await db.execute(
            select(func.count(Purchase.id)).where(Purchase.purchase_number.like(f"{prefix}%"))
        )).scalar_one()
        purchase_number = f"{prefix}{count + 1:04d}"

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
        db.add(purchase)
        await db.flush()
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
        db.add(purchase)
        await db.flush()

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

    for order_id in affected_order_ids:
        await _recalc_order_cost(db, order_id)

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

    pur.is_deleted = True
    await db.flush()

    for order_id in affected_order_ids:
        await _recalc_order_cost(db, order_id)

    await write_audit(db, current_user.id, "purchase", pur.id, AuditActionEnum.delete,
                      {"purchase_number": pur.purchase_number})
    await db.commit()
