"""add code field to counterparties"""
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.add_column("counterparties", sa.Column("code", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("counterparties", "code")
