import uuid
from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import String, Text, Boolean, Enum, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import TimestampMixin


class LinkTypeEnum(str, PyEnum):
    order = "order"
    client = "client"
    none = "none"


class ReimburseStatusEnum(str, PyEnum):
    pending = "pending"
    approved = "approved"
    paid = "paid"
    rejected = "rejected"


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("expense_categories.id"), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    rate_to_cny: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    link_type: Mapped[LinkTypeEnum] = mapped_column(Enum(LinkTypeEnum, name="linktypeenum"), default=LinkTypeEnum.none, nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=True)
    is_reimbursement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reimburse_to_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reimburse_status: Mapped[ReimburseStatusEnum | None] = mapped_column(Enum(ReimburseStatusEnum, name="reimburseestatusnum"), nullable=True)
    reimburse_paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
