"""Short squeeze risk detection."""
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def score_short_risk(symbol: str, short_data: dict, tech: dict, config: dict) -> dict:
    si_threshold    = config.get("signals", {}).get("short_interest_threshold", 10)
    price_gain_thr  = config.get("signals", {}).get("squeeze_price_gain_pct", 5)

    short_float  = short_data.get("short_float") or 0
    short_ratio  = short_data.get("short_ratio") or 0
    rel_volume   = short_data.get("rel_volume") or tech.get("vol_ratio", 1)
    price_chg_5d = tech.get("chg_5d", 0)
    price_chg_1d = tech.get("chg_1d", 0)
    rsi          = tech.get("rsi", 50)

    risk_score = 0
    factors = []

    if short_float > 25:
        risk_score += 35; factors.append(f"Extreme short float: {short_float:.1f}%")
    elif short_float > 15:
        risk_score += 25; factors.append(f"Very high short float: {short_float:.1f}%")
    elif short_float > si_threshold:
        risk_score += 15; factors.append(f"High short float: {short_float:.1f}%")

    if short_ratio > 10:
        risk_score += 20; factors.append(f"Days-to-cover: {short_ratio:.1f}")
    elif short_ratio > 5:
        risk_score += 10; factors.append(f"Elevated DTC: {short_ratio:.1f}")

    if price_chg_5d > price_gain_thr * 2:
        risk_score += 25; factors.append(f"Strong 5d gain: +{price_chg_5d:.1f}%")
    elif price_chg_5d > price_gain_thr:
        risk_score += 15; factors.append(f"5d gain: +{price_chg_5d:.1f}%")

    if price_chg_1d > 5:
        risk_score += 15; factors.append(f"Intraday move: +{price_chg_1d:.1f}%")

    if rel_volume > 3:
        risk_score += 20; factors.append(f"Volume spike: {rel_volume:.1f}x")
    elif rel_volume > 2:
        risk_score += 10; factors.append(f"High volume: {rel_volume:.1f}x")

    if rsi > 65 and short_float > si_threshold:
        risk_score += 10; factors.append(f"Overbought + high SI: RSI {rsi:.0f}")

    if risk_score >= 60:
        level = "EXTREME"
    elif risk_score >= 35:
        level = "HIGH"
    elif risk_score >= 15:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "symbol":       symbol,
        "risk_level":   level,
        "risk_score":   risk_score,
        "short_float":  short_float,
        "short_ratio":  short_ratio,
        "rel_volume":   rel_volume,
        "price_chg_5d": price_chg_5d,
        "price_chg_1d": price_chg_1d,
        "risk_factors": factors,
    }


def get_high_risk_shorts(all_short_data: Dict[str, dict], all_technicals: Dict[str, dict], config: dict) -> List[dict]:
    """Score all symbols and return sorted by risk score descending."""
    results = []
    for symbol, sd in all_short_data.items():
        tech = all_technicals.get(symbol, {})
        if not tech:
            continue
        results.append(score_short_risk(symbol, sd, tech, config))
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results