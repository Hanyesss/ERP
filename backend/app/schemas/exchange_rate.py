import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from app.models.exchange_rate import RateCurrencyEnum, RateSourceEnum


class ExchangeRateCreate(BaseModel):
    currency: RateCurrencyEnum
    rate_to_cny: Decimal
    rate_date: date
    source: RateSourceEnum = RateSourceEnum.manual


class ExchangeRateResponse(BaseModel):
    id: uuid.UUID
    currency: RateCurrencyEnum
    rate_to_cny: Decimal
    rate_date: date
    created_by: uuid.UUID
    created_by_name: str
    source: RateSourceEnum
    created_at: datetime

    class Config:
        from_attributes = True


class ExchangeRateListResponse(BaseModel):
    items: list[ExchangeRateResponse]
    total: int


class RateCheckResponse(BaseModel):
    rates: dict[str, float]
    missing: list[str]
