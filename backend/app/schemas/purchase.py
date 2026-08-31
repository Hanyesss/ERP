import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel


class PurchaseItemCreate(BaseModel):
    order_item_id: Optional[uuid.UUID] = None   # None → складская позиция (по name)
    quantity: Decimal
    cost_price: Decimal
    name: Optional[str] = None                   # для складской позиции
    name_cn: Optional[str] = None
    unit: Optional[str] = None


class PurchaseCreate(BaseModel):
    purchase_number: Optional[str] = None
    supplier_id: uuid.UUID
    purchase_date: date
    currency: str = "CNY"
    rate_to_cny: Decimal = Decimal("1")
    notes: Optional[str] = None
    items: List[PurchaseItemCreate] = []
    # logistics-only fields
    order_id: Optional[uuid.UUID] = None
    total_amount: Optional[Decimal] = None
    excluded_from_accounting: bool = False


class PurchaseUpdate(BaseModel):
    supplier_id: Optional[uuid.UUID] = None
    purchase_date: Optional[date] = None
    currency: Optional[str] = None
    rate_to_cny: Optional[Decimal] = None
    payment_status: Optional[str] = None
    notes: Optional[str] = None
    items: Optional[List[PurchaseItemCreate]] = None
    excluded_from_accounting: Optional[bool] = None


class PurchaseItemResponse(BaseModel):
    id: uuid.UUID
    order_item_id: Optional[uuid.UUID] = None
    order_item_name: Optional[str] = None
    order_number: Optional[str] = None
    quantity: Decimal
    cost_price: Decimal
    cost_amount: Decimal
    name: Optional[str] = None
    is_stock: bool = False
    remaining_quantity: Optional[Decimal] = None


class StockItemResponse(BaseModel):
    """Складская позиция с остатком (для выбора при продаже)."""
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    unit: Optional[str] = None
    quantity: Decimal
    remaining_quantity: Decimal
    cost_price: Decimal
    cost_price_cny: Decimal
    currency: str
    purchase_id: uuid.UUID
    purchase_number: str
    purchase_date: date


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
    paid_amount_cny: Decimal = Decimal("0")
    remaining_amount_cny: Decimal = Decimal("0")
    notes: Optional[str] = None
    created_at: datetime
    items: List[PurchaseItemResponse] = []
    order_id: Optional[uuid.UUID] = None
    order_number: Optional[str] = None
    created_by_name: Optional[str] = None
    excluded_from_accounting: bool = False
    payment_requested: bool = False
    payment_requested_by_name: Optional[str] = None
    payment_requested_at: Optional[datetime] = None


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
    paid_amount_cny: Decimal = Decimal("0")
    remaining_amount_cny: Decimal = Decimal("0")
    order_id: Optional[uuid.UUID] = None
    order_number: Optional[str] = None
    excluded_from_accounting: bool = False
    payment_requested: bool = False


class PurchaseListResponse(BaseModel):
    items: List[PurchaseListItem]
    total: int
    page: int
    page_size: int
    page_total_cny: Decimal
