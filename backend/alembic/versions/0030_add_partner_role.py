"""add partner to userrole and counterpartytype enums

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE must run outside a transaction block on older PG; run in autocommit
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'partner'"))
        op.execute(sa.text("ALTER TYPE counterpartytype ADD VALUE IF NOT EXISTS 'partner'"))


def downgrade() -> None:
    pass  # Cannot remove enum values in PostgreSQL
