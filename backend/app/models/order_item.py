import uuid
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_cn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    sale_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    sale_rate_to_cny: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    cost_rate_to_cny: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
