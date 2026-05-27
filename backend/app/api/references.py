from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.user_role import UserRoleEntry
from app.models.business_type import BusinessType

router = APIRouter(prefix="/api/references", tags=["references"])


@router.get("/managers")
async def get_managers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(User)
        .join(UserRoleEntry, UserRoleEntry.user_id == User.id)
        .where(User.is_active == True, UserRoleEntry.role.in_(["manager", "admin"]))
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
