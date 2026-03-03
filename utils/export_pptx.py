"""PowerPoint report generation — Objectif Lune Command Center.

Generates a clean, branded PPTX with KPI cards, tables, charts,
and auto-generated takeaways.  Every slide is built on a blank layout
with manually positioned shapes for full visual control.
"""

import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import plotly.graph_objects as go
import tempfile
import os

from utils.calculations import (
    calculate_baselines,
    aggregate_by_period,
    aggregate_for_date,
    format_currency,
    format_number,
    format_pct,
)
from utils.constants import COLORS, PLATFORM_COLORS, ROAS_TARGETS, load_settings


# ── Theme colours (RGBColor) ────────────────────────────────────
DARK_BLUE = RGBColor(0x2D, 0x3E, 0x50)
PRIMARY_BLUE = RGBColor(0x4A, 0x6F, 0xA5)
GREEN = RGBColor(0x6B, 0x8F, 0x71)
RED = RGBColor(0xC4, 0x5C, 0x4A)
ORANGE = RGBColor(0xC7, 0x8B, 0x52)
GRAY = RGBColor(0x7A, 0x7A, 0x72)
WARM_WHITE = RGBColor(0xFA, 0xFA, 0xF7)
CREAM = RGBColor(0xF5, 0xF0, 0xE8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


# ── Slide dimensions ────────────────────────────────────────────
SLIDE_W = Inches(10)
SLIDE_H = Inches(7.5)


# =====================================================================
#  Low-level drawing helpers
# =====================================================================

def _set_cell_border(cell, color=RGBColor(0xE0, 0xDC, 0xD5), width=Pt(0.5)):
    """Apply a thin border to all four sides of a table cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for edge in ("lnL", "lnR", "lnT", "lnB"):
        from lxml import etree
        ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        ln = etree.SubElement(tcPr, f"{{{ns}}}{edge}")
        ln.set("w", str(int(width)))
        solidFill = etree.SubElement(ln, f"{{{ns}}}solidFill")
        srgbClr = etree.SubElement(solidFill, f"{{{ns}}}srgbClr")
        srgbClr.set("val", f"{color[0]:02X}{color[1]:02X}{color[2]:02X}"
                     if isinstance(color, tuple)
                     else f"{color.red:02X}{color.green:02X}{color.blue:02X}" if hasattr(color, 'red')
                     else "E0DCD5")


def _add_textbox(slide, left, top, width, height, text,
                 font_size=Pt(11), font_color=GRAY, bold=False,
                 alignment=PP_ALIGN.LEFT, word_wrap=True):
    """Shorthand: add a positioned text box and return its text frame."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = word_wrap
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = font_size
    p.font.color.rgb = font_color
    p.font.bold = bold
    p.alignment = alignment
    return tf


def _add_slide_title(slide, text, left=Inches(0.6), top=Inches(0.35)):
    """Place a slide title (24 pt, dark blue, bold)."""
    _add_textbox(
        slide, left, top, Inches(8.8), Inches(0.55),
        text, font_size=Pt(24), font_color=DARK_BLUE, bold=True,
    )


def _add_thin_rule(slide, top):
    """Draw a subtle horizontal line across the slide."""
    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.6), top, Inches(8.8), Pt(1.5),
    )
    line.fill.solid()
    line.fill.fore_color.rgb = CREAM
    line.line.fill.background()


def _draw_kpi_box(slide, left, top, width, height, label, value,
                  delta=None, value_color=DARK_BLUE):
    """Draw a single KPI card (cream rounded rectangle)."""
    box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        left, top, width, height,
    )
    box.fill.solid()
    box.fill.fore_color.rgb = CREAM
    box.line.fill.background()
    # Reduce corner rounding
    box.adjustments[0] = 0.08

    tf = box.text_frame
    tf.word_wrap = True
    tf.paragraphs[0].space_before = Pt(4)

    # Label
    p_label = tf.paragraphs[0]
    p_label.text = label
    p_label.font.size = Pt(9)
    p_label.font.color.rgb = GRAY
    p_label.alignment = PP_ALIGN.CENTER

    # Value
    p_val = tf.add_paragraph()
    p_val.text = str(value)
    p_val.font.size = Pt(20)
    p_val.font.bold = True
    p_val.font.color.rgb = value_color
    p_val.alignment = PP_ALIGN.CENTER
    p_val.space_before = Pt(2)

    # Delta (optional)
    if delta is not None and delta != "":
        p_delta = tf.add_paragraph()
        p_delta.text = str(delta)
        p_delta.font.size = Pt(9)
        is_positive = str(delta).startswith("+")
        p_delta.font.color.rgb = GREEN if is_positive else RED
        p_delta.alignment = PP_ALIGN.CENTER
        p_delta.space_before = Pt(1)


def _draw_kpi_row(slide, kpis, top=Inches(1.25), card_h=Inches(1.15)):
    """Draw a horizontal row of KPI cards, centred on the slide."""
    n = len(kpis)
    card_w = Inches(2.05)
    gap = Inches(0.25)
    total_w = n * Inches(2.05) + (n - 1) * Inches(0.25)
    start_left = (SLIDE_W - total_w) // 2

    for i, kpi in enumerate(kpis):
        left = start_left + i * (card_w + gap)
        _draw_kpi_box(
            slide, left, top, card_w, card_h,
            label=kpi["label"],
            value=kpi["value"],
            delta=kpi.get("delta"),
            value_color=kpi.get("color", DARK_BLUE),
        )


# =====================================================================
#  Table helper
# =====================================================================

def _add_styled_table(slide, headers, rows, top=Inches(2.7),
                      col_widths=None, roas_col_idx=None):
    """Add a table with dark-blue header and alternating cream/white rows.

    If *roas_col_idx* is given, values in that column are coloured
    green/red vs the ROAS target for the row's campaign type.
    """
    n_rows = len(rows) + 1  # +1 for header
    n_cols = len(headers)
    left = Inches(0.6)
    width = Inches(8.8)
    height = Inches(0.28 * n_rows)

    tbl_shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    tbl = tbl_shape.table

    # Column widths
    if col_widths:
        for i, w in enumerate(col_widths):
            tbl.columns[i].width = Inches(w)

    # Header row
    for c, header in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = DARK_BLUE
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(9)
            p.font.bold = True
            p.font.color.rgb = WHITE
            p.alignment = PP_ALIGN.CENTER
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE

    # Data rows
    for r, row_data in enumerate(rows):
        bg = CREAM if r % 2 == 0 else WHITE
        for c, val in enumerate(row_data):
            cell = tbl.cell(r + 1, c)
            cell.text = str(val) if val is not None else "\u2014"
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(9)
                p.font.color.rgb = DARK_BLUE
                p.alignment = PP_ALIGN.CENTER

            # Colour ROAS column
            if roas_col_idx is not None and c == roas_col_idx:
                _color_roas_cell(cell, val, row_data)

    return tbl_shape


def _color_roas_cell(cell, roas_val, row_data):
    """Colour a ROAS cell green/red based on the campaign-type target."""
    try:
        roas_num = float(str(roas_val).replace(",", ""))
    except (ValueError, TypeError):
        return

    # Determine target from the row's campaign_type column (index 1)
    ctype = str(row_data[1]).strip() if len(row_data) > 1 else ""
    target = ROAS_TARGETS.get(ctype, ROAS_TARGETS.get("Prospecting", 8))
    color = GREEN if roas_num >= target else RED
    for p in cell.text_frame.paragraphs:
        p.font.color.rgb = color
        p.font.bold = True


# =====================================================================
#  Chart helper
# =====================================================================

def _try_add_roas_chart(slide, daily_df, platform, top_inches=4.0):
    """Attempt to render a ROAS line chart via plotly + kaleido.

    Falls back gracefully to a text note if kaleido is not installed.
    """
    if daily_df.empty:
        return

    plat_color = PLATFORM_COLORS.get(platform, COLORS["blue"])

    try:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily_df["period"],
            y=daily_df["roas"],
            mode="lines+markers",
            line=dict(color=plat_color, width=2.5),
            marker=dict(size=4, color=plat_color),
            name="ROAS",
        ))

        # Target lines
        for ct, target in ROAS_TARGETS.items():
            fig.add_hline(
                y=target, line_dash="dot", line_color="#C45C4A",
                line_width=1,
                annotation_text=f"{ct} target ({target})",
                annotation_font_size=9,
                annotation_font_color="#7A7A72",
                annotation_position="top left",
            )

        fig.update_layout(
            title=None,
            yaxis_title="ROAS",
            xaxis_title=None,
            height=320,
            width=880,
            plot_bgcolor="#FAFAF7",
            paper_bgcolor="#FAFAF7",
            margin=dict(l=50, r=20, t=10, b=35),
            font=dict(family="Helvetica, Arial, sans-serif", size=10, color="#2D3E50"),
            showlegend=False,
        )
        fig.update_xaxes(showgrid=False, tickformat="%d/%m")
        fig.update_yaxes(showgrid=True, gridcolor="#E8E4DD", gridwidth=0.8)

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        fig.write_image(tmp.name, width=880, height=320, scale=2)
        slide.shapes.add_picture(
            tmp.name,
            Inches(0.6), Inches(top_inches),
            Inches(8.8), Inches(3.0),
        )
        os.unlink(tmp.name)
    except Exception:
        _add_textbox(
            slide, Inches(0.6), Inches(top_inches), Inches(8.8), Inches(0.5),
            "(ROAS chart requires the kaleido package: pip install kaleido)",
            font_size=Pt(9), font_color=GRAY, alignment=PP_ALIGN.LEFT,
        )


# =====================================================================
#  Takeaway generator
# =====================================================================

def _generate_takeaways(filtered: pd.DataFrame) -> list[str]:
    """Return 3-4 auto-generated bullet points from the data."""
    bullets = []

    plat_agg = (
        filtered.groupby("platform")
        .agg(spend=("spend", "sum"), revenue=("revenue", "sum"),
             conversions=("conversions", "sum"))
        .reset_index()
    )
    plat_agg["roas"] = np.where(
        plat_agg["spend"] > 0, plat_agg["revenue"] / plat_agg["spend"], 0
    )
    plat_agg["aov"] = np.where(
        plat_agg["conversions"] > 0, plat_agg["revenue"] / plat_agg["conversions"], 0
    )

    if not plat_agg.empty:
        best = plat_agg.loc[plat_agg["roas"].idxmax()]
        worst = plat_agg.loc[plat_agg["roas"].idxmin()]
        bullets.append(
            f"Best ROAS: {best['platform']} at {best['roas']:.1f}x "
            f"on {format_currency(best['spend'])} spend."
        )
        if best["platform"] != worst["platform"]:
            bullets.append(
                f"Lowest ROAS: {worst['platform']} at {worst['roas']:.1f}x "
                f"({format_currency(worst['spend'])} spend)."
            )

    total_orders = filtered["conversions"].sum()
    total_revenue = filtered["revenue"].sum()
    overall_aov = total_revenue / total_orders if total_orders > 0 else 0
    bullets.append(
        f"Total orders: {format_number(total_orders, 0)} "
        f"with an AOV of {format_currency(overall_aov)}."
    )

    # Check platforms vs targets
    for _, row in plat_agg.iterrows():
        plat = row["platform"]
        roas = row["roas"]
        prosp_target = ROAS_TARGETS.get("Prospecting", 8)
        if roas >= prosp_target * 1.5:
            bullets.append(
                f"{plat} significantly exceeded the Prospecting target "
                f"({roas:.1f}x vs {prosp_target}x)."
            )
            break
        elif roas < prosp_target * 0.7:
            bullets.append(
                f"{plat} is well below the Prospecting target "
                f"({roas:.1f}x vs {prosp_target}x) \u2014 review spend allocation."
            )
            break

    return bullets[:4]


# =====================================================================
#  Prior-period comparison helper
# =====================================================================

def _compute_prior_period_kpis(df, start_date, end_date, platforms=None):
    """Return (spend, revenue, roas, orders) for the prior period of equal length."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    duration = (end - start).days
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=duration)

    mask = df["date"].between(prior_start, prior_end)
    if platforms:
        mask = mask & df["platform"].isin(platforms)
    prior = df[mask]

    if prior.empty:
        return None

    spend = prior["spend"].sum()
    revenue = prior["revenue"].sum()
    roas = revenue / spend if spend > 0 else 0
    orders = prior["conversions"].sum()
    return {"spend": spend, "revenue": revenue, "roas": roas, "orders": orders}


def _delta_str(current, prior):
    """Return a formatted +/-% string, or empty string if unavailable."""
    if prior is None or prior == 0:
        return ""
    pct = (current - prior) / abs(prior) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


# =====================================================================
#  SLIDE BUILDERS
# =====================================================================

def _build_title_slide(prs, date_range_str):
    """Slide 1 -- Title slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank

    # Main title
    _add_textbox(
        slide, Inches(0.6), Inches(2.4), Inches(8.8), Inches(1.0),
        "Performance Report",
        font_size=Pt(36), font_color=DARK_BLUE, bold=True,
        alignment=PP_ALIGN.LEFT,
    )

    # Date range subtitle
    _add_textbox(
        slide, Inches(0.6), Inches(3.4), Inches(8.8), Inches(0.5),
        date_range_str,
        font_size=Pt(14), font_color=GRAY, bold=False,
        alignment=PP_ALIGN.LEFT,
    )

    # Bottom branding
    _add_textbox(
        slide, Inches(0.6), Inches(6.6), Inches(8.8), Inches(0.4),
        "Objectif Lune \u2014 Command Center",
        font_size=Pt(9), font_color=GRAY, bold=False,
        alignment=PP_ALIGN.LEFT,
    )

    return slide


def _build_executive_summary(prs, filtered, prior_kpis):
    """Slide 2 -- Executive Summary with 4 KPI cards + summary line."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_slide_title(slide, "Executive Summary")
    _add_thin_rule(slide, Inches(0.95))

    total_spend = filtered["spend"].sum()
    total_revenue = filtered["revenue"].sum()
    total_orders = filtered["conversions"].sum()
    blended_roas = total_revenue / total_spend if total_spend > 0 else 0

    # Build delta strings
    d_spend = _delta_str(total_spend, prior_kpis["spend"]) if prior_kpis else ""
    d_rev = _delta_str(total_revenue, prior_kpis["revenue"]) if prior_kpis else ""
    d_roas = _delta_str(blended_roas, prior_kpis["roas"]) if prior_kpis else ""
    d_orders = _delta_str(total_orders, prior_kpis["orders"]) if prior_kpis else ""

    kpis = [
        {"label": "Total Spend", "value": format_currency(total_spend), "delta": d_spend},
        {"label": "Total Revenue", "value": format_currency(total_revenue), "delta": d_rev},
        {"label": "Blended ROAS", "value": format_number(blended_roas, 1), "delta": d_roas},
        {"label": "Total Orders", "value": format_number(total_orders, 0), "delta": d_orders},
    ]
    _draw_kpi_row(slide, kpis, top=Inches(1.3), card_h=Inches(1.25))

    # Summary line
    summary = (
        f"ROAS of {blended_roas:.1f} across {format_currency(total_spend)} spend, "
        f"{format_number(total_orders, 0)} orders"
    )
    _add_textbox(
        slide, Inches(0.6), Inches(2.85), Inches(8.8), Inches(0.4),
        summary,
        font_size=Pt(11), font_color=GRAY, alignment=PP_ALIGN.CENTER,
    )

    return slide


def _build_platform_table_slide(prs, filtered):
    """Slide 3 -- Platform Breakdown table."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_slide_title(slide, "Platform Performance")
    _add_thin_rule(slide, Inches(0.95))

    plat_summary = (
        filtered.groupby(["platform", "campaign_type"])
        .agg(
            spend=("spend", "sum"),
            revenue=("revenue", "sum"),
            impressions=("impressions", "sum"),
            conversions=("conversions", "sum"),
        )
        .reset_index()
    )
    plat_summary["roas"] = np.where(
        plat_summary["spend"] > 0,
        plat_summary["revenue"] / plat_summary["spend"], 0,
    )
    plat_summary["cpm"] = np.where(
        plat_summary["impressions"] > 0,
        plat_summary["spend"] / plat_summary["impressions"] * 1000, 0,
    )
    plat_summary = plat_summary.sort_values(["platform", "campaign_type"])

    headers = ["Platform", "Type", "Spend", "Revenue", "ROAS", "Orders", "CPM"]
    rows = []
    for _, r in plat_summary.iterrows():
        rows.append([
            r["platform"],
            r["campaign_type"],
            format_currency(r["spend"]),
            format_currency(r["revenue"]),
            format_number(r["roas"], 1),
            format_number(r["conversions"], 0),
            format_currency(r["cpm"]),
        ])

    _add_styled_table(
        slide, headers, rows,
        top=Inches(1.25),
        col_widths=[1.4, 1.2, 1.3, 1.3, 0.9, 0.9, 1.0],
        roas_col_idx=4,
    )

    return slide


def _build_platform_slide(prs, filtered, platform):
    """Slide 4+ -- One slide per platform."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_slide_title(slide, f"{platform} \u2014 Performance")
    _add_thin_rule(slide, Inches(0.95))

    plat_data = filtered[filtered["platform"] == platform]
    plat_spend = plat_data["spend"].sum()
    plat_revenue = plat_data["revenue"].sum()
    plat_roas = plat_revenue / plat_spend if plat_spend > 0 else 0
    plat_orders = plat_data["conversions"].sum()

    # KPI boxes
    kpis = [
        {"label": "Spend", "value": format_currency(plat_spend)},
        {"label": "Revenue", "value": format_currency(plat_revenue)},
        {"label": "ROAS", "value": format_number(plat_roas, 1)},
        {"label": "Orders", "value": format_number(plat_orders, 0)},
    ]
    _draw_kpi_row(slide, kpis, top=Inches(1.2), card_h=Inches(1.0))

    # Mini breakdown table: Prospecting vs Retargeting
    type_agg = (
        plat_data.groupby("campaign_type")
        .agg(
            spend=("spend", "sum"),
            revenue=("revenue", "sum"),
            impressions=("impressions", "sum"),
            conversions=("conversions", "sum"),
        )
        .reset_index()
    )
    type_agg["roas"] = np.where(
        type_agg["spend"] > 0, type_agg["revenue"] / type_agg["spend"], 0,
    )
    type_agg["cpm"] = np.where(
        type_agg["impressions"] > 0,
        type_agg["spend"] / type_agg["impressions"] * 1000, 0,
    )

    headers = ["Type", "Spend", "Revenue", "ROAS", "Orders", "CPM"]
    rows = []
    for _, r in type_agg.iterrows():
        rows.append([
            r["campaign_type"],
            format_currency(r["spend"]),
            format_currency(r["revenue"]),
            format_number(r["roas"], 1),
            format_number(r["conversions"], 0),
            format_currency(r["cpm"]),
        ])

    _add_styled_table(
        slide, headers, rows,
        top=Inches(2.55),
        col_widths=[1.4, 1.5, 1.5, 1.0, 1.0, 1.2],
        roas_col_idx=3,
    )

    # ROAS trend chart
    plat_daily = aggregate_by_period(plat_data, "daily", group_cols=["platform"])
    _try_add_roas_chart(slide, plat_daily, platform, top_inches=4.2)

    return slide


def _build_takeaways_slide(prs, filtered):
    """Final slide -- Key Takeaways (auto-generated)."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_slide_title(slide, "Key Takeaways")
    _add_thin_rule(slide, Inches(0.95))

    bullets = _generate_takeaways(filtered)

    top = Inches(1.4)
    for i, bullet in enumerate(bullets):
        y = top + Inches(i * 0.65)
        # Bullet marker
        _add_textbox(
            slide, Inches(0.7), y, Inches(0.3), Inches(0.4),
            "\u2022", font_size=Pt(14), font_color=PRIMARY_BLUE,
            bold=True, alignment=PP_ALIGN.LEFT,
        )
        # Bullet text
        _add_textbox(
            slide, Inches(1.05), y, Inches(8.0), Inches(0.55),
            bullet, font_size=Pt(12), font_color=DARK_BLUE,
            bold=False, alignment=PP_ALIGN.LEFT,
        )

    # Bottom branding
    _add_textbox(
        slide, Inches(0.6), Inches(6.6), Inches(8.8), Inches(0.4),
        "Objectif Lune \u2014 Command Center",
        font_size=Pt(9), font_color=GRAY, alignment=PP_ALIGN.LEFT,
    )

    return slide


# =====================================================================
#  PUBLIC API
# =====================================================================

def generate_pptx_report(
    df: pd.DataFrame,
    start_date,
    end_date,
    platforms: list = None,
) -> BytesIO:
    """Generate a branded PowerPoint report and return a BytesIO buffer.

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset with columns: date, platform, campaign_type, spend,
        revenue, impressions, clicks, conversions, etc.
    start_date, end_date : date-like
        Reporting window boundaries.
    platforms : list[str] | None
        Optional filter to limit which platforms are included.

    Returns
    -------
    BytesIO
        In-memory PPTX file ready for Streamlit download.
    """
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    settings = load_settings()

    # ── Filter data ──────────────────────────────────────────────
    mask = df["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    if platforms:
        mask = mask & df["platform"].isin(platforms)
    filtered = df[mask].copy()

    # Date range string
    if hasattr(start_date, "strftime"):
        date_range_str = (
            f"{start_date.strftime('%d/%m/%Y')} \u2014 {end_date.strftime('%d/%m/%Y')}"
        )
    else:
        date_range_str = f"{start_date} \u2014 {end_date}"

    # Handle empty data
    if filtered.empty:
        _build_title_slide(prs, date_range_str)
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        _add_slide_title(slide, "No Data Available")
        _add_textbox(
            slide, Inches(0.6), Inches(2.0), Inches(8.8), Inches(1.0),
            "No data found for the selected period and platforms.",
            font_size=Pt(14), font_color=GRAY, alignment=PP_ALIGN.CENTER,
        )
        output = BytesIO()
        prs.save(output)
        output.seek(0)
        return output

    # Prior period for comparison
    prior_kpis = _compute_prior_period_kpis(df, start_date, end_date, platforms)

    # ── Build slides ─────────────────────────────────────────────
    _build_title_slide(prs, date_range_str)
    _build_executive_summary(prs, filtered, prior_kpis)
    _build_platform_table_slide(prs, filtered)

    for platform in sorted(filtered["platform"].unique()):
        _build_platform_slide(prs, filtered, platform)

    _build_takeaways_slide(prs, filtered)

    # ── Save ─────────────────────────────────────────────────────
    output = BytesIO()
    prs.save(output)
    output.seek(0)
    return output
