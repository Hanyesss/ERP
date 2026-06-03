import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.integration_settings import IntegrationSettings
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_charge import OrderCharge
from app.models.counterparty import Counterparty
from .client import IrswayClient
from .schemas import ShipmentCreatePayload, ShipmentItemPayload, ShipmentStatusPayload, TradeOrderPayload

logger = logging.getLogger(__name__)

INTEGRATION_NAME = "irsway_site"


async def get_active_client(db: AsyncSession) -> Optional[IrswayClient]:
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == INTEGRATION_NAME)
    )).scalar_one_or_none()
    if not row or not row.is_enabled or not row.base_url or not row.api_token:
        return None
    return IrswayClient(base_url=row.base_url, api_token=row.api_token)


def _charge_usd(charge: Optional[OrderCharge]) -> Optional[float]:
    """
    Возвращает сумму расхода в USD.
    Если расход в USD — берём amount напрямую.
    Если в другой валюте — берём amount_cny как приближение (НЕ USD!),
    логируем предупреждение. Логистические расходы должны вводиться в USD.
    """
    if not charge or not charge.amount:
        return None
    if charge.currency == "USD":
        return float(charge.amount)
    logger.warning(
        "Charge %s currency=%s (not USD) — sending amount_cny=%.2f as fallback; "
        "logistics charges should be entered in USD",
        charge.charge_type, charge.currency, float(charge.amount_cny or 0),
    )
    return float(charge.amount_cny) if charge.amount_cny else None


async def _build_shipment_payload(order: Order, db: AsyncSession) -> ShipmentCreatePayload:
    # Перечитываем items и charges из БД (заказ уже закоммичен)
    items_rows = (await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )).scalars().all()

    charge_rows = (await db.execute(
        select(OrderCharge).where(OrderCharge.order_id == order.id)
    )).scalars().all()
    # Словарь charge_type → первая запись (дублей не должно быть)
    charges: dict[str, OrderCharge] = {}
    for c in charge_rows:
        if c.charge_type not in charges:
            charges[c.charge_type] = c

    client_row = (await db.execute(
        select(Counterparty).where(Counterparty.id == order.client_id)
    )).scalar_one_or_none()

    client_phone: Optional[str] = None
    if client_row and isinstance(client_row.contact_info, dict):
        client_phone = client_row.contact_info.get("phone")

    # insurance_percent — передаём как число-процент (безразмерное), не конвертируем
    ins_charge = charges.get("insurance_percent")
    insurance_percent: Optional[float] = None
    if ins_charge and ins_charge.amount:
        insurance_percent = float(ins_charge.amount)

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

    payload = ShipmentCreatePayload(
        erp_order_id=str(order.id),
        erp_order_number=order.order_number,
        client_phone=client_phone,
        client_code=client_row.code.upper() if client_row and client_row.code else None,
        client_name=client_row.name if client_row else "",
        recipient=order.recipient,
        destination=order.destination,
        tracking_number=order.tracking_number,
        total_amount_cny=float(order.total_sale_cny),
        currency=order.client_currency,
        notes=order.notes,
        items=items,
        generate_invoice=True,
        insurance_percent=insurance_percent,
        china_delivery=_charge_usd(charges.get("china_delivery")),
        packing=_charge_usd(charges.get("extra_packing")),
        market_fee=_charge_usd(charges.get("loaders")),
    )

    logger.info(
        "Irsway payload для заказа %s: client_code=%s client_phone=%s "
        "items=%d insurance_percent=%s china_delivery=%s packing=%s market_fee=%s",
        order.order_number,
        payload.client_code,
        payload.client_phone,
        len(payload.items),
        payload.insurance_percent,
        payload.china_delivery,
        payload.packing,
        payload.market_fee,
    )

    return payload


async def sync_order_to_site(order: Order, db: AsyncSession) -> Tuple[bool, str]:
    client = await get_active_client(db)
    if client is None:
        order.sync_status = "disabled"
        order.sync_error = None
        return False, "Integration disabled or not configured"

    payload = await _build_shipment_payload(order, db)

    loop = asyncio.get_event_loop()

    if order.external_shipment_number:
        result = await loop.run_in_executor(
            None, lambda: client.update_shipment(order.external_shipment_number, payload)
        )
        logger.info(
            "Irsway update_shipment %s → error=%s id=%s",
            order.external_shipment_number, result.error, result.id,
        )
    else:
        result = await loop.run_in_executor(
            None, lambda: client.create_shipment(payload)
        )
        logger.info(
            "Irsway create_shipment %s → error=%s id=%s number=%s",
            order.order_number, result.error, result.id, result.shipment_number,
        )

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


async def sync_trade_order_to_site(order: Order, db: AsyncSession) -> Tuple[bool, str]:
    """Синхронизирует торговый заказ на сайт irsway.com."""
    client = await get_active_client(db)
    if client is None:
        order.sync_status = "disabled"
        return False, "Integration disabled"

    client_row = (await db.execute(
        select(Counterparty).where(Counterparty.id == order.client_id)
    )).scalar_one_or_none()

    # Формируем наименование товаров из позиций
    from app.models.order_item import OrderItem
    items_rows = (await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )).scalars().all()
    goods_name = ", ".join(i.name for i in items_rows if i.name) or ""

    # Статус оплаты
    from app.models.payment import PaymentStatus
    ps = order.payment_status
    if hasattr(ps, 'value'):
        ps = ps.value
    status_map = {"unpaid": "unpaid", "partial": "partial", "paid": "paid"}
    payment_status = status_map.get(str(ps), "unpaid")

    payload = TradeOrderPayload(
        erp_order_id=str(order.id),
        number=order.order_number,
        client_code=client_row.code.upper() if client_row and client_row.code else None,
        client_name=client_row.name if client_row else "",
        goods_name=goods_name,
        order_date=order.order_date.isoformat() if order.order_date else None,
        currency=str(order.client_currency.value if hasattr(order.client_currency, 'value') else order.client_currency),
        total_amount_cny=float(order.total_sale_cny) if order.total_sale_cny else None,
        paid_amount_cny=float(order.total_sale_cny - order.remaining_amount_cny)
            if order.total_sale_cny and hasattr(order, 'remaining_amount_cny') else 0.0,
        payment_status=payment_status,
        notes=order.notes,
    )

    loop = asyncio.get_event_loop()

    if order.external_shipment_number:
        result = await loop.run_in_executor(
            None, lambda: client.update_trade_order(order.external_shipment_number, payload)
        )
    else:
        result = await loop.run_in_executor(
            None, lambda: client.create_trade_order(payload)
        )

    if result.error:
        order.sync_status = "failed"
        order.sync_error = result.error
        order.synced_at = datetime.now(timezone.utc)
        return False, result.error

    order.sync_status = "synced"
    order.sync_error = None
    order.synced_at = datetime.now(timezone.utc)
    if result.number:
        order.external_shipment_number = result.number

    settings_row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == INTEGRATION_NAME)
    )).scalar_one_or_none()
    if settings_row:
        settings_row.last_sync_at = datetime.now(timezone.utc)
        settings_row.last_sync_status = "ok"

    logger.info("Trade order synced: %s → status=%s remaining=%s",
                order.order_number, payment_status, result.remaining_cny)
    return True, "ok"


async def push_status_to_site(
    order: Order, db: AsyncSession, status: str, comment: Optional[str] = None
) -> Tuple[bool, str]:
    client = await get_active_client(db)
    if client is None:
        return False, "Integration disabled or not configured"

    if not order.external_shipment_id:
        synced, msg = await sync_order_to_site(order, db)
        if not synced:
            return False, msg

    loop = asyncio.get_event_loop()
    payload = ShipmentStatusPayload(status=status, comment=comment)
    result = await loop.run_in_executor(
        None, lambda: client.add_status(order.external_shipment_number, payload)
    )
    logger.info(
        "Irsway add_status %s status=%s → error=%s",
        order.external_shipment_number, status, result.error,
    )

    if result.error:
        return False, result.error

    return True, "ok"
