import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User
from app.models.exchange_rate import ExchangeRate, RateSourceEnum
from app.schemas.exchange_rate import (
    ExchangeRateCreate, ExchangeRateResponse,
    ExchangeRateListResponse, RateCheckResponse,
)

router = APIRouter(prefix="/api/exchange-rates", tags=["exchange-rates"])


@router.get("/check", response_model=RateCheckResponse)
async def check_rates(
    rate_date: date = Query(alias="date"),
    currencies: str = Query(default="RUB,USDT"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    currency_list = [c.strip() for c in currencies.split(",") if c.strip() and c.strip() != "CNY"]
    rates: dict[str, float] = {"CNY": 1.0}
    missing: list[str] = []

    for currency in currency_list:
        result = await db.execute(
            select(ExchangeRate)
            .where(ExchangeRate.currency == currency, ExchangeRate.rate_date == rate_date)
        )
        rate = result.scalar_one_or_none()
        if rate:
            rates[currency] = float(rate.rate_to_cny)
        else:
            missing.append(currency)

    return RateCheckResponse(rates=rates, missing=missing)


@router.get("", response_model=ExchangeRateListResponse)
async def list_rates(
    currency: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(ExchangeRate)
    if currency:
        q = q.where(ExchangeRate.currency == currency)
    if date_from:
        q = q.where(ExchangeRate.rate_date >= date_from)
    if date_to:
        q = q.where(ExchangeRate.rate_date <= date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.order_by(ExchangeRate.rate_date.desc(), ExchangeRate.currency)
    q = q.offset((page - 1) * page_size).limit(page_size)
    rates = (await db.execute(q)).scalars().all()

    user_ids = list({r.created_by for r in rates})
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u.full_name for u in users_result.scalars().all()}

    items = []
    for r in rates:
        items.append(ExchangeRateResponse(
            id=r.id,
            currency=r.currency,
            rate_to_cny=r.rate_to_cny,
            rate_date=r.rate_date,
            created_by=r.created_by,
            created_by_name=users_map.get(r.created_by, ""),
            source=r.source,
            created_at=r.created_at,
        ))

    return ExchangeRateListResponse(items=items, total=total)


@router.put("/upsert", response_model=ExchangeRateResponse)
async def upsert_rate(
    body: ExchangeRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать или обновить курс вручную. Всегда сохраняет с source=manual."""
    result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.currency == body.currency, ExchangeRate.rate_date == body.rate_date)
    )
    rate = result.scalar_one_or_none()
    if rate:
        rate.rate_to_cny = body.rate_to_cny
        rate.source = RateSourceEnum.manual
    else:
        rate = ExchangeRate(
            id=uuid.uuid4(),
            currency=body.currency,
            rate_to_cny=body.rate_to_cny,
            rate_date=body.rate_date,
            created_by=current_user.id,
            source=RateSourceEnum.manual,
        )
        db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return ExchangeRateResponse(
        id=rate.id, currency=rate.currency, rate_to_cny=rate.rate_to_cny,
        rate_date=rate.rate_date, created_by=rate.created_by,
        created_by_name=current_user.full_name, source=rate.source, created_at=rate.created_at,
    )


@router.post("/auto-fetch")
async def auto_fetch_rates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "accountant")),
):
    """
    Загрузить курсы с MOEX (fallback: ЦБ РФ) и сохранить с source=auto.
    Если за сегодня уже стоит source=manual — этот курс НЕ перезаписывается.
    Возвращает итог: что сохранено, что пропущено.
    """
    import asyncio
    from app.utils.moex_rates import fetch_rates

    loop = asyncio.get_event_loop()
    try:
        fetched = await loop.run_in_executor(None, fetch_rates)
    except Exception as exc:
        raise HTTPException(502, f"Не удалось получить курсы: {exc}")

    today = date.today()
    to_save = {
        "RUB":  fetched["rub_to_cny"],
        "USD":  fetched["usd_to_cny"],
        "USDT": fetched["usdt_to_cny"],
    }

    saved: list[str] = []
    skipped: list[str] = []

    for currency, rate_value in to_save.items():
        existing = (await db.execute(
            select(ExchangeRate).where(
                ExchangeRate.currency == currency,
                ExchangeRate.rate_date == today,
            )
        )).scalar_one_or_none()

        if existing and existing.source == RateSourceEnum.manual:
            skipped.append(currency)
            continue

        if existing:
            existing.rate_to_cny = rate_value
            existing.source = RateSourceEnum.auto
        else:
            db.add(ExchangeRate(
                id=uuid.uuid4(),
                currency=currency,
                rate_to_cny=rate_value,
                rate_date=today,
                created_by=current_user.id,
                source=RateSourceEnum.auto,
            ))
        saved.append(currency)

    await db.commit()

    return {
        "ok": True,
        "fetch_source": fetched["source"],
        "rate_date": str(today),
        "rates": {
            "RUB":  float(fetched["rub_to_cny"]),
            "USD":  float(fetched["usd_to_cny"]),
            "USDT": float(fetched["usdt_to_cny"]),
        },
        "saved": saved,
        "skipped_manual": skipped,
    }


@router.post("", response_model=ExchangeRateResponse, status_code=status.HTTP_201_CREATED)
async def create_rate(
    body: ExchangeRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.currency == body.currency, ExchangeRate.rate_date == body.rate_date)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rate for {body.currency} on {body.rate_date} already exists",
        )

    rate = ExchangeRate(
        id=uuid.uuid4(),
        currency=body.currency,
        rate_to_cny=body.rate_to_cny,
        rate_date=body.rate_date,
        created_by=current_user.id,
        source=RateSourceEnum.manual,
    )
    db.add(rate)
    await db.commit()
    await db.refresh(rate)

    return ExchangeRateResponse(
        id=rate.id,
        currency=rate.currency,
        rate_to_cny=rate.rate_to_cny,
        rate_date=rate.rate_date,
        created_by=rate.created_by,
        created_by_name=current_user.full_name,
        source=rate.source,
        created_at=rate.created_at,
    )
