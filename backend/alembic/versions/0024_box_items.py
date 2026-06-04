"""box_items — позиции товаров внутри коробки

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "box_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("box_id", UUID(as_uuid=True),
                  sa.ForeignKey("warehouse_boxes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("photo_path", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_box_items_box_id", "box_items", ["box_id"])

    # Переносим item_name существующих коробок как первую позицию
    op.execute("""
        INSERT INTO box_items (id, box_id, name, quantity, sort_order)
        SELECT gen_random_uuid(), id, item_name, 1, 0
        FROM warehouse_boxes
        WHERE item_name IS NOT NULL AND item_name != ''
    """)


def downgrade() -> None:
    op.drop_index("ix_box_items_box_id", "box_items")
    op.drop_table("box_items")
