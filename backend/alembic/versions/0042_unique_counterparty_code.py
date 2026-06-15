"""unique constraint on counterparties.code

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-15
"""
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_counterparties_code", "counterparties", ["code"])


def downgrade():
    op.drop_constraint("uq_counterparties_code", "counterparties", type_="unique")
