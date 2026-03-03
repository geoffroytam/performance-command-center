"""PowerPoint report generation with charts, tables, and branding."""

import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.chart import XL_CHART_TYPE
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

# Color constants
DARK_BLUE = RGBColor(0x1B, 0x4F, 0x72)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x66, 0x66, 0x66)
GREEN = RGBColor(0x2D, 0x8B, 0x4E)
RED = RGBColor(0xC0, 0x39, 0x2B)


def add_title_slide(prs, title_text: str, subtitle_text: str = ""):
    """Add a title slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    title = slide.shapes.title
    title.text = title_text
    title.text_frame.paragraphs[0].font.color.rgb = DARK_BLUE
    title.text_frame.paragraphs[0].font.size = Pt(28)

    if subtitle_text and slide.placeholders[1]:
        subtitle = slide.placeholders[1]
        subtitle.text = subtitle_text
        subtitle.text_frame.paragraphs[0].font.color.rgb = GRAY
        subtitle.text_frame.paragraphs[0].font.size = Pt(14)

    return slide


def add_content_slide(prs, title_text: str) -> object:
    """Add a content slide with a title."""
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # Blank layout
    # Add title text box
    left = Inches(0.5)
    top = Inches(0.3)
    width = Inches(9)
    height = Inches(0.6)
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(22)
    p.font.color.rgb = DARK_BLUE
    p.font.bold = True
    return slide


def add_table_to_slide(slide, data: list[list], col_widths: list = None, top: float = 1.2):
    """Add a formatted table to a slide."""
    if not data or len(data) < 2:
        return

    rows = len(data)
    cols = len(data[0])

    left = Inches(0.5)
    top_pos = Inches(top)
    width = Inches(9)
    height = Inches(0.3 * rows)

    table_shape = slide.shapes.add_table(rows, cols, left, top_pos, width, height)
    table = table_shape.table

    for r_idx, row in enumerate(data):
        for c_idx, value in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.text = str(value) if value is not None else "—"

            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(9)
                paragraph.alignment = PP_ALIGN.CENTER

                if r_idx == 0:
                    # Header row
                    paragraph.font.bold = True
                    paragraph.font.color.rgb = WHITE
                    paragraph.font.size = Pt(10)

            if r_idx == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = DARK_BLUE

    return table_shape


def add_kpi_cards(slide, kpis: list[dict], top: float = 1.2):
    """Add KPI metric cards to a slide."""
    n = len(kpis)
    card_width = 2.0
    spacing = 0.3
    total_width = n * card_width + (n - 1) * spacing
    start_left = (10 - total_width) / 2

    for idx, kpi in enumerate(kpis):
        left = Inches(start_left + idx * (card_width + spacing))
        top_pos = Inches(top)
        width = Inches(card_width)
        height = Inches(1.2)

        shape = slide.shapes.add_shape(
            1,  # Rectangle
            left, top_pos, width, height,
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(0xF2, 0xF2, 0xF2)
        shape.line.fill.background()

        tf = shape.text_frame
        tf.word_wrap = True

        # Label
        p = tf.paragraphs[0]
        p.text = kpi.get("label", "")
        p.font.size = Pt(9)
        p.font.color.rgb = GRAY
        p.alignment = PP_ALIGN.CENTER

        # Value
        p2 = tf.add_paragraph()
        p2.text = kpi.get("value", "—")
        p2.font.size = Pt(18)
        p2.font.bold = True
        p2.font.color.rgb = DARK_BLUE
        p2.alignment = PP_ALIGN.CENTER

        # Delta
        delta = kpi.get("delta", "")
        if delta:
            p3 = tf.add_paragraph()
            p3.text = delta
            p3.font.size = Pt(9)
            p3.font.color.rgb = GREEN if delta.startswith("+") else RED
            p3.alignment = PP_ALIGN.CENTER


def export_plotly_as_image(fig) -> str:
    """Export a plotly figure as a temporary PNG file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.write_image(tmp.name, width=900, height=400, scale=2)
    return tmp.name


def generate_pptx_report(
    df: pd.DataFrame,
    start_date,
    end_date,
    platforms: list = None,
) -> BytesIO:
    """
    Generate a PowerPoint presentation report.

    Returns BytesIO buffer ready for download.
    """
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    settings = load_settings()

    # Filter data
    mask = df["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    if platforms:
        mask = mask & df["platform"].isin(platforms)
    filtered = df[mask].copy()

    if filtered.empty:
        slide = add_title_slide(prs, "Performance Report", "No data available for selected period")
        output = BytesIO()
        prs.save(output)
        output.seek(0)
        return output

    date_range_str = f"{start_date.strftime('%d/%m/%Y')} — {end_date.strftime('%d/%m/%Y')}" if hasattr(start_date, 'strftime') else str(start_date)

    # ── Slide 1: Title ────────────────────────────────────────
    add_title_slide(
        prs,
        "Performance Report",
        f"{date_range_str}\nGenerated {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    )

    # ── Slide 2: Executive Summary ────────────────────────────
    slide2 = add_content_slide(prs, "Executive Summary")

    total_spend = filtered["spend"].sum()
    total_revenue = filtered["revenue"].sum()
    total_orders = filtered["conversions"].sum()
    blended_roas = total_revenue / total_spend if total_spend > 0 else 0

    kpi_cards = [
        {"label": "Total Spend", "value": format_currency(total_spend)},
        {"label": "Total Revenue", "value": format_currency(total_revenue)},
        {"label": "Blended ROAS", "value": format_number(blended_roas, 1)},
        {"label": "Total Orders", "value": format_number(total_orders, 0)},
    ]
    add_kpi_cards(slide2, kpi_cards)

    # ── Slide 3: Platform Performance Table ───────────────────
    slide3 = add_content_slide(prs, "Platform Performance")

    daily_agg = aggregate_by_period(filtered, "daily", group_cols=["platform", "campaign_type"])
    platform_summary = (
        filtered.groupby(["platform", "campaign_type"])
        .agg(spend=("spend", "sum"), revenue=("revenue", "sum"),
             impressions=("impressions", "sum"), clicks=("clicks", "sum"),
             conversions=("conversions", "sum"))
        .reset_index()
    )
    platform_summary["roas"] = np.where(
        platform_summary["spend"] > 0,
        platform_summary["revenue"] / platform_summary["spend"],
        0,
    )
    platform_summary["cpm"] = np.where(
        platform_summary["impressions"] > 0,
        platform_summary["spend"] / platform_summary["impressions"] * 1000,
        0,
    )

    table_data = [["Platform", "Type", "Spend", "Revenue", "ROAS", "CPM", "Orders"]]
    for _, row in platform_summary.iterrows():
        table_data.append([
            row["platform"],
            row["campaign_type"],
            format_currency(row["spend"]),
            format_currency(row["revenue"]),
            format_number(row["roas"], 1),
            format_currency(row["cpm"]),
            format_number(row["conversions"], 0),
        ])

    add_table_to_slide(slide3, table_data)

    # ── Slides 4-N: Per-Platform Slides ───────────────────────
    for platform in sorted(filtered["platform"].unique()):
        slide = add_content_slide(prs, f"{platform} Performance")

        plat_data = filtered[filtered["platform"] == platform]
        plat_spend = plat_data["spend"].sum()
        plat_revenue = plat_data["revenue"].sum()
        plat_roas = plat_revenue / plat_spend if plat_spend > 0 else 0
        plat_orders = plat_data["conversions"].sum()

        kpis = [
            {"label": "Spend", "value": format_currency(plat_spend)},
            {"label": "Revenue", "value": format_currency(plat_revenue)},
            {"label": "ROAS", "value": format_number(plat_roas, 1)},
            {"label": "Orders", "value": format_number(plat_orders, 0)},
        ]
        add_kpi_cards(slide, kpis)

        # ROAS trend chart as image
        plat_daily = aggregate_by_period(plat_data, "daily", group_cols=["platform"])
        if not plat_daily.empty:
            try:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=plat_daily["period"],
                    y=plat_daily["roas"],
                    mode="lines+markers",
                    line=dict(color=PLATFORM_COLORS.get(platform, COLORS["blue"]), width=2),
                    marker=dict(size=5),
                ))
                fig.update_layout(
                    title=f"ROAS Trend — {platform}",
                    yaxis_title="ROAS",
                    height=400,
                    plot_bgcolor="white",
                    margin=dict(l=60, r=20, t=50, b=40),
                )
                fig.update_yaxes(showgrid=True, gridcolor="#E5E5E5")

                img_path = export_plotly_as_image(fig)
                slide.shapes.add_picture(
                    img_path,
                    Inches(0.5), Inches(2.8),
                    Inches(9), Inches(4),
                )
                os.unlink(img_path)
            except Exception:
                # If plotly image export fails (no kaleido), add text instead
                txBox = slide.shapes.add_textbox(Inches(0.5), Inches(3), Inches(9), Inches(1))
                tf = txBox.text_frame
                p = tf.paragraphs[0]
                p.text = "(Chart image requires kaleido package: pip install kaleido)"
                p.font.size = Pt(10)
                p.font.color.rgb = GRAY

    # Save
    output = BytesIO()
    prs.save(output)
    output.seek(0)
    return output
