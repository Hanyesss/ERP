import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel


class PurchaseItemCreate(BaseModel):
    order_item_id: uuid.UUID
    quantity: Decimal
    cost_price: Decimal


class PurchaseCreate(BaseModel):
    purchase_number: Optional[str] = None
    supplier_id: uuid.UUID
    purchase_date: date
    currency: str = "CNY"
    rate_to_cny: Decimal = Decimal("1")
    notes: Optional[str] = None
    items: List[PurchaseItemCreate] = []


class PurchaseUpdate(BaseModel):
    supplier_id: Optional[uuid.UUID] = None
    purchase_date: Optional[date] = None
    currency: Optional[str] = None
    rate_to_cny: Optional[Decimal] = None
    payment_status: Optional[str] = None
    notes: Optional[str] = None
    items: Optional[List[PurchaseItemCreate]] = None


class PurchaseItemResponse(BaseModel):
    id: uuid.UUID
    order_item_id: uuid.UUID
    order_item_name: Optional[str] = None
    order_number: Optional[str] = None
    quantity: Decimal
    cost_price: Decimal
    cost_amount: Decimal


class PurchaseResponse(BaseModel):
    id: uuid.UUID
    purchase_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    purchase_date: date
    currency: str
    total_amount: Decimal
    rate_to_cny: Decimal
    total_amount_cny: Decimal
    payment_status: str
    notes: Optional[str] = None
    created_at: datetime
    items: List[PurchaseItemResponse] = []


class PurchaseListItem(BaseModel):
    id: uuid.UUID
    purchase_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    purchase_date: date
    currency: str
    total_amount: Decimal
    total_amount_cny: Decimal
    payment_status: str
    items_count: int = 0


class PurchaseListResponse(BaseModel):
    items: List[PurchaseListItem]
    total: int
    page: int
    page_size: int
    page_total_cny: Decimal
