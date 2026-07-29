"""Сравнение предложений поставщиков по логистике (замена Excel-файла).

QuoteRequest — строка заявки (товар/вес/объём/направление). Может быть
создана из логистического заказа или вручную.
SupplierQuote — предложение конкретного поставщика по этой заявке
(цена за кг/куб, срок, страховка). Выбранное предложение фиксируется
в QuoteRequest.selected_quote_id.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from decimal import Decimal
from sqlalchemy import String, Text, Enum, ForeignKey, DateTime, Numeric, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class PriceUnitEnum(str, PyEnum):
    per_kg = "per_kg"      # цена за кг
    per_cbm = "per_cbm"    # цена за м³


class QuoteRequest(Base):
    __tablename__ = "quote_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Привязка к логистическому заказу (гибрид: может быть NULL для ручной строки)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)

    order_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    product_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cargo_value: Mapped[str | None] = mapped_column(String(120), nullable=True)   # 货值: "5000", "1%", "300$"
    box: Mapped[str | None] = mapped_column(String(120), nullable=True)           # 纸箱18 / 木托1 / 合包缠绕
    dimensions: Mapped[str | None] = mapped_column(Text, nullable=True)           # "51*46*35" (может быть многострочным)
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)   # 莫斯科
    dispatch_place: Mapped[str | None] = mapped_column(String(255), nullable=True) # 佛山
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Выбор поставщика
    selected_quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    selected_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SupplierQuote(Base):
    __tablename__ = "supplier_quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quote_requests.id", ondelete="CASCADE"), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price_unit: Mapped[PriceUnitEnum] = mapped_column(
        Enum(PriceUnitEnum, name="priceunitenum"), default=PriceUnitEnum.per_kg, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    delivery_days: Mapped[str | None] = mapped_column(String(120), nullable=True)   # "18-22天"
    insurance_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)                   # "没晚到赔付" и т.п.

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
