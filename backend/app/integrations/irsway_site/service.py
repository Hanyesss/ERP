import asyncio
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.integration_settings import IntegrationSettings
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.counterparty import Counterparty
from .client import IrswayClient
from .schemas import ShipmentCreatePayload, ShipmentItemPayload, ShipmentStatusPayload


INTEGRATION_NAME = "irsway_site"


async def get_active_client(db: AsyncSession) -> Optional[IrswayClient]:
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == INTEGRATION_NAME)
    )).scalar_one_or_none()
    if not row or not row.is_enabled or not row.base_url or not row.api_token:
        return None
    return IrswayClient(base_url=row.base_url, api_token=row.api_token)


async def _build_shipment_payload(order: Order, db: AsyncSession) -> ShipmentCreatePayload:
    items_rows = (await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )).scalars().all()

    client_row = (await db.execute(
        select(Counterparty).where(Counterparty.id == order.client_id)
    )).scalar_one_or_none()

    client_phone: Optional[str] = None
    if client_row and isinstance(client_row.contact_info, dict):
        client_phone = client_row.contact_info.get("phone")

    items = [
        ShipmentItemPayload(
            name=item.name,
            weight_kg=float(item.weight_kg) if item.weight_kg is not None else None,
            volume_m3=float(item.volume_m3) if item.volume_m3 is not None else None,
            places_count=item.places_count,
            cargo_value=float(item.cargo_value) if item.cargo_value is not None else None,
            cargo_value_currency=item.cargo_value_currency,
            price_per_kg=float(item.price_per_kg) if item.price_per_kg is not None else None,
            price_per_kg_currency=item.price_per_kg_currency,
        )
        for item in items_rows
    ]

    return ShipmentCreatePayload(
        erp_order_id=str(order.id),
        erp_order_number=order.order_number,
        client_phone=client_phone,
        client_name=client_row.name if client_row else "",
        recipient=order.recipient,
        destination=order.destination,
        tracking_number=order.tracking_number,
        total_amount_cny=float(order.total_sale_cny),
        currency=order.client_currency,
        notes=order.notes,
        items=items,
        generate_invoice=True,
    )


async def sync_order_to_site(order: Order, db: AsyncSession) -> Tuple[bool, str]:
    client = await get_active_client(db)
    if client is None:
        order.sync_status = "disabled"
        order.sync_error = None
        return False, "Integration disabled or not configured"

    payload = await _build_shipment_payload(order, db)

    loop = asyncio.get_event_loop()

    if order.external_shipment_number:
        result = await loop.run_in_executor(None, lambda: client.update_shipment(order.external_shipment_number, payload))
    else:
        result = await loop.run_in_executor(None, lambda: client.create_shipment(payload))

    if result.error:
        order.sync_status = "failed"
        order.sync_error = result.error
        order.synced_at = datetime.now(timezone.utc)
        return False, result.error

    order.sync_status = "synced"
    order.sync_error = None
    order.synced_at = datetime.now(timezone.utc)
    if result.id:
        order.external_shipment_id = result.id
    if result.shipment_number:
        order.external_shipment_number = result.shipment_number
    if result.invoice_url:
        order.external_invoice_url = result.invoice_url
    if result.tracking_url:
        order.external_tracking_url = result.tracking_url

    settings_row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == INTEGRATION_NAME)
    )).scalar_one_or_none()
    if settings_row:
        settings_row.last_sync_at = datetime.now(timezone.utc)
        settings_row.last_sync_status = "ok"
        settings_row.last_sync_error = None

    return True, "ok"


async def push_status_to_site(order: Order, db: AsyncSession, status: str, comment: Optional[str] = None) -> Tuple[bool, str]:
    client = await get_active_client(db)
    if client is None:
        return False, "Integration disabled or not configured"

    if not order.external_shipment_id:
        synced, msg = await sync_order_to_site(order, db)
        if not synced:
            return False, msg

    loop = asyncio.get_event_loop()
    payload = ShipmentStatusPayload(status=status, comment=comment)
    result = await loop.run_in_executor(None, lambda: client.add_status(order.external_shipment_number, payload))

    if result.error:
        return False, result.error

    return True, "ok"
