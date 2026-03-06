"""Technical indicators: RSI, moving averages, trend slope, Bollinger Bands, volume."""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def compute_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_moving_averages(prices: pd.Series, windows=(20, 50, 200)) -> Dict[str, pd.Series]:
    return {f"MA{w}": prices.rolling(w).mean() for w in windows}


def compute_trend_slope(prices: pd.Series, window: int = 20) -> float:
    """Normalized linear regression slope (% per day)."""
    if len(prices) < window:
        return 0.0
    recent = prices.iloc[-window:].values
    x = np.arange(window)
    try:
        slope, _ = np.polyfit(x, recent, 1)
        return float(slope / recent[0] * 100)
    except Exception:
        return 0.0


def volume_ratio(volume: pd.Series, window: int = 20) -> float:
    """Current volume vs N-day average ratio."""
    if len(volume) < window + 1:
        return 1.0
    avg = volume.iloc[-window - 1:-1].mean()
    return float(volume.iloc[-1] / avg) if avg > 0 else 1.0


def compute_technicals(df: pd.DataFrame) -> dict:
    """Compute all technical indicators. Returns dict with current values."""
    close = df["Close"]
    vol = df.get("Volume")

    rsi_series = compute_rsi(close)
    mas = compute_moving_averages(close)

    cur = float(close.iloc[-1])
    cur_rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0

    def safe_ma(key):
        v = mas[key].iloc[-1]
        return float(v) if not pd.isna(v) else cur

    ma20 = safe_ma("MA20") if len(close) >= 20 else cur
    ma50 = safe_ma("MA50") if len(close) >= 50 else cur
    ma200 = safe_ma("MA200") if len(close) >= 200 else cur

    def chg(n):
        return float((close.iloc[-1] / close.iloc[-n - 1] - 1) * 100) if len(close) > n else 0.0

    high = df.get("High", close)
    low = df.get("Low", close)
    tr = pd.concat([high - low,
                    (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else float(tr.mean())

    if len(close) >= 252:
        h52 = float(close.iloc[-252:].max())
        l52 = float(close.iloc[-252:].min())
    else:
        h52 = float(close.max())
        l52 = float(close.min())

    return {
        "price":           round(cur, 2),
        "rsi":             round(cur_rsi, 1),
        "ma20":            round(ma20, 2),
        "ma50":            round(ma50, 2),
        "ma200":           round(ma200, 2),
        "slope_20d":       round(compute_trend_slope(close, 20), 4),
        "chg_1d":          round(chg(1), 2),
        "chg_5d":          round(chg(5), 2),
        "chg_20d":         round(chg(20), 2),
        "vol_ratio":       round(volume_ratio(vol) if vol is not None else 1.0, 2),
        "atr_pct":         round(atr / cur * 100, 2),
        "above_ma20":      cur > ma20,
        "above_ma50":      cur > ma50,
        "above_ma200":     cur > ma200,
        "golden_cross":    ma50 > ma200,
        "high_52w":        round(h52, 2),
        "low_52w":         round(l52, 2),
        "pct_from_52w_high": round((cur / h52 - 1) * 100, 2),
    }


def detect_regime_change(df: pd.DataFrame) -> Optional[str]:
    """Detect golden/death cross or MA50 breakouts in last 5 days."""
    if len(df) < 52:
        return None
    close = df["Close"]
    mas = compute_moving_averages(close)
    ma50 = mas["MA50"]
    ma200 = mas["MA200"]
    changes = []

    if len(ma50.dropna()) >= 5 and len(ma200.dropna()) >= 5:
        m50n, m200n = ma50.iloc[-1], ma200.iloc[-1]
        m50p, m200p = ma50.iloc[-5], ma200.iloc[-5]
        if pd.notna(m50n) and pd.notna(m200n) and pd.notna(m50p) and pd.notna(m200p):
            if m50n > m200n and m50p <= m200p:
                changes.append("GOLDEN CROSS (MA50>MA200)")
            elif m50n < m200n and m50p >= m200p:
                changes.append("DEATH CROSS (MA50<MA200)")

    if len(ma50.dropna()) >= 3:
        pn, pp = close.iloc[-1], close.iloc[-3]
        mn, mp = ma50.iloc[-1], ma50.iloc[-3]
        if pd.notna(mn) and pd.notna(mp):
            if pn > mn and pp <= mp:
                changes.append("Price broke above MA50")
            elif pn < mn and pp >= mp:
                changes.append("Price broke below MA50")

    return " | ".join(changes) if changes else None