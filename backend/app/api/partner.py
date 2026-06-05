import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.counterparty import Counterparty, CounterpartyType
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.expense import Expense, LinkTypeEnum, ReimburseStatusEnum
from app.models.partner_payout import PartnerPayout
from app.models.company import Company
from app.models.audit_log import AuditActionEnum
from app.utils.audit import write_audit

router = APIRouter(tags=["partner"])

_ADMIN_ROLES = ("accountant", "admin")
_COMMISSION_CATEGORY_ID = uuid.UUID("c1000001-0000-0000-0000-000000000013")

# Orders are "client paid" when payment_status is paid or partial
_PAID_STATUSES = [PaymentStatus.paid, PaymentStatus.partial]


# ── helpers ────────────────────────────────────────────────────────────────────

def _share(order: Order) -> Decimal:
    """Partner share = (sale - cost) / 2 (may be negative)."""
    return ((order.total_sale_cny - order.total_cost_cny) / Decimal("2")).quantize(Decimal("0.01"))


async def _get_partner_counterparty(db: AsyncSession, user: User) -> Counterparty:
    if not user.partner_counterparty_id:
        raise HTTPException(403, "User is not linked to a partner counterparty")
    cp = (await db.execute(
        select(Counterparty).where(Counterparty.id == user.partner_counterparty_id)
    )).scalar_one_or_none()
    if not cp:
        raise HTTPException(404, "Partner counterparty not found")
    return cp


async def _partner_client_ids(db: AsyncSession, partner_cp_id: uuid.UUID) -> List[uuid.UUID]:
    rows = (await db.execute(
        select(Counterparty.id).where(
            Counterparty.partner_id == partner_cp_id,
            Counterparty.is_active == True,
        )
    )).all()
    return [r[0] for r in rows]


async def _partner_orders_query(client_ids: List[uuid.UUID],
                                date_from: Optional[date] = None,
                                date_to: Optional[date] = None):
    """Base select for paid, non-cancelled orders of the given clients."""
    q = select(Order).where(
        Order.client_id.in_(client_ids),
        Order.payment_status.in_(_PAID_STATUSES),
        Order.status != OrderStatus.cancelled,
    )
    if date_from:
        q = q.where(Order.order_date >= date_from)
    if date_to:
        q = q.where(Order.order_date <= date_to)
    return q


async def _total_accrued(db: AsyncSession, client_ids: List[uuid.UUID],
                         date_from: Optional[date] = None,
                         date_to: Optional[date] = None) -> Decimal:
    if not client_ids:
        return Decimal("0")
    q = await _partner_orders_query(client_ids, date_from, date_to)
    orders = (await db.execute(q)).scalars().all()
    return sum((_share(o) for o in orders), Decimal("0"))


async def _total_paid(db: AsyncSession, partner_cp_id: uuid.UUID) -> Decimal:
    """Sum of approved + paid payouts."""
    val = (await db.execute(
        select(func.coalesce(func.sum(PartnerPayout.amount), 0)).where(
            PartnerPayout.partner_counterparty_id == partner_cp_id,
            PartnerPayout.is_deleted == False,
            PartnerPayout.status.in_(["approved", "paid"]),
        )
    )).scalar_one()
    return Decimal(val)


# ── schemas ──────────────────────────────────────────────────────────────────

class PartnerClientItem(BaseModel):
    id: uuid.UUID
    name: str
    name_cn: Optional[str] = None
    code: Optional[str] = None


class PartnerSummary(BaseModel):
    partner_id: uuid.UUID
    partner_name: str
    clients: List[PartnerClientItem]
    total_accrued: Decimal
    total_paid: Decimal
    balance: Decimal


class PartnerOrderItem(BaseModel):
    id: uuid.UUID
    order_number: str
    client_id: uuid.UUID
    client_name: Optional[str] = None
    order_date: date
    status: str
    payment_status: str
    sale_cny: Decimal
    cost_cny: Decimal
    margin_cny: Decimal
    share_cny: Decimal


class PayoutRequestBody(BaseModel):
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    notes: Optional[str] = None


class PayoutItem(BaseModel):
    id: uuid.UUID
    partner_counterparty_id: uuid.UUID
    partner_name: Optional[str] = None
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    amount: Decimal
    status: str
    notes: Optional[str] = None
    expense_id: Optional[uuid.UUID] = None
    created_at: Optional[str] = None


class PayoutUpdateBody(BaseModel):
    status: str  # approved / rejected / paid


class AdminPartnerItem(BaseModel):
    partner_id: uuid.UUID
    partner_name: str
    total_accrued: Decimal
    total_paid: Decimal
    balance: Decimal


# ── partner self-service endpoints ─────────────────────────────────────────────

@router.get("/api/partner/summary", response_model=PartnerSummary)
async def partner_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("partner")),
):
    partner = await _get_partner_counterparty(db, current_user)
    client_ids = await _partner_client_ids(db, partner.id)

    clients = []
    if client_ids:
        rows = (await db.execute(
            select(Counterparty).where(Counterparty.id.in_(client_ids)).order_by(Counterparty.name)
        )).scalars().all()
        clients = [
            PartnerClientItem(id=c.id, name=c.name, name_cn=c.name_cn, code=c.code)
            for c in rows
        ]

    total_accrued = await _total_accrued(db, client_ids)
    total_paid = await _total_paid(db, partner.id)

    return PartnerSummary(
        partner_id=partner.id,
        partner_name=partner.name,
        clients=clients,
        total_accrued=total_accrued,
        total_paid=total_paid,
        balance=total_accrued - total_paid,
    )


@router.get("/api/partner/clients", response_model=List[PartnerClientItem])
async def partner_clients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("partner")),
):
    partner = await _get_partner_counterparty(db, current_user)
    rows = (await db.execute(
        select(Counterparty).where(
            Counterparty.partner_id == partner.id,
            Counterparty.is_active == True,
        ).order_by(Counterparty.name)
    )).scalars().all()
    return [PartnerClientItem(id=c.id, name=c.name, name_cn=c.name_cn, code=c.code) for c in rows]


@router.get("/api/partner/orders", response_model=List[PartnerOrderItem])
async def partner_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("partner")),
):
    partner = await _get_partner_counterparty(db, current_user)
    client_ids = await _partner_client_ids(db, partner.id)
    if not client_ids:
        return []

    ClientAlias = aliased(Counterparty)
    rows = (await db.execute(
        select(Order, ClientAlias.name.label("client_name"))
        .join(ClientAlias, Order.client_id == ClientAlias.id)
        .where(
            Order.client_id.in_(client_ids),
            Order.payment_status.in_(_PAID_STATUSES),
            Order.status != OrderStatus.cancelled,
        )
        .order_by(Order.order_date.desc())
    )).all()

    result = []
    for r in rows:
        o = r[0]
        margin = (o.total_sale_cny - o.total_cost_cny).quantize(Decimal("0.01"))
        result.append(PartnerOrderItem(
            id=o.id, order_number=o.order_number,
            client_id=o.client_id, client_name=r.client_name,
            order_date=o.order_date,
            status=o.status.value if hasattr(o.status, "value") else o.status,
            payment_status=o.payment_status.value if hasattr(o.payment_status, "value") else o.payment_status,
            sale_cny=o.total_sale_cny, cost_cny=o.total_cost_cny,
            margin_cny=margin, share_cny=_share(o),
        ))
    return result


@router.post("/api/partner/payout-request", response_model=PayoutItem, status_code=status.HTTP_201_CREATED)
async def partner_payout_request(
    body: PayoutRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("partner")),
):
    partner = await _get_partner_counterparty(db, current_user)
    client_ids = await _partner_client_ids(db, partner.id)

    amount = await _total_accrued(db, client_ids, body.period_from, body.period_to)
    # Subtract what's already been paid/approved so the partner requests only the remaining balance
    already = await _total_paid(db, partner.id)
    requestable = amount - already if (body.period_from is None and body.period_to is None) else amount

    if requestable <= 0:
        raise HTTPException(422, "Nothing to pay out for the selected period")

    company = (await db.execute(
        select(Company).where(Company.is_active == True).limit(1)
    )).scalar_one_or_none()
    if not company:
        raise HTTPException(400, "No active company found")

    # Create a reimbursement-style expense (commission to partner)
    desc = f"Выплата партнёру {partner.name}"
    if body.period_from or body.period_to:
        desc += f" ({body.period_from or '...'} — {body.period_to or '...'})"
    expense = Expense(
        id=uuid.uuid4(),
        company_id=company.id,
        expense_date=date.today(),
        category_id=_COMMISSION_CATEGORY_ID,
        currency="CNY",
        amount=requestable,
        rate_to_cny=Decimal("1"),
        amount_cny=requestable,
        link_type=LinkTypeEnum.none,
        is_reimbursement=True,
        reimburse_to_user_id=current_user.id,
        reimburse_status=ReimburseStatusEnum.pending,
        description=desc,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(expense)

    payout = PartnerPayout(
        id=uuid.uuid4(),
        partner_counterparty_id=partner.id,
        period_from=body.period_from,
        period_to=body.period_to,
        amount=requestable,
        status="pending",
        requested_by=current_user.id,
        notes=body.notes,
        expense_id=expense.id,
        is_deleted=False,
    )
    db.add(payout)
    await db.flush()
    await write_audit(db, current_user.id, "partner_payout", payout.id, AuditActionEnum.create,
                      {"amount": str(requestable), "expense_id": str(expense.id)})
    await db.commit()
    await db.refresh(payout)

    return PayoutItem(
        id=payout.id, partner_counterparty_id=payout.partner_counterparty_id,
        partner_name=partner.name,
        period_from=payout.period_from, period_to=payout.period_to,
        amount=payout.amount, status=payout.status, notes=payout.notes,
        expense_id=payout.expense_id,
        created_at=payout.created_at.isoformat() if payout.created_at else None,
    )


@router.get("/api/partner/payouts", response_model=List[PayoutItem])
async def partner_payouts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("partner")),
):
    partner = await _get_partner_counterparty(db, current_user)
    rows = (await db.execute(
        select(PartnerPayout).where(
            PartnerPayout.partner_counterparty_id == partner.id,
            PartnerPayout.is_deleted == False,
        ).order_by(PartnerPayout.created_at.desc())
    )).scalars().all()
    return [
        PayoutItem(
            id=p.id, partner_counterparty_id=p.partner_counterparty_id,
            partner_name=partner.name,
            period_from=p.period_from, period_to=p.period_to,
            amount=p.amount, status=p.status, notes=p.notes, expense_id=p.expense_id,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in rows
    ]


# ── admin / accountant endpoints ────────────────────────────────────────────────

@router.get("/api/admin/partners", response_model=List[AdminPartnerItem])
async def admin_partners(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ADMIN_ROLES)),
):
    partners = (await db.execute(
        select(Counterparty).where(
            Counterparty.type == CounterpartyType.partner,
            Counterparty.is_active == True,
        ).order_by(Counterparty.name)
    )).scalars().all()

    result = []
    for p in partners:
        client_ids = await _partner_client_ids(db, p.id)
        accrued = await _total_accrued(db, client_ids)
        paid = await _total_paid(db, p.id)
        result.append(AdminPartnerItem(
            partner_id=p.id, partner_name=p.name,
            total_accrued=accrued, total_paid=paid, balance=accrued - paid,
        ))
    return result


@router.get("/api/admin/partner-payouts", response_model=List[PayoutItem])
async def admin_partner_payouts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ADMIN_ROLES)),
):
    PartnerAlias = aliased(Counterparty)
    rows = (await db.execute(
        select(PartnerPayout, PartnerAlias.name.label("partner_name"))
        .join(PartnerAlias, PartnerPayout.partner_counterparty_id == PartnerAlias.id)
        .where(PartnerPayout.is_deleted == False)
        .order_by(PartnerPayout.created_at.desc())
    )).all()
    return [
        PayoutItem(
            id=r[0].id, partner_counterparty_id=r[0].partner_counterparty_id,
            partner_name=r.partner_name,
            period_from=r[0].period_from, period_to=r[0].period_to,
            amount=r[0].amount, status=r[0].status, notes=r[0].notes,
            expense_id=r[0].expense_id,
            created_at=r[0].created_at.isoformat() if r[0].created_at else None,
        )
        for r in rows
    ]


@router.patch("/api/admin/partner-payouts/{payout_id}", response_model=PayoutItem)
async def admin_update_partner_payout(
    payout_id: uuid.UUID,
    body: PayoutUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ADMIN_ROLES)),
):
    if body.status not in ("approved", "rejected", "paid"):
        raise HTTPException(422, "Invalid status")

    payout = (await db.execute(
        select(PartnerPayout).where(
            PartnerPayout.id == payout_id, PartnerPayout.is_deleted == False
        )
    )).scalar_one_or_none()
    if not payout:
        raise HTTPException(404, "Payout not found")

    payout.status = body.status
    payout.approved_by = current_user.id

    # Sync the linked expense reimbursement status
    if payout.expense_id:
        expense = (await db.execute(
            select(Expense).where(Expense.id == payout.expense_id)
        )).scalar_one_or_none()
        if expense:
            if body.status == "approved":
                expense.reimburse_status = ReimburseStatusEnum.approved
            elif body.status == "rejected":
                expense.reimburse_status = ReimburseStatusEnum.rejected
            elif body.status == "paid":
                expense.reimburse_status = ReimburseStatusEnum.paid
                expense.reimburse_paid_date = date.today()

    await write_audit(db, current_user.id, "partner_payout", payout.id, AuditActionEnum.update,
                      {"status": body.status})
    await db.commit()
    await db.refresh(payout)

    partner_name = (await db.execute(
        select(Counterparty.name).where(Counterparty.id == payout.partner_counterparty_id)
    )).scalar_one_or_none()

    return PayoutItem(
        id=payout.id, partner_counterparty_id=payout.partner_counterparty_id,
        partner_name=partner_name,
        period_from=payout.period_from, period_to=payout.period_to,
        amount=payout.amount, status=payout.status, notes=payout.notes,
        expense_id=payout.expense_id,
        created_at=payout.created_at.isoformat() if payout.created_at else None,
    )
