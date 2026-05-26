# ERP — Логистика и торговля (Россия — Китай)

Монорепо: `backend/` (FastAPI + PostgreSQL) и `frontend/` (React + Ant Design).

---

## Быстрый старт

### 1. Запуск PostgreSQL через Docker

```bash
cd /home/akhmad/ERP
docker-compose up -d
```

Дождитесь статуса healthy (обычно 10–15 секунд):
```bash
docker-compose ps
```

### 2. Виртуальное окружение Python и зависимости backend

```bash
cd /home/akhmad/ERP/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Применить миграции

```bash
cd /home/akhmad/ERP/backend
source .venv/bin/activate   # если не активировано
alembic upgrade head
```

### 4. Заполнить базу начальными данными (seed)

```bash
cd /home/akhmad/ERP/backend
source .venv/bin/activate
python -m app.utils.seed
```

Скрипт идемпотентен — при повторном запуске дублей не создаёт.

### 5. Запустить backend

```bash
cd /home/akhmad/ERP/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Backend доступен по адресу: http://localhost:8000  
Swagger UI: http://localhost:8000/docs

### 6. Установить зависимости и запустить frontend

В новом терминале:
```bash
cd /home/akhmad/ERP/frontend
npm install
npm run dev
```

Frontend доступен по адресу: http://localhost:5173

---

## Вход в систему

Откройте http://localhost:5173 в браузере.

| Поле    | Значение     |
|---------|--------------|
| Логин   | `admin`      |
| Пароль  | `admin123`   |

---

## Переменные окружения

**backend/.env** (создан автоматически из .env.example):
- `DATABASE_URL` — строка подключения к PostgreSQL
- `JWT_SECRET` — секрет для подписи JWT токенов
- `JWT_EXPIRE_MINUTES` — время жизни токена (по умолчанию 480 минут)
- `CORS_ORIGINS` — список разрешённых origin через запятую

**frontend/.env** (создан автоматически):
- `VITE_API_URL` — базовый URL backend API

---

## Структура проекта

```
ERP/
├── backend/          — FastAPI приложение
│   ├── app/
│   │   ├── models/   — SQLAlchemy 2.0 модели (14 таблиц)
│   │   ├── api/      — Эндпоинты (auth)
│   │   ├── core/     — JWT, зависимости
│   │   ├── schemas/  — Pydantic схемы
│   │   └── utils/    — Seed-скрипт
│   └── alembic/      — Миграции
└── frontend/         — React + TypeScript + Ant Design 5
    └── src/
        ├── pages/    — LoginPage, DashboardPage
        ├── api/      — axios клиент
        ├── hooks/    — useAuth
        └── locales/  — ru.json, zh.json
```
