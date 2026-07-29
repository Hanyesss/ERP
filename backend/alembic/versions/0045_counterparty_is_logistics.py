"""add is_logistics flag to counterparties

Revision ID: 0045
Revises: 0044
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = '0045'
down_revision = '0044'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('counterparties', sa.Column(
        'is_logistics', sa.Boolean(), server_default=sa.text('false'), nullable=False
    ))


def downgrade() -> None:
    op.drop_column('counterparties', 'is_logistics')
