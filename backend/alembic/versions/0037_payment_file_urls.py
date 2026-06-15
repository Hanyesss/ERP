"""payment_file_urls — поддержка до 10 файлов на платёж

Revision ID: 0037
Revises: 0036
Create Date: 2026-06-15
"""
import json
from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payments", sa.Column("file_urls", sa.Text(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, file_url FROM payments WHERE file_url IS NOT NULL AND file_url <> ''")
    ).fetchall()
    if rows:
        for row in rows:
            conn.execute(
                sa.text("UPDATE payments SET file_urls = :urls WHERE id = :id"),
                {"urls": json.dumps([row[1]]), "id": str(row[0])},
            )


def downgrade():
    op.drop_column("payments", "file_urls")
