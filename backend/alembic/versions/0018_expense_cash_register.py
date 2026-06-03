"""expense cash_register_id"""
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.add_column(
        "expenses",
        sa.Column("cash_register_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cash_registers.id"), nullable=True),
    )


def downgrade():
    op.drop_column("expenses", "cash_register_id")
