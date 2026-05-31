"""add cash registers and cash transactions"""
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table(
        "cash_registers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "cash_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cash_register_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cash_registers.id"), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("direction", sa.Enum("in", "out", name="txdirection"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 2), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column("payments", sa.Column(
        "cash_register_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("cash_registers.id"),
        nullable=True,
    ))


def downgrade():
    op.drop_column("payments", "cash_register_id")
    op.drop_table("cash_transactions")
    op.drop_table("cash_registers")
    op.execute("DROP TYPE IF EXISTS txdirection")
