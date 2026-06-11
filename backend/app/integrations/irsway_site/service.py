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
from .schemas import ShipmentCreatePayload, ShipmentItemPayload, ShipmentStatusPayload, TradeOrderPayload, WarehouseStockPayload, WarehouseStockItem, ReconciliationPayload, ReconciliationRowPayload, PaymentEntryPayload

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

    partner_code: Optional[str] = None
    if client_row and client_row.partner_id:
        partner_row = (await db.execute(
            select(Counterparty).where(Counterparty.id == client_row.partner_id)
        )).scalar_one_or_none()
        if partner_row and partner_row.code:
            partner_code = partner_row.code.strip().upper()

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
        partner_code=partner_code,
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
        "Irsway payload для заказа %s: client_code=%s partner_code=%s client_phone=%s "
        "items=%d insurance_percent=%s china_delivery=%s packing=%s market_fee=%s",
        order.order_number,
        payload.client_code,
        payload.partner_code,
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

    number_changed = (
        order.external_shipment_number is not None
        and order.external_shipment_number != order.order_number
    )

    if order.external_shipment_number and not number_changed:
        # Номер не менялся — обновляем существующее отправление
        result = await loop.run_in_executor(
            None, lambda: client.update_shipment(order.external_shipment_number, payload)
        )
        logger.info(
            "Irsway update_shipment %s → error=%s id=%s",
            order.external_shipment_number, result.error, result.id,
        )
        # 404 — отправление удалено на сайте, пересоздаём
        if result.error and "404" in result.error:
            logger.warning(
                "Irsway: shipment %s not found (404), re-creating",
                order.external_shipment_number,
            )
            order.external_shipment_number = None
            order.external_shipment_id = None
            result = await loop.run_in_executor(
                None, lambda: client.create_shipment(payload)
            )
            logger.info(
                "Irsway re-create after 404: %s → error=%s id=%s number=%s",
                order.order_number, result.error, result.id, result.shipment_number,
            )
    else:
        # Нет отправления или номер изменился — создаём новое
        if number_changed:
            old_number = order.external_shipment_number
            logger.info(
                "Irsway: order_number changed (%s → %s), deleting old and creating new shipment",
                old_number, order.order_number,
            )
            del_result = await loop.run_in_executor(
                None, lambda: client.delete_shipment(old_number)
            )
            if del_result.error:
                logger.warning("Irsway: delete old shipment %s → %s", old_number, del_result.error)
            order.external_shipment_number = None
            order.external_shipment_id = None
            order.external_invoice_url = None
            order.external_tracking_url = None
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
    from app.models.order import PaymentStatus
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
        # Если уже существует — обновляем
        if result.error and "already exists" in (result.error or ""):
            result = await loop.run_in_executor(
                None, lambda: client.update_trade_order(payload.number, payload)
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

    # Upload PDF invoice to irsway
    trade_number = order.external_shipment_number or order.order_number
    try:
        from app.api.order_pdf import generate_trade_pdf_bytes
        pdf_bytes = await generate_trade_pdf_bytes(order.id, db)
        inv_result = await loop.run_in_executor(
            None, lambda: client.upload_trade_invoice(trade_number, pdf_bytes)
        )
        if inv_result.invoice_url:
            order.external_invoice_url = inv_result.invoice_url
            logger.info("Trade invoice uploaded for %s → %s", trade_number, inv_result.invoice_url)
        elif inv_result.error:
            logger.warning("Trade invoice upload failed for %s: %s", trade_number, inv_result.error)
    except Exception as e:
        logger.warning("Trade invoice generation/upload failed for %s: %s", trade_number, e)

    settings_row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == INTEGRATION_NAME)
    )).scalar_one_or_none()
    if settings_row:
        settings_row.last_sync_at = datetime.now(timezone.utc)
        settings_row.last_sync_status = "ok"

    logger.info("Trade order synced: %s → status=%s remaining=%s",
                order.order_number, payment_status, result.remaining_cny)
    return True, "ok"


async def sync_box_to_site(box, counterparty, db: AsyncSession) -> bool:
    """Push a WarehouseBox snapshot to irsway WarehouseStock."""
    client = await get_active_client(db)
    if client is None:
        return False

    items = [
        WarehouseStockItem(
            name=item.name,
            quantity=item.quantity,
            tracking_code=item.tracking_code,
        )
        for item in (box.items or [])
    ]

    status_val = box.status.value if hasattr(box.status, 'value') else str(box.status)

    payload = WarehouseStockPayload(
        box_code=box.box_code,
        client_code=counterparty.code.upper() if counterparty and counterparty.code else "",
        item_name=box.item_name or "",
        items=items,
        weight=float(box.weight) if box.weight is not None else None,
        volume=float(box.volume) if box.volume is not None else None,
        density=float(box.density) if box.density is not None else None,
        status=status_val,
        received_at=box.received_at.isoformat() if box.received_at else None,
        shipped_at=box.shipped_at.isoformat() if box.shipped_at else None,
        erp_box_id=str(box.id),
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: client.upsert_warehouse_stock(payload))

    if not result.ok:
        logger.warning("Warehouse stock sync failed for %s: %s", box.box_code, result.error)
        return False

    logger.info("Warehouse stock synced: %s", box.box_code)
    return True


async def push_reconciliation_to_site(client_id, db: AsyncSession) -> bool:
    """Compute safe reconciliation snapshot for a client and push to irsway."""
    import uuid as _uuid
    from decimal import Decimal
    from sqlalchemy import func

    client = await get_active_client(db)
    if client is None:
        return False

    cp = (await db.execute(
        select(Counterparty).where(Counterparty.id == client_id)
    )).scalar_one_or_none()
    if not cp or not cp.code:
        return False

    from app.models.order import Order, OrderStatus
    from app.models.payment import Payment
    from app.models.payment_allocation import PaymentAllocation

    paid_sq = (
        select(
            PaymentAllocation.order_id,
            func.coalesce(func.sum(PaymentAllocation.amount_cny), Decimal("0")).label("paid_cny"),
        )
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .where(Payment.is_active == True)
        .group_by(PaymentAllocation.order_id)
        .subquery()
    )

    order_rows = (await db.execute(
        select(
            Order.id,
            Order.order_number,
            Order.order_date,
            Order.total_sale_cny,
            Order.payment_status,
            func.coalesce(paid_sq.c.paid_cny, Decimal("0")).label("paid_cny"),
        )
        .outerjoin(paid_sq, Order.id == paid_sq.c.order_id)
        .where(
            Order.client_id == client_id,
            Order.status != OrderStatus.cancelled,
            Order.excluded_from_accounting == False,
        )
        .order_by(Order.order_date.desc())
    )).all()

    # Загружаем платёжные аллокации для всех заказов клиента одним запросом
    order_ids = [r[0] for r in order_rows]
    alloc_detail_rows = []
    if order_ids:
        alloc_detail_rows = (await db.execute(
            select(
                PaymentAllocation.order_id,
                Payment.payment_date,
                PaymentAllocation.amount_cny,
            )
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .where(
                PaymentAllocation.order_id.in_(order_ids),
                Payment.is_active == True,
            )
            .order_by(PaymentAllocation.order_id, Payment.payment_date)
        )).all()

    # Группируем платежи по order_id
    from collections import defaultdict
    payments_by_order: dict = defaultdict(list)
    for alloc_order_id, payment_date, amount_cny in alloc_detail_rows:
        payments_by_order[alloc_order_id].append(
            PaymentEntryPayload(
                date=payment_date.isoformat() if payment_date else "",
                amount_cny=str((amount_cny or Decimal("0")).quantize(Decimal("0.01"))),
            )
        )

    rows = []
    total_revenue = Decimal("0")
    total_paid_d = Decimal("0")
    for r in order_rows:
        order_id, order_number, order_date, total_sale_cny, payment_status, paid_cny = r
        revenue = total_sale_cny or Decimal("0")
        paid = paid_cny or Decimal("0")
        remaining = max(revenue - paid, Decimal("0"))
        total_revenue += revenue
        total_paid_d += paid
        ps = payment_status.value if hasattr(payment_status, 'value') else str(payment_status or "unpaid")
        rows.append(ReconciliationRowPayload(
            order_number=order_number,
            order_date=order_date.isoformat() if order_date else None,
            total_sale_cny=str(revenue.quantize(Decimal("0.01"))),
            paid_cny=str(paid.quantize(Decimal("0.01"))),
            remaining=str(remaining.quantize(Decimal("0.01"))),
            payment_status=ps,
            payments=payments_by_order.get(order_id, []),
        ))

    balance = total_paid_d - total_revenue
    payload = ReconciliationPayload(
        client_code=cp.code.upper(),
        rows=rows,
        total_revenue=float(total_revenue),
        total_paid=float(total_paid_d),
        balance=float(balance),
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: client.push_reconciliation(payload))

    if not result.ok:
        logger.warning("Reconciliation push failed for %s: %s", cp.code, result.error)
        return False

    logger.info("Reconciliation pushed for %s: %d orders", cp.code, len(rows))
    return True


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
