"""quote_requests: client_price + box to Text

Revision ID: 0048
Revises: 0047
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa

revision = '0048'
down_revision = '0047'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('quote_requests', sa.Column('client_price', sa.Numeric(18, 4), nullable=True))
    op.alter_column('quote_requests', 'box', type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column('quote_requests', 'box', type_=sa.String(120), existing_nullable=True)
    op.drop_column('quote_requests', 'client_price')
