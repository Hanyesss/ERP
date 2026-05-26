import uuid
from typing import Optional, Any
from pydantic import BaseModel, EmailStr
from app.models.counterparty import CounterpartyType, CurrencyEnum


class ContactInfo(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class CounterpartyCreate(BaseModel):
    name: str
    name_cn: Optional[str] = None
    type: CounterpartyType
    default_currency: CurrencyEnum = CurrencyEnum.CNY
    contact_info: Optional[ContactInfo] = None
    notes: Optional[str] = None


class CounterpartyUpdate(BaseModel):
    name: Optional[str] = None
    name_cn: Optional[str] = None
    type: Optional[CounterpartyType] = None
    default_currency: Optional[CurrencyEnum] = None
    contact_info: Optional[ContactInfo] = None
    notes: Optional[str] = None


class CounterpartyResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    type: CounterpartyType
    default_currency: CurrencyEnum
    contact_info: Optional[dict] = None
    notes: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class CounterpartyListResponse(BaseModel):
    items: list[CounterpartyResponse]
    total: int
    page: int
    page_size: int
