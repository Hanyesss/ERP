# Отчёт: Финансовая целостность кассы

**Дата:** 2026-06-03  
**Тип:** исправление критических багов  
**Статус:** ✅ реализовано локально, готово к деплою  
**Коммит:** `87ba511`

---

## Контекст

По результатам финансового аудита (`FINANCIAL_AUDIT.md`) выявлены критические баги в модуле кассы.  
Бэкап БД перед деплоем: `/opt/erp/backup_before_cash_fix_20260603.sql` ✅

Подтверждённое расхождение на боевой БД: **6 мёртвых транзакций, ошибка 253 915 CNY** в кассах `Aslan RUB` и `Han USDT`.

---

## Что исправлено

### П1 — Удаление платежа теперь откатывает кассу 🔴→✅

**Файл:** `backend/app/api/payments.py` — функция `delete_payment`

**Было:** платёж помечался `is_active=False`, но `CashTransaction` оставалась в БД → баланс кассы врал на сумму каждого удалённого платежа.

**Стало:** при удалении платежа для каждой активной `CashTransaction` с `payment_id` этого платежа создаётся **компенсирующая транзакция** обратного направления:
- Если платёж был `direction=in` → компенсация `direction=out` (и наоборот)
- `amount` = сумма исходной транзакции
- `notes` = `"Отмена платежа: {id[:8]}"`
- `balance_after` = пересчитанный баланс
- Пишется аудит для каждой компенсации

Оригинальная транзакция **не удаляется** — остаётся в истории. Компенсация обнуляет её эффект на баланс.

```python
# payments.py — delete_payment (упрощённо)
cash_txs = await db.execute(
    select(CashTransaction).where(
        CashTransaction.payment_id == payment_id,
        CashTransaction.is_active == True,
    )
)
for tx in cash_txs:
    comp_direction = "out" if tx.direction == "in" else "in"
    cur_bal = await _get_balance(db, tx.cash_register_id)
    db.add(CashTransaction(direction=comp_direction, amount=tx.amount, ...))
    await write_audit(...)
```

---

### П2 — Флаг `is_active` у CashTransaction 🔴→✅

**Файл:** `backend/app/models/cash_register.py`

Добавлено поле `is_active: bool = True` в модель `CashTransaction`.

`_get_balance` теперь считает только активные транзакции:
```python
# cash_registers.py — _get_balance
.where(
    CashTransaction.cash_register_id == register_id,
    CashTransaction.is_active == True,   # ← новый фильтр
)
```

Аналогично обновлён bulk-запрос балансов в `list_registers`.

В истории транзакций неактивные отображаются зачёркнутым текстом с тегом «отменена».

---

### П4 — Начальный баланс кассы 🟠→✅

**Файлы:** `backend/app/models/cash_register.py`, `backend/app/api/cash_registers.py`, `frontend/src/pages/CashRegistersPage.tsx`

Добавлено поле `initial_balance: Decimal = 0` в модель `CashRegister`.

Формула баланса:
```
баланс кассы = initial_balance + SUM(amount активных транзакций in) - SUM(amount активных транзакций out)
```

**API:**
- `POST /api/cash-registers` — принимает `initial_balance` (необязательный, default 0)
- `PATCH /api/cash-registers/{id}` — поле `initial_balance` доступно **только для admin**, при изменении пишется аудит:
  ```json
  { "initial_balance": { "old": "0.00", "new": "50000.00" } }
  ```

**Фронтенд:**
- В форме создания/редактирования кассы — поле «Начальный баланс» с иконкой 🔒
- Редактировать может только admin; остальные видят поле disabled
- В таблице касс под основным балансом показывается «нач. X» если `initial_balance != 0`

---

### П3 — Аудит кассовых операций 🟠→✅

**Файлы:** `backend/app/api/payments.py`, `backend/app/api/expenses.py`, `backend/app/api/cash_registers.py`

Теперь `write_audit` вызывается при **каждой** операции с кассой:

| Событие | entity_type | reason в changes |
|---------|-------------|-----------------|
| Платёж создан (касса пополнена/списана) | `cash_transaction` | `payment` |
| Платёж удалён → компенсация | `cash_transaction` | `payment_deleted` |
| Расход создан (списание из кассы) | `cash_transaction` | `expense` |
| Расход удалён → компенсация | `cash_transaction` | `expense_deleted` |
| Возмещение оплачено | `cash_transaction` | `reimbursement` |
| Перевод между кассами | `cash_transfer` | — |
| Транзакции перевода (×2) | `cash_transaction` | `transfer` |
| Изменение `initial_balance` | `cash_register` | `{old, new}` |

---

### П6 — Защита отменённого заказа 🟡→✅

**Файл:** `backend/app/api/orders.py` — функция `update_order`

Добавлена проверка в начале `PATCH /orders/{id}`:
```python
if order.status == OrderStatus.cancelled:
    raise HTTPException(422, "Отменённый заказ нельзя редактировать или реактивировать")
```

Отменённый заказ **не может** вернуться в расчёт прибыли через изменение статуса через API. `total_sale_cny` при этом сохраняется в БД (для истории).

---

## Миграция схемы БД

**Файл:** `backend/alembic/versions/0021_cash_integrity.py`

```sql
-- Начальный баланс кассы
ALTER TABLE cash_registers
  ADD COLUMN initial_balance NUMERIC(18,2) NOT NULL DEFAULT 0;

-- Флаг активности кассовой транзакции
ALTER TABLE cash_transactions
  ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX ix_cash_transactions_is_active ON cash_transactions (is_active);
```

---

## Скрипт корректировки данных

**Файл:** `backend/fix_dead_cash_transactions.py`

Находит все `CashTransaction` от удалённых платежей (`payment.is_active=False`), для которых ещё нет компенсирующей транзакции, и создаёт компенсации.

**Идемпотентен:** повторный запуск не создаёт дубли — проверяет наличие существующих компенсаций (ищет по notes `%Отмена платеж%` или `%Корректировка%`).

### Запуск Dry-run (только показать, ничего не менять)
```bash
docker exec erp_backend python fix_dead_cash_transactions.py
```

Выводит:
- Список мёртвых транзакций (касса, платёж, сумма, дата)
- Уже скомпенсированные — помечены ✅
- Требующие отката — помечены ❌
- Итоговое влияние на балансы касс (текущая ошибка в CNY)

### Запуск Apply (применить)
```bash
docker exec erp_backend python fix_dead_cash_transactions.py --apply
```

Создаёт компенсирующие транзакции + записи в `audit_log` с `reason: data_integrity_fix`.  
Выводит новые балансы касс после исправления.

---

## Проверка локально (результаты тестов)

| Тест | Результат |
|------|-----------|
| Создание кассы с `initial_balance=10000` | ✅ balance=10000 |
| Создание платежа 5000 → баланс 15000 | ✅ |
| Удаление платежа → баланс вернулся к 10000 | ✅ компенсация `out 5000` создана |
| История: оригинальная транзакция + компенсация видны | ✅ |
| Dry-run скрипта — находит и показывает транзакции | ✅ |
| Idempotency — повторный dry-run видит ✅ УЖЕ КОМПЕНСИРОВАНА | ✅ |
| Редактирование `initial_balance` не-admin → 403 | ✅ |
| Отмена заказа + попытка PATCH → 422 | ✅ |
| TypeScript компиляция — ошибок нет | ✅ |
| Миграция 0021 применена без ошибок | ✅ |

---

## Порядок деплоя на продакшн

> ⚠️ Бэкап БД уже сделан: `/opt/erp/backup_before_cash_fix_20260603.sql`

```bash
# 1. Получить код
cd /opt/erp
git pull origin main

# 2. Пересобрать и запустить (миграция 0021 применится автоматически при старте)
docker compose up -d --build

# 3. Убедиться что backend стартовал
docker logs erp_backend --tail 10

# 4. Dry-run скрипта — ОБЯЗАТЕЛЬНО проверить вывод
docker exec erp_backend python fix_dead_cash_transactions.py
```

**После dry-run:** сверьте что найденные транзакции соответствуют известным удалённым платежам.  
Ожидаемый вывод: **6 транзакций**, кассы **Aslan RUB** и **Han USDT**, суммарная ошибка **253 915 CNY**.

```bash
# 5. Только после подтверждения — применить
docker exec erp_backend python fix_dead_cash_transactions.py --apply

# 6. Проверить балансы касс
```

---

## Что НЕ делалось (отложено)

- **П7** — унификация флагов (`is_deleted` → `is_active` в Purchase) — отдельное задание, риск широкой правки
- **balance_after** — поле `balance_after` в истории не пересчитывается для старых записей (только для новых). Не влияет на реальный баланс (он вычисляется через SUM, не из `balance_after`)
