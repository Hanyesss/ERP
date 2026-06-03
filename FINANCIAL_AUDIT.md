# Финансовый аудит ERP — Отчёт

**Дата:** 2026-06-03  
**Статус:** только чтение, код не изменялся  
**Цель:** выявить риски в кассе, удалениях, аудите и расчёте прибыли

---

## 1. КАССА

### 1.1 Как хранится баланс

Баланс **нигде не хранится** как число. Каждый раз вычисляется из всех `CashTransaction`:

```python
# cash_registers.py:54
async def _get_balance(db, register_id):
    select(func.coalesce(func.sum(
        case((CashTransaction.direction == "in", CashTransaction.amount),
             else_=-CashTransaction.amount)
    ), Decimal("0"))).where(CashTransaction.cash_register_id == register_id)
```

`balance_after` в транзакции — исторический снимок баланса в момент записи.  
Не участвует в текущем расчёте баланса — только для отображения.

`initial_balance` — **не существует**. Нельзя задать начальный остаток кассы.

---

### 1.2 Модели

**CashRegister** (`models/cash_register.py`):
```
id, name, currency, notes, is_active
```
❌ Нет поля `balance`, нет `initial_balance`

**CashTransaction** (`models/cash_register.py`):
```
id, cash_register_id, payment_id (nullable), direction (in/out),
amount, balance_after, notes, created_by
```

**CashTransfer** (`models/cash_transfer.py`):
```
id, from_register_id, to_register_id,
from_amount, to_amount, exchange_rate,
transfer_date, notes, created_by, created_at
```

---

### 1.3 Когда создаётся CashTransaction

| Операция | Транзакция | Файл:строка |
|----------|-----------|-------------|
| Создание платежа (in/out) | ✅ Создаётся | `payments.py:519` |
| Создание расхода с кассой | ✅ Создаётся | `expenses.py:36` |
| Перевод между кассами | ✅ Две транзакции | `cash_registers.py:245` |
| mark-paid возмещения | ✅ Компенсирующая inflow | `expenses.py:575` |

**Создание при платеже** (`payments.py:519-533`):
```python
current_balance = await _get_balance(db, body.cash_register_id)
new_balance = current_balance + body.amount  # если direction=in
              # или current_balance - body.amount  # если direction=out
db.add(CashTransaction(
    cash_register_id=body.cash_register_id,
    payment_id=payment.id,
    direction=tx_direction,
    amount=body.amount,
    balance_after=new_balance,
    notes=body.notes,
    created_by=current_user.id,
))
```

**Создание при расходе** (`expenses.py:36-63`):
```python
async def _record_cash_outflow(db, cash_register_id, amount, notes, created_by):
    current_balance = await ...  # SUM из транзакций
    balance_after = current_balance - amount
    db.add(CashTransaction(
        cash_register_id=cash_register_id,
        direction=TxDirection.outflow,
        amount=amount,
        balance_after=balance_after,
        notes=notes,
        created_by=created_by,
    ))
```

---

### 1.4 🔴 Удаление платежа — КРИТИЧЕСКИЙ БАГ

**DELETE платежа** (`payments.py:601-623`):
```python
@router.delete("/{payment_id}")
async def delete_payment(...):
    payment.is_active = False          # ← Платёж помечен удалённым
    await _recalc_all_for_payment(db, payment)  # пересчёт статусов заказов
    await write_audit(...)
    await db.commit()
    # !! CashTransaction НЕ удаляется и НЕ компенсируется !!
    # Транзакция в БД остаётся с direction=in/out
    # Баланс кассы НЕПРАВИЛЬНЫЙ
```

**DELETE расхода** (`expenses.py:455-495`) — сделано правильно:
```python
@router.delete("/{expense_id}")
async def delete_expense(...):
    expense.is_active = False
    # Если был расход с кассы — создаётся компенсирующая транзакция:
    if expense.cash_register_id and not expense.is_reimbursement:
        db.add(CashTransaction(
            direction=TxDirection.inflow,        # ← обратная операция
            amount=expense.amount_cny,
            balance_after=cur_bal + expense.amount_cny,
            notes=f"Отмена расхода: {expense.description[:80]}",
        ))
```

**Итог:** расходы откатываются корректно, **платежи — нет**.  
Каждый удалённый платёж оставляет "мёртвую" транзакцию в кассе.

---

### 1.5 Редактирование кассы

Есть `PATCH /cash-registers/{id}` (`cash_registers.py:114`):
```python
# Можно менять: name, currency, notes, is_active
# initial_balance — отсутствует в CashRegisterUpdate
```
Нельзя задать начальный баланс ни при создании, ни при редактировании.

---

## 2. УДАЛЕНИЯ (SOFT DELETE)

### 2.1 Сводная таблица

| Сущность | Тип удаления | Поле | Файл эндпоинта |
|----------|-------------|------|----------------|
| Payment | Soft | `is_active = False` | `payments.py:601` |
| Expense | Soft | `is_active = False` | `expenses.py:455` |
| Order | Статус | `status = cancelled` | `orders.py:767` |
| Purchase | Soft | `is_deleted = True` | `purchases.py:479` |
| CashTransaction | **Нет DELETE** | — | — |
| CashRegister | Soft через PATCH | `is_active = False` | `cash_registers.py:114` |

### 2.2 Фильтры в GET-запросах

```python
# payments.py:364
select(Payment).where(Payment.is_active == True)

# expenses.py:175
select(Expense).where(Expense.is_active == True)

# orders.py:440
select(Order).where(Order.status != OrderStatus.cancelled)

# purchases.py:196
select(Purchase).where(Purchase.is_deleted == False)

# cash_registers.py — CashTransaction: ФИЛЬТРА НЕТ
# Все транзакции видны и участвуют в расчётах
```

### 2.3 Удалённые записи в расчётах

| Расчёт | Исключает удалённые? |
|--------|---------------------|
| Баланс кассы | ❌ CashTransaction не фильтруется |
| P&L (выручка) | ✅ `status != cancelled` |
| P&L (себестоимость) | ✅ `Purchase.is_deleted == False` |
| P&L (расходы) | ✅ `Expense.is_active == True` |
| Отчёт по клиентам | ✅ `status != cancelled` |
| Статус оплаты заказа | ✅ `Payment.is_active == True` (через аллокации) |

### 2.4 Несогласованность флагов

- `Payment`, `Expense`, `CashRegister` → `is_active`
- `Purchase` → `is_deleted`
- `Order` → `status`
- `CashTransaction` → нет механизма удаления вообще

---

## 3. АУДИТ

### 3.1 Модель AuditLog (`models/audit_log.py`)

```python
class AuditLog(Base):
    id:           UUID
    user_id:      UUID (ForeignKey users.id)
    entity_type:  str(100)       # "payment", "expense", "order" и т.д.
    entity_id:    UUID
    action:       AuditActionEnum  # create | update | delete
    changes:      JSONB           # {"old": {...}, "new": {...}}
    created_at:   DateTime(timezone=True)
```

### 3.2 Что реально логируется

| Сущность | CREATE | UPDATE | DELETE |
|----------|--------|--------|--------|
| Payment | ✅ | ✅ | ✅ `{soft_deleted: True}` |
| Expense | ✅ | ✅ | ✅ |
| Order | ✅ | ✅ | ✅ |
| Purchase | ✅ | ✅ | ✅ |
| User | ✅ | ✅ | ✅ |
| Counterparty | ✅ | ✅ | ✅ |
| OrderFile | ✅ | — | ✅ |
| OrderItemPhoto | ✅ | — | ✅ |
| **CashTransaction** | ❌ | ❌ | ❌ |
| **CashTransfer** | ❌ | ❌ | ❌ |

### 3.3 Пробел: кассовые операции без аудита

Все операции с кассой (создание транзакций при платежах, расходах, переводах) не оставляют следа в `audit_log`.

При разборе расхождений невозможно ответить:
- Кто и когда внёс деньги в кассу?
- Кто создал перевод между кассами?
- Почему баланс не сходится?

Аудит при DELETE платежа пишет `{soft_deleted: True}` — но **не отражает**, что кассовая транзакция при этом не откатилась. Это скрывает проблему.

---

## 4. ПРИБЫЛЬ (P&L)

### 4.1 Как считается

Всё вычисляется **на лету из БД** в `report_service.py`. Хранённые `total_sale_cny` и `total_cost_cny` в таблице `orders` используются для суммирования.

**Выручка** (`report_service.py:49-60`):
```python
order_filter = [
    Order.order_date >= date_from,
    Order.order_date <= date_to,
    Order.status != OrderStatus.cancelled,   # ← единственный фильтр
]
revenue = SUM(Order.total_sale_cny) WHERE *order_filter
```

**Себестоимость** (`report_service.py:73-82`):
```python
COGS = SUM(PurchaseItem.cost_amount)
    JOIN Purchase WHERE Purchase.is_deleted == False
    JOIN OrderItem WHERE OrderItem.order_id IN (заказы из order_filter)
```

**Расходы** (`report_service.py:85-105`):
```python
expenses = SUM(Expense.amount_cny) WHERE
    expense_date IN [date_from, date_to]
    AND is_active == True
    AND NOT (is_reimbursement == True AND reimburse_status == "rejected")
```

### 4.2 Хранённые суммы в orders

`total_sale_cny` и `total_cost_cny` — хранённые числа, обновляются:
- При создании заказа (`orders.py:628`)
- При изменении позиций/сборов (`orders.py:742`)
- При изменении закупок (`purchases.py` → `_recalc_order_cost()`)

При отмене заказа (`cancel_order`, `orders.py:777`):
- Статус → `cancelled`
- **`total_sale_cny` НЕ обнуляется** — число остаётся в БД
- Заказ выпадает из P&L через фильтр `status != cancelled` ✅

### 4.3 Риск при отмене заказа

Сценарий риска:
1. Заказ создан, `total_sale_cny = 100 000 CNY`
2. Заказ отменён → выпал из P&L ✅
3. Кто-то напрямую меняет статус в БД обратно на `active`
4. Заказ снова попадает в P&L с той же суммой

При текущем API (нет эндпоинта разотмены) риск минимальный.  
Архитектурно ненадёжно — защиты нет.

---

## МАТРИЦА РИСКОВ

| № | Приоритет | Риск | Где | Описание |
|---|-----------|------|-----|----------|
| П1 | 🔴 КРИТИЧНО | Удаление платежа не откатывает кассу | `payments.py:601` | `payment.is_active=False`, но `CashTransaction` остаётся. Баланс кассы неправильный после каждого удалённого платежа. |
| П2 | 🔴 КРИТИЧНО | CashTransaction нельзя отменить | `cash_registers.py` | Нет поля `is_active`, нет механизма отмены. Ошибочные транзакции нельзя убрать из расчёта. |
| П3 | 🟠 ВЫСОКИЙ | Кассовые операции не логируются | `payments.py:519`, `cash_registers.py:245` | Создание/изменение `CashTransaction` и `CashTransfer` не пишется в `audit_log`. История кассы невосстановима. |
| П4 | 🟠 ВЫСОКИЙ | Нельзя задать начальный баланс кассы | `models/cash_register.py` | Нет поля `initial_balance`. Касса всегда начинается с нуля — невозможно завести кассу с реальным остатком. |
| П5 | 🟡 СРЕДНИЙ | `balance_after` устаревает при изменении истории | `cash_registers.py` | Если вставить/удалить транзакцию в середину — все последующие `balance_after` становятся неверными. Пока не используется в расчётах — не критично. |
| П6 | 🟡 СРЕДНИЙ | `total_sale_cny` не обнуляется при отмене заказа | `orders.py:777` | При `cancel_order` хранённое число остаётся. Риск при ручном изменении статуса в БД. |
| П7 | 🟡 СРЕДНИЙ | Разные флаги soft-delete | `payments.py`, `purchases.py` | `is_active` vs `is_deleted` — несогласованность усложняет поддержку. |
| П8 | 🟢 НИЗКИЙ | CashTransfer не попадает в аудит | `cash_registers.py:245` | Переводы между кассами не логируются. |

---

## ПЛАН ИСПРАВЛЕНИЙ (предварительный)

### Этап 1 — Критичное (касса)
1. **DELETE платежа** → добавить компенсирующую `CashTransaction` (как в `delete_expense`)
2. **`initial_balance`** → добавить поле в `CashRegister`, миграция, учесть в `_get_balance()`
3. **Аудит кассы** → `write_audit` при создании `CashTransaction` и `CashTransfer`

### Этап 2 — Архитектура
4. **Унификация soft-delete** → перевести `Purchase` с `is_deleted` на `is_active`
5. **`balance_after`** — рассмотреть отказ от хранения, оставить только вычисляемый баланс

### Этап 3 — Защита
6. **`total_sale_cny` при отмене** → обнулять или добавить защиту от повторной активации заказа

---

*Отчёт составлен на основе анализа кода. Данные в БД не проверялись.*  
*До исправления П1 балансам касс доверять нельзя — при каждом удалённом платеже баланс расходится.*
