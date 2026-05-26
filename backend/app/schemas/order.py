import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

VALID_CHARGE_TYPES = {"delivery", "insurance_percent", "insurance_cost", "china_delivery", "extra_packing", "loaders"}
ALLOWED_CURRENCIES = {"CNY", "RUB", "USDT", "USD"}


class OrderChargeCreate(BaseModel):
    charge_type: str
    amount: Decimal
    currency: str = "USD"
    notes: Optional[str] = None


class OrderChargeResponse(BaseModel):
    id: uuid.UUID
    charge_type: str
    amount: Decimal
    currency: str
    amount_cny: Decimal
    rate_to_cny: Decimal
    notes: Optional[str] = None


class OrderItemCreate(BaseModel):
    name: str
    name_cn: Optional[str] = None
    # Trade / services
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    cost_price: Optional[Decimal] = None
    cost_currency: Optional[str] = None
    supplier_id: Optional[uuid.UUID] = None
    sale_price: Optional[Decimal] = None
    sale_currency: Optional[str] = None
    # Logistics
    weight_kg: Optional[Decimal] = None
    volume_m3: Optional[Decimal] = None
    price_per_kg: Optional[Decimal] = None
    price_per_kg_currency: Optional[str] = None
    cargo_value: Optional[Decimal] = None
    cargo_value_currency: Optional[str] = None
    places_count: Optional[int] = None


class OrderCreate(BaseModel):
    order_number: str
    order_date: date
    client_id: uuid.UUID
    business_type_id: uuid.UUID
    manager_id: uuid.UUID
    client_currency: str = "CNY"
    notes: Optional[str] = None
    items: list[OrderItemCreate] = []
    charges: list[OrderChargeCreate] = []
    # Logistics metadata
    recipient: Optional[str] = None
    destination: Optional[str] = None
    arrival_date: Optional[date] = None
    tracking_number: Optional[str] = None


class OrderUpdate(BaseModel):
    order_date: Optional[date] = None
    client_id: Optional[uuid.UUID] = None
    business_type_id: Optional[uuid.UUID] = None
    manager_id: Optional[uuid.UUID] = None
    client_currency: Optional[str] = None
    notes: Optional[str] = None
    items: Optional[list[OrderItemCreate]] = None
    charges: Optional[list[OrderChargeCreate]] = None
    recipient: Optional[str] = None
    destination: Optional[str] = None
    arrival_date: Optional[date] = None
    tracking_number: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    cost_price: Optional[Decimal] = None
    cost_currency: Optional[str] = None
    supplier_id: Optional[uuid.UUID] = None
    supplier_name: Optional[str] = None
    sale_price: Optional[Decimal] = None
    sale_currency: Optional[str] = None
    sale_rate_to_cny: Optional[Decimal] = None
    cost_rate_to_cny: Optional[Decimal] = None
    # Logistics
    weight_kg: Optional[Decimal] = None
    volume_m3: Optional[Decimal] = None
    density_kg_m3: Optional[Decimal] = None
    price_per_kg: Optional[Decimal] = None
    price_per_kg_currency: Optional[str] = None
    cargo_value: Optional[Decimal] = None
    cargo_value_currency: Optional[str] = None
    places_count: Optional[int] = None

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
    recipient: Optional[str] = None
    destination: Optional[str] = None
    arrival_date: Optional[date] = None
    tracking_number: Optional[str] = None
    created_at: datetime
    items: list[OrderItemResponse] = []
    charges: list[OrderChargeResponse] = []


class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int
    page_total_sale_cny: Decimal
    page_total_cost_cny: Decimal
