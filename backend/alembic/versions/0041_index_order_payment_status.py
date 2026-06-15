"""index order payment statuses

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-15
"""
from alembic import op
from sqlalchemy import text

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

_indexes = [
    ("ix_orders_payment_status", "orders", "payment_status"),
    ("ix_orders_supplier_payment_status", "orders", "supplier_payment_status"),
    ("ix_orders_order_date", "orders", "order_date"),
    ("ix_orders_client_id", "orders", "client_id"),
]


def upgrade():
    conn = op.get_bind()
    for name, table, col in _indexes:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({col})"))


def downgrade():
    for name, table, _ in _indexes:
        op.drop_index(name, table_name=table)
