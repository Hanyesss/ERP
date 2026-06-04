import uuid
from decimal import Decimal
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Text, Numeric, Enum, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class BoxStatus(str, PyEnum):
    on_warehouse = "on_warehouse"
    shipped = "shipped"


class WarehouseBox(Base):
    __tablename__ = "warehouse_boxes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    box_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    counterparty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    density: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, server_default="0")
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Основное наименование (совместимость)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[BoxStatus] = mapped_column(
        Enum(BoxStatus, name="boxstatus"), nullable=False, server_default="on_warehouse", index=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items: Mapped[list["BoxItem"]] = relationship(
        "BoxItem", back_populates="box",
        cascade="all, delete-orphan",
        order_by="BoxItem.sort_order",
    )


class BoxItem(Base):
    """Позиция товара внутри коробки (несколько позиций на одну коробку)."""
    __tablename__ = "box_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    box_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouse_boxes.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    box: Mapped["WarehouseBox"] = relationship("WarehouseBox", back_populates="items")


class PackingList(Base):
    __tablename__ = "packing_lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    box_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    total_weight: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    total_volume: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    total_boxes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
