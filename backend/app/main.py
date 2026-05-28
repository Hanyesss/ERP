from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.auth import router as auth_router
from app.api.counterparties import router as counterparties_router
from app.api.orders import router as orders_router
from app.api.order_files import router as order_files_router, files_router
from app.api.exchange_rates import router as exchange_rates_router
from app.api.references import router as references_router
from app.api.purchases import router as purchases_router
from app.api.payments import router as payments_router
from app.api.dashboard import router as dashboard_router
from app.api.expenses import router as expenses_router
from app.api.warehouses import router as warehouses_router
from app.api.reports import router as reports_router

app = FastAPI(title="ERP API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(counterparties_router)
app.include_router(orders_router)
app.include_router(order_files_router)
app.include_router(files_router)
app.include_router(exchange_rates_router)
app.include_router(references_router)
app.include_router(purchases_router)
app.include_router(payments_router)
app.include_router(dashboard_router)
app.include_router(expenses_router)
app.include_router(warehouses_router)
app.include_router(reports_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
