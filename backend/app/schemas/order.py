import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class OrderItemCreate(BaseModel):
    name: str
    name_cn: Optional[str] = None
    quantity: Decimal
    unit: Optional[str] = None
    cost_price: Decimal
    cost_currency: str = "CNY"
    supplier_id: Optional[uuid.UUID] = None
    sale_price: Decimal
    sale_currency: str = "CNY"


class OrderCreate(BaseModel):
    order_number: str
    order_date: date
    client_id: uuid.UUID
    business_type_id: uuid.UUID
    manager_id: uuid.UUID
    client_currency: str = "CNY"
    notes: Optional[str] = None
    items: list[OrderItemCreate] = []


class OrderUpdate(BaseModel):
    order_date: Optional[date] = None
    client_id: Optional[uuid.UUID] = None
    business_type_id: Optional[uuid.UUID] = None
    manager_id: Optional[uuid.UUID] = None
    client_currency: Optional[str] = None
    notes: Optional[str] = None
    items: Optional[list[OrderItemCreate]] = None


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    quantity: Decimal
    unit: Optional[str] = None
    cost_price: Decimal
    cost_currency: str
    supplier_id: Optional[uuid.UUID] = None
    supplier_name: Optional[str] = None
    sale_price: Decimal
    sale_currency: str
    sale_rate_to_cny: Decimal
    cost_rate_to_cny: Decimal

    class Config:
        from_attributes = True


class OrderListItem(BaseModel):
    id: uuid.UUID
    order_number: str
    order_date: date
    client_id: uuid.UUID
    client_name: str
    business_type_id: uuid.UUID
    business_type_name: str
    business_type_code: str
    manager_id: uuid.UUID
    manager_name: str
    status: str
    client_currency: str
    total_sale_cny: Decimal
    total_cost_cny: Decimal
    payment_status: str
    supplier_payment_status: str


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    order_date: date
    client_id: uuid.UUID
    client_name: str
    business_type_id: uuid.UUID
    business_type_name: str
    business_type_name_cn: Optional[str] = None
    business_type_code: str
    manager_id: uuid.UUID
    manager_name: str
    status: str
    client_currency: str
    total_sale_cny: Decimal
    total_cost_cny: Decimal
    payment_status: str
    supplier_payment_status: str
    notes: Optional[str] = None
    created_at: datetime
    items: list[OrderItemResponse] = []


class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int
    page_total_sale_cny: Decimal
    page_total_cost_cny: Decimal
