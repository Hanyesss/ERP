import uuid
from datetime import datetime, timezone, date as date_type
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
from app.models.cash_transfer import CashTransfer
from app.models.audit_log import AuditActionEnum
from app.utils.audit import write_audit

router = APIRouter(prefix="/api/cash-registers", tags=["cash-registers"])

_EDIT_ROLES = require_roles("accountant", "admin")


class CashRegisterCreate(BaseModel):
    name: str
    currency: str
    notes: Optional[str] = None
    initial_balance: Decimal = Decimal("0")


class CashRegisterUpdate(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    initial_balance: Optional[Decimal] = None   # только admin


class CashRegisterResponse(BaseModel):
    id: uuid.UUID
    name: str
    currency: str
    notes: Optional[str] = None
    is_active: bool
    balance: Decimal
    initial_balance: Decimal


class CashTransactionResponse(BaseModel):
    id: uuid.UUID
    payment_id: Optional[uuid.UUID] = None
    direction: str
    amount: Decimal
    balance_after: Decimal
    operation_type: Optional[str] = None   # системный ключ (переводится по языку)
    notes: Optional[str] = None            # пользовательский текст (не переводится)
    is_active: bool
    created_by_name: str
    created_at: str


async def _get_balance(db: AsyncSession, register_id: uuid.UUID) -> Decimal:
    """Баланс = initial_balance + SUM(активных транзакций)."""
    reg = (await db.execute(
        select(CashRegister.initial_balance).where(CashRegister.id == register_id)
    )).scalar_one_or_none()
    initial = reg if reg is not None else Decimal("0")

    result = await db.execute(
        select(func.coalesce(
            func.sum(
                case(
                    (CashTransaction.direction == "in", CashTransaction.amount),
                    else_=-CashTransaction.amount,
                )
            ),
            Decimal("0"),
        )).where(
            CashTransaction.cash_register_id == register_id,
            CashTransaction.is_active == True,
        )
    )
    tx_sum = result.scalar_one() or Decimal("0")
    return initial + tx_sum


@router.get("", response_model=List[CashRegisterResponse])
async def list_registers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    registers = (await db.execute(
        select(CashRegister).where(CashRegister.is_active == True).order_by(CashRegister.name)
    )).scalars().all()

    # Суммируем только активные транзакции
    balances_result = await db.execute(
        select(
            CashTransaction.cash_register_id,
            func.coalesce(func.sum(case(
                (CashTransaction.direction == "in", CashTransaction.amount),
                else_=-CashTransaction.amount,
            )), Decimal("0")).label("tx_sum"),
        ).where(CashTransaction.is_active == True)
        .group_by(CashTransaction.cash_register_id)
    )
    tx_sums = {row[0]: row[1] for row in balances_result.all()}

    return [
        CashRegisterResponse(
            id=r.id, name=r.name, currency=r.currency,
            notes=r.notes, is_active=r.is_active,
            initial_balance=r.initial_balance,
            balance=r.initial_balance + tx_sums.get(r.id, Decimal("0")),
        )
        for r in registers
    ]


@router.post("", response_model=CashRegisterResponse)
async def create_register(
    body: CashRegisterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_EDIT_ROLES),
):
    reg = CashRegister(
        id=uuid.uuid4(),
        name=body.name,
        currency=body.currency,
        notes=body.notes,
        initial_balance=body.initial_balance,
    )
    db.add(reg)
    await db.flush()
    await write_audit(db, current_user.id, "cash_register", reg.id, AuditActionEnum.create,
                      {"name": body.name, "currency": body.currency,
                       "initial_balance": str(body.initial_balance)})
    await db.commit()
    await db.refresh(reg)
    return CashRegisterResponse(
        id=reg.id, name=reg.name, currency=reg.currency,
        notes=reg.notes, is_active=reg.is_active,
        initial_balance=reg.initial_balance,
        balance=reg.initial_balance,
    )


@router.patch("/{register_id}", response_model=CashRegisterResponse)
async def update_register(
    register_id: uuid.UUID,
    body: CashRegisterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_EDIT_ROLES),
):
    reg = (await db.execute(select(CashRegister).where(CashRegister.id == register_id))).scalar_one_or_none()
    if not reg:
        raise HTTPException(404, "Cash register not found")

    changes: dict = {}

    if body.name is not None:
        reg.name = body.name
    if body.currency is not None:
        reg.currency = body.currency
    if body.notes is not None:
        reg.notes = body.notes
    if body.is_active is not None:
        reg.is_active = body.is_active

    # initial_balance — только admin, с аудитом
    if body.initial_balance is not None:
        if not current_user.has_role("admin"):
            raise HTTPException(403, "Только admin может менять начальный баланс кассы")
        old_initial = reg.initial_balance
        reg.initial_balance = body.initial_balance
        changes["initial_balance"] = {"old": str(old_initial), "new": str(body.initial_balance)}

    await write_audit(db, current_user.id, "cash_register", reg.id, AuditActionEnum.update, changes or None)
    await db.commit()
    await db.refresh(reg)
    balance = await _get_balance(db, reg.id)
    return CashRegisterResponse(
        id=reg.id, name=reg.name, currency=reg.currency,
        notes=reg.notes, is_active=reg.is_active,
        initial_balance=reg.initial_balance, balance=balance,
    )


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
            operation_type=t.operation_type,
            notes=t.notes,
            is_active=t.is_active,
            created_by_name=users_map.get(t.created_by, ""),
            created_at=t.created_at.isoformat(),
        )
        for t in txs
    ]


# ── Transfers ────────────────────────────────────────────────────────────────

class TransferCreate(BaseModel):
    from_register_id: uuid.UUID
    to_register_id: uuid.UUID
    from_amount: Decimal
    to_amount: Decimal
    exchange_rate: Decimal = Decimal("1")
    transfer_date: date_type
    notes: Optional[str] = None


class TransferResponse(BaseModel):
    id: uuid.UUID
    from_register_id: uuid.UUID
    from_register_name: str
    from_currency: str
    to_register_id: uuid.UUID
    to_register_name: str
    to_currency: str
    from_amount: Decimal
    to_amount: Decimal
    exchange_rate: Decimal
    transfer_date: str
    notes: Optional[str] = None
    created_by_name: str
    created_at: str


@router.post("/transfer", response_model=TransferResponse)
async def create_transfer(
    body: TransferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.from_register_id == body.to_register_id:
        raise HTTPException(422, "Нельзя переводить в ту же кассу")

    from_reg = (await db.execute(select(CashRegister).where(CashRegister.id == body.from_register_id, CashRegister.is_active == True))).scalar_one_or_none()
    to_reg   = (await db.execute(select(CashRegister).where(CashRegister.id == body.to_register_id,   CashRegister.is_active == True))).scalar_one_or_none()
    if not from_reg:
        raise HTTPException(404, "Касса-отправитель не найдена")
    if not to_reg:
        raise HTTPException(404, "Касса-получатель не найдена")

    now = datetime.now(timezone.utc)

    transfer = CashTransfer(
        id=uuid.uuid4(),
        from_register_id=body.from_register_id,
        to_register_id=body.to_register_id,
        from_amount=body.from_amount,
        to_amount=body.to_amount,
        exchange_rate=body.exchange_rate,
        transfer_date=body.transfer_date,
        notes=body.notes,
        created_by=current_user.id,
        created_at=now,
    )
    db.add(transfer)
    await db.flush()

    # Транзакция списания
    from_balance = await _get_balance(db, body.from_register_id)
    out_tx = CashTransaction(
        id=uuid.uuid4(),
        cash_register_id=body.from_register_id,
        direction="out",
        amount=body.from_amount,
        balance_after=from_balance - body.from_amount,
        operation_type="transfer_out",
        notes=f"{to_reg.name}" + (f": {body.notes}" if body.notes else ""),
        created_by=current_user.id,
        created_at=now,
    )
    db.add(out_tx)

    # Транзакция зачисления
    to_balance = await _get_balance(db, body.to_register_id)
    in_tx = CashTransaction(
        id=uuid.uuid4(),
        cash_register_id=body.to_register_id,
        direction="in",
        amount=body.to_amount,
        balance_after=to_balance + body.to_amount,
        operation_type="transfer_in",
        notes=f"{from_reg.name}" + (f": {body.notes}" if body.notes else ""),
        created_by=current_user.id,
        created_at=now,
    )
    db.add(in_tx)
    await db.flush()

    # Аудит перевода
    await write_audit(db, current_user.id, "cash_transfer", transfer.id, AuditActionEnum.create, {
        "from_register": from_reg.name, "from_currency": from_reg.currency,
        "from_amount": str(body.from_amount),
        "to_register": to_reg.name, "to_currency": to_reg.currency,
        "to_amount": str(body.to_amount),
        "exchange_rate": str(body.exchange_rate),
    })
    # Аудит транзакций
    await write_audit(db, current_user.id, "cash_transaction", out_tx.id, AuditActionEnum.create, {
        "register": from_reg.name, "direction": "out",
        "amount": str(body.from_amount), "reason": "transfer",
    })
    await write_audit(db, current_user.id, "cash_transaction", in_tx.id, AuditActionEnum.create, {
        "register": to_reg.name, "direction": "in",
        "amount": str(body.to_amount), "reason": "transfer",
    })

    await db.commit()

    return TransferResponse(
        id=transfer.id,
        from_register_id=from_reg.id, from_register_name=from_reg.name, from_currency=from_reg.currency,
        to_register_id=to_reg.id,   to_register_name=to_reg.name,   to_currency=to_reg.currency,
        from_amount=transfer.from_amount, to_amount=transfer.to_amount,
        exchange_rate=transfer.exchange_rate,
        transfer_date=str(transfer.transfer_date),
        notes=transfer.notes,
        created_by_name=current_user.full_name,
        created_at=transfer.created_at.isoformat(),
    )


@router.get("/transfers", response_model=List[TransferResponse])
async def list_transfers(
    register_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(CashTransfer).order_by(CashTransfer.created_at.desc())
    if register_id:
        from sqlalchemy import or_
        q = q.where(or_(CashTransfer.from_register_id == register_id, CashTransfer.to_register_id == register_id))
    q = q.offset((page - 1) * page_size).limit(page_size)
    transfers = (await db.execute(q)).scalars().all()

    reg_ids = {t.from_register_id for t in transfers} | {t.to_register_id for t in transfers}
    user_ids = {t.created_by for t in transfers}
    regs = {r.id: r for r in (await db.execute(select(CashRegister).where(CashRegister.id.in_(reg_ids)))).scalars().all()} if reg_ids else {}
    users = {u.id: u.full_name for u in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()} if user_ids else {}

    result = []
    for t in transfers:
        fr = regs.get(t.from_register_id)
        tr = regs.get(t.to_register_id)
        result.append(TransferResponse(
            id=t.id,
            from_register_id=t.from_register_id, from_register_name=fr.name if fr else "—", from_currency=fr.currency if fr else "",
            to_register_id=t.to_register_id,     to_register_name=tr.name if tr else "—", to_currency=tr.currency if tr else "",
            from_amount=t.from_amount, to_amount=t.to_amount, exchange_rate=t.exchange_rate,
            transfer_date=str(t.transfer_date), notes=t.notes,
            created_by_name=users.get(t.created_by, ""),
            created_at=t.created_at.isoformat(),
        ))
    return result
