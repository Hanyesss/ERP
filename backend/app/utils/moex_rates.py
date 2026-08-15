"""
Fetch live exchange rates from MOEX (fallback: CBR).
Same algorithm as irsway's shipments/services/rates.py — keeps both systems in sync.
"""
import logging
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

_MOEX_TIMEOUT = 10
_CBR_TIMEOUT = 10
_USD_USDT = Decimal("1.02")


def _d(x) -> Decimal:
    return Decimal(str(x))


def _moex_price(secid: str) -> Decimal:
    url = (
        "https://iss.moex.com/iss/engines/currency/markets/selt/boards/CETS/"
        f"securities/{secid}.json"
    )
    r = httpx.get(url, params={"iss.meta": "off", "iss.only": "marketdata",
                               "marketdata.columns": "LAST,WAPRICE"},
                  timeout=_MOEX_TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    md = r.json().get("marketdata", {}).get("data", [])
    if not md:
        raise RuntimeError(f"MOEX: no marketdata for {secid}")
    last, waprice = md[0][0], md[0][1]
    if last not in (None, "", 0):
        return _d(last)
    if waprice not in (None, "", 0):
        return _d(waprice)
    raise RuntimeError(f"MOEX market closed for {secid}: LAST and WAPRICE empty")


def _moex_any(secids: list[str]) -> Decimal:
    last_err = None
    for s in secids:
        try:
            return _moex_price(s)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"MOEX cannot get price for {secids}: {last_err}")


def _cbr_usd_cny_rub() -> tuple[Decimal, Decimal]:
    r = httpx.get("https://www.cbr.ru/scripts/XML_daily.asp", timeout=_CBR_TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    xml = r.text

    def _find(charcode: str) -> Decimal:
        idx = xml.find(f"<CharCode>{charcode}</CharCode>")
        if idx == -1:
            raise RuntimeError(f"CBR: {charcode} not found")
        vi = xml.find("<Value>", idx)
        ve = xml.find("</Value>", vi)
        return _d(xml[vi + 7:ve].strip().replace(",", "."))

    return _find("USD"), _find("CNY")


def fetch_rates() -> dict:
    """
    Returns rates as stored in ERP ExchangeRate table (rate_to_cny):
      rub_to_cny  : 1 RUB  = ? CNY
      usd_to_cny  : 1 USD  = ? CNY
      usdt_to_cny : 1 USDT = ? CNY
    """
    try:
        usd_rub = _moex_any(["USD000UTSTOM", "USDRUB_TOM", "USDRUB_TOD"])
        cny_rub = _moex_any(["CNYRUB_TOM", "CNYRUB_TOD"])
        source = "moex"
    except Exception as e:
        logger.warning("MOEX unavailable (%s), falling back to CBR", e)
        usd_rub, cny_rub = _cbr_usd_cny_rub()
        source = "cbr"

    usd_to_cny = usd_rub / cny_rub
    rub_to_cny = _d("1") / cny_rub
    usdt_to_cny = usd_to_cny / _USD_USDT

    logger.info(
        "Rates fetched from %s: USD/CNY=%.4f RUB/CNY=%.6f USDT/CNY=%.4f",
        source, usd_to_cny, rub_to_cny, usdt_to_cny,
    )

    return {
        "rub_to_cny":  rub_to_cny,
        "usd_to_cny":  usd_to_cny,
        "usdt_to_cny": usdt_to_cny,
        "source": source,
    }
