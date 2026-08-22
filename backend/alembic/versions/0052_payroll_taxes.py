"""payroll_records: taxes (manual, subtracted from salary)

Revision ID: 0052
Revises: 0051
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa

revision = '0052'
down_revision = '0051'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('payroll_records', sa.Column('taxes', sa.Numeric(14, 2), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('payroll_records', 'taxes')
