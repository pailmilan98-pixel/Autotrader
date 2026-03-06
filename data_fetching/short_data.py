"""Short interest data scraping from Finviz."""
import warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict
import time
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://finviz.com/",
}


def fetch_finviz_short_data(symbol: str) -> dict:
    """Scrape short interest data for a single symbol from Finviz."""
    url = f"https://finviz.com/quote.ashx?t={symbol}&ty=c&p=d&b=1"
    result = {
        "symbol":       symbol,
        "short_float":  None,
        "short_ratio":  None,
        "short_shares": None,
        "avg_volume":   None,
        "rel_volume":   None,
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        cells = []
        for table in soup.find_all("table"):
            tds = table.find_all("td")
            if len(tds) >= 20:
                cells = tds
                break

        data = {}
        for i in range(0, len(cells) - 1, 2):
            key = cells[i].get_text(strip=True)
            val = cells[i + 1].get_text(strip=True)
            data[key] = val

        def parse_number(s: str) -> float:
            s = s.replace(",", "").strip()
            if s.endswith("M"):
                return float(s[:-1]) * 1e6
            if s.endswith("B"):
                return float(s[:-1]) * 1e9
            return float(s)

        sf = data.get("Short Float", "")
        if sf:
            try:
                result["short_float"] = float(sf.replace("%", "").strip())
            except Exception:
                pass

        sr = data.get("Short Ratio", "")
        if sr:
            try:
                result["short_ratio"] = float(sr)
            except Exception:
                pass

        si = data.get("Short Interest", "")
        if si:
            try:
                result["short_shares"] = parse_number(si)
            except Exception:
                pass

        rv = data.get("Rel Volume", "")
        if rv:
            try:
                result["rel_volume"] = float(rv)
            except Exception:
                pass

        av = data.get("Avg Volume", "")
        if av:
            try:
                result["avg_volume"] = parse_number(av)
            except Exception:
                pass

        logger.info(
            f"Short data {symbol}: float={result['short_float']}% ratio={result['short_ratio']}"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error for {symbol}: {e}")
    except Exception as e:
        logger.error(f"Parse error for {symbol}: {e}")
    return result


def fetch_short_data_batch(symbols: List[str], delay: float = 1.5) -> Dict[str, dict]:
    """Fetch short data for multiple symbols with rate limiting."""
    results = {}
    for i, symbol in enumerate(symbols):
        logger.info(f"Short data: {symbol} ({i + 1}/{len(symbols)})")
        results[symbol] = fetch_finviz_short_data(symbol)
        if i < len(symbols) - 1:
            time.sleep(delay)
    return results


def build_short_dataframe(short_data: Dict[str, dict]) -> pd.DataFrame:
    """Convert short data dict to sorted DataFrame."""
    df = pd.DataFrame(list(short_data.values()))
    if "short_float" in df.columns:
        df = df.sort_values("short_float", ascending=False, na_position="last")
    return df.reset_index(drop=True)
