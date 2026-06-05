"""add seller to userrole enum

Revision ID: 0028
Revises: 0027
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'seller'"))


def downgrade() -> None:
    pass  # Cannot remove enum values in PostgreSQL
