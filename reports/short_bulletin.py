"""Short risk bulletin PDF generator."""
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
    PageBreak, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER

BG    = colors.HexColor("#1a1a2e")
PANEL = colors.HexColor("#16213e")
ACCENT= colors.HexColor("#0f3460")
GREEN = colors.HexColor("#4ade80")
RED   = colors.HexColor("#f87171")
YELLOW= colors.HexColor("#facc15")
ORANGE= colors.HexColor("#fb923c")
CYAN  = colors.HexColor("#22d3ee")
WHITE = colors.white
GREY  = colors.HexColor("#94a3b8")

RISK_COLORS = {
    "EXTREME": RED,
    "HIGH":    ORANGE,
    "MEDIUM":  YELLOW,
    "LOW":     GREEN,
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


def _risk_bar_chart(risk_items):
    """Bar chart of short interest % for high/extreme risk items."""
    if not risk_items:
        return None
    syms = [r["symbol"] for r in risk_items[:20]]
    vals = [r.get("short_float", 0) or 0 for r in risk_items[:20]]
    risk_lvls = [r.get("risk_level","LOW") for r in risk_items[:20]]
    bar_colors_map = {"EXTREME":"#f87171","HIGH":"#fb923c","MEDIUM":"#facc15","LOW":"#4ade80"}
    bar_clrs = [bar_colors_map.get(l,"#94a3b8") for l in risk_lvls]

    fig, ax = plt.subplots(figsize=(8, 3))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    x = np.arange(len(syms))
    ax.bar(x, vals, color=bar_clrs, width=0.6, edgecolor="#0f3460", linewidth=0.5)
    ax.axhline(10, color="#facc15", linewidth=0.8, linestyle="--", label="10% threshold")
    ax.set_xticks(x)
    ax.set_xticklabels(syms, rotation=30, ha="right", color="white", fontsize=8)
    ax.set_ylabel("Short Float %", color="#94a3b8", fontsize=8)
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_edgecolor("#0f3460")
    ax.legend(facecolor="#16213e", edgecolor="#0f3460",
              labelcolor="white", fontsize=8)
    ax.set_title("Short Interest by Symbol", color="white", fontsize=10, pad=8)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_short_bulletin(output_path, short_risks):
    """
    Generate short risk bulletin PDF.

    Parameters
    ----------
    output_path : full path for output PDF
    short_risks : list of dicts from signals.short_risk.score_short_risk()
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title="Short Risk Bulletin")
    title_s, sub_s, section_s, body_s = _styles()
    story = []

    from reportlab.platypus import Image as RLImage

    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")
    story.append(Paragraph("Short Risk Bulletin", title_s))
    story.append(Paragraph(now_str, sub_s))
    story.append(HRFlowable(width="100%", color=RED, thickness=1))
    story.append(Spacer(1, 0.4*cm))

    # Summary counts
    counts = {"EXTREME":0,"HIGH":0,"MEDIUM":0,"LOW":0}
    for r in short_risks:
        lvl = r.get("risk_level","LOW")
        counts[lvl] = counts.get(lvl,0) + 1

    sum_rows = [["Risk Level","Count"]]
    for lvl, cnt in counts.items():
        sum_rows.append([lvl, str(cnt)])
    sum_tbl = Table(sum_rows, colWidths=[6*cm, 4*cm])
    sts = _tbl_style()
    for i, (lvl,_) in enumerate(list(counts.items()), 1):
        c = RISK_COLORS.get(lvl, WHITE)
        sts.add("TEXTCOLOR",(0,i),(0,i),c)
        sts.add("FONTNAME",(0,i),(0,i),"Helvetica-Bold")
    sum_tbl.setStyle(sts)
    story.append(sum_tbl)
    story.append(Spacer(1, 0.4*cm))

    # Bar chart
    high_risk = [r for r in short_risks if r.get("risk_level") in ("EXTREME","HIGH","MEDIUM")]
    if high_risk:
        try:
            chart_bytes = _risk_bar_chart(high_risk)
            if chart_bytes:
                story.append(RLImage(io.BytesIO(chart_bytes), width=15*cm, height=5*cm))
                story.append(Spacer(1, 0.3*cm))
        except Exception:
            pass

    # EXTREME risk section
    extreme = [r for r in short_risks if r.get("risk_level") == "EXTREME"]
    if extreme:
        story.append(Paragraph("EXTREME Short Squeeze Risk", section_s))
        ex_rows = [["Symbol","Short%","S.Ratio","RelVol","Score","Signals"]]
        for r in extreme:
            ex_rows.append([
                r["symbol"],
                f"{r.get('short_float',0):.1f}%" if r.get("short_float") else "—",
                f"{r.get('short_ratio',0):.1f}" if r.get("short_ratio") else "—",
                f"{r.get('rel_volume',0):.2f}" if r.get("rel_volume") else "—",
                str(r.get("score","")),
                "; ".join(r.get("signals",[]))[:50],
            ])
        ext_tbl = Table(ex_rows, colWidths=[2.5*cm,2*cm,2*cm,2*cm,1.5*cm,7*cm])
        ets = _tbl_style(RED)
        ets.add("TEXTCOLOR",(0,0),(-1,0),WHITE)
        ext_tbl.setStyle(ets)
        story.append(ext_tbl)
        story.append(Spacer(1, 0.4*cm))

    # HIGH risk section
    high_only = [r for r in short_risks if r.get("risk_level") == "HIGH"]
    if high_only:
        story.append(Paragraph("HIGH Short Squeeze Risk", section_s))
        h_rows = [["Symbol","Short%","S.Ratio","RelVol","Score","Signals"]]
        for r in high_only:
            h_rows.append([
                r["symbol"],
                f"{r.get('short_float',0):.1f}%" if r.get("short_float") else "—",
                f"{r.get('short_ratio',0):.1f}" if r.get("short_ratio") else "—",
                f"{r.get('rel_volume',0):.2f}" if r.get("rel_volume") else "—",
                str(r.get("score","")),
                "; ".join(r.get("signals",[]))[:50],
            ])
        ht = Table(h_rows, colWidths=[2.5*cm,2*cm,2*cm,2*cm,1.5*cm,7*cm])
        hts = _tbl_style(ORANGE)
        hts.add("TEXTCOLOR",(0,0),(-1,0),BG)
        ht.setStyle(hts)
        story.append(ht)
        story.append(Spacer(1, 0.4*cm))

    # Full table
    story.append(PageBreak())
    story.append(Paragraph("Full Short Risk Table", section_s))
    all_rows = [["Symbol","Risk Level","Short%","S.Ratio","RelVol","RSI","Score"]]
    for r in short_risks:
        all_rows.append([
            r["symbol"],
            r.get("risk_level","LOW"),
            f"{r.get('short_float',0):.1f}%" if r.get("short_float") else "—",
            f"{r.get('short_ratio',0):.1f}" if r.get("short_ratio") else "—",
            f"{r.get('rel_volume',0):.2f}" if r.get("rel_volume") else "—",
            f"{r.get('rsi',0):.1f}" if r.get("rsi") else "—",
            str(r.get("score","")),
        ])
    at = Table(all_rows, colWidths=[2.5*cm,2.5*cm,2*cm,2*cm,2*cm,2*cm,2*cm])
    ats = _tbl_style()
    for i, r in enumerate(short_risks, 1):
        c = RISK_COLORS.get(r.get("risk_level","LOW"), WHITE)
        ats.add("TEXTCOLOR",(1,i),(1,i),c)
        ats.add("FONTNAME",(1,i),(1,i),"Helvetica-Bold")
    at.setStyle(ats)
    story.append(at)

    doc.build(story)
    return output_path
