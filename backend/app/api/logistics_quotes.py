"""API сравнения предложений поставщиков по логистике."""
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased
from pydantic import BaseModel

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.logistics_quote import QuoteRequest, SupplierQuote, PriceUnitEnum
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.counterparty import Counterparty, CounterpartyType
from app.models.warehouse import Warehouse

router = APIRouter(prefix="/api/logistics-quotes", tags=["logistics-quotes"])

_ALLOWED = ("employee", "admin")


# ── Schemas ──────────────────────────────────────────────────────────────────
class QuoteRequestCreate(BaseModel):
    order_id: Optional[uuid.UUID] = None
    order_number: Optional[str] = None
    product_name: Optional[str] = None
    cargo_value: Optional[str] = None
    box: Optional[str] = None
    dimensions: Optional[str] = None
    volume_m3: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    destination: Optional[str] = None
    dispatch_place: Optional[str] = None
    client_price: Optional[Decimal] = None
    notes: Optional[str] = None


class QuoteRequestUpdate(BaseModel):
    order_number: Optional[str] = None
    product_name: Optional[str] = None
    cargo_value: Optional[str] = None
    box: Optional[str] = None
    dimensions: Optional[str] = None
    volume_m3: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    destination: Optional[str] = None
    dispatch_place: Optional[str] = None
    client_price: Optional[Decimal] = None
    notes: Optional[str] = None


class SupplierQuoteCreate(BaseModel):
    supplier_id: uuid.UUID
    price: Decimal
    price_unit: PriceUnitEnum = PriceUnitEnum.per_kg
    currency: str = "USD"
    delivery_days: Optional[str] = None
    insurance_pct: Optional[Decimal] = None
    notes: Optional[str] = None


class SupplierQuoteUpdate(BaseModel):
    price: Optional[Decimal] = None
    price_unit: Optional[PriceUnitEnum] = None
    currency: Optional[str] = None
    delivery_days: Optional[str] = None
    insurance_pct: Optional[Decimal] = None
    notes: Optional[str] = None


class SelectBody(BaseModel):
    quote_id: uuid.UUID


# ── Helpers ──────────────────────────────────────────────────────────────────
def _quote_dict(q: SupplierQuote, supplier_name: str, creator_name: str) -> dict:
    # Итоговая стоимость = цена × (вес или объём)
    return {
        "id": str(q.id),
        "supplier_id": str(q.supplier_id),
        "supplier_name": supplier_name,
        "price": q.price,
        "price_unit": q.price_unit.value if hasattr(q.price_unit, "value") else q.price_unit,
        "currency": q.currency,
        "delivery_days": q.delivery_days,
        "insurance_pct": q.insurance_pct,
        "notes": q.notes,
        "created_by_name": creator_name,
    }


async def _load_request(db: AsyncSession, req: QuoteRequest) -> dict:
    Creator = aliased(User)
    Selector = aliased(User)
    row = (await db.execute(
        select(QuoteRequest, Creator.full_name, Selector.full_name)
        .outerjoin(Creator, QuoteRequest.created_by == Creator.id)
        .outerjoin(Selector, QuoteRequest.selected_by == Selector.id)
        .where(QuoteRequest.id == req.id)
    )).first()
    r, creator_name, selector_name = row

    quotes_rows = (await db.execute(
        select(SupplierQuote, Counterparty.name, User.full_name)
        .join(Counterparty, SupplierQuote.supplier_id == Counterparty.id)
        .outerjoin(User, SupplierQuote.created_by == User.id)
        .where(SupplierQuote.request_id == r.id)
        .order_by(SupplierQuote.created_at)
    )).all()
    quotes = [_quote_dict(q, sname, cname or "") for q, sname, cname in quotes_rows]

    total = None
    if r.selected_quote_id:
        sel = next((q for q in quotes if q["id"] == str(r.selected_quote_id)), None)
        if sel:
            base = r.weight_kg if sel["price_unit"] == "per_kg" else r.volume_m3
            if base is not None:
                total = (Decimal(str(sel["price"])) * Decimal(str(base))).quantize(Decimal("0.01"))

    density = None
    if r.weight_kg and r.volume_m3 and r.volume_m3 != 0:
        density = (Decimal(str(r.weight_kg)) / Decimal(str(r.volume_m3))).quantize(Decimal("0.01"))

    return {
        "id": str(r.id),
        "order_id": str(r.order_id) if r.order_id else None,
        "order_number": r.order_number,
        "product_name": r.product_name,
        "cargo_value": r.cargo_value,
        "box": r.box,
        "dimensions": r.dimensions,
        "volume_m3": r.volume_m3,
        "weight_kg": r.weight_kg,
        "density": density,
        "destination": r.destination,
        "dispatch_place": r.dispatch_place,
        "client_price": r.client_price,
        "notes": r.notes,
        "selected_quote_id": str(r.selected_quote_id) if r.selected_quote_id else None,
        "selected_by_name": selector_name,
        "selected_at": r.selected_at.isoformat() if r.selected_at else None,
        "created_by_name": creator_name,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "quotes": quotes,
        "selected_total": total,
    }


# ── Requests ─────────────────────────────────────────────────────────────────
@router.get("/pending-count")
async def pending_count(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    """Количество необработанных сравнений (без выбранного поставщика)."""
    cnt = (await db.execute(
        select(func.count(QuoteRequest.id)).where(
            QuoteRequest.is_active == True,
            QuoteRequest.selected_quote_id.is_(None),
        )
    )).scalar_one()
    return {"count": cnt or 0}


@router.get("/requests")
async def list_requests(
    search: Optional[str] = Query(None),
    order_id: Optional[uuid.UUID] = Query(None),
    only_unselected: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    stmt = select(QuoteRequest).where(QuoteRequest.is_active == True)
    if order_id:
        stmt = stmt.where(QuoteRequest.order_id == order_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (QuoteRequest.order_number.ilike(like)) | (QuoteRequest.product_name.ilike(like))
        )
    if only_unselected:
        stmt = stmt.where(QuoteRequest.selected_quote_id.is_(None))
    stmt = stmt.order_by(QuoteRequest.created_at.desc())
    reqs = (await db.execute(stmt)).scalars().all()
    return [await _load_request(db, r) for r in reqs]


@router.post("/requests")
async def create_request(
    body: QuoteRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    data = body.model_dump()

    # Автозаполнение из логистического заказа
    if body.order_id:
        order = (await db.execute(select(Order).where(Order.id == body.order_id))).scalar_one_or_none()
        if not order:
            raise HTTPException(422, "Order not found")
        if not data.get("order_number"):
            data["order_number"] = order.order_number
        if not data.get("destination"):
            data["destination"] = order.destination
        if not data.get("dispatch_place") and order.warehouse_id:
            wh = (await db.execute(select(Warehouse).where(Warehouse.id == order.warehouse_id))).scalar_one_or_none()
            if wh:
                data["dispatch_place"] = wh.name
        # Вес/объём/товар из позиций заказа
        agg = (await db.execute(
            select(
                func.coalesce(func.sum(OrderItem.weight_kg), None),
                func.coalesce(func.sum(OrderItem.volume_m3), None),
            ).where(OrderItem.order_id == order.id)
        )).first()
        if agg:
            if data.get("weight_kg") is None:
                data["weight_kg"] = agg[0]
            if data.get("volume_m3") is None:
                data["volume_m3"] = agg[1]
        if not data.get("product_name"):
            names = (await db.execute(
                select(OrderItem.name).where(OrderItem.order_id == order.id)
            )).scalars().all()
            if names:
                data["product_name"] = ", ".join([n for n in names if n][:5])

    req = QuoteRequest(id=uuid.uuid4(), created_by=current_user.id, **data)
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return await _load_request(db, req)


@router.patch("/requests/{request_id}")
async def update_request(
    request_id: uuid.UUID,
    body: QuoteRequestUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    req = (await db.execute(select(QuoteRequest).where(QuoteRequest.id == request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Request not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(req, field, value)
    await db.commit()
    await db.refresh(req)
    return await _load_request(db, req)


@router.delete("/requests/{request_id}", status_code=204)
async def delete_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    req = (await db.execute(select(QuoteRequest).where(QuoteRequest.id == request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Request not found")
    req.is_active = False
    await db.commit()


# ── Quotes ───────────────────────────────────────────────────────────────────
@router.post("/requests/{request_id}/quotes")
async def add_quote(
    request_id: uuid.UUID,
    body: SupplierQuoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    req = (await db.execute(select(QuoteRequest).where(QuoteRequest.id == request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Request not found")
    supplier = (await db.execute(select(Counterparty).where(Counterparty.id == body.supplier_id))).scalar_one_or_none()
    if not supplier or supplier.type not in (CounterpartyType.supplier, CounterpartyType.both):
        raise HTTPException(422, "Supplier must be a counterparty of type 'supplier' or 'both'")
    q = SupplierQuote(id=uuid.uuid4(), request_id=request_id, created_by=current_user.id, **body.model_dump())
    db.add(q)
    await db.commit()
    await db.refresh(req)
    return await _load_request(db, req)


@router.patch("/quotes/{quote_id}")
async def update_quote(
    quote_id: uuid.UUID,
    body: SupplierQuoteUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    q = (await db.execute(select(SupplierQuote).where(SupplierQuote.id == quote_id))).scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Quote not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(q, field, value)
    await db.commit()
    req = (await db.execute(select(QuoteRequest).where(QuoteRequest.id == q.request_id))).scalar_one()
    return await _load_request(db, req)


@router.delete("/quotes/{quote_id}", status_code=204)
async def delete_quote(
    quote_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    q = (await db.execute(select(SupplierQuote).where(SupplierQuote.id == quote_id))).scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Quote not found")
    # Снять выбор, если удаляем выбранное предложение
    req = (await db.execute(select(QuoteRequest).where(QuoteRequest.id == q.request_id))).scalar_one()
    if req.selected_quote_id == q.id:
        req.selected_quote_id = None
        req.selected_by = None
        req.selected_at = None
    await db.delete(q)
    await db.commit()


# ── Выбор поставщика ─────────────────────────────────────────────────────────
@router.post("/requests/{request_id}/select")
async def select_quote(
    request_id: uuid.UUID,
    body: SelectBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    req = (await db.execute(select(QuoteRequest).where(QuoteRequest.id == request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Request not found")
    q = (await db.execute(
        select(SupplierQuote).where(SupplierQuote.id == body.quote_id, SupplierQuote.request_id == request_id)
    )).scalar_one_or_none()
    if not q:
        raise HTTPException(422, "Quote not found for this request")
    req.selected_quote_id = q.id
    req.selected_by = current_user.id
    req.selected_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(req)
    return await _load_request(db, req)


@router.post("/requests/{request_id}/unselect")
async def unselect_quote(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    req = (await db.execute(select(QuoteRequest).where(QuoteRequest.id == request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Request not found")
    req.selected_quote_id = None
    req.selected_by = None
    req.selected_at = None
    await db.commit()
    await db.refresh(req)
    return await _load_request(db, req)
