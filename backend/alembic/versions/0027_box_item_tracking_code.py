"""box_items.tracking_code

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("box_items",
        sa.Column("tracking_code", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("box_items", "tracking_code")
