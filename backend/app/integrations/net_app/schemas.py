from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class NetClientIn(BaseModel):
    client_code: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class NetStatusIn(BaseModel):
    code: str
    label: Optional[str] = None
    lifecycle: Optional[str] = "active"


class NetOrderIn(BaseModel):
    """Входящий payload от приложения NET (PARCEL)."""
    external_ref: str
    source: str = "net"
    business_type: str = "logistics"
    client: NetClientIn = Field(default_factory=NetClientIn)
    tracking_number: Optional[str] = None
    marketplace: Optional[str] = None
    description: Optional[str] = None
    weight_g: Optional[int] = None
    status: NetStatusIn
    occurred_at: Optional[datetime] = None


class NetOrderResult(BaseModel):
    ok: bool = True
    external_ref: str
    order_number: str
    created: bool
