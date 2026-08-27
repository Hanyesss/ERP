"""net inbound: orders.source/external_ref/cargo_status + net_status_events

Revision ID: 0053
Revises: 0052
Create Date: 2026-08-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0053'
down_revision = '0052'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # orders: источник заказа + ключ идемпотентности NET + последний статус груза
    op.add_column('orders', sa.Column('source', sa.String(16), nullable=False, server_default='erp'))
    op.add_column('orders', sa.Column('external_ref', sa.String(64), nullable=True))
    op.add_column('orders', sa.Column('cargo_status', sa.String(40), nullable=True))
    op.add_column('orders', sa.Column('cargo_status_label', sa.String(120), nullable=True))
    op.add_column('orders', sa.Column('cargo_status_at', sa.DateTime(timezone=True), nullable=True))

    op.create_index('ix_orders_source', 'orders', ['source'])
    # уникальность external_ref только среди NET-заказов
    op.create_index(
        'uq_orders_external_ref_net', 'orders', ['external_ref'],
        unique=True, postgresql_where=sa.text("source = 'net'"),
    )

    # история движения груза NET
    op.create_table(
        'net_status_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(40), nullable=False),
        sa.Column('label', sa.String(120), nullable=True),
        sa.Column('lifecycle', sa.String(16), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('order_id', 'code', 'occurred_at', name='uq_net_status_event'),
    )
    op.create_index('ix_net_status_events_order_id', 'net_status_events', ['order_id'])


def downgrade() -> None:
    op.drop_index('ix_net_status_events_order_id', table_name='net_status_events')
    op.drop_table('net_status_events')
    op.drop_index('uq_orders_external_ref_net', table_name='orders')
    op.drop_index('ix_orders_source', table_name='orders')
    op.drop_column('orders', 'cargo_status_at')
    op.drop_column('orders', 'cargo_status_label')
    op.drop_column('orders', 'cargo_status')
    op.drop_column('orders', 'external_ref')
    op.drop_column('orders', 'source')
