"""Macro/market regime data: VIX, indices, yields."""
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import yfinance as yf
from typing import Dict
import logging

from data_fetching.ssl_session import get_yf_session

logger = logging.getLogger(__name__)
_SESSION = get_yf_session()

MACRO_SYMBOLS = {
    "VIX":       "^VIX",
    "SP500":     "^GSPC",
    "NASDAQ":    "^IXIC",
    "DOW":       "^DJI",
    "EUROSTOXX": "^STOXX50E",
    "10Y_YIELD": "^TNX",
    "GOLD":      "GLD",
    "OIL":       "USO",
    "DXY":       "DX-Y.NYB",
}


def fetch_macro_snapshot() -> Dict:
    """Fetch current macro data with 1d/5d/20d changes."""
    result = {}
    for name, symbol in MACRO_SYMBOLS.items():
        try:
            hist = yf.Ticker(symbol, session=_SESSION).history(period="1mo")
            if hist.empty:
                continue
            c   = float(hist["Close"].iloc[-1])
            p1  = float(hist["Close"].iloc[-2])  if len(hist) > 1  else c
            p5  = float(hist["Close"].iloc[-6])  if len(hist) > 5  else c
            p20 = float(hist["Close"].iloc[-21]) if len(hist) > 20 else c
            result[name] = {
                "symbol":  symbol,
                "price":   round(c, 2),
                "change_1d_pct":  round((c / p1  - 1) * 100, 2),
                "change_5d_pct":  round((c / p5  - 1) * 100, 2),
                "change_20d_pct": round((c / p20 - 1) * 100, 2),
            }
        except Exception as e:
            logger.error(f"Macro error {name}: {e}")
    vix  = result.get("VIX",   {}).get("price", 20)
    sp20 = result.get("SP500", {}).get("change_20d_pct", 0)
    if vix < 15 and sp20 > 2:
        result["regime"] = "RISK_ON"
    elif vix > 25 or sp20 < -5:
        result["regime"] = "RISK_OFF"
    else:
        result["regime"] = "NEUTRAL"
    return result


def get_market_regime(macro: Dict) -> str:
    """Classify market regime: RISK_ON / NEUTRAL / RISK_OFF."""
    return macro.get("regime", "NEUTRAL")
