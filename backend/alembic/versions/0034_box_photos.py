"""box_photos table — до 3 фото на коробку

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-07
"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "box_photos",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("box_id", UUID(as_uuid=True), nullable=False),
        sa.Column("photo_path", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["box_id"], ["warehouse_boxes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_box_photos_box_id", "box_photos", ["box_id"])

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, photo_path FROM warehouse_boxes WHERE photo_path IS NOT NULL AND photo_path <> ''")
    ).fetchall()
    if rows:
        conn.execute(
            sa.text(
                "INSERT INTO box_photos (id, box_id, photo_path, sort_order) "
                "VALUES (:id, :box_id, :photo_path, 0)"
            ),
            [{"id": uuid.uuid4(), "box_id": r[0], "photo_path": r[1]} for r in rows],
        )


def downgrade():
    op.drop_index("ix_box_photos_box_id", table_name="box_photos")
    op.drop_table("box_photos")
