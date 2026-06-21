from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.user_role import UserRoleEntry
from app.models.business_type import BusinessType
from app.models.expense_category import ExpenseCategory

router = APIRouter(prefix="/api/references", tags=["references"])


@router.get("/managers")
async def get_managers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(User)
        .join(UserRoleEntry, UserRoleEntry.user_id == User.id)
        .where(User.is_active == True, UserRoleEntry.role.in_(["seller", "manager", "purchaser", "accountant", "admin"]))
        .distinct()
        .order_by(User.full_name)
    )
    users = result.scalars().all()
    return [{"id": str(u.id), "full_name": u.full_name} for u in users]


@router.get("/business-types")
async def get_business_types(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(BusinessType).order_by(BusinessType.name))
    bts = result.scalars().all()
    return [{"id": str(bt.id), "name": bt.name, "name_cn": bt.name_cn, "code": bt.code} for bt in bts]


@router.get("/expense-categories")
async def get_expense_categories(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExpenseCategory).where(ExpenseCategory.is_active == True).order_by(ExpenseCategory.name)
    )
    cats = result.scalars().all()
    return [{"id": str(c.id), "name": c.name, "name_cn": c.name_cn} for c in cats]


@router.get("/employees")
async def get_employees(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """All active users — used for reimbursement target selection."""
    result = await db.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    )
    users = result.scalars().all()
    return [{"id": str(u.id), "full_name": u.full_name} for u in users]
