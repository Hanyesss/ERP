"""Reports API."""
import uuid
import tempfile
import os
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import require_roles
from app.models.user import User
from app.services import report_service
from app.services.excel_export import (
    export_pnl, export_by_client, export_by_supplier,
    export_expenses, export_tonnage,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])

_FINANCE_ROLES = ("accountant", "admin")
_TONNAGE_ROLES = ("manager", "accountant", "admin")

EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _excel_response(data_bytes: bytes, filename: str) -> FileResponse:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.write(data_bytes)
    tmp.flush()
    tmp.close()
    return FileResponse(
        path=tmp.name,
        media_type=EXCEL_CONTENT_TYPE,
        filename=filename,
        background=None,
    )


@router.get("/pnl")
async def get_pnl_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    business_type_id: Optional[uuid.UUID] = Query(None),
    warehouse_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    return await report_service.get_pnl(db, date_from, date_to, business_type_id, warehouse_id)


@router.get("/pnl/export")
async def export_pnl_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    business_type_id: Optional[uuid.UUID] = Query(None),
    warehouse_id: Optional[uuid.UUID] = Query(None),
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    data = await report_service.get_pnl(db, date_from, date_to, business_type_id, warehouse_id)
    data_bytes = export_pnl(data, lang)
    return _excel_response(data_bytes, f"pnl_{date_from}_{date_to}.xlsx")


@router.get("/by-client")
async def get_by_client_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    return await report_service.get_by_client(db, date_from, date_to)


@router.get("/by-client/export")
async def export_by_client_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    data = await report_service.get_by_client(db, date_from, date_to)
    data_bytes = export_by_client(data, lang)
    return _excel_response(data_bytes, f"by_client_{date_from}_{date_to}.xlsx")


@router.get("/by-client/{client_id}")
async def get_client_detail(
    client_id: uuid.UUID,
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    return await report_service.get_client_detail(db, client_id, date_from, date_to)


@router.get("/by-supplier")
async def get_by_supplier_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    return await report_service.get_by_supplier(db, date_from, date_to)


@router.get("/by-supplier/export")
async def export_by_supplier_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    data = await report_service.get_by_supplier(db, date_from, date_to)
    data_bytes = export_by_supplier(data, lang)
    return _excel_response(data_bytes, f"by_supplier_{date_from}_{date_to}.xlsx")


@router.get("/by-supplier/{supplier_id}")
async def get_supplier_detail(
    supplier_id: uuid.UUID,
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    return await report_service.get_supplier_detail(db, supplier_id, date_from, date_to)


@router.get("/expenses")
async def get_expenses_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    link_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    return await report_service.get_expenses_structure(db, date_from, date_to, link_type)


@router.get("/expenses/export")
async def export_expenses_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    link_type: Optional[str] = Query(None),
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_FINANCE_ROLES)),
):
    data = await report_service.get_expenses_structure(db, date_from, date_to, link_type)
    data_bytes = export_expenses(data, lang)
    return _excel_response(data_bytes, f"expenses_{date_from}_{date_to}.xlsx")


@router.get("/tonnage")
async def get_tonnage_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    warehouse_id: Optional[uuid.UUID] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_TONNAGE_ROLES)),
):
    return await report_service.get_tonnage(db, date_from, date_to, warehouse_id, client_id)


@router.get("/tonnage/export")
async def export_tonnage_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    warehouse_id: Optional[uuid.UUID] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_TONNAGE_ROLES)),
):
    data = await report_service.get_tonnage(db, date_from, date_to, warehouse_id, client_id)
    data_bytes = export_tonnage(data, lang)
    return _excel_response(data_bytes, f"tonnage_{date_from}_{date_to}.xlsx")
