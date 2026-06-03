"""cash_transactions.operation_type — системный тип операции для i18n

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cash_transactions",
        sa.Column("operation_type", sa.String(50), nullable=True))
    op.create_index("ix_cash_tx_operation_type", "cash_transactions", ["operation_type"])

    # Заполняем operation_type для старых записей по паттерну notes
    # Это best-effort: если notes начинается с известного префикса — определяем тип
    op.execute("""
        UPDATE cash_transactions SET operation_type =
            CASE
                WHEN notes LIKE 'Расход:%'              THEN 'expense'
                WHEN notes LIKE 'Возмещение:%'          THEN 'reimbursement'
                WHEN notes LIKE 'Отмена расхода:%'      THEN 'expense_cancel'
                WHEN notes LIKE 'Отмена платежа:%'      THEN 'payment_cancel'
                WHEN notes LIKE 'Корректировка:%'       THEN 'data_fix'
                WHEN notes LIKE 'Перевод →%'            THEN 'transfer_out'
                WHEN notes LIKE 'Перевод ←%'            THEN 'transfer_in'
                WHEN direction = 'in'                   THEN 'payment_in'
                WHEN direction = 'out'                  THEN 'payment_out'
                ELSE NULL
            END
        WHERE operation_type IS NULL
    """)

    # Очищаем системный префикс из notes, оставляя только пользовательский текст
    # Формат был: «Системный ярлык: пользовательский текст» → оставляем после двоеточия
    op.execute("""
        UPDATE cash_transactions SET notes =
            CASE
                WHEN notes LIKE 'Расход: %'             THEN SUBSTRING(notes FROM 9)
                WHEN notes LIKE 'Возмещение: %'         THEN SUBSTRING(notes FROM 13)
                WHEN notes LIKE 'Отмена расхода: %'     THEN SUBSTRING(notes FROM 17)
                WHEN notes LIKE 'Отмена платежа: %'     THEN SUBSTRING(notes FROM 17)
                WHEN notes LIKE 'Корректировка: %'      THEN SUBSTRING(notes FROM 16)
                WHEN notes LIKE 'Перевод → %'           THEN SUBSTRING(notes FROM 11)
                WHEN notes LIKE 'Перевод ← %'           THEN SUBSTRING(notes FROM 11)
                ELSE notes
            END
        WHERE notes IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_cash_tx_operation_type", "cash_transactions")
    op.drop_column("cash_transactions", "operation_type")
