"""expense qr_url — QR-фото для возмещений

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("expenses", sa.Column("qr_url", sa.String(1000), nullable=True))


def downgrade():
    op.drop_column("expenses", "qr_url")
