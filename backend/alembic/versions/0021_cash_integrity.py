"""cash integrity: initial_balance, CashTransaction.is_active

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Начальный баланс кассы
    op.add_column("cash_registers",
        sa.Column("initial_balance", sa.Numeric(18, 2), nullable=False, server_default="0"))

    # Флаг активности кассовой транзакции
    op.add_column("cash_transactions",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.create_index("ix_cash_transactions_is_active", "cash_transactions", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_cash_transactions_is_active", "cash_transactions")
    op.drop_column("cash_transactions", "is_active")
    op.drop_column("cash_registers", "initial_balance")
