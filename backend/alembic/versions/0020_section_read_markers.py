"""section_read_markers

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "section_read_markers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(50), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "section", name="uq_section_read_marker"),
    )
    op.create_index("ix_section_read_markers_user_id", "section_read_markers", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_section_read_markers_user_id", "section_read_markers")
    op.drop_table("section_read_markers")
