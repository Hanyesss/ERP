import uuid
import secrets
import string
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete as sql_delete
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, field_validator

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.models.user import User, UserRole, UserLang
from app.models.user_role import UserRoleEntry
from app.models.audit_log import AuditActionEnum
from app.utils.audit import write_audit

router = APIRouter(prefix="/api/users", tags=["users"])

_ADMIN = require_roles("admin")


# ─── Schemas ────────────────────────────────────────────────────────────────

class UserListItem(BaseModel):
    id: uuid.UUID
    full_name: str
    login: str
    roles: List[str]
    lang: str
    is_active: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_user(cls, u: User) -> "UserListItem":
        return cls(
            id=u.id,
            full_name=u.full_name,
            login=u.login,
            roles=u.roles,
            lang=u.lang,
            is_active=u.is_active,
        )


class UserDetail(UserListItem):
    pass


class UserCreate(BaseModel):
    full_name: str
    login: str
    password: str
    lang: UserLang = UserLang.ru
    roles: List[UserRole]
    is_active: bool = True

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("roles")
    @classmethod
    def roles_not_empty(cls, v: List[UserRole]) -> List[UserRole]:
        if not v:
            raise ValueError("At least one role is required")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None
    lang: Optional[UserLang] = None
    roles: Optional[List[UserRole]] = None
    is_active: Optional[bool] = None

    @field_validator("roles")
    @classmethod
    def roles_not_empty(cls, v: Optional[List[UserRole]]) -> Optional[List[UserRole]]:
        if v is not None and len(v) == 0:
            raise ValueError("At least one role is required")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class ResetPasswordBody(BaseModel):
    password: Optional[str] = None  # if None — generate random

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class ResetPasswordResponse(BaseModel):
    new_password: str


# ─── Helpers ────────────────────────────────────────────────────────────────

def _generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _count_active_admins(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(UserRoleEntry.id))
        .join(User, User.id == UserRoleEntry.user_id)
        .where(
            UserRoleEntry.role == UserRole.admin,
            User.is_active == True,
        )
    )
    return result.scalar_one()


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.role_entries))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("", response_model=List[UserListItem])
async def list_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_ADMIN),
):
    q = select(User).options(selectinload(User.role_entries))

    filters = []
    if is_active is not None:
        filters.append(User.is_active == is_active)
    if search:
        like = f"%{search}%"
        filters.append(
            (User.full_name.ilike(like)) | (User.login.ilike(like))
        )
    if filters:
        q = q.where(and_(*filters))

    if role:
        q = q.join(UserRoleEntry, UserRoleEntry.user_id == User.id).where(
            UserRoleEntry.role == role
        )

    q = q.order_by(User.full_name)
    result = await db.execute(q)
    users = result.scalars().unique().all()
    return [UserListItem.from_user(u) for u in users]


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(_ADMIN),
):
    user = await _get_user_or_404(db, user_id)
    return UserDetail.from_user(user)


@router.post("", response_model=UserDetail, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_ADMIN),
):
    # Check login uniqueness
    existing = await db.execute(select(User).where(User.login == body.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Login already taken")

    new_user = User(
        id=uuid.uuid4(),
        login=body.login,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        lang=body.lang,
        is_active=body.is_active,
    )
    db.add(new_user)

    for role in body.roles:
        db.add(UserRoleEntry(id=uuid.uuid4(), user_id=new_user.id, role=role))

    await db.flush()
    await write_audit(db, admin.id, "user", new_user.id, AuditActionEnum.create,
                      {"login": body.login, "roles": [r.value for r in body.roles]})
    await db.commit()
    await db.refresh(new_user)

    result = await db.execute(
        select(User).options(selectinload(User.role_entries)).where(User.id == new_user.id)
    )
    return UserDetail.from_user(result.scalar_one())


@router.patch("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_ADMIN),
):
    user = await _get_user_or_404(db, user_id)

    changes: dict = {}

    if body.login is not None and body.login != user.login:
        existing = await db.execute(select(User).where(User.login == body.login))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Login already taken")
        changes["login"] = body.login
        user.login = body.login

    if body.password is not None:
        user.password_hash = hash_password(body.password)
        changes["action"] = "password_changed"

    if body.full_name is not None:
        changes["full_name"] = body.full_name
        user.full_name = body.full_name

    if body.lang is not None:
        changes["lang"] = body.lang.value
        user.lang = body.lang

    if body.is_active is not None and body.is_active != user.is_active:
        # Guard: cannot deactivate last active admin
        if not body.is_active and UserRole.admin in [UserRole(r) for r in user.roles]:
            count = await _count_active_admins(db)
            if count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot deactivate the last active administrator"
                )
        changes["is_active"] = body.is_active
        user.is_active = body.is_active

    if body.roles is not None:
        # Guard: if removing admin role and this is the last active admin
        old_roles = set(user.roles)
        new_roles = set(r.value for r in body.roles)
        removing_admin = UserRole.admin.value in old_roles and UserRole.admin.value not in new_roles
        if removing_admin and user.is_active:
            count = await _count_active_admins(db)
            if count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove admin role from the last active administrator"
                )

        # Rewrite user_roles via bulk DELETE to avoid ORM identity-map conflicts
        await db.execute(sql_delete(UserRoleEntry).where(UserRoleEntry.user_id == user.id))
        await db.flush()

        for role in body.roles:
            db.add(UserRoleEntry(id=uuid.uuid4(), user_id=user.id, role=role))

        changes["roles"] = [r.value for r in body.roles]

    await db.flush()
    if changes:
        await write_audit(db, admin.id, "user", user.id, AuditActionEnum.update, changes)
    await db.commit()

    result = await db.execute(
        select(User).options(selectinload(User.role_entries)).where(User.id == user.id)
    )
    return UserDetail.from_user(result.scalar_one())


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    user_id: uuid.UUID,
    body: ResetPasswordBody,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_ADMIN),
):
    user = await _get_user_or_404(db, user_id)
    new_pwd = body.password if body.password else _generate_password()
    user.password_hash = hash_password(new_pwd)
    await write_audit(db, admin.id, "user", user.id, AuditActionEnum.update,
                      {"action": "reset_password"})
    await db.commit()
    return ResetPasswordResponse(new_password=new_pwd)


@router.post("/{user_id}/toggle-active", response_model=UserDetail)
async def toggle_active(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_ADMIN),
):
    user = await _get_user_or_404(db, user_id)

    # Prevent self-block
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    # Guard last active admin
    if user.is_active and UserRole.admin in [UserRole(r) for r in user.roles]:
        count = await _count_active_admins(db)
        if count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot deactivate the last active administrator"
            )

    user.is_active = not user.is_active
    await write_audit(db, admin.id, "user", user.id, AuditActionEnum.update,
                      {"is_active": user.is_active})
    await db.commit()

    result = await db.execute(
        select(User).options(selectinload(User.role_entries)).where(User.id == user.id)
    )
    return UserDetail.from_user(result.scalar_one())
