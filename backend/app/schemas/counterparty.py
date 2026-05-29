import uuid
from typing import Optional, Any
from pydantic import BaseModel
from app.models.counterparty import CounterpartyType, CurrencyEnum


class ContactInfo(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class CounterpartyCreate(BaseModel):
    name: str
    name_cn: Optional[str] = None
    code: Optional[str] = None
    type: CounterpartyType
    default_currency: CurrencyEnum = CurrencyEnum.CNY
    contact_info: Optional[ContactInfo] = None
    notes: Optional[str] = None


class CounterpartyUpdate(BaseModel):
    name: Optional[str] = None
    name_cn: Optional[str] = None
    code: Optional[str] = None
    type: Optional[CounterpartyType] = None
    default_currency: Optional[CurrencyEnum] = None
    contact_info: Optional[ContactInfo] = None
    notes: Optional[str] = None


class CounterpartyResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    code: Optional[str] = None
    type: CounterpartyType
    default_currency: CurrencyEnum
    contact_info: Optional[dict] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_obj(cls, obj) -> "CounterpartyResponse":
        phone = None
        if obj.contact_info and isinstance(obj.contact_info, dict):
            phone = obj.contact_info.get("phone")
        return cls(
            id=obj.id, name=obj.name, name_cn=obj.name_cn, code=obj.code,
            type=obj.type, default_currency=obj.default_currency,
            contact_info=obj.contact_info, phone=phone,
            notes=obj.notes, is_active=obj.is_active,
        )


class CounterpartyListResponse(BaseModel):
    items: list[CounterpartyResponse]
    total: int
    page: int
    page_size: int
