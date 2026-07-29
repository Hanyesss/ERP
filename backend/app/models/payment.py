import uuid
from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import String, Text, Enum, Numeric, Date, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import TimestampMixin


class PaymentDirection(str, PyEnum):
    incoming = "in"
    outgoing = "out"


class PaymentCurrencyEnum(str, PyEnum):
    CNY = "CNY"
    RUB = "RUB"
    USDT = "USDT"
    USD = "USD"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    direction: Mapped[PaymentDirection] = mapped_column(
        Enum(PaymentDirection, name="paymentdirection", values_callable=lambda e: [x.value for x in e]),
        nullable=False
    )
    counterparty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[PaymentCurrencyEnum] = mapped_column(Enum(PaymentCurrencyEnum, name="paymentcurrencyenum"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    rate_to_cny: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    network_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_urls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of paths
    pending_change: Mapped[str | None] = mapped_column(Text, nullable=True)
    cash_register_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_registers.id"), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    external_tx_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Привязка к плану платежа (взнос): депозит/финальный. NULL — обычный платёж.
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_plans.id"), nullable=True)
    installment_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "deposit" / "balance"
