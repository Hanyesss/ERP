"""logistics fields, order charges, file improvements, USD currency

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot run inside a transaction in PostgreSQL < 12
    # Using autocommit_block to commit first, then add enum values
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE ratecurrencyenum ADD VALUE IF NOT EXISTS 'USD'"))
        op.execute(sa.text("ALTER TYPE ordercurrencyenum ADD VALUE IF NOT EXISTS 'USD'"))
        op.execute(sa.text("ALTER TYPE currencyenum ADD VALUE IF NOT EXISTS 'USD'"))
        op.execute(sa.text("ALTER TYPE paymentcurrencyenum ADD VALUE IF NOT EXISTS 'USD'"))
        op.execute(sa.text("ALTER TYPE filetypeenum ADD VALUE IF NOT EXISTS 'cargo_photo'"))

    # Charge type enum (kept for reference, but column uses VARCHAR for flexibility)
    op.execute(sa.text(
        "CREATE TYPE chargetypeenum AS ENUM "
        "('delivery','insurance_percent','insurance_cost','china_delivery','extra_packing','loaders')"
    ))

    # Logistics fields in orders
    op.execute(sa.text("ALTER TABLE orders ADD COLUMN recipient TEXT"))
    op.execute(sa.text("ALTER TABLE orders ADD COLUMN destination TEXT"))
    op.execute(sa.text("ALTER TABLE orders ADD COLUMN arrival_date DATE"))
    op.execute(sa.text("ALTER TABLE orders ADD COLUMN tracking_number TEXT"))

    # Make trade-specific order_item columns nullable (logistics items may not have them)
    op.execute(sa.text("ALTER TABLE order_items ALTER COLUMN quantity DROP NOT NULL"))
    op.execute(sa.text("ALTER TABLE order_items ALTER COLUMN sale_price DROP NOT NULL"))
    op.execute(sa.text("ALTER TABLE order_items ALTER COLUMN cost_price DROP NOT NULL"))
    op.execute(sa.text("ALTER TABLE order_items ALTER COLUMN sale_currency DROP NOT NULL"))
    op.execute(sa.text("ALTER TABLE order_items ALTER COLUMN cost_currency DROP NOT NULL"))
    op.execute(sa.text("ALTER TABLE order_items ALTER COLUMN sale_rate_to_cny DROP NOT NULL"))
    op.execute(sa.text("ALTER TABLE order_items ALTER COLUMN cost_rate_to_cny DROP NOT NULL"))

    # Logistics fields in order_items
    op.execute(sa.text("ALTER TABLE order_items ADD COLUMN weight_kg NUMERIC(10,3)"))
    op.execute(sa.text("ALTER TABLE order_items ADD COLUMN volume_m3 NUMERIC(10,3)"))
    op.execute(sa.text("ALTER TABLE order_items ADD COLUMN density_kg_m3 NUMERIC(10,2)"))
    op.execute(sa.text("ALTER TABLE order_items ADD COLUMN price_per_kg NUMERIC(18,2)"))
    op.execute(sa.text("ALTER TABLE order_items ADD COLUMN price_per_kg_currency VARCHAR(10)"))
    op.execute(sa.text("ALTER TABLE order_items ADD COLUMN cargo_value NUMERIC(18,2)"))
    op.execute(sa.text("ALTER TABLE order_items ADD COLUMN cargo_value_currency VARCHAR(10)"))
    op.execute(sa.text("ALTER TABLE order_items ADD COLUMN places_count INTEGER"))

    # Add missing columns to order_files
    op.execute(sa.text("ALTER TABLE order_files ADD COLUMN IF NOT EXISTS file_size_bytes INTEGER"))
    op.execute(sa.text("ALTER TABLE order_files ADD COLUMN IF NOT EXISTS mime_type TEXT"))

    # Logistics cost breakdown table
    op.execute(sa.text("""
        CREATE TABLE order_charges (
            id UUID PRIMARY KEY,
            order_id UUID NOT NULL REFERENCES orders(id),
            charge_type VARCHAR(50) NOT NULL,
            amount NUMERIC(18,2) NOT NULL,
            currency VARCHAR(10) NOT NULL,
            amount_cny NUMERIC(18,2) NOT NULL,
            rate_to_cny NUMERIC(18,8) NOT NULL,
            notes TEXT
        )
    """))

    # Seed USD/CNY rate for today (skip if already exists)
    op.execute(sa.text("""
        INSERT INTO exchange_rates (id, currency, rate_to_cny, rate_date, created_by, source, created_at)
        SELECT
            gen_random_uuid(),
            'USD',
            7.10,
            CURRENT_DATE,
            (SELECT id FROM users WHERE role = 'admin' ORDER BY created_at LIMIT 1),
            'manual',
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM exchange_rates WHERE currency = 'USD' AND rate_date = CURRENT_DATE
        )
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS order_charges"))
    op.execute(sa.text("DROP TYPE IF EXISTS chargetypeenum"))
    # Note: removing enum values (USD, cargo_photo) is not supported in PostgreSQL
    # To fully revert, drop and recreate affected enums with the old values
