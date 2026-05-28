from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, not_

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.purchase import Purchase
from app.models.payment import Payment, PaymentDirection
from app.models.payment_allocation import PaymentAllocation
from app.models.purchase_payment_link import PurchasePaymentLink
from app.models.expense import Expense, ReimburseStatusEnum
from app.models.expense_category import ExpenseCategory
from app.models.counterparty import Counterparty
from app.models.warehouse import Warehouse
from app.models.business_type import BusinessType

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

D0 = Decimal("0")


def _d(v) -> str:
    return str(v or D0)


# ── existing balances endpoint (kept for backwards compat) ──────────────────

@router.get("/balances")
async def get_dashboard_balances(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.models.order import OrderStatus
    order_paid_sq = (
        select(
            PaymentAllocation.order_id,
            func.coalesce(func.sum(PaymentAllocation.amount_cny), D0).label("paid_cny"),
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
                func.sum(Order.total_sale_cny - func.coalesce(order_paid_sq.c.paid_cny, D0)),
                D0,
            ).label("remaining"),
        )
        .outerjoin(order_paid_sq, Order.id == order_paid_sq.c.order_id)
        .where(Order.status != OrderStatus.cancelled, Order.payment_status != "paid")
    )).one()

    pur_paid_sq = (
        select(
            PurchasePaymentLink.purchase_id,
            func.coalesce(func.sum(PurchasePaymentLink.amount_cny), D0).label("paid_cny"),
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
                func.sum(Purchase.total_amount_cny - func.coalesce(pur_paid_sq.c.paid_cny, D0)),
                D0,
            ).label("remaining"),
        )
        .outerjoin(pur_paid_sq, Purchase.id == pur_paid_sq.c.purchase_id)
        .where(Purchase.is_deleted == False, Purchase.payment_status != "paid")
    )).one()

    return {
        "total_receivable_cny": _d(order_row.remaining),
        "total_payable_cny": _d(pur_row.remaining),
        "unpaid_orders_count": order_row.cnt or 0,
        "unpaid_purchases_count": pur_row.cnt or 0,
    }


# ── main widgets endpoint ────────────────────────────────────────────────────

@router.get("/widgets")
async def get_widgets(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    if not date_from:
        date_from = today.replace(day=1)
    if not date_to:
        date_to = today

    result: dict = {}
    roles = set(user.roles)

    # ── TONNAGE (manager, admin, accountant) ────────────────────────────────
    if roles & {"manager", "admin", "accountant"}:
        rows = (await db.execute(
            select(
                Warehouse.name.label("warehouse"),
                func.coalesce(func.sum(OrderItem.weight_kg), D0).label("total_kg"),
            )
            .join(Order, Order.warehouse_id == Warehouse.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.order_date >= date_from,
                Order.order_date <= date_to,
                Order.status != OrderStatus.cancelled,
                OrderItem.weight_kg.isnot(None),
            )
            .group_by(Warehouse.name)
            .order_by(func.sum(OrderItem.weight_kg).desc())
        )).all()
        result["tonnage"] = [{"warehouse": r.warehouse, "kg": float(r.total_kg)} for r in rows]

    # ── ADMIN / ACCOUNTANT widgets ──────────────────────────────────────────
    if roles & {"admin", "accountant"}:

        # Finances: incoming payments (revenue) and outgoing (purchases paid)
        pay_rows = (await db.execute(
            select(
                Payment.direction,
                func.coalesce(func.sum(Payment.amount_cny), D0).label("total"),
            )
            .where(
                Payment.is_active == True,
                Payment.payment_date >= date_from,
                Payment.payment_date <= date_to,
            )
            .group_by(Payment.direction)
        )).all()
        revenue = D0
        purchases_paid = D0
        for r in pay_rows:
            if str(r.direction) in ("in", "PaymentDirection.incoming"):
                revenue = r.total or D0
            else:
                purchases_paid = r.total or D0

        expenses_sum = (await db.execute(
            select(func.coalesce(func.sum(Expense.amount_cny), D0))
            .where(
                Expense.is_active == True,
                Expense.expense_date >= date_from,
                Expense.expense_date <= date_to,
                not_(and_(
                    Expense.is_reimbursement == True,
                    Expense.reimburse_status == ReimburseStatusEnum.rejected,
                )),
            )
        )).scalar_one() or D0

        profit = revenue - purchases_paid - expenses_sum

        # Previous period delta
        period_days = (date_to - date_from).days + 1
        prev_from = date_from - timedelta(days=period_days)
        prev_to = date_from - timedelta(days=1)

        prev_pay = (await db.execute(
            select(
                Payment.direction,
                func.coalesce(func.sum(Payment.amount_cny), D0).label("total"),
            )
            .where(
                Payment.is_active == True,
                Payment.payment_date >= prev_from,
                Payment.payment_date <= prev_to,
            )
            .group_by(Payment.direction)
        )).all()
        prev_revenue = D0
        for r in prev_pay:
            if str(r.direction) in ("in", "PaymentDirection.incoming"):
                prev_revenue = r.total or D0

        def pct_change(current, previous):
            if not previous:
                return None
            return round(float((current - previous) / previous * 100), 1)

        result["finances"] = {
            "revenue": _d(revenue),
            "purchases_paid": _d(purchases_paid),
            "expenses": _d(expenses_sum),
            "profit": _d(profit),
            "revenue_change_pct": pct_change(revenue, prev_revenue),
        }

        # Profit dynamics — last 6 months
        six_months_ago = today.replace(day=1) - timedelta(days=150)
        dyn_rows = (await db.execute(
            select(
                func.date_trunc("month", Payment.payment_date).label("month"),
                Payment.direction,
                func.coalesce(func.sum(Payment.amount_cny), D0).label("total"),
            )
            .where(
                Payment.is_active == True,
                Payment.payment_date >= six_months_ago,
            )
            .group_by(func.date_trunc("month", Payment.payment_date), Payment.direction)
            .order_by(func.date_trunc("month", Payment.payment_date))
        )).all()

        months: dict = {}
        for r in dyn_rows:
            m = r.month.strftime("%Y-%m")
            if m not in months:
                months[m] = {"month": m, "revenue": D0, "cost": D0}
            if str(r.direction) in ("in", "PaymentDirection.incoming"):
                months[m]["revenue"] = r.total or D0
            else:
                months[m]["cost"] = r.total or D0

        exp_dyn = (await db.execute(
            select(
                func.date_trunc("month", Expense.expense_date).label("month"),
                func.coalesce(func.sum(Expense.amount_cny), D0).label("total"),
            )
            .where(
                Expense.is_active == True,
                Expense.expense_date >= six_months_ago,
                not_(and_(
                    Expense.is_reimbursement == True,
                    Expense.reimburse_status == ReimburseStatusEnum.rejected,
                )),
            )
            .group_by(func.date_trunc("month", Expense.expense_date))
        )).all()
        for r in exp_dyn:
            m = r.month.strftime("%Y-%m")
            if m not in months:
                months[m] = {"month": m, "revenue": D0, "cost": D0}
            months[m]["expenses"] = r.total or D0

        result["profit_dynamics"] = [
            {
                "month": v["month"],
                "revenue": float(v["revenue"]),
                "profit": float(v["revenue"] - v.get("cost", D0) - v.get("expenses", D0)),
            }
            for v in sorted(months.values(), key=lambda x: x["month"])
        ]

        # Debts
        order_paid_sq = (
            select(PaymentAllocation.order_id,
                   func.coalesce(func.sum(PaymentAllocation.amount_cny), D0).label("paid"))
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .where(Payment.is_active == True)
            .group_by(PaymentAllocation.order_id).subquery()
        )
        receivable = (await db.execute(
            select(func.coalesce(func.sum(
                Order.total_sale_cny - func.coalesce(order_paid_sq.c.paid, D0)
            ), D0))
            .outerjoin(order_paid_sq, Order.id == order_paid_sq.c.order_id)
            .where(Order.status != OrderStatus.cancelled, Order.payment_status != "paid")
        )).scalar_one() or D0

        pur_paid_sq = (
            select(PurchasePaymentLink.purchase_id,
                   func.coalesce(func.sum(PurchasePaymentLink.amount_cny), D0).label("paid"))
            .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
            .where(Payment.is_active == True)
            .group_by(PurchasePaymentLink.purchase_id).subquery()
        )
        payable = (await db.execute(
            select(func.coalesce(func.sum(
                Purchase.total_amount_cny - func.coalesce(pur_paid_sq.c.paid, D0)
            ), D0))
            .outerjoin(pur_paid_sq, Purchase.id == pur_paid_sq.c.purchase_id)
            .where(Purchase.is_deleted == False, Purchase.payment_status != "paid")
        )).scalar_one() or D0

        result["debts"] = {"receivable": _d(receivable), "payable": _d(payable)}

        # Top 5 clients by revenue
        top_clients = (await db.execute(
            select(
                Counterparty.name.label("client"),
                func.coalesce(func.sum(Payment.amount_cny), D0).label("revenue"),
            )
            .join(Order, Order.client_id == Counterparty.id)
            .join(PaymentAllocation, PaymentAllocation.order_id == Order.id)
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .where(
                Payment.is_active == True,
                Payment.direction == PaymentDirection.incoming,
                Payment.payment_date >= date_from,
                Payment.payment_date <= date_to,
            )
            .group_by(Counterparty.name)
            .order_by(func.sum(Payment.amount_cny).desc())
            .limit(5)
        )).all()
        result["top_clients"] = [
            {"client": r.client, "revenue": float(r.revenue)} for r in top_clients
        ]

        # Expense structure by category
        exp_cats = (await db.execute(
            select(
                ExpenseCategory.name.label("category"),
                func.coalesce(func.sum(Expense.amount_cny), D0).label("total"),
            )
            .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
            .where(
                Expense.is_active == True,
                Expense.expense_date >= date_from,
                Expense.expense_date <= date_to,
                not_(and_(
                    Expense.is_reimbursement == True,
                    Expense.reimburse_status == ReimburseStatusEnum.rejected,
                )),
            )
            .group_by(ExpenseCategory.name)
            .order_by(func.sum(Expense.amount_cny).desc())
        )).all()
        result["expense_structure"] = [
            {"category": r.category, "value": float(r.total)} for r in exp_cats
        ]

    # ── MANAGER widgets ──────────────────────────────────────────────────────
    if "manager" in roles:
        my_orders = (await db.execute(
            select(
                Order.status,
                func.count(Order.id).label("cnt"),
                func.coalesce(func.sum(Order.total_sale_cny), D0).label("revenue"),
            )
            .where(
                Order.manager_id == user.id,
                Order.order_date >= date_from,
                Order.order_date <= date_to,
                Order.status != OrderStatus.cancelled,
            )
            .group_by(Order.status)
        )).all()

        status_counts = {r.status: r.cnt for r in my_orders}
        my_revenue = sum(r.revenue or D0 for r in my_orders)

        # My client debts
        my_order_paid_sq = (
            select(PaymentAllocation.order_id,
                   func.coalesce(func.sum(PaymentAllocation.amount_cny), D0).label("paid"))
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .where(Payment.is_active == True)
            .group_by(PaymentAllocation.order_id).subquery()
        )
        my_debt = (await db.execute(
            select(func.coalesce(func.sum(
                Order.total_sale_cny - func.coalesce(my_order_paid_sq.c.paid, D0)
            ), D0))
            .outerjoin(my_order_paid_sq, Order.id == my_order_paid_sq.c.order_id)
            .where(
                Order.manager_id == user.id,
                Order.status != OrderStatus.cancelled,
                Order.payment_status != "paid",
            )
        )).scalar_one() or D0

        # Recent 10 orders
        recent = (await db.execute(
            select(Order.id, Order.order_number, Order.order_date,
                   Order.status, Order.total_sale_cny, Counterparty.name.label("client"))
            .join(Counterparty, Order.client_id == Counterparty.id)
            .where(Order.manager_id == user.id, Order.status != OrderStatus.cancelled)
            .order_by(Order.order_date.desc(), Order.order_number.desc())
            .limit(10)
        )).all()

        result["my_orders"] = {
            "new": status_counts.get("new", 0),
            "active": status_counts.get("active", 0),
            "closed": status_counts.get("closed", 0),
            "revenue": _d(my_revenue),
            "client_debt": _d(my_debt),
        }
        result["recent_orders"] = [
            {
                "id": str(r.id), "order_number": r.order_number,
                "order_date": str(r.order_date), "status": r.status,
                "total_sale_cny": float(r.total_sale_cny or D0),
                "client": r.client,
            }
            for r in recent
        ]

    # ── PURCHASER widgets ────────────────────────────────────────────────────
    if "purchaser" in roles:
        my_purch = (await db.execute(
            select(
                func.count(Purchase.id).label("cnt"),
                func.coalesce(func.sum(Purchase.total_amount_cny), D0).label("total"),
            )
            .where(
                Purchase.created_by == user.id,
                Purchase.is_deleted == False,
                Purchase.purchase_date >= date_from,
                Purchase.purchase_date <= date_to,
            )
        )).one()

        # Supplier debt for my purchases
        pur_paid_sq2 = (
            select(PurchasePaymentLink.purchase_id,
                   func.coalesce(func.sum(PurchasePaymentLink.amount_cny), D0).label("paid"))
            .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
            .where(Payment.is_active == True)
            .group_by(PurchasePaymentLink.purchase_id).subquery()
        )
        my_supplier_debt = (await db.execute(
            select(func.coalesce(func.sum(
                Purchase.total_amount_cny - func.coalesce(pur_paid_sq2.c.paid, D0)
            ), D0))
            .outerjoin(pur_paid_sq2, Purchase.id == pur_paid_sq2.c.purchase_id)
            .where(
                Purchase.created_by == user.id,
                Purchase.is_deleted == False,
                Purchase.payment_status != "paid",
            )
        )).scalar_one() or D0

        # To purchase: orders with remaining items
        from app.models.purchase_item import PurchaseItem
        purchased_sq = (
            select(
                PurchaseItem.order_item_id,
                func.coalesce(func.sum(PurchaseItem.quantity), D0).label("bought"),
            )
            .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
            .where(Purchase.is_deleted == False)
            .group_by(PurchaseItem.order_item_id)
            .subquery()
        )
        needs_purchase = (await db.execute(
            select(
                Order.id.label("order_id"),
                Order.order_number,
                Counterparty.name.label("client"),
                func.sum(
                    OrderItem.quantity - func.coalesce(purchased_sq.c.bought, D0)
                ).label("remaining_qty"),
            )
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(Counterparty, Order.client_id == Counterparty.id)
            .outerjoin(purchased_sq, purchased_sq.c.order_item_id == OrderItem.id)
            .where(
                Order.status.in_(["new", "active"]),
                OrderItem.quantity.isnot(None),
            )
            .group_by(Order.id, Order.order_number, Counterparty.name)
            .having(func.sum(OrderItem.quantity - func.coalesce(purchased_sq.c.bought, D0)) > 0)
            .order_by(Order.order_date.desc())
            .limit(20)
        )).all()

        # Top 5 suppliers
        top_suppliers = (await db.execute(
            select(
                Counterparty.name.label("supplier"),
                func.coalesce(func.sum(Purchase.total_amount_cny), D0).label("total"),
            )
            .join(Counterparty, Purchase.supplier_id == Counterparty.id)
            .where(
                Purchase.is_deleted == False,
                Purchase.purchase_date >= date_from,
                Purchase.purchase_date <= date_to,
            )
            .group_by(Counterparty.name)
            .order_by(func.sum(Purchase.total_amount_cny).desc())
            .limit(5)
        )).all()

        result["my_purchases"] = {
            "count": my_purch.cnt or 0,
            "total_cny": _d(my_purch.total),
            "supplier_debt": _d(my_supplier_debt),
        }
        result["needs_purchase"] = [
            {
                "order_id": str(r.order_id), "order_number": r.order_number,
                "client": r.client, "remaining_qty": float(r.remaining_qty or 0),
            }
            for r in needs_purchase
        ]
        result["top_suppliers"] = [
            {"supplier": r.supplier, "total": float(r.total)} for r in top_suppliers
        ]

    # ── EMPLOYEE widgets ─────────────────────────────────────────────────────
    if "employee" in roles or not (roles & {"admin", "accountant", "manager", "purchaser"}):
        reimb_rows = (await db.execute(
            select(
                Expense.reimburse_status,
                func.count(Expense.id).label("cnt"),
                func.coalesce(func.sum(Expense.amount_cny), D0).label("total"),
            )
            .where(
                Expense.is_reimbursement == True,
                Expense.is_active == True,
                Expense.reimburse_to_user_id == user.id,
                Expense.expense_date >= date_from,
                Expense.expense_date <= date_to,
            )
            .group_by(Expense.reimburse_status)
        )).all()

        reimb_by_status = {str(r.reimburse_status): {"cnt": r.cnt, "total": float(r.total or D0)}
                           for r in reimb_rows}

        # Balance: approved but not yet paid
        balance_row = (await db.execute(
            select(func.coalesce(func.sum(Expense.amount_cny), D0))
            .where(
                Expense.is_reimbursement == True,
                Expense.is_active == True,
                Expense.reimburse_to_user_id == user.id,
                Expense.reimburse_status == ReimburseStatusEnum.approved,
            )
        )).scalar_one() or D0

        result["my_reimbursements"] = {
            "by_status": reimb_by_status,
            "balance_owed": _d(balance_row),
        }

    return result
