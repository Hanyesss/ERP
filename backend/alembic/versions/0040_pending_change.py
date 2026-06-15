"""add pending_change to expenses and payments"""
revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.add_column("expenses", sa.Column("pending_change", sa.Text(), nullable=True))
    op.add_column("payments", sa.Column("pending_change", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("expenses", "pending_change")
    op.drop_column("payments", "pending_change")
