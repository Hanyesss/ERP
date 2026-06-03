# IRS ERP — Описание проекта

## Общее

Внутренняя ERP-система для компании, занимающейся торговлей и логистикой из Китая.  
Управляет заказами, закупками, платежами, расходами, складом и аналитикой.

**Боевой сервер:** https://erp.irsway.com (порт 8443)  
**Репозиторий:** https://github.com/Hanyesss/irserp

---

## Стек технологий

| Слой | Технология |
|------|-----------|
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL 16 |
| Frontend | React 18 + TypeScript, Ant Design, React Query, Vite |
| Инфраструктура | Docker Compose (3 контейнера) |
| Аутентификация | JWT в cookie (8 часов), bcrypt |
| PDF | WeasyPrint + Jinja2 |
| Excel | openpyxl |
| QR-коды | qrcode[pil] |
| HTTP-клиент | httpx (для интеграции с irsway.com) |

---

## Инфраструктура (Docker Compose)

```
erp_postgres   — PostgreSQL 16, порт 5432
erp_backend    — FastAPI, порт 8000 (внутренний)
erp_frontend   — React/nginx, порт 80 (или APP_PORT)
```

Переменные окружения в `.env`:
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `DATABASE_URL` — asyncpg строка подключения
- `JWT_SECRET` — секрет для JWT
- `JWT_EXPIRE_MINUTES` — время жизни токена (480 = 8 часов)
- `CORS_ORIGINS` — разрешённые origins

---

## Роли пользователей

| Роль | Доступ |
|------|--------|
| `admin` | Полный доступ ко всему |
| `accountant` | Платежи, кассы, расходы, отчёты, одобрение возмещений |
| `manager` | Свои заказы, курсы валют, дашборд |
| `purchaser` | Закупки, просмотр заказов |
| `employee` | Создание расходов, просмотр своих заказов |

---

## Модели данных (30 таблиц)

### Пользователи
- **users** — логин, хэш пароля, полное имя, язык (ru/zh), is_active
- **user_role_entries** — связь user ↔ role (employee/manager/purchaser/accountant/admin)
- **sessions** — JWT сессии (опционально)

### Справочники
- **companies** — компании (name, name_cn)
- **counterparties** — контрагенты: клиенты и поставщики (name, name_cn, code, type: client|supplier|both, default_currency, contact_info JSONB)
- **business_types** — типы бизнеса (торговля, логистика, услуги)
- **expense_categories** — категории расходов (сидируются в миграции)
- **exchange_rates** — курсы валют (RUB/USDT/USD → CNY)

### Заказы
- **orders** — основная таблица заказов
  - order_number (unique), client_id, manager_id, business_type_id
  - status: new|active|closed|cancelled
  - total_sale_cny, total_cost_cny
  - payment_status, supplier_payment_status: unpaid|partial|paid
  - Логистика: recipient, destination, arrival_date, tracking_number, warehouse_id
  - Интеграция irsway: external_shipment_id/number/invoice_url/tracking_url, sync_status
- **order_items** — позиции заказа (name, name_cn, quantity, sale_price, sale_currency, sale_rate_to_cny, weight_kg, volume_m3, price_per_kg, cargo_value)
- **order_charges** — дополнительные сборы (страховка, упаковка, доставка КНР и т.д.)
- **order_files** — документы заказа (invoice, packing, cargo_photo, other)
- **order_item_photos** — фотографии товаров

### Закупки
- **purchases** — закупки у поставщиков (purchase_number, supplier_id, currency, total_amount, rate_to_cny, total_amount_cny, payment_status, order_id для логистики)
- **purchase_items** — позиции закупки (order_item_id, quantity, cost_price, cost_amount)
- **purchase_files** — документы закупки
- **purchase_payments_link** — привязка платежей к закупкам (payment_id, purchase_id, amount_cny)

### Платежи
- **payments** — входящие/исходящие платежи (direction: in|out, counterparty_id, currency, amount, rate_to_cny, amount_cny, cash_register_id)
- **payment_allocations** — распределение входящих платежей по заказам (payment_id, order_id, amount_cny)

### Расходы
- **expenses** — расходы компании
  - expense_date, category_id, currency, amount, amount_cny
  - link_type: order|client|none
  - is_reimbursement — возмещение сотруднику
  - reimburse_status: pending|approved|paid|rejected
  - cash_register_id

### Кассы
- **cash_registers** — кассы (name, currency)
- **cash_transactions** — операции кассы (direction, amount, balance_after)
- **cash_transfers** — переводы между кассами (from_register_id, to_register_id, from_amount, to_amount)

### Склад
- **warehouses** — склады (name, name_cn, city)
- **warehouse_boxes** — коробки (box_code unique, counterparty_id, warehouse_id, weight, volume, status: on_warehouse|shipped)
- **packing_lists** — листы упаковки (box_ids JSONB, pdf_path)

### Система
- **notifications** — уведомления пользователей (type, title, body, link, is_read)
- **audit_logs** — логирование действий (entity_type, entity_id, action: create|update|delete, changes JSONB)
- **integration_settings** — конфиги интеграций (base_url, api_token, is_enabled)
- **section_read_markers** — отметки прочтения разделов меню (user_id, section, last_read_at)

---

## API эндпоинты

### Auth
```
POST /api/auth/login       — вход (cookie JWT)
POST /api/auth/logout      — выход
GET  /api/auth/me          — текущий пользователь
```

### Users (только admin)
```
GET    /api/users
POST   /api/users
GET    /api/users/{id}
PUT    /api/users/{id}
DELETE /api/users/{id}
```

### Counterparties
```
GET    /api/counterparties?search&type&page
GET    /api/counterparties/{id}
POST   /api/counterparties
PATCH  /api/counterparties/{id}
DELETE /api/counterparties/{id}
POST   /api/counterparties/{id}/create-site-account   — создать аккаунт на irsway.com
POST   /api/counterparties/{id}/link-site-account     — привязать к существующему
PATCH  /api/counterparties/{id}/update-site-credentials
```

### Orders
```
GET    /api/orders?status&manager_id&client_id&date_from&date_to&page
GET    /api/orders/{id}
POST   /api/orders
PATCH  /api/orders/{id}
DELETE /api/orders/{id}
POST   /api/orders/{id}/close
GET    /api/orders/{id}/available-for-purchase
GET    /api/orders/{id}/history
GET    /api/orders/next-number?date
```

### Purchases
```
GET    /api/purchases?supplier_id&payment_status&date_from&date_to&order_id&page
GET    /api/purchases/{id}
POST   /api/purchases
PATCH  /api/purchases/{id}
DELETE /api/purchases/{id}
```

### Payments
```
GET    /api/payments?direction&counterparty_id&currency&date_from&date_to&page
GET    /api/payments/{id}
POST   /api/payments
PATCH  /api/payments/{id}
DELETE /api/payments/{id}
GET    /api/payments/for-order/{order_id}
```

### Expenses
```
GET    /api/expenses?category_id&link_type&reimburse_status&date_from&date_to&page
GET    /api/expenses/{id}
POST   /api/expenses
PATCH  /api/expenses/{id}
DELETE /api/expenses/{id}
POST   /api/expenses/{id}/approve
POST   /api/expenses/{id}/reject
POST   /api/expenses/{id}/mark-paid
```

### Dashboard
```
GET /api/dashboard/widgets?date_from&date_to
```

### Exchange Rates
```
GET  /api/exchange-rates?currency&date_from&date_to&page
POST /api/exchange-rates
GET  /api/exchange-rates/check?date&currencies
```

### Warehouses & Boxes
```
GET    /api/warehouses
POST   /api/warehouses
PATCH  /api/warehouses/{id}
DELETE /api/warehouses/{id}

GET    /api/warehouse-boxes?warehouse_id&counterparty_id&status&page
POST   /api/warehouse-boxes
PATCH  /api/warehouse-boxes/{id}
POST   /api/warehouse-boxes/{id}/ship
POST   /api/warehouse-boxes/packing-list
GET    /api/warehouse-boxes/packing-list/{id}
```

### Cash Registers
```
GET    /api/cash-registers
POST   /api/cash-registers
PATCH  /api/cash-registers/{id}
GET    /api/cash-registers/{id}/transactions
POST   /api/cash-transfers
```

### Notifications
```
GET  /api/notifications?unread_only&limit
GET  /api/notifications/unread-count
GET  /api/notifications/section-counts     — счётчики новых по разделам (только admin)
POST /api/notifications/{id}/mark-read
POST /api/notifications/mark-all-read
POST /api/notifications/section-read/{section}
DELETE /api/notifications/{id}
```

### Reports
```
GET /api/reports/pnl?date_from&date_to&business_type_id
GET /api/reports/pnl/export
GET /api/reports/by-client?date_from&date_to
GET /api/reports/by-client/export
GET /api/reports/by-supplier?date_from&date_to
GET /api/reports/by-supplier/export
GET /api/reports/expenses?date_from&date_to
GET /api/reports/expenses/export
GET /api/reports/tonnage?date_from&date_to
GET /api/reports/tonnage/export
```

### Integration (irsway.com)
```
GET  /api/integration-settings/{name}
POST /api/integration-settings/{name}
POST /api/integration-settings/{name}/test
```

### References
```
GET /api/references/managers
GET /api/references/business-types
GET /api/references/expense-categories
GET /api/references/employees
```

### Files
```
POST   /api/orders/{id}/files
GET    /api/orders/{id}/files
DELETE /api/order-files/{id}

POST   /api/orders/{id}/items/{item_id}/photos
DELETE /api/order-item-photos/{id}

POST   /api/purchases/{id}/files
DELETE /api/purchase-files/{id}
```

---

## Миграции (20 штук)

| # | Что добавлено |
|---|---------------|
| 0001 | Начальная схема: users, counterparties, orders, purchases, payments, expenses |
| 0002 | Поля логистики в orders/order_items (вес, объём, склад) |
| 0003 | Роли пользователей, purchase_items |
| 0004 | is_active в payments (soft-delete) |
| 0005 | Модуль расходов (expenses, expense_categories, возмещения) |
| 0006 | Сид категорий расходов |
| 0007 | order_id в purchases (для логистических закупок) |
| 0008 | Склады (warehouses) |
| 0009 | model/specification в order_items, фотографии товаров |
| 0010 | Уведомления (notifications) |
| 0011 | Интеграция irsway (sync_status, sync_error, synced_at в orders) |
| 0012 | Новые категории расходов (упаковка и др.) |
| 0013 | Поле code в counterparties |
| 0014 | Кассы (cash_registers, cash_transactions) |
| 0015 | Документы закупок (purchase_files), is_deleted в purchases |
| 0016 | Переводы между кассами (cash_transfers) |
| 0017 | Коробки на складе (warehouse_boxes, packing_lists) |
| 0018 | cash_register_id в expenses |
| 0019 | Индексы производительности (box_code, counterparty_id и др.) |
| 0020 | Маркеры прочтения разделов (section_read_markers) |

---

## Фронтенд — страницы

| Страница | Путь | Доступ |
|----------|------|--------|
| Логин | /login | Все |
| Дашборд | /dashboard | Все (виджеты по роли) |
| Контрагенты | /counterparties | Все роли |
| Заказы | /orders | Все роли |
| Детали заказа | /orders/:id | Все роли |
| Форма заказа | /orders/new, /orders/:id/edit | manager+ |
| Закупки | /purchases | purchaser+ |
| Детали закупки | /purchases/:id | purchaser+ |
| Форма закупки | /purchases/new | purchaser+ |
| Платежи | /payments | accountant+ |
| Детали платежа | /payments/:id | accountant+ |
| Форма платежа | /payments/new | accountant+ |
| Расходы | /expenses | Все роли |
| Детали расхода | /expenses/:id | Все роли |
| Форма расхода | /expenses/new, /expenses/:id/edit | Все роли |
| Курсы валют | /exchange-rates | manager+ |
| Склады | /warehouses | employee+ |
| Кассы | /cash-registers | accountant+ |
| Отчёты | /reports | manager+ |
| Пользователи | /users | admin |
| Интеграции | /settings/integrations | admin |
| Уведомления | /notifications | Все |

---

## Ключевые бизнес-процессы

### Расчёт итогов заказа
- `total_sale_cny` = Σ(quantity × sale_price × rate_to_cny) по позициям + сборы
- `total_cost_cny` = Σ(cost_amount) из purchase_items связанных закупок
- `payment_status` = пересчёт из PaymentAllocations (допуск 5 CNY на курсовую разницу)
- `supplier_payment_status` = пересчёт из статусов закупок

### Платёж → Заказ
1. Создаётся Payment (direction=in, counterparty=клиент)
2. Через PaymentAllocation привязывается к одному или нескольким заказам
3. Автоматически пересчитывается payment_status каждого заказа
4. При полной оплате — уведомление менеджеру и бухгалтеру

### Платёж → Закупка
1. Создаётся Payment (direction=out, counterparty=поставщик)
2. Через PurchasePaymentLink привязывается к закупкам
3. Автоматически пересчитывается payment_status каждой закупки

### Расход → Возмещение сотруднику
1. Сотрудник создаёт Expense с is_reimbursement=true
2. Бухгалтер/admin видит в разделе расходов, одобряет (approve) или отклоняет (reject)
3. При одобрении: статус → approved, уведомление сотруднику
4. При оплате: статус → paid, запись в CashTransaction кассы

### Синхронизация с irsway.com
- Логистические заказы синхронизируются с irsway через API
- Создание аккаунтов клиентов на сайте из карточки контрагента
- Торговые заказы (PI) синхронизируются как TradeOrder

---

## Интеграция irsway.com

Настраивается в разделе **Интеграции** (admin).  
Хранит: base_url, api_token, is_enabled.

**Методы клиента:**
- `create_shipment()` — создать отправление
- `update_shipment()` — обновить данные
- `add_status()` — добавить статус отправления
- `create_client()` — зарегистрировать клиента
- `link_client()` — привязать код к существующему аккаунту
- `update_client_credentials()` — сменить логин/пароль клиента
- `create_trade_order()` — создать торговый заказ (PI)
- `update_trade_order()` — обновить торговый заказ

---

## Уведомления

Колокольчик в шапке показывает количество непрочитанных.  
Уведомления генерируются автоматически при:
- Создании нового заказа → менеджеру и всем purchaser
- Полной оплате заказа → менеджеру и accountant
- Создании возмещения → accountant и admin
- Одобрении/отклонении возмещения → сотруднику
- Полной оплате закупки → purchaser и accountant

**Бейджи на разделах** (только admin):  
Красные числа рядом с Заказами, Платежами, Расходами, Закупками — количество новых документов с момента последнего просмотра раздела.

---

## Темы оформления (только локально)

- ☀️ Светлая (по умолчанию)
- 🌑 Тёмная
- 🎀 Hello Kitty (розовая)

---

## Мультивалютность

Базовая валюта — **CNY**.  
Поддерживаются: CNY, RUB, USDT, USD.  
Курсы хранятся в exchange_rates (на каждую дату).  
Все итоговые суммы всегда в CNY.

---

## Мультиязычность

- Русский (ru) — по умолчанию
- Китайский (zh)
- Переключается кнопкой в шапке, сохраняется в localStorage

---

## Структура репозитория

```
/ERP
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env (не в git)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/versions/   ← 20 миграций
│   └── app/
│       ├── main.py         ← FastAPI app, подключение роутеров
│       ├── database.py     ← AsyncSession, Base
│       ├── config.py       ← настройки из .env
│       ├── models/         ← 30 SQLAlchemy моделей
│       ├── schemas/        ← Pydantic request/response схемы
│       ├── api/            ← FastAPI роутеры
│       ├── services/       ← notifications, reports, excel_export
│       ├── integrations/   ← irsway_site client & service
│       ├── core/           ← security (JWT/bcrypt), deps (get_current_user)
│       ├── utils/          ← audit logger
│       └── templates/      ← Jinja2 HTML для PDF
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── vite.config.ts
    └── src/
        ├── App.tsx         ← routing, темы
        ├── api/            ← axios клиент + методы по разделам
        ├── pages/          ← страницы
        ├── components/     ← переиспользуемые компоненты
        ├── hooks/          ← useAuth, useRole, useIsMobile, useSectionCounts
        ├── types/          ← TypeScript интерфейсы
        └── locales/        ← ru.json, zh.json (i18n)
```

---

## Деплой на сервер

```bash
# Сервер: 195.161.68.123
# ERP: https://erp.irsway.com (порт 8443 → nginx → 80 → docker 80)

# Обновить с GitHub:
cd /opt/erp
git pull origin main
docker compose up -d --build

# Только перезапустить backend (БЕЗ пересборки):
docker compose restart backend
```

> ⚠️ **ВАЖНО:** При пересборке образа (`--build`) нужен актуальный `requirements.txt`.  
> Если backend не стартует — проверить: `docker logs erp_backend --tail 30`  
> Частая причина: отсутствует пакет в requirements.txt (например openpyxl).
