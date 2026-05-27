import uuid
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    preferred_supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_cn: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Trade / services fields (nullable for logistics)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sale_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sale_rate_to_cny: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)

    # Logistics-specific fields
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    density_kg_m3: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    price_per_kg_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cargo_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    cargo_value_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    places_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
