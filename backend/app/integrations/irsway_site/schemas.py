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
    # client_code используется irsway для привязки owner (приоритет); client_phone — запасной вариант
    client_phone: Optional[str] = None
    client_code: Optional[str] = None
    partner_code: Optional[str] = None  # код партнёра, к которому привязан клиент
    client_name: str
    recipient: Optional[str] = None
    destination: Optional[str] = None
    tracking_number: Optional[str] = None
    total_amount_cny: float
    currency: str
    notes: Optional[str] = None
    items: list[ShipmentItemPayload] = []
    generate_invoice: bool = True
    # Хранимые поля расходов на стороне irsway (в USD).
    # delivery_cost и insurance_cost НЕ включены — они @property на irsway (weight×price_per_kg
    # и cargo_value×insurance_percent/100), устанавливать их через API невозможно.
    insurance_percent: Optional[float] = None  # процент, не валюта
    china_delivery: Optional[float] = None     # USD
    packing: Optional[float] = None            # USD (ERP: extra_packing)
    market_fee: Optional[float] = None         # USD (ERP: loaders)


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


class TradeOrderPayload(BaseModel):
    """Payload для создания/обновления торгового заказа на сайте."""
    erp_order_id: str
    number: str
    client_code: Optional[str] = None
    client_name: str
    goods_name: Optional[str] = None
    order_date: Optional[str] = None      # YYYY-MM-DD
    currency: str = "CNY"
    total_amount_cny: Optional[float] = None
    paid_amount_cny: Optional[float] = None
    payment_status: str = "unpaid"        # unpaid / partial / paid
    invoice_url: Optional[str] = None
    notes: Optional[str] = None


class TradeOrderResult(BaseModel):
    id: Optional[int] = None
    number: Optional[str] = None
    remaining_cny: Optional[str] = None
    error: Optional[str] = None


class HealthResult(BaseModel):
    ok: bool
    message: Optional[str] = None


class ClientCreateResult(BaseModel):
    ok: bool
    error: Optional[str] = None
    user_id: Optional[str] = None
