import logging
import httpx
from typing import Optional
from .schemas import (
    ShipmentCreatePayload, ShipmentStatusPayload,
    ShipmentResult, ShipmentClientResult, HealthResult, ClientCreateResult,
    TradeOrderPayload, TradeOrderResult,
    WarehouseStockPayload, WarehouseStockResult,
    ReconciliationPayload, ReconciliationResult,
)

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 15.0


class IrswayClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        url = f"{self.base_url}/{path.lstrip('/')}"
        logger.info("Irsway API → %s", url)
        return url

    def _parse_shipment(self, data: dict) -> ShipmentResult:
        statuses = data.get("statuses") or []
        last_status = statuses[-1].get("status") if statuses else data.get("status")
        return ShipmentResult(
            id=str(data.get("id")) if data.get("id") else None,
            shipment_number=data.get("number"),
            invoice_url=data.get("invoice_url"),
            tracking_url=data.get("public_tracking_url"),
            status=last_status,
        )

    def _build_shipment_body(self, payload: ShipmentCreatePayload) -> dict:
        items = payload.items or []
        total_weight = sum(i.weight_kg for i in items if i.weight_kg) or None
        total_volume = sum(i.volume_m3 for i in items if i.volume_m3) or None
        total_places = sum(i.places_count for i in items if i.places_count) or None
        goods_name = ", ".join(i.name for i in items if i.name) if items else ""
        price_per_kg = items[0].price_per_kg if items and items[0].price_per_kg else None

        body: dict = {
            "number": payload.erp_order_number,
            "erp_order_id": payload.erp_order_id,
            "client_name": payload.client_name,
            "destination": payload.destination,
            "receiver_name": payload.recipient,
            "goods_name": goods_name,
        }
        if payload.client_code:
            body["client_code"] = payload.client_code
        if payload.client_phone:
            body["client_phone"] = payload.client_phone
        if payload.partner_code:
            body["partner_code"] = payload.partner_code
        if total_weight is not None:
            body["weight"] = total_weight
        if total_volume is not None:
            body["volume"] = total_volume
        if total_places is not None:
            body["places_count"] = total_places
        if price_per_kg is not None:
            body["price_per_kg"] = price_per_kg
        # cargo_value нужен irsway для расчёта insurance_cost = cargo_value × insurance_percent / 100
        total_cargo = sum(i.cargo_value for i in items if i.cargo_value) or None
        if total_cargo is not None:
            body["cargo_value"] = total_cargo
            cargo_currency = next((i.cargo_value_currency for i in items if i.cargo_value and i.cargo_value_currency), None)
            if cargo_currency:
                body["cargo_value_currency"] = cargo_currency
        body["total_amount_cny"] = payload.total_amount_cny
        body["generate_invoice"] = payload.generate_invoice
        if payload.insurance_percent is not None:
            body["insurance_percent"] = payload.insurance_percent
        if payload.china_delivery is not None:
            body["china_delivery"] = payload.china_delivery
        if payload.packing is not None:
            body["packing"] = payload.packing
        if payload.market_fee is not None:
            body["market_fee"] = payload.market_fee
        return body

    def health(self) -> HealthResult:
        try:
            r = httpx.get(self._url("/api/v1/health/"), headers=self.headers, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 200:
                return HealthResult(ok=True, message=r.text[:200])
            return HealthResult(ok=False, message=f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            return HealthResult(ok=False, message=str(e))

    def create_client(self, username: str, password: str, full_name: str, phone: Optional[str] = None, code: Optional[str] = None) -> ClientCreateResult:
        body: dict = {"username": username, "password": password, "full_name": full_name}
        if phone:
            body["phone"] = phone
        if code:
            body["code"] = code
        try:
            r = httpx.post(
                self._url("/api/v1/clients/"),
                headers=self.headers,
                json=body,
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                data = r.json()
                return ClientCreateResult(ok=True, user_id=str(data.get("user_id") or data.get("id") or ""))
            return ClientCreateResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ClientCreateResult(ok=False, error=str(e))

    def update_client_credentials(self, username: str, new_username: Optional[str] = None, new_password: Optional[str] = None) -> ClientCreateResult:
        body: dict = {}
        if new_username:
            body["new_username"] = new_username
        if new_password:
            body["new_password"] = new_password
        try:
            r = httpx.patch(
                self._url(f"/api/v1/clients/{username}/"),
                headers=self.headers,
                json=body,
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                return ClientCreateResult(ok=True, user_id=data.get("username", ""))
            return ClientCreateResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ClientCreateResult(ok=False, error=str(e))

    def link_client(self, code: str) -> ClientCreateResult:
        try:
            r = httpx.post(
                self._url("/api/v1/clients/link/"),
                headers=self.headers,
                json={"code": code},
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                data = r.json()
                client = data.get("client") or {}
                return ClientCreateResult(ok=True, user_id=str(client.get("user_id") or ""))
            return ClientCreateResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ClientCreateResult(ok=False, error=str(e))

    def lookup_client(self, phone: str) -> ShipmentClientResult:
        try:
            r = httpx.get(
                self._url("/api/v1/clients/lookup/"),
                headers=self.headers,
                params={"phone": phone},
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("found"):
                    client = data.get("client") or {}
                    return ShipmentClientResult(
                        id=str(client.get("user_id")),
                        name=client.get("full_name"),
                        found=True,
                    )
            return ShipmentClientResult(found=False)
        except Exception:
            return ShipmentClientResult(found=False)

    def create_shipment(self, payload: ShipmentCreatePayload) -> ShipmentResult:
        try:
            r = httpx.post(
                self._url("/api/v1/shipments/"),
                headers=self.headers,
                json=self._build_shipment_body(payload),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                return self._parse_shipment(r.json())
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ShipmentResult(error=str(e))

    def get_shipment(self, shipment_number: str) -> ShipmentResult:
        try:
            r = httpx.get(
                self._url(f"/api/v1/shipments/{shipment_number}/"),
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code == 200:
                return self._parse_shipment(r.json())
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ShipmentResult(error=str(e))

    def delete_shipment(self, shipment_number: str) -> ShipmentResult:
        try:
            r = httpx.delete(
                self._url(f"/api/v1/shipments/{shipment_number}/"),
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 204):
                return ShipmentResult()
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            return ShipmentResult(error=str(e))

    def update_shipment(self, shipment_number: str, payload: ShipmentCreatePayload) -> ShipmentResult:
        try:
            body = self._build_shipment_body(payload)
            body.pop("number", None)  # site does not allow renaming an existing shipment
            r = httpx.patch(
                self._url(f"/api/v1/shipments/{shipment_number}/"),
                headers=self.headers,
                json=body,
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code == 200:
                return self._parse_shipment(r.json())
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ShipmentResult(error=str(e))

    # ── Trade Orders ──────────────────────────────────────────────────────────

    def create_trade_order(self, payload: TradeOrderPayload) -> TradeOrderResult:
        try:
            r = httpx.post(
                self._url("/api/v1/trade-orders/"),
                headers=self.headers,
                json=payload.model_dump(exclude_none=True),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                data = r.json()
                return TradeOrderResult(id=data.get("id"), number=data.get("number"),
                                        remaining_cny=data.get("remaining_cny"))
            return TradeOrderResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return TradeOrderResult(error=str(e))

    def update_trade_order(self, number: str, payload: TradeOrderPayload) -> TradeOrderResult:
        try:
            r = httpx.patch(
                self._url(f"/api/v1/trade-orders/{number}/"),
                headers=self.headers,
                json=payload.model_dump(exclude_none=True),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                return TradeOrderResult(id=data.get("id"), number=data.get("number"),
                                        remaining_cny=data.get("remaining_cny"))
            return TradeOrderResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return TradeOrderResult(error=str(e))

    def delete_trade_order(self, number: str) -> TradeOrderResult:
        try:
            r = httpx.delete(
                self._url(f"/api/v1/trade-orders/{number}/"),
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 204):
                return TradeOrderResult()
            return TradeOrderResult(error=f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            return TradeOrderResult(error=str(e))

    def upload_trade_invoice(self, number: str, pdf_bytes: bytes) -> TradeOrderResult:
        upload_headers = {k: v for k, v in self.headers.items() if k != "Content-Type"}
        try:
            r = httpx.post(
                self._url(f"/api/v1/trade-orders/{number}/invoice/"),
                headers=upload_headers,
                files={"invoice": (f"{number}.pdf", pdf_bytes, "application/pdf")},
                timeout=30.0,
            )
            if r.status_code in (200, 201):
                return TradeOrderResult(invoice_url=r.json().get("invoice_url"))
            return TradeOrderResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return TradeOrderResult(error=str(e))

    def upsert_warehouse_stock(self, payload: WarehouseStockPayload) -> WarehouseStockResult:
        try:
            r = httpx.post(
                self._url("/api/v1/warehouse-stock/"),
                headers=self.headers,
                json=payload.model_dump(exclude_none=True),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                return WarehouseStockResult()
            return WarehouseStockResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return WarehouseStockResult(ok=False, error=str(e))

    def push_reconciliation(self, payload: ReconciliationPayload) -> ReconciliationResult:
        try:
            r = httpx.post(
                self._url("/api/v1/reconciliation/"),
                headers=self.headers,
                json=payload.model_dump(),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                return ReconciliationResult()
            return ReconciliationResult(ok=False, error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ReconciliationResult(ok=False, error=str(e))

    def add_status(self, shipment_number: str, payload: ShipmentStatusPayload) -> ShipmentResult:
        try:
            r = httpx.post(
                self._url(f"/api/v1/shipments/{shipment_number}/statuses/"),
                headers=self.headers,
                json=payload.model_dump(),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                data = r.json()
                statuses = data.get("statuses") or []
                last_status = statuses[-1].get("status") if statuses else None
                return ShipmentResult(id=shipment_number, status=last_status)
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ShipmentResult(error=str(e))
