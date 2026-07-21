# ERP ↔ TronTok Partner API — Анализ интеграции

**Дата:** 2026-06-21  
**Статус:** Read-only анализ. Код не изменялся.

---

## Главная развилка

**`POST /partner/charge` — НЕ реализован.**

Вся инфраструктура готова: таблица `partner_charges` в БД существует
(`db.py:338–347`), лимиты `charge_single_limit` / `charge_daily_limit` есть
на модели `partners`, тест-скрипт (`scripts/test_partner_api.py:278–318`)
покрывает этот эндпоинт с идемпотентностью — но **обработчика маршрута нет
в `partner_api.py`**. Строка 15 того же файла:
*"Partners CANNOT deduct client balances — read-only + provision + withdraw
initiation only."*

Это работа на стороне TronTok, без неё ERP не может списывать.

---

## Сводная таблица

| Потребность ERP | Есть в TronTok partner API | Примечание |
|---|---|---|
| GET баланс клиента | **ДА** | `GET /partner/balance?external_id=` → `{credited, paid_out, in_flight, available}` (`partner_api.py:211`) |
| Внутренний off-chain дебет | **НЕТ** | Таблица `partner_charges` есть, роут отсутствует. Нужно реализовать. |
| Перевод между аккаунтами | Нет | `POST /partner/withdraw-request` — pending, клиент подтверждает 2FA сам |
| Идемпотентность при дебете | **ДА** (как только роут появится) | Поле `ref` с `UNIQUE(partner_id, ref)`, схема уже в БД |
| Привязка клиента ERP → TronTok | **ДА** | `partner_users.external_id` — при provision передаём `client_code` из ERP |
| Создать аккаунт с внешним кодом | **ДА** | `POST /partner/provision` идемпотентен, принимает `external_id` |
| Ошибка при нехватке баланса | ДА (в user-side API) | `InsufficientBalance` → HTTP 422 |
| Хранение credentials в ERP | **ДА** | Таблица `integration_settings` — добавить строку `"trontok"` |
| Существующая интеграция ERP ↔ TronTok | **НЕТ** | С нуля, ни одного упоминания trontok в кодовой базе ERP |

---

## Часть A — TronTok (`/home/akhmad/projects/irs-pay`)

### Все эндпоинты partner API

Файл: `src/irs_pay/partner_api.py`, строки 154–371.

```
GET  /partner/ping                  — health check (без auth)
GET  /partner/setup                 — self-test HTML (без auth)
GET  /partner/sdk                   — скачать SDK (без auth)
GET  /partner/account               — статистика партнёра
POST /partner/provision             — создать/получить кошелёк, привязать пользователя
GET  /partner/balance               — USDT-баланс клиента
GET  /partner/deposit-address       — TRON-адрес для пополнения
GET  /partner/transactions          — история ledger клиента
POST /partner/withdraw-request      — создать pending-заявку на вывод (требует 2FA клиента)
GET  /partner/user-status           — has_password + totp_enabled
POST /partner/totp-setup            — сгенерировать TOTP-секрет
POST /partner/totp-enable           — включить 2FA
```

**ОТСУТСТВУЕТ:** `POST /partner/charge`

### Аутентификация

FACT (`partner_api.py:50–85`): каждый запрос требует трёх заголовков:
- `X-Partner-Key` — 64-символьный hex-ключ партнёра
- `X-Timestamp` — Unix timestamp (запросы старше 300 сек отклоняются)
- `X-Signature` — `HMAC-SHA256(api_key, "METHOD\nPATH\nTIMESTAMP\n" + body)`

Один ключ на все операции — read и write. Отдельного read-only токена нет.

### Идемпотентность

FACT: `POST /partner/withdraw-request` идемпотентен по полю `ref`
(`partners.py:41–52`, `UNIQUE(partner_id, ref)` в `db.py:362`).
При повторном вызове возвращает `idempotent: true` и HTTP 200 вместо 201.

Для `POST /partner/charge` — схема идентичная (UNIQUE(partner_id, ref) в
`partner_charges`), но роута нет.

### Идентификация клиента

FACT (`partner_api.py:90–123`): клиент идентифицируется двумя способами:
- По `email` (query param)
- По `external_id` (query param) — произвольный TEXT, задаётся при provision

FACT (`db.py:327–336`): таблица `partner_users`:
```
partner_id   → partners(id)
user_id      → users(id)
external_id  TEXT                    ← сюда идёт client_code из ERP
UNIQUE(partner_id, external_id)
```

`POST /partner/provision` идемпотентен — безопасно вызывать повторно.
Возвращает: `user_id`, `email`, `deposit_address`, `created`, `linked`.

### Схема `partner_charges` (таблица есть, роута нет)

FACT (`db.py:338–347`):
```sql
id          SERIAL PK
partner_id  → partners(id)
client_id   → clients(id)
amount      NUMERIC(20,6)
ref         TEXT
description TEXT
created_at  TIMESTAMPTZ
UNIQUE(partner_id, ref)
```

### Что возвращает withdraw-request (ближайший аналог)

FACT (`partner_api.py:302–312`):
```json
{
  "request_id": <int>,
  "ref": "<str>",
  "status": "pending_user_confirm",
  "idempotent": <bool>,
  "amount": "<decimal>",
  "to_address": "<str>",
  "note": "user must confirm via TronTok cabinet with 2FA"
}
```
Баланс не меняется до подтверждения клиентом. `balance_after` не возвращается.

### Нехватка баланса

FACT (`transfers.py:144–183`): `InsufficientBalance` → HTTP 422.  
HYPOTHESIS: charge-эндпоинт при нехватке вернёт то же самое — тест-скрипт
(`test_partner_api.py:304, 316`) ожидает именно 422.

### Схема balance (`client_balances`, `db.py:96–99`)

```
client_id   PK → clients(id)
credited    NUMERIC(20,6)   — всё зачисленное on-chain
paid_out    NUMERIC(20,6)   — всё списанное
in_flight   NUMERIC(20,6)   — замороженное (pending withdrawal)
available   = credited - paid_out - in_flight   (computed)
```

---

## Часть B — ERP (`/home/akhmad/ERP`)

### Модель Counterparty

FACT (`backend/app/models/counterparty.py:25–40`), таблица `counterparties`:
```
id               UUID PK
code             String(20)   — стабильный внешний код (используется в irsway sync)
name, name_cn
type             enum: client | supplier | both | partner
default_currency enum: CNY | RUB | USDT | USD
contact_info     JSONB        — phone, email, address
partner_id       FK → self
```

MISSING: нет `trontok_id`, `trontok_account_id`, `usdt_address` или любого
другого поля под внешнюю платёжную систему.

### Модель Payment и флоу оплаты

FACT (`backend/app/models/payment.py:25–47`), таблица `payments`:
```
direction         "in" | "out"
counterparty_id   FK → counterparties
cash_register_id  FK → cash_registers  (обязателен)
currency          CNY | RUB | USDT | USD
amount, rate_to_cny, amount_cny
network_fee       (для блокчейн-комиссий)
notes, file_url, file_urls
pending_change    JSON (approval workflow)
```

FACT (`backend/app/api/payments.py:521–689`): флоу создания платежа:
1. Проверка counterparty
2. Проверка `cash_register_id` (обязателен, строка 537)
3. Получение курса валюты
4. INSERT Payment
5. Автоматически — INSERT CashTransaction на выбранной кассе
6. INSERT PaymentAllocation / PurchasePaymentLink
7. Пересчёт статуса оплаты заказа/закупки

MISSING: нет поля `source`, нет `external_tx_id` для хранения ID транзакции
из внешней системы.

### Кассы и USDT

FACT (`backend/app/models/cash_register.py:12–20`): `CashRegister` — поле
`currency` это свободный текст String(10). USDT-касса технически поддерживается.

FACT: `CashTransaction` создаётся автоматически при каждом Payment.
Защита от отрицательного баланса работает (строка 627).

FACT (`backend/app/api/payments.py:603`): курс USDT обрабатывается корректно
(`_RANK = {"USD": 3, "USDT": 2, "CNY": 1, "RUB": 0}`).

MISSING: USDT-касса не создаётся seed-скриптом. Создаётся вручную через admin.

### Существующие интеграции

FACT: Zero TronTok / crypto упоминаний в кодовой базе ERP.  
FACT: `integrations/` содержит только `irsway_site/` (client.py, service.py, schemas.py).  
FACT: В .env и docker-compose нет никаких ключей TronTok.

### IntegrationSettings

FACT (`backend/app/models/integration_settings.py:10–23`), таблица
`integration_settings`:
```
integration_name  Text UNIQUE  — ключ интеграции
base_url          Text nullable
api_token         Text nullable  — хранится plaintext в БД (masked при отдаче)
is_enabled        Boolean
last_sync_at, last_sync_status, last_sync_error
```

Сейчас одна запись: `"irsway_site"`. Таблица generic — достаточно добавить
строку `"trontok"` с `base_url` TronTok и `api_token = partner_key`.

---

## Архитектура интеграции

### Поток оплаты

```
Клиент нажимает "Оплатить с TronTok" в ERP
        ↓
ERP: GET /partner/balance?external_id={counterparty.code}
     → показать актуальный баланс (не кешировать!)
        ↓
Клиент подтверждает сумму
        ↓
ERP генерирует: ref = "erp-pay-{payment_uuid}"  (идемпотентный ключ)
ERP: POST /partner/charge {
       external_id: counterparty.code,
       amount: N,
       ref: "erp-pay-{uuid}",
       description: "Оплата заказа #{order_id}"
     }
        ↓
TronTok: проверяет баланс → списывает → пишет в ledger
         возвращает: { charge_id, balance_after, ref, created_at }
        ↓
ERP: создаёт Payment (currency=USDT, direction="in",
                      cash_register="USDT TronTok",
                      external_tx_id=charge_id)
     CashTransaction создаётся автоматически
```

### Привязка клиента ERP → TronTok

При первом обращении к TronTok для клиента:
```
POST /partner/provision {
  email: counterparty.contact_info.email,
  external_id: counterparty.code   ← client_code из ERP
}
```
Идемпотентен — безопасно вызывать повторно. Результат сохраняется в
`counterparties.trontok_linked = true` (новая колонка).

### Рассинхрон баланса

ERP запрашивает баланс непосредственно перед показом формы оплаты.
TronTok проверяет актуальный баланс в момент `POST /partner/charge`.
Если клиент потратил баланс через другой канал между показом и
подтверждением — TronTok вернёт 422, ERP покажет ошибку. Это корректное
поведение, дополнительной логики не требует.

### Двойной клик (идемпотентность)

ERP генерирует `ref = "erp-pay-{payment_uuid}"` до первого запроса.
При повторном вызове TronTok вернёт `idempotent: true` — баланс спишется
ровно один раз.

---

## Порядок работ

### Этап 0 — TronTok (блокирует всё остальное)

Реализовать `POST /partner/charge` в `partner_api.py`:
- Схема запроса: `external_id | email`, `amount`, `ref`, `description`
- Логика: `UNIQUE(partner_id, ref)` → idempotency, проверка баланса,
  INSERT в `partner_charges`, UPDATE `client_balances`, INSERT в `ledger`
- Ответ: `{ charge_id, ref, amount, balance_after, created_at, idempotent }`
- 422 при нехватке баланса
- 200 + `idempotent: true` при повторном `ref`

### Этап 1 — ERP (можно начать параллельно с Этапом 0)

1. **Миграция `counterparties`**: добавить колонку `trontok_linked BOOLEAN DEFAULT FALSE`
   (и опционально `trontok_id TEXT`)
2. **Миграция `payments`**: добавить колонку `external_tx_id TEXT` (для хранения
   `charge_id` из TronTok)
3. **`integration_settings`**: добавить строку `"trontok"` через admin UI или seed
4. **Новый модуль** `backend/app/integrations/trontok/`:
   - `client.py` — HMAC-auth клиент (по аналогии с `irsway_site/client.py`)
   - Методы: `get_balance(external_id)`, `provision(email, external_id)`, `charge(external_id, amount, ref, description)`
5. **API**: новый endpoint или расширение существующего флоу платежа для source="trontok"
6. **Admin**: создать USDT TronTok кассу через UI

---

## Гипотезы (явно помечены)

- HYPOTHESIS: `POST /partner/charge` реализуется за 1–2 дня — вся схема готова,
  нужен только роут + логика по аналогии с `transfers.service_payment`.
- HYPOTHESIS: `trontok_linked` достаточно как флаг; `trontok_id` нужен только
  если потребуется хранить числовой `user_id` TronTok (для debug/reconciliation).
- HYPOTHESIS: `external_tx_id` на `Payment` удобен для reconciliation, но не
  блокирует MVP — можно добавить во второй итерации.
- HYPOTHESIS: credentials TronTok лучше хранить в `integration_settings` (DB),
  а не в .env — admin может сменить ключ без рестарта контейнера.
