"""Авто-создание и синхронизация планов платежей по заказам/закупкам."""
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_plan import PaymentPlan, PlanStatus
from app.models.order import Order
from app.models.purchase import Purchase


async def create_plan_for_order(db: AsyncSession, order: Order, created_by: uuid.UUID) -> None:
    """Ожидаемый входящий платёж от клиента по заказу."""
    exists = (await db.execute(
        select(PaymentPlan.id).where(PaymentPlan.order_id == order.id, PaymentPlan.is_active == True)
    )).scalar_one_or_none()
    if exists:
        return
    plan = PaymentPlan(
        id=uuid.uuid4(),
        direction="in",
        order_id=order.id,
        counterparty_id=order.client_id,
        currency=str(getattr(order.client_currency, "value", order.client_currency) or "CNY"),
        expected_amount=order.total_sale_cny or Decimal("0"),
        expected_cny=order.total_sale_cny or Decimal("0"),
        status=PlanStatus.pending,
        created_by=created_by,
    )
    db.add(plan)


async def create_plan_for_purchase(db: AsyncSession, purchase: Purchase, created_by: uuid.UUID) -> None:
    """Ожидаемый исходящий платёж поставщику по закупке."""
    exists = (await db.execute(
        select(PaymentPlan.id).where(PaymentPlan.purchase_id == purchase.id, PaymentPlan.is_active == True)
    )).scalar_one_or_none()
    if exists:
        return
    plan = PaymentPlan(
        id=uuid.uuid4(),
        direction="out",
        purchase_id=purchase.id,
        counterparty_id=purchase.supplier_id,
        currency=str(getattr(purchase.currency, "value", purchase.currency) or "CNY"),
        expected_amount=purchase.total_amount or Decimal("0"),
        expected_cny=purchase.total_amount_cny or Decimal("0"),
        status=PlanStatus.pending,
        created_by=created_by,
    )
    db.add(plan)


async def sync_plan_for_order(db: AsyncSession, order: Order) -> None:
    """Обновить ожидаемую сумму плана при изменении суммы заказа."""
    plan = (await db.execute(
        select(PaymentPlan).where(PaymentPlan.order_id == order.id, PaymentPlan.is_active == True)
    )).scalar_one_or_none()
    if not plan:
        return
    plan.expected_amount = order.total_sale_cny or Decimal("0")
    plan.expected_cny = order.total_sale_cny or Decimal("0")


async def sync_plan_for_purchase(db: AsyncSession, purchase: Purchase) -> None:
    plan = (await db.execute(
        select(PaymentPlan).where(PaymentPlan.purchase_id == purchase.id, PaymentPlan.is_active == True)
    )).scalar_one_or_none()
    if not plan:
        return
    plan.expected_amount = purchase.total_amount or Decimal("0")
    plan.expected_cny = purchase.total_amount_cny or Decimal("0")
