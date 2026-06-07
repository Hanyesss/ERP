"""box_item_photos table — до 3 фото на позицию коробки

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "box_item_photos",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("box_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("photo_path", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["box_item_id"], ["box_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_box_item_photos_box_item_id", "box_item_photos", ["box_item_id"])

    # Мигрируем существующие одиночные фото из box_items.photo_path
    op.execute("""
        INSERT INTO box_item_photos (id, box_item_id, photo_path, sort_order)
        SELECT gen_random_uuid(), id, photo_path, 0
        FROM box_items
        WHERE photo_path IS NOT NULL AND photo_path <> ''
    """)


def downgrade():
    op.drop_index("ix_box_item_photos_box_item_id", table_name="box_item_photos")
    op.drop_table("box_item_photos")
