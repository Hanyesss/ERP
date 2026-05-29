import uuid
import tempfile
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.database import get_db
from app.core.deps import require_roles
from app.models.user import User
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_item_photo import OrderItemPhoto
from app.models.order_charge import OrderCharge
from app.models.order_file import OrderFile
from app.models.counterparty import Counterparty
from app.models.business_type import BusinessType
from app.models.company import Company

router = APIRouter(prefix="/api/orders", tags=["order-pdf"])

_PDF_ROLES = ("manager", "accountant", "admin")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "pdf"
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


def _fmt_decimal(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
        return f"{v:,.2f}".replace(",", " ")
    except Exception:
        return str(value)


def _get_photo_abs_path(photo: OrderItemPhoto) -> str:
    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    ext = ext_map.get(photo.mime_type or "", ".jpg")
    path = UPLOADS_DIR / "order_items" / str(photo.order_item_id) / f"{photo.id}{ext}"
    return str(path)


@router.get("/{order_id}/client-pdf")
async def download_client_pdf(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_PDF_ROLES)),
):
    # Load order
    ClientAlias = aliased(Counterparty)
    stmt = (
        select(Order, ClientAlias, BusinessType)
        .join(ClientAlias, Order.client_id == ClientAlias.id)
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .where(Order.id == order_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(404, "Order not found")
    order, client, bt = row

    if bt.code == "logistics":
        raise HTTPException(400, "PDF export is only available for trade/services orders")

    # Company info
    company = (await db.execute(
        select(Company).where(Company.is_active == True).limit(1)
    )).scalar_one_or_none()
    company_name = company.name if company else "Наша компания"

    # Client phone
    client_phone = None
    if client.contact_info and isinstance(client.contact_info, dict):
        client_phone = client.contact_info.get("phone")

    # Items
    item_rows = (await db.execute(
        select(OrderItem)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id)
    )).scalars().all()

    item_ids = [it.id for it in item_rows]
    photos_by_item: dict[uuid.UUID, list] = {}
    if item_ids:
        photo_rows = (await db.execute(
            select(OrderItemPhoto)
            .where(OrderItemPhoto.order_item_id.in_(item_ids))
            .order_by(OrderItemPhoto.order_item_id, OrderItemPhoto.sort_order)
        )).scalars().all()
        for ph in photo_rows:
            photos_by_item.setdefault(ph.order_item_id, []).append(ph)

    has_photos = any(photos_by_item.get(it.id) for it in item_rows)

    # Build items for template
    total_cny = Decimal("0")
    rate = order.items[0].sale_rate_to_cny if False else None  # unused shortcut

    template_items = []
    currency_totals: dict[str, Decimal] = {}
    for it in item_rows:
        qty = it.quantity or Decimal("0")
        price = it.sale_price or Decimal("0")
        total = (qty * price).quantize(Decimal("0.01"))
        cur_raw = it.sale_currency or "CNY"
        cur = str(cur_raw.value if hasattr(cur_raw, 'value') else cur_raw)
        currency_totals[cur] = currency_totals.get(cur, Decimal("0")) + total
        rate_val = it.sale_rate_to_cny or Decimal("1")
        total_cny += (total * rate_val).quantize(Decimal("0.01"))

        photos_data = []
        for ph in photos_by_item.get(it.id, []):
            abs_path = _get_photo_abs_path(ph)
            if Path(abs_path).exists():
                # WeasyPrint requires file:// URIs for local files
                photos_data.append({"abs_path": Path(abs_path).as_uri()})

        template_items.append({
            "name": it.name,
            "name_cn": it.name_cn,
            "model": it.model,
            "specification": it.specification,
            "quantity": it.quantity,
            "unit": it.unit,
            "sale_price": it.sale_price,
            "sale_currency": cur,
            "total": total,
            "photos": photos_data,
        })

    # Primary currency total — force to string (SQLAlchemy enum value)
    client_currency = str(order.client_currency.value if hasattr(order.client_currency, 'value') else order.client_currency)
    total_in_currency = currency_totals.get(client_currency, Decimal("0"))
    if client_currency == "CNY":
        total_in_currency = total_cny

    # Price currency for column header: dominant sale currency, fallback to client_currency
    if currency_totals:
        price_currency = max(currency_totals, key=lambda k: currency_totals[k])
    else:
        price_currency = client_currency

    # Render template
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["fmt_decimal"] = _fmt_decimal
    tmpl = env.get_template("client_order.html")
    html = tmpl.render(
        company_name=company_name,
        company_phone=None,
        company_email=None,
        order_number=order.order_number,
        order_date=order.order_date.strftime("%d.%m.%Y"),
        client_name=client.name,
        client_phone=client_phone,
        client_currency=client_currency,
        items=template_items,
        has_photos=has_photos,
        price_currency=price_currency,
        total_cny=total_cny,
        total_in_currency=total_in_currency,
        notes=order.notes,
    )

    # Generate PDF with WeasyPrint
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html, base_url=str(UPLOADS_DIR)).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")

    filename = f"quotation_{order.order_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


CHARGE_TYPE_LABELS = {
    "delivery": "Доставка",
    "insurance_percent": "Страховой %",
    "insurance_cost": "Страховка",
    "china_delivery": "Доставка по Китаю",
    "extra_packing": "Доп. упаковка",
    "loaders": "Грузчики",
}


@router.get("/{order_id}/logistics-pdf")
async def download_logistics_pdf(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_PDF_ROLES)),
):
    ClientAlias = aliased(Counterparty)
    stmt = (
        select(Order, ClientAlias, BusinessType)
        .join(ClientAlias, Order.client_id == ClientAlias.id)
        .join(BusinessType, Order.business_type_id == BusinessType.id)
        .where(Order.id == order_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(404, "Order not found")
    order, client, bt = row

    if bt.code != "logistics":
        raise HTTPException(400, "PDF накладная доступна только для логистических заказов")

    company = (await db.execute(
        select(Company).where(Company.is_active == True).limit(1)
    )).scalar_one_or_none()
    company_name = company.name if company else "Наша компания"

    client_phone = None
    if client.contact_info and isinstance(client.contact_info, dict):
        client_phone = client.contact_info.get("phone")

    item_rows = (await db.execute(
        select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
    )).scalars().all()

    charge_rows = (await db.execute(
        select(OrderCharge).where(OrderCharge.order_id == order_id)
    )).scalars().all()

    file_rows = (await db.execute(
        select(OrderFile)
        .where(OrderFile.order_id == order_id, OrderFile.file_type == "cargo_photo")
        .order_by(OrderFile.uploaded_at)
    )).scalars().all()

    template_items = []
    for it in item_rows:
        wkg = float(it.weight_kg) if it.weight_kg else None
        vm3 = float(it.volume_m3) if it.volume_m3 else None
        density = f"{wkg / vm3:.2f}" if wkg and vm3 and vm3 > 0 else "—"
        template_items.append({
            "name": it.name,
            "weight_kg": it.weight_kg,
            "volume_m3": it.volume_m3,
            "density": density,
            "price_per_kg": it.price_per_kg,
            "price_per_kg_currency": str(it.price_per_kg_currency.value if hasattr(it.price_per_kg_currency, "value") else it.price_per_kg_currency or "USD"),
            "cargo_value": it.cargo_value,
            "cargo_value_currency": str(it.cargo_value_currency.value if hasattr(it.cargo_value_currency, "value") else it.cargo_value_currency or "USD"),
            "places_count": it.places_count,
        })

    template_charges = []
    total_cny = Decimal("0")
    for ch in charge_rows:
        if ch.charge_type == "insurance_percent":
            continue
        label = CHARGE_TYPE_LABELS.get(ch.charge_type, ch.charge_type)
        template_charges.append({
            "label": label,
            "amount": ch.amount,
            "currency": ch.currency,
            "amount_cny": ch.amount_cny,
        })
        total_cny += ch.amount_cny

    cargo_photos = []
    for f in file_rows:
        abs_path = UPLOADS_DIR / f.file_url
        if abs_path.exists():
            cargo_photos.append({
                "abs_path": abs_path.as_uri(),
                "file_name": f.file_name,
            })

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["fmt_decimal"] = _fmt_decimal
    tmpl = env.get_template("logistics_waybill.html")
    html = tmpl.render(
        company_name=company_name,
        company_phone=None,
        company_email=None,
        order_number=order.order_number,
        order_date=order.order_date.strftime("%d.%m.%Y"),
        client_name=client.name,
        client_phone=client_phone,
        recipient=order.recipient,
        destination=order.destination,
        arrival_date=order.arrival_date.strftime("%d.%m.%Y") if order.arrival_date else None,
        tracking_number=order.tracking_number,
        items=template_items,
        charges=template_charges,
        total_cny=total_cny,
        cargo_photos=cargo_photos,
        notes=order.notes,
    )

    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html, base_url=str(UPLOADS_DIR)).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")

    filename = f"waybill_{order.order_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
