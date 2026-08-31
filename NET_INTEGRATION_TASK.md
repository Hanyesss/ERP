# Задание: приём заказов и статусов из приложения NET (раздел «NET» в ERP)

> Это законченное ТЗ. Реализуй **всё** за один заход: миграция + входной API + сервис +
> вкладка NET в UI + тесты. Внешняя система (приложение PARCEL, `app.net-delivery.com`)
> **уже задеплоена и уже шлёт** описанный ниже payload — тебе нужно его принять.

## 0. Контекст и принцип
- ERP = центр управления. Приложение NET (склад КНР → трекинг → выдача в ПВЗ) **пушит** к нам
  заказы клиентов и обновления статуса груза. Мы их принимаем и показываем в отдельном разделе **NET**.
- Сейчас интеграция `irsway_site` — только **исходящая** (ERP → сайт). У `Order` **нет поля источника**.
  Здесь мы строим **входящую** сторону. NET-заказы **никуда обратно не пушим** (не на irsway_site).
- Стек ERP: FastAPI + SQLAlchemy(async) + Alembic + React/AntD. Делай в стиле существующего кода.

---

## 1. Контракт (то, что NET уже отправляет)

**Endpoint (создать):** `POST /api/integration/net/orders`
**Заголовок авторизации:** `Authorization: Token <NET_INBOUND_TOKEN>` (см. §3)
**Content-Type:** `application/json`

**Тело запроса** (реальный пример, поля с `null` возможны везде, кроме `external_ref` и `status.code`):
```json
{
  "external_ref": "PB00000029",
  "source": "net",
  "business_type": "logistics",
  "client": {
    "client_code": "PR-10008",
    "name": "Иван Петров",
    "phone": "+79991234567",
    "email": "ivan@example.com"
  },
  "tracking_number": "SFERP42",
  "marketplace": "1688",
  "description": "Кроссовки",
  "weight_g": 1200,
  "status": {
    "code": "RECEIVED_WH",
    "label": "Принят на складе в Китае",
    "lifecycle": "active"
  },
  "occurred_at": "2026-08-27T14:16:04+00:00"
}
```

Семантика полей:
- `external_ref` — **стабильный уникальный ключ** заказа со стороны NET (штрихкод посылки). По нему
  **идемпотентный upsert**: первый вызов создаёт заказ, последующие обновляют его и добавляют статус.
  Один и тот же `external_ref` НИКОГДА не создаёт второй заказ.
- `source` — всегда `"net"`. Сохрани в новую колонку `orders.source`.
- `business_type` — всегда `"logistics"`. Резолвь в `business_type_id` по `BusinessType.code == "logistics"`.
- `client.*` — идентификация клиента. Резолв/создание контрагента см. §5.
- `tracking_number`, `marketplace`, `description`, `weight_g`, `occurred_at` — метаданные груза.
- `status.code` — код статуса NET (полный список в §6). `status.label` — готовая русская подпись.
  `status.lifecycle` — одно из `active | closed | cancelled` (маппинг на `OrderStatus` см. §6).

**Ответ 200/201** (JSON, NET его логирует, строгой схемы не требует, но сделай так):
```json
{ "ok": true, "external_ref": "PB00000029", "order_number": "NET-PB00000029", "created": true }
```
- `created: true` при первом создании, `false` при обновлении.

**Коды ошибок:**
- `401` — нет/неверный токен.
- `422` — не прошла валидация тела (Pydantic).
- `200/201` — успех (idempotent: повтор того же статуса — тоже успех, `created:false`).
- Никаких `500` на штатных путях. Клиент-отсутствует → создать контрагента (§5), не падать.

> Дополнительно (по желанию, для отладки): `GET /api/integration/net/orders/{external_ref}` →
> вернуть текущий заказ + историю статусов. Не обязательно.

---

## 2. Роутер и подключение
- Новый файл `app/api/integration_net.py`:
  ```python
  router = APIRouter(prefix="/api/integration/net", tags=["net-inbound"])
  ```
- Подключи в `app/main.py`: `app.include_router(net_inbound_router)`.
- Авторизация — **только токен-хедер** (НЕ cookie-JWT из `deps.get_current_user`). См. §3.

---

## 3. Авторизация (token header, через IntegrationSettings)
Не заводи новый способ — переиспользуй таблицу `IntegrationSettings` (`app/models/integration_settings.py`):
- Заведи запись: `integration_name="net_inbound"`, `api_token=<секрет>`, `is_enabled=true`.
  (Значение токена сгенерит владелец; тот же токен пропишется в NET как `ERP_TOKEN`. Для seed —
  положи заглушку и/или бери из env `NET_INBOUND_TOKEN`, если задан, приоритетнее БД.)
- Зависимость `require_net_token`:
  ```python
  async def require_net_token(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
      # ожидаем "Token <value>"
      if not authorization or not authorization.startswith("Token "):
          raise HTTPException(401, "missing token")
      token = authorization.split(" ", 1)[1].strip()
      row = (await db.execute(select(IntegrationSettings)
             .where(IntegrationSettings.integration_name == "net_inbound"))).scalar_one_or_none()
      expected = os.getenv("NET_INBOUND_TOKEN") or (row.api_token if row and row.is_enabled else None)
      if not expected or not hmac.compare_digest(token, expected):
          raise HTTPException(401, "bad token")
  ```
- Навесь на роутер: `dependencies=[Depends(require_net_token)]`.

---

## 4. Миграция БД (Alembic)
Добавь в `orders`:
| колонка | тип | назначение |
|---|---|---|
| `source` | `String(16)`, nullable, default `"erp"`, **index** | источник заказа: `erp` \| `net` |
| `external_ref` | `String(64)`, nullable, **unique index (partial where source='net')** | ключ идемпотентности NET |
| `cargo_status` | `String(40)`, nullable | последний код статуса груза NET (напр. `READY_FOR_PICKUP`) |
| `cargo_status_label` | `String(120)`, nullable | русская подпись статуса |
| `cargo_status_at` | `timestamptz`, nullable | время последнего статуса |

Также создай таблицу истории (полный трек движения — нужно для раздела NET):
```
net_status_events(
  id PK,
  order_id FK->orders.id index,
  code String(40),
  label String(120),
  lifecycle String(16),
  occurred_at timestamptz,
  created_at timestamptz default now()
)
```
Уникальность события: `(order_id, code, occurred_at)` — чтобы повтор того же пуша не плодил дубли.
Существующие заказы: `source` проставь `"erp"` (data-migration/`server_default`).

Обнови ORM-модель `app/models/order.py` соответствующими полями + модель `NetStatusEvent`.

---

## 5. Логика upsert (сервис `app/integrations/net_app/service.py`)
Сделай отдельный сервис (по образцу `app/integrations/irsway_site/`), функция `upsert_net_order(db, payload) -> dict`:

1. **Найти заказ** по `external_ref` (+ `source='net'`).
2. **Резолв business_type**: `BusinessType.code == payload.business_type` (`"logistics"`). Если нет — 422.
3. **Резолв клиента (контрагента)** — по порядку:
   - по `Counterparty.code == client.client_code` (uppercased), иначе
   - по `client.phone`, иначе по `client.email`;
   - если не найден — **создать** контрагента: `name = client.name or client.client_code`,
     `code = client.client_code`, `phone`, `email`, тип — как для обычного клиента-физлица
     (используй тот же путь/дефолты, что и `ClientCreate` из irsway-приёма, если есть).
   - Полученный `client_id` — в заказ.
4. **Если заказа нет — создать** (НЕ через `create_order` из `orders.py`, т.к. он пушит на irsway_site!
   Собери ORM `Order` напрямую или сделай внутренний helper без sync):
   - `order_number = f"NET-{external_ref}"` (уникально), `source="net"`, `external_ref=external_ref`,
     `business_type_id`, `client_id`, `order_date = occurred_at.date() or today`,
     `client_currency="CNY"` (или дефолт компании), `tracking_number`, `notes = description`,
     `warehouse_id=None`, `manager_id/created_by` — системный/None (integration).
   - `excluded_from_accounting` — на твоё усмотрение (NET-груз без денег в ERP → можно `false`).
   - Вес: если у `Order`/позиций есть поле веса — заполни из `weight_g` (гр → кг при необходимости).
   - **НЕ вызывай** `sync_order_to_site` / `sync_trade_order_to_site`.
5. **Обновить статус** (и при создании, и при обновлении):
   - `order.cargo_status = status.code`, `cargo_status_label = status.label`,
     `cargo_status_at = occurred_at or now()`.
   - `order.status` (OrderStatus) ← из `status.lifecycle`: `active→active`, `closed→closed`,
     `cancelled→cancelled` (значение `new` не используем для NET; при создании ставь `active`).
   - Добавь строку в `net_status_events` (идемпотентно по `(order_id, code, occurred_at)`).
6. `commit`. Верни `{ok:true, external_ref, order_number, created: <bool>}`.

**Идемпотентность/гонки:** обрабатывай `IntegrityError` на `order_number`/`external_ref` как «уже создан»
→ перезагрузи и обнови (не плоди дубль). Повтор того же статуса → `created:false`, без исключений.

---

## 6. Статусы NET → ERP
Полный список кодов `status.code`, которые шлёт NET (порядок = движение груза):
```
DECLARED           Заявлен клиентом            (lifecycle active)
CN_IN_TRANSIT      В пути по Китаю             (active)
RECEIVED_WH        Принят на складе в Китае    (active)
PACKED_BAG         Упакован                    (active)
BATCH_DEPARTED     Отправлен из Китая          (active)
CHECKPOINT_PASS    Пройден чек-пойнт           (active)
BORDER_ARRIVED     На границе                  (active)
CUSTOMS_CLEARED    Прошёл таможню              (active)
ARRIVED_HUB        В сортировочном центре РФ   (active)
SORTED_TO_POINT    Едет в пункт выдачи         (active)
READY_FOR_PICKUP   Готов к выдаче              (active)
ARRIVED_PICKUP_POINT В пункте выдачи           (active)
DELIVERED          Выдан клиенту               (closed)
RETURNED_TO_HUB    Возврат на склад            (cancelled)
```
`label` уже приходит готовым — можешь использовать его как есть; список выше на случай, если захочешь
свой словарь. Маппинг `OrderStatus` бери из `status.lifecycle` (это авторитетно), а НЕ угадывай по коду.

---

## 7. Frontend — раздел «NET»
Файлы: `app/frontend/src/pages/OrdersPage.tsx`, `components/orders/OrderTable.tsx`.
1. Добавь фильтр/вкладку **«NET»** — по `source=net` (и, симметрично, «ERP»/«Все»). Проще всего:
   таб-переключатель над таблицей `Все | ERP | NET`, прокидывающий `source` в запрос списка заказов.
2. Список заказов (`GET /api/orders`) — поддержи query-параметр **`source`** на бэке (в `orders.py`
   list-эндпоинте добавь фильтр по `Order.source`).
3. В таблице для NET-заказов покажи колонку **«Статус груза»** = `cargo_status_label` (+ время).
4. В карточке заказа — блок «Движение груза»: список `net_status_events` (label + occurred_at),
   как таймлайн. Для ERP-заказов блок скрыт.
5. Тег источника `NET`/`ERP` в строке (маленький бейдж).

Никаких новых денежных/бухгалтерских экранов — NET-заказ это логистический документ.

---

## 8. Приёмочные проверки (сделай и прогони)
Токен для теста возьми из `IntegrationSettings.net_inbound` (или env `NET_INBOUND_TOKEN`).
1. **Создание:**
   ```
   curl -sX POST http://localhost:<port>/api/integration/net/orders \
     -H "Authorization: Token $TOK" -H "Content-Type: application/json" \
     -d '{"external_ref":"PB00000029","source":"net","business_type":"logistics",
          "client":{"client_code":"PR-10008","name":"Иван Петров","phone":"+79991234567","email":"ivan@ex.com"},
          "tracking_number":"SFERP42","marketplace":"1688","description":"Кроссовки","weight_g":1200,
          "status":{"code":"RECEIVED_WH","label":"Принят на складе в Китае","lifecycle":"active"},
          "occurred_at":"2026-08-27T14:16:04+00:00"}'
   ```
   Ожидаемо: `201`, `created:true`, в БД — заказ `NET-PB00000029`, контрагент `PR-10008` создан,
   `source=net`, `cargo_status=RECEIVED_WH`, 1 строка в `net_status_events`.
2. **Идемпотентный апдейт статуса:** повтори тот же запрос со `status.code":"DELIVERED","lifecycle":"closed"` →
   `200`, `created:false`, тот же заказ, `order.status=closed`, `cargo_status=DELIVERED`, +1 событие,
   **второго заказа нет**.
3. **Повтор один-в-один** (тот же статус/occurred_at) → успех, `created:false`, **без дубля события**.
4. **Без токена / неверный токен** → `401`.
5. **Клиент без client_code** (только phone) → контрагент находится/создаётся по phone.
6. **UI:** вкладка NET показывает заказ, «Статус груза» и таймлайн движения; вкладка ERP его не показывает.
7. Убедись, что создание NET-заказа **не дёргает** `sync_order_to_site` (никаких исходящих на irsway).

---

## 9. Что вернуть владельцу
- Значение токена `net_inbound` (или подтверждение, что взяли из `NET_INBOUND_TOKEN`) — его пропишут в NET (`ERP_TOKEN`).
- Публичный URL приёма (ожидается `https://erp.net-delivery.com/api/integration/net/orders`).
- Краткий отчёт: миграция применена, эндпоинт отвечает, приёмочные проверки §8 зелёные.

## 10. Границы
- Не трогай существующую исходящую интеграцию `irsway_site`.
- NET-заказы не пушим наружу.
- Не ломай текущие эндпоинты `/api/orders` (добавление фильтра `source` — обратно совместимо).
- Деньги/бухгалтерию по NET-заказам не считаем (это трекинговые документы), если владелец не скажет иначе.
