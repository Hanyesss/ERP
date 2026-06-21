"""
ERP ↔ TronTok partner API proxy.

Authentication: incoming requests must carry
    Authorization: Token <irsway_site.api_token>
(same shared token that ERP uses when calling irsway).
"""
import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.database import get_db
from app.integrations.trontok.client import TronTokClient, TronTokError, TronTokNotFound
from app.models.cash_register import CashRegister, CashTransaction
from app.models.company import Company
from app.models.counterparty import Counterparty
from app.models.exchange_rate import ExchangeRate
from app.models.integration_settings import IntegrationSettings
from app.models.payment import Payment
from app.models.payment_allocation import PaymentAllocation
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trontok", tags=["trontok"])

_TRONTOK_INTEGRATION = "trontok"
_IRSWAY_INTEGRATION = "irsway_site"
_USDT_REGISTER_NAME = "USDT TronTok"


# ── Auth ──────────────────────────────────────────────────────────────────────

async def _require_site_auth(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not authorization or not authorization.startswith("Token "):
        raise HTTPException(401, "Missing Token authorization")
    token = authorization[6:].strip()
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == _IRSWAY_INTEGRATION)
    )).scalar_one_or_none()
    if not row or not row.api_token or token != row.api_token:
        raise HTTPException(403, "Invalid integration token")


# ── TronTok client factory ────────────────────────────────────────────────────

async def _get_tt_client(db: AsyncSession) -> TronTokClient:
    row = (await db.execute(
        select(IntegrationSettings).where(
            IntegrationSettings.integration_name == _TRONTOK_INTEGRATION,
            IntegrationSettings.is_enabled == True,
        )
    )).scalar_one_or_none()
    if not row or not row.api_token or not row.base_url:
        raise HTTPException(503, "TronTok integration not configured or disabled")
    return TronTokClient(api_key=row.api_token, base_url=row.base_url)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_counterparty(db: AsyncSession, client_code: str) -> Counterparty:
    cp = (await db.execute(
        select(Counterparty).where(
            Counterparty.code == client_code.upper(),
            Counterparty.is_active == True,
        )
    )).scalar_one_or_none()
    if not cp:
        raise HTTPException(404, f"Counterparty '{client_code}' not found")
    return cp


async def _get_usdt_register(db: AsyncSession) -> CashRegister:
    reg = (await db.execute(
        select(CashRegister).where(
            CashRegister.name == _USDT_REGISTER_NAME,
            CashRegister.is_active == True,
        )
    )).scalar_one_or_none()
    if not reg:
        raise HTTPException(500, f"Cash register '{_USDT_REGISTER_NAME}' not found — run seed")
    return reg


async def _get_usdt_rate(db: AsyncSession, for_date: date) -> Decimal:
    row = (await db.execute(
        select(ExchangeRate).where(ExchangeRate.currency == "USDT")
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )).scalar_one_or_none()
    return Decimal(str(row.rate_to_cny)) if row else Decimal("7.2")


async def _get_default_company(db: AsyncSession) -> Company:
    company = (await db.execute(
        select(Company).where(Company.is_active == True).limit(1)
    )).scalar_one_or_none()
    if not company:
        raise HTTPException(500, "No active company configured")
    return company


async def _get_system_user(db: AsyncSession) -> User:
    user = (await db.execute(
        select(User).where(User.login == "admin", User.is_active == True)
    )).scalar_one_or_none()
    if not user:
        user = (await db.execute(
            select(User).where(User.is_active == True).limit(1)
        )).scalar_one_or_none()
    if not user:
        raise HTTPException(500, "No active user found for Payment creation")
    return user


async def _get_register_balance(db: AsyncSession, register_id: uuid.UUID) -> Decimal:
    from app.api.cash_registers import _get_balance
    return await _get_balance(db, register_id)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ProvisionBody(BaseModel):
    email: str
    client_code: str


class TotpEnableBody(BaseModel):
    email: str
    code: str


class ForgotPasswordBody(BaseModel):
    email: str


class VerifyPaymentBody(BaseModel):
    ref: str
    client_code: str
    erp_order_id: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/provision")
async def provision(
    body: ProvisionBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_site_auth),
):
    client = await _get_tt_client(db)
    try:
        result = await client.provision(email=body.email, external_id=body.client_code.upper())
    except TronTokError as e:
        raise HTTPException(502, f"TronTok error: {e}")

    # Mark counterparty as linked if found in ERP
    cp = (await db.execute(
        select(Counterparty).where(
            Counterparty.code == body.client_code.upper(),
            Counterparty.is_active == True,
        )
    )).scalar_one_or_none()
    if cp and not cp.trontok_linked:
        cp.trontok_linked = True
        cp.trontok_provisioned_at = datetime.now(timezone.utc)
        await db.commit()

    return result


@router.get("/user-status")
async def user_status(
    client_code: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_site_auth),
):
    client = await _get_tt_client(db)
    try:
        return await client.user_status(external_id=client_code.upper())
    except TronTokNotFound:
        return {"has_password": False, "totp_enabled": False}
    except TronTokError as e:
        raise HTTPException(502, f"TronTok error: {e}")


@router.get("/balance")
async def balance(
    client_code: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_site_auth),
):
    client = await _get_tt_client(db)
    try:
        return await client.get_balance(external_id=client_code.upper())
    except TronTokError as e:
        raise HTTPException(502, f"TronTok error: {e}")


@router.post("/totp-setup")
async def totp_setup(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_site_auth),
):
    email = body.get("email", "")
    if not email:
        raise HTTPException(422, "email is required")
    client = await _get_tt_client(db)
    try:
        return await client.totp_setup(email=email)
    except TronTokError as e:
        raise HTTPException(502, f"TronTok error: {e}")


@router.post("/totp-enable")
async def totp_enable(
    body: TotpEnableBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_site_auth),
):
    client = await _get_tt_client(db)
    try:
        return await client.totp_enable(email=body.email, code=body.code)
    except TronTokError as e:
        raise HTTPException(502, f"TronTok error: {e}")


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_site_auth),
):
    client = await _get_tt_client(db)
    ok = await client.forgot_password(email=body.email)
    return {"ok": ok}


@router.post("/verify-payment")
async def verify_payment(
    body: VerifyPaymentBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_site_auth),
):
    """
    1. Idempotency: return existing Payment if external_tx_id=ref already exists.
    2. Poll TronTok payment-status (up to 5 attempts).
    3. Create Payment + CashTransaction in ERP.
    4. Optionally link to ERP order if erp_order_id is provided.
    """
    ref = body.ref.strip()
    client_code = body.client_code.upper()

    # 1. Idempotency
    existing = (await db.execute(
        select(Payment).where(
            Payment.external_tx_id == ref,
            Payment.is_active == True,
        )
    )).scalar_one_or_none()
    if existing:
        return {"ok": True, "idempotent": True, "payment_id": str(existing.id)}

    # 2. Counterparty lookup
    cp = await _get_counterparty(db, client_code)

    # 3. TronTok payment-status with retries
    tt_client = await _get_tt_client(db)
    tt_result = None
    for attempt in range(5):
        try:
            tt_result = await tt_client.payment_status(ref=ref, external_id=client_code)
            if tt_result.get("found"):
                break
        except TronTokNotFound:
            pass
        except TronTokError as e:
            logger.warning("TronTok payment_status attempt %d failed: %s", attempt + 1, e)
        if attempt < 4:
            await asyncio.sleep(2)

    if not tt_result or not tt_result.get("found"):
        return {"ok": False, "found": False, "message": "Payment not confirmed yet — try again later"}

    amount_usdt = Decimal(str(tt_result["amount"]))
    today = date.today()

    # 4. Exchange rate + amounts
    rate = await _get_usdt_rate(db, today)
    amount_cny = (amount_usdt * rate).quantize(Decimal("0.01"))

    # 5. Cash register + company + system user
    reg = await _get_usdt_register(db)
    company = await _get_default_company(db)
    sys_user = await _get_system_user(db)

    # 6. Current register balance
    current_balance = await _get_register_balance(db, reg.id)
    new_balance = current_balance + amount_usdt

    # 7. Create Payment
    payment = Payment(
        id=uuid.uuid4(),
        company_id=company.id,
        direction="in",
        counterparty_id=cp.id,
        cash_register_id=reg.id,
        payment_date=today,
        currency="USDT",
        amount=amount_usdt,
        rate_to_cny=rate,
        amount_cny=amount_cny,
        notes=f"TronTok ref: {ref}",
        external_tx_id=ref,
        payment_source="trontok",
        created_by=sys_user.id,
        is_active=True,
    )
    db.add(payment)
    await db.flush()

    # 8. CashTransaction
    cash_tx = CashTransaction(
        id=uuid.uuid4(),
        cash_register_id=reg.id,
        payment_id=payment.id,
        direction="in",
        amount=amount_usdt,
        balance_after=new_balance,
        operation_type="payment_in",
        notes=f"TronTok ref: {ref}",
        created_by=sys_user.id,
    )
    db.add(cash_tx)
    await db.flush()

    # 9. Optional allocation to ERP order
    if body.erp_order_id:
        try:
            from app.models.order import Order
            order_uuid = uuid.UUID(body.erp_order_id)
            order = (await db.execute(
                select(Order).where(Order.id == order_uuid)
            )).scalar_one_or_none()
            if order:
                alloc = PaymentAllocation(
                    id=uuid.uuid4(),
                    payment_id=payment.id,
                    order_id=order.id,
                    amount_cny=amount_cny,
                )
                db.add(alloc)
                await db.flush()
                from app.api.payments import _recalc_all_for_payment
                await _recalc_all_for_payment(db, payment)
        except Exception as exc:
            logger.warning("Could not link payment to order %s: %s", body.erp_order_id, exc)

    # 10. Mark counterparty trontok_linked
    if not cp.trontok_linked:
        cp.trontok_linked = True
        cp.trontok_provisioned_at = datetime.now(timezone.utc)

    await db.commit()
    logger.info("TronTok payment verified and recorded: ref=%s amount=%s USDT payment_id=%s",
                ref, amount_usdt, payment.id)

    return {"ok": True, "idempotent": False, "payment_id": str(payment.id), "amount_usdt": str(amount_usdt)}


# ── ERP-frontend endpoints (JWT auth) ─────────────────────────────────────────

class TronTokSettingsResponse(BaseModel):
    base_url: Optional[str] = None
    api_token_masked: Optional[str] = None
    is_enabled: bool


class TronTokSettingsUpdate(BaseModel):
    api_token: Optional[str] = None
    base_url: Optional[str] = None
    is_enabled: Optional[bool] = None


def _mask_key(key: Optional[str]) -> Optional[str]:
    if not key or len(key) < 8:
        return key
    return key[:4] + "****" + key[-4:]


@router.get("/erp-settings", response_model=TronTokSettingsResponse)
async def erp_get_trontok_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """Get TronTok integration settings (partner key, enabled). Admin only."""
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == _TRONTOK_INTEGRATION)
    )).scalar_one_or_none()
    if not row:
        return TronTokSettingsResponse(is_enabled=False)
    return TronTokSettingsResponse(
        base_url=row.base_url,
        api_token_masked=_mask_key(row.api_token),
        is_enabled=row.is_enabled,
    )


@router.put("/erp-settings", response_model=TronTokSettingsResponse)
async def erp_update_trontok_settings(
    body: TronTokSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """Update TronTok partner key / base_url / enabled. Admin only."""
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == _TRONTOK_INTEGRATION)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "TronTok integration not found — run seed")
    if body.base_url is not None:
        row.base_url = body.base_url
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled
    if body.api_token is not None:
        masked = _mask_key(row.api_token)
        if body.api_token != masked:
            row.api_token = body.api_token
    await db.commit()
    return TronTokSettingsResponse(
        base_url=row.base_url,
        api_token_masked=_mask_key(row.api_token),
        is_enabled=row.is_enabled,
    )


@router.post("/erp-test")
async def erp_test_trontok(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    """Test TronTok connection using saved (or provided) partner key. Admin only."""
    row = (await db.execute(
        select(IntegrationSettings).where(IntegrationSettings.integration_name == _TRONTOK_INTEGRATION)
    )).scalar_one_or_none()

    api_key = body.get("api_token") or (row.api_token if row else None)
    base_url = body.get("base_url") or (row.base_url if row else None)

    if api_key and row and api_key == _mask_key(row.api_token):
        api_key = row.api_token

    if not api_key or not base_url:
        return {"ok": False, "message": "Партнёрский ключ и base_url обязательны"}

    client = TronTokClient(api_key=api_key, base_url=base_url)
    try:
        account = await client._get("/me/account")
        name = account.get("name", "?")
        status_val = account.get("status", "?")
        users = account.get("users_total", "?")
        return {"ok": True, "message": f"Партнёр: {name} | статус: {status_val} | пользователей: {users}"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


@router.get("/erp-balance")
async def erp_get_counterparty_balance(
    counterparty_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "accountant", "manager")),
):
    """Fetch TronTok balance for a counterparty. Uses ERP JWT auth (for ERP frontend)."""
    try:
        cp_uuid = uuid.UUID(counterparty_id)
    except ValueError:
        raise HTTPException(422, "Invalid counterparty_id")

    cp = (await db.execute(
        select(Counterparty).where(Counterparty.id == cp_uuid, Counterparty.is_active == True)
    )).scalar_one_or_none()
    if not cp:
        raise HTTPException(404, "Counterparty not found")
    if not cp.trontok_linked:
        return {"trontok_linked": False, "balance": None}
    if not cp.code:
        raise HTTPException(422, "Counterparty has no code")

    tt_client = await _get_tt_client(db)
    try:
        bal = await tt_client.get_balance(external_id=cp.code.upper())
        return {"trontok_linked": True, "balance": bal}
    except TronTokError as exc:
        raise HTTPException(502, f"TronTok error: {exc}")
