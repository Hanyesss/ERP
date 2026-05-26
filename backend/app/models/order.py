import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import String, Text, Enum, Numeric, Date, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import TimestampMixin


class OrderStatus(str, PyEnum):
    new = "new"
    active = "active"
    closed = "closed"
    cancelled = "cancelled"


class PaymentStatus(str, PyEnum):
    unpaid = "unpaid"
    partial = "partial"
    paid = "paid"


class OrderCurrencyEnum(str, PyEnum):
    CNY = "CNY"
    RUB = "RUB"
    USDT = "USDT"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=False)
    business_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("business_types.id"), nullable=False)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="orderstatus"), default=OrderStatus.new, nullable=False)
    client_currency: Mapped[OrderCurrencyEnum] = mapped_column(Enum(OrderCurrencyEnum, name="ordercurrencyenum"), default=OrderCurrencyEnum.CNY, nullable=False)
    total_sale_cny: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    total_cost_cny: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, name="paymentstatus"), default=PaymentStatus.unpaid, nullable=False)
    supplier_payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, name="paymentstatus"), default=PaymentStatus.unpaid, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
