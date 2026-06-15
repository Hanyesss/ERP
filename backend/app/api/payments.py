import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
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
    OrderPaymentBalance, PurchasePaymentBalance, CounterpartyBalance, UnallocatedPaymentItem,
)
from app.utils.audit import write_audit
from app.services.notifications import on_payment_unassigned, on_order_paid, on_purchase_paid
from app.models.cash_register import CashRegister, CashTransaction

router = APIRouter(prefix="/api/payments", tags=["payments"])

_ALLOWED = ("employee", "seller", "manager", "purchaser", "accountant", "admin", "partner")
_MAX_FILES = 10


def _parse_file_urls(payment) -> list[str]:
    if payment.file_urls:
        try:
            return json.loads(payment.file_urls)
        except Exception:
            pass
    if payment.file_url:
        return [payment.file_url]
    return []


def _save_file_urls(payment, urls: list[str]) -> None:
    payment.file_urls = json.dumps(urls) if urls else None
    payment.file_url = urls[0] if urls else None


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
    remaining = total - paid_cny
    # Tolerance = 0.5% of order total or 5 CNY minimum (covers FX rounding on RUB/USDT conversions)
    TOLERANCE = max(total * Decimal("0.005"), Decimal("5"))
    if paid_cny <= 0:
        order.payment_status = PaymentStatus.unpaid
    elif remaining <= TOLERANCE:
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
    """Recalculate order.supplier_payment_status based on ALL purchases linked to order."""
    from app.models.order_item import OrderItem
    from app.models.purchase_item import PurchaseItem

    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        return

    # Trade purchases: linked via PurchaseItem → OrderItem
    trade_result = await db.execute(
        select(Purchase.payment_status)
        .join(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == order_id, Purchase.is_deleted == False)
        .distinct()
    )
    # Logistics purchases: linked directly via Purchase.order_id
    logistics_result = await db.execute(
        select(Purchase.payment_status)
        .where(Purchase.order_id == order_id, Purchase.is_deleted == False)
        .distinct()
    )

    statuses = {row[0] for row in trade_result.all()} | {row[0] for row in logistics_result.all()}

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

    cash_reg = None
    if payment.cash_register_id:
        cash_reg = (await db.execute(
            select(CashRegister).where(CashRegister.id == payment.cash_register_id)
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

    urls = _parse_file_urls(payment)

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
        file_url=urls[0] if urls else None,
        file_urls=urls,
        pending_change=getattr(payment, "pending_change", None),
        cash_register_id=payment.cash_register_id,
        cash_register_name=cash_reg.name if cash_reg else None,
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
            # Guard: total allocations from ALL payments must not exceed order amount
            other_alloc = (await db.execute(
                select(func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")))
                .join(Payment, PaymentAllocation.payment_id == Payment.id)
                .where(
                    PaymentAllocation.order_id == alloc.order_id,
                    PaymentAllocation.payment_id != payment.id,
                    Payment.is_active == True,
                )
            )).scalar_one() or Decimal("0")
            order_total = order.total_sale_cny or Decimal("0")
            order_tolerance = max(order_total * Decimal("0.005"), Decimal("5"))
            if other_alloc + alloc.amount_cny > order_total + order_tolerance:
                raise HTTPException(
                    422,
                    f"Order {order.order_number}: allocation would exceed order amount "
                    f"({other_alloc + alloc.amount_cny:.2f} > {order_total:.2f} CNY)"
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
        affected_client_ids: set = set()
        for row in alloc_rows.all():
            await _recalc_order_payment_status(db, row[0])
            # Обновляем статус оплаты торгового заказа на сайте
            try:
                order_obj = (await db.execute(
                    select(Order).where(Order.id == row[0])
                )).scalar_one_or_none()
                if order_obj:
                    affected_client_ids.add(order_obj.client_id)
                    if order_obj.sync_status == "synced":
                        from app.models.business_type import BusinessType
                        bt = (await db.execute(
                            select(BusinessType).where(BusinessType.id == order_obj.business_type_id)
                        )).scalar_one_or_none()
                        if bt and bt.code == "trade":
                            from app.integrations.irsway_site.service import sync_trade_order_to_site
                            await sync_trade_order_to_site(order_obj, db)
            except Exception:
                pass
        # Push reconciliation for affected clients
        for cid in affected_client_ids:
            try:
                from app.integrations.irsway_site.service import push_reconciliation_to_site
                await push_reconciliation_to_site(cid, db)
            except Exception:
                pass
    else:
        link_rows = await db.execute(
            select(PurchasePaymentLink.purchase_id)
            .where(PurchasePaymentLink.payment_id == payment.id)
        )
        for row in link_rows.all():
            purchase_id = row[0]
            await _recalc_purchase_payment_status(db, purchase_id)

            affected_order_ids: set = set()

            # Торговые закупки: order через PurchaseItem → OrderItem
            from app.models.purchase_item import PurchaseItem
            from app.models.order_item import OrderItem
            order_rows = await db.execute(
                select(OrderItem.order_id)
                .join(PurchaseItem, PurchaseItem.order_item_id == OrderItem.id)
                .where(PurchaseItem.purchase_id == purchase_id)
                .distinct()
            )
            for orow in order_rows.all():
                affected_order_ids.add(orow[0])

            # Логистические закупки: order через Purchase.order_id напрямую
            pur_row = await db.execute(
                select(Purchase.order_id).where(Purchase.id == purchase_id)
            )
            direct_order_id = pur_row.scalar_one_or_none()
            if direct_order_id:
                affected_order_ids.add(direct_order_id)

            for order_id in affected_order_ids:
                await _recalc_order_supplier_payment_status(db, order_id)


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
    created_by_id: Optional[uuid.UUID] = Query(None),
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
    if created_by_id:
        stmt = stmt.where(Payment.created_by == created_by_id)

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

    # Validate cash register
    cash_reg = (await db.execute(
        select(CashRegister).where(CashRegister.id == body.cash_register_id, CashRegister.is_active == True)
    )).scalar_one_or_none()
    if not cash_reg:
        raise HTTPException(422, "Касса не найдена или неактивна")

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
        cash_register_id=body.cash_register_id,
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

    # Проверяем: все ли аллокации ведут на исключённые записи → не создаём CashTransaction
    skip_cash_tx = False
    if body.allocations:
        excluded_count = 0
        for alloc in body.allocations:
            if alloc.order_id:
                excl = (await db.execute(
                    select(Order.excluded_from_accounting).where(Order.id == alloc.order_id)
                )).scalar_one_or_none()
                if excl:
                    excluded_count += 1
            elif alloc.purchase_id:
                excl = (await db.execute(
                    select(Purchase.excluded_from_accounting).where(Purchase.id == alloc.purchase_id)
                )).scalar_one_or_none()
                if excl:
                    excluded_count += 1
        skip_cash_tx = (excluded_count == len(body.allocations) and excluded_count > 0)

    if not skip_cash_tx:
        # Создаём транзакцию кассы — сумма в ВАЛЮТЕ КАССЫ
        from app.api.cash_registers import _get_balance
        reg = (await db.execute(
            select(CashRegister).where(CashRegister.id == body.cash_register_id)
        )).scalar_one()
        reg_currency = reg.currency

        _RANK = {"USD": 3, "USDT": 2, "CNY": 1, "RUB": 0}
        exp_rank = _RANK.get(body.currency, 1)
        reg_rank = _RANK.get(reg_currency, 1)

        if body.currency == reg_currency:
            cash_amount = body.amount
        elif reg_currency == "CNY":
            cash_amount = amount_cny
        else:
            if not body.cash_rate or body.cash_rate <= 0:
                raise HTTPException(
                    422,
                    f"cross_currency_rate_required:{body.currency}:{reg_currency}"
                )
            if exp_rank > reg_rank:
                # Платёж в крупной валюте (напр. USD→CNY): cash_rate = 1 USD = X CNY
                cash_amount = (body.amount * body.cash_rate).quantize(Decimal("0.000001"))
            else:
                # Платёж в мелкой валюте (напр. CNY→USDT): cash_rate = 1 USDT = X CNY
                cash_amount = (body.amount / body.cash_rate).quantize(Decimal("0.000001"))

        current_balance = await _get_balance(db, body.cash_register_id)
        tx_direction = "in" if body.direction == "in" else "out"
        new_balance = current_balance + cash_amount if tx_direction == "in" else current_balance - cash_amount
        cash_tx = CashTransaction(
            id=uuid.uuid4(),
            cash_register_id=body.cash_register_id,
            payment_id=payment.id,
            direction=tx_direction,
            amount=cash_amount,
            balance_after=new_balance,
            operation_type="payment_in" if tx_direction == "in" else "payment_out",
            notes=body.notes,   # пользовательский текст (примечание к платежу)
            created_by=current_user.id,
        )
        db.add(cash_tx)
        await db.flush()
        await write_audit(db, current_user.id, "cash_transaction", cash_tx.id, AuditActionEnum.create, {
            "register_id": str(body.cash_register_id),
            "direction": tx_direction,
            "amount": str(body.amount),
            "reason": "payment",
            "payment_id": str(payment.id),
        })

    await _apply_allocations(db, payment, body.allocations)
    await db.flush()

    await _recalc_all_for_payment(db, payment)

    await write_audit(
        db, current_user.id, "payment", payment.id, AuditActionEnum.create,
        {"direction": body.direction, "amount_cny": str(amount_cny),
         "counterparty": cp.name, "allocations": len(body.allocations)}
    )
    # Notify: unassigned incoming payment
    if body.direction == "in" and not body.allocations:
        await on_payment_unassigned(db, payment.id, str(body.amount), body.currency, cp.name)
    # Notify: order fully paid
    if body.direction == "in" and body.allocations:
        for alloc in body.allocations:
            if alloc.order_id:
                order = (await db.execute(select(Order).where(Order.id == alloc.order_id))).scalar_one_or_none()
                if order and order.payment_status == "paid":
                    client = (await db.execute(select(Counterparty).where(Counterparty.id == order.client_id))).scalar_one_or_none()
                    await on_order_paid(db, order.id, order.order_number, order.manager_id,
                                        client.name if client else "", str(order.total_sale_cny))
    # Notify: purchase fully paid + clear payment_requested
    if body.direction == "out" and body.allocations:
        for alloc in body.allocations:
            if alloc.purchase_id:
                pur = (await db.execute(select(Purchase).where(Purchase.id == alloc.purchase_id))).scalar_one_or_none()
                if pur:
                    if pur.payment_requested:
                        pur.payment_requested = False
                        pur.payment_requested_by = None
                        pur.payment_requested_at = None
                    if pur.payment_status == "paid":
                        await on_purchase_paid(db, pur.id, pur.purchase_number,
                                               pur.created_by, str(pur.total_amount_cny))
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

    # Non-accountants cannot change financial fields directly
    _ACCOUNTANT = ("accountant", "admin")
    if not current_user.has_role(*_ACCOUNTANT):
        blocked = {"amount", "currency", "rate_to_cny"} & set(update_data.keys())
        if blocked:
            raise HTTPException(403, "Изменение суммы требует подтверждения. Используйте запрос на изменение суммы.")

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


# ── amount change request workflow ───────────────────────────────────────────

import datetime as _pdatetime

class PaymentChangeRequestBody(BaseModel):
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    rate_to_cny: Optional[Decimal] = None
    reason: str = ""


@router.post("/{payment_id}/request-change", status_code=200)
async def request_payment_change(
    payment_id: uuid.UUID,
    body: PaymentChangeRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    pending = {
        "amount": str(body.amount) if body.amount is not None else str(payment.amount),
        "currency": body.currency or str(payment.currency.value if hasattr(payment.currency, "value") else payment.currency),
        "rate_to_cny": str(body.rate_to_cny) if body.rate_to_cny is not None else str(payment.rate_to_cny),
        "reason": body.reason,
        "requested_by": str(current_user.id),
        "requested_by_name": current_user.full_name or "",
        "requested_at": _pdatetime.datetime.utcnow().isoformat(),
    }
    payment.pending_change = json.dumps(pending, ensure_ascii=False)
    await write_audit(db, current_user.id, "payment", payment.id, AuditActionEnum.update,
                      {"change_requested": pending})
    await db.commit()
    return {"ok": True}


@router.post("/{payment_id}/approve-change", response_model=PaymentResponse)
async def approve_payment_change(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("accountant", "admin")),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")
    if not getattr(payment, "pending_change", None):
        raise HTTPException(404, "Нет активного запроса на изменение")

    pending = json.loads(payment.pending_change)
    payment.amount = Decimal(pending["amount"])
    payment.rate_to_cny = Decimal(pending["rate_to_cny"])
    payment.amount_cny = (payment.amount * payment.rate_to_cny).quantize(Decimal("0.01"))
    payment.pending_change = None
    await _recalc_all_for_payment(db, payment)
    await write_audit(db, current_user.id, "payment", payment.id, AuditActionEnum.update,
                      {"change_approved": pending})
    await db.commit()
    return await _load_payment(db, payment.id)


@router.post("/{payment_id}/reject-change", response_model=PaymentResponse)
async def reject_payment_change(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("accountant", "admin")),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")
    payment.pending_change = None
    await write_audit(db, current_user.id, "payment", payment.id, AuditActionEnum.update,
                      {"change_rejected": True})
    await db.commit()
    return await _load_payment(db, payment.id)


class DeleteBody(BaseModel):
    reason: str

    @validator("reason")
    def reason_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Укажите причину удаления")
        return v.strip()


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: uuid.UUID,
    body: DeleteBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    payment.is_active = False
    await db.flush()

    # Откат кассы: для каждой активной транзакции этого платежа создаём компенсирующую
    cash_txs = (await db.execute(
        select(CashTransaction).where(
            CashTransaction.payment_id == payment_id,
            CashTransaction.is_active == True,
        )
    )).scalars().all()

    from app.api.cash_registers import _get_balance
    for tx in cash_txs:
        comp_direction = "out" if tx.direction == "in" else "in"
        cur_bal = await _get_balance(db, tx.cash_register_id)
        comp_amount = tx.amount
        new_bal = cur_bal + comp_amount if comp_direction == "in" else cur_bal - comp_amount
        comp_tx = CashTransaction(
            id=uuid.uuid4(),
            cash_register_id=tx.cash_register_id,
            direction=comp_direction,
            amount=comp_amount,
            balance_after=new_bal,
            operation_type="payment_cancel",
            notes=payment.notes or str(payment.id)[:8],  # пользовательский текст платежа
            created_by=current_user.id,
        )
        db.add(comp_tx)
        await db.flush()
        await write_audit(db, current_user.id, "cash_transaction", comp_tx.id, AuditActionEnum.create, {
            "register_id": str(tx.cash_register_id),
            "direction": comp_direction,
            "amount": str(comp_amount),
            "reason": "payment_deleted",
            "original_tx_id": str(tx.id),
            "payment_id": str(payment_id),
        })

    # Recalculate affected statuses (must happen before deleting allocations
    # so _recalc_all_for_payment knows which orders/purchases to touch)
    await _recalc_all_for_payment(db, payment)

    # Remove allocations that are now dead (payment is inactive)
    await db.execute(delete(PaymentAllocation).where(PaymentAllocation.payment_id == payment_id))
    await db.execute(delete(PurchasePaymentLink).where(PurchasePaymentLink.payment_id == payment_id))
    await db.flush()

    await write_audit(
        db, current_user.id, "payment", payment.id, AuditActionEnum.delete,
        {"soft_deleted": True, "cash_compensations": len(cash_txs), "reason": body.reason,
         "amount_cny": str(payment.amount_cny), "direction": payment.direction}
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
        .with_for_update()
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    # Replace existing allocations for the same orders/purchases (prevent duplicates).
    # If an allocation for the same order already exists from this payment, it is replaced.
    if payment.direction == "in":
        order_ids = [a.order_id for a in allocations if a.order_id]
        if order_ids:
            await db.execute(
                delete(PaymentAllocation).where(
                    PaymentAllocation.payment_id == payment_id,
                    PaymentAllocation.order_id.in_(order_ids),
                )
            )
            await db.flush()
    else:
        purchase_ids = [a.purchase_id for a in allocations if a.purchase_id]
        if purchase_ids:
            await db.execute(
                delete(PurchasePaymentLink).where(
                    PurchasePaymentLink.payment_id == payment_id,
                    PurchasePaymentLink.purchase_id.in_(purchase_ids),
                )
            )
            await db.flush()

    # Check remaining allocations after replacement
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


@router.get("/balance/counterparty/{counterparty_id}", response_model=CounterpartyBalance)
async def get_counterparty_payment_balance(
    counterparty_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("manager", "purchaser", "accountant", "admin")),
):
    from app.schemas.payment import UnallocatedPaymentItem

    # All incoming payments for this client with cash register info
    pay_rows = (await db.execute(
        select(Payment, CashRegister)
        .outerjoin(CashRegister, Payment.cash_register_id == CashRegister.id)
        .where(
            Payment.counterparty_id == counterparty_id,
            Payment.is_active == True,
            Payment.direction == "in",
        )
        .order_by(Payment.payment_date.desc())
    )).all()
    payments = [r[0] for r in pay_rows]
    reg_map: dict = {r[0].id: r[1] for r in pay_rows}

    total_paid = sum(p.amount_cny for p in payments) or Decimal("0")

    # Allocations per payment
    if payments:
        pay_ids = [p.id for p in payments]
        alloc_rows = (await db.execute(
            select(
                PaymentAllocation.payment_id,
                func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")).label("alloc"),
            )
            .where(PaymentAllocation.payment_id.in_(pay_ids))
            .group_by(PaymentAllocation.payment_id)
        )).all()
        alloc_map: dict = {r[0]: r[1] for r in alloc_rows}
    else:
        alloc_map = {}

    total_alloc = sum(alloc_map.values()) or Decimal("0")

    unallocated_payments = []
    for p in payments:
        paid = p.amount_cny or Decimal("0")
        alloc = alloc_map.get(p.id, Decimal("0"))
        unalloc = max(paid - alloc, Decimal("0"))
        if unalloc > Decimal("0.01"):
            reg = reg_map.get(p.id)
            unallocated_payments.append(UnallocatedPaymentItem(
                payment_id=p.id,
                payment_date=str(p.payment_date),
                amount=p.amount,
                currency=p.currency.value if hasattr(p.currency, 'value') else str(p.currency),
                amount_cny=paid,
                unallocated_cny=unalloc,
                cash_register_id=reg.id if reg else None,
                cash_register_name=reg.name if reg else None,
                cash_register_currency=reg.currency if reg else None,
            ))

    return CounterpartyBalance(
        counterparty_id=counterparty_id,
        total_paid_cny=total_paid,
        total_allocated_cny=total_alloc,
        unallocated_cny=max(total_paid - total_alloc, Decimal("0")),
        unallocated_payments=unallocated_payments,
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


# ── Receipt upload for payment ────────────────────────────────────────────────

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
_MAX_FILE_SIZE = 10 * 1024 * 1024
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@router.post("/{payment_id}/receipt")
async def upload_payment_receipt(
    payment_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    urls = _parse_file_urls(payment)
    if len(urls) >= _MAX_FILES:
        raise HTTPException(422, f"Максимум {_MAX_FILES} файлов на платёж")

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")
    mime = file.content_type or ""
    if mime not in _ALLOWED_MIME:
        raise HTTPException(422, "Allowed: jpg, png, webp, pdf")

    dest_dir = UPLOADS_DIR / "payments" / str(payment_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "file").suffix.lower() or ".bin"
    stored_name = f"{uuid.uuid4()}{ext}"
    (dest_dir / stored_name).write_bytes(content)

    urls.append(f"payments/{payment_id}/{stored_name}")
    _save_file_urls(payment, urls)

    await write_audit(db, current_user.id, "payment", payment.id, AuditActionEnum.update,
                      {"receipt_uploaded": file.filename, "total_files": len(urls)})
    await db.commit()
    return await _load_payment(db, payment.id)


@router.delete("/{payment_id}/receipt/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_receipt_file(
    payment_id: uuid.UUID,
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    urls = _parse_file_urls(payment)
    target = f"payments/{payment_id}/{filename}"
    if target not in urls:
        raise HTTPException(404, "File not found")

    file_path = UPLOADS_DIR / target
    if file_path.exists():
        file_path.unlink()

    urls.remove(target)
    _save_file_urls(payment, urls)

    await write_audit(db, current_user.id, "payment", payment.id, AuditActionEnum.update,
                      {"receipt_deleted": filename, "remaining_files": len(urls)})
    await db.commit()


@router.delete("/{payment_id}/receipt", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_receipt(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить все файлы платежа (backward-compat)."""
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.is_active == True)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment not found")

    urls = _parse_file_urls(payment)
    if not urls:
        raise HTTPException(404, "No receipt")

    for url in urls:
        file_path = UPLOADS_DIR / url
        if file_path.exists():
            file_path.unlink()

    _save_file_urls(payment, [])
    await write_audit(db, current_user.id, "payment", payment.id, AuditActionEnum.update,
                      {"receipt_deleted_all": True})
    await db.commit()
