import uuid
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
from app.models.base import TimestampMixin


class CounterpartyType(str, PyEnum):
    client = "client"
    supplier = "supplier"
    both = "both"


class CurrencyEnum(str, PyEnum):
    CNY = "CNY"
    RUB = "RUB"
    USDT = "USDT"


class Counterparty(Base, TimestampMixin):
    __tablename__ = "counterparties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_cn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[CounterpartyType] = mapped_column(Enum(CounterpartyType, name="counterpartytype"), nullable=False)
    default_currency: Mapped[CurrencyEnum] = mapped_column(Enum(CurrencyEnum, name="currencyenum"), default=CurrencyEnum.CNY, nullable=False)
    contact_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
