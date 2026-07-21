"""Report aggregation service - all aggregations via SQL GROUP BY/SUM."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_, not_, text

from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.purchase import Purchase
from app.models.purchase_item import PurchaseItem
from app.models.purchase_payment_link import PurchasePaymentLink
from app.models.expense import Expense
from app.models.expense_category import ExpenseCategory
from app.models.counterparty import Counterparty
from app.models.payment import Payment
from app.models.payment_allocation import PaymentAllocation
from app.models.business_type import BusinessType
from app.models.warehouse import Warehouse
from app.models.user import User


def _prev_period(date_from: date, date_to: date):
    delta = date_to - date_from
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - delta
    return prev_from, prev_to


async def _calc_pnl_for_period(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    business_type_id: Optional[uuid.UUID] = None,
    warehouse_id: Optional[uuid.UUID] = None,
):
    D0 = Decimal("0")

    # Revenue = all incoming payments; outgoing = all supplier payments
    pay_filter = [
        Payment.is_active == True,
        Payment.payment_date >= date_from,
        Payment.payment_date <= date_to,
    ]

    revenue_row = await db.execute(
        select(func.coalesce(func.sum(Payment.amount_cny), D0))
        .where(*pay_filter, Payment.direction == "in")
    )
    revenue = revenue_row.scalar_one() or D0

    outgoing_row = await db.execute(
        select(func.coalesce(func.sum(Payment.amount_cny), D0))
        .where(*pay_filter, Payment.direction == "out")
    )
    outgoing = outgoing_row.scalar_one() or D0

    # All expenses in period
    exp_filter = [
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
        Expense.is_active == True,
        not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
    ]

    expenses_sum = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount_cny), D0)).where(*exp_filter)
    )).scalar_one() or D0

    # Expenses by category for pie chart
    cat_rows = await db.execute(
        select(
            ExpenseCategory.name,
            ExpenseCategory.name_cn,
            func.coalesce(func.sum(Expense.amount_cny), D0).label("amount_cny"),
        )
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*exp_filter)
        .group_by(ExpenseCategory.name, ExpenseCategory.name_cn)
        .order_by(func.sum(Expense.amount_cny).desc())
    )
    expenses_by_category = [
        {"category_name": r[0], "category_name_cn": r[1], "amount_cny": r[2] or D0}
        for r in cat_rows.all()
    ]

    net_profit = revenue - outgoing - expenses_sum

    return {
        "revenue": revenue,
        "outgoing": outgoing,
        "expenses": expenses_sum,
        "net_profit": net_profit,
        "expenses_by_category": expenses_by_category,
    }


async def get_pnl(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    business_type_id: Optional[uuid.UUID] = None,
    warehouse_id: Optional[uuid.UUID] = None,
):
    current = await _calc_pnl_for_period(db, date_from, date_to, business_type_id, warehouse_id)
    prev_from, prev_to = _prev_period(date_from, date_to)
    prev = await _calc_pnl_for_period(db, prev_from, prev_to, business_type_id, warehouse_id)

    def pct_change(curr, prev_val):
        if prev_val and prev_val != 0:
            return float(((curr - prev_val) / abs(prev_val)) * 100)
        return None

    return {
        "date_from": date_from,
        "date_to": date_to,
        "prev_date_from": prev_from,
        "prev_date_to": prev_to,
        **current,
        "prev_period": prev,
        "pct_revenue": pct_change(current["revenue"], prev["revenue"]),
        "pct_net_profit": pct_change(current["net_profit"], prev["net_profit"]),
    }


async def get_by_client(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    business_type_id: Optional[uuid.UUID] = None,
):
    order_filter = [
        Order.order_date >= date_from,
        Order.order_date <= date_to,
        Order.status != OrderStatus.cancelled,
        Order.excluded_from_accounting == False,
    ]
    if business_type_id:
        order_filter.append(Order.business_type_id == business_type_id)

    # Total incoming payments per client in period (not just allocated amounts)
    payment_sq = (
        select(
            Payment.counterparty_id,
            func.coalesce(func.sum(Payment.amount_cny), Decimal("0")).label("paid_cny"),
        )
        .where(
            Payment.is_active == True,
            Payment.direction == "in",
            Payment.payment_date >= date_from,
            Payment.payment_date <= date_to,
        )
        .group_by(Payment.counterparty_id)
        .subquery()
    )

    order_rows = await db.execute(
        select(
            Order.client_id,
            Counterparty.name.label("client_name"),
            func.coalesce(func.sum(Order.total_sale_cny), Decimal("0")).label("revenue"),
        )
        .join(Counterparty, Order.client_id == Counterparty.id)
        .where(*order_filter)
        .group_by(Order.client_id, Counterparty.name)
    )
    client_data = {
        row[0]: {
            "client_id": row[0],
            "client_name": row[1],
            "revenue": row[2] or Decimal("0"),
            "paid": Decimal("0"),
            "allocated": Decimal("0"),
            "cogs": Decimal("0"),
            "direct_expenses": Decimal("0"),
            "client_expenses": Decimal("0"),
            "paid_to_supplier": Decimal("0"),
        }
        for row in order_rows.all()
    }

    if not client_data:
        return []

    client_ids = list(client_data.keys())

    # Paid = allocations for orders IN the period (from active payments, no payment_date filter).
    # This correctly handles prepayments and payments made outside the report period.
    alloc_period_rows = await db.execute(
        select(
            Order.client_id,
            func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")).label("alloc_cny"),
        )
        .join(PaymentAllocation, PaymentAllocation.order_id == Order.id)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(
            *order_filter,
            Order.client_id.in_(client_ids),
            Payment.is_active == True,
        )
        .group_by(Order.client_id)
    )
    for row in alloc_period_rows.all():
        if row[0] in client_data:
            client_data[row[0]]["paid"] = row[1] or Decimal("0")

    # Unallocated balance = all-time incoming payments - all-time allocations to any order.
    # Needed to show how much client money is sitting unassigned.
    all_time_pay_rows = await db.execute(
        select(
            Payment.counterparty_id,
            func.coalesce(func.sum(Payment.amount_cny), Decimal("0")).label("total_in"),
        )
        .where(
            Payment.is_active == True,
            Payment.direction == "in",
            Payment.counterparty_id.in_(client_ids),
        )
        .group_by(Payment.counterparty_id)
    )
    all_time_pay = {row[0]: row[1] or Decimal("0") for row in all_time_pay_rows.all()}

    all_time_alloc_rows = await db.execute(
        select(
            Order.client_id,
            func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")).label("total_alloc"),
        )
        .join(PaymentAllocation, PaymentAllocation.order_id == Order.id)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(
            Order.client_id.in_(client_ids),
            Payment.is_active == True,
        )
        .group_by(Order.client_id)
    )
    all_time_alloc = {row[0]: row[1] or Decimal("0") for row in all_time_alloc_rows.all()}

    # COGS per client
    orders_subq = (
        select(Order.id, Order.client_id)
        .where(*order_filter)
        .subquery()
    )

    cogs_rows = await db.execute(
        select(
            orders_subq.c.client_id,
            func.coalesce(func.sum(PurchaseItem.cost_amount), Decimal("0")).label("cogs"),
        )
        .join(PurchaseItem, and_(
            PurchaseItem.purchase_id == Purchase.id,
        ))
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(orders_subq, OrderItem.order_id == orders_subq.c.id)
        .where(Purchase.is_deleted == False)
        .group_by(orders_subq.c.client_id)
        .select_from(Purchase)
    )
    for row in cogs_rows.all():
        if row[0] in client_data:
            client_data[row[0]]["cogs"] = row[1] or Decimal("0")

    # Direct expenses per client (via order link)
    direct_exp_rows = await db.execute(
        select(
            orders_subq.c.client_id,
            func.coalesce(func.sum(Expense.amount_cny), Decimal("0")).label("direct_exp"),
        )
        .join(orders_subq, Expense.order_id == orders_subq.c.id)
        .where(
            Expense.link_type == "order",
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
            Expense.is_active == True,
            not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
        )
        .group_by(orders_subq.c.client_id)
    )
    for row in direct_exp_rows.all():
        if row[0] in client_data:
            client_data[row[0]]["direct_expenses"] = row[1] or Decimal("0")

    # Client expenses per client
    client_exp_rows = await db.execute(
        select(
            Expense.client_id,
            func.coalesce(func.sum(Expense.amount_cny), Decimal("0")).label("client_exp"),
        )
        .where(
            Expense.link_type == "client",
            Expense.client_id.in_(client_ids),
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
            Expense.is_active == True,
            not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
        )
        .group_by(Expense.client_id)
    )
    for row in client_exp_rows.all():
        if row[0] in client_data:
            client_data[row[0]]["client_expenses"] = row[1] or Decimal("0")

    # paid_to_supplier: PurchasePaymentLink amounts for purchases linked to orders in period,
    # split proportionally by COGS share per client (handles multi-client purchases correctly)
    dir_pur_cogs_sq = (
        select(
            Purchase.id.label("purchase_id"),
            orders_subq.c.client_id,
            func.coalesce(func.sum(PurchaseItem.cost_amount), Decimal("0")).label("client_cogs"),
        )
        .select_from(Purchase)
        .join(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(orders_subq, OrderItem.order_id == orders_subq.c.id)
        .where(Purchase.is_deleted == False)
        .group_by(Purchase.id, orders_subq.c.client_id)
        .subquery()
    )
    pur_total_cogs_sq = (
        select(
            dir_pur_cogs_sq.c.purchase_id,
            func.sum(dir_pur_cogs_sq.c.client_cogs).label("total_cogs"),
        )
        .group_by(dir_pur_cogs_sq.c.purchase_id)
        .subquery()
    )
    paid_supplier_rows = await db.execute(
        select(
            dir_pur_cogs_sq.c.client_id,
            func.coalesce(
                func.sum(
                    PurchasePaymentLink.amount_cny *
                    dir_pur_cogs_sq.c.client_cogs /
                    func.nullif(pur_total_cogs_sq.c.total_cogs, 0)
                ),
                Decimal("0"),
            ).label("paid_supplier"),
        )
        .select_from(PurchasePaymentLink)
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .join(dir_pur_cogs_sq, PurchasePaymentLink.purchase_id == dir_pur_cogs_sq.c.purchase_id)
        .join(pur_total_cogs_sq, PurchasePaymentLink.purchase_id == pur_total_cogs_sq.c.purchase_id)
        .where(
            Payment.is_active == True,
            dir_pur_cogs_sq.c.client_id.in_(client_ids),
        )
        .group_by(dir_pur_cogs_sq.c.client_id)
    )
    for row in paid_supplier_rows.all():
        if row[0] in client_data:
            client_data[row[0]]["paid_to_supplier"] = row[1] or Decimal("0")

    result = []
    for cd in client_data.values():
        revenue = cd["revenue"]
        cogs = cd["cogs"]
        direct_exp = cd["direct_expenses"]
        client_exp = cd["client_expenses"]
        paid = cd["paid"]  # allocations for orders in period
        total_in = all_time_pay.get(cd["client_id"], Decimal("0"))
        total_alloc_any = all_time_alloc.get(cd["client_id"], Decimal("0"))
        unallocated = max(total_in - total_alloc_any, Decimal("0"))
        net_profit = revenue - cogs - direct_exp - client_exp
        # positive = overpayment/credit, negative = debt
        balance = paid - revenue
        result.append({
            "client_id": cd["client_id"],
            "client_name": cd["client_name"],
            "revenue": revenue,
            "paid_by_client": paid,
            "paid_to_supplier": cd["paid_to_supplier"],
            "unallocated_cny": unallocated,
            "cogs": cogs,
            "direct_expenses": direct_exp,
            "client_expenses": client_exp,
            "net_profit": net_profit,
            "balance": balance,
        })

    result.sort(key=lambda x: x["net_profit"], reverse=True)
    return result


async def get_by_direction(db: AsyncSession, date_from: date, date_to: date):
    """Report grouped by business type (direction)."""
    order_filter = [
        Order.order_date >= date_from,
        Order.order_date <= date_to,
        Order.status != OrderStatus.cancelled,
        Order.excluded_from_accounting == False,
    ]

    # Revenue per direction
    rev_rows = await db.execute(
        select(
            Order.business_type_id,
            BusinessType.name.label("bt_name"),
            BusinessType.name_cn.label("bt_name_cn"),
            func.coalesce(func.sum(Order.total_sale_cny), Decimal("0")).label("revenue"),
        )
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .where(*order_filter)
        .group_by(Order.business_type_id, BusinessType.name, BusinessType.name_cn)
    )
    direction_data: dict = {}
    for row in rev_rows.all():
        direction_data[row[0]] = {
            "direction_id": str(row[0]),
            "direction_name": row[1],
            "direction_name_cn": row[2] or "",
            "revenue": row[3] or Decimal("0"),
            "paid": Decimal("0"),
            "cogs": Decimal("0"),
            "direct_expenses": Decimal("0"),
            "client_expenses": Decimal("0"),
            "paid_to_supplier": Decimal("0"),
        }

    if not direction_data:
        return []

    direction_ids = list(direction_data.keys())

    # Paid = allocations for orders in period (no payment_date filter)
    alloc_rows = await db.execute(
        select(
            Order.business_type_id,
            func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")).label("alloc_cny"),
        )
        .join(PaymentAllocation, PaymentAllocation.order_id == Order.id)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(*order_filter, Order.business_type_id.in_(direction_ids), Payment.is_active == True)
        .group_by(Order.business_type_id)
    )
    for row in alloc_rows.all():
        if row[0] in direction_data:
            direction_data[row[0]]["paid"] = row[1] or Decimal("0")

    # COGS per direction
    orders_subq = select(Order.id, Order.business_type_id).where(*order_filter).subquery()
    cogs_rows = await db.execute(
        select(
            orders_subq.c.business_type_id,
            func.coalesce(func.sum(PurchaseItem.cost_amount), Decimal("0")).label("cogs"),
        )
        .join(PurchaseItem, and_(PurchaseItem.purchase_id == Purchase.id))
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(orders_subq, OrderItem.order_id == orders_subq.c.id)
        .where(Purchase.is_deleted == False)
        .group_by(orders_subq.c.business_type_id)
        .select_from(Purchase)
    )
    for row in cogs_rows.all():
        if row[0] in direction_data:
            direction_data[row[0]]["cogs"] = row[1] or Decimal("0")

    # Direct expenses per direction
    direct_exp_rows = await db.execute(
        select(
            orders_subq.c.business_type_id,
            func.coalesce(func.sum(Expense.amount_cny), Decimal("0")).label("direct_exp"),
        )
        .join(orders_subq, Expense.order_id == orders_subq.c.id)
        .where(
            Expense.link_type == "order",
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
            Expense.is_active == True,
            not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
        )
        .group_by(orders_subq.c.business_type_id)
    )
    for row in direct_exp_rows.all():
        if row[0] in direction_data:
            direction_data[row[0]]["direct_expenses"] = row[1] or Decimal("0")

    # paid_to_supplier per direction: proportional by COGS share
    bt_pur_cogs_sq = (
        select(
            Purchase.id.label("purchase_id"),
            orders_subq.c.business_type_id,
            func.coalesce(func.sum(PurchaseItem.cost_amount), Decimal("0")).label("client_cogs"),
        )
        .select_from(Purchase)
        .join(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(orders_subq, OrderItem.order_id == orders_subq.c.id)
        .where(Purchase.is_deleted == False)
        .group_by(Purchase.id, orders_subq.c.business_type_id)
        .subquery()
    )
    bt_total_cogs_sq = (
        select(
            bt_pur_cogs_sq.c.purchase_id,
            func.sum(bt_pur_cogs_sq.c.client_cogs).label("total_cogs"),
        )
        .group_by(bt_pur_cogs_sq.c.purchase_id)
        .subquery()
    )
    paid_supplier_dir_rows = await db.execute(
        select(
            bt_pur_cogs_sq.c.business_type_id,
            func.coalesce(
                func.sum(
                    PurchasePaymentLink.amount_cny *
                    bt_pur_cogs_sq.c.client_cogs /
                    func.nullif(bt_total_cogs_sq.c.total_cogs, 0)
                ),
                Decimal("0"),
            ).label("paid_supplier"),
        )
        .select_from(PurchasePaymentLink)
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .join(bt_pur_cogs_sq, PurchasePaymentLink.purchase_id == bt_pur_cogs_sq.c.purchase_id)
        .join(bt_total_cogs_sq, PurchasePaymentLink.purchase_id == bt_total_cogs_sq.c.purchase_id)
        .where(Payment.is_active == True)
        .group_by(bt_pur_cogs_sq.c.business_type_id)
    )
    for row in paid_supplier_dir_rows.all():
        if row[0] in direction_data:
            direction_data[row[0]]["paid_to_supplier"] = row[1] or Decimal("0")

    result = []
    for dd in direction_data.values():
        revenue = dd["revenue"]
        paid = dd["paid"]
        cogs = dd["cogs"]
        direct_exp = dd["direct_expenses"]
        net_profit = revenue - cogs - direct_exp
        balance = paid - revenue
        result.append({
            "direction_id": dd["direction_id"],
            "direction_name": dd["direction_name"],
            "direction_name_cn": dd["direction_name_cn"],
            "revenue": revenue,
            "paid_by_client": paid,
            "paid_to_supplier": dd["paid_to_supplier"],
            "cogs": cogs,
            "direct_expenses": direct_exp,
            "net_profit": net_profit,
            "balance": balance,
        })

    result.sort(key=lambda x: x["net_profit"], reverse=True)
    return result


async def get_by_supplier(db: AsyncSession, date_from: date, date_to: date):
    from datetime import datetime
    today = date.today()

    purchase_filter = [
        Purchase.purchase_date >= date_from,
        Purchase.purchase_date <= date_to,
        Purchase.is_deleted == False,
        Purchase.excluded_from_accounting == False,
    ]

    purch_rows = await db.execute(
        select(
            Purchase.supplier_id,
            Counterparty.name.label("supplier_name"),
            func.coalesce(func.sum(Purchase.total_amount_cny), Decimal("0")).label("total_purchased_cny"),
            func.count(Purchase.id).label("count"),
        )
        .join(Counterparty, Purchase.supplier_id == Counterparty.id)
        .where(*purchase_filter)
        .group_by(Purchase.supplier_id, Counterparty.name)
    )
    supplier_data = {
        row[0]: {
            "supplier_id": row[0],
            "supplier_name": row[1],
            "total_purchased_cny": row[2] or Decimal("0"),
            "count": row[3],
            "paid_cny": Decimal("0"),
            "has_overdue": False,
        }
        for row in purch_rows.all()
    }

    if not supplier_data:
        return []

    supplier_ids = list(supplier_data.keys())

    # Paid amounts per supplier
    paid_rows = await db.execute(
        select(
            Purchase.supplier_id,
            func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")).label("paid"),
        )
        .join(PurchasePaymentLink, Purchase.id == PurchasePaymentLink.purchase_id)
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .where(
            Purchase.supplier_id.in_(supplier_ids),
            Purchase.purchase_date >= date_from,
            Purchase.purchase_date <= date_to,
            Purchase.is_deleted == False,
            Payment.is_active == True,
        )
        .group_by(Purchase.supplier_id)
    )
    for row in paid_rows.all():
        if row[0] in supplier_data:
            supplier_data[row[0]]["paid_cny"] = row[1] or Decimal("0")

    # Has overdue: any purchase > 30 days old with remaining > 0
    cutoff = today - timedelta(days=30)
    overdue_rows = await db.execute(
        select(Purchase.supplier_id).distinct()
        .where(
            Purchase.supplier_id.in_(supplier_ids),
            Purchase.purchase_date >= date_from,
            Purchase.purchase_date <= date_to,
            Purchase.is_deleted == False,
            Purchase.purchase_date <= cutoff,
            Purchase.payment_status != "paid",
        )
    )
    overdue_ids = {row[0] for row in overdue_rows.all()}
    for sid in overdue_ids:
        if sid in supplier_data:
            supplier_data[sid]["has_overdue"] = True

    result = []
    for sd in supplier_data.values():
        total = sd["total_purchased_cny"]
        paid = sd["paid_cny"]
        result.append({
            "supplier_id": sd["supplier_id"],
            "supplier_name": sd["supplier_name"],
            "total_purchased_cny": total,
            "paid_cny": paid,
            "debt_cny": max(total - paid, Decimal("0")),
            "count": sd["count"],
            "has_overdue": sd["has_overdue"],
        })

    result.sort(key=lambda x: x["total_purchased_cny"], reverse=True)
    return result


async def get_client_detail(
    db: AsyncSession,
    client_id: uuid.UUID,
    date_from: date,
    date_to: date,
):
    order_filter = [
        Order.client_id == client_id,
        Order.order_date >= date_from,
        Order.order_date <= date_to,
        Order.status != OrderStatus.cancelled,
        Order.excluded_from_accounting == False,
    ]

    # Client name
    client_row = await db.execute(select(Counterparty.name).where(Counterparty.id == client_id))
    client_name = client_row.scalar_one_or_none() or ""

    # Paid per order
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

    order_rows = await db.execute(
        select(
            Order.id,
            Order.order_number,
            Order.order_date,
            Order.total_sale_cny,
            Order.payment_status,
            func.coalesce(paid_sq.c.paid_cny, Decimal("0")).label("paid_cny"),
        )
        .outerjoin(paid_sq, Order.id == paid_sq.c.order_id)
        .where(*order_filter)
        .order_by(Order.order_date.desc())
    )
    orders_raw = order_rows.all()

    if not orders_raw:
        # Still need to check client expenses (representative) even without orders
        client_exp_row = await db.execute(
            select(func.coalesce(func.sum(Expense.amount_cny), Decimal("0")))
            .where(
                Expense.link_type == "client",
                Expense.client_id == client_id,
                Expense.expense_date >= date_from,
                Expense.expense_date <= date_to,
                Expense.is_active == True,
                not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
            )
        )
        client_expenses = client_exp_row.scalar_one() or Decimal("0")
        return {
            "client_id": str(client_id),
            "client_name": client_name,
            "orders": [],
            "client_expenses": client_expenses,
            "total_revenue": Decimal("0"),
            "total_cogs": Decimal("0"),
            "total_direct_expenses": Decimal("0"),
            "total_paid": Decimal("0"),
            "total_profit": -client_expenses,
            "balance": Decimal("0"),
        }

    order_ids = [r[0] for r in orders_raw]
    order_map = {
        r[0]: {
            "order_id": r[0],
            "order_number": r[1],
            "order_date": r[2],
            "total_sale_cny": r[3] or Decimal("0"),
            "payment_status": r[4],
            "paid_cny": r[5] or Decimal("0"),
            "cogs": Decimal("0"),
            "direct_expenses": Decimal("0"),
        }
        for r in orders_raw
    }

    # COGS per order
    cogs_rows = await db.execute(
        select(
            OrderItem.order_id,
            func.coalesce(func.sum(PurchaseItem.cost_amount), Decimal("0")).label("cogs"),
        )
        .join(PurchaseItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
        .where(
            OrderItem.order_id.in_(order_ids),
            Purchase.is_deleted == False,
        )
        .group_by(OrderItem.order_id)
    )
    for row in cogs_rows.all():
        if row[0] in order_map:
            order_map[row[0]]["cogs"] = row[1] or Decimal("0")

    # Direct expenses per order
    exp_filter = [
        Expense.link_type == "order",
        Expense.order_id.in_(order_ids),
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
        Expense.is_active == True,
        not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
    ]
    direct_exp_rows = await db.execute(
        select(
            Expense.order_id,
            func.coalesce(func.sum(Expense.amount_cny), Decimal("0")).label("direct_exp"),
        )
        .where(*exp_filter)
        .group_by(Expense.order_id)
    )
    for row in direct_exp_rows.all():
        if row[0] in order_map:
            order_map[row[0]]["direct_expenses"] = row[1] or Decimal("0")

    # Client expenses (представительские)
    client_exp_row = await db.execute(
        select(func.coalesce(func.sum(Expense.amount_cny), Decimal("0")))
        .where(
            Expense.link_type == "client",
            Expense.client_id == client_id,
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
            Expense.is_active == True,
            not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
        )
    )
    client_expenses = client_exp_row.scalar_one() or Decimal("0")

    # Build order list
    order_list = []
    total_revenue = Decimal("0")
    total_cogs = Decimal("0")
    total_direct_exp = Decimal("0")
    total_paid = Decimal("0")
    for od in order_map.values():
        revenue = od["total_sale_cny"]
        cogs = od["cogs"]
        direct_exp = od["direct_expenses"]
        paid = od["paid_cny"]
        profit = revenue - cogs - direct_exp
        remaining = max(revenue - paid, Decimal("0"))
        total_revenue += revenue
        total_cogs += cogs
        total_direct_exp += direct_exp
        total_paid += paid
        order_list.append({
            "order_id": str(od["order_id"]),
            "order_number": od["order_number"],
            "order_date": od["order_date"],
            "total_sale_cny": revenue,
            "cogs": cogs,
            "direct_expenses": direct_exp,
            "paid_cny": paid,
            "payment_status": od["payment_status"],
            "remaining": remaining,
            "profit": profit,
        })

    # All-time incoming payments (no date filter) for unallocated balance calculation
    all_time_incoming_row = await db.execute(
        select(func.coalesce(func.sum(Payment.amount_cny), Decimal("0")))
        .where(
            Payment.counterparty_id == client_id,
            Payment.is_active == True,
            Payment.direction == "in",
        )
    )
    all_time_incoming = all_time_incoming_row.scalar_one() or Decimal("0")

    # All-time allocations to any order for this client (from active payments)
    all_time_alloc_row = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .join(Order, PaymentAllocation.order_id == Order.id)
        .where(Order.client_id == client_id, Payment.is_active == True)
    )
    all_time_alloc = all_time_alloc_row.scalar_one() or Decimal("0")

    unallocated_cny = max(all_time_incoming - all_time_alloc, Decimal("0"))

    total_profit = (total_revenue - total_cogs - total_direct_exp) - client_expenses
    # balance: positive = overpayment, negative = debt (based on allocations, not payment dates)
    balance = total_paid - total_revenue

    return {
        "client_id": str(client_id),
        "client_name": client_name,
        "orders": order_list,
        "client_expenses": client_expenses,
        "total_revenue": total_revenue,
        "total_cogs": total_cogs,
        "total_direct_expenses": total_direct_exp,
        "total_paid": total_paid,
        "unallocated_cny": unallocated_cny,
        "total_profit": total_profit,
        "balance": balance,
    }


async def get_supplier_detail(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    date_from: date,
    date_to: date,
):
    purchase_filter = [
        Purchase.supplier_id == supplier_id,
        Purchase.purchase_date >= date_from,
        Purchase.purchase_date <= date_to,
        Purchase.is_deleted == False,
        Purchase.excluded_from_accounting == False,
    ]

    # Supplier name
    supp_row = await db.execute(select(Counterparty.name).where(Counterparty.id == supplier_id))
    supplier_name = supp_row.scalar_one_or_none() or ""

    # Paid per purchase
    paid_sq = (
        select(
            PurchasePaymentLink.purchase_id,
            func.coalesce(func.sum(PurchasePaymentLink.amount_cny), Decimal("0")).label("paid_cny"),
        )
        .join(Payment, PurchasePaymentLink.payment_id == Payment.id)
        .where(Payment.is_active == True)
        .group_by(PurchasePaymentLink.purchase_id)
        .subquery()
    )

    purch_rows = await db.execute(
        select(
            Purchase.id,
            Purchase.purchase_number,
            Purchase.purchase_date,
            Purchase.total_amount_cny,
            Purchase.payment_status,
            Purchase.order_id,
            func.coalesce(paid_sq.c.paid_cny, Decimal("0")).label("paid_cny"),
        )
        .outerjoin(paid_sq, Purchase.id == paid_sq.c.purchase_id)
        .where(*purchase_filter)
        .order_by(Purchase.purchase_date.desc())
    )
    purchases_raw = purch_rows.all()

    if not purchases_raw:
        return {
            "supplier_id": str(supplier_id),
            "supplier_name": supplier_name,
            "purchases": [],
            "total_purchased_cny": Decimal("0"),
            "total_paid_cny": Decimal("0"),
            "balance": Decimal("0"),
        }

    # Get order numbers for linked orders
    order_ids = [r[5] for r in purchases_raw if r[5] is not None]
    order_number_map: dict = {}
    if order_ids:
        ord_rows = await db.execute(
            select(Order.id, Order.order_number, Order.total_sale_cny)
            .where(Order.id.in_(order_ids))
        )
        for row in ord_rows.all():
            order_number_map[row[0]] = {"order_number": row[1], "total_sale_cny": row[2]}

    purchase_list = []
    total_purchased = Decimal("0")
    total_paid = Decimal("0")
    for r in purchases_raw:
        purchase_id, purchase_number, purchase_date, total_cny, pay_status, order_id, paid_cny = r
        total_cny = total_cny or Decimal("0")
        paid_cny = paid_cny or Decimal("0")
        remaining = max(total_cny - paid_cny, Decimal("0"))
        total_purchased += total_cny
        total_paid += paid_cny
        ord_info = order_number_map.get(order_id) if order_id else None
        purchase_list.append({
            "purchase_id": str(purchase_id),
            "purchase_number": purchase_number,
            "purchase_date": purchase_date,
            "order_number": ord_info["order_number"] if ord_info else None,
            "order_sale_cny": ord_info["total_sale_cny"] if ord_info else None,
            "total_amount_cny": total_cny,
            "paid_cny": paid_cny,
            "payment_status": pay_status,
            "remaining": remaining,
        })

    balance = total_paid - total_purchased

    return {
        "supplier_id": str(supplier_id),
        "supplier_name": supplier_name,
        "purchases": purchase_list,
        "total_purchased_cny": total_purchased,
        "total_paid_cny": total_paid,
        "balance": balance,
    }


async def get_expenses_structure(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    link_type: Optional[str] = None,
):
    exp_filter = [
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
        Expense.is_active == True,
        not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
    ]
    if link_type:
        exp_filter.append(Expense.link_type == link_type)

    total_row = await db.execute(
        select(func.coalesce(func.sum(Expense.amount_cny), Decimal("0")))
        .where(*exp_filter)
    )
    total = total_row.scalar_one() or Decimal("0")

    cat_rows = await db.execute(
        select(
            ExpenseCategory.name,
            ExpenseCategory.name_cn,
            func.coalesce(func.sum(Expense.amount_cny), Decimal("0")).label("amount_cny"),
            func.count(Expense.id).label("count"),
        )
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*exp_filter)
        .group_by(ExpenseCategory.name, ExpenseCategory.name_cn)
        .order_by(func.sum(Expense.amount_cny).desc())
    )

    result = []
    for row in cat_rows.all():
        amount = row[2] or Decimal("0")
        pct = float((amount / total * 100).quantize(Decimal("0.1"))) if total > 0 else 0.0
        result.append({
            "category_name": row[0],
            "category_name_cn": row[1],
            "amount_cny": amount,
            "count": row[3],
            "percent": pct,
        })

    return {"total": total, "items": result}


async def get_tonnage(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    warehouse_id: Optional[uuid.UUID] = None,
    client_id: Optional[uuid.UUID] = None,
):
    logistics_filter = [
        Order.order_date >= date_from,
        Order.order_date <= date_to,
        Order.status != OrderStatus.cancelled,
        BusinessType.code == "logistics",
    ]
    if warehouse_id:
        logistics_filter.append(Order.warehouse_id == warehouse_id)
    if client_id:
        logistics_filter.append(Order.client_id == client_id)

    base_stmt = (
        select(Order.id)
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .where(*logistics_filter)
        .subquery()
    )

    # Total summary
    summary_row = await db.execute(
        select(
            func.coalesce(func.sum(OrderItem.weight_kg), Decimal("0")).label("total_weight_kg"),
            func.coalesce(func.sum(OrderItem.volume_m3), Decimal("0")).label("total_volume_m3"),
            func.count(func.distinct(OrderItem.order_id)).label("order_count"),
        )
        .join(base_stmt, OrderItem.order_id == base_stmt.c.id)
    )
    summary = summary_row.first()
    total_weight_kg = summary[0] or Decimal("0")
    total_volume_m3 = summary[1] or Decimal("0")
    order_count = summary[2] or 0

    # By warehouse
    by_warehouse_rows = await db.execute(
        select(
            Warehouse.id,
            Warehouse.name,
            Warehouse.name_cn,
            func.count(func.distinct(Order.id)).label("order_count"),
            func.coalesce(func.sum(OrderItem.weight_kg), Decimal("0")).label("total_weight_kg"),
            func.coalesce(func.sum(OrderItem.volume_m3), Decimal("0")).label("total_volume_m3"),
        )
        .join(Order, Order.warehouse_id == Warehouse.id)
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(*logistics_filter)
        .group_by(Warehouse.id, Warehouse.name, Warehouse.name_cn)
        .order_by(func.sum(OrderItem.weight_kg).desc())
    )
    by_warehouse = [
        {
            "warehouse_id": row[0],
            "warehouse_name": row[1],
            "warehouse_name_cn": row[2],
            "order_count": row[3],
            "total_weight_kg": row[4] or Decimal("0"),
            "total_volume_m3": row[5] or Decimal("0"),
        }
        for row in by_warehouse_rows.all()
    ]

    # By month
    by_month_rows = await db.execute(
        select(
            func.extract("year", Order.order_date).label("year"),
            func.extract("month", Order.order_date).label("month"),
            func.coalesce(func.sum(OrderItem.weight_kg), Decimal("0")).label("total_weight_kg"),
            func.coalesce(func.sum(OrderItem.volume_m3), Decimal("0")).label("total_volume_m3"),
        )
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(*logistics_filter)
        .group_by(
            func.extract("year", Order.order_date),
            func.extract("month", Order.order_date),
        )
        .order_by(
            func.extract("year", Order.order_date),
            func.extract("month", Order.order_date),
        )
    )
    by_month = [
        {
            "year": int(row[0]),
            "month": int(row[1]),
            "total_weight_kg": row[2] or Decimal("0"),
            "total_volume_m3": row[3] or Decimal("0"),
        }
        for row in by_month_rows.all()
    ]

    return {
        "total_weight_kg": total_weight_kg,
        "total_volume_m3": total_volume_m3,
        "order_count": order_count,
        "by_warehouse": by_warehouse,
        "by_month": by_month,
    }


async def get_tonnage_detail(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    warehouse_id: Optional[uuid.UUID] = None,
    client_id: Optional[uuid.UUID] = None,
):
    """Построчная детализация тоннажа: заказ, вес, объём, склад, автор заказа.

    Только логистика — как и в сводном отчёте. Склад присоединяем через
    LEFT JOIN, чтобы заказы без склада не пропадали из выгрузки.
    """
    filters = [
        Order.order_date >= date_from,
        Order.order_date <= date_to,
        Order.status != OrderStatus.cancelled,
        BusinessType.code == "logistics",
    ]
    if warehouse_id:
        filters.append(Order.warehouse_id == warehouse_id)
    if client_id:
        filters.append(Order.client_id == client_id)

    rows = (await db.execute(
        select(
            Order.order_number,
            Order.order_date,
            Counterparty.name.label("client_name"),
            Warehouse.name.label("warehouse_name"),
            Warehouse.name_cn.label("warehouse_name_cn"),
            func.coalesce(func.sum(OrderItem.weight_kg), Decimal("0")).label("total_weight_kg"),
            func.coalesce(func.sum(OrderItem.volume_m3), Decimal("0")).label("total_volume_m3"),
            User.full_name.label("created_by_name"),
        )
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .outerjoin(Warehouse, Order.warehouse_id == Warehouse.id)
        .outerjoin(Counterparty, Order.client_id == Counterparty.id)
        .outerjoin(User, Order.created_by == User.id)
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
        .where(*filters)
        .group_by(
            Order.id, Order.order_number, Order.order_date,
            Counterparty.name, Warehouse.name, Warehouse.name_cn, User.full_name,
        )
        .order_by(Order.order_date, Order.order_number)
    )).all()

    return [
        {
            "order_number": r.order_number,
            "order_date": r.order_date,
            "client_name": r.client_name,
            "warehouse_name": r.warehouse_name,
            "warehouse_name_cn": r.warehouse_name_cn,
            "total_weight_kg": r.total_weight_kg or Decimal("0"),
            "total_volume_m3": r.total_volume_m3 or Decimal("0"),
            "created_by_name": r.created_by_name,
        }
        for r in rows
    ]
