import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import String, Text, Enum, Numeric, Date, ForeignKey, DateTime, func, Boolean
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
    USD = "USD"


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
    # Logistics-specific fields
    recipient: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # Integration sync fields
    external_shipment_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_shipment_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_tracking_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    excluded_from_accounting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Источник заказа + входящая интеграция NET (приложение PARCEL → ERP)
    source: Mapped[str] = mapped_column(String(16), default="erp", nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cargo_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cargo_status_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cargo_status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Обмен валют (business_type=currency_exchange)
    exchange_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    exchange_buy_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    exchange_sell_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    exchange_buy_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    exchange_sell_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
