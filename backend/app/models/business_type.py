import uuid
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class BusinessType(Base):
    __tablename__ = "business_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_cn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
