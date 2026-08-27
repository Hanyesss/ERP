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


# ── Агрегатная отправка (WH → ERP), уровень отправки, а не посылки ──────────────

class NetBoxIn(BaseModel):
    box_code: str
    city: Optional[str] = None
    weight_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    paid_rub: Optional[float] = None
    parcels_count: Optional[int] = None


class NetShipmentIn(BaseModel):
    shipment_ref: str
    created_at: Optional[datetime] = None
    total_weight_kg: Optional[float] = None
    total_volume_m3: Optional[float] = None
    total_paid_rub: Optional[float] = 0
    boxes_count: Optional[int] = None
    parcels_count: Optional[int] = None
    destinations: list[str] = Field(default_factory=list)
    boxes: list[NetBoxIn] = Field(default_factory=list)


class NetShipmentResult(BaseModel):
    ok: bool = True
    shipment_ref: str
    erp_order_number: str
    created: bool
