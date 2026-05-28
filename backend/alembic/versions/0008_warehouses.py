"""warehouses: add warehouses table and warehouse_id to orders"""
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.create_table(
        "warehouses",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_cn", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column("orders", sa.Column(
        "warehouse_id",
        sa.dialects.postgresql.UUID(as_uuid=True),
        sa.ForeignKey("warehouses.id"),
        nullable=True,
    ))


def downgrade():
    op.drop_column("orders", "warehouse_id")
    op.drop_table("warehouses")
