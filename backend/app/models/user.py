import uuid
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import TimestampMixin


class UserRole(str, PyEnum):
    employee = "employee"
    manager = "manager"
    accountant = "accountant"
    admin = "admin"


class UserLang(str, PyEnum):
    ru = "ru"
    zh = "zh"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="userrole"), nullable=False)
    lang: Mapped[UserLang] = mapped_column(Enum(UserLang, name="userlang"), default=UserLang.ru, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
