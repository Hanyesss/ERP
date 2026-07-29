"""API планов платежей (ожидаемые оплаты по заказам/закупкам)."""
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from app.database import get_db
from app.core.deps import require_roles
from app.models.user import User
from app.models.payment_plan import PaymentPlan, PlanStatus
from app.models.payment import Payment
from app.models.counterparty import Counterparty
from app.models.order import Order
from app.models.purchase import Purchase

router = APIRouter(prefix="/api/payment-plans", tags=["payment-plans"])

_ALLOWED = ("manager", "purchaser", "accountant", "admin")


async def _plan_dict(db: AsyncSession, plan: PaymentPlan) -> dict:
    cp = (await db.execute(select(Counterparty.name).where(Counterparty.id == plan.counterparty_id))).scalar_one_or_none()
    doc_number = None
    if plan.order_id:
        doc_number = (await db.execute(select(Order.order_number).where(Order.id == plan.order_id))).scalar_one_or_none()
    elif plan.purchase_id:
        doc_number = (await db.execute(select(Purchase.purchase_number).where(Purchase.id == plan.purchase_id))).scalar_one_or_none()

    Creator = aliased(User)
    inst_rows = (await db.execute(
        select(Payment, Creator.full_name)
        .outerjoin(Creator, Payment.created_by == Creator.id)
        .where(Payment.plan_id == plan.id, Payment.is_active == True)
        .order_by(Payment.payment_date)
    )).all()
    installments = [{
        "id": str(p.id),
        "kind": p.installment_kind,
        "amount": p.amount,
        "currency": p.currency.value if hasattr(p.currency, "value") else p.currency,
        "amount_cny": p.amount_cny,
        "payment_date": str(p.payment_date),
        "created_by_name": cname or "",
    } for p, cname in inst_rows]

    paid_cny = sum((Decimal(str(i["amount_cny"])) for i in installments), Decimal("0"))
    remaining_cny = max((plan.expected_cny or Decimal("0")) - paid_cny, Decimal("0"))

    return {
        "id": str(plan.id),
        "direction": plan.direction,
        "order_id": str(plan.order_id) if plan.order_id else None,
        "purchase_id": str(plan.purchase_id) if plan.purchase_id else None,
        "doc_number": doc_number,
        "counterparty_id": str(plan.counterparty_id),
        "counterparty_name": cp,
        "currency": plan.currency,
        "expected_amount": plan.expected_amount,
        "expected_cny": plan.expected_cny,
        "paid_cny": paid_cny,
        "remaining_cny": remaining_cny,
        "status": plan.status.value if hasattr(plan.status, "value") else plan.status,
        "installments": installments,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


@router.get("")
async def list_plans(
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    stmt = select(PaymentPlan).where(PaymentPlan.is_active == True)
    if direction:
        stmt = stmt.where(PaymentPlan.direction == direction)
    if status:
        stmt = stmt.where(PaymentPlan.status == status)
    if search:
        cp_ids = select(Counterparty.id).where(Counterparty.name.ilike(f"%{search}%"))
        stmt = stmt.where(PaymentPlan.counterparty_id.in_(cp_ids))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(PaymentPlan.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    plans = (await db.execute(stmt)).scalars().all()
    return {
        "items": [await _plan_dict(db, p) for p in plans],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/{plan_id}")
async def get_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    plan = (await db.execute(select(PaymentPlan).where(PaymentPlan.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")
    return await _plan_dict(db, plan)
