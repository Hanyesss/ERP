# Разведка: отмена/удаление заказов и кросс-валютные расходы

**Дата:** 2026-06-03  
**Тип:** аудит — только чтение, код не менялся  
**Статус:** выявлены 5 проблем, одна критичная

---

## 1. Отмена заказа — `cancel_order`

**Файл:** `backend/app/api/orders.py:769`

```python
@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order(order_id, db, current_user):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = OrderStatus.cancelled          # ← только смена статуса
    await write_audit(db, current_user.id, "order", order.id,
                      AuditActionEnum.delete, {"order_number": order.order_number})
    await db.commit()
```

**Выводы:**
- Физического удаления нет — заказ остаётся в БД со статусом `cancelled`
- Нет проверки бизнес-типа (logistics/trade) — можно отменить любой заказ
- Нет проверки `sync_status` — синхронизированный логистический заказ отменяется так же
- Аудит пишется: `action=delete`, `{"order_number": "..."}` — след есть
- Нет отката: платежи, расходы, закупки по заказу остаются без изменений

---

## 2. Логистика vs Торговля — нет блокировки нигде

**Файл:** `frontend/src/components/orders/OrderTable.tsx:154–166`

```tsx
render: (_, row) => (
  <Space>
    <Button icon={<EyeOutlined />} size="small" onClick={...} />
    <Button icon={<EditOutlined />} size="small" onClick={...} />
    <Popconfirm
      title={t("order.cancel_confirm")}
      onConfirm={() => cancelMutation.mutate(row.id)}
    >
      <Button icon={<DeleteOutlined />} size="small" danger />
    </Popconfirm>
  </Space>
),
```

Кнопка «Удалить» (красный `DeleteOutlined`) показывается для **всех** заказов без каких-либо условий. Ни `business_type_code !== "logistics"`, ни проверки `sync_status` нет.

Бэкенд (`cancel_order`) тоже не блокирует по типу или статусу синхронизации.

> Если пользователь говорит «логистику нельзя отменить» — это не соответствует коду.
> В текущей версии ограничений нет ни на фронте, ни на бэке.

---

## 3. Фильтр «Отменённые» — баг: всегда пустой

**Файл:** `backend/app/api/orders.py:440,449–450`

```python
stmt = stmt.where(Order.status != OrderStatus.cancelled)   # строка 440 — всегда

# ... позже:
if order_status:
    stmt = stmt.where(Order.status == order_status)        # строка 450 — если передан ?status=
```

При запросе `GET /api/orders?status=cancelled` выполняются **оба** условия:

```sql
WHERE status != 'cancelled'   -- строка 440, всегда применяется
  AND status  = 'cancelled'   -- строка 450, применяется при ?status=cancelled
```

Результат: `0 строк` всегда. Отменённые заказы **недоступны через API вообще никак**.

**Фронтенд** (`OrderTable.tsx:171`):
```tsx
const statusOptions = ["new", "active", "closed", "cancelled"]
  .map(s => ({ value: s, label: t(`order.status_${s}`) }));
```

Фильтр `cancelled` есть в выпадающем списке — но из-за бага бэкенда всегда возвращает пустой список. Пользователь отменил заказ, выбрал «Отменённые» → видит пусто. Ощущение что «заказ пропал бесследно».

---

## 4. Удаление заказа — мягкое, но с неполным аудитом

`DELETE /api/orders/{id}` → `cancel_order` → **мягкое удаление** (`status=cancelled`).

Физического `DELETE` из БД нигде нет. Заказ остаётся в таблице `orders`.

**Аудит:**
```python
await write_audit(db, current_user.id, "order", order.id,
                  AuditActionEnum.delete,
                  {"order_number": order.order_number})   # ← только номер!
```

Пишется только `order_number`. **Не сохраняются:** `total_sale_cny`, `client_id`, `manager_id`, `payment_status`, `total_cost_cny` — невозможно восстановить что именно было в заказе до отмены.

**Проблема целостности:** после отмены заказ пропадает из интерфейса (баг п.3), но его платежи, расходы и закупки остаются в системе и по-прежнему влияют на отчёты и балансы. Создаётся иллюзия «заказ удалён», хотя данные никуда не делись.

---

## 5. Кросс-валютный расход — критичный баг кассы

### Как работает сейчас

**`create_expense`** (`expenses.py:354–415`):
```python
rate = body.rate_to_cny                # курс валюты расхода → CNY
amount_cny = body.amount * rate        # сумма в CNY для отчётов

# При списании с кассы:
await _record_cash_outflow(
    db,
    body.cash_register_id,
    amount_cny,                        # ← списывается CNY-эквивалент, не исходная сумма
    ...
)
```

**`_record_cash_outflow`** (`expenses.py:36–64`):
```python
balance_after = current_balance - amount   # amount = amount_cny
tx = CashTransaction(
    amount=amount,                         # в транзакцию пишется amount_cny
    ...
)
```

### Пример — где ломается

| | |
|--|--|
| Расход | 1000 USDT на рекламу |
| Курс USDT→CNY | 7.25 |
| `amount_cny` | 7250 |
| Касса | USDT (баланс: 500 USDT) |
| **Что списывается** | **7250** (как будто это юани/USDT) |
| **Баланс USDT после** | 500 − 7250 = **−6750** ← НЕВЕРНО |
| **Должно быть** | 500 − 1000 = −500 |

### Когда работает корректно

Только если валюта расхода = CNY (базовая валюта). Тогда `rate=1`, `amount_cny=amount`, списывается правильно.

### Корень проблемы

`_record_cash_outflow` принимает `amount` и списывает его «как есть», не зная валюту кассы. Нет конвертации `amount_cny → валюта кассы`. Нет проверки совместимости валют расхода и кассы.

---

## Итоговая таблица проблем

| # | Проблема | Тяжесть | Файл:строка |
|---|----------|---------|-------------|
| А | Отменённые заказы недоступны — двойной WHERE (`!= cancelled AND = cancelled`) | 🔴 Высокая | `orders.py:440,450` |
| Б | Кнопка «Удалить» для всех заказов без ограничений по типу/статусу синхронизации | 🟡 Средняя | `OrderTable.tsx:157` |
| В | Аудит отмены сохраняет только `order_number`, без финансовых данных | 🟡 Средняя | `orders.py:780` |
| Г | Расход в иностранной валюте на валютную кассу списывает CNY-эквивалент вместо исходной суммы | 🔴 **Критичная** | `expenses.py:411–415` |
| Д | При отмене заказа платежи/расходы/закупки не пересчитываются и не отвязываются | 🟡 Средняя | `orders.py:769` |

---

## Рекомендации к исправлению

### А — Отменённые заказы (быстро)
Убрать жёсткий фильтр `status != cancelled` из базового запроса. Вместо этого — если `?status` не передан, показывать всё кроме cancelled (текущее поведение). Если `?status=cancelled` — показывать только cancelled. Одно условие `if order_status: stmt.where(status == order_status) else: stmt.where(status != cancelled)`.

### Г — Кросс-валютный расход (критично, требует миграции)
В `_record_cash_outflow` нужно получать валюту кассы и списывать правильную сумму:
- Если валюта расхода = валюта кассы → списывать `body.amount`
- Если валюта расхода = CNY, касса = иная валюта → списывать `amount / rate_kassy_to_cny`
- Иначе: не разрешать или показывать предупреждение

### Б — Кнопка удаления (UX)
Скрывать кнопку если `row.sync_status === "synced"` и `row.business_type_code === "logistics"`. Или добавить предупреждение что логистический синхронизированный заказ нельзя отменять без отмены на irsway.

### В — Аудит (просто)
В `cancel_order` добавить в `changes` весь снимок заказа: `{"order_number", "total_sale_cny", "client_name", "payment_status", ...}`.

### Д — Отвязка данных (сложно, отдельно)
Это архитектурный вопрос. Минимально: пересчитать `payment_status` связанных платежей и закупок при отмене заказа.
