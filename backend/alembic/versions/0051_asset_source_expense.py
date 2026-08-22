"""assets: source_expense_id (link office-deposit expense -> asset)

Revision ID: 0051
Revises: 0050
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0051'
down_revision = '0050'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('source_expense_id', UUID(as_uuid=True), nullable=True))
    op.create_unique_constraint('uq_assets_source_expense', 'assets', ['source_expense_id'])


def downgrade() -> None:
    op.drop_constraint('uq_assets_source_expense', 'assets', type_='unique')
    op.drop_column('assets', 'source_expense_id')
