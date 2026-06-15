# ОТЧЁТ ЭТАПА 1 — Разведка синхронизации / ЛК клиента

Дата: 2026-06-11  
Статус: **ждём ОК по плану**

---

## 1. Синхронизация логистики (ERP → сайт)

### Поток данных

```
create_order / update_order
  [backend/app/api/orders.py : ~660, ~807]
  → bt.code == "logistics"
  → sync_order_to_site(order, db)
      [backend/app/integrations/irsway_site/service.py : sync_order_to_site()]
      → _build_shipment_payload()   — items, charges, client_code, partner_code, erp_order_id
      → если external_shipment_number И номер не менялся
            → PATCH /api/v1/shipments/{number}/   (без поля "number" в теле)
        иначе (новый или номер сменился)
            → DELETE старого (405 → игнорируем) + POST /api/v1/shipments/
      → сохраняет в Order: external_shipment_id, external_shipment_number,
                           external_invoice_url, external_tracking_url, sync_status
```

### Токен

`Authorization: Token {api_token}` — хранится в `IntegrationSettings` (БД ERP).  
На сайте: `shipments/api/authentication.py → ERPTokenAuthentication`.

### Поля sync в модели Order

| Поле | Описание |
|------|----------|
| `sync_status` | `synced` / `failed` / `disabled` / `pending` |
| `external_shipment_number` | номер отправления на сайте (= ERP order_number при создании) |
| `external_shipment_id` | внутренний ID сайта |
| `external_invoice_url` | URL накладной, сгенерированной сайтом |
| `external_tracking_url` | URL публичного трекинга |

### Кнопки в OrderDetailPage (frontend)

| Кнопка | Endpoint ERP | Что делает |
|--------|-------------|------------|
| «Синхронизировать» / «Снова» | `POST /api/orders/{id}/sync-to-site` | вызывает sync_order_to_site |
| «Скачать накладную» | — | ссылка на `external_invoice_url` |
| «Отслеживание» | — | ссылка на `external_tracking_url` |
| «Отправить статус груза» | `POST /api/orders/{id}/push-status` | → `POST /api/v1/shipments/{number}/statuses/` |

### Накладная

Генерируется **на сайте** при `generate_invoice=True` в payload.  
URL возвращается в ответе → сохраняется в `order.external_invoice_url`.

---

## 2. Торговые заказы — что уже готово

### ERP (service.py)

`sync_trade_order_to_site()` — существует, вызывается **автоматически** при create/update торгового заказа (без кнопки, без sync_status).

Поля payload:
```
number, erp_order_id, client_code, client_name, goods_name,
order_date, currency, total_amount_cny, paid_amount_cny, payment_status, notes
```

### Сайт

| Элемент | Статус |
|---------|--------|
| Модель `TradeOrder` | ✅ есть (`shipments/models.py`) |
| `POST /api/v1/trade-orders/` | ✅ есть |
| `PATCH /api/v1/trade-orders/{number}/` | ✅ есть |
| `GET /api/v1/trade-orders/{number}/` | ✅ есть |
| Привязка к клиенту | ✅ по `client_code` → `ClientProfile` → `owner` |
| Отображение в ЛК | ✅ есть в `client_dashboard` → `trade_orders` → шаблон |

### Модель TradeOrder (сайт)

```python
number           # уникальный, = ERP order_number
erp_order_id     # UUID из ERP
owner            # FK User (выставляется по client_code)
client_code
client_name
goods_name
order_date
currency
total_amount_cny
paid_amount_cny
payment_status   # unpaid / partial / paid
invoice_url      # URL PDF — поле есть, но ERP сейчас не передаёт
notes
remaining_cny    # property: total - paid
```

### Что не хватает торговым

1. `invoice_url` — ERP не передаёт (накладная для торговли генерируется в ERP, не на сайте)
2. Нет sync-кнопки и sync_status в UI ERP — синхронизация тихая
3. Вкладка в ЛК не выделена (HTML-блок без табов под логистикой)

---

## 3. Склад — структура данных

### Модель WarehouseBox (ERP)

```
backend/app/models/warehouse_box.py
backend/app/api/warehouse_boxes.py
```

| Поле | Тип | Описание |
|------|-----|----------|
| `box_code` | str | уникальный код (BOX-A2424-001) |
| `counterparty_id` | UUID FK | → Counterparty.code = client_code |
| `warehouse_id` | UUID FK | склад |
| `weight` | Decimal(12,3) | кг |
| `volume` | Decimal(12,4) | м³ |
| `density` | Decimal(12,3) | кг/м³ |
| `item_name` | str | наименование |
| `status` | enum | `on_warehouse` / `shipped` |
| `received_at` | datetime | |
| `shipped_at` | datetime | null если на складе |
| `items` | list[BoxItem] | позиции (name, quantity, tracking_code) |
| `photos` | list[BoxPhoto] | фото (до 3 шт) |

### Связь ERP ↔ сайт

`Counterparty.code` (ERP, поле `String(20)`) == `ClientProfile.client_code` (сайт)

### На сайте

Нет ни модели, ни endpoint для склада. **Рекомендуется pull-архитектура**: сайт запрашивает ERP при открытии вкладки.

---

## 4. Взаиморасчёт — безопасные поля

### Источник данных

`backend/app/services/report_service.py → get_client_detail(db, client_id, date_from, date_to)`

### Таблица полей

| Поле | ✅/❌ | Комментарий |
|------|-------|-------------|
| `order_number` | ✅ | номер заказа |
| `order_date` | ✅ | дата заказа |
| `total_sale_cny` | ✅ | выставленная сумма (счёт клиенту) |
| `paid_cny` | ✅ | оплачено по заказу |
| `remaining` | ✅ | остаток долга по заказу |
| `payment_status` | ✅ | unpaid / partial / paid |
| `total_revenue` | ✅ | итого выставлено |
| `total_paid` | ✅ | итого оплачено |
| `balance` | ✅ | сальдо (долг или переплата) |
| `cogs` | ❌ | себестоимость закупки — **не отдавать** |
| `direct_expenses` | ❌ | прямые расходы — **не отдавать** |
| `profit` | ❌ | прибыль по заказу — **не отдавать** |
| `client_expenses` | ❌ | расходы на клиента — **не отдавать** |
| `total_cogs` | ❌ | суммарный закуп — **не отдавать** |
| `net_profit` | ❌ | чистая прибыль — **не отдавать** |

### Принцип безопасности

Опасные поля **физически не включать в payload** нового endpoint — не фильтровать на фронте.  
Новый endpoint: `GET /api/client-portal/reconciliation/{client_code}` — только safe-поля.

---

## 5. ЛК клиента (сайт) — текущая структура

```
URL:      GET /dashboard/
View:     shipments/views_client.py → client_dashboard()
Template: shipments/templates/shipments/dashboard.html
Auth:     @login_required (Django session)
```

### Что сейчас в шаблоне

Два HTML-блока подряд — без вкладок:
1. «My shipments» — таблица логистических отправлений с прогресс-баром статусов
2. «My orders» — таблица торговых заказов (number, goods, total, paid, remaining, status, invoice)

### ClientProfile

```python
# shipments/models.py
user         # OneToOne → Django User
phone        # unique, нормализованный
client_code  # unique, uppercase — ключ связи с ERP
language     # ru / zh / en  (для i18n)
```

### i18n

Django `{% trans %}` + locale-файлы: `locale/ru/`, плюс `ar/`, `tr/` (неполные).  
Языки для новых вкладок: **ru / zh / en**.

---

## 6. Отличие торгового заказа от логистического (ERP)

| | Логистика | Торговля |
|-|-----------|----------|
| `business_type.code` | `"logistics"` | `"trade"` |
| Позиции OrderItem | вес, объём, мест, цена/кг | наименование, количество, цена |
| Синхронизация | `sync_order_to_site` | `sync_trade_order_to_site` |
| Накладная | генерирует сайт | генерирует ERP (order_pdf.py) |
| sync_status / кнопки | ✅ есть в UI | ❌ нет (тихая) |
| external_* поля | заполняются | не заполняются |

---

## ПЛАН РЕАЛИЗАЦИИ (на согласование)

### Задача 1 — Торговые заказы в ЛК

**ERP:**
- Добавить кнопку «Синхронизировать» в OrderDetailPage для торговых заказов (аналог логистики)
- Передавать `invoice_url` в payload (ссылка на PDF накладной из ERP)
- Сохранять sync_status для торговых (уже есть поле в модели)

**Сайт:**
- Вынести «My orders» в отдельную вкладку «Торговля»
- i18n строк вкладки (ru/zh/en)

### Задача 2 — Склад (pull-архитектура)

**ERP:**
- Новый endpoint `GET /api/client-portal/warehouse/{client_code}` с токен-аутентификацией
- Возвращает: короба на складе по клиенту — box_code, item_name, items[], weight, volume, density, received_at

**Сайт:**
- Новая вкладка «Склад» — при открытии JS-fetch к ERP endpoint
- Таблица: код коробки, позиции, вес, объём, плотность, дата поступления
- i18n (ru/zh/en)

### Задача 3 — Взаиморасчёт (pull-архитектура)

**ERP:**
- Новый endpoint `GET /api/client-portal/reconciliation/{client_code}` — только safe-поля
- Аутентификация: тот же ERP-токен (из IntegrationSettings)

**Сайт:**
- Новая вкладка «Взаиморасчёт» — JS-fetch к ERP endpoint
- Таблица заказов: номер, дата, счёт, оплачено, остаток, статус
- Итоги: общий счёт / оплачено / баланс
- i18n (ru/zh/en)

### Итог — 4 вкладки в dashboard.html

```
[ Логистика ]  [ Торговля ]  [ Склад ]  [ Взаиморасчёт ]
```

### Аутентификация ERP-endpoints для сайта

Вариант A: тот же `Authorization: Token {api_token}` из IntegrationSettings  
Вариант B: отдельный read-only токен для клиентского портала  
**Рекомендую вариант A** — инфраструктура уже есть, не нужно новых таблиц.

---

*Жду ОК по плану или правок перед Этапом 2.*
