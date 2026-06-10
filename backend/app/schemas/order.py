import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
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


class OrderItemPhotoResponse(BaseModel):
    id: uuid.UUID
    file_url: str
    file_name: str
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    sort_order: int = 0
    uploaded_at: datetime


class OrderItemCreate(BaseModel):
    id: Optional[uuid.UUID] = None   # присутствует при edit (frontend передаёт существующий ID)
    name: str
    name_cn: Optional[str] = None
    model: Optional[str] = None
    specification: Optional[str] = None
    # Trade / services
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    preferred_supplier_id: Optional[uuid.UUID] = None
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
    # manager_id is intentionally excluded — always set to current user in the endpoint
    client_currency: str = "CNY"
    notes: Optional[str] = None
    items: list[OrderItemCreate] = []
    charges: list[OrderChargeCreate] = []
    # Logistics metadata
    recipient: Optional[str] = None
    destination: Optional[str] = None
    arrival_date: Optional[date] = None
    tracking_number: Optional[str] = None
    warehouse_id: Optional[uuid.UUID] = None
    excluded_from_accounting: bool = False


class OrderUpdate(BaseModel):
    order_number: Optional[str] = None
    order_date: Optional[date] = None
    client_id: Optional[uuid.UUID] = None
    business_type_id: Optional[uuid.UUID] = None
    # manager_id intentionally excluded — cannot be changed after creation
    client_currency: Optional[str] = None
    notes: Optional[str] = None
    items: Optional[list[OrderItemCreate]] = None
    charges: Optional[list[OrderChargeCreate]] = None
    recipient: Optional[str] = None
    destination: Optional[str] = None
    arrival_date: Optional[date] = None
    tracking_number: Optional[str] = None
    warehouse_id: Optional[uuid.UUID] = None
    excluded_from_accounting: Optional[bool] = None


# ── Item response (role-aware) ─────────────────────────────────────────────────

class OrderItemResponseManager(BaseModel):
    """What a manager sees: sale data + preferred_supplier name, no cost."""
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    model: Optional[str] = None
    specification: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    preferred_supplier_id: Optional[uuid.UUID] = None
    preferred_supplier_name: Optional[str] = None
    sale_price: Optional[Decimal] = None
    sale_currency: Optional[str] = None
    sale_rate_to_cny: Optional[Decimal] = None
    # Logistics
    weight_kg: Optional[Decimal] = None
    volume_m3: Optional[Decimal] = None
    density_kg_m3: Optional[Decimal] = None
    price_per_kg: Optional[Decimal] = None
    price_per_kg_currency: Optional[str] = None
    cargo_value: Optional[Decimal] = None
    cargo_value_currency: Optional[str] = None
    places_count: Optional[int] = None
    purchased_quantity: Optional[Decimal] = None
    photos: List[OrderItemPhotoResponse] = []


class PurchaseItemBrief(BaseModel):
    id: uuid.UUID
    purchase_id: uuid.UUID
    purchase_number: str
    quantity: Decimal
    cost_price: Decimal
    cost_amount: Decimal


class OrderItemResponseFull(BaseModel):
    """What purchaser/accountant/admin sees: sale + purchase data."""
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    model: Optional[str] = None
    specification: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    preferred_supplier_id: Optional[uuid.UUID] = None
    preferred_supplier_name: Optional[str] = None
    sale_price: Optional[Decimal] = None
    sale_currency: Optional[str] = None
    sale_rate_to_cny: Optional[Decimal] = None
    # Logistics
    weight_kg: Optional[Decimal] = None
    volume_m3: Optional[Decimal] = None
    density_kg_m3: Optional[Decimal] = None
    price_per_kg: Optional[Decimal] = None
    price_per_kg_currency: Optional[str] = None
    cargo_value: Optional[Decimal] = None
    cargo_value_currency: Optional[str] = None
    places_count: Optional[int] = None
    # Purchase data
    purchased_quantity: Optional[Decimal] = None
    purchase_items: List[PurchaseItemBrief] = []
    photos: List[OrderItemPhotoResponse] = []


# Keep for backwards compatibility in orders.py
OrderItemResponse = OrderItemResponseFull


class OrderListItem(BaseModel):
    id: uuid.UUID
    order_number: str
    order_date: date
    client_id: uuid.UUID
    client_name: str
    client_code: Optional[str] = None
    business_type_id: uuid.UUID
    business_type_name: str
    business_type_name_cn: Optional[str] = None
    business_type_code: str
    manager_id: uuid.UUID
    manager_name: str
    status: str
    client_currency: str
    total_sale_cny: Decimal
    total_cost_cny: Optional[Decimal] = None
    payment_status: str
    supplier_payment_status: Optional[str] = None
    paid_amount_cny: Decimal = Decimal("0")
    remaining_amount_cny: Decimal = Decimal("0")
    sync_status: Optional[str] = None
    excluded_from_accounting: bool = False


class OrderResponseManager(BaseModel):
    """Visible to manager: no cost/margin/supplier_payment_status."""
    id: uuid.UUID
    order_number: str
    order_date: date
    client_id: uuid.UUID
    client_name: str
    client_phone: Optional[str] = None
    business_type_id: uuid.UUID
    business_type_name: str
    business_type_name_cn: Optional[str] = None
    business_type_code: str
    manager_id: uuid.UUID
    manager_name: str
    status: str
    client_currency: str
    total_sale_cny: Decimal
    payment_status: str
    paid_amount_cny: Decimal = Decimal("0")
    remaining_amount_cny: Decimal = Decimal("0")
    notes: Optional[str] = None
    recipient: Optional[str] = None
    destination: Optional[str] = None
    arrival_date: Optional[date] = None
    tracking_number: Optional[str] = None
    warehouse_id: Optional[uuid.UUID] = None
    warehouse_name: Optional[str] = None
    created_at: datetime
    items: List[OrderItemResponseManager] = []
    charges: List[OrderChargeResponse] = []
    # Sync fields
    external_shipment_id: Optional[str] = None
    external_shipment_number: Optional[str] = None
    external_invoice_url: Optional[str] = None
    external_tracking_url: Optional[str] = None
    sync_status: Optional[str] = None
    sync_error: Optional[str] = None
    synced_at: Optional[datetime] = None
    excluded_from_accounting: bool = False


class OrderResponseFull(BaseModel):
    """Visible to purchaser/accountant/admin: all fields."""
    id: uuid.UUID
    order_number: str
    order_date: date
    client_id: uuid.UUID
    client_name: str
    client_phone: Optional[str] = None
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
    expenses_cny: Decimal = Decimal("0")
    payment_status: str
    supplier_payment_status: str
    paid_amount_cny: Decimal = Decimal("0")
    remaining_amount_cny: Decimal = Decimal("0")
    notes: Optional[str] = None
    recipient: Optional[str] = None
    destination: Optional[str] = None
    arrival_date: Optional[date] = None
    tracking_number: Optional[str] = None
    warehouse_id: Optional[uuid.UUID] = None
    warehouse_name: Optional[str] = None
    created_at: datetime
    items: List[OrderItemResponseFull] = []
    charges: List[OrderChargeResponse] = []
    # Sync fields
    external_shipment_id: Optional[str] = None
    external_shipment_number: Optional[str] = None
    external_invoice_url: Optional[str] = None
    external_tracking_url: Optional[str] = None
    sync_status: Optional[str] = None
    sync_error: Optional[str] = None
    synced_at: Optional[datetime] = None
    excluded_from_accounting: bool = False


# Alias for imports that still use OrderResponse
OrderResponse = OrderResponseFull


class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int
    page_total_sale_cny: Decimal
    page_total_cost_cny: Optional[Decimal] = None


class AvailableForPurchaseItem(BaseModel):
    """Order item with how much is still available to purchase."""
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    sale_price: Optional[Decimal] = None
    sale_currency: Optional[str] = None
    preferred_supplier_id: Optional[uuid.UUID] = None
    preferred_supplier_name: Optional[str] = None
    already_purchased: Decimal = Decimal("0")
    available_to_purchase: Decimal = Decimal("0")
