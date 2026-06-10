"""
Разовая чистка осиротевших purchase_items от soft-deleted закупок.

Причина: при DELETE /api/purchases/{id} закупка ставится is_deleted=TRUE,
но её purchase_items физически не удалялись. FK-constraint блокирует
удаление order_item при редактировании заказа → 500 Internal Server Error.

Запуск:
  python fix_orphan_purchase_items.py           -- dry-run (только показать)
  python fix_orphan_purchase_items.py --apply   -- бэкап + физическое удаление

Идемпотентен: повторный запуск ничего не сделает (строк не будет).
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://erp:erp_dev_password@localhost:5432/erp"),
)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, delete, text


async def run(apply: bool = False):
    from app.models.purchase_item import PurchaseItem
    from app.models.purchase import Purchase
    from app.models.order_item import OrderItem
    from app.models.order import Order

    DATABASE_URL = os.environ["DATABASE_URL"]
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n{'='*65}")
    print(f"  Чистка осиротевших purchase_items — режим: {mode}")
    print(f"{'='*65}\n")

    async with async_session() as db:
        # Найти все осиротевшие purchase_items
        rows = (await db.execute(
            select(
                PurchaseItem.id.label("pi_id"),
                PurchaseItem.order_item_id,
                PurchaseItem.purchase_id,
                OrderItem.name.label("item_name"),
                OrderItem.model.label("item_model"),
                Purchase.purchase_number,
                Order.order_number,
            )
            .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
            .join(OrderItem, PurchaseItem.order_item_id == OrderItem.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Purchase.is_deleted == True)
            .order_by(Order.order_number, Purchase.purchase_number)
        )).all()

        if not rows:
            print("✅ Осиротевших purchase_items не найдено — база чистая.\n")
            await engine.dispose()
            return

        # Сгруппировать по заказу для отчёта
        by_order: dict = {}
        for r in rows:
            by_order.setdefault(r.order_number, []).append(r)

        print(f"Найдено осиротевших purchase_items: {len(rows)}")
        print(f"Затронуто заказов: {len(by_order)}\n")

        for order_num, items in by_order.items():
            print(f"  Заказ {order_num}:")
            for r in items:
                print(f"    purchase_item {r.pi_id}")
                print(f"      order_item_id : {r.order_item_id}")
                print(f"      item          : {r.item_name} / {r.item_model or '—'}")
                print(f"      закупка       : {r.purchase_number} (is_deleted=TRUE)")
            print()

        if not apply:
            print(f"{'='*65}")
            print("  DRY-RUN завершён — изменений нет.")
            print("  Для применения: python fix_orphan_purchase_items.py --apply")
            print(f"{'='*65}\n")
            await engine.dispose()
            return

        # === APPLY ===
        # Бэкап в текстовый файл рядом со скриптом
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(os.path.dirname(__file__), f"backup_orphan_purchase_items_{ts}.sql")
        pi_ids = [r.pi_id for r in rows]

        with open(backup_path, "w") as f:
            f.write("-- Бэкап осиротевших purchase_items перед удалением\n")
            f.write(f"-- Дата: {ts}\n")
            f.write(f"-- Строк: {len(pi_ids)}\n\n")
            for r in rows:
                f.write(
                    f"-- order={r.order_number} purchase={r.purchase_number} item={r.item_name}\n"
                    f"-- INSERT INTO purchase_items (id, order_item_id, purchase_id) VALUES "
                    f"('{r.pi_id}', '{r.order_item_id}', '{r.purchase_id}');\n\n"
                )
        print(f"📦 Бэкап записан: {backup_path}\n")

        # Удаляем
        result = await db.execute(
            delete(PurchaseItem).where(PurchaseItem.id.in_(pi_ids))
        )
        deleted = result.rowcount
        await db.commit()

        print(f"✅ Удалено строк: {deleted}")
        print(f"\nЗатронутые заказы:")
        for order_num in by_order:
            print(f"  {order_num}: удалено {len(by_order[order_num])} purchase_item(s)")

        print(f"\n{'='*65}")
        print("  Чистка завершена успешно.")
        print(f"{'='*65}\n")

    await engine.dispose()


if __name__ == "__main__":
    apply_mode = "--apply" in sys.argv
    asyncio.run(run(apply=apply_mode))
