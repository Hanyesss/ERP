import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.payment import Payment, PaymentDirection
from app.models.payment_allocation import PaymentAllocation
from app.models.purchase_payment_link import PurchasePaymentLink
from app.models.order import Order, PaymentStatus
from app.models.purchase import Purchase, PurchasePaymentStatus
from app.models.counterparty import Counterparty
from app.models.company import Company
from app.models.exchange_rate import ExchangeRate
from app.models.audit_log import AuditActionEnum
from app.schemas.payment import (
    PaymentCreate, PaymentUpdate,
    PaymentResponse, PaymentListItem, PaymentListResponse,
    AllocationResponse, AllocationIn,
    OrderPaymentBalance, PurchasePaymentBalance,
)
from app.utils.audit import write_audit

router = APIRouter(prefix="/api/payments", tags=["payments"])

_ALLOWED = ("accountant", "admin")


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_default_company(db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.is_active == True).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(400, "No active company found")
    return company


async def _recalc_order_payment_status(db: AsyncSession, order_id: uuid.UUID) -> None:
    """Recalculate order.payment_status based on active incoming payment allocations."""
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        return

    paid_sum_row = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(PaymentAllocation.order_id == order_id, Payment.is_active == True)
    )
    paid_cny = paid_sum_row.scalar_one() or Decimal("0")

    total = order.total_sale_cny or Decimal("0")
    if paid_cny <= 0:
        order.payment_status = PaymentStatus.unpaid
    elif paid_cny >= total:
        order.payment_status = PaymentStatus.paid
    else:
        order.payment_status = PaymentStatus.partial


async def _recalc_purchase_payment_status(db: AsyncSession, purchase_id: uuid.UUID) -> None:
    """Recalculate purchase.payment_status based on active outgoing purchase payment links."""
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        return

    paid_sum_row = await db.execute(
        select(func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")))
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .where(PurchasePaymentLink.purchase_id == purchase_id, Payment.is_active == True)
    )
    paid_cny = paid_sum_row.scalar_one() or Decimal("0")

    total = pur.total_amount_cny or Decimal("0")
    if paid_cny <= 0:
        pur.payment_status = PurchasePaymentStatus.unpaid
    elif paid_cny >= total:
        pur.payment_status = PurchasePaymentStatus.paid
    else:
        pur.payment_status = PurchasePaymentStatus.partial


async def _recalc_order_supplier_payment_status(db: AsyncSession, order_id: uuid.UUID) -> None:
    """Recalculate order.supplier_payment_status based on purchases linked to order items."""
    from app.models.order_item import OrderItem
    from app.models.purchase_item import PurchaseItem

    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        return

    # Get all active purchases linked to this order's items
    result = await db.execute(
        select(Purchase.payment_status)
        .join(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == order_id, Purchase.is_deleted == False)
        .distinct()
    )
    statuses = {row[0] for row in result.all()}

    if not statuses:
        order.supplier_payment_status = PaymentStatus.unpaid
    elif all(s == PurchasePaymentStatus.paid for s in statuses):
        order.supplier_payment_status = PaymentStatus.paid
    elif any(s in (PurchasePaymentStatus.partial, PurchasePaymentStatus.paid) for s in statuses):
        order.supplier_payment_status = PaymentStatus.partial
    else:
        order.supplier_payment_status = PaymentStatus.unpaid


async def _load_payment(db: AsyncSession, payment_id: uuid.UUID) -> PaymentResponse:
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    cp = (await db.execute(
        select(Counterparty).where(Counterparty.id == payment.counterparty_id)
    )).scalar_one_or_none()

    creator = (await db.execute(
        select(User).where(User.id == payment.created_by)
    )).scalar_one_or_none()

    # Load allocations
    alloc_rows = await db.execute(
        select(PaymentAllocation, Order.order_number)
        .outerjoin(Order, PaymentAllocation.order_id == Order.id)
        .where(PaymentAllocation.payment_id == payment_id)
    )
    alloc_data = alloc_rows.all()

    pur_alloc_rows = await db.execute(
        select(PurchasePaymentLink, Purchase.purchase_number)
        .outerjoin(Purchase, PurchasePaymentLink.purchase_id == Purchase.id)
        .where(PurchasePaymentLink.payment_id == payment_id)
    )
    pur_alloc_data = pur_alloc_rows.all()

    allocations = [
        AllocationResponse(
            id=r[0].id, order_id=r[0].order_id, order_number=r[1],
            amount_cny=r[0].amount_cny, notes=r[0].notes,
        )
        for r in alloc_data
    ] + [
        AllocationResponse(
            id=r[0].id, purchase_id=r[0].purchase_id, purchase_number=r[1],
            amount_cny=r[0].amount_cny, notes=r[0].notes,
        )
        for r in pur_alloc_data
    ]

    allocated = sum(a.amount_cny for a in allocations)

    return PaymentResponse(
        id=payment.id,
        direction=payment.direction,
        counterparty_id=payment.counterparty_id,
        counterparty_name=cp.name if cp else "",
        payment_date=payment.payment_date,
        currency=payment.currency,
        amount=payment.amount,
        rate_to_cny=payment.rate_to_cny,
        amount_cny=payment.amount_cny,
        network_fee=payment.network_fee,
        notes=payment.notes,
        is_active=payment.is_active,
        created_by_name=creator.full_name if creator else "",
        created_at=payment.created_at,
        allocations=allocations,
        allocated_cny=allocated,
        unallocated_cny=max(payment.amount_cny - allocated, Decimal("0")),
    )


async def _apply_allocations(
    db: AsyncSession, payment: Payment, allocations: list[AllocationIn]
) -> None:
    """Validate and insert allocations for a payment."""
    total_alloc = sum(a.amount_cny for a in allocations)
    if total_alloc > payment.amount_cny:
        raise HTTPException(
            422,
            f"Total allocations ({total_alloc}) exceed payment amount ({payment.amount_cny})"
        )

    for alloc in allocations:
        if payment.direction == "in":
            if not alloc.order_id:
                raise HTTPException(422, "Incoming payment allocations must reference order_id")
            order = (await db.execute(select(Order).where(Order.id == alloc.order_id))).scalar_one_or_none()
            if not order:
                raise HTTPException(422, f"Order {alloc.order_id} not found")
            if order.client_id != payment.counterparty_id:
                raise HTTPException(
                    422, f"Order {order.order_number} does not belong to the selected client"
                )
            db.add(PaymentAllocation(
                id=uuid.uuid4(),
                payment_id=payment.id,
                order_id=alloc.order_id,
                amount_cny=alloc.amount_cny,
                notes=alloc.notes,
            ))
        else:
            if not alloc.purchase_id:
                raise HTTPException(422, "Outgoing payment allocations must reference purchase_id")
            pur = (await db.execute(
                select(Purchase).where(Purchase.id == alloc.purchase_id, Purchase.is_deleted == False)
            )).scalar_one_or_none()
            if not pur:
                raise HTTPException(422, f"Purchase {alloc.purchase_id} not found")
            if pur.supplier_id != payment.counterparty_id:
                raise HTTPException(
                    422, f"Purchase {pur.purchase_number} does not belong to the selected supplier"
                )
            db.add(PurchasePaymentLink(
                id=uuid.uuid4(),
                payment_id=payment.id,
                purchase_id=alloc.purchase_id,
                amount_cny=alloc.amount_cny,
                notes=alloc.notes,
            ))


async def _recalc_all_for_payment(db: AsyncSession, payment: Payment) -> None:
    """Recalculate statuses for all orders/purchases referenced by this payment."""
    if payment.direction == "in":
        alloc_rows = await db.execute(
            select(PaymentAllocation.order_id)
            .where(PaymentAllocation.payment_id == payment.id)
        )
        for row in alloc_rows.all():
            await _recalc_order_payment_status(db, row[0])
    else:
        link_rows = await db.execute(
            select(PurchasePaymentLink.purchase_id)
            .where(PurchasePaymentLink.payment_id == payment.id)
        )
        for row in link_rows.all():
            await _recalc_purchase_payment_status(db, row[0])
            # Find which orders are linked through purchase items
            from app.models.purchase_item import PurchaseItem
            from app.models.order_item import OrderItem
            order_rows = await db.execute(
                select(OrderItem.order_id)
                .join(PurchaseItem, PurchaseItem.order_item_id == OrderItem.id)
                .where(PurchaseItem.purchase_id == row[0])
                .distinct()
            )
            for orow in order_rows.all():
                await _recalc_order_supplier_payment_status(db, orow[0])


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=PaymentListResponse)
async def list_payments(
    direction: Optional[str] = Query(None),
    counterparty_id: Optional[uuid.UUID] = Query(None),
    currency: Optional[str] = Query(None),
    has_allocations: Optional[bool] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    CreatorAlias = aliased(User)

    # Subquery for allocated_cny per payment
    order_alloc_sq = (
        select(
            PaymentAllocation.payment_id,
            func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")).label("order_alloc"),
        )
        .group_by(PaymentAllocation.payment_id)
        .subquery()
    )
    pur_alloc_sq = (
        select(
            PurchasePaymentLink.payment_id,
            func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")).label("pur_alloc"),
        )
        .group_by(PurchasePaymentLink.payment_id)
        .subquery()
    )

    stmt = (
        select(
            Payment,
            Counterparty.name.label("cp_name"),
            CreatorAlias.full_name.label("creator_name"),
            func.coalesce(order_alloc_sq.c.order_alloc, Decimal("0")).label("order_alloc"),
            func.coalesce(pur_alloc_sq.c.pur_alloc, Decimal("0")).label("pur_alloc"),
        )
        .join(Counterparty, Payment.counterparty_id == Counterparty.id)
        .join(CreatorAlias, Payment.created_by == CreatorAlias.id)
        .outerjoin(order_alloc_sq, Payment.id == order_alloc_sq.c.payment_id)
        .outerjoin(pur_alloc_sq, Payment.id == pur_alloc_sq.c.payment_id)
        .where(Payment.is_active == True)
    )

    if direction:
        stmt = stmt.where(Payment.direction == direction)
    if counterparty_id:
        stmt = stmt.where(Payment.counterparty_id == counterparty_id)
    if currency:
        stmt = stmt.where(Payment.currency == currency)
    if date_from:
        stmt = stmt.where(Payment.payment_date >= date_from)
    if date_to:
        stmt = stmt.where(Payment.payment_date <= date_to)
    if search:
        stmt = stmt.where(Counterparty.name.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    # Totals before pagination
    totals_stmt = (
        select(
            Payment.direction,
            func.sum(Payment.amount_cny).label("total_cny"),
        )
        .where(Payment.is_active == True)
    )
    if direction:
        totals_stmt = totals_stmt.where(Payment.direction == direction)
    if counterparty_id:
        totals_stmt = totals_stmt.where(Payment.counterparty_id == counterparty_id)
    if date_from:
        totals_stmt = totals_stmt.where(Payment.payment_date >= date_from)
    if date_to:
        totals_stmt = totals_stmt.where(Payment.payment_date <= date_to)
    totals_stmt = totals_stmt.group_by(Payment.direction)
    totals_rows = (await db.execute(totals_stmt)).all()
    incoming_cny = Decimal("0")
    outgoing_cny = Decimal("0")
    for row in totals_rows:
        if row[0] == "in":
            incoming_cny = row[1] or Decimal("0")
        else:
            outgoing_cny = row[1] or Decimal("0")

    stmt = stmt.order_by(Payment.payment_date.desc(), Payment.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    # Count allocations per payment
    payment_ids = [r[0].id for r in rows]
    alloc_counts: dict = {}
    if payment_ids:
        oa = (await db.execute(
            select(PaymentAllocation.payment_id, func.count().label("cnt"))
            .where(PaymentAllocation.payment_id.in_(payment_ids))
            .group_by(PaymentAllocation.payment_id)
        )).all()
        for row in oa:
            alloc_counts[row[0]] = alloc_counts.get(row[0], 0) + row[1]
        pa = (await db.execute(
            select(PurchasePaymentLink.payment_id, func.count().label("cnt"))
            .where(PurchasePaymentLink.payment_id.in_(payment_ids))
            .group_by(PurchasePaymentLink.payment_id)
        )).all()
        for row in pa:
            alloc_counts[row[0]] = alloc_counts.get(row[0], 0) + row[1]

    items = [
        PaymentListItem(
            id=r[0].id,
            direction=r[0].direction,
            counterparty_id=r[0].counterparty_id,
            counterparty_name=r.cp_name,
            payment_date=r[0].payment_date,
            currency=r[0].currency,
            amount=r[0].amount,
            amount_cny=r[0].amount_cny,
            allocations_count=alloc_counts.get(r[0].id, 0),
            allocated_cny=r.order_alloc + r.pur_alloc,
            is_active=r[0].is_active,
            created_by_name=r.creator_name,
        )
        for r in rows
    ]

    return PaymentListResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_incoming_cny=incoming_cny, total_outgoing_cny=outgoing_cny,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    return await _load_payment(db, payment_id)


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    company = await _get_default_company(db)

    # Validate counterparty exists
    cp = (await db.execute(
        select(Counterparty).where(Counterparty.id == body.counterparty_id, Counterparty.is_active == True)
    )).scalar_one_or_none()
    if not cp:
        raise HTTPException(422, "Counterparty not found or inactive")

    # Auto-fetch rate if not CNY
    rate = body.rate_to_cny
    if body.currency != "CNY" and rate == Decimal("1"):
        rate_row = (await db.execute(
            select(ExchangeRate).where(
                ExchangeRate.currency == body.currency,
                ExchangeRate.rate_date == body.payment_date,
            )
        )).scalar_one_or_none()
        if rate_row:
            rate = rate_row.rate_to_cny

    amount_cny = (body.amount * rate).quantize(Decimal("0.01"))

    payment = Payment(
        id=uuid.uuid4(),
        company_id=company.id,
        direction=body.direction,
        counterparty_id=body.counterparty_id,
        payment_date=body.payment_date,
        currency=body.currency,
        amount=body.amount,
        rate_to_cny=rate,
        amount_cny=amount_cny,
        network_fee=body.network_fee,
        notes=body.notes,
        created_by=current_user.id,
        is_active=True,
    )
    db.add(payment)
    await db.flush()

    await _apply_allocations(db, payment, body.allocations)
    await db.flush()

    await _recalc_all_for_payment(db, payment)

    await write_audit(
        db, current_user.id, "payment", payment.id, AuditActionEnum.create,
        {"direction": body.direction, "amount_cny": str(amount_cny),
         "counterparty": cp.name, "allocations": len(body.allocations)}
    )
    await db.commit()
    return await _load_payment(db, payment.id)


@router.patch("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: uuid.UUID,
    body: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(payment, field, value)

    # Recalculate amount_cny if amount or rate changed
    if "amount" in update_data or "rate_to_cny" in update_data:
        payment.amount_cny = (payment.amount * payment.rate_to_cny).quantize(Decimal("0.01"))

    await _recalc_all_for_payment(db, payment)

    await write_audit(
        db, current_user.id, "payment", payment.id, AuditActionEnum.update,
        {"updated_fields": list(update_data.keys())}
    )
    await db.commit()
    return await _load_payment(db, payment.id)


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    payment.is_active = False
    await db.flush()

    # Recalculate affected statuses
    await _recalc_all_for_payment(db, payment)

    await write_audit(
        db, current_user.id, "payment", payment.id, AuditActionEnum.delete,
        {"soft_deleted": True}
    )
    await db.commit()


@router.post("/{payment_id}/allocate", response_model=PaymentResponse)
async def add_allocations(
    payment_id: uuid.UUID,
    allocations: list[AllocationIn],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    # Check existing allocations
    existing_alloc = (await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")))
        .where(PaymentAllocation.payment_id == payment_id)
    )).scalar_one() or Decimal("0")
    existing_pur_alloc = (await db.execute(
        select(func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")))
        .where(PurchasePaymentLink.payment_id == payment_id)
    )).scalar_one() or Decimal("0")

    new_total = existing_alloc + existing_pur_alloc + sum(a.amount_cny for a in allocations)
    if new_total > payment.amount_cny:
        raise HTTPException(
            422,
            f"Total would exceed payment amount: {new_total} > {payment.amount_cny}"
        )

    await _apply_allocations(db, payment, allocations)
    await db.flush()
    await _recalc_all_for_payment(db, payment)

    await write_audit(
        db, current_user.id, "payment", payment.id, AuditActionEnum.update,
        {"added_allocations": len(allocations)}
    )
    await db.commit()
    return await _load_payment(db, payment.id)


# ── balance helpers (used by order/purchase detail pages) ─────────────────────

@router.get("/balance/order/{order_id}", response_model=OrderPaymentBalance)
async def get_order_payment_balance(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("manager", "purchaser", "accountant", "admin")),
):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    paid_row = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(PaymentAllocation.order_id == order_id, Payment.is_active == True)
    )
    paid_cny = paid_row.scalar_one() or Decimal("0")
    total = order.total_sale_cny or Decimal("0")

    return OrderPaymentBalance(
        order_id=order.id,
        order_number=order.order_number,
        total_cny=total,
        paid_cny=paid_cny,
        remaining_cny=max(total - paid_cny, Decimal("0")),
        payment_status=order.payment_status,
    )


@router.get("/balance/purchase/{purchase_id}", response_model=PurchasePaymentBalance)
async def get_purchase_payment_balance(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("purchaser", "accountant", "admin")),
):
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        raise HTTPException(404, "Purchase not found")

    paid_row = await db.execute(
        select(func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")))
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .where(PurchasePaymentLink.purchase_id == purchase_id, Payment.is_active == True)
    )
    paid_cny = paid_row.scalar_one() or Decimal("0")
    total = pur.total_amount_cny or Decimal("0")

    return PurchasePaymentBalance(
        purchase_id=pur.id,
        purchase_number=pur.purchase_number,
        total_cny=total,
        paid_cny=paid_cny,
        remaining_cny=max(total - paid_cny, Decimal("0")),
        payment_status=pur.payment_status,
    )


# ── order-scoped incoming payment list ────────────────────────────────────────

@router.get("/for-order/{order_id}")
async def get_payments_for_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("manager", "purchaser", "accountant", "admin")),
):
    """Returns incoming payments allocated to a specific order."""
    rows = await db.execute(
        select(
            Payment,
            PaymentAllocation.amount_cny.label("alloc_cny"),
            Counterparty.name.label("cp_name"),
        )
        .join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
        .join(Counterparty, Payment.counterparty_id == Counterparty.id)
        .where(
            PaymentAllocation.order_id == order_id,
            Payment.is_active == True,
        )
        .order_by(Payment.payment_date.desc())
    )
    result = rows.all()
    return [
        {
            "id": str(r[0].id),
            "payment_date": r[0].payment_date.isoformat(),
            "currency": r[0].currency,
            "amount": str(r[0].amount),
            "amount_cny": str(r[0].amount_cny),
            "alloc_cny": str(r.alloc_cny),
            "counterparty_name": r.cp_name,
            "direction": r[0].direction,
        }
        for r in result
    ]


# ── purchase-scoped outgoing payment list ─────────────────────────────────────

@router.get("/for-purchase/{purchase_id}")
async def get_payments_for_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("purchaser", "accountant", "admin")),
):
    """Returns outgoing payments linked to a specific purchase."""
    rows = await db.execute(
        select(
            Payment,
            PurchasePaymentLink.amount_cny.label("alloc_cny"),
            Counterparty.name.label("cp_name"),
        )
        .join(PurchasePaymentLink, PurchasePaymentLink.payment_id == Payment.id)
        .join(Counterparty, Payment.counterparty_id == Counterparty.id)
        .where(
            PurchasePaymentLink.purchase_id == purchase_id,
            Payment.is_active == True,
        )
        .order_by(Payment.payment_date.desc())
    )
    result = rows.all()
    return [
        {
            "id": str(r[0].id),
            "payment_date": r[0].payment_date.isoformat(),
            "currency": r[0].currency,
            "amount": str(r[0].amount),
            "amount_cny": str(r[0].amount_cny),
            "alloc_cny": str(r.alloc_cny),
            "supplier_name": r.cp_name,
            "direction": r[0].direction,
        }
        for r in result
    ]
