"""stock: purchase_items as stock lines + stock_allocations (склад/остаток)

Revision ID: 0055
Revises: 0054
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0055'
down_revision = '0054'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Складская позиция = purchase_item без привязки к заказу (order_item_id NULL) + собственное имя
    op.alter_column('purchase_items', 'order_item_id', existing_type=UUID(as_uuid=True), nullable=True)
    op.add_column('purchase_items', sa.Column('name', sa.String(255), nullable=True))
    op.add_column('purchase_items', sa.Column('name_cn', sa.String(255), nullable=True))
    op.add_column('purchase_items', sa.Column('unit', sa.String(50), nullable=True))
    op.add_column('purchase_items', sa.Column('is_stock', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # Списание со склада: сколько единиц складской позиции ушло в позицию заказа
    op.create_table(
        'stock_allocations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('purchase_item_id', UUID(as_uuid=True), sa.ForeignKey('purchase_items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('order_item_id', UUID(as_uuid=True), sa.ForeignKey('order_items.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('quantity', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('cost_amount_cny', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('stock_allocations')
    op.drop_column('purchase_items', 'is_stock')
    op.drop_column('purchase_items', 'unit')
    op.drop_column('purchase_items', 'name_cn')
    op.drop_column('purchase_items', 'name')
    op.alter_column('purchase_items', 'order_item_id', existing_type=UUID(as_uuid=True), nullable=False)
