"""add packaging expense categories"""
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op

NEW_CATEGORIES = [
    ("c1000001-0000-0000-0000-000000000013", "Упаковка", "包装费"),
    ("c1000001-0000-0000-0000-000000000014", "Материалы для упаковки", "包装材料"),
]


def upgrade():
    for cat_id, name, name_cn in NEW_CATEGORIES:
        op.execute(sa.text(f"""
            INSERT INTO expense_categories (id, name, name_cn, is_active)
            VALUES ('{cat_id}', '{name}', '{name_cn}', true)
            ON CONFLICT (id) DO NOTHING
        """))


def downgrade():
    ids = ", ".join(f"'{c[0]}'" for c in NEW_CATEGORIES)
    op.execute(sa.text(f"DELETE FROM expense_categories WHERE id IN ({ids})"))
