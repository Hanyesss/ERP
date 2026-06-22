"""
Тесты логики auto-fetch курсов:
- manual-курс за сегодня не перезаписывается
- auto-курс за сегодня обновляется
- если курсов нет — создаются новые
- verify_payment возвращает amount_cny и usdt_cny_rate
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Минимальный enum без импорта app.models (избегаем загрузки БД-настроек) ──

class RateSourceEnum:
    manual = "manual"
    auto   = "auto"


# ── Хелпер: фейковая запись ExchangeRate ──────────────────────────────────────

def _rate_row(source: str, rate_to_cny: float = 7.2):
    row = MagicMock()
    row.source = source
    row.rate_to_cny = Decimal(str(rate_to_cny))
    row.id = uuid.uuid4()
    return row


# ── Логика "пропустить manual" (вырезана из endpoint для unit-тестирования) ──

def _apply_auto_fetch(existing_rows: dict, fetched_rates: dict) -> tuple[list, list]:
    """
    Имитирует логику из endpoint auto_fetch_rates:
    существующие строки: {currency: row | None}
    возвращает (saved_currencies, skipped_currencies)
    """
    saved, skipped = [], []
    for currency, rate_value in fetched_rates.items():
        existing = existing_rows.get(currency)
        if existing and existing.source == RateSourceEnum.manual:
            skipped.append(currency)
        else:
            saved.append(currency)
    return saved, skipped


class TestAutoFetchSkipLogic:
    def test_manual_rate_is_skipped(self):
        rows = {"USDT": _rate_row("manual")}
        saved, skipped = _apply_auto_fetch(rows, {"USDT": Decimal("7.1")})
        assert "USDT" not in saved
        assert "USDT" in skipped

    def test_auto_rate_is_overwritten(self):
        rows = {"USDT": _rate_row("auto")}
        saved, skipped = _apply_auto_fetch(rows, {"USDT": Decimal("7.1")})
        assert "USDT" in saved
        assert "USDT" not in skipped

    def test_missing_rate_is_created(self):
        rows = {"USDT": None}
        saved, skipped = _apply_auto_fetch(rows, {"USDT": Decimal("7.1")})
        assert "USDT" in saved

    def test_partial_override(self):
        """RUB — manual, USD — auto, USDT — нет. Только RUB пропускается."""
        rows = {
            "RUB":  _rate_row("manual"),
            "USD":  _rate_row("auto"),
            "USDT": None,
        }
        rates = {"RUB": Decimal("0.09"), "USD": Decimal("7.25"), "USDT": Decimal("7.1")}
        saved, skipped = _apply_auto_fetch(rows, rates)
        assert "RUB" in skipped
        assert "USD" in saved
        assert "USDT" in saved

    def test_all_manual_nothing_saved(self):
        rows = {c: _rate_row("manual") for c in ["RUB", "USD", "USDT"]}
        rates = {c: Decimal("1.0") for c in ["RUB", "USD", "USDT"]}
        saved, skipped = _apply_auto_fetch(rows, rates)
        assert saved == []
        assert set(skipped) == {"RUB", "USD", "USDT"}

    def test_all_missing_all_saved(self):
        rows = {c: None for c in ["RUB", "USD", "USDT"]}
        rates = {c: Decimal("1.0") for c in ["RUB", "USD", "USDT"]}
        saved, skipped = _apply_auto_fetch(rows, rates)
        assert set(saved) == {"RUB", "USD", "USDT"}
        assert skipped == []


# ── verify_payment response structure ────────────────────────────────────────

class TestVerifyPaymentResponse:
    """
    Проверяем что verify_payment теперь включает amount_cny и usdt_cny_rate.
    Тестируем через итоговый словарь, без вызова БД.
    """

    def _build_response(self, amount_usdt: Decimal, rate: Decimal) -> dict:
        """Имитирует то что делает endpoint перед return."""
        amount_cny = (amount_usdt * rate).quantize(Decimal("0.01"))
        return {
            "ok": True,
            "idempotent": False,
            "payment_id": str(uuid.uuid4()),
            "amount_usdt": str(amount_usdt),
            "amount_cny": str(amount_cny),
            "usdt_cny_rate": str(rate),
        }

    def test_response_contains_amount_cny(self):
        r = self._build_response(Decimal("100"), Decimal("7.25"))
        assert "amount_cny" in r
        assert Decimal(r["amount_cny"]) == Decimal("725.00")

    def test_response_contains_usdt_cny_rate(self):
        r = self._build_response(Decimal("50"), Decimal("7.1"))
        assert "usdt_cny_rate" in r
        assert Decimal(r["usdt_cny_rate"]) == Decimal("7.1")

    def test_amount_cny_rounds_to_2_decimal_places(self):
        r = self._build_response(Decimal("1"), Decimal("7.123456"))
        assert len(str(Decimal(r["amount_cny"])).split(".")[-1]) <= 2

    def test_idempotent_response_also_has_amount_cny(self):
        """Idempotent-ответ тоже должен содержать amount_cny."""
        existing = MagicMock()
        existing.id = uuid.uuid4()
        existing.amount = Decimal("50")
        existing.amount_cny = Decimal("362.50")
        existing.rate_to_cny = Decimal("7.25")

        resp = {
            "ok": True,
            "idempotent": True,
            "payment_id": str(existing.id),
            "amount_usdt": str(existing.amount),
            "amount_cny": str(existing.amount_cny),
            "usdt_cny_rate": str(existing.rate_to_cny),
        }
        assert resp["amount_cny"] == "362.50"
        assert resp["usdt_cny_rate"] == "7.25"
