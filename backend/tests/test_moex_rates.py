"""
Тесты утилиты moex_rates.py:
- MOEX успех: парсинг LAST и WAPRICE
- MOEX → ЦБ РФ fallback при закрытой бирже
- ЦБ РФ: парсинг XML
- Правильный расчёт rub_to_cny, usd_to_cny, usdt_to_cny
"""
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _moex_response(last=None, waprice=None):
    """Фейковый ответ MOEX ISS."""
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "marketdata": {"data": [[last, waprice]]}
    }
    return mock


def _cbr_response(usd_rub="85.5000", cny_rub="11.5000"):
    """Фейковый XML ЦБ РФ."""
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.text = f"""<?xml version="1.0" encoding="windows-1251"?>
<ValCurs>
  <Valute ID="R01235">
    <CharCode>USD</CharCode><Value>{usd_rub}</Value>
  </Valute>
  <Valute ID="R01375">
    <CharCode>CNY</CharCode><Value>{cny_rub}</Value>
  </Valute>
</ValCurs>"""
    return mock


# ── _moex_price ───────────────────────────────────────────────────────────────

class TestMoexPrice:
    def test_uses_last_when_available(self):
        from app.utils.moex_rates import _moex_price
        with patch("app.utils.moex_rates.requests.get", return_value=_moex_response(last=85.5)):
            assert _moex_price("USD000UTSTOM") == Decimal("85.5")

    def test_falls_back_to_waprice_when_last_is_none(self):
        from app.utils.moex_rates import _moex_price
        with patch("app.utils.moex_rates.requests.get", return_value=_moex_response(last=None, waprice=85.3)):
            assert _moex_price("USD000UTSTOM") == Decimal("85.3")

    def test_raises_when_both_null(self):
        from app.utils.moex_rates import _moex_price
        with patch("app.utils.moex_rates.requests.get", return_value=_moex_response(last=None, waprice=None)):
            with pytest.raises(RuntimeError, match="MOEX market closed"):
                _moex_price("USD000UTSTOM")

    def test_raises_when_no_marketdata(self):
        from app.utils.moex_rates import _moex_price
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {"marketdata": {"data": []}}
        with patch("app.utils.moex_rates.requests.get", return_value=mock):
            with pytest.raises(RuntimeError, match="no marketdata"):
                _moex_price("USD000UTSTOM")


# ── _cbr_usd_cny_rub ─────────────────────────────────────────────────────────

class TestCbrParsing:
    def test_parses_usd_and_cny(self):
        from app.utils.moex_rates import _cbr_usd_cny_rub
        with patch("app.utils.moex_rates.requests.get", return_value=_cbr_response("85,5000", "11,5000")):
            usd, cny = _cbr_usd_cny_rub()
        assert usd == Decimal("85.5")
        assert cny == Decimal("11.5")

    def test_dot_separator_also_works(self):
        from app.utils.moex_rates import _cbr_usd_cny_rub
        with patch("app.utils.moex_rates.requests.get", return_value=_cbr_response("85.5000", "11.5000")):
            usd, cny = _cbr_usd_cny_rub()
        assert usd == Decimal("85.5")
        assert cny == Decimal("11.5")


# ── fetch_rates ───────────────────────────────────────────────────────────────

class TestFetchRates:
    def _mock_moex(self, usd_rub=85.0, cny_rub=11.5):
        """Возвращает side_effect для requests.get под MOEX-запросы."""
        def _get(url, **kw):
            if "USD" in url or "USD000" in url.upper():
                return _moex_response(last=usd_rub)
            return _moex_response(last=cny_rub)
        return _get

    def test_moex_path_calculates_correct_rates(self):
        from app.utils.moex_rates import fetch_rates
        # USD/RUB=85, CNY/RUB=11.5 → usd_to_cny = 85/11.5 ≈ 7.3913
        calls = [
            _moex_response(last=85.0),  # USD/RUB
            _moex_response(last=11.5),  # CNY/RUB
        ]
        with patch("app.utils.moex_rates.requests.get", side_effect=calls):
            r = fetch_rates()

        assert r["source"] == "moex"
        assert abs(float(r["usd_to_cny"]) - 85.0 / 11.5) < 0.0001
        assert abs(float(r["rub_to_cny"]) - 1.0 / 11.5) < 0.00001
        # usdt_to_cny = usd_to_cny / 1.02
        expected_usdt = (Decimal("85.0") / Decimal("11.5")) / Decimal("1.02")
        assert abs(float(r["usdt_to_cny"]) - float(expected_usdt)) < 0.0001

    def test_falls_back_to_cbr_when_moex_closed(self):
        from app.utils.moex_rates import fetch_rates
        # Первые запросы к MOEX возвращают null → MOEX закрыт → fallback CBR
        moex_closed = _moex_response(last=None, waprice=None)
        cbr_resp = _cbr_response("85.0000", "11.5000")

        def _get(url, **kw):
            if "cbr.ru" in url:
                return cbr_resp
            return moex_closed

        with patch("app.utils.moex_rates.requests.get", side_effect=_get):
            r = fetch_rates()

        assert r["source"] == "cbr"
        assert abs(float(r["usd_to_cny"]) - 85.0 / 11.5) < 0.0001

    def test_usdt_rate_uses_fixed_1_02_multiplier(self):
        from app.utils.moex_rates import fetch_rates
        calls = [
            _moex_response(last=102.0),  # USD/RUB=102, удобно для проверки
            _moex_response(last=10.0),   # CNY/RUB=10 → usd_to_cny=10.2
        ]
        with patch("app.utils.moex_rates.requests.get", side_effect=calls):
            r = fetch_rates()
        # usd_to_cny = 102/10 = 10.2, usdt_to_cny = 10.2 / 1.02 = 10.0
        assert abs(float(r["usdt_to_cny"]) - 10.0) < 0.0001

    def test_result_keys_present(self):
        from app.utils.moex_rates import fetch_rates
        calls = [_moex_response(last=85.0), _moex_response(last=11.5)]
        with patch("app.utils.moex_rates.requests.get", side_effect=calls):
            r = fetch_rates()
        assert {"rub_to_cny", "usd_to_cny", "usdt_to_cny", "source"} <= r.keys()
