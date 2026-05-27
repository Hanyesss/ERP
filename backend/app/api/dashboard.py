from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.core.deps import require_roles
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.purchase import Purchase
from app.models.payment import Payment
from app.models.payment_allocation import PaymentAllocation
from app.models.purchase_payment_link import PurchasePaymentLink

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/balances")
async def get_dashboard_balances(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("accountant", "admin")),
):
    order_paid_sq = (
        select(
            PaymentAllocation.order_id,
            func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")).label("paid_cny"),
        )
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(Payment.is_active == True)
        .group_by(PaymentAllocation.order_id)
        .subquery()
    )

    order_row = (await db.execute(
        select(
            func.count(Order.id).label("cnt"),
            func.coalesce(
                func.sum(Order.total_sale_cny - func.coalesce(order_paid_sq.c.paid_cny, Decimal("0"))),
                Decimal("0")
            ).label("remaining"),
        )
        .outerjoin(order_paid_sq, Order.id == order_paid_sq.c.order_id)
        .where(Order.status != OrderStatus.cancelled, Order.payment_status != "paid")
    )).one()

    pur_paid_sq = (
        select(
            PurchasePaymentLink.purchase_id,
            func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")).label("paid_cny"),
        )
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .where(Payment.is_active == True)
        .group_by(PurchasePaymentLink.purchase_id)
        .subquery()
    )

    pur_row = (await db.execute(
        select(
            func.count(Purchase.id).label("cnt"),
            func.coalesce(
                func.sum(Purchase.total_amount_cny - func.coalesce(pur_paid_sq.c.paid_cny, Decimal("0"))),
                Decimal("0")
            ).label("remaining"),
        )
        .outerjoin(pur_paid_sq, Purchase.id == pur_paid_sq.c.purchase_id)
        .where(Purchase.is_deleted == False, Purchase.payment_status != "paid")
    )).one()

    return {
        "total_receivable_cny": str(order_row.remaining or Decimal("0")),
        "total_payable_cny": str(pur_row.remaining or Decimal("0")),
        "unpaid_orders_count": order_row.cnt or 0,
        "unpaid_purchases_count": pur_row.cnt or 0,
    }
