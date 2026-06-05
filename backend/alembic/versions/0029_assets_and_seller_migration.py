"""assets table and migrate manager->seller

Revision ID: 0029
Revises: 0028
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migrate existing manager role entries to seller
    op.execute(sa.text("UPDATE user_roles SET role = 'seller' WHERE role = 'manager'"))

    # Create assets table
    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("account", sa.String(500), nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("assets")
    op.execute(sa.text("UPDATE user_roles SET role = 'manager' WHERE role = 'seller'"))
