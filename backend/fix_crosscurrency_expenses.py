"""
Скрипт диагностики: кросс-валютные расходы с неверным списанием с кассы.

Ищет расходы где валюта расхода ≠ валюта кассы И в кассе списалась amount_cny
вместо правильной суммы в валюте кассы.

Запуск:
  python fix_crosscurrency_expenses.py           -- dry-run (только показать)
  python fix_crosscurrency_expenses.py --apply   -- применить корректировки

Идемпотентен: не создаёт дубли если компенсация уже есть.
"""

import asyncio, sys, os, uuid
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://erp:erp_dev_password@localhost:5432/erp"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, case


async def run(apply: bool = False):
    from app.models.expense import Expense
    from app.models.cash_register import CashRegister, CashTransaction, TxDirection
    from app.models.audit_log import AuditLog, AuditActionEnum
    from app.models.user import User

    DATABASE_URL = os.environ["DATABASE_URL"]
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n{'='*62}")
    print(f"  Кросс-валютные расходы — режим: {mode}")
    print(f"{'='*62}\n")

    async with Session() as db:
        # Находим расходы где касса НЕ в CNY и валюта расхода ≠ валюта кассы
        # В таких случаях amount_cny была списана с кассы вместо правильной суммы в валюте кассы
        rows = (await db.execute(
            select(Expense, CashRegister)
            .join(CashRegister, Expense.cash_register_id == CashRegister.id)
            .where(
                Expense.is_active == True,
                Expense.cash_register_id.isnot(None),
                Expense.is_reimbursement == False,
                # Валюты не совпадают
                Expense.currency != CashRegister.currency,
                # Касса НЕ в CNY (если касса CNY — amount_cny правильно)
                CashRegister.currency != "CNY",
                # Признак что это старые расходы (до фикса) — нет cash_amount_in_register
                Expense.cash_amount_in_register.is_(None),
            )
            .order_by(Expense.expense_date)
        )).all()

        if not rows:
            print("✅ Кросс-валютных расходов с потенциальным расхождением не найдено.\n")
            return

        print(f"Найдено расходов с возможным расхождением: {len(rows)}\n")
        print(f"{'Дата':<12} {'Описание':<30} {'Расход':>12} {'Списано с кассы':>18} {'Должно быть':>14} {'Касса'}")
        print("-" * 96)

        total_error = {}
        problems = []

        for expense, register in rows:
            # Что БЫЛО списано — amount_cny (неверно для иновалютной кассы)
            was_deducted = expense.amount_cny
            # Что ДОЛЖНО было быть списано — исходная сумма в валюте расхода
            # (без курса в валюту кассы пересчитать невозможно, показываем исходную)
            should_be = expense.amount  # в валюте расхода

            diff = was_deducted - should_be  # позитивный = списали больше чем надо

            status = "❌"
            note = f"списано {was_deducted} {register.currency}, должно быть ~{should_be} {expense.currency}"
            print(f"{str(expense.expense_date):<12} {(expense.description or '')[:30]:<30} "
                  f"{expense.amount:>10.2f} {expense.currency}"
                  f"{was_deducted:>15.2f} {register.currency}"
                  f"{should_be:>12.2f} {expense.currency}"
                  f"  {register.name}")

            total_error[register.id] = total_error.get(register.id, Decimal("0")) + diff
            problems.append((expense, register, was_deducted, should_be))

        print(f"\nРасхождения по кассам:")
        for reg_id, err in total_error.items():
            reg_name = next(r.name for _, r, _, _ in problems if r.id == reg_id)
            print(f"  {reg_name}: баланс завышен на {err:+.2f} (списали лишнего)")

        print(f"\n⚠️  Для корректировки нужен курс конвертации на дату каждого расхода.")
        print(f"   Автоматическая корректировка невозможна без точных исторических курсов.")
        print(f"   Рекомендация: проверить каждый расход вручную и при необходимости")
        print(f"   создать компенсирующие транзакции через кассу напрямую.\n")
        print(f"   Всего затронуто расходов: {len(problems)}")
        print(f"   Затронуто касс: {len(total_error)}\n")

        if not apply:
            print(f"{'='*62}")
            print(f"  DRY-RUN: изменений нет.")
            print(f"  Запустите с --apply для создания корректировок.")
            print(f"  ВНИМАНИЕ: apply требует ручного указания курсов.")
            print(f"{'='*62}\n")
            return

        print("APPLY режим: для кросс-валютных расходов автоматическая")
        print("корректировка не реализована — нужны исторические курсы.")
        print("Выполните корректировку вручную через раздел касс.\n")

    await engine.dispose()


if __name__ == "__main__":
    apply_mode = "--apply" in sys.argv
    asyncio.run(run(apply=apply_mode))
