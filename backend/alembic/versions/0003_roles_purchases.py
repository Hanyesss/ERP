"""roles many-to-many, purchases, purchase_items

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Add 'purchaser' to userrole enum ───────────────────────────────────
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'purchaser'"))

    # ── 2. Create user_roles (many-to-many) ───────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_roles (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role        userrole NOT NULL,
            created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(user_id, role)
        )
    """))

    # ── 3. Migrate existing roles from users.role → user_roles ────────────────
    op.execute(sa.text("""
        INSERT INTO user_roles (id, user_id, role, created_at)
        SELECT gen_random_uuid(), id, role, NOW()
        FROM users
        WHERE role IS NOT NULL
        ON CONFLICT (user_id, role) DO NOTHING
    """))

    # ── 4. Drop role column from users ────────────────────────────────────────
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS role"))

    # ── 5. Create purchases table ─────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TYPE purchasecurrencyenum AS ENUM ('CNY', 'RUB', 'USDT', 'USD')
    """))
    op.execute(sa.text("""
        CREATE TYPE purchasepaymentstatus AS ENUM ('unpaid', 'partial', 'paid')
    """))
    op.execute(sa.text("""
        CREATE TABLE purchases (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            purchase_number  TEXT UNIQUE NOT NULL,
            company_id       UUID NOT NULL REFERENCES companies(id),
            supplier_id      UUID NOT NULL REFERENCES counterparties(id),
            purchase_date    DATE NOT NULL,
            currency         purchasecurrencyenum NOT NULL DEFAULT 'CNY',
            total_amount     NUMERIC(18,2) NOT NULL DEFAULT 0,
            rate_to_cny      NUMERIC(18,8) NOT NULL DEFAULT 1,
            total_amount_cny NUMERIC(18,2) NOT NULL DEFAULT 0,
            payment_status   purchasepaymentstatus NOT NULL DEFAULT 'unpaid',
            notes            TEXT,
            created_by       UUID REFERENCES users(id),
            created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_deleted       BOOLEAN NOT NULL DEFAULT FALSE
        )
    """))

    # ── 6. Create purchase_items table ────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE purchase_items (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            purchase_id    UUID NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
            order_item_id  UUID NOT NULL REFERENCES order_items(id),
            quantity       NUMERIC(18,4) NOT NULL DEFAULT 0,
            cost_price     NUMERIC(18,2) NOT NULL DEFAULT 0,
            cost_amount    NUMERIC(18,2) NOT NULL DEFAULT 0
        )
    """))

    # ── 7. Create purchase_payments_link table ────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE purchase_payments_link (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            payment_id  UUID NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
            purchase_id UUID NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
            amount_cny  NUMERIC(18,2) NOT NULL DEFAULT 0,
            notes       TEXT
        )
    """))

    # ── 8. Rename supplier_id → preferred_supplier_id in order_items ──────────
    op.execute(sa.text(
        "ALTER TABLE order_items RENAME COLUMN supplier_id TO preferred_supplier_id"
    ))

    # ── 9. Migrate existing cost data from order_items → purchases ────────────
    # For each distinct (order_id, preferred_supplier_id, cost_currency) group,
    # create one purchase and corresponding purchase_items.
    # Uses the order_date from the parent order.
    existing = conn.execute(sa.text("""
        SELECT
            oi.id            AS item_id,
            oi.order_id,
            o.order_date,
            o.company_id,
            o.order_number,
            oi.preferred_supplier_id,
            oi.cost_price,
            oi.cost_currency,
            oi.cost_rate_to_cny,
            oi.quantity
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE oi.cost_price IS NOT NULL AND oi.cost_price > 0
        ORDER BY oi.order_id, oi.preferred_supplier_id, oi.cost_currency
    """)).fetchall()

    if existing:
        # Group by (order_id, preferred_supplier_id, cost_currency)
        from collections import defaultdict
        import uuid as _uuid

        groups: dict = defaultdict(list)
        for row in existing:
            key = (str(row.order_id), str(row.preferred_supplier_id) if row.preferred_supplier_id else "NONE", row.cost_currency or "CNY")
            groups[key].append(row)

        # We need a fallback supplier for items without preferred_supplier_id
        # Use a placeholder: try to find any supplier, else skip
        fallback_supplier = conn.execute(sa.text("""
            SELECT id FROM counterparties
            WHERE type IN ('supplier', 'both')
            LIMIT 1
        """)).fetchone()

        pur_counter: dict[str, int] = {}

        for (order_id, supplier_key, currency), rows in groups.items():
            if supplier_key == "NONE":
                if not fallback_supplier:
                    continue
                supplier_id = str(fallback_supplier.id)
            else:
                supplier_id = supplier_key

            order_date = rows[0].order_date
            company_id = str(rows[0].company_id)
            order_number = rows[0].order_number

            date_key = order_date.strftime("%Y%m%d")
            pur_counter[date_key] = pur_counter.get(date_key, 0) + 1
            pur_number = f"PUR-{date_key}-{pur_counter[date_key]:04d}"

            rate = rows[0].cost_rate_to_cny or 1
            total_amount = sum(
                (r.quantity or 0) * (r.cost_price or 0) for r in rows
            )
            total_amount_cny = float(total_amount) * float(rate)

            pur_id = str(_uuid.uuid4())
            safe_currency = currency if currency in ("CNY", "RUB", "USDT", "USD") else "CNY"
            conn.execute(sa.text(f"""
                INSERT INTO purchases
                    (id, purchase_number, company_id, supplier_id, purchase_date,
                     currency, total_amount, rate_to_cny, total_amount_cny,
                     payment_status, notes, created_at)
                VALUES
                    (:id, :num, :company_id, :supplier_id, :purchase_date,
                     '{safe_currency}'::purchasecurrencyenum, :total_amount, :rate_to_cny, :total_amount_cny,
                     'unpaid'::purchasepaymentstatus,
                     :notes, NOW())
            """), {
                "id": pur_id,
                "num": pur_number,
                "company_id": company_id,
                "supplier_id": supplier_id,
                "purchase_date": order_date,
                "total_amount": float(total_amount),
                "rate_to_cny": float(rate),
                "total_amount_cny": float(total_amount_cny),
                "notes": f"Мигрировано из заказа {order_number}",
            })

            for r in rows:
                qty = float(r.quantity or 0)
                price = float(r.cost_price or 0)
                conn.execute(sa.text("""
                    INSERT INTO purchase_items (id, purchase_id, order_item_id, quantity, cost_price, cost_amount)
                    VALUES (:id, :pur_id, :item_id, :qty, :price, :amount)
                """), {
                    "id": str(_uuid.uuid4()),
                    "pur_id": pur_id,
                    "item_id": str(r.item_id),
                    "qty": qty,
                    "price": price,
                    "amount": qty * price,
                })

    # ── 10. Drop cost columns from order_items ────────────────────────────────
    op.execute(sa.text("ALTER TABLE order_items DROP COLUMN IF EXISTS cost_price"))
    op.execute(sa.text("ALTER TABLE order_items DROP COLUMN IF EXISTS cost_currency"))
    op.execute(sa.text("ALTER TABLE order_items DROP COLUMN IF EXISTS cost_rate_to_cny"))


def downgrade() -> None:
    # Reverse the most impactful steps (cost columns restoration not attempted)
    op.execute(sa.text("ALTER TABLE order_items DROP COLUMN IF EXISTS preferred_supplier_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS purchase_payments_link"))
    op.execute(sa.text("DROP TABLE IF EXISTS purchase_items"))
    op.execute(sa.text("DROP TABLE IF EXISTS purchases"))
    op.execute(sa.text("DROP TYPE IF EXISTS purchasepaymentstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS purchasecurrencyenum"))
    op.execute(sa.text("DROP TABLE IF EXISTS user_roles"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN role userrole"))
