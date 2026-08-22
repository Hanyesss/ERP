"""payroll_employees: link to system user (user_id)

Revision ID: 0050
Revises: 0049
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0050'
down_revision = '0049'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('payroll_employees', sa.Column('user_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_payroll_employee_user', 'payroll_employees', 'users', ['user_id'], ['id'])
    op.create_unique_constraint('uq_payroll_employee_user', 'payroll_employees', ['user_id'])


def downgrade() -> None:
    op.drop_constraint('uq_payroll_employee_user', 'payroll_employees', type_='unique')
    op.drop_constraint('fk_payroll_employee_user', 'payroll_employees', type_='foreignkey')
    op.drop_column('payroll_employees', 'user_id')
