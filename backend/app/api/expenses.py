import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, validator as pydantic_validator
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.expense import Expense, LinkTypeEnum, ReimburseStatusEnum
from app.models.expense_category import ExpenseCategory
from app.models.asset import Asset
from app.models.order import Order
from app.models.counterparty import Counterparty
from app.models.company import Company
from app.models.cash_register import CashRegister, CashTransaction, TxDirection
from app.models.exchange_rate import ExchangeRate
from app.models.audit_log import AuditActionEnum
from app.schemas.expense import (
    ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseListItem,
    ExpenseListResponse, ReimbursementBalance,
    ApproveBody, RejectBody, MarkPaidBody,
)
from app.utils.audit import write_audit
from app.services.notifications import (
    on_reimbursement_created, on_reimbursement_status_changed,
)

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


async def _record_cash_outflow(
    db: AsyncSession,
    cash_register_id: uuid.UUID,
    cash_amount: Decimal,       # сумма В ВАЛЮТЕ КАССЫ (не в CNY!)
    notes: str,
    created_by: uuid.UUID,
    reason: str = "expense",
) -> None:
    """Записывает расход в кассу. cash_amount — уже в валюте кассы."""
    from app.api.cash_registers import _get_balance
    current_balance = await _get_balance(db, cash_register_id)
    balance_after = current_balance - cash_amount
    tx = CashTransaction(
        id=uuid.uuid4(),
        cash_register_id=cash_register_id,
        direction=TxDirection.outflow,
        amount=cash_amount,
        balance_after=balance_after,
        operation_type=reason,   # "expense", "reimbursement", etc. — уже системный ключ
        notes=notes,             # пользовательский текст
        created_by=created_by,
    )
    db.add(tx)
    await db.flush()
    await write_audit(db, created_by, "cash_transaction", tx.id, AuditActionEnum.create, {
        "register_id": str(cash_register_id),
        "direction": "out",
        "amount": str(cash_amount),
        "reason": reason,
    })

# Порядок «крупности» валют: USD > USDT > CNY > RUB.
# cash_rate всегда выражается как «1 {крупная} = X {мелкая}».
_CURRENCY_RANK = {"USD": 3, "USDT": 2, "CNY": 1, "RUB": 0}


def _compute_cash_outflow(
    reg_currency: str,
    exp_currency: str,
    amount: Decimal,
    amount_cny: Decimal,
    cash_rate: Optional[Decimal],
) -> Decimal:
    """Сколько списать с кассы В ВАЛЮТЕ КАССЫ для расхода/возмещения.

    - валюта расхода == валюта кассы → списываем сумму как есть;
    - касса в CNY → списываем amount_cny (курс к CNY уже известен);
    - иначе (касса в другой валюте, отличной от расхода) → нужен cash_rate,
      конвертируем по принципу «1 крупная = X мелкая».
    """
    if exp_currency == reg_currency:
        return amount
    if reg_currency == "CNY":
        return amount_cny
    if not cash_rate or cash_rate <= 0:
        raise HTTPException(422, f"cross_currency_rate_required:{exp_currency}:{reg_currency}")
    exp_rank = _CURRENCY_RANK.get(exp_currency, 1)
    reg_rank = _CURRENCY_RANK.get(reg_currency, 1)
    if exp_rank > reg_rank:
        # Расход в крупной валюте (напр. USD→CNY): 1 USD = X CNY → amount * rate
        return (amount * cash_rate).quantize(Decimal("0.000001"))
    # Расход в мелкой валюте (напр. CNY→USDT): 1 USDT = X CNY → amount / rate
    return (amount / cash_rate).quantize(Decimal("0.000001"))


_ACCOUNTANT_ROLES = ("accountant", "admin")
_ALL_ROLES = ("employee", "manager", "purchaser", "accountant", "admin")

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


async def _get_default_company(db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.is_active == True).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(400, "No active company found")
    return company


OFFICE_DEPOSIT_CATEGORY = "Депозит за офис"


async def _sync_office_deposit_asset(db: AsyncSession, expense: Expense) -> None:
    """Расход категории «Депозит за офис» — возвратный залог → отражаем как Актив.

    Идемпотентно: держим единственный Актив на расход (source_expense_id).
    Расход удалён/деактивирован или категория сменилась → актив скрываем.
    """
    cat = (await db.execute(
        select(ExpenseCategory).where(ExpenseCategory.id == expense.category_id)
    )).scalar_one_or_none()
    is_deposit = bool(cat and cat.name == OFFICE_DEPOSIT_CATEGORY)

    asset = (await db.execute(
        select(Asset).where(Asset.source_expense_id == expense.id)
    )).scalar_one_or_none()

    active = is_deposit and expense.is_active
    if active:
        if asset:
            asset.is_deleted = False
            asset.name = expense.description or OFFICE_DEPOSIT_CATEGORY
            asset.price = expense.amount_cny
            asset.quantity = Decimal("1")
            asset.purchase_date = expense.expense_date
        else:
            db.add(Asset(
                id=uuid.uuid4(),
                name=expense.description or OFFICE_DEPOSIT_CATEGORY,
                quantity=Decimal("1"),
                price=expense.amount_cny,
                account=None,
                purchase_date=expense.expense_date,
                created_by=expense.created_by,
                source_expense_id=expense.id,
                is_deleted=False,
            ))
    elif asset:
        asset.is_deleted = True


async def _load_expense(db: AsyncSession, expense_id: uuid.UUID) -> ExpenseResponse:
    OrderAlias = aliased(Order)
    ClientAlias = aliased(Counterparty)
    ReimburseUserAlias = aliased(User)
    CreatorAlias = aliased(User)
    CategoryAlias = aliased(ExpenseCategory)
    CashRegisterAlias = aliased(CashRegister)

    row = (await db.execute(
        select(
            Expense,
            CategoryAlias.name.label("cat_name"),
            CategoryAlias.name_cn.label("cat_name_cn"),
            OrderAlias.order_number.label("order_number"),
            ClientAlias.name.label("client_name"),
            ReimburseUserAlias.full_name.label("reimburse_to_name"),
            CreatorAlias.full_name.label("creator_name"),
            CashRegisterAlias.name.label("cash_register_name"),
        )
        .join(CategoryAlias, Expense.category_id == CategoryAlias.id)
        .outerjoin(OrderAlias, Expense.order_id == OrderAlias.id)
        .outerjoin(ClientAlias, Expense.client_id == ClientAlias.id)
        .outerjoin(ReimburseUserAlias, Expense.reimburse_to_user_id == ReimburseUserAlias.id)
        .join(CreatorAlias, Expense.created_by == CreatorAlias.id)
        .outerjoin(CashRegisterAlias, Expense.cash_register_id == CashRegisterAlias.id)
        .where(Expense.id == expense_id, Expense.is_active == True)
    )).first()

    if not row:
        raise HTTPException(404, "Expense not found")

    e = row[0]
    return ExpenseResponse(
        id=e.id, expense_date=e.expense_date,
        category_id=e.category_id, category_name=row.cat_name, category_name_cn=row.cat_name_cn,
        currency=e.currency, amount=e.amount, rate_to_cny=e.rate_to_cny, amount_cny=e.amount_cny,
        link_type=e.link_type, order_id=e.order_id, order_number=row.order_number,
        client_id=e.client_id, client_name=row.client_name,
        is_reimbursement=e.is_reimbursement,
        reimburse_to_user_id=e.reimburse_to_user_id, reimburse_to_name=row.reimburse_to_name,
        reimburse_status=e.reimburse_status, reimburse_paid_date=e.reimburse_paid_date,
        reject_reason=e.reject_reason, description=e.description,
        receipt_url=e.receipt_url, qr_url=getattr(e, "qr_url", None),
        pending_change=getattr(e, "pending_change", None),
        cash_register_id=e.cash_register_id, cash_register_name=row.cash_register_name,
        created_by=e.created_by, created_by_name=row.creator_name,
        created_at=e.created_at, is_active=e.is_active,
    )


# ── list ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=ExpenseListResponse)
async def list_expenses(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    category_id: Optional[uuid.UUID] = Query(None),
    link_type: Optional[str] = Query(None),
    order_id: Optional[uuid.UUID] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    currency: Optional[str] = Query(None),
    is_reimbursement: Optional[bool] = Query(None),
    reimburse_status: Optional[str] = Query(None),
    created_by_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_accountant = current_user.has_role(*_ACCOUNTANT_ROLES)

    OrderAlias = aliased(Order)
    ClientAlias = aliased(Counterparty)
    ReimburseUserAlias = aliased(User)
    CreatorAlias = aliased(User)
    CategoryAlias = aliased(ExpenseCategory)
    CashRegAlias = aliased(CashRegister)

    stmt = (
        select(
            Expense,
            CategoryAlias.name.label("cat_name"),
            CategoryAlias.name_cn.label("cat_name_cn"),
            OrderAlias.order_number.label("order_number"),
            ClientAlias.name.label("client_name"),
            ReimburseUserAlias.full_name.label("reimburse_to_name"),
            CreatorAlias.full_name.label("creator_name"),
            CashRegAlias.name.label("cash_register_name"),
        )
        .join(CategoryAlias, Expense.category_id == CategoryAlias.id)
        .outerjoin(OrderAlias, Expense.order_id == OrderAlias.id)
        .outerjoin(ClientAlias, Expense.client_id == ClientAlias.id)
        .outerjoin(ReimburseUserAlias, Expense.reimburse_to_user_id == ReimburseUserAlias.id)
        .join(CreatorAlias, Expense.created_by == CreatorAlias.id)
        .outerjoin(CashRegAlias, Expense.cash_register_id == CashRegAlias.id)
        .where(Expense.is_active == True)
    )

    # Non-accountant users see only their own
    if not is_accountant:
        stmt = stmt.where(Expense.created_by == current_user.id)

    if date_from:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to:
        stmt = stmt.where(Expense.expense_date <= date_to)
    if category_id:
        stmt = stmt.where(Expense.category_id == category_id)
    if link_type:
        stmt = stmt.where(Expense.link_type == link_type)
    if order_id:
        stmt = stmt.where(Expense.order_id == order_id)
    if client_id:
        stmt = stmt.where(Expense.client_id == client_id)
    if currency:
        stmt = stmt.where(Expense.currency == currency)
    if is_reimbursement is not None:
        stmt = stmt.where(Expense.is_reimbursement == is_reimbursement)
    if reimburse_status:
        stmt = stmt.where(Expense.reimburse_status == reimburse_status)
    if created_by_id and is_accountant:
        stmt = stmt.where(Expense.created_by == created_by_id)
    if search:
        stmt = stmt.where(Expense.description.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    # Page totals by link_type
    totals_stmt = select(
        Expense.link_type,
        func.sum(Expense.amount_cny).label("total"),
    ).where(Expense.is_active == True)
    if not is_accountant:
        totals_stmt = totals_stmt.where(Expense.created_by == current_user.id)
    if date_from:
        totals_stmt = totals_stmt.where(Expense.expense_date >= date_from)
    if date_to:
        totals_stmt = totals_stmt.where(Expense.expense_date <= date_to)
    if category_id:
        totals_stmt = totals_stmt.where(Expense.category_id == category_id)
    if link_type:
        totals_stmt = totals_stmt.where(Expense.link_type == link_type)
    if order_id:
        totals_stmt = totals_stmt.where(Expense.order_id == order_id)
    if client_id:
        totals_stmt = totals_stmt.where(Expense.client_id == client_id)
    if is_reimbursement is not None:
        totals_stmt = totals_stmt.where(Expense.is_reimbursement == is_reimbursement)
    if reimburse_status:
        totals_stmt = totals_stmt.where(Expense.reimburse_status == reimburse_status)
    totals_stmt = totals_stmt.group_by(Expense.link_type)
    totals_rows = (await db.execute(totals_stmt)).all()

    total_order_cny = Decimal("0")
    total_client_cny = Decimal("0")
    total_none_cny = Decimal("0")
    for row in totals_rows:
        lt = row[0]
        val = row[1] or Decimal("0")
        if lt == "order":
            total_order_cny = val
        elif lt == "client":
            total_client_cny = val
        else:
            total_none_cny = val

    stmt = stmt.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    items = [
        ExpenseListItem(
            id=r[0].id, expense_date=r[0].expense_date,
            category_id=r[0].category_id, category_name=r.cat_name, category_name_cn=r.cat_name_cn,
            currency=r[0].currency, amount=r[0].amount, amount_cny=r[0].amount_cny,
            link_type=r[0].link_type,
            order_id=r[0].order_id, order_number=r.order_number,
            client_id=r[0].client_id, client_name=r.client_name,
            is_reimbursement=r[0].is_reimbursement,
            reimburse_to_user_id=r[0].reimburse_to_user_id, reimburse_to_name=r.reimburse_to_name,
            reimburse_status=r[0].reimburse_status,
            description=r[0].description, receipt_url=r[0].receipt_url,
            cash_register_id=r[0].cash_register_id, cash_register_name=r.cash_register_name,
            created_by=r[0].created_by, created_by_name=r.creator_name,
            created_at=r[0].created_at, is_active=r[0].is_active,
        )
        for r in rows
    ]

    total_cny = total_order_cny + total_client_cny + total_none_cny
    return ExpenseListResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_cny=total_cny,
        total_order_cny=total_order_cny,
        total_client_cny=total_client_cny,
        total_none_cny=total_none_cny,
    )


# ── detail ────────────────────────────────────────────────────────────────────

@router.get("/my-balance", response_model=ReimbursementBalance)
async def get_my_reimbursement_balance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_user_balance(db, current_user.id)


@router.get("/user/{user_id}/balance", response_model=ReimbursementBalance)
async def get_user_reimbursement_balance(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ACCOUNTANT_ROLES)),
):
    return await _get_user_balance(db, user_id)


async def _get_user_balance(db: AsyncSession, user_id: uuid.UUID) -> ReimbursementBalance:
    rows = (await db.execute(
        select(Expense.reimburse_status, func.sum(Expense.amount_cny).label("total"),
               func.count(Expense.id).label("cnt"))
        .where(
            Expense.reimburse_to_user_id == user_id,
            Expense.is_reimbursement == True,
            Expense.is_active == True,
            Expense.reimburse_status.in_(["pending", "approved", "paid"]),
        )
        .group_by(Expense.reimburse_status)
    )).all()

    totals = {r[0]: {"amount": r[1] or Decimal("0"), "cnt": r[2]} for r in rows}
    approved = totals.get("approved", {}).get("amount", Decimal("0"))
    paid = totals.get("paid", {}).get("amount", Decimal("0"))
    pending_cnt = totals.get("pending", {}).get("cnt", 0)
    approved_cnt = totals.get("approved", {}).get("cnt", 0)

    return ReimbursementBalance(
        approved_amount_cny=approved,
        paid_amount_cny=paid,
        owed_cny=approved,
        pending_count=pending_cnt,
        approved_count=approved_cnt,
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = await _load_expense(db, expense_id)
    if not current_user.has_role(*_ACCOUNTANT_ROLES) and expense.created_by != current_user.id:
        raise HTTPException(403, "Access denied")
    return expense


# ── create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    body: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Non-accountant can only create reimbursements
    if not body.is_reimbursement and not current_user.has_role(*_ACCOUNTANT_ROLES):
        raise HTTPException(403, "Only accountant/admin can create non-reimbursement expenses")

    company = await _get_default_company(db)

    # Auto-fetch rate
    rate = body.rate_to_cny
    if body.currency != "CNY" and rate == Decimal("1"):
        rate_row = (await db.execute(
            select(ExchangeRate).where(
                ExchangeRate.currency == body.currency,
                ExchangeRate.rate_date == body.expense_date,
            )
        )).scalar_one_or_none()
        if rate_row:
            rate = rate_row.rate_to_cny

    amount_cny = (body.amount * rate).quantize(Decimal("0.01"))

    # Validate link references
    if body.link_type == "order" and body.order_id:
        order = (await db.execute(select(Order).where(Order.id == body.order_id))).scalar_one_or_none()
        if not order:
            raise HTTPException(422, "Order not found")
    if body.link_type == "client" and body.client_id:
        client = (await db.execute(select(Counterparty).where(Counterparty.id == body.client_id))).scalar_one_or_none()
        if not client:
            raise HTTPException(422, "Client not found")

    reimburse_status = None
    reimburse_to = None
    if body.is_reimbursement:
        reimburse_status = ReimburseStatusEnum.pending
        reimburse_to = body.reimburse_to_user_id or current_user.id

    expense = Expense(
        id=uuid.uuid4(),
        company_id=company.id,
        expense_date=body.expense_date,
        category_id=body.category_id,
        currency=body.currency,
        amount=body.amount,
        rate_to_cny=rate,
        amount_cny=amount_cny,
        link_type=body.link_type,
        order_id=body.order_id if body.link_type == "order" else None,
        client_id=body.client_id if body.link_type == "client" else None,
        is_reimbursement=body.is_reimbursement,
        reimburse_to_user_id=reimburse_to,
        reimburse_status=reimburse_status,
        description=body.description,
        receipt_url=body.receipt_url,
        cash_register_id=body.cash_register_id,
        cash_amount_in_register=None,  # заполним ниже после расчёта
        is_active=True,
        created_by=current_user.id,
    )
    db.add(expense)
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.create,
                      {"description": body.description, "amount_cny": str(amount_cny),
                       "is_reimbursement": body.is_reimbursement})
    if body.is_reimbursement:
        await on_reimbursement_created(db, expense.id, str(amount_cny), current_user.full_name)
    # Списание с кассы (только для прямых расходов — не возмещений)
    if body.cash_register_id and not body.is_reimbursement:
        reg = (await db.execute(
            select(CashRegister).where(CashRegister.id == body.cash_register_id)
        )).scalar_one_or_none()
        reg_currency = reg.currency if reg else "CNY"

        cash_amount = _compute_cash_outflow(
            reg_currency, body.currency, body.amount, amount_cny, body.cash_rate,
        )

        # Сохраняем сколько реально списали с кассы
        expense.cash_amount_in_register = cash_amount
        await _record_cash_outflow(
            db, body.cash_register_id, cash_amount,
            body.description[:80],  # только пользовательский текст
            current_user.id,
        )
    await db.flush()
    await _sync_office_deposit_asset(db, expense)
    await db.commit()
    return await _load_expense(db, expense.id)


# ── update ────────────────────────────────────────────────────────────────────

@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    body: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")

    # Access check
    if not current_user.has_role(*_ACCOUNTANT_ROLES) and expense.created_by != current_user.id:
        raise HTTPException(403, "Access denied")
    if expense.reimburse_status == ReimburseStatusEnum.paid and not current_user.has_role("admin"):
        raise HTTPException(422, "Cannot edit a paid reimbursement")

    data = body.model_dump(exclude_unset=True)

    # Non-accountants cannot change financial fields directly
    if not current_user.has_role(*_ACCOUNTANT_ROLES):
        blocked = {"amount", "currency", "rate_to_cny"} & set(data.keys())
        if blocked:
            raise HTTPException(403, "Изменение суммы требует подтверждения. Используйте запрос на изменение суммы.")

    old_cash_register_id = expense.cash_register_id
    old_cash_amount = expense.cash_amount_in_register

    for field, value in data.items():
        setattr(expense, field, value)

    if "amount" in data or "rate_to_cny" in data:
        expense.amount_cny = (expense.amount * expense.rate_to_cny).quantize(Decimal("0.01"))

    # Если добавили кассу впервые (не возмещение, не было кассы раньше) — создаём транзакцию
    new_cash_register_id = expense.cash_register_id
    if (
        new_cash_register_id
        and not expense.is_reimbursement
        and not old_cash_register_id
        and not old_cash_amount
    ):
        reg = (await db.execute(
            select(CashRegister).where(CashRegister.id == new_cash_register_id)
        )).scalar_one_or_none()
        reg_currency = reg.currency if reg else "CNY"
        cash_amount = expense.amount if reg_currency == expense.currency else expense.amount_cny
        expense.cash_amount_in_register = cash_amount
        await _record_cash_outflow(
            db, new_cash_register_id, cash_amount,
            (expense.description or "")[:80],
            current_user.id,
        )

    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"updated": list(data.keys())})
    await _sync_office_deposit_asset(db, expense)
    await db.commit()
    return await _load_expense(db, expense.id)


# ── amount change request workflow ───────────────────────────────────────────

import json as _json
import datetime as _datetime

class ChangeRequestBody(BaseModel):
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    rate_to_cny: Optional[Decimal] = None
    reason: str = ""


@router.post("/{expense_id}/request-change", status_code=200)
async def request_expense_change(
    expense_id: uuid.UUID,
    body: ChangeRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")
    if not current_user.has_role(*_ACCOUNTANT_ROLES) and expense.created_by != current_user.id:
        raise HTTPException(403, "Access denied")

    pending = {
        "amount": str(body.amount) if body.amount is not None else str(expense.amount),
        "currency": body.currency or expense.currency,
        "rate_to_cny": str(body.rate_to_cny) if body.rate_to_cny is not None else str(expense.rate_to_cny),
        "reason": body.reason,
        "requested_by": str(current_user.id),
        "requested_by_name": current_user.full_name or "",
        "requested_at": _datetime.datetime.utcnow().isoformat(),
    }
    expense.pending_change = _json.dumps(pending, ensure_ascii=False)
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"change_requested": pending})
    await db.commit()
    return {"ok": True}


@router.post("/{expense_id}/approve-change", response_model=ExpenseResponse)
async def approve_expense_change(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ACCOUNTANT_ROLES)),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")
    if not getattr(expense, "pending_change", None):
        raise HTTPException(404, "Нет активного запроса на изменение")

    pending = _json.loads(expense.pending_change)
    expense.amount = Decimal(pending["amount"])
    expense.currency = pending["currency"]
    expense.rate_to_cny = Decimal(pending["rate_to_cny"])
    expense.amount_cny = (expense.amount * expense.rate_to_cny).quantize(Decimal("0.01"))
    expense.pending_change = None
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"change_approved": pending})
    await db.commit()
    return await _load_expense(db, expense.id)


@router.post("/{expense_id}/reject-change", response_model=ExpenseResponse)
async def reject_expense_change(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ACCOUNTANT_ROLES)),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")
    expense.pending_change = None
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"change_rejected": True})
    await db.commit()
    return await _load_expense(db, expense.id)


# ── delete ────────────────────────────────────────────────────────────────────

class ExpenseDeleteBody(BaseModel):
    reason: str

    @pydantic_validator("reason")
    def reason_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Укажите причину удаления")
        return v.strip()


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: uuid.UUID,
    body: ExpenseDeleteBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")

    if not current_user.has_role(*_ACCOUNTANT_ROLES) and expense.created_by != current_user.id:
        raise HTTPException(403, "Access denied")
    if expense.reimburse_status == ReimburseStatusEnum.paid and not current_user.has_role("admin"):
        raise HTTPException(422, "Cannot delete a paid reimbursement")

    expense.is_active = False
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.delete,
                      {"reason": body.reason, "amount_cny": str(expense.amount_cny),
                       "currency": expense.currency, "description": expense.description})

    # Возврат в кассу если было списание (прямой расход ИЛИ оплаченное возмещение)
    needs_refund = expense.cash_register_id and (
        (not expense.is_reimbursement and expense.cash_amount_in_register) or
        (expense.is_reimbursement and expense.reimburse_status == ReimburseStatusEnum.paid
         and expense.cash_amount_in_register)
    )
    if needs_refund:
        from app.api.cash_registers import _get_balance
        refund_amount = expense.cash_amount_in_register
        cur_bal = await _get_balance(db, expense.cash_register_id)
        comp_tx = CashTransaction(
            id=uuid.uuid4(),
            cash_register_id=expense.cash_register_id,
            direction=TxDirection.inflow,
            amount=refund_amount,
            balance_after=cur_bal + refund_amount,
            operation_type="expense_cancel",
            notes=expense.description[:80] if expense.description else "",
            created_by=current_user.id,
        )
        db.add(comp_tx)
        await db.flush()
        await write_audit(db, current_user.id, "cash_transaction", comp_tx.id, AuditActionEnum.create, {
            "register_id": str(expense.cash_register_id),
            "direction": "in",
            "amount": str(refund_amount),
            "reason": "expense_deleted",
            "expense_id": str(expense_id),
        })

    await _sync_office_deposit_asset(db, expense)
    await db.commit()


# ── reimbursement workflow ─────────────────────────────────────────────────────

@router.post("/{expense_id}/approve", response_model=ExpenseResponse)
async def approve_reimbursement(
    expense_id: uuid.UUID,
    body: ApproveBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ACCOUNTANT_ROLES)),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")
    if not expense.is_reimbursement:
        raise HTTPException(422, "Not a reimbursement")
    if expense.reimburse_status != ReimburseStatusEnum.pending:
        raise HTTPException(422, "Only pending reimbursements can be approved")

    if body.amount is not None:
        expense.amount = body.amount
        expense.amount_cny = (body.amount * expense.rate_to_cny).quantize(Decimal("0.01"))

    expense.reimburse_status = ReimburseStatusEnum.approved
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"reimburse_status": "approved"})
    if expense.reimburse_to_user_id:
        await on_reimbursement_status_changed(
            db, expense.id, expense.reimburse_to_user_id,
            "approved", str(expense.amount_cny),
        )
    await db.commit()
    return await _load_expense(db, expense.id)


@router.post("/{expense_id}/reject", response_model=ExpenseResponse)
async def reject_reimbursement(
    expense_id: uuid.UUID,
    body: RejectBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ACCOUNTANT_ROLES)),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")
    if not expense.is_reimbursement:
        raise HTTPException(422, "Not a reimbursement")
    if expense.reimburse_status not in (ReimburseStatusEnum.pending, ReimburseStatusEnum.approved):
        raise HTTPException(422, "Cannot reject in current status")

    expense.reimburse_status = ReimburseStatusEnum.rejected
    expense.reject_reason = body.reject_reason
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"reimburse_status": "rejected", "reject_reason": body.reject_reason})
    if expense.reimburse_to_user_id:
        await on_reimbursement_status_changed(
            db, expense.id, expense.reimburse_to_user_id,
            "rejected", str(expense.amount_cny),
        )
    await db.commit()
    return await _load_expense(db, expense.id)


@router.post("/{expense_id}/mark-paid", response_model=ExpenseResponse)
async def mark_reimbursement_paid(
    expense_id: uuid.UUID,
    body: MarkPaidBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ACCOUNTANT_ROLES)),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")
    if not expense.is_reimbursement:
        raise HTTPException(422, "Not a reimbursement")
    if expense.reimburse_status != ReimburseStatusEnum.approved:
        raise HTTPException(422, "Only approved reimbursements can be marked as paid")

    expense.reimburse_status = ReimburseStatusEnum.paid
    expense.reimburse_paid_date = body.paid_date
    if body.cash_register_id:
        expense.cash_register_id = body.cash_register_id
        # Списываем в валюте кассы: если валюта расхода == валюта кассы — берём amount,
        # иначе берём amount_cny (касса CNY) или требуем конвертацию.
        reg = (await db.execute(
            select(CashRegister).where(CashRegister.id == body.cash_register_id)
        )).scalar_one_or_none()
        reg_currency = reg.currency if reg else "CNY"
        outflow_amount = _compute_cash_outflow(
            reg_currency, expense.currency, expense.amount, expense.amount_cny, body.cash_rate,
        )
        expense.cash_amount_in_register = outflow_amount
        await _record_cash_outflow(
            db, body.cash_register_id, outflow_amount,
            expense.description[:80],
            current_user.id,
            reason="reimbursement",
        )
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"reimburse_status": "paid", "paid_date": str(body.paid_date),
                       "cash_register_id": str(body.cash_register_id) if body.cash_register_id else None})
    if expense.reimburse_to_user_id:
        await on_reimbursement_status_changed(
            db, expense.id, expense.reimburse_to_user_id,
            "paid", str(expense.amount_cny),
        )
    await db.commit()
    return await _load_expense(db, expense.id)


# ── receipt upload ─────────────────────────────────────────────────────────────

@router.post("/{expense_id}/receipt", response_model=ExpenseResponse)
async def upload_receipt(
    expense_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")

    if not current_user.has_role(*_ACCOUNTANT_ROLES) and expense.created_by != current_user.id:
        raise HTTPException(403, "Access denied")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")

    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(422, f"File type not allowed: {mime}")

    dest_dir = UPLOADS_DIR / "expenses" / str(expense_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "file").suffix.lower() or ".bin"
    stored_name = f"{uuid.uuid4()}{ext}"
    (dest_dir / stored_name).write_bytes(content)

    expense.receipt_url = f"expenses/{expense_id}/{stored_name}"
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"receipt_uploaded": file.filename})
    await db.commit()
    return await _load_expense(db, expense.id)


# ── qr photo upload ──────────────────────────────────────────────────────────

@router.post("/{expense_id}/qr", response_model=ExpenseResponse)
async def upload_qr(
    expense_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")

    if not current_user.has_role(*_ACCOUNTANT_ROLES) and expense.created_by != current_user.id:
        raise HTTPException(403, "Access denied")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")

    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(422, f"File type not allowed: {mime}")

    dest_dir = UPLOADS_DIR / "expenses" / str(expense_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "file").suffix.lower() or ".bin"
    stored_name = f"qr_{uuid.uuid4()}{ext}"
    (dest_dir / stored_name).write_bytes(content)

    if expense.qr_url:
        old = UPLOADS_DIR / expense.qr_url
        if old.exists():
            old.unlink()

    expense.qr_url = f"expenses/{expense_id}/{stored_name}"
    await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                      {"qr_uploaded": file.filename})
    await db.commit()
    return await _load_expense(db, expense.id)


@router.delete("/{expense_id}/qr", status_code=204)
async def delete_qr(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_active == True)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")

    if expense.qr_url:
        old = UPLOADS_DIR / expense.qr_url
        if old.exists():
            old.unlink()
        expense.qr_url = None
        await write_audit(db, current_user.id, "expense", expense.id, AuditActionEnum.update,
                          {"qr_deleted": True})
        await db.commit()


# ── history ────────────────────────────────────────────────────────────────────

@router.get("/{expense_id}/history")
async def get_expense_history(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (await db.execute(
        select(Expense).where(Expense.id == expense_id)
    )).scalar_one_or_none()
    if not expense:
        raise HTTPException(404, "Expense not found")

    if not current_user.has_role(*_ACCOUNTANT_ROLES) and expense.created_by != current_user.id:
        raise HTTPException(403, "Access denied")

    from app.models.audit_log import AuditLog
    rows = (await db.execute(
        select(AuditLog, User.full_name.label("user_name"))
        .join(User, AuditLog.user_id == User.id)
        .where(AuditLog.entity_type == "expense", AuditLog.entity_id == expense_id)
        .order_by(AuditLog.created_at.desc())
    )).all()

    return [
        {
            "id": str(r[0].id),
            "action": r[0].action,
            "user_id": str(r[0].user_id),
            "user_name": r[1],
            "changes": r[0].changes,
            "created_at": r[0].created_at.isoformat(),
        }
        for r in rows
    ]
