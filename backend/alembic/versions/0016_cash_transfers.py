"""cash transfers between registers"""
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table(
        "cash_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("from_register_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cash_registers.id"), nullable=False),
        sa.Column("to_register_id",   postgresql.UUID(as_uuid=True), sa.ForeignKey("cash_registers.id"), nullable=False),
        sa.Column("from_amount",   sa.Numeric(18, 2), nullable=False),
        sa.Column("to_amount",     sa.Numeric(18, 2), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(18, 8), nullable=False, server_default="1"),
        sa.Column("transfer_date", sa.Date, nullable=False),
        sa.Column("notes",         sa.Text, nullable=True),
        sa.Column("created_by",    postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("cash_transfers")
