"""integration_settings table and sync fields on orders"""
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table(
        "integration_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("integration_name", sa.Text(), nullable=False, unique=True),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("api_token", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.Text(), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.add_column("orders", sa.Column("external_shipment_id", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("external_shipment_number", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("external_invoice_url", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("external_tracking_url", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("sync_status", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("sync_error", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("orders", "synced_at")
    op.drop_column("orders", "sync_error")
    op.drop_column("orders", "sync_status")
    op.drop_column("orders", "external_tracking_url")
    op.drop_column("orders", "external_invoice_url")
    op.drop_column("orders", "external_shipment_number")
    op.drop_column("orders", "external_shipment_id")
    op.drop_table("integration_settings")
