"""
Скрипт чистки дублирующихся order_items.

Находит позиции с одинаковыми (name, model, sale_price, quantity, sale_currency)
в одном заказе, удаляет лишние копии, пересчитывает total_sale_cny.

Запуск:
  python fix_duplicate_order_items.py           -- dry-run
  python fix_duplicate_order_items.py --apply   -- применить

Идемпотентен.
"""
import asyncio, sys, os
from decimal import Decimal
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://erp:erp_dev_password@localhost:5432/erp"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func


async def run(apply: bool = False):
    from app.models.order import Order
    from app.models.order_item import OrderItem
    from app.models.purchase_item import PurchaseItem
    from app.models.purchase import Purchase

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n{'='*62}\n  Дубли позиций заказов — {mode}\n{'='*62}\n")

    async with Session() as db:
        # Все заказы с их позициями
        all_items = (await db.execute(
            select(OrderItem).order_by(OrderItem.order_id, OrderItem.id)
        )).scalars().all()

        # Группируем по order_id
        by_order: dict = defaultdict(list)
        for item in all_items:
            by_order[item.order_id].append(item)

        # ID позиций с закупками (нельзя удалять)
        purchased_ids = set((await db.execute(
            select(PurchaseItem.order_item_id)
            .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
            .where(Purchase.is_deleted == False)
        )).scalars().all())

        total_orders_affected = 0
        total_dupes_removed = 0

        for order_id, items in by_order.items():
            # Ключ дубля: (name, model, sale_price, quantity, sale_currency)
            seen: dict = {}
            dupes_to_delete = []

            for item in items:
                key = (
                    item.name or "",
                    item.model or "",
                    str(item.sale_price or ""),
                    str(item.quantity or ""),
                    item.sale_currency or "",
                )
                if key in seen:
                    # Дубль — предпочитаем оставить тот у кого есть закупки
                    existing = seen[key]
                    if item.id in purchased_ids and existing.id not in purchased_ids:
                        dupes_to_delete.append(existing)
                        seen[key] = item
                    else:
                        dupes_to_delete.append(item)
                else:
                    seen[key] = item

            if not dupes_to_delete:
                continue

            # Получаем заказ
            order = (await db.execute(
                select(Order).where(Order.id == order_id)
            )).scalar_one_or_none()
            if not order:
                continue

            kept = [i for i in items if i not in dupes_to_delete]
            old_total = order.total_sale_cny

            # Пересчёт total_sale_cny по оставшимся
            new_total = sum(
                (i.quantity or Decimal("0")) * (i.sale_price or Decimal("0"))
                for i in kept
            )

            print(f"Заказ {order.order_number} (id={str(order_id)[:8]}...)")
            print(f"  Дублей к удалению: {len(dupes_to_delete)}")
            for d in dupes_to_delete:
                flag = " [с закупкой — ПРОПУСК]" if d.id in purchased_ids else ""
                print(f"    × {d.name or ''} | кол={d.quantity} | цена={d.sale_price} {d.sale_currency}{flag}")
            print(f"  total_sale_cny: {old_total} → {new_total:.2f}")
            print()

            total_orders_affected += 1
            safe_to_delete = [d for d in dupes_to_delete if d.id not in purchased_ids]
            total_dupes_removed += len(safe_to_delete)

            if apply:
                for d in safe_to_delete:
                    await db.delete(d)
                order.total_sale_cny = Decimal(str(new_total)).quantize(Decimal("0.01"))

        if total_orders_affected == 0:
            print("✅ Дублей не найдено — база чистая.\n")
        else:
            print(f"Итого: {total_orders_affected} заказов, {total_dupes_removed} дублей к удалению")

        if apply and total_orders_affected > 0:
            await db.commit()
            print("✅ Корректировка применена.\n")
        elif not apply:
            print(f"\n{'='*62}")
            print(f"  DRY-RUN — изменений нет.")
            print(f"  Для применения: python fix_duplicate_order_items.py --apply")
            print(f"{'='*62}\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(apply="--apply" in sys.argv))
