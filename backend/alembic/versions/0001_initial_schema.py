"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE TYPE userrole AS ENUM ('employee','manager','accountant','admin')"))
    op.execute(sa.text("CREATE TYPE userlang AS ENUM ('ru','zh')"))
    op.execute(sa.text("CREATE TYPE counterpartytype AS ENUM ('client','supplier','both')"))
    op.execute(sa.text("CREATE TYPE currencyenum AS ENUM ('CNY','RUB','USDT')"))
    op.execute(sa.text("CREATE TYPE ratecurrencyenum AS ENUM ('RUB','USDT')"))
    op.execute(sa.text("CREATE TYPE ratesourceenum AS ENUM ('auto','manual')"))
    op.execute(sa.text("CREATE TYPE orderstatus AS ENUM ('new','active','closed','cancelled')"))
    op.execute(sa.text("CREATE TYPE ordercurrencyenum AS ENUM ('CNY','RUB','USDT')"))
    op.execute(sa.text("CREATE TYPE paymentstatus AS ENUM ('unpaid','partial','paid')"))
    op.execute(sa.text("CREATE TYPE filetypeenum AS ENUM ('invoice','packing','photo','other')"))
    op.execute(sa.text("CREATE TYPE paymentdirection AS ENUM ('in','out')"))
    op.execute(sa.text("CREATE TYPE paymentcurrencyenum AS ENUM ('CNY','RUB','USDT')"))
    op.execute(sa.text("CREATE TYPE linktypeenum AS ENUM ('order','client','none')"))
    op.execute(sa.text("CREATE TYPE reimburseestatusnum AS ENUM ('pending','approved','paid','rejected')"))
    op.execute(sa.text("CREATE TYPE auditactionenum AS ENUM ('create','update','delete')"))

    op.execute(sa.text("""
        CREATE TABLE companies (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            name_cn VARCHAR(255),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            login VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            role userrole NOT NULL,
            lang userlang NOT NULL DEFAULT 'ru',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE counterparties (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            name_cn VARCHAR(255),
            type counterpartytype NOT NULL,
            default_currency currencyenum NOT NULL DEFAULT 'CNY',
            contact_info JSONB,
            notes TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE business_types (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            name_cn VARCHAR(255),
            code VARCHAR(50) NOT NULL UNIQUE
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE expense_categories (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            name_cn VARCHAR(255),
            is_active BOOLEAN NOT NULL DEFAULT true
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE exchange_rates (
            id UUID PRIMARY KEY,
            currency ratecurrencyenum NOT NULL,
            rate_to_cny NUMERIC(18,8) NOT NULL,
            rate_date DATE NOT NULL,
            created_by UUID NOT NULL REFERENCES users(id),
            source ratesourceenum NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE orders (
            id UUID PRIMARY KEY,
            order_number VARCHAR(100) NOT NULL UNIQUE,
            company_id UUID NOT NULL REFERENCES companies(id),
            client_id UUID NOT NULL REFERENCES counterparties(id),
            business_type_id UUID NOT NULL REFERENCES business_types(id),
            manager_id UUID NOT NULL REFERENCES users(id),
            order_date DATE NOT NULL,
            status orderstatus NOT NULL DEFAULT 'new',
            client_currency ordercurrencyenum NOT NULL DEFAULT 'CNY',
            total_sale_cny NUMERIC(18,2) NOT NULL DEFAULT 0,
            total_cost_cny NUMERIC(18,2) NOT NULL DEFAULT 0,
            payment_status paymentstatus NOT NULL DEFAULT 'unpaid',
            supplier_payment_status paymentstatus NOT NULL DEFAULT 'unpaid',
            notes TEXT,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE order_items (
            id UUID PRIMARY KEY,
            order_id UUID NOT NULL REFERENCES orders(id),
            supplier_id UUID REFERENCES counterparties(id),
            name VARCHAR(255) NOT NULL,
            name_cn VARCHAR(255),
            quantity NUMERIC(18,4) NOT NULL,
            unit VARCHAR(50),
            sale_price NUMERIC(18,2) NOT NULL,
            cost_price NUMERIC(18,2) NOT NULL,
            sale_currency VARCHAR(10) NOT NULL,
            cost_currency VARCHAR(10) NOT NULL,
            sale_rate_to_cny NUMERIC(18,8) NOT NULL,
            cost_rate_to_cny NUMERIC(18,8) NOT NULL
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE order_files (
            id UUID PRIMARY KEY,
            order_id UUID NOT NULL REFERENCES orders(id),
            file_url VARCHAR(1000) NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_type filetypeenum NOT NULL,
            uploaded_by UUID NOT NULL REFERENCES users(id),
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE payments (
            id UUID PRIMARY KEY,
            company_id UUID NOT NULL REFERENCES companies(id),
            direction paymentdirection NOT NULL,
            counterparty_id UUID NOT NULL REFERENCES counterparties(id),
            payment_date DATE NOT NULL,
            currency paymentcurrencyenum NOT NULL,
            amount NUMERIC(18,2) NOT NULL,
            rate_to_cny NUMERIC(18,8) NOT NULL,
            amount_cny NUMERIC(18,2) NOT NULL,
            network_fee NUMERIC(18,2),
            notes TEXT,
            file_url VARCHAR(1000),
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE payment_allocations (
            id UUID PRIMARY KEY,
            payment_id UUID NOT NULL REFERENCES payments(id),
            order_id UUID NOT NULL REFERENCES orders(id),
            amount_cny NUMERIC(18,2) NOT NULL,
            notes TEXT
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE expenses (
            id UUID PRIMARY KEY,
            company_id UUID NOT NULL REFERENCES companies(id),
            expense_date DATE NOT NULL,
            category_id UUID NOT NULL REFERENCES expense_categories(id),
            currency VARCHAR(10) NOT NULL,
            amount NUMERIC(18,2) NOT NULL,
            rate_to_cny NUMERIC(18,8) NOT NULL,
            amount_cny NUMERIC(18,2) NOT NULL,
            link_type linktypeenum NOT NULL DEFAULT 'none',
            order_id UUID REFERENCES orders(id),
            client_id UUID REFERENCES counterparties(id),
            is_reimbursement BOOLEAN NOT NULL DEFAULT false,
            reimburse_to_user_id UUID REFERENCES users(id),
            reimburse_status reimburseestatusnum,
            reimburse_paid_date DATE,
            reject_reason TEXT,
            description TEXT NOT NULL,
            receipt_url VARCHAR(1000),
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE audit_log (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            entity_type VARCHAR(100) NOT NULL,
            entity_id UUID NOT NULL,
            action auditactionenum NOT NULL,
            changes JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE sessions (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            token VARCHAR(500) NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))


def downgrade() -> None:
    for table in ["sessions", "audit_log", "expenses", "payment_allocations", "payments",
                  "order_files", "order_items", "orders", "exchange_rates",
                  "expense_categories", "business_types", "counterparties", "users", "companies"]:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {table} CASCADE"))

    for typ in ["auditactionenum", "reimburseestatusnum", "linktypeenum", "paymentcurrencyenum",
                "paymentdirection", "filetypeenum", "paymentstatus", "ordercurrencyenum",
                "orderstatus", "ratesourceenum", "ratecurrencyenum", "currencyenum",
                "counterpartytype", "userlang", "userrole"]:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {typ}"))
