import uuid
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import String, Numeric, ForeignKey, Date, Boolean, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import TimestampMixin


class PurchaseCurrency(str, PyEnum):
    CNY = "CNY"
    RUB = "RUB"
    USDT = "USDT"
    USD = "USD"


class PurchasePaymentStatus(str, PyEnum):
    unpaid = "unpaid"
    partial = "partial"
    paid = "paid"


class Purchase(Base, TimestampMixin):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=False)
    purchase_date: Mapped[object] = mapped_column(Date, nullable=False)
    currency: Mapped[PurchaseCurrency] = mapped_column(Enum(PurchaseCurrency, name="purchasecurrencyenum"), default=PurchaseCurrency.CNY, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    rate_to_cny: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("1"), nullable=False)
    total_amount_cny: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    payment_status: Mapped[PurchasePaymentStatus] = mapped_column(Enum(PurchasePaymentStatus, name="purchasepaymentstatus"), default=PurchasePaymentStatus.unpaid, nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    items: Mapped[list["PurchaseItem"]] = relationship("PurchaseItem", back_populates="purchase", lazy="selectin")
