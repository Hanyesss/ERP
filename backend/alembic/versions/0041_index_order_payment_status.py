"""index order payment statuses

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-15
"""
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_orders_payment_status", "orders", ["payment_status"])
    op.create_index("ix_orders_supplier_payment_status", "orders", ["supplier_payment_status"])
    op.create_index("ix_orders_order_date", "orders", ["order_date"])
    op.create_index("ix_orders_client_id", "orders", ["client_id"])


def downgrade():
    op.drop_index("ix_orders_payment_status", table_name="orders")
    op.drop_index("ix_orders_supplier_payment_status", table_name="orders")
    op.drop_index("ix_orders_order_date", table_name="orders")
    op.drop_index("ix_orders_client_id", table_name="orders")
