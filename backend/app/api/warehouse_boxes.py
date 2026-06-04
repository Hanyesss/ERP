import uuid
import io
import base64
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, status
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.warehouse_box import WarehouseBox, BoxItem, PackingList, BoxStatus
from sqlalchemy.orm import selectinload, aliased
from app.models.counterparty import Counterparty
from app.models.warehouse import Warehouse

router = APIRouter(prefix="/api/warehouse-boxes", tags=["warehouse-boxes"])

_BOX_ROLES = ("employee", "manager", "accountant", "admin")

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "pdf"
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class BoxItemIn(BaseModel):
    name: str
    quantity: int = 1
    sort_order: int = 0


class BoxCreate(BaseModel):
    counterparty_id: uuid.UUID
    warehouse_id: uuid.UUID
    weight: Decimal
    volume: Decimal
    item_name: str
    description: Optional[str] = None
    tracking_number: Optional[str] = None  # задача 5: трек-номер / штрихкод
    items: list[BoxItemIn] = []
    count: int = 1


class BoxUpdate(BaseModel):
    weight: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    items: Optional[list[BoxItemIn]] = None


class PackingListRequest(BaseModel):
    box_ids: list[uuid.UUID]


class ShipRequest(BaseModel):
    box_codes: list[str]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _calc_density(weight: Decimal, volume: Decimal) -> Decimal:
    if not volume or volume == 0:
        return Decimal("0")
    return (weight / volume).quantize(Decimal("0.001"))


def _box_dir(box_id: uuid.UUID) -> Path:
    d = UPLOADS_DIR / "boxes" / str(box_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _compress_image(data: bytes, max_px: int = 800, quality: int = 72) -> bytes:
    """Сжимает изображение до max_px по большей стороне, JPEG качество quality."""
    try:
        from PIL import Image as PILImage
        import io
        img = PILImage.open(io.BytesIO(data))
        # Конвертируем RGBA→RGB если нужно
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        # Уменьшаем если больше max_px
        w, h = img.size
        if max(w, h) > max_px:
            ratio = max_px / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception:
        return data  # возвращаем оригинал если что-то пошло не так


def _packing_list_dir() -> Path:
    d = UPLOADS_DIR / "packing_lists"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _photo_url(photo_path: Optional[str]) -> Optional[str]:
    if not photo_path:
        return None
    return f"/files/{photo_path}"


def _photo_to_base64(photo_path: Optional[str], max_px: int = 400) -> Optional[str]:
    """Читает фото, сжимает для вставки в PDF (400px, q=65) и кодирует в base64."""
    if not photo_path:
        return None
    full = UPLOADS_DIR / photo_path
    if not full.exists():
        return None
    data = full.read_bytes()
    compressed = _compress_image(data, max_px=max_px, quality=65)
    b64 = base64.b64encode(compressed).decode()
    return f"data:image/jpeg;base64,{b64}"


def _generate_qr_base64(data: str) -> str:
    import qrcode
    # box_size=12, border=2 → (21+4)×12 = 300px ≈ 40мм при 203 DPI — чётко сканируется
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _fmt_decimal(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
        return f"{v:,.3f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _fmt_dec2(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


async def _generate_packing_list_pdf(boxes_data: list[dict]) -> bytes:
    """Build packing list PDF. boxes_data is list of dicts with box + counterparty info."""
    from collections import defaultdict

    # Group by counterparty
    groups: dict[str, dict] = {}
    for b in boxes_data:
        cid = b["counterparty_id"]
        if cid not in groups:
            groups[cid] = {
                "counterparty_code": b["counterparty_code"],
                "counterparty_name": b["counterparty_name"],
                "boxes": [],
            }
        groups[cid]["boxes"].append(b)

    # Build template context
    client_groups = []
    grand_weight = Decimal("0")
    grand_volume = Decimal("0")
    grand_count = 0

    for cid, g in groups.items():
        sum_w = sum(Decimal(str(b["weight"])) for b in g["boxes"])
        sum_v = sum(Decimal(str(b["volume"])) for b in g["boxes"])
        density = _calc_density(sum_w, sum_v)
        for b in g["boxes"]:
            b["photo_b64"] = _photo_to_base64(b.get("photo_path"), max_px=300)
            # Конвертируем фото каждой позиции
            for it in b.get("box_items", []):
                it["photo_b64"] = _photo_to_base64(it.get("photo_path"), max_px=150)
        client_groups.append({
            "counterparty_code": g["counterparty_code"],
            "counterparty_name": g["counterparty_name"],
            "boxes": g["boxes"],
            "sum_weight": sum_w,
            "sum_volume": sum_v,
            "density": density,
        })
        grand_weight += sum_w
        grand_volume += sum_v
        grand_count += len(g["boxes"])

    grand_density = _calc_density(grand_weight, grand_volume)
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["fmt_decimal"] = _fmt_decimal
    tmpl = env.get_template("packing_list.html")
    html = tmpl.render(
        client_groups=client_groups,
        grand_weight=grand_weight,
        grand_volume=grand_volume,
        grand_density=grand_density,
        grand_count=grand_count,
        generated_at=now_str,
    )

    try:
        import weasyprint
        return weasyprint.HTML(string=html).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")


async def _next_box_code(db: AsyncSession, client_code: str) -> str:
    prefix = f"BOX-{client_code}-"
    result = await db.execute(
        select(WarehouseBox.box_code)
        .where(WarehouseBox.box_code.like(f"{prefix}%"))
        .order_by(WarehouseBox.box_code.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    num = 1
    if last:
        try:
            num = int(last.rsplit("-", 1)[-1]) + 1
        except ValueError:
            pass
    return f"{prefix}{num:05d}"


def _box_to_dict(box: WarehouseBox, cp: Optional[Counterparty] = None, wh: Optional[Warehouse] = None,
                 received_by_name: Optional[str] = None, shipped_by_name: Optional[str] = None) -> dict:
    # Позиции коробки (если загружены через selectinload)
    items_data = []
    if hasattr(box, "items") and box.items is not None:
        for it in sorted(box.items, key=lambda x: x.sort_order):
            items_data.append({
                "id": str(it.id),
                "name": it.name,
                "quantity": it.quantity,
                "photo_url": _photo_url(it.photo_path),
                "photo_path": it.photo_path,
                "sort_order": it.sort_order,
            })
    return {
        "id": str(box.id),
        "box_code": box.box_code,
        "counterparty_id": str(box.counterparty_id),
        "counterparty_code": cp.code if cp else None,
        "counterparty_name": cp.name if cp else None,
        "warehouse_id": str(box.warehouse_id),
        "warehouse_name": wh.name if wh else None,
        "received_by_name": received_by_name,
        "shipped_by_name": shipped_by_name,
        "weight": float(box.weight),
        "volume": float(box.volume),
        "density": float(box.density),
        "item_name": box.item_name,
        "description": box.description,
        "tracking_number": box.tracking_number,
        "items": items_data,
        "photo_url": _photo_url(box.photo_path),
        "photo_path": box.photo_path,
        "status": box.status.value,
        "received_at": box.received_at.isoformat() if box.received_at else None,
        "shipped_at": box.shipped_at.isoformat() if box.shipped_at else None,
    }


# ── Endpoints (static paths BEFORE {id}) ─────────────────────────────────────

@router.get("/check/{box_code}")
async def check_box_code(
    box_code: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    """Быстрая проверка статуса коробки по коду — для валидации при сканировании."""
    box = (await db.execute(
        select(WarehouseBox).where(WarehouseBox.box_code == box_code.upper())
    )).scalar_one_or_none()
    if not box:
        return {"found": False, "status": None, "box_code": box_code.upper()}
    return {"found": True, "status": box.status.value, "box_code": box.box_code}


@router.get("/balance")
async def get_balance(
    warehouse_id: Optional[uuid.UUID] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    from app.models.user import User as UserModel

    stmt = (
        select(WarehouseBox, Counterparty, Warehouse)
        .join(Counterparty, WarehouseBox.counterparty_id == Counterparty.id)
        .join(Warehouse, WarehouseBox.warehouse_id == Warehouse.id)
        .where(WarehouseBox.status == BoxStatus.on_warehouse)
        .options(selectinload(WarehouseBox.items))
    )
    if warehouse_id:
        stmt = stmt.where(WarehouseBox.warehouse_id == warehouse_id)
    if search:
        stmt = stmt.where(Counterparty.code.ilike(f"%{search}%"))
    stmt = stmt.order_by(Counterparty.code, WarehouseBox.received_at)

    rows = (await db.execute(stmt)).all()

    # Загружаем имена пользователей одним запросом
    user_ids = {box.received_by for box, _, _ in rows if box.received_by}
    users: dict = {}
    if user_ids:
        user_rows = (await db.execute(
            select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(user_ids))
        )).all()
        users = {str(uid): name for uid, name in user_rows}

    from collections import OrderedDict
    groups: dict[str, dict] = OrderedDict()
    for box, cp, wh in rows:
        cid = str(cp.id)
        if cid not in groups:
            groups[cid] = {
                "counterparty_id": cid,
                "counterparty_code": cp.code or "",
                "counterparty_name": cp.name,
                "boxes": [],
            }
        groups[cid]["boxes"].append(_box_to_dict(
            box, cp, wh,
            received_by_name=users.get(str(box.received_by)) if box.received_by else None,
        ))

    result = []
    for cid, g in groups.items():
        boxes = g["boxes"]
        sum_w = sum(b["weight"] for b in boxes)
        sum_v = sum(b["volume"] for b in boxes)
        density = float(_calc_density(Decimal(str(sum_w)), Decimal(str(sum_v))))
        result.append({
            **g,
            "sum_weight": sum_w,
            "sum_volume": sum_v,
            "total_density": density,
            "boxes_count": len(boxes),
        })
    return result


@router.get("/shipped")
async def get_shipped(
    warehouse_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    from app.models.user import User as UserModel

    stmt = (
        select(WarehouseBox, Counterparty, Warehouse)
        .join(Counterparty, WarehouseBox.counterparty_id == Counterparty.id)
        .join(Warehouse, WarehouseBox.warehouse_id == Warehouse.id)
        .where(WarehouseBox.status == BoxStatus.shipped)
        .options(selectinload(WarehouseBox.items))
    )
    if warehouse_id:
        stmt = stmt.where(WarehouseBox.warehouse_id == warehouse_id)
    stmt = stmt.order_by(WarehouseBox.shipped_at.desc())
    rows = (await db.execute(stmt)).all()

    # Собираем все user_ids и загружаем их одним запросом
    user_ids = set()
    for box, _, _ in rows:
        if box.received_by: user_ids.add(box.received_by)
        if box.shipped_by: user_ids.add(box.shipped_by)
    users: dict = {}
    if user_ids:
        user_rows = (await db.execute(
            select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(user_ids))
        )).all()
        users = {str(uid): name for uid, name in user_rows}

    return [
        _box_to_dict(box, cp, wh,
                     received_by_name=users.get(str(box.received_by)) if box.received_by else None,
                     shipped_by_name=users.get(str(box.shipped_by)) if box.shipped_by else None)
        for box, cp, wh in rows
    ]


@router.get("/packing-lists")
async def get_packing_lists(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    packing_lists = (await db.execute(
        select(PackingList).order_by(PackingList.created_at.desc()).limit(100)
    )).scalars().all()

    result = []
    for pl in packing_lists:
        # Получаем уникальных клиентов из коробок этого пакинг-листа
        clients: list[str] = []
        if pl.box_ids:
            box_ids_parsed = [uuid.UUID(bid) for bid in pl.box_ids if bid]
            if box_ids_parsed:
                cp_rows = (await db.execute(
                    select(Counterparty.code, Counterparty.name)
                    .join(WarehouseBox, WarehouseBox.counterparty_id == Counterparty.id)
                    .where(WarehouseBox.id.in_(box_ids_parsed))
                    .distinct()
                )).all()
                clients = [r.code or r.name for r in cp_rows]
        result.append({
            "id": str(pl.id),
            "created_at": pl.created_at.isoformat(),
            "total_boxes": pl.total_boxes,
            "total_weight": float(pl.total_weight) if pl.total_weight else None,
            "total_volume": float(pl.total_volume) if pl.total_volume else None,
            "pdf_url": f"/files/{pl.pdf_path}" if pl.pdf_path else None,
            "box_count": len(pl.box_ids) if pl.box_ids else 0,
            "clients": clients,
        })
    return result


@router.post("/packing-list")
async def generate_packing_list_preview(
    body: PackingListRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    if not body.box_ids:
        raise HTTPException(400, "No boxes selected")

    rows = (await db.execute(
        select(WarehouseBox, Counterparty)
        .join(Counterparty, WarehouseBox.counterparty_id == Counterparty.id)
        .where(WarehouseBox.id.in_(body.box_ids))
        .options(selectinload(WarehouseBox.items))
    )).all()

    if not rows:
        raise HTTPException(404, "Boxes not found")

    boxes_data = []
    for box, cp in rows:
        box_item_list = sorted(box.items, key=lambda x: x.sort_order) if box.items else []
        boxes_data.append({
            "counterparty_id": str(cp.id),
            "counterparty_code": cp.code or cp.name,
            "counterparty_name": cp.name,
            "box_code": box.box_code,
            "item_name": box.item_name,
            "weight": float(box.weight),
            "volume": float(box.volume),
            "density": float(box.density),
            "description": box.description or "",
            "photo_path": box.photo_path,
            "box_items": [
                {"name": it.name, "quantity": it.quantity, "photo_path": it.photo_path}
                for it in box_item_list
            ],
        })

    pdf_bytes = await _generate_packing_list_pdf(boxes_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="packing_list_preview.pdf"'},
    )


@router.post("/ship")
async def ship_boxes(
    body: ShipRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_BOX_ROLES)),
):
    if not body.box_codes:
        raise HTTPException(400, "No box codes provided")

    # Проверяем уже отгруженные
    already_shipped = (await db.execute(
        select(WarehouseBox.box_code)
        .where(
            WarehouseBox.box_code.in_(body.box_codes),
            WarehouseBox.status == BoxStatus.shipped,
        )
    )).scalars().all()
    if already_shipped:
        raise HTTPException(
            422,
            f"Уже отгружено: {', '.join(already_shipped)}. Отгрузка отменена."
        )

    rows = (await db.execute(
        select(WarehouseBox, Counterparty)
        .join(Counterparty, WarehouseBox.counterparty_id == Counterparty.id)
        .where(
            WarehouseBox.box_code.in_(body.box_codes),
            WarehouseBox.status == BoxStatus.on_warehouse,
        )
        .options(selectinload(WarehouseBox.items))
    )).all()

    if not rows:
        raise HTTPException(404, "Коробки не найдены на складе")

    now = datetime.now(timezone.utc)
    shipped_ids = []
    boxes_data = []
    total_weight = Decimal("0")
    total_volume = Decimal("0")

    for box, cp in rows:
        box.status = BoxStatus.shipped
        box.shipped_at = now
        box.updated_at = now
        box.shipped_by = current_user.id
        shipped_ids.append(str(box.id))
        total_weight += box.weight
        total_volume += box.volume
        ship_items = sorted(box.items, key=lambda x: x.sort_order) if box.items else []
        boxes_data.append({
            "counterparty_id": str(cp.id),
            "counterparty_code": cp.code or cp.name,
            "counterparty_name": cp.name,
            "box_code": box.box_code,
            "item_name": box.item_name,
            "weight": float(box.weight),
            "volume": float(box.volume),
            "density": float(box.density),
            "description": box.description or "",
            "photo_path": box.photo_path,
            "box_items": [
                {"name": it.name, "quantity": it.quantity, "photo_path": it.photo_path}
                for it in ship_items
            ],
        })

    # Generate and save the final packing list PDF
    pdf_bytes = await _generate_packing_list_pdf(boxes_data)
    pdf_name = f"packing_list_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = _packing_list_dir() / pdf_name
    pdf_path.write_bytes(pdf_bytes)
    relative_pdf = f"packing_lists/{pdf_name}"

    pl = PackingList(
        id=uuid.uuid4(),
        pdf_path=relative_pdf,
        box_ids=shipped_ids,
        total_weight=total_weight,
        total_volume=total_volume,
        total_boxes=len(shipped_ids),
        created_by=current_user.id,
    )
    db.add(pl)
    await db.commit()

    not_found = [c for c in body.box_codes if c not in {b.box_code for b, _ in rows}]

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf_name}"',
            "X-Shipped-Count": str(len(shipped_ids)),
            "X-Not-Found": ",".join(not_found),
        },
    )


# ── CRUD with dynamic {id} ────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_box(
    body: BoxCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_BOX_ROLES)),
):
    cp = (await db.execute(
        select(Counterparty).where(Counterparty.id == body.counterparty_id)
    )).scalar_one_or_none()
    if not cp:
        raise HTTPException(404, "Counterparty not found")

    wh = (await db.execute(
        select(Warehouse).where(Warehouse.id == body.warehouse_id, Warehouse.is_active == True)
    )).scalar_one_or_none()
    if not wh:
        raise HTTPException(404, "Warehouse not found")

    client_code = cp.code or cp.name[:10].upper().replace(" ", "")
    density = _calc_density(body.weight, body.volume)
    count = max(1, min(body.count or 1, 500))  # от 1 до 500 коробок

    created_boxes = []
    for _ in range(count):
        box_code = await _next_box_code(db, client_code)
        box = WarehouseBox(
            id=uuid.uuid4(),
            box_code=box_code,
            counterparty_id=body.counterparty_id,
            warehouse_id=body.warehouse_id,
            weight=body.weight,
            volume=body.volume,
            density=density,
            item_name=body.item_name,
            description=body.description,
            tracking_number=body.tracking_number,
            status=BoxStatus.on_warehouse,
            received_by=current_user.id,
        )
        db.add(box)
        await db.flush()

        # Создаём позиции товаров (если переданы)
        items_src = body.items if body.items else [BoxItemIn(name=body.item_name, quantity=1)]
        for idx, item_in in enumerate(items_src):
            db.add(BoxItem(
                id=uuid.uuid4(),
                box_id=box.id,
                name=item_in.name,
                quantity=item_in.quantity,
                sort_order=item_in.sort_order if item_in.sort_order else idx,
            ))
        created_boxes.append(box)

    await db.commit()

    # Возвращаем одну или список
    if count == 1:
        await db.refresh(created_boxes[0])
        # Загружаем items
        box_with_items = (await db.execute(
            select(WarehouseBox).where(WarehouseBox.id == created_boxes[0].id)
            .options(selectinload(WarehouseBox.items))
        )).scalar_one()
        return _box_to_dict(box_with_items, cp)

    # Несколько коробок — возвращаем список
    box_ids = [b.id for b in created_boxes]
    boxes_loaded = (await db.execute(
        select(WarehouseBox).where(WarehouseBox.id.in_(box_ids))
        .options(selectinload(WarehouseBox.items))
        .order_by(WarehouseBox.box_code)
    )).scalars().all()
    return [_box_to_dict(b, cp) for b in boxes_loaded]


@router.post("/{box_id}/items/{item_id}/photo")
async def upload_box_item_photo(
    box_id: uuid.UUID,
    item_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    """Загрузить фото для конкретной позиции товара в коробке."""
    item = (await db.execute(
        select(BoxItem).where(BoxItem.id == item_id, BoxItem.box_id == box_id)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Box item not found")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(422, f"File type not allowed: {mime}")

    compressed = _compress_image(content, max_px=800, quality=72)
    stored_name = f"item_{item_id}_{uuid.uuid4()}.jpg"
    dest = _box_dir(box_id) / stored_name
    dest.write_bytes(compressed)

    relative = f"boxes/{box_id}/{stored_name}"
    item.photo_path = relative
    await db.commit()
    return {"photo_url": _photo_url(relative), "photo_path": relative}


@router.post("/{box_id}/photo")
async def upload_box_photo(
    box_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    box = (await db.execute(
        select(WarehouseBox).where(WarehouseBox.id == box_id)
    )).scalar_one_or_none()
    if not box:
        raise HTTPException(404, "Box not found")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, "File too large (max 10 MB)")

    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(422, f"File type not allowed: {mime}")

    # Сжимаем перед сохранением — экономит место и ускоряет пакинг-лист
    compressed = _compress_image(content, max_px=800, quality=72)
    stored_name = f"{uuid.uuid4()}.jpg"
    dest = _box_dir(box_id) / stored_name
    dest.write_bytes(compressed)

    relative = f"boxes/{box_id}/{stored_name}"
    box.photo_path = relative
    box.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"photo_url": _photo_url(relative), "photo_path": relative}


@router.post("/qr-bulk")
async def get_qr_bulk(
    body: PackingListRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    """Генерирует PDF 80×60мм с N страницами — по одной этикетке на каждую коробку."""
    if not body.box_ids:
        raise HTTPException(400, "No boxes selected")

    rows = (await db.execute(
        select(WarehouseBox, Counterparty)
        .join(Counterparty, WarehouseBox.counterparty_id == Counterparty.id)
        .where(WarehouseBox.id.in_(body.box_ids))
        .order_by(WarehouseBox.box_code)
    )).all()

    if not rows:
        raise HTTPException(404, "Boxes not found")

    labels = []
    for box, cp in rows:
        labels.append({
            "qr_image": _generate_qr_base64(box.box_code),
            "box_code": box.box_code,
            "client_code": cp.code or cp.name,
            "client_name": cp.name,
            "item_name": box.item_name,
            "weight": float(box.weight),
            "volume": float(box.volume),
            "density": float(box.density),
            "received_at": box.received_at.strftime("%d.%m.%Y") if box.received_at else "",
        })

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    html = env.get_template("box_label_bulk.html").render(labels=labels)

    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="labels.pdf"'},
    )


@router.get("/{box_id}/qr-png")
async def get_qr_png(
    box_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    """Возвращает QR код как PNG (для быстрой групповой печати)."""
    box = (await db.execute(
        select(WarehouseBox).where(WarehouseBox.id == box_id)
    )).scalar_one_or_none()
    if not box:
        raise HTTPException(404, "Box not found")
    import qrcode
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=12, border=2)
    qr.add_data(box.box_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "max-age=3600"})


@router.get("/{box_id}/qr")
async def get_qr_label(
    box_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    result = (await db.execute(
        select(WarehouseBox, Counterparty)
        .join(Counterparty, WarehouseBox.counterparty_id == Counterparty.id)
        .where(WarehouseBox.id == box_id)
    )).first()
    if not result:
        raise HTTPException(404, "Box not found")
    box, cp = result

    qr_b64 = _generate_qr_base64(box.box_code)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tmpl = env.get_template("box_label.html")
    html = tmpl.render(
        qr_image=qr_b64,
        box_code=box.box_code,
        client_code=cp.code or cp.name,
        client_name=cp.name,
        item_name=box.item_name,
        weight=float(box.weight),
        volume=float(box.volume),
        density=float(box.density),
        received_at=box.received_at.strftime("%d.%m.%Y") if box.received_at else "",
    )

    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{box.box_code}.pdf"'},
    )


@router.patch("/{box_id}")
async def update_box(
    box_id: uuid.UUID,
    body: BoxUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    box = (await db.execute(
        select(WarehouseBox).where(WarehouseBox.id == box_id)
    )).scalar_one_or_none()
    if not box:
        raise HTTPException(404, "Box not found")
    if box.status != BoxStatus.on_warehouse:
        raise HTTPException(400, "Cannot edit shipped box")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(box, field, value)

    if body.weight is not None or body.volume is not None:
        box.density = _calc_density(box.weight, box.volume)

    box.updated_at = datetime.now(timezone.utc)
    await db.commit()

    cp = (await db.execute(
        select(Counterparty).where(Counterparty.id == box.counterparty_id)
    )).scalar_one_or_none()
    return _box_to_dict(box, cp)


@router.delete("/{box_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_box(
    box_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*_BOX_ROLES)),
):
    box = (await db.execute(
        select(WarehouseBox).where(WarehouseBox.id == box_id)
    )).scalar_one_or_none()
    if not box:
        raise HTTPException(404, "Box not found")
    if box.status != BoxStatus.on_warehouse:
        raise HTTPException(400, "Cannot delete shipped box")
    await db.delete(box)
    await db.commit()
