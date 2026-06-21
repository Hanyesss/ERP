"""add trontok fields to counterparties and payments

Revision ID: 0043
Revises: 0042
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = '0043'
down_revision = '0042'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('counterparties', sa.Column(
        'trontok_linked', sa.Boolean(), server_default=sa.text('false'), nullable=False
    ))
    op.add_column('counterparties', sa.Column(
        'trontok_provisioned_at', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('payments', sa.Column('external_tx_id', sa.Text(), nullable=True))
    op.add_column('payments', sa.Column('payment_source', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('payments', 'payment_source')
    op.drop_column('payments', 'external_tx_id')
    op.drop_column('counterparties', 'trontok_provisioned_at')
    op.drop_column('counterparties', 'trontok_linked')
