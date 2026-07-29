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
from app.api.users import router as users_router
from app.api.order_item_photos import router as order_item_photos_router
from app.api.order_pdf import router as order_pdf_router
from app.api.notifications import router as notifications_router
from app.api.integration import router as integration_router, orders_router as integration_orders_router
from app.api.cash_registers import router as cash_registers_router
from app.api.purchase_files import router as purchase_files_router
from app.api.warehouse_boxes import router as warehouse_boxes_router
from app.api.assets import router as assets_router
from app.api.partner import router as partner_router
from app.api.trontok import router as trontok_router
from app.api.logistics_quotes import router as logistics_quotes_router

app = FastAPI(title="ERP API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Shipped-Count", "X-Not-Found"],
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
app.include_router(users_router)
app.include_router(order_item_photos_router)
app.include_router(order_pdf_router)
app.include_router(notifications_router)
app.include_router(integration_router)
app.include_router(integration_orders_router)
app.include_router(cash_registers_router)
app.include_router(purchase_files_router)
app.include_router(warehouse_boxes_router)
app.include_router(assets_router)
app.include_router(partner_router)
app.include_router(trontok_router)
app.include_router(logistics_quotes_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
