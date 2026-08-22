"""Раздел «Зарплаты»: работники, месячный расчёт, ежедневный табель, выплата.

Расчёт (всё в CNY):
    цена дня    = оклад / рабочих дней
    заработано  = цена дня * отработано дней
    переработка = (цена дня / 8) * часы переработки
    К ВЫПЛАТЕ    = заработано + бонус + переработка - соц. страхование
"""
import calendar
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import require_roles
from app.models.user import User
from app.models.payroll import PayrollEmployee, PayrollRecord, PayrollAttendance

# роль пользователя → должность по умолчанию
_ROLE_TITLES = {
    "manager": "Менеджер",
    "accountant": "Бухгалтер",
    "purchaser": "Закупщик",
    "seller": "Продавец",
    "employee": "Сотрудник",
    "admin": "Администратор",
    "partner": "Партнёр",
}
_ROLE_PRIORITY = ["manager", "accountant", "purchaser", "seller", "employee", "admin", "partner"]


def _position_from_roles(roles: list[str]) -> Optional[str]:
    for r in _ROLE_PRIORITY:
        if r in roles:
            return _ROLE_TITLES.get(r, r)
    return None
from app.models.expense import Expense, LinkTypeEnum
from app.models.expense_category import ExpenseCategory
from app.models.cash_register import CashRegister
from app.api.expenses import _compute_cash_outflow, _record_cash_outflow, _get_default_company

router = APIRouter(prefix="/api/payroll", tags=["payroll"])

_ROLES = ("accountant", "admin")
Q2 = Decimal("0.01")


# ── schemas ─────────────────────────────────────────────────────────────────
class EmployeeIn(BaseModel):
    user_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    position: Optional[str] = None


class EmployeePatch(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None


class RecordPatch(BaseModel):
    monthly_salary: Optional[Decimal] = None
    working_days: Optional[int] = None
    social_insurance: Optional[Decimal] = None
    bonus: Optional[Decimal] = None


class AttendanceDay(BaseModel):
    day: int
    attended: bool = False
    overtime_hours: Decimal = Decimal("0")


class PayIn(BaseModel):
    cash_register_id: uuid.UUID
    expense_date: Optional[date] = None
    cash_rate: Optional[Decimal] = None


# ── helpers ─────────────────────────────────────────────────────────────────
def _compute(rec: PayrollRecord, atts: list[PayrollAttendance]) -> dict:
    monthly = rec.monthly_salary or Decimal("0")
    wd = rec.working_days or 24
    daily = (monthly / wd) if wd else Decimal("0")
    days_attended = sum(1 for a in atts if a.attended)
    ot_hours = sum((a.overtime_hours or Decimal("0")) for a in atts)
    base_earned = daily * days_attended
    overtime_pay = (daily / 8) * ot_hours if ot_hours else Decimal("0")
    net = base_earned + (rec.bonus or Decimal("0")) + overtime_pay - (rec.social_insurance or Decimal("0"))
    return {
        "daily_rate": daily.quantize(Q2),
        "days_attended": days_attended,
        "overtime_hours": Decimal(ot_hours).quantize(Q2),
        "base_earned": base_earned.quantize(Q2),
        "overtime_pay": overtime_pay.quantize(Q2),
        "net_total": net.quantize(Q2),
    }


def _record_dict(rec: PayrollRecord, emp: PayrollEmployee) -> dict:
    atts = list(rec.attendance or [])
    c = _compute(rec, atts)
    return {
        "id": str(rec.id),
        "employee_id": str(emp.id),
        "employee_name": emp.name,
        "position": emp.position,
        "year": rec.year,
        "month": rec.month,
        "monthly_salary": rec.monthly_salary,
        "working_days": rec.working_days,
        "social_insurance": rec.social_insurance,
        "bonus": rec.bonus,
        "is_paid": rec.is_paid,
        "paid_at": rec.paid_at.isoformat() if rec.paid_at else None,
        **c,
    }


# ── employees ───────────────────────────────────────────────────────────────
@router.get("/employees")
async def list_employees(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ROLES)),
):
    rows = (await db.execute(
        select(PayrollEmployee).order_by(PayrollEmployee.is_active.desc(), PayrollEmployee.name)
    )).scalars().all()
    return [{"id": str(e.id), "name": e.name, "position": e.position, "is_active": e.is_active} for e in rows]


@router.get("/available-users")
async def available_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ROLES)),
):
    """Активные сотрудники системы, которых ещё нет в списке работников (для выпадашки)."""
    taken = (await db.execute(
        select(PayrollEmployee.user_id).where(PayrollEmployee.user_id.isnot(None))
    )).scalars().all()
    taken_set = set(taken)
    users = (await db.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    )).scalars().all()
    return [
        {"user_id": str(u.id), "full_name": u.full_name, "position": _position_from_roles(u.roles)}
        for u in users if u.id not in taken_set
    ]


@router.post("/employees")
async def create_employee(
    body: EmployeeIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ROLES)),
):
    name = (body.name or "").strip()
    position = (body.position or None)
    user_id = body.user_id

    if user_id:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(422, "Сотрудник не найден")
        exists = (await db.execute(
            select(PayrollEmployee).where(PayrollEmployee.user_id == user_id)
        )).scalar_one_or_none()
        if exists:
            raise HTTPException(422, "Этот сотрудник уже добавлен")
        name = name or user.full_name
        if not position:
            position = _position_from_roles(user.roles)

    if not name:
        raise HTTPException(422, "Укажите сотрудника или имя")

    emp = PayrollEmployee(id=uuid.uuid4(), name=name, position=position, user_id=user_id)
    db.add(emp)
    await db.commit()
    return {"id": str(emp.id), "name": emp.name, "position": emp.position, "is_active": emp.is_active}


@router.patch("/employees/{employee_id}")
async def patch_employee(
    employee_id: uuid.UUID,
    body: EmployeePatch,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ROLES)),
):
    emp = (await db.execute(select(PayrollEmployee).where(PayrollEmployee.id == employee_id))).scalar_one_or_none()
    if not emp:
        raise HTTPException(404, "Работник не найден")
    if body.name is not None:
        emp.name = body.name.strip()
    if body.position is not None:
        emp.position = body.position or None
    if body.is_active is not None:
        emp.is_active = body.is_active
    await db.commit()
    return {"id": str(emp.id), "name": emp.name, "position": emp.position, "is_active": emp.is_active}


# ── month view (get-or-create records) ────────────────────────────────────────
@router.get("/month")
async def get_month(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ROLES)),
):
    employees = (await db.execute(
        select(PayrollEmployee).where(PayrollEmployee.is_active == True).order_by(PayrollEmployee.name)
    )).scalars().all()

    existing = (await db.execute(
        select(PayrollRecord)
        .options(selectinload(PayrollRecord.attendance))
        .where(PayrollRecord.year == year, PayrollRecord.month == month)
    )).scalars().all()
    by_emp = {r.employee_id: r for r in existing}

    created = False
    for emp in employees:
        if emp.id not in by_emp:
            rec = PayrollRecord(id=uuid.uuid4(), employee_id=emp.id, year=year, month=month)
            db.add(rec)
            created = True
    if created:
        await db.commit()
        existing = (await db.execute(
            select(PayrollRecord)
            .options(selectinload(PayrollRecord.attendance))
            .where(PayrollRecord.year == year, PayrollRecord.month == month)
        )).scalars().all()
        by_emp = {r.employee_id: r for r in existing}

    rows = [_record_dict(by_emp[emp.id], emp) for emp in employees if emp.id in by_emp]
    totals = {
        "net_total": sum((Decimal(str(r["net_total"])) for r in rows), Decimal("0")),
        "count": len(rows),
    }
    return {"year": year, "month": month, "days_in_month": calendar.monthrange(year, month)[1], "rows": rows, "totals": totals}


@router.patch("/records/{record_id}")
async def patch_record(
    record_id: uuid.UUID,
    body: RecordPatch,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ROLES)),
):
    rec = (await db.execute(
        select(PayrollRecord).options(selectinload(PayrollRecord.attendance), selectinload(PayrollRecord.employee))
        .where(PayrollRecord.id == record_id)
    )).scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Запись не найдена")
    if rec.is_paid:
        raise HTTPException(422, "Зарплата уже выплачена — изменение недоступно")
    if body.monthly_salary is not None:
        rec.monthly_salary = body.monthly_salary
    if body.working_days is not None:
        rec.working_days = max(1, body.working_days)
    if body.social_insurance is not None:
        rec.social_insurance = body.social_insurance
    if body.bonus is not None:
        rec.bonus = body.bonus
    await db.commit()
    await db.refresh(rec, ["attendance", "employee"])
    return _record_dict(rec, rec.employee)


# ── attendance (daily timesheet) ──────────────────────────────────────────────
@router.get("/records/{record_id}/attendance")
async def get_attendance(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ROLES)),
):
    rec = (await db.execute(
        select(PayrollRecord).options(selectinload(PayrollRecord.attendance)).where(PayrollRecord.id == record_id)
    )).scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Запись не найдена")
    days_in_month = calendar.monthrange(rec.year, rec.month)[1]
    stored = {a.day: a for a in rec.attendance}
    days = []
    for d in range(1, days_in_month + 1):
        a = stored.get(d)
        days.append({
            "day": d,
            "attended": a.attended if a else False,
            "overtime_hours": (a.overtime_hours if a else Decimal("0")),
        })
    return {"record_id": str(rec.id), "year": rec.year, "month": rec.month, "days_in_month": days_in_month, "days": days}


@router.put("/records/{record_id}/attendance")
async def put_attendance(
    record_id: uuid.UUID,
    body: list[AttendanceDay],
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_ROLES)),
):
    rec = (await db.execute(
        select(PayrollRecord).options(selectinload(PayrollRecord.attendance), selectinload(PayrollRecord.employee))
        .where(PayrollRecord.id == record_id)
    )).scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Запись не найдена")
    if rec.is_paid:
        raise HTTPException(422, "Зарплата уже выплачена — табель недоступен")
    days_in_month = calendar.monthrange(rec.year, rec.month)[1]
    stored = {a.day: a for a in rec.attendance}
    for item in body:
        if item.day < 1 or item.day > days_in_month:
            continue
        a = stored.get(item.day)
        ot = item.overtime_hours or Decimal("0")
        if ot < 0:
            ot = Decimal("0")
        if a:
            a.attended = item.attended
            a.overtime_hours = ot
        else:
            db.add(PayrollAttendance(
                id=uuid.uuid4(), record_id=rec.id, day=item.day,
                attended=item.attended, overtime_hours=ot,
            ))
    await db.commit()
    await db.refresh(rec, ["attendance", "employee"])
    return _record_dict(rec, rec.employee)


# ── pay (post to expense + cash register) ─────────────────────────────────────
@router.post("/records/{record_id}/pay")
async def pay_record(
    record_id: uuid.UUID,
    body: PayIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROLES)),
):
    rec = (await db.execute(
        select(PayrollRecord).options(selectinload(PayrollRecord.attendance), selectinload(PayrollRecord.employee))
        .where(PayrollRecord.id == record_id)
    )).scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Запись не найдена")
    if rec.is_paid:
        raise HTTPException(422, "Зарплата уже выплачена")

    comp = _compute(rec, list(rec.attendance or []))
    net: Decimal = comp["net_total"]
    if net <= 0:
        raise HTTPException(422, "Сумма к выплате должна быть больше 0")

    cat = (await db.execute(
        select(ExpenseCategory).where(ExpenseCategory.name == "Зарплата", ExpenseCategory.is_active == True)
    )).scalar_one_or_none()
    if not cat:
        raise HTTPException(422, "Категория расходов «Зарплата» не найдена")

    reg = (await db.execute(
        select(CashRegister).where(CashRegister.id == body.cash_register_id, CashRegister.is_active == True)
    )).scalar_one_or_none()
    if not reg:
        raise HTTPException(422, "Касса не найдена или неактивна")

    company = await _get_default_company(db)
    exp_date = body.expense_date or date.today()
    emp_name = rec.employee.name if rec.employee else "—"
    desc = f"Зарплата — {emp_name} — {rec.month:02d}.{rec.year}"

    expense = Expense(
        id=uuid.uuid4(),
        company_id=company.id,
        expense_date=exp_date,
        category_id=cat.id,
        currency="CNY",
        amount=net,
        rate_to_cny=Decimal("1"),
        amount_cny=net,
        link_type=LinkTypeEnum.none,
        description=desc,
        cash_register_id=reg.id,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(expense)

    cash_amount = _compute_cash_outflow(reg.currency, "CNY", net, net, body.cash_rate)
    expense.cash_amount_in_register = cash_amount
    await _record_cash_outflow(db, reg.id, cash_amount, desc[:80], current_user.id)

    rec.is_paid = True
    rec.paid_expense_id = expense.id
    rec.paid_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(rec, ["attendance", "employee"])
    return {"ok": True, "net_total": str(net), "expense_id": str(expense.id), "record": _record_dict(rec, rec.employee)}
