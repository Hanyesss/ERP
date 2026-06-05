import uuid
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import TimestampMixin


class UserRole(str, PyEnum):
    employee = "employee"
    seller = "seller"
    manager = "manager"
    purchaser = "purchaser"
    accountant = "accountant"
    admin = "admin"
    partner = "partner"


# Alias used by user_role.py
UserRoleEnum = UserRole


class UserLang(str, PyEnum):
    ru = "ru"
    zh = "zh"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    lang: Mapped[UserLang] = mapped_column(Enum(UserLang, name="userlang"), default=UserLang.ru, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Links a partner user to their partner counterparty
    partner_counterparty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=True
    )

    role_entries: Mapped[list["UserRoleEntry"]] = relationship(  # type: ignore[name-defined]
        "UserRoleEntry", foreign_keys="UserRoleEntry.user_id", lazy="selectin"
    )

    @property
    def roles(self) -> list[str]:
        return [r.role for r in self.role_entries]

    def has_role(self, *roles: str) -> bool:
        user_roles = set(self.roles)
        return bool(user_roles.intersection(roles))
