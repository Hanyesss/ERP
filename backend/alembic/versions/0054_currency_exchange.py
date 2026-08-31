"""orders: currency-exchange fields (обмен валют)

Revision ID: 0054
Revises: 0053
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = '0054'
down_revision = '0053'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('exchange_amount', sa.Numeric(18, 4), nullable=True))
    op.add_column('orders', sa.Column('exchange_buy_currency', sa.String(10), nullable=True))
    op.add_column('orders', sa.Column('exchange_sell_currency', sa.String(10), nullable=True))
    op.add_column('orders', sa.Column('exchange_buy_rate', sa.Numeric(18, 8), nullable=True))
    op.add_column('orders', sa.Column('exchange_sell_rate', sa.Numeric(18, 8), nullable=True))

    # Вид деятельности «Обмен валют»
    op.execute(
        "INSERT INTO business_types (id, code, name, name_cn) "
        "SELECT gen_random_uuid(), 'currency_exchange', 'Обмен валют', '货币兑换' "
        "WHERE NOT EXISTS (SELECT 1 FROM business_types WHERE code = 'currency_exchange')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM business_types WHERE code = 'currency_exchange'")
    op.drop_column('orders', 'exchange_sell_rate')
    op.drop_column('orders', 'exchange_buy_rate')
    op.drop_column('orders', 'exchange_sell_currency')
    op.drop_column('orders', 'exchange_buy_currency')
    op.drop_column('orders', 'exchange_amount')
