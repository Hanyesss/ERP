"""
Скрипт корректировки: откат кассовых транзакций от удалённых платежей.

Запуск:
  python fix_dead_cash_transactions.py           -- dry-run (только показать, не менять)
  python fix_dead_cash_transactions.py --apply   -- применить корректировки

Идемпотентен: повторный запуск не создаёт дубли (проверяет наличие компенсации).
"""

import asyncio
import sys
import uuid
from decimal import Decimal
from datetime import datetime, timezone

# Добавляем путь к приложению
import os
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", "postgresql+asyncpg://erp:erp_dev_password@localhost:5432/erp"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, case, text


async def run(apply: bool = False):
    from app.models.cash_register import CashRegister, CashTransaction
    from app.models.payment import Payment
    from app.models.audit_log import AuditLog, AuditActionEnum

    DATABASE_URL = os.environ["DATABASE_URL"]
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n{'='*60}")
    print(f"  Корректировка кассы — режим: {mode}")
    print(f"{'='*60}\n")

    async with async_session() as db:
        # Ищем активные CashTransaction, чей payment удалён (is_active=False)
        dead_txs_result = await db.execute(
            select(CashTransaction, Payment, CashRegister)
            .join(Payment, CashTransaction.payment_id == Payment.id)
            .join(CashRegister, CashTransaction.cash_register_id == CashRegister.id)
            .where(
                Payment.is_active == False,
                CashTransaction.is_active == True,
                CashTransaction.payment_id.isnot(None),
            )
            .order_by(CashRegister.name, CashTransaction.created_at)
        )
        dead_rows = dead_txs_result.all()

        if not dead_rows:
            print("✅ Мёртвых транзакций не найдено — база чистая.\n")
            return

        print(f"Найдено мёртвых транзакций: {len(dead_rows)}\n")

        # Проверяем для каждой нет ли уже компенсации
        to_fix = []
        for tx, payment, register in dead_rows:
            # Компенсация — транзакция с обратным направлением, без payment_id,
            # с notes содержащим "Отмена платежа" или "Корректировка" и тем же register
            comp_direction = "out" if tx.direction == "in" else "in"
            from sqlalchemy import or_ as sa_or
            comp_check = await db.execute(
                select(func.count(CashTransaction.id)).where(
                    CashTransaction.cash_register_id == tx.cash_register_id,
                    CashTransaction.payment_id.is_(None),
                    CashTransaction.direction == comp_direction,
                    CashTransaction.amount == tx.amount,
                    # Компенсация от нового delete_payment: "Отмена платежа: xxxxxxxx"
                    # Компенсация от скрипта миграции:     "Корректировка: откат ..."
                    sa_or(
                        CashTransaction.notes.like("%Отмена платеж%"),
                        CashTransaction.notes.like("%Корректировка%"),
                    ),
                )
            )
            already_compensated = comp_check.scalar_one() > 0

            print(f"  {'✅ УЖЕ КОМПЕНСИРОВАНА' if already_compensated else '❌ ТРЕБУЕТ ОТКАТA'}")
            print(f"     Касса:     {register.name} ({register.currency})")
            print(f"     Платёж:    {payment.id} (удалён: {not payment.is_active})")
            print(f"     Транзакция:{tx.id}")
            print(f"     Направление:{tx.direction}  Сумма: {tx.amount}")
            print(f"     Создана:   {tx.created_at}")
            print()

            if not already_compensated:
                to_fix.append((tx, payment, register))

        if not to_fix:
            print("✅ Все мёртвые транзакции уже скомпенсированы.\n")
            return

        print(f"\nТребуют исправления: {len(to_fix)} транзакций")

        # Подсчёт итогового влияния на балансы
        from collections import defaultdict
        balance_errors: dict = defaultdict(Decimal)
        for tx, payment, register in to_fix:
            sign = Decimal("1") if tx.direction == "in" else Decimal("-1")
            balance_errors[register.name] += sign * tx.amount

        print("\nВлияние на балансы касс (текущая ошибка):")
        for reg_name, error in balance_errors.items():
            sign_str = f"+{error}" if error > 0 else str(error)
            print(f"  {reg_name}: {sign_str} (касса показывает на столько больше/меньше чем должна)")

        if not apply:
            print(f"\n{'='*60}")
            print("  DRY-RUN завершён — изменений нет.")
            print("  Для применения запустите с флагом --apply")
            print(f"{'='*60}\n")
            return

        # === APPLY ===
        print("\nПрименяю корректировки...\n")

        # Найдём системного пользователя (admin) для created_by
        from app.models.user import User, UserRole
        admin_result = await db.execute(
            select(User).join(User.role_entries).where(
                UserRole.role == "admin", User.is_active == True
            ).limit(1)
        )
        admin_user = admin_result.scalar_one_or_none()
        if not admin_user:
            print("❌ Не найден admin-пользователь. Прерываю.")
            return

        # Вычисляем текущий баланс каждой кассы через _get_balance
        async def get_current_balance(register_id):
            reg_result = await db.execute(
                select(CashRegister.initial_balance).where(CashRegister.id == register_id)
            )
            initial = reg_result.scalar_one_or_none() or Decimal("0")
            tx_result = await db.execute(
                select(func.coalesce(func.sum(case(
                    (CashTransaction.direction == "in", CashTransaction.amount),
                    else_=-CashTransaction.amount,
                )), Decimal("0"))).where(
                    CashTransaction.cash_register_id == register_id,
                    CashTransaction.is_active == True,
                )
            )
            return initial + (tx_result.scalar_one() or Decimal("0"))

        applied = 0
        for tx, payment, register in to_fix:
            comp_direction = "out" if tx.direction == "in" else "in"
            cur_bal = await get_current_balance(tx.cash_register_id)
            comp_amount = tx.amount
            new_bal = cur_bal + comp_amount if comp_direction == "in" else cur_bal - comp_amount

            comp_tx = CashTransaction(
                id=uuid.uuid4(),
                cash_register_id=tx.cash_register_id,
                direction=comp_direction,
                amount=comp_amount,
                balance_after=new_bal,
                notes=f"Корректировка: откат удалённого платежа (миграция целостности)",
                created_by=admin_user.id,
            )
            db.add(comp_tx)
            await db.flush()

            # Аудит корректировки
            db.add(AuditLog(
                id=uuid.uuid4(),
                user_id=admin_user.id,
                entity_type="cash_transaction",
                entity_id=comp_tx.id,
                action=AuditActionEnum.create,
                changes={
                    "register_id": str(tx.cash_register_id),
                    "register_name": register.name,
                    "direction": comp_direction,
                    "amount": str(comp_amount),
                    "reason": "data_integrity_fix",
                    "original_tx_id": str(tx.id),
                    "deleted_payment_id": str(payment.id),
                    "script": "fix_dead_cash_transactions.py",
                },
            ))

            print(f"  ✅ {register.name}: создана компенсация {comp_direction} {comp_amount} → баланс {new_bal}")
            applied += 1

        await db.commit()
        print(f"\n✅ Применено корректировок: {applied}")
        print(f"\nНовые балансы касс после исправления:")
        processed_registers = set()
        for tx, payment, register in to_fix:
            if register.id not in processed_registers:
                new_bal = await get_current_balance(register.id)
                print(f"  {register.name} ({register.currency}): {new_bal}")
                processed_registers.add(register.id)

        print(f"\n{'='*60}")
        print("  Корректировка завершена успешно.")
        print(f"{'='*60}\n")

    await engine.dispose()


if __name__ == "__main__":
    apply_mode = "--apply" in sys.argv
    asyncio.run(run(apply=apply_mode))
