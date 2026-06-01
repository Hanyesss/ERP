import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Numeric, Date, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class CashTransfer(Base):
    __tablename__ = "cash_transfers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_register_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_registers.id"), nullable=False)
    to_register_id:   Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_registers.id"), nullable=False)
    from_amount:   Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    to_amount:     Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("1"))
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
