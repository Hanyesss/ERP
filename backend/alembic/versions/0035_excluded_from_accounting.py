"""excluded_from_accounting field for orders and purchases

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("excluded_from_accounting", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("purchases", sa.Column("excluded_from_accounting", sa.Boolean(), nullable=False, server_default="false"))


def downgrade():
    op.drop_column("orders", "excluded_from_accounting")
    op.drop_column("purchases", "excluded_from_accounting")
