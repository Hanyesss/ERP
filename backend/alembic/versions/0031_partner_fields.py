"""partner linkage fields on counterparties and users

Revision ID: 0031
Revises: 0030
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "counterparties",
        sa.Column("partner_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_counterparties_partner_id",
        "counterparties", "counterparties",
        ["partner_id"], ["id"],
    )
    op.add_column(
        "users",
        sa.Column("partner_counterparty_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_partner_counterparty_id",
        "users", "counterparties",
        ["partner_counterparty_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_partner_counterparty_id", "users", type_="foreignkey")
    op.drop_column("users", "partner_counterparty_id")
    op.drop_constraint("fk_counterparties_partner_id", "counterparties", type_="foreignkey")
    op.drop_column("counterparties", "partner_id")
