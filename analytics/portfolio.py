"""Portfolio analysis: P&L, drawdown, sector exposure."""
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def load_portfolio(csv_path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.strip().lower() for c in df.columns]
        if "short_position" not in df.columns:
            df["short_position"] = False
        df["short_position"] = df["short_position"].apply(
            lambda x: str(x).strip().lower() in ("true", "1", "yes")
        )
        return df
    except FileNotFoundError:
        logger.warning(f"Portfolio file not found: {csv_path}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading portfolio: {e}")
        return pd.DataFrame()


def enrich_portfolio(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Add current prices and P&L to portfolio DataFrame."""
    from data_fetching.market_data import fetch_current_price
    if portfolio.empty:
        return portfolio
    portfolio = portfolio.copy()
    cur_prices, pnl, pnl_pct, mvals = [], [], [], []
    for _, row in portfolio.iterrows():
        entry = float(row["entry_price"])
        shares = float(row["shares"])
        is_short = bool(row.get("short_position", False))
        cur = fetch_current_price(str(row["symbol"])) or entry
        if is_short:
            p = (entry - cur) * shares
            pp = (entry - cur) / entry * 100
            mv = -cur * shares
        else:
            p = (cur - entry) * shares
            pp = (cur - entry) / entry * 100
            mv = cur * shares
        cur_prices.append(round(cur, 2))
        pnl.append(round(p, 2))
        pnl_pct.append(round(pp, 2))
        mvals.append(round(mv, 2))
    portfolio["current_price"] = cur_prices
    portfolio["pnl"] = pnl
    portfolio["pnl_pct"] = pnl_pct
    portfolio["market_value"] = mvals
    return portfolio


def sector_exposure(portfolio: pd.DataFrame) -> pd.DataFrame:
    if portfolio.empty or "sector" not in portfolio.columns:
        return pd.DataFrame()
    total_abs = portfolio["market_value"].abs().sum()
    if total_abs == 0:
        return pd.DataFrame()
    grouped = portfolio.groupby("sector")["market_value"].sum().reset_index()
    grouped["exposure_pct"] = (grouped["market_value"] / total_abs * 100).round(1)
    return grouped.sort_values("exposure_pct", ascending=False)


def calculate_portfolio_volatility(portfolio: pd.DataFrame, price_history: dict) -> float:
    """Estimate annualized portfolio volatility %."""
    if portfolio.empty:
        return 0.0
    returns_list, weights = [], []
    for _, row in portfolio.iterrows():
        sym = row["symbol"]
        if sym not in price_history:
            continue
        ret = price_history[sym]["Close"].pct_change().dropna()
        if len(ret) > 20:
            returns_list.append(ret)
            weights.append(abs(row.get("market_value", 1)))
    if not returns_list:
        return 0.0
    returns_df = pd.concat(returns_list, axis=1).dropna()
    if returns_df.empty:
        return 0.0
    total_w = sum(weights[:len(returns_df.columns)])
    if total_w == 0:
        return 0.0
    norm_w = [w / total_w for w in weights[:len(returns_df.columns)]]
    port_ret = returns_df.values @ np.array(norm_w)
    return round(float(np.std(port_ret) * np.sqrt(252) * 100), 2)


def max_drawdown(portfolio: pd.DataFrame, price_history: dict) -> dict:
    """Calculate max drawdown per position."""
    results = {}
    for _, row in portfolio.iterrows():
        sym = row["symbol"]
        if sym not in price_history:
            continue
        close = price_history[sym]["Close"]
        entry_date = row.get("entry_date")
        if entry_date:
            try:
                close = close[close.index >= pd.Timestamp(entry_date)]
            except Exception:
                pass
        if len(close) < 2:
            continue
        running_max = close.cummax()
        dd = (close - running_max) / running_max * 100
        results[sym] = {
            "max_drawdown_pct": round(float(dd.min()), 2),
            "current_drawdown_pct": round(float(dd.iloc[-1]), 2),
        }
    return results


def check_alerts(portfolio: pd.DataFrame, stop_loss_pct: float = 7.0, target_pct: float = 15.0) -> List[dict]:
    """Return list of stop-loss / target-hit alerts."""
    alerts = []
    if portfolio.empty:
        return alerts
    for _, row in portfolio.iterrows():
        pnl_pct = row.get("pnl_pct", 0)
        sym = row["symbol"]
        label = "Short" if bool(row.get("short_position", False)) else "Long"
        if pnl_pct <= -stop_loss_pct:
            alerts.append({
                "symbol": sym, "type": "STOP_LOSS",
                "message": f"{label} {sym} stop-loss hit: {pnl_pct:.1f}%",
                "pnl_pct": pnl_pct,
            })
        elif pnl_pct >= target_pct:
            alerts.append({
                "symbol": sym, "type": "TARGET",
                "message": f"{label} {sym} target hit: +{pnl_pct:.1f}%",
                "pnl_pct": pnl_pct,
            })
    return alerts