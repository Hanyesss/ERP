"""remove duplicate Аренда офиса category"""
revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op

_OLD_ID = "23a59ba6-18f5-4587-b3de-46d05d649618"
_NEW_ID = "c1000001-0000-0000-0000-000000000001"


def upgrade():
    op.execute(sa.text(f"""
        UPDATE expenses SET category_id = '{_NEW_ID}'
        WHERE category_id = '{_OLD_ID}'
    """))
    op.execute(sa.text(f"DELETE FROM expense_categories WHERE id = '{_OLD_ID}'"))


def downgrade():
    op.execute(sa.text(f"""
        INSERT INTO expense_categories (id, name, name_cn, is_active)
        VALUES ('{_OLD_ID}', 'Аренда офиса', '办公室租金', true)
        ON CONFLICT (id) DO NOTHING
    """))
