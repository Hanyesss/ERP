"""purchase_files table and user is_deleted flag"""
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table(
        "purchase_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchases.id"), nullable=False),
        sa.Column("file_url", sa.String(1000), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_purchase_files_purchase_id", "purchase_files", ["purchase_id"])

    op.add_column("users", sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"))


def downgrade():
    op.drop_column("users", "is_deleted")
    op.drop_table("purchase_files")
