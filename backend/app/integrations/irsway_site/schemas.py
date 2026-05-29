from typing import Optional
from pydantic import BaseModel


class ShipmentClientLookup(BaseModel):
    phone: str


class ShipmentClientResult(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    found: bool = False


class ShipmentItemPayload(BaseModel):
    name: str
    weight_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    places_count: Optional[int] = None
    cargo_value: Optional[float] = None
    cargo_value_currency: Optional[str] = None
    price_per_kg: Optional[float] = None
    price_per_kg_currency: Optional[str] = None


class ShipmentCreatePayload(BaseModel):
    erp_order_id: str
    erp_order_number: str
    client_phone: Optional[str] = None
    client_name: str
    recipient: Optional[str] = None
    destination: Optional[str] = None
    tracking_number: Optional[str] = None
    total_amount_cny: float
    currency: str
    notes: Optional[str] = None
    items: list[ShipmentItemPayload] = []


class ShipmentStatusPayload(BaseModel):
    status: str
    comment: Optional[str] = None


class ShipmentResult(BaseModel):
    id: Optional[str] = None
    shipment_number: Optional[str] = None
    invoice_url: Optional[str] = None
    tracking_url: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


class HealthResult(BaseModel):
    ok: bool
    message: Optional[str] = None
