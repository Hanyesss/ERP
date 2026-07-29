"""logistics supplier quotes: quote_requests + supplier_quotes

Revision ID: 0044
Revises: 0043
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0044'
down_revision = '0043'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'quote_requests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', UUID(as_uuid=True), sa.ForeignKey('orders.id'), nullable=True),
        sa.Column('order_number', sa.String(120), nullable=True),
        sa.Column('product_name', sa.Text(), nullable=True),
        sa.Column('cargo_value', sa.String(120), nullable=True),
        sa.Column('box', sa.String(120), nullable=True),
        sa.Column('dimensions', sa.Text(), nullable=True),
        sa.Column('volume_m3', sa.Numeric(18, 3), nullable=True),
        sa.Column('weight_kg', sa.Numeric(18, 2), nullable=True),
        sa.Column('destination', sa.String(255), nullable=True),
        sa.Column('dispatch_place', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('selected_quote_id', UUID(as_uuid=True), nullable=True),
        sa.Column('selected_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('selected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )
    op.create_index('ix_quote_requests_order_id', 'quote_requests', ['order_id'])

    priceunit = sa.Enum('per_kg', 'per_cbm', name='priceunitenum')
    priceunit.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'supplier_quotes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', UUID(as_uuid=True),
                  sa.ForeignKey('quote_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('supplier_id', UUID(as_uuid=True), sa.ForeignKey('counterparties.id'), nullable=False),
        sa.Column('price', sa.Numeric(18, 4), nullable=False),
        sa.Column('price_unit', priceunit, server_default='per_kg', nullable=False),
        sa.Column('currency', sa.String(10), server_default='USD', nullable=False),
        sa.Column('delivery_days', sa.String(120), nullable=True),
        sa.Column('insurance_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_supplier_quotes_request_id', 'supplier_quotes', ['request_id'])


def downgrade() -> None:
    op.drop_index('ix_supplier_quotes_request_id', 'supplier_quotes')
    op.drop_table('supplier_quotes')
    op.drop_index('ix_quote_requests_order_id', 'quote_requests')
    op.drop_table('quote_requests')
    sa.Enum(name='priceunitenum').drop(op.get_bind(), checkfirst=True)
