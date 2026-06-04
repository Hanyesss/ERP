"""warehouse_box.tracking_number

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("warehouse_boxes",
        sa.Column("tracking_number", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("warehouse_boxes", "tracking_number")
