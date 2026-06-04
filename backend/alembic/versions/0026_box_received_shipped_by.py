"""warehouse_box received_by, shipped_by

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("warehouse_boxes",
        sa.Column("received_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("warehouse_boxes",
        sa.Column("shipped_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("warehouse_boxes", "shipped_by")
    op.drop_column("warehouse_boxes", "received_by")
