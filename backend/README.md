# Backend

FastAPI + SQLAlchemy 2.0 + PostgreSQL 16 + Alembic

## Запуск

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.utils.seed
uvicorn app.main:app --reload --port 8000
```

## API

- `POST /api/auth/login` — вход, устанавливает HTTP-only cookie
- `POST /api/auth/logout` — выход, удаляет cookie
- `GET /api/auth/me` — текущий пользователь (требует cookie)
- `GET /health` — проверка работоспособности
- `GET /docs` — Swagger UI
