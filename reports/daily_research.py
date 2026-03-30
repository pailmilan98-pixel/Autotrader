"""Daily research PDF report generator."""
import io
import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image as RLImage, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER

BG    = colors.HexColor("#1a1a2e")
PANEL = colors.HexColor("#16213e")
ACCENT= colors.HexColor("#0f3460")
GREEN = colors.HexColor("#4ade80")
RED   = colors.HexColor("#f87171")
YELLOW= colors.HexColor("#facc15")
CYAN  = colors.HexColor("#22d3ee")
WHITE = colors.white
GREY  = colors.HexColor("#94a3b8")

SIGNAL_COLORS = {
    "BUY":       GREEN,
    "WEAK_BUY":  colors.HexColor("#86efac"),
    "HOLD":      YELLOW,
    "WEAK_SELL": colors.HexColor("#fca5a5"),
    "SELL":      RED,
}


def _styles():
    base = getSampleStyleSheet()
    title_s = ParagraphStyle("RT", parent=base["Title"],
        textColor=WHITE, fontSize=20, spaceAfter=4,
        alignment=TA_CENTER, fontName="Helvetica-Bold")
    sub_s = ParagraphStyle("Sub", parent=base["Normal"],
        textColor=GREY, fontSize=10, alignment=TA_CENTER, spaceAfter=12)
    section_s = ParagraphStyle("Sec", parent=base["Heading2"],
        textColor=CYAN, fontSize=13, spaceBefore=14,
        spaceAfter=6, fontName="Helvetica-Bold")
    body_s = ParagraphStyle("Body", parent=base["Normal"],
        textColor=WHITE, fontSize=9, leading=13)
    return title_s, sub_s, section_s, body_s


def _tbl_style(hdr=ACCENT):
    return TableStyle([
        ("BACKGROUND",    (0,0),(-1, 0), hdr),
        ("TEXTCOLOR",     (0,0),(-1, 0), WHITE),
        ("FONTNAME",      (0,0),(-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1, 0), 9),
        ("BACKGROUND",    (0,1),(-1,-1), PANEL),
        ("TEXTCOLOR",     (0,1),(-1,-1), WHITE),
        ("FONTSIZE",      (0,1),(-1,-1), 8),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [PANEL, BG]),
        ("GRID",          (0,0),(-1,-1), 0.3, GREY),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ])


def _macro_bar_chart(macro_data):
    labels, values, bar_colors = [], [], []
    for name, info in macro_data.items():
        if name == "regime":
            continue
        chg = info.get("change_1d_pct", 0) or 0
        labels.append(name)
        values.append(chg)
        bar_colors.append("#4ade80" if chg >= 0 else "#f87171")
    fig, ax = plt.subplots(figsize=(8, 3))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    x = np.arange(len(labels))
    ax.bar(x, values, color=bar_colors, width=0.6, edgecolor="#0f3460", linewidth=0.5)
    ax.axhline(0, color="#94a3b8", linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", color="white", fontsize=8)
    ax.set_ylabel("1-Day %", color="#94a3b8", fontsize=8)
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_edgecolor("#0f3460")
    ax.set_title("Macro Snapshot - 1-Day Change", color="white", fontsize=10, pad=8)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_daily_research_report(output_path, signals, macro_data,
                                   price_data, regime_changes, fundamentals):
    """Generate daily research PDF."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title="Daily Research Report")
    title_s, sub_s, section_s, body_s = _styles()
    story = []

    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")
    story.append(Paragraph("Daily Research Report", title_s))
    story.append(Paragraph(now_str, sub_s))
    story.append(HRFlowable(width="100%", color=ACCENT, thickness=1))
    story.append(Spacer(1, 0.4*cm))

    # Macro table
    story.append(Paragraph("Macro Snapshot", section_s))
    macro_rows = [["Asset", "Price", "1D%", "5D%", "20D%"]]
    regime_str = ""
    for name, info in macro_data.items():
        if name == "regime":
            regime_str = info
            continue
        p   = info.get("price", 0) or 0
        d1  = info.get("change_1d_pct", 0) or 0
        d5  = info.get("change_5d_pct", 0) or 0
        d20 = info.get("change_20d_pct", 0) or 0
        macro_rows.append([
            name,
            f"{p:,.2f}",
            f"{d1:+.2f}%",
            f"{d5:+.2f}%",
            f"{d20:+.2f}%",
        ])
    mt = Table(macro_rows, colWidths=[3*cm, 2.5*cm, 2*cm, 2*cm, 2*cm])
    mts = _tbl_style()
    for i, row in enumerate(macro_rows[1:], 1):
        try:
            c = GREEN if float(row[2].replace("%","").replace("+","")) >= 0 else RED
        except Exception:
            c = WHITE
        mts.add("TEXTCOLOR", (2, i), (2, i), c)
    mt.setStyle(mts)
    story.append(mt)
    story.append(Spacer(1, 0.3*cm))

    try:
        chart_bytes = _macro_bar_chart(macro_data)
        story.append(RLImage(io.BytesIO(chart_bytes), width=15*cm, height=5*cm))
    except Exception:
        pass

    if regime_str:
        story.append(Spacer(1, 0.2*cm))
        c = GREEN if "RISK_ON" in regime_str else (RED if "RISK_OFF" in regime_str else YELLOW)
        story.append(Paragraph(f"Market Regime: {regime_str}",
            ParagraphStyle("Reg", textColor=c, fontSize=10, fontName="Helvetica-Bold")))

    # Regime changes
    if regime_changes:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph("Regime Changes Detected", section_s))
        rc_rows = [["Symbol", "Change"]]
        for sym, chg in regime_changes:
            rc_rows.append([sym, chg])
        rct = Table(rc_rows, colWidths=[4*cm, 12*cm])
        rct.setStyle(_tbl_style())
        story.append(rct)

    # Buy candidates
    story.append(PageBreak())
    story.append(Paragraph("Buy Candidates", section_s))
    buy_sigs = [s for s in signals if s.get("signal") in ("BUY", "WEAK_BUY")]
    if buy_sigs:
        buy_rows = [["Symbol","Signal","Score","RSI","MA Trend","Reasons"]]
        for s in buy_sigs:
            tech = s.get("technicals", {})
            buy_rows.append([
                s["symbol"], s["signal"], str(s.get("score","")),
                f"{tech.get('rsi',0):.1f}" if tech.get("rsi") else "—",
                tech.get("ma_trend","—"),
                "; ".join(s.get("reasons",[]))[:60],
            ])
        bt = Table(buy_rows, colWidths=[2.5*cm,2.5*cm,1.5*cm,1.5*cm,2.5*cm,7*cm])
        bts = _tbl_style(GREEN)
        bts.add("TEXTCOLOR",(0,0),(-1,0),BG)
        bt.setStyle(bts)
        story.append(bt)
    else:
        story.append(Paragraph("No buy candidates today.", body_s))

    story.append(Spacer(1, 0.6*cm))

    # Sell candidates
    story.append(Paragraph("Sell Candidates", section_s))
    sell_sigs = [s for s in signals if s.get("signal") in ("SELL","WEAK_SELL")]
    if sell_sigs:
        sell_rows = [["Symbol","Signal","Score","RSI","MA Trend","Reasons"]]
        for s in sell_sigs:
            tech = s.get("technicals", {})
            sell_rows.append([
                s["symbol"], s["signal"], str(s.get("score","")),
                f"{tech.get('rsi',0):.1f}" if tech.get("rsi") else "—",
                tech.get("ma_trend","—"),
                "; ".join(s.get("reasons",[]))[:60],
            ])
        st2 = Table(sell_rows, colWidths=[2.5*cm,2.5*cm,1.5*cm,1.5*cm,2.5*cm,7*cm])
        sts2 = _tbl_style(RED)
        st2.setStyle(sts2)
        story.append(st2)
    else:
        story.append(Paragraph("No sell candidates today.", body_s))

    # Full signal table
    story.append(PageBreak())
    story.append(Paragraph("Full Signal Table", section_s))
    full_rows = [["Symbol","Signal","Score","RSI","SMA20","SMA50","VolRatio","Slope"]]
    for s in signals:
        tech = s.get("technicals", {})
        full_rows.append([
            s["symbol"], s.get("signal",""), str(s.get("score","")),
            f"{tech.get('rsi',0):.1f}" if tech.get("rsi") is not None else "—",
            f"{tech.get('sma20',0):.2f}" if tech.get("sma20") else "—",
            f"{tech.get('sma50',0):.2f}" if tech.get("sma50") else "—",
            f"{tech.get('volume_ratio',0):.2f}" if tech.get("volume_ratio") else "—",
            f"{tech.get('slope',0):.4f}" if tech.get("slope") is not None else "—",
        ])
    ft = Table(full_rows, colWidths=[2.5*cm,2.5*cm,1.5*cm,1.5*cm,2*cm,2*cm,2.5*cm,2.5*cm])
    fts = _tbl_style()
    for i, s in enumerate(signals, 1):
        c = SIGNAL_COLORS.get(s.get("signal","HOLD"), WHITE)
        fts.add("TEXTCOLOR",(1,i),(1,i),c)
    ft.setStyle(fts)
    story.append(ft)

    # Fundamentals
    if fundamentals:
        story.append(PageBreak())
        story.append(Paragraph("Fundamentals", section_s))
        fund_rows = [["Symbol","P/E","Mkt Cap(B)","Beta","Float","Sector"]]
        for sym, fd in fundamentals.items():
            pe  = fd.get("pe_ratio","—")
            mc  = fd.get("market_cap","—")
            bt2 = fd.get("beta","—")
            fl  = fd.get("float_shares","—")
            sec = fd.get("sector","—")
            try:    mc_str = f"{float(mc)/1e9:.1f}" if mc and mc != "—" else "—"
            except: mc_str = "—"
            try:    fl_str = f"{float(fl)/1e6:.1f}M" if fl and fl != "—" else "—"
            except: fl_str = "—"
            fund_rows.append([
                sym,
                f"{pe:.1f}" if isinstance(pe,(int,float)) else str(pe),
                mc_str,
                f"{bt2:.2f}" if isinstance(bt2,(int,float)) else str(bt2),
                fl_str,
                str(sec)[:20],
            ])
        fund_tbl = Table(fund_rows, colWidths=[2.5*cm,2*cm,3*cm,2*cm,2.5*cm,5*cm])
        fund_tbl.setStyle(_tbl_style())
        story.append(fund_tbl)

    doc.build(story)
    return output_path
