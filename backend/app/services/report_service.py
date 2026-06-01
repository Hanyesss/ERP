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
    # Build base order filter
    order_filter = [
        Order.order_date >= date_from,
        Order.order_date <= date_to,
        Order.status != OrderStatus.cancelled,
    ]
    if business_type_id:
        order_filter.append(Order.business_type_id == business_type_id)
    if warehouse_id:
        order_filter.append(Order.warehouse_id == warehouse_id)

    # Revenue total
    rev_row = await db.execute(
        select(func.coalesce(func.sum(Order.total_sale_cny), Decimal("0")))
        .where(*order_filter)
    )
    revenue = rev_row.scalar_one() or Decimal("0")

    # Revenue by business_type_code
    rev_by_type_rows = await db.execute(
        select(BusinessType.code, func.coalesce(func.sum(Order.total_sale_cny), Decimal("0")).label("rev"))
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .where(*order_filter)
        .group_by(BusinessType.code)
    )
    revenue_by_type = {row[0]: row[1] or Decimal("0") for row in rev_by_type_rows.all()}

    # Orders subquery for the period
    orders_subq = (
        select(Order.id)
        .where(*order_filter)
        .subquery()
    )

    # COGS: purchase_items linked to purchase linked to orders in period
    cogs_row = await db.execute(
        select(func.coalesce(func.sum(PurchaseItem.cost_amount), Decimal("0")))
        .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .where(
            OrderItem.order_id.in_(orders_subq),
            Purchase.is_deleted == False,
        )
    )
    cogs = cogs_row.scalar_one() or Decimal("0")

    # Expenses in period
    exp_filter_base = [
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
        Expense.is_active == True,
        not_(and_(Expense.is_reimbursement == True, Expense.reimburse_status == "rejected")),
    ]
    # When filtering by business_type, exclude company/employee expenses (link_type="none")
    # Services business type should only count direct order-linked expenses
    exp_filter_for_type = list(exp_filter_base)
    if business_type_id:
        exp_filter_for_type.append(Expense.link_type != "none")

    exp_rows = await db.execute(
        select(
            Expense.link_type,
            func.coalesce(func.sum(Expense.amount_cny), Decimal("0")).label("total")
        )
        .where(*exp_filter_for_type)
        .group_by(Expense.link_type)
    )
    expenses_by_type = {row[0]: row[1] or Decimal("0") for row in exp_rows.all()}

    direct_expenses = expenses_by_type.get("order", Decimal("0"))
    client_expenses = expenses_by_type.get("client", Decimal("0"))
    general_expenses = expenses_by_type.get("none", Decimal("0"))

    # Expenses by category for pie chart
    cat_rows = await db.execute(
        select(
            ExpenseCategory.name,
            ExpenseCategory.name_cn,
            func.coalesce(func.sum(Expense.amount_cny), Decimal("0")).label("amount_cny"),
        )
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*exp_filter_for_type)
        .group_by(ExpenseCategory.name, ExpenseCategory.name_cn)
        .order_by(func.sum(Expense.amount_cny).desc())
    )
    expenses_by_category = [
        {"category_name": r[0], "category_name_cn": r[1], "amount_cny": r[2] or Decimal("0")}
        for r in cat_rows.all()
    ]

    gross_profit = revenue - cogs - direct_expenses
    net_profit = gross_profit - client_expenses - general_expenses

    return {
        "revenue": revenue,
        "revenue_by_type": revenue_by_type,
        "cogs": cogs,
        "direct_expenses": direct_expenses,
        "client_expenses": client_expenses,
        "general_expenses": general_expenses,
        "gross_profit": gross_profit,
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
        "pct_gross_profit": pct_change(current["gross_profit"], prev["gross_profit"]),
        "pct_net_profit": pct_change(current["net_profit"], prev["net_profit"]),
    }


async def get_by_client(db: AsyncSession, date_from: date, date_to: date):
    order_filter = [
        Order.order_date >= date_from,
        Order.order_date <= date_to,
        Order.status != OrderStatus.cancelled,
    ]

    # Revenue + paid per client
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
            Order.client_id,
            Counterparty.name.label("client_name"),
            func.coalesce(func.sum(Order.total_sale_cny), Decimal("0")).label("revenue"),
            func.coalesce(func.sum(func.coalesce(paid_sq.c.paid_cny, Decimal("0"))), Decimal("0")).label("paid"),
        )
        .join(Counterparty, Order.client_id == Counterparty.id)
        .outerjoin(paid_sq, Order.id == paid_sq.c.order_id)
        .where(*order_filter)
        .group_by(Order.client_id, Counterparty.name)
    )
    client_data = {
        row[0]: {
            "client_id": row[0],
            "client_name": row[1],
            "revenue": row[2] or Decimal("0"),
            "paid": row[3] or Decimal("0"),
            "cogs": Decimal("0"),
            "direct_expenses": Decimal("0"),
            "client_expenses": Decimal("0"),
        }
        for row in order_rows.all()
    }

    if not client_data:
        return []

    client_ids = list(client_data.keys())

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

    result = []
    for cd in client_data.values():
        revenue = cd["revenue"]
        cogs = cd["cogs"]
        direct_exp = cd["direct_expenses"]
        client_exp = cd["client_expenses"]
        paid = cd["paid"]
        net_profit = revenue - cogs - direct_exp - client_exp
        debt = max(revenue - paid, Decimal("0"))
        result.append({
            "client_id": cd["client_id"],
            "client_name": cd["client_name"],
            "revenue": revenue,
            "paid": paid,
            "cogs": cogs,
            "direct_expenses": direct_exp,
            "client_expenses": client_exp,
            "net_profit": net_profit,
            "debt": debt,
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
