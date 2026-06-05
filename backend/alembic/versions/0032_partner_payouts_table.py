"""partner_payouts table and commission expense category

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

_COMMISSION_CATEGORY_ID = "c1000001-0000-0000-0000-000000000013"


def upgrade() -> None:
    op.create_table(
        "partner_payouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("partner_counterparty_id", UUID(as_uuid=True),
                  sa.ForeignKey("counterparties.id"), nullable=False),
        sa.Column("period_from", sa.Date, nullable=True),
        sa.Column("period_to", sa.Date, nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("expense_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index(
        "ix_partner_payouts_partner",
        "partner_payouts", ["partner_counterparty_id"],
    )

    # Seed "Комиссия / Бонус партнёру" expense category
    op.execute(sa.text(f"""
        INSERT INTO expense_categories (id, name, name_cn, is_active)
        VALUES ('{_COMMISSION_CATEGORY_ID}', 'Комиссия / Бонус партнёру', '合伙人佣金', true)
        ON CONFLICT (id) DO NOTHING
    """))


def downgrade() -> None:
    op.execute(sa.text(f"DELETE FROM expense_categories WHERE id = '{_COMMISSION_CATEGORY_ID}'"))
    op.drop_index("ix_partner_payouts_partner", table_name="partner_payouts")
    op.drop_table("partner_payouts")
