"""expenses module: is_active column + worker1 user"""
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

import uuid
import sqlalchemy as sa
from alembic import op

WORKER_ID = "11111111-aaaa-bbbb-cccc-000000000001"
WORKER_ROLE_ID = "11111111-aaaa-bbbb-cccc-000000000002"
WORKER_HASH = "$2b$12$Df1jIefffBh/71pIhcOis.pOIb6TAoj6BuwsUJv5GxlttC0czrQCa"


def upgrade():
    op.add_column("expenses", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))

    op.execute(sa.text(f"""
        INSERT INTO users (id, login, password_hash, full_name, is_active, lang, created_at)
        VALUES ('{WORKER_ID}', 'worker1', '{WORKER_HASH}',
                'Иван Грузчик / 装卸工伊万', true, 'ru', now())
        ON CONFLICT (login) DO NOTHING
    """))
    op.execute(sa.text(f"""
        INSERT INTO user_roles (id, user_id, role, created_at)
        SELECT '{WORKER_ROLE_ID}', id, 'employee', now()
        FROM users WHERE login = 'worker1'
        ON CONFLICT DO NOTHING
    """))


def downgrade():
    op.drop_column("expenses", "is_active")
    op.execute(sa.text("DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE login = 'worker1')"))
    op.execute(sa.text("DELETE FROM users WHERE login = 'worker1'"))
