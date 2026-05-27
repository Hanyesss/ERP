import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator


class AllocationIn(BaseModel):
    """One allocation line when creating/updating a payment."""
    order_id: Optional[uuid.UUID] = None
    purchase_id: Optional[uuid.UUID] = None
    amount_cny: Decimal
    notes: Optional[str] = None


class PaymentCreate(BaseModel):
    direction: str          # "in" | "out"
    counterparty_id: uuid.UUID
    payment_date: date
    currency: str           # CNY | RUB | USDT | USD
    amount: Decimal
    rate_to_cny: Decimal = Decimal("1")
    network_fee: Optional[Decimal] = None
    notes: Optional[str] = None
    allocations: List[AllocationIn] = []


class PaymentUpdate(BaseModel):
    payment_date: Optional[date] = None
    currency: Optional[str] = None
    amount: Optional[Decimal] = None
    rate_to_cny: Optional[Decimal] = None
    network_fee: Optional[Decimal] = None
    notes: Optional[str] = None


class AllocationResponse(BaseModel):
    id: uuid.UUID
    order_id: Optional[uuid.UUID] = None
    order_number: Optional[str] = None
    purchase_id: Optional[uuid.UUID] = None
    purchase_number: Optional[str] = None
    amount_cny: Decimal
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    direction: str
    counterparty_id: uuid.UUID
    counterparty_name: str
    payment_date: date
    currency: str
    amount: Decimal
    rate_to_cny: Decimal
    amount_cny: Decimal
    network_fee: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: bool
    created_by_name: str
    created_at: datetime
    allocations: List[AllocationResponse] = []
    allocated_cny: Decimal = Decimal("0")
    unallocated_cny: Decimal = Decimal("0")


class PaymentListItem(BaseModel):
    id: uuid.UUID
    direction: str
    counterparty_id: uuid.UUID
    counterparty_name: str
    payment_date: date
    currency: str
    amount: Decimal
    amount_cny: Decimal
    allocations_count: int = 0
    allocated_cny: Decimal = Decimal("0")
    is_active: bool
    created_by_name: str


class PaymentListResponse(BaseModel):
    items: List[PaymentListItem]
    total: int
    page: int
    page_size: int
    total_incoming_cny: Decimal
    total_outgoing_cny: Decimal


class OrderPaymentBalance(BaseModel):
    order_id: uuid.UUID
    order_number: str
    total_cny: Decimal
    paid_cny: Decimal
    remaining_cny: Decimal
    payment_status: str


class PurchasePaymentBalance(BaseModel):
    purchase_id: uuid.UUID
    purchase_number: str
    total_cny: Decimal
    paid_cny: Decimal
    remaining_cny: Decimal
    payment_status: str
