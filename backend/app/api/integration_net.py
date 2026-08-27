"""Входящий API для приложения NET (PARCEL): приём заказов и статусов груза.

Авторизация — только токен-хедер `Authorization: Token <NET_INBOUND_TOKEN>`
(НЕ cookie-JWT). Токен берётся из env NET_INBOUND_TOKEN (приоритет) или из
IntegrationSettings(integration_name="net_inbound").
"""
import os
import hmac
import logging
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.integration_settings import IntegrationSettings
from app.models.order import Order
from app.models.net_status_event import NetStatusEvent
from app.integrations.net_app.schemas import NetOrderIn, NetShipmentIn
from app.integrations.net_app.service import (
    upsert_net_order, upsert_net_shipment, NetUpsertError, INTEGRATION_NAME,
)

log = logging.getLogger("net_inbound")


async def require_net_token(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if not authorization or not authorization.startswith("Token "):
        raise HTTPException(401, "missing token")
    token = authorization.split(" ", 1)[1].strip()
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == INTEGRATION_NAME)
    )).scalar_one_or_none()
    expected = os.getenv("NET_INBOUND_TOKEN") or (row.api_token if row and row.is_enabled else None)
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "bad token")


router = APIRouter(
    prefix="/api/integration/net",
    tags=["net-inbound"],
    dependencies=[Depends(require_net_token)],
)


@router.post("/shipments")
async def receive_net_shipment(
    payload: NetShipmentIn,
    db: AsyncSession = Depends(get_db),
):
    """Приём агрегатной отправки от склада (wh.net-delivery.com) → один логистический заказ."""
    try:
        result = await upsert_net_shipment(db, payload)
    except NetUpsertError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # noqa: BLE001 — не отдаём 500 на штатных путях
        await db.rollback()
        log.exception("net shipment upsert failed: %s", e)
        raise HTTPException(422, "upsert failed")
    status_code = 201 if result.get("created") else 200
    return JSONResponse(status_code=status_code, content=result)


@router.post("/orders")
async def receive_net_order(
    payload: NetOrderIn,
    db: AsyncSession = Depends(get_db),
):
    """ОТКЛЮЧЕНО. Пер-посылочный приём был отладочным — заменён на /shipments
    (агрегатный заказ на уровне отправки). ERP пер-посылочные заказы не хранит."""
    raise HTTPException(
        410, "per-parcel intake retired; use POST /api/integration/net/shipments"
    )


@router.get("/orders/{external_ref}")
async def get_net_order(
    external_ref: str,
    db: AsyncSession = Depends(get_db),
):
    order = (await db.execute(
        select(Order).where(Order.external_ref == external_ref, Order.source == "net")
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "not found")
    events = (await db.execute(
        select(NetStatusEvent)
        .where(NetStatusEvent.order_id == order.id)
        .order_by(NetStatusEvent.occurred_at)
    )).scalars().all()
    return {
        "external_ref": order.external_ref,
        "order_number": order.order_number,
        "status": order.status.value if order.status else None,
        "cargo_status": order.cargo_status,
        "cargo_status_label": order.cargo_status_label,
        "cargo_status_at": order.cargo_status_at.isoformat() if order.cargo_status_at else None,
        "tracking_number": order.tracking_number,
        "events": [
            {
                "code": e.code, "label": e.label, "lifecycle": e.lifecycle,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in events
        ],
    }
