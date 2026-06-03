import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel


class ExpenseCreate(BaseModel):
    expense_date: date
    category_id: uuid.UUID
    currency: str
    amount: Decimal
    rate_to_cny: Decimal = Decimal("1")
    link_type: str = "none"
    order_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None
    description: str
    receipt_url: Optional[str] = None
    is_reimbursement: bool = False
    reimburse_to_user_id: Optional[uuid.UUID] = None
    cash_register_id: Optional[uuid.UUID] = None


class ExpenseUpdate(BaseModel):
    expense_date: Optional[date] = None
    category_id: Optional[uuid.UUID] = None
    currency: Optional[str] = None
    amount: Optional[Decimal] = None
    rate_to_cny: Optional[Decimal] = None
    link_type: Optional[str] = None
    order_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    reimburse_to_user_id: Optional[uuid.UUID] = None
    cash_register_id: Optional[uuid.UUID] = None


class ExpenseListItem(BaseModel):
    id: uuid.UUID
    expense_date: date
    category_id: uuid.UUID
    category_name: str
    category_name_cn: Optional[str] = None
    currency: str
    amount: Decimal
    amount_cny: Decimal
    link_type: str
    order_id: Optional[uuid.UUID] = None
    order_number: Optional[str] = None
    client_id: Optional[uuid.UUID] = None
    client_name: Optional[str] = None
    is_reimbursement: bool
    reimburse_to_user_id: Optional[uuid.UUID] = None
    reimburse_to_name: Optional[str] = None
    reimburse_status: Optional[str] = None
    description: str
    receipt_url: Optional[str] = None
    cash_register_id: Optional[uuid.UUID] = None
    cash_register_name: Optional[str] = None
    created_by: uuid.UUID
    created_by_name: str
    created_at: datetime
    is_active: bool


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    expense_date: date
    category_id: uuid.UUID
    category_name: str
    category_name_cn: Optional[str] = None
    currency: str
    amount: Decimal
    rate_to_cny: Decimal
    amount_cny: Decimal
    link_type: str
    order_id: Optional[uuid.UUID] = None
    order_number: Optional[str] = None
    client_id: Optional[uuid.UUID] = None
    client_name: Optional[str] = None
    is_reimbursement: bool
    reimburse_to_user_id: Optional[uuid.UUID] = None
    reimburse_to_name: Optional[str] = None
    reimburse_status: Optional[str] = None
    reimburse_paid_date: Optional[date] = None
    reject_reason: Optional[str] = None
    description: str
    receipt_url: Optional[str] = None
    cash_register_id: Optional[uuid.UUID] = None
    cash_register_name: Optional[str] = None
    created_by: uuid.UUID
    created_by_name: str
    created_at: datetime
    is_active: bool


class ExpenseListResponse(BaseModel):
    items: List[ExpenseListItem]
    total: int
    page: int
    page_size: int
    total_cny: Decimal
    total_order_cny: Decimal = Decimal("0")
    total_client_cny: Decimal = Decimal("0")
    total_none_cny: Decimal = Decimal("0")


class ApproveBody(BaseModel):
    amount: Optional[Decimal] = None


class RejectBody(BaseModel):
    reject_reason: str


class MarkPaidBody(BaseModel):
    paid_date: date
    cash_register_id: Optional[uuid.UUID] = None


class ReimbursementBalance(BaseModel):
    approved_amount_cny: Decimal
    paid_amount_cny: Decimal
    owed_cny: Decimal
    pending_count: int
    approved_count: int
