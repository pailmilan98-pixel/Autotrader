"""Market data fetching via yfinance."""
import time
import warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import yfinance as yf
import pandas as pd
from typing import List, Dict, Optional
import logging

from data_fetching.ssl_session import get_yf_session

logger = logging.getLogger(__name__)
_SESSION = get_yf_session()


def fetch_price_history(symbols: List[str], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """Fetch daily OHLCV data for a list of symbols using a single batch download."""
    if not symbols:
        return {}
    data = {}
    try:
        raw = yf.download(
            symbols,
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
        if len(symbols) == 1:
            sym = symbols[0]
            if not raw.empty:
                data[sym] = raw
                logger.info(f"Fetched {len(raw)} rows for {sym}")
        else:
            for symbol in symbols:
                try:
                    df = raw[symbol].dropna(how="all")
                    if not df.empty:
                        data[symbol] = df
                        logger.info(f"Fetched {len(df)} rows for {symbol}")
                    else:
                        logger.warning(f"No price data for {symbol}")
                except KeyError:
                    logger.warning(f"No price data for {symbol}")
    except Exception as e:
        logger.error(f"Batch price download failed: {e}")
    return data


def fetch_current_price(symbol: str) -> Optional[float]:
    """Fetch latest closing price for a symbol."""
    try:
        ticker = yf.Ticker(symbol, session=_SESSION)
        hist = ticker.history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
    return None


def fetch_fundamentals(symbols: List[str]) -> Dict[str, dict]:
    """Fetch key fundamental metrics for a list of symbols."""
    fundamentals = {}
    for symbol in symbols:
        try:
            time.sleep(0.5)
            info = yf.Ticker(symbol, session=_SESSION).info
            fundamentals[symbol] = {
                "name":           info.get("longName") or info.get("shortName", symbol),
                "sector":         info.get("sector", "N/A"),
                "market_cap":     info.get("marketCap"),
                "pe_ratio":       info.get("trailingPE"),
                "pb_ratio":       info.get("priceToBook"),
                "ps_ratio":       info.get("priceToSalesTrailing12Months"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth":info.get("earningsGrowth"),
                "dividend_yield": info.get("dividendYield"),
                "beta":           info.get("beta"),
                "52w_high":       info.get("fiftyTwoWeekHigh"),
                "52w_low":        info.get("fiftyTwoWeekLow"),
                "avg_volume_10d": info.get("averageVolume10days"),
                "float_shares":   info.get("floatShares"),
            }
        except Exception as e:
            logger.error(f"Error fetching fundamentals for {symbol}: {e}")
            fundamentals[symbol] = {"name": symbol, "sector": "N/A"}
    return fundamentals


def get_all_symbols(config: dict) -> List[str]:
    """Flatten all watchlist symbols from config."""
    wl = config.get("watchlist", {})
    symbols = []
    for category in ["etfs", "us_stocks", "eu_stocks", "crypto"]:
        symbols.extend(wl.get(category, []))
    return symbols
