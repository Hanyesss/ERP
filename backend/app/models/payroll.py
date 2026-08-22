import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String, Numeric, Integer, Boolean, ForeignKey, DateTime,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class PayrollEmployee(Base):
    """Работник для расчёта зарплаты (отдельный список, не пользователи системы)."""
    __tablename__ = "payroll_employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, unique=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PayrollRecord(Base):
    """Месячный расчёт зарплаты одного работника. Все суммы в CNY."""
    __tablename__ = "payroll_records"
    __table_args__ = (
        UniqueConstraint("employee_id", "year", "month", name="uq_payroll_record_emp_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..12
    monthly_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    working_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="24")
    social_insurance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    taxes: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    bonus: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paid_expense_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    employee: Mapped["PayrollEmployee"] = relationship("PayrollEmployee")
    attendance: Mapped[list["PayrollAttendance"]] = relationship(
        "PayrollAttendance", back_populates="record", cascade="all, delete-orphan"
    )


class PayrollAttendance(Base):
    """Табель: один день месяца — присутствие + часы переработки."""
    __tablename__ = "payroll_attendance"
    __table_args__ = (
        UniqueConstraint("record_id", "day", name="uq_payroll_att_record_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..31
    attended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, server_default="0")

    record: Mapped["PayrollRecord"] = relationship("PayrollRecord", back_populates="attendance")
