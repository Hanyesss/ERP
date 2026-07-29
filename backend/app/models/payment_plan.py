"""План платежа (ожидаемая оплата по заказу/закупке).

Создаётся автоматически при создании заказа (входящий, от клиента) или
закупки (исходящий, поставщику). Пока не оплачен — статус pending
(«ждёт оплаты»), кассу не трогает. Фактические оплаты — это обычные
Payment-записи (взносы: депозит/финальный), привязанные к плану через
Payment.plan_id. Статус плана считается из суммы взносов.
"""
import uuid
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import Enum, Numeric, ForeignKey, Boolean, Text, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import TimestampMixin


class PlanStatus(str, PyEnum):
    pending = "pending"     # ждёт оплаты (взносов нет)
    deposit = "deposit"     # оплачен депозит (частично)
    paid = "paid"           # оплачен полностью


class PaymentPlan(Base, TimestampMixin):
    __tablename__ = "payment_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    direction: Mapped[str] = mapped_column(String(3), nullable=False)  # "in" / "out"
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchases.id"), nullable=True)
    counterparty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=False)

    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    expected_cny: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))

    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, name="planstatus"), default=PlanStatus.pending, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
