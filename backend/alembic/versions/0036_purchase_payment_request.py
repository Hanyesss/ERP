"""purchase payment_requested fields + payments file_url index

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchases", sa.Column(
        "payment_requested", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("purchases", sa.Column(
        "payment_requested_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
    ))
    op.add_column("purchases", sa.Column(
        "payment_requested_at", sa.DateTime(timezone=True), nullable=True
    ))
    op.create_foreign_key(
        "fk_purchases_payment_requested_by",
        "purchases", "users",
        ["payment_requested_by"], ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_purchases_payment_requested_by", "purchases", type_="foreignkey")
    op.drop_column("purchases", "payment_requested_at")
    op.drop_column("purchases", "payment_requested_by")
    op.drop_column("purchases", "payment_requested")
