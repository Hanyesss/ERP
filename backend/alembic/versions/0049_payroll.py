"""payroll: employees, monthly records, daily attendance

Revision ID: 0049
Revises: 0048
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0049'
down_revision = '0048'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'payroll_employees',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('position', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'payroll_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('payroll_employees.id', ondelete='CASCADE'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('monthly_salary', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('working_days', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('social_insurance', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('bonus', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('is_paid', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('paid_expense_id', UUID(as_uuid=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('employee_id', 'year', 'month', name='uq_payroll_record_emp_month'),
    )
    op.create_index('ix_payroll_records_employee_id', 'payroll_records', ['employee_id'])
    op.create_table(
        'payroll_attendance',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('record_id', UUID(as_uuid=True), sa.ForeignKey('payroll_records.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day', sa.Integer(), nullable=False),
        sa.Column('attended', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('overtime_hours', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.UniqueConstraint('record_id', 'day', name='uq_payroll_att_record_day'),
    )
    op.create_index('ix_payroll_attendance_record_id', 'payroll_attendance', ['record_id'])


def downgrade() -> None:
    op.drop_table('payroll_attendance')
    op.drop_table('payroll_records')
    op.drop_table('payroll_employees')
