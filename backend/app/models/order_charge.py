import uuid
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class OrderCharge(Base):
    __tablename__ = "order_charges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    charge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    rate_to_cny: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
