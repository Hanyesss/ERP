"""warehouse boxes and packing lists"""
revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    op.execute("""
        CREATE TYPE boxstatus AS ENUM ('on_warehouse', 'shipped')
    """)

    op.execute("""
        CREATE TABLE warehouse_boxes (
            id UUID PRIMARY KEY,
            box_code VARCHAR(50) UNIQUE NOT NULL,
            counterparty_id UUID NOT NULL REFERENCES counterparties(id),
            warehouse_id UUID NOT NULL REFERENCES warehouses(id),
            weight NUMERIC(12, 3) NOT NULL,
            volume NUMERIC(12, 4) NOT NULL,
            density NUMERIC(12, 3) NOT NULL DEFAULT 0,
            item_name VARCHAR(255) NOT NULL,
            description TEXT,
            photo_path VARCHAR(500),
            status boxstatus NOT NULL DEFAULT 'on_warehouse',
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            shipped_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX ix_warehouse_boxes_box_code ON warehouse_boxes(box_code)")
    op.execute("CREATE INDEX ix_warehouse_boxes_counterparty ON warehouse_boxes(counterparty_id)")
    op.execute("CREATE INDEX ix_warehouse_boxes_warehouse_id ON warehouse_boxes(warehouse_id)")
    op.execute("CREATE INDEX ix_warehouse_boxes_status ON warehouse_boxes(status)")

    op.execute("""
        CREATE TABLE packing_lists (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            pdf_path VARCHAR(500),
            box_ids JSONB NOT NULL,
            total_weight NUMERIC(14, 3),
            total_volume NUMERIC(14, 4),
            total_boxes INTEGER,
            created_by UUID NOT NULL REFERENCES users(id)
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS packing_lists")
    op.execute("DROP TABLE IF EXISTS warehouse_boxes")
    op.execute("DROP TYPE IF EXISTS boxstatus")
