import httpx
from typing import Optional
from .schemas import (
    ShipmentCreatePayload, ShipmentStatusPayload,
    ShipmentResult, ShipmentClientResult, HealthResult,
)

DEFAULT_TIMEOUT = 15.0


class IrswayClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def health(self) -> HealthResult:
        try:
            r = httpx.get(self._url("/api/erp/health"), headers=self.headers, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 200:
                return HealthResult(ok=True, message=r.text[:200])
            return HealthResult(ok=False, message=f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            return HealthResult(ok=False, message=str(e))

    def lookup_client(self, phone: str) -> ShipmentClientResult:
        try:
            r = httpx.post(
                self._url("/api/erp/clients/lookup"),
                headers=self.headers,
                json={"phone": phone},
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                return ShipmentClientResult(
                    id=data.get("id"),
                    name=data.get("name"),
                    found=bool(data.get("id")),
                )
            return ShipmentClientResult(found=False)
        except Exception:
            return ShipmentClientResult(found=False)

    def create_shipment(self, payload: ShipmentCreatePayload) -> ShipmentResult:
        try:
            r = httpx.post(
                self._url("/api/erp/shipments"),
                headers=self.headers,
                json=payload.model_dump(),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                data = r.json()
                return ShipmentResult(
                    id=data.get("id") or data.get("shipment_id"),
                    shipment_number=data.get("shipment_number") or data.get("number"),
                    invoice_url=data.get("invoice_url"),
                    tracking_url=data.get("tracking_url"),
                    status=data.get("status"),
                )
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ShipmentResult(error=str(e))

    def get_shipment(self, shipment_id: str) -> ShipmentResult:
        try:
            r = httpx.get(
                self._url(f"/api/erp/shipments/{shipment_id}"),
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                return ShipmentResult(
                    id=data.get("id") or data.get("shipment_id"),
                    shipment_number=data.get("shipment_number") or data.get("number"),
                    invoice_url=data.get("invoice_url"),
                    tracking_url=data.get("tracking_url"),
                    status=data.get("status"),
                )
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ShipmentResult(error=str(e))

    def update_shipment(self, shipment_id: str, payload: ShipmentCreatePayload) -> ShipmentResult:
        try:
            r = httpx.put(
                self._url(f"/api/erp/shipments/{shipment_id}"),
                headers=self.headers,
                json=payload.model_dump(),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                return ShipmentResult(
                    id=data.get("id") or data.get("shipment_id"),
                    shipment_number=data.get("shipment_number") or data.get("number"),
                    invoice_url=data.get("invoice_url"),
                    tracking_url=data.get("tracking_url"),
                    status=data.get("status"),
                )
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ShipmentResult(error=str(e))

    def add_status(self, shipment_id: str, payload: ShipmentStatusPayload) -> ShipmentResult:
        try:
            r = httpx.post(
                self._url(f"/api/erp/shipments/{shipment_id}/status"),
                headers=self.headers,
                json=payload.model_dump(),
                timeout=DEFAULT_TIMEOUT,
            )
            if r.status_code in (200, 201):
                data = r.json()
                return ShipmentResult(
                    id=shipment_id,
                    status=data.get("status"),
                )
            return ShipmentResult(error=f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return ShipmentResult(error=str(e))
