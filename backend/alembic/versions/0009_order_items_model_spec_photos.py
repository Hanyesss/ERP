"""order_items: add model/specification; create order_item_photos"""
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    op.add_column("order_items", sa.Column("model", sa.Text(), nullable=True))
    op.add_column("order_items", sa.Column("specification", sa.Text(), nullable=True))

    op.create_table(
        "order_item_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_order_item_photos_item_id", "order_item_photos", ["order_item_id"])


def downgrade():
    op.drop_table("order_item_photos")
    op.drop_column("order_items", "specification")
    op.drop_column("order_items", "model")
