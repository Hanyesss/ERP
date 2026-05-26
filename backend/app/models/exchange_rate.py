import uuid
from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import String, Enum, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import TimestampMixin


class RateCurrencyEnum(str, PyEnum):
    RUB = "RUB"
    USDT = "USDT"
    USD = "USD"


class RateSourceEnum(str, PyEnum):
    auto = "auto"
    manual = "manual"


class ExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    currency: Mapped[RateCurrencyEnum] = mapped_column(Enum(RateCurrencyEnum, name="ratecurrencyenum"), nullable=False)
    rate_to_cny: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source: Mapped[RateSourceEnum] = mapped_column(Enum(RateSourceEnum, name="ratesourceenum"), nullable=False)
