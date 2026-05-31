import uuid
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from pydantic import BaseModel

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.cash_register import CashRegister, CashTransaction

router = APIRouter(prefix="/api/cash-registers", tags=["cash-registers"])

_EDIT_ROLES = require_roles("accountant", "admin")


class CashRegisterCreate(BaseModel):
    name: str
    currency: str
    notes: Optional[str] = None


class CashRegisterUpdate(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class CashRegisterResponse(BaseModel):
    id: uuid.UUID
    name: str
    currency: str
    notes: Optional[str] = None
    is_active: bool
    balance: Decimal


class CashTransactionResponse(BaseModel):
    id: uuid.UUID
    payment_id: Optional[uuid.UUID] = None
    direction: str
    amount: Decimal
    balance_after: Decimal
    notes: Optional[str] = None
    created_by_name: str
    created_at: str


async def _get_balance(db: AsyncSession, register_id: uuid.UUID) -> Decimal:
    result = await db.execute(
        select(func.coalesce(
            func.sum(
                case(
                    (CashTransaction.direction == "in", CashTransaction.amount),
                    else_=-CashTransaction.amount,
                )
            ),
            Decimal("0"),
        )).where(CashTransaction.cash_register_id == register_id)
    )
    return result.scalar_one() or Decimal("0")


@router.get("", response_model=List[CashRegisterResponse])
async def list_registers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CashRegister).where(CashRegister.is_active == True).order_by(CashRegister.name)
    )
    registers = result.scalars().all()
    items = []
    for r in registers:
        balance = await _get_balance(db, r.id)
        items.append(CashRegisterResponse(
            id=r.id, name=r.name, currency=r.currency,
            notes=r.notes, is_active=r.is_active, balance=balance,
        ))
    return items


@router.post("", response_model=CashRegisterResponse)
async def create_register(
    body: CashRegisterCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_EDIT_ROLES),
):
    reg = CashRegister(id=uuid.uuid4(), name=body.name, currency=body.currency, notes=body.notes)
    db.add(reg)
    await db.commit()
    await db.refresh(reg)
    return CashRegisterResponse(id=reg.id, name=reg.name, currency=reg.currency,
                                notes=reg.notes, is_active=reg.is_active, balance=Decimal("0"))


@router.patch("/{register_id}", response_model=CashRegisterResponse)
async def update_register(
    register_id: uuid.UUID,
    body: CashRegisterUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_EDIT_ROLES),
):
    reg = (await db.execute(select(CashRegister).where(CashRegister.id == register_id))).scalar_one_or_none()
    if not reg:
        raise HTTPException(404, "Cash register not found")
    if body.name is not None:
        reg.name = body.name
    if body.currency is not None:
        reg.currency = body.currency
    if body.notes is not None:
        reg.notes = body.notes
    if body.is_active is not None:
        reg.is_active = body.is_active
    await db.commit()
    await db.refresh(reg)
    balance = await _get_balance(db, reg.id)
    return CashRegisterResponse(id=reg.id, name=reg.name, currency=reg.currency,
                                notes=reg.notes, is_active=reg.is_active, balance=balance)


@router.get("/{register_id}/transactions", response_model=List[CashTransactionResponse])
async def get_transactions(
    register_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reg = (await db.execute(select(CashRegister).where(CashRegister.id == register_id))).scalar_one_or_none()
    if not reg:
        raise HTTPException(404, "Cash register not found")

    from app.models.user import User as UserModel
    txs_result = await db.execute(
        select(CashTransaction)
        .where(CashTransaction.cash_register_id == register_id)
        .order_by(CashTransaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    txs = txs_result.scalars().all()

    user_ids = list({t.created_by for t in txs})
    users_map = {}
    if user_ids:
        users_res = await db.execute(select(UserModel).where(UserModel.id.in_(user_ids)))
        users_map = {u.id: u.full_name for u in users_res.scalars().all()}

    return [
        CashTransactionResponse(
            id=t.id,
            payment_id=t.payment_id,
            direction=t.direction,
            amount=t.amount,
            balance_after=t.balance_after,
            notes=t.notes,
            created_by_name=users_map.get(t.created_by, ""),
            created_at=t.created_at.isoformat(),
        )
        for t in txs
    ]
