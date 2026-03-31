"""
AutoTrader – Daily Research & Monitoring Orchestrator
Run directly:  python main.py [daily_research|short_monitoring|portfolio|alerts|all]
Scheduled via: run_daily.bat (Windows Task Scheduler)
"""
import argparse
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

import yaml

# ── logging setup ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"{datetime.now():%Y-%m-%d}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("autotrader")


def load_config(path: str = "config.yaml") -> dict:
    cfg_path = BASE_DIR / path
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── task functions ─────────────────────────────────────────────────────────────
def daily_research(config: dict) -> None:
    """Fetch data, compute signals, generate daily research PDF."""
    log.info("=== DAILY RESEARCH START ===")

    from data_fetching.market_data import get_all_symbols, fetch_price_history, fetch_fundamentals
    from data_fetching.macro_data import fetch_macro_snapshot
    from analytics.technicals import compute_technicals, detect_regime_change
    from signals.buy_sell import generate_all_signals
    from reports.daily_research import generate_daily_research_report

    symbols = get_all_symbols(config)
    log.info("Symbols: %d total", len(symbols))

    log.info("Fetching price history …")
    price_data = fetch_price_history(symbols)

    log.info("Fetching macro snapshot …")
    macro = fetch_macro_snapshot()

    log.info("Fetching fundamentals …")
    fundamentals = fetch_fundamentals(symbols[:30])   # limit to first 30 for speed

    log.info("Computing technicals …")
    all_tech = {}
    regime_changes = []
    for sym, df in price_data.items():
        if df is None or df.empty:
            continue
        try:
            tech = compute_technicals(df)
            all_tech[sym] = tech
            chg = detect_regime_change(df)
            if chg:
                regime_changes.append((sym, chg))
        except Exception as e:
            log.warning("Technicals failed for %s: %s", sym, e)

    log.info("Generating signals …")
    signals = generate_all_signals(all_tech, config)

    now = datetime.now()
    out_dir = BASE_DIR / config["output"]["reports_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / f"research_{now:%Y%m%d_%H%M}.pdf")

    log.info("Writing PDF: %s", out_path)
    generate_daily_research_report(
        output_path=out_path,
        signals=signals,
        macro_data=macro,
        price_data=price_data,
        regime_changes=regime_changes,
        fundamentals=fundamentals,
    )
    log.info("=== DAILY RESEARCH COMPLETE: %s ===", out_path)


def daily_short_monitoring(config: dict) -> None:
    """Fetch short data, score squeeze risk, generate short bulletin PDF."""
    log.info("=== SHORT MONITORING START ===")

    from data_fetching.market_data import get_all_symbols, fetch_price_history
    from data_fetching.short_data import fetch_short_data_batch
    from analytics.technicals import compute_technicals
    from signals.short_risk import score_short_risk, get_high_risk_shorts
    from reports.short_bulletin import generate_short_bulletin

    symbols = get_all_symbols(config)

    log.info("Fetching short data from Finviz (rate-limited) …")
    short_data = fetch_short_data_batch(symbols)

    log.info("Fetching price history for technicals …")
    price_data = fetch_price_history(symbols)

    all_tech = {}
    for sym, df in price_data.items():
        if df is None or df.empty:
            continue
        try:
            all_tech[sym] = compute_technicals(df)
        except Exception:
            pass

    log.info("Scoring short risk …")
    all_risks = []
    for sym in symbols:
        sd = short_data.get(sym, {})
        tech = all_tech.get(sym, {})
        risk = score_short_risk(sym, sd, tech, config)
        all_risks.append(risk)

    all_risks.sort(key=lambda r: r.get("score", 0), reverse=True)

    now = datetime.now()
    out_dir = BASE_DIR / config["output"]["short_reports_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / f"short_bulletin_{now:%Y%m%d_%H%M}.pdf")

    log.info("Writing PDF: %s", out_path)
    generate_short_bulletin(output_path=out_path, short_risks=all_risks)
    log.info("=== SHORT MONITORING COMPLETE: %s ===", out_path)


def daily_portfolio_update(config: dict) -> None:
    """Enrich portfolio, compute KPIs, generate portfolio health PDF."""
    log.info("=== PORTFOLIO UPDATE START ===")

    csv_path = BASE_DIR / config["portfolio"]["csv_path"]
    if not csv_path.exists():
        log.warning("Portfolio CSV not found: %s  — skipping.", csv_path)
        return

    from data_fetching.market_data import fetch_price_history
    from analytics.portfolio import (
        load_portfolio, enrich_portfolio,
        sector_exposure, calculate_portfolio_volatility,
        max_drawdown, check_alerts,
    )
    from reports.portfolio_health import generate_portfolio_health_report

    log.info("Loading portfolio …")
    portfolio = load_portfolio(str(csv_path))

    log.info("Fetching current prices …")
    symbols = portfolio["symbol"].tolist()
    price_history = fetch_price_history(symbols, period="6mo")

    log.info("Enriching portfolio …")
    portfolio = enrich_portfolio(portfolio, price_history)

    sectors = sector_exposure(portfolio)
    vol = calculate_portfolio_volatility(portfolio, price_history)
    mdd = max_drawdown(portfolio, price_history)
    alerts = check_alerts(
        portfolio,
        stop_loss_pct=config["alerts"]["stop_loss_pct"],
        target_pct=config["alerts"]["target_pct"],
    )

    total_value = portfolio["market_value"].sum()
    total_pnl   = portfolio["pnl"].sum()
    total_pnl_pct = (total_pnl / (total_value - total_pnl) * 100
                     if (total_value - total_pnl) != 0 else 0)

    kpis = {
        "total_value":    total_value,
        "total_pnl":      total_pnl,
        "total_pnl_pct":  total_pnl_pct,
        "volatility":     vol,
        "max_drawdown":   mdd,
        "num_positions":  len(portfolio),
    }

    now = datetime.now()
    out_dir = BASE_DIR / config["output"]["reports_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / f"portfolio_{now:%Y%m%d_%H%M}.pdf")

    log.info("Writing PDF: %s", out_path)
    generate_portfolio_health_report(
        output_path=out_path,
        portfolio_df=portfolio,
        kpis=kpis,
        sector_data=sectors,
        price_history=price_history,
        alerts=alerts,
    )

    if alerts:
        log.warning("PORTFOLIO ALERTS: %d triggered", len(alerts))
        for a in alerts:
            log.warning("  [%s] %s — %s", a.get("type"), a.get("symbol"), a.get("message"))

    log.info("=== PORTFOLIO UPDATE COMPLETE: %s ===", out_path)


def send_daily_alerts(config: dict) -> None:
    """Check intraday moves and send email alert if thresholds breached."""
    log.info("=== EMAIL ALERTS START ===")

    from data_fetching.market_data import get_all_symbols, fetch_price_history
    from alerts.email_alert import check_intraday_moves, send_email_alert

    symbols = get_all_symbols(config)
    price_data = fetch_price_history(symbols, period="5d")

    alert_items = check_intraday_moves(price_data, config)

    if not alert_items:
        log.info("No intraday moves exceed threshold — no email sent.")
    else:
        chart_symbols = [a["symbol"] for a in alert_items[:5]]
        subject = f"AutoTrader Alert — {len(alert_items)} moves detected {datetime.now():%Y-%m-%d}"
        try:
            send_email_alert(config, subject, alert_items, chart_symbols)
            log.info("Alert email sent: %d items", len(alert_items))
        except Exception as e:
            log.error("Failed to send email: %s", e)

    log.info("=== EMAIL ALERTS COMPLETE ===")


def run_all(config: dict) -> None:
    """Run all daily tasks in sequence."""
    tasks = [
        ("daily_research",        daily_research),
        ("daily_short_monitoring", daily_short_monitoring),
        ("daily_portfolio_update", daily_portfolio_update),
        ("send_daily_alerts",      send_daily_alerts),
    ]
    for name, fn in tasks:
        try:
            fn(config)
        except Exception:
            log.error("Task [%s] failed:\n%s", name, traceback.format_exc())


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoTrader daily runner")
    parser.add_argument(
        "task",
        nargs="?",
        default="all",
        choices=["all","daily_research","short_monitoring","portfolio","alerts"],
        help="Which task to run (default: all)",
    )
    args = parser.parse_args()

    cfg = load_config()

    task_map = {
        "all":               run_all,
        "daily_research":    daily_research,
        "short_monitoring":  daily_short_monitoring,
        "portfolio":         daily_portfolio_update,
        "alerts":            send_daily_alerts,
    }
    task_map[args.task](cfg)
