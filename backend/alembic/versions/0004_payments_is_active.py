"""payments: add is_active column

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payments", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))


def downgrade():
    op.drop_column("payments", "is_active")
