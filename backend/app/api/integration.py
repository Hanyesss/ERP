import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.core.deps import require_roles, get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.business_type import BusinessType
from app.models.integration_settings import IntegrationSettings
from app.integrations.irsway_site.service import sync_order_to_site, push_status_to_site, get_active_client, INTEGRATION_NAME
from app.integrations.irsway_site.client import IrswayClient

router = APIRouter(prefix="/api/integration-settings", tags=["integration"])
orders_router = APIRouter(prefix="/api/orders", tags=["orders-sync"])

_SYNC_ROLES = ("manager", "accountant", "admin")


def _mask_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    if len(token) <= 4:
        return "x" * len(token)
    return "x" * (len(token) - 4) + token[-4:]


class IntegrationSettingsResponse(BaseModel):
    id: uuid.UUID
    integration_name: str
    base_url: Optional[str] = None
    api_token_masked: Optional[str] = None
    is_enabled: bool
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IntegrationSettingsUpdate(BaseModel):
    base_url: Optional[str] = None
    api_token: Optional[str] = None
    is_enabled: Optional[bool] = None


class TestConnectionBody(BaseModel):
    base_url: Optional[str] = None
    api_token: Optional[str] = None


class PushStatusBody(BaseModel):
    status: str
    comment: Optional[str] = None


async def _get_or_create_settings(db: AsyncSession) -> IntegrationSettings:
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == INTEGRATION_NAME)
    )).scalar_one_or_none()
    if not row:
        row = IntegrationSettings(
            id=uuid.uuid4(),
            integration_name=INTEGRATION_NAME,
        )
        db.add(row)
        await db.flush()
    return row


@router.get("", response_model=IntegrationSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    row = await _get_or_create_settings(db)
    await db.commit()
    return IntegrationSettingsResponse(
        id=row.id,
        integration_name=row.integration_name,
        base_url=row.base_url,
        api_token_masked=_mask_token(row.api_token),
        is_enabled=row.is_enabled,
        last_sync_at=row.last_sync_at,
        last_sync_status=row.last_sync_status,
        last_sync_error=row.last_sync_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.put("", response_model=IntegrationSettingsResponse)
async def update_settings(
    body: IntegrationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    row = await _get_or_create_settings(db)

    if body.base_url is not None:
        row.base_url = body.base_url
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled
    if body.api_token is not None:
        current_mask = _mask_token(row.api_token)
        if body.api_token != current_mask:
            row.api_token = body.api_token

    await db.commit()
    await db.refresh(row)

    return IntegrationSettingsResponse(
        id=row.id,
        integration_name=row.integration_name,
        base_url=row.base_url,
        api_token_masked=_mask_token(row.api_token),
        is_enabled=row.is_enabled,
        last_sync_at=row.last_sync_at,
        last_sync_status=row.last_sync_status,
        last_sync_error=row.last_sync_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/test")
async def test_connection(
    body: TestConnectionBody,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == INTEGRATION_NAME)
    )).scalar_one_or_none()

    base_url = body.base_url
    api_token = body.api_token

    if not base_url and row:
        base_url = row.base_url
    if not api_token and row:
        api_token = row.api_token
    elif api_token and row and api_token == _mask_token(row.api_token):
        api_token = row.api_token

    if not base_url or not api_token:
        raise HTTPException(422, "base_url and api_token are required")

    import asyncio
    client = IrswayClient(base_url=base_url, api_token=api_token)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, client.health)

    return {"ok": result.ok, "message": result.message}


@orders_router.post("/{order_id}/sync-to-site")
async def sync_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_SYNC_ROLES)),
):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    bt = (await db.execute(select(BusinessType).where(BusinessType.id == order.business_type_id))).scalar_one_or_none()
    if not bt or bt.code != "logistics":
        raise HTTPException(422, "Sync is only available for logistics orders")

    success, msg = await sync_order_to_site(order, db)
    await db.commit()

    return {
        "success": success,
        "message": msg,
        "sync_status": order.sync_status,
        "external_shipment_id": order.external_shipment_id,
        "external_shipment_number": order.external_shipment_number,
        "external_invoice_url": order.external_invoice_url,
        "external_tracking_url": order.external_tracking_url,
        "synced_at": order.synced_at,
    }


@orders_router.post("/{order_id}/push-status")
async def push_order_status(
    order_id: uuid.UUID,
    body: PushStatusBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_SYNC_ROLES)),
):
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")

    bt = (await db.execute(select(BusinessType).where(BusinessType.id == order.business_type_id))).scalar_one_or_none()
    if not bt or bt.code != "logistics":
        raise HTTPException(422, "Push status is only available for logistics orders")

    success, msg = await push_status_to_site(order, db, body.status, body.comment)
    await db.commit()

    return {"success": success, "message": msg}
