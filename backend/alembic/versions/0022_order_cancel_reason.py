"""order cancel_reason field

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.add_column("expenses", sa.Column("cash_amount_in_register", sa.Numeric(18, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "cash_amount_in_register")
    op.drop_column("orders", "cancel_reason")
