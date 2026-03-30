"""Buy/Sell signal generation.
BUY:  RSI < threshold AND slope > 0 AND volume > avg
SELL: RSI > threshold OR trend breakdown
"""
import pandas as pd
from typing import Dict, List
from analytics.technicals import compute_technicals, detect_regime_change
import logging

logger = logging.getLogger(__name__)


def generate_signal(symbol: str, tech: dict, config: dict) -> dict:
    rsi_buy  = config.get("signals", {}).get("rsi_buy_threshold", 35)
    rsi_sell = config.get("signals", {}).get("rsi_sell_threshold", 70)
    vol_mult = config.get("signals", {}).get("volume_multiplier", 1.2)

    rsi       = tech["rsi"]
    slope     = tech["slope_20d"]
    vol_ratio = tech["vol_ratio"]
    above_ma50 = tech["above_ma50"]
    above_ma200 = tech["above_ma200"]

    score = 0
    buy_reasons, sell_reasons = [], []

    # --- BUY ---
    if rsi < rsi_buy:
        buy_reasons.append(f"RSI oversold ({rsi:.1f})")
        score += 30
    elif rsi < 45:
        buy_reasons.append(f"RSI low ({rsi:.1f})")
        score += 10

    if slope > 0:
        buy_reasons.append(f"Positive trend (+{slope:.3f}%/d)")
        score += 20

    if vol_ratio >= vol_mult:
        buy_reasons.append(f"High volume ({vol_ratio:.1f}x avg)")
        score += 15

    if above_ma50 and above_ma200:
        buy_reasons.append("Above MA50 & MA200")
        score += 15
    elif above_ma50:
        buy_reasons.append("Above MA50")
        score += 8

    if tech.get("golden_cross"):
        buy_reasons.append("Golden Cross")
        score += 20

    # --- SELL ---
    if rsi > rsi_sell:
        sell_reasons.append(f"RSI overbought ({rsi:.1f})")
        score -= 30
    elif rsi > 60:
        sell_reasons.append(f"RSI elevated ({rsi:.1f})")
        score -= 10

    if slope < -0.05:
        sell_reasons.append(f"Negative trend ({slope:.3f}%/d)")
        score -= 20

    if not above_ma50:
        sell_reasons.append("Below MA50 (breakdown)")
        score -= 15

    if not above_ma200:
        sell_reasons.append("Below MA200 (bearish)")
        score -= 15

    if not tech.get("golden_cross") and not above_ma200:
        sell_reasons.append("Death Cross condition")
        score -= 10

    if score >= 45 and len(buy_reasons) >= 2:
        signal, reasons = "BUY", buy_reasons
    elif score <= -35 and sell_reasons:
        signal, reasons = "SELL", sell_reasons
    elif score >= 20:
        signal, reasons = "WEAK_BUY", buy_reasons
    elif score <= -15:
        signal, reasons = "WEAK_SELL", sell_reasons
    else:
        signal, reasons = "HOLD", buy_reasons + sell_reasons

    return {
        "symbol":   symbol,
        "signal":   signal,
        "score":    score,
        "rsi":      rsi,
        "slope_20d": slope,
        "vol_ratio": vol_ratio,
        "chg_1d":   tech["chg_1d"],
        "chg_5d":   tech["chg_5d"],
        "price":    tech["price"],
        "reasons":  reasons,
    }


def generate_all_signals(price_data: Dict[str, pd.DataFrame], config: dict) -> List[dict]:
    """Generate signals for all symbols, sorted BUY -> HOLD -> SELL."""
    signals = []
    for symbol, df in price_data.items():
        if len(df) < 20:
            logger.warning(f"Not enough data for {symbol}")
            continue
        try:
            tech = compute_technicals(df)
            sig  = generate_signal(symbol, tech, config)
            sig["regime_change"] = detect_regime_change(df)
            signals.append(sig)
        except Exception as e:
            logger.error(f"Signal error for {symbol}: {e}")

    order = {"BUY": 0, "WEAK_BUY": 1, "HOLD": 2, "WEAK_SELL": 3, "SELL": 4}
    signals.sort(key=lambda x: (order.get(x["signal"], 2), -x["score"]))
    return signals