"""purchases: add order_id for logistics purchases"""
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.add_column("purchases", sa.Column(
        "order_id",
        sa.dialects.postgresql.UUID(as_uuid=True),
        sa.ForeignKey("orders.id"),
        nullable=True,
    ))


def downgrade():
    op.drop_column("purchases", "order_id")
