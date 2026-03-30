"""Portfolio health PDF report generator."""
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

# Palette for sector pie
SECTOR_COLORS = [
    "#22d3ee","#4ade80","#facc15","#fb923c","#f87171",
    "#c084fc","#60a5fa","#34d399","#f472b6","#a78bfa",
]


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
    kpi_s = ParagraphStyle("KPI", parent=base["Normal"],
        textColor=WHITE, fontSize=10, leading=16)
    return title_s, sub_s, section_s, kpi_s


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


def _sector_pie(sector_data):
    """Sector exposure pie chart."""
    labels = list(sector_data.keys())
    values = [abs(v) for v in sector_data.values()]
    if not values or sum(values) == 0:
        return None
    fig, ax = plt.subplots(figsize=(6, 4))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")
    clrs = SECTOR_COLORS[:len(labels)]
    wedges, texts, autotexts = ax.pie(
        values, labels=None, colors=clrs,
        autopct="%1.1f%%", pctdistance=0.82,
        wedgeprops=dict(width=0.5, edgecolor="#1a1a2e", linewidth=1.5),
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontsize(7)
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5),
              facecolor="#16213e", edgecolor="#0f3460",
              labelcolor="white", fontsize=8)
    ax.set_title("Sector Exposure", color="white", fontsize=11, pad=10)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _pnl_chart(portfolio_df):
    """Bar chart of P&L per position."""
    try:
        syms = portfolio_df["symbol"].tolist()
        pnls = portfolio_df["pnl_pct"].tolist()
    except Exception:
        return None
    if not syms:
        return None
    clrs = ["#4ade80" if p >= 0 else "#f87171" for p in pnls]
    fig, ax = plt.subplots(figsize=(8, 3))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    x = np.arange(len(syms))
    ax.bar(x, pnls, color=clrs, width=0.6, edgecolor="#0f3460", linewidth=0.5)
    ax.axhline(0, color="#94a3b8", linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(syms, rotation=30, ha="right", color="white", fontsize=8)
    ax.set_ylabel("P&L %", color="#94a3b8", fontsize=8)
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_edgecolor("#0f3460")
    ax.set_title("Position P&L %", color="white", fontsize=10, pad=8)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_portfolio_health_report(
    output_path, portfolio_df, kpis, sector_data, price_history, alerts
):
    """
    Generate portfolio health PDF.

    Parameters
    ----------
    output_path   : full path for output PDF
    portfolio_df  : enriched DataFrame from analytics.portfolio.enrich_portfolio()
    kpis          : dict with keys: total_value, total_pnl, total_pnl_pct,
                    volatility, max_drawdown, num_positions
    sector_data   : dict {sector: market_value} from analytics.portfolio.sector_exposure()
    price_history : dict {symbol: DataFrame} for charts
    alerts        : list of dicts from analytics.portfolio.check_alerts()
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title="Portfolio Health Report")
    title_s, sub_s, section_s, kpi_s = _styles()
    story = []

    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")
    story.append(Paragraph("Portfolio Health Report", title_s))
    story.append(Paragraph(now_str, sub_s))
    story.append(HRFlowable(width="100%", color=ACCENT, thickness=1))
    story.append(Spacer(1, 0.4*cm))

    # KPI table
    story.append(Paragraph("Key Performance Indicators", section_s))
    tv   = kpis.get("total_value", 0) or 0
    tp   = kpis.get("total_pnl", 0) or 0
    tp_p = kpis.get("total_pnl_pct", 0) or 0
    vol  = kpis.get("volatility", 0) or 0
    mdd  = kpis.get("max_drawdown", 0) or 0
    npos = kpis.get("num_positions", 0) or 0

    kpi_rows = [
        ["Total Value",    f"${tv:,.2f}"],
        ["Total P&L",      f"${tp:,.2f}  ({tp_p:+.2f}%)"],
        ["Annl. Volatility",f"{vol:.2f}%"],
        ["Max Drawdown",   f"{mdd:.2f}%"],
        ["Positions",      str(npos)],
    ]
    kpi_tbl = Table(kpi_rows, colWidths=[6*cm, 8*cm])
    ktps = TableStyle([
        ("BACKGROUND", (0,0),( 0,-1), ACCENT),
        ("BACKGROUND", (1,0),( 1,-1), PANEL),
        ("TEXTCOLOR",  (0,0),(-1,-1), WHITE),
        ("FONTNAME",   (0,0),( 0,-1), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0),(-1,-1), 10),
        ("GRID",       (0,0),(-1,-1), 0.3, GREY),
        ("ALIGN",      (0,0),(-1,-1), "LEFT"),
        ("TOPPADDING", (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("LEFTPADDING",(0,0),(-1,-1), 8),
    ])
    pnl_color = GREEN if tp >= 0 else RED
    ktps.add("TEXTCOLOR",(1,1),(1,1),pnl_color)
    ktps.add("FONTNAME", (1,1),(1,1),"Helvetica-Bold")
    kpi_tbl.setStyle(ktps)
    story.append(kpi_tbl)
    story.append(Spacer(1, 0.4*cm))

    # Alerts
    if alerts:
        story.append(Paragraph("Active Alerts", section_s))
        al_rows = [["Symbol","Type","Message"]]
        for al in alerts:
            al_rows.append([
                al.get("symbol",""),
                al.get("type",""),
                al.get("message","")[:60],
            ])
        al_tbl = Table(al_rows, colWidths=[2.5*cm,3*cm,11*cm])
        alts = _tbl_style(RED)
        alts.add("TEXTCOLOR",(0,0),(-1,0),WHITE)
        al_tbl.setStyle(alts)
        story.append(al_tbl)
        story.append(Spacer(1, 0.4*cm))

    # P&L bar chart
    try:
        pnl_bytes = _pnl_chart(portfolio_df)
        if pnl_bytes:
            story.append(RLImage(io.BytesIO(pnl_bytes), width=15*cm, height=5*cm))
            story.append(Spacer(1, 0.3*cm))
    except Exception:
        pass

    # Sector pie
    if sector_data:
        story.append(Paragraph("Sector Exposure", section_s))
        try:
            pie_bytes = _sector_pie(sector_data)
            if pie_bytes:
                story.append(RLImage(io.BytesIO(pie_bytes), width=12*cm, height=8*cm))
        except Exception:
            pass

        sec_rows = [["Sector","Market Value","Weight%"]]
        total_mv = sum(abs(v) for v in sector_data.values()) or 1
        for sec, mv in sorted(sector_data.items(), key=lambda x: abs(x[1]), reverse=True):
            sec_rows.append([
                sec,
                f"${mv:,.0f}",
                f"{abs(mv)/total_mv*100:.1f}%",
            ])
        sec_tbl = Table(sec_rows, colWidths=[6*cm, 5*cm, 5*cm])
        sec_tbl.setStyle(_tbl_style())
        story.append(sec_tbl)

    # Positions table
    story.append(PageBreak())
    story.append(Paragraph("Position Detail", section_s))
    pos_rows = [["Symbol","Entry","Current","Shares","P&L$","P&L%","Short","Sector"]]
    try:
        for _, row in portfolio_df.iterrows():
            is_short = bool(row.get("short_position", False))
            pnl_val  = row.get("pnl", 0) or 0
            pnl_pct  = row.get("pnl_pct", 0) or 0
            pos_rows.append([
                str(row.get("symbol","")),
                f"{row.get('entry_price',0):.2f}",
                f"{row.get('current_price',0):.2f}",
                str(row.get("shares","")),
                f"${pnl_val:,.2f}",
                f"{pnl_pct:+.2f}%",
                "SHORT" if is_short else "LONG",
                str(row.get("sector",""))[:12],
            ])
    except Exception as e:
        pos_rows.append([str(e),"","","","","","",""])
    pos_tbl = Table(pos_rows,
        colWidths=[2.5*cm,2*cm,2*cm,1.5*cm,2.5*cm,2*cm,2*cm,2.5*cm])
    pts = _tbl_style()
    for i in range(1, len(pos_rows)):
        try:
            pct_str = pos_rows[i][5]
            pct_val = float(pct_str.replace("%","").replace("+",""))
            c = GREEN if pct_val >= 0 else RED
        except Exception:
            c = WHITE
        pts.add("TEXTCOLOR",(4,i),(5,i),c)
    pos_tbl.setStyle(pts)
    story.append(pos_tbl)

    doc.build(story)
    return output_path
