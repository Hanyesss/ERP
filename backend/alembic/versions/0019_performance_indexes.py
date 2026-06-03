"""performance indexes on frequently queried columns"""
revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    # order_items — каждая загрузка заказа делает seq scan
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items(order_id)")

    # orders — фильтрация по клиенту, статусу, дате, типу бизнеса
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_client_id ON orders(client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_business_type_id ON orders(business_type_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_order_date ON orders(order_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_manager_id ON orders(manager_id)")

    # order_charges — загружается с каждым заказом
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_charges_order_id ON order_charges(order_id)")

    # payment_allocations — критично для расчёта остатков
    op.execute("CREATE INDEX IF NOT EXISTS ix_payment_allocations_order_id ON payment_allocations(order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payment_allocations_payment_id ON payment_allocations(payment_id)")
    # payment_allocations.purchase_id не существует в этой таблице — пропускаем

    # payments — список платежей
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_counterparty_id ON payments(counterparty_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_direction ON payments(direction)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_payment_date ON payments(payment_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_is_active ON payments(is_active)")

    # purchases
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchases_supplier_id ON purchases(supplier_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchases_order_id ON purchases(order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchases_payment_status ON purchases(payment_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchases_purchase_date ON purchases(purchase_date)")

    # purchase_items
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchase_items_purchase_id ON purchase_items(purchase_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchase_items_order_item_id ON purchase_items(order_item_id)")

    # counterparties
    op.execute("CREATE INDEX IF NOT EXISTS ix_counterparties_type ON counterparties(type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_counterparties_is_active ON counterparties(is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_counterparties_code ON counterparties(code)")

    # expenses
    op.execute("CREATE INDEX IF NOT EXISTS ix_expenses_created_by ON expenses(created_by)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_expenses_expense_date ON expenses(expense_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_expenses_order_id ON expenses(order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_expenses_is_active ON expenses(is_active)")

    # cash_transactions — баланс кассы считается на каждый запрос
    op.execute("CREATE INDEX IF NOT EXISTS ix_cash_transactions_register_id ON cash_transactions(cash_register_id)")

    # notifications
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)")

    # order_item_photos
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_files_order_id ON order_files(order_id)")

    # purchase_payment_link
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchase_payment_link_purchase_id ON purchase_payments_link(purchase_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchase_payment_link_payment_id ON purchase_payments_link(payment_id)")


def downgrade():
    indexes = [
        "ix_order_items_order_id", "ix_orders_client_id", "ix_orders_business_type_id",
        "ix_orders_status", "ix_orders_order_date", "ix_orders_manager_id",
        "ix_order_charges_order_id",
        "ix_payment_allocations_order_id", "ix_payment_allocations_payment_id",
        "ix_payment_allocations_purchase_id",
        "ix_payments_counterparty_id", "ix_payments_direction",
        "ix_payments_payment_date", "ix_payments_is_active",
        "ix_purchases_supplier_id", "ix_purchases_order_id",
        "ix_purchases_payment_status", "ix_purchases_purchase_date",
        "ix_purchase_items_purchase_id", "ix_purchase_items_order_item_id",
        "ix_counterparties_type", "ix_counterparties_is_active", "ix_counterparties_code",
        "ix_expenses_created_by", "ix_expenses_expense_date",
        "ix_expenses_order_id", "ix_expenses_is_active",
        "ix_cash_transactions_register_id",
        "ix_notifications_user_id", "ix_order_files_order_id",
        "ix_purchase_payment_link_purchase_id", "ix_purchase_payment_link_payment_id",
    ]
    for idx in indexes:
        op.execute(f"DROP INDEX IF EXISTS {idx}")
