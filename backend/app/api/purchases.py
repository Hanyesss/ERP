import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database import get_db
from app.core.deps import require_roles
from app.models.user import User
from app.models.purchase import Purchase, PurchasePaymentStatus
from app.models.purchase_item import PurchaseItem
from app.models.order_item import OrderItem
from app.models.order import Order
from app.models.counterparty import Counterparty, CounterpartyType
from app.models.company import Company
from app.models.audit_log import AuditActionEnum
from app.schemas.purchase import (
    PurchaseCreate, PurchaseUpdate, PurchaseResponse, PurchaseItemResponse,
    PurchaseListItem, PurchaseListResponse,
)
from app.utils.audit import write_audit

router = APIRouter(prefix="/api/purchases", tags=["purchases"])

_ALLOWED = ("purchaser", "accountant", "admin")


async def _get_default_company(db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.is_active == True).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(400, "No active company found")
    return company


async def _load_purchase(db: AsyncSession, purchase_id: uuid.UUID) -> PurchaseResponse:
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        raise HTTPException(404, "Purchase not found")

    supplier = (await db.execute(
        select(Counterparty).where(Counterparty.id == pur.supplier_id)
    )).scalar_one_or_none()

    items_stmt = (
        select(PurchaseItem, OrderItem.name.label("item_name"), Order.order_number)
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(PurchaseItem.purchase_id == purchase_id)
    )
    item_rows = (await db.execute(items_stmt)).all()

    items = [
        PurchaseItemResponse(
            id=r[0].id, order_item_id=r[0].order_item_id,
            order_item_name=r[1], order_number=r[2],
            quantity=r[0].quantity, cost_price=r[0].cost_price, cost_amount=r[0].cost_amount,
        )
        for r in item_rows
    ]

    return PurchaseResponse(
        id=pur.id, purchase_number=pur.purchase_number,
        supplier_id=pur.supplier_id, supplier_name=supplier.name if supplier else "",
        purchase_date=pur.purchase_date, currency=pur.currency,
        total_amount=pur.total_amount, rate_to_cny=pur.rate_to_cny,
        total_amount_cny=pur.total_amount_cny,
        payment_status=pur.payment_status,
        notes=pur.notes, created_at=pur.created_at,
        items=items,
    )


async def _recalc_order_cost(db: AsyncSession, order_id: uuid.UUID) -> None:
    """Update order.total_cost_cny from purchase_items linked to this order."""
    result = await db.execute(
        select(func.sum(PurchaseItem.cost_amount))
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
        .where(OrderItem.order_id == order_id, Purchase.is_deleted == False)
    )
    total_cost = result.scalar_one() or Decimal("0")
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if order:
        order.total_cost_cny = total_cost


@router.get("", response_model=PurchaseListResponse)
async def list_purchases(
    search: Optional[str] = Query(None),
    supplier_id: Optional[uuid.UUID] = Query(None),
    payment_status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    stmt = (
        select(
            Purchase,
            Counterparty.name.label("supplier_name"),
            func.count(PurchaseItem.id).label("items_count"),
        )
        .join(Counterparty, Purchase.supplier_id == Counterparty.id)
        .outerjoin(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
        .where(Purchase.is_deleted == False)
        .group_by(Purchase.id, Counterparty.name)
    )

    if search:
        stmt = stmt.where(Purchase.purchase_number.ilike(f"%{search}%"))
    if supplier_id:
        stmt = stmt.where(Purchase.supplier_id == supplier_id)
    if payment_status:
        stmt = stmt.where(Purchase.payment_status == payment_status)
    if date_from:
        stmt = stmt.where(Purchase.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(Purchase.purchase_date <= date_to)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Purchase.purchase_date.desc(), Purchase.purchase_number.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    items = [
        PurchaseListItem(
            id=r[0].id, purchase_number=r[0].purchase_number,
            supplier_id=r[0].supplier_id, supplier_name=r[1],
            purchase_date=r[0].purchase_date, currency=r[0].currency,
            total_amount=r[0].total_amount, total_amount_cny=r[0].total_amount_cny,
            payment_status=r[0].payment_status, items_count=r[2],
        )
        for r in rows
    ]

    page_total_cny = sum(r[0].total_amount_cny for r in rows) or Decimal("0")

    return PurchaseListResponse(
        items=items, total=total, page=page, page_size=page_size,
        page_total_cny=page_total_cny,
    )


@router.get("/next-number")
async def get_next_purchase_number(
    purchase_date: date = Query(alias="date"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    prefix = f"PUR-{purchase_date.strftime('%Y%m%d')}-"
    count = (await db.execute(
        select(func.count(Purchase.id)).where(Purchase.purchase_number.like(f"{prefix}%"))
    )).scalar_one()
    return {"purchase_number": f"{prefix}{count + 1:04d}"}


@router.get("/{purchase_id}", response_model=PurchaseResponse)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ALLOWED)),
):
    return await _load_purchase(db, purchase_id)


@router.post("", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    body: PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    company = await _get_default_company(db)

    supplier = (await db.execute(
        select(Counterparty).where(Counterparty.id == body.supplier_id)
    )).scalar_one_or_none()
    if not supplier or supplier.type not in (CounterpartyType.supplier, CounterpartyType.both):
        raise HTTPException(422, "Supplier must be counterparty of type 'supplier' or 'both'")

    # Auto-generate purchase number if not provided
    purchase_number = body.purchase_number
    if not purchase_number:
        prefix = f"PUR-{body.purchase_date.strftime('%Y%m%d')}-"
        count = (await db.execute(
            select(func.count(Purchase.id)).where(Purchase.purchase_number.like(f"{prefix}%"))
        )).scalar_one()
        purchase_number = f"{prefix}{count + 1:04d}"

    # Validate items and check available quantities
    affected_order_ids: set[uuid.UUID] = set()
    validated_items = []

    for item_data in body.items:
        oi = (await db.execute(
            select(OrderItem).where(OrderItem.id == item_data.order_item_id)
        )).scalar_one_or_none()
        if not oi:
            raise HTTPException(422, f"OrderItem {item_data.order_item_id} not found")
        if oi.quantity is None:
            raise HTTPException(422, f"OrderItem {item_data.order_item_id} has no quantity")

        already = (await db.execute(
            select(func.sum(PurchaseItem.quantity))
            .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
            .where(PurchaseItem.order_item_id == item_data.order_item_id, Purchase.is_deleted == False)
        )).scalar_one() or Decimal("0")

        available = oi.quantity - already
        if item_data.quantity > available:
            raise HTTPException(
                422,
                f"Item '{oi.name}': requested {item_data.quantity}, available {available}"
            )

        validated_items.append((oi, item_data))
        affected_order_ids.add(oi.order_id)

    # Calculate totals
    total_amount = sum(i.quantity * i.cost_price for _, i in validated_items) if validated_items else Decimal("0")
    rate = body.rate_to_cny
    total_amount_cny = (total_amount * rate).quantize(Decimal("0.01"))

    purchase = Purchase(
        id=uuid.uuid4(),
        purchase_number=purchase_number,
        company_id=company.id,
        supplier_id=body.supplier_id,
        purchase_date=body.purchase_date,
        currency=body.currency,
        total_amount=total_amount.quantize(Decimal("0.01")),
        rate_to_cny=rate,
        total_amount_cny=total_amount_cny,
        payment_status=PurchasePaymentStatus.unpaid,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(purchase)
    await db.flush()

    for oi, item_data in validated_items:
        # For cost_amount, use purchase currency rate to CNY
        cost_amount_cny = (item_data.quantity * item_data.cost_price * rate).quantize(Decimal("0.01"))
        db.add(PurchaseItem(
            id=uuid.uuid4(),
            purchase_id=purchase.id,
            order_item_id=item_data.order_item_id,
            quantity=item_data.quantity,
            cost_price=item_data.cost_price,
            cost_amount=cost_amount_cny,
        ))

    await db.flush()

    # Update total_cost_cny on affected orders
    for order_id in affected_order_ids:
        await _recalc_order_cost(db, order_id)

    await write_audit(db, current_user.id, "purchase", purchase.id, AuditActionEnum.create,
                      {"purchase_number": purchase_number, "total_cny": str(total_amount_cny)})
    await db.commit()
    return await _load_purchase(db, purchase.id)


@router.patch("/{purchase_id}", response_model=PurchaseResponse)
async def update_purchase(
    purchase_id: uuid.UUID,
    body: PurchaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        raise HTTPException(404, "Purchase not found")
    if pur.payment_status == PurchasePaymentStatus.paid:
        raise HTTPException(422, "Cannot modify a fully paid purchase")

    update_data = body.model_dump(exclude_unset=True)
    items_data = update_data.pop("items", None)

    for field, value in update_data.items():
        setattr(pur, field, value)

    affected_order_ids: set[uuid.UUID] = set()

    if items_data is not None:
        # Delete existing items, collect affected orders
        existing_pi = (await db.execute(
            select(PurchaseItem, OrderItem.order_id)
            .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
            .where(PurchaseItem.purchase_id == purchase_id)
        )).all()
        for _, order_id in existing_pi:
            affected_order_ids.add(order_id)

        await db.execute(delete(PurchaseItem).where(PurchaseItem.purchase_id == purchase_id))
        await db.flush()

        from app.schemas.purchase import PurchaseItemCreate
        validated_items = []
        for item_data in [PurchaseItemCreate(**i) if isinstance(i, dict) else i for i in items_data]:
            oi = (await db.execute(
                select(OrderItem).where(OrderItem.id == item_data.order_item_id)
            )).scalar_one_or_none()
            if not oi:
                raise HTTPException(422, f"OrderItem {item_data.order_item_id} not found")
            validated_items.append((oi, item_data))
            affected_order_ids.add(oi.order_id)

        rate = update_data.get("rate_to_cny", pur.rate_to_cny)
        total_amount = sum(i.quantity * i.cost_price for _, i in validated_items) if validated_items else Decimal("0")
        pur.total_amount = total_amount.quantize(Decimal("0.01"))
        pur.total_amount_cny = (total_amount * rate).quantize(Decimal("0.01"))

        for oi, item_data in validated_items:
            cost_amount_cny = (item_data.quantity * item_data.cost_price * rate).quantize(Decimal("0.01"))
            db.add(PurchaseItem(
                id=uuid.uuid4(),
                purchase_id=purchase_id,
                order_item_id=item_data.order_item_id,
                quantity=item_data.quantity,
                cost_price=item_data.cost_price,
                cost_amount=cost_amount_cny,
            ))

        await db.flush()

    for order_id in affected_order_ids:
        await _recalc_order_cost(db, order_id)

    await write_audit(db, current_user.id, "purchase", pur.id, AuditActionEnum.update,
                      {"purchase_number": pur.purchase_number})
    await db.commit()
    return await _load_purchase(db, pur.id)


@router.delete("/{purchase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALLOWED)),
):
    pur = (await db.execute(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.is_deleted == False)
    )).scalar_one_or_none()
    if not pur:
        raise HTTPException(404, "Purchase not found")
    if pur.payment_status == PurchasePaymentStatus.paid:
        raise HTTPException(422, "Cannot delete a fully paid purchase")

    # Collect affected orders before soft-delete
    existing_pi = (await db.execute(
        select(PurchaseItem, OrderItem.order_id)
        .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
        .where(PurchaseItem.purchase_id == purchase_id)
    )).all()
    affected_order_ids = {row[1] for row in existing_pi}

    pur.is_deleted = True
    await db.flush()

    for order_id in affected_order_ids:
        await _recalc_order_cost(db, order_id)

    await write_audit(db, current_user.id, "purchase", pur.id, AuditActionEnum.delete,
                      {"purchase_number": pur.purchase_number})
    await db.commit()
