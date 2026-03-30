"""Email alert system via Gmail SMTP with embedded price charts."""
import smtplib
import logging
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf

logger = logging.getLogger(__name__)


def generate_price_chart(symbol: str, period: str = "3mo") -> Optional[bytes]:
    """Generate a dark-themed price chart and return PNG bytes."""
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty:
            return None

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6),
                                        gridspec_kw={"height_ratios": [3, 1]})
        fig.patch.set_facecolor("#1a1a2e")
        for ax in (ax1, ax2):
            ax.set_facecolor("#16213e")
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_color("#444")

        ax1.plot(hist.index, hist["Close"], color="#00d4ff", linewidth=1.5, label="Price")
        if len(hist) >= 20:
            ax1.plot(hist.index, hist["Close"].rolling(20).mean(),
                     color="#ffd700", linewidth=1, linestyle="--", label="MA20")
        if len(hist) >= 50:
            ax1.plot(hist.index, hist["Close"].rolling(50).mean(),
                     color="#ff6b6b", linewidth=1, linestyle="--", label="MA50")

        ax1.set_title(f"{symbol} â€“ {period}", color="white", fontsize=12)
        ax1.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=8)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

        colors = ["#26a69a" if c >= o else "#ef5350"
                  for c, o in zip(hist["Close"], hist["Open"])]
        ax2.bar(hist.index, hist["Volume"], color=colors, alpha=0.8)
        ax2.set_ylabel("Volume", color="white", fontsize=8)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.error(f"Chart error for {symbol}: {e}")
        return None


def send_email_alert(config: dict, subject: str, alerts: List[dict],
                     chart_symbols: Optional[List[str]] = None) -> bool:
    """Send HTML alert email with optional embedded charts."""
    ecfg = config.get("alerts", {}).get("email", {})
    smtp_server = ecfg.get("smtp_server", "smtp.gmail.com")
    smtp_port   = ecfg.get("smtp_port", 587)
    sender      = ecfg.get("sender")
    recipient   = ecfg.get("recipient")
    app_password = ecfg.get("app_password", "")

    if not all([sender, recipient, app_password]) or app_password == "YOUR_GMAIL_APP_PASSWORD":
        logger.error("Email not configured. Set app_password in config.yaml")
        return False

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    type_colors = {
        "BUY": "#00c853", "SELL": "#d50000",
        "STOP_LOSS": "#ff6d00", "TARGET": "#00bfa5", "SHORT_RISK": "#aa00ff",
    }

    rows_html = ""
    for a in alerts:
        c = type_colors.get(a.get("type", ""), "#888888")
        rows_html += (
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #333;color:{c};font-weight:bold'>"
            f"{a.get('type','â€”')}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #333'>{a.get('symbol','â€”')}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #333'>{a.get('message','')}</td>"
            f"</tr>"
        )

    chart_imgs_html = ""
    chart_data = {}
    if chart_symbols:
        for i, sym in enumerate(chart_symbols[:3]):
            img_bytes = generate_price_chart(sym)
            if img_bytes:
                cid = f"chart_{i}"
                chart_data[cid] = img_bytes
                chart_imgs_html += (
                    f"<div style='margin-top:20px'>"
                    f"<h3 style='color:#00d4ff'>{sym}</h3>"
                    f"<img src='cid:{cid}' style='max-width:100%;border-radius:8px'>"
                    f"</div>"
                )

    html = f"""
<html><body style='background:#0f0f1a;color:#e0e0e0;font-family:Arial,sans-serif;padding:20px'>
  <h2 style='color:#00d4ff'>AutoTrader Alert</h2>
  <p style='color:#888'>{today}</p>
  <table style='width:100%;border-collapse:collapse;background:#1a1a2e;border-radius:8px'>
    <thead>
      <tr style='background:#0d47a1'>
        <th style='padding:10px;text-align:left;color:white'>Type</th>
        <th style='padding:10px;text-align:left;color:white'>Symbol</th>
        <th style='padding:10px;text-align:left;color:white'>Details</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  {chart_imgs_html}
  <p style='margin-top:30px;color:#555;font-size:11px'>
    AutoTrader Research System &middot; Self-use only &middot; Not financial advice
  </p>
</body></html>"""

    msg.attach(MIMEText(html, "html"))
    for cid, img_bytes in chart_data.items():
        img = MIMEImage(img_bytes, _subtype="png")
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline")
        msg.attach(img)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, app_password)
            server.sendmail(sender, recipient, msg.as_string())
        logger.info(f"Email sent: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail auth failed. Check App Password in config.yaml.")
        return False
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False


def check_intraday_moves(price_data: dict, config: dict) -> List[dict]:
    """Detect symbols with significant intraday price moves."""
    threshold = config.get("alerts", {}).get("price_move_threshold", 3.0)
    alerts = []
    for symbol, df in price_data.items():
        if df.empty or len(df) < 2:
            continue
        chg = float((df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100)
        if abs(chg) >= threshold:
            alerts.append({
                "symbol": symbol,
                "type": "BUY" if chg > 0 else "SELL",
                "message": f"Intraday move: {chg:+.2f}%",
            })
    return alerts