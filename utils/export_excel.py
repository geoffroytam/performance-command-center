"""Excel report generation with formatting, conditional formatting, and charts."""

import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.chart import LineChart, Reference

from utils.calculations import (
    calculate_baselines,
    aggregate_by_period,
    aggregate_for_date,
)
from utils.constants import COLORS, ROAS_TARGETS, load_settings

# Style constants
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="1B4F72", end_color="1B4F72", fill_type="solid")
GREEN_FILL = PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid")
RED_FILL = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")
ORANGE_FILL = PatternFill(start_color="FDEBD0", end_color="FDEBD0", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="D5D8DC"),
    right=Side(style="thin", color="D5D8DC"),
    top=Side(style="thin", color="D5D8DC"),
    bottom=Side(style="thin", color="D5D8DC"),
)


def style_header_row(ws, num_cols: int):
    """Apply header styling to the first row."""
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER


def auto_width(ws):
    """Auto-adjust column widths."""
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except Exception:
                pass
        adjusted = min(max_length + 3, 25)
        ws.column_dimensions[col_letter].width = adjusted


def apply_roas_formatting(ws, roas_col: int, start_row: int, end_row: int, campaign_type_col: int = None):
    """Color-code ROAS cells based on targets."""
    settings = load_settings()
    prosp_target = settings.get("roas_target_prospecting", 8)
    retarg_target = settings.get("roas_target_retargeting", 14)

    for row in range(start_row, end_row + 1):
        roas_cell = ws.cell(row=row, column=roas_col)
        try:
            roas_val = float(roas_cell.value) if roas_cell.value else None
        except (ValueError, TypeError):
            continue

        if roas_val is None:
            continue

        target = prosp_target  # Default
        if campaign_type_col:
            ctype = ws.cell(row=row, column=campaign_type_col).value
            if ctype and "retarg" in str(ctype).lower():
                target = retarg_target

        if roas_val >= target:
            roas_cell.fill = GREEN_FILL
        else:
            roas_cell.fill = RED_FILL


def df_to_sheet(ws, df: pd.DataFrame, include_header: bool = True):
    """Write a DataFrame to a worksheet with formatting."""
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=include_header), 1):
        for c_idx, value in enumerate(row, 1):
            cell = ws.cell(row=r_idx, column=c_idx)
            if isinstance(value, float) and pd.isna(value):
                cell.value = None
            else:
                cell.value = value
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center")

    if include_header:
        style_header_row(ws, len(df.columns))


def generate_excel_report(
    df: pd.DataFrame,
    start_date,
    end_date,
    platforms: list = None,
    include_charts: bool = True,
) -> BytesIO:
    """
    Generate a full Excel report with multiple sheets.

    Returns BytesIO buffer ready for download.
    """
    wb = Workbook()
    settings = load_settings()

    # Filter data
    mask = df["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    if platforms:
        mask = mask & df["platform"].isin(platforms)
    filtered = df[mask].copy()

    if filtered.empty:
        ws = wb.active
        ws.title = "No Data"
        ws["A1"] = "No data available for the selected filters."
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    # ── Sheet 1: Daily Performance ────────────────────────────
    ws1 = wb.active
    ws1.title = "Daily Performance"

    daily = aggregate_by_period(filtered, "daily", group_cols=["platform", "campaign_type"])
    daily = daily.sort_values(["period", "platform", "campaign_type"]).reset_index(drop=True)
    daily["date"] = daily["period"].dt.strftime("%d/%m/%Y")

    display_cols = [
        "date", "platform", "campaign_type", "spend", "revenue", "roas",
        "impressions", "clicks", "conversions", "cpm", "ctr", "cvr", "aov", "cpa",
    ]
    daily_display = daily[[c for c in display_cols if c in daily.columns]].copy()

    # Rename for display
    col_rename = {
        "date": "Date", "platform": "Platform", "campaign_type": "Type",
        "spend": "Spend (R$)", "revenue": "Revenue (R$)", "roas": "ROAS",
        "impressions": "Impressions", "clicks": "Clicks", "conversions": "Orders",
        "cpm": "CPM (R$)", "ctr": "CTR (%)", "cvr": "CVR (%)",
        "aov": "AOV (R$)", "cpa": "CPA (R$)",
    }
    daily_display = daily_display.rename(columns=col_rename)

    # Round numeric columns
    for col in daily_display.select_dtypes(include=[np.number]).columns:
        daily_display[col] = daily_display[col].round(2)

    df_to_sheet(ws1, daily_display)

    # ROAS conditional formatting
    roas_col_idx = list(daily_display.columns).index("ROAS") + 1
    type_col_idx = list(daily_display.columns).index("Type") + 1
    apply_roas_formatting(ws1, roas_col_idx, 2, len(daily_display) + 1, type_col_idx)

    # Freeze panes
    ws1.freeze_panes = "D2"
    auto_width(ws1)

    # ── Sheet 2: Weekly Summary ───────────────────────────────
    ws2 = wb.create_sheet("Weekly Summary")
    weekly = aggregate_by_period(filtered, "weekly", group_cols=["platform", "campaign_type"])
    weekly = weekly.sort_values(["period", "platform", "campaign_type"]).reset_index(drop=True)
    weekly["week"] = weekly["period"].dt.strftime("W%V %Y")

    # WoW deltas
    for kpi in ["roas", "cpm", "ctr", "cvr", "aov"]:
        weekly[f"{kpi}_wow"] = weekly.groupby(["platform", "campaign_type"])[kpi].pct_change() * 100

    weekly_display_cols = [
        "week", "platform", "campaign_type", "spend", "revenue", "roas",
        "roas_wow", "cpm", "cpm_wow", "ctr", "ctr_wow", "cvr", "cvr_wow", "aov", "aov_wow",
        "conversions",
    ]
    weekly_display = weekly[[c for c in weekly_display_cols if c in weekly.columns]].copy()
    for col in weekly_display.select_dtypes(include=[np.number]).columns:
        weekly_display[col] = weekly_display[col].round(2)
    weekly_display = weekly_display.rename(columns={
        "week": "Week", "platform": "Platform", "campaign_type": "Type",
        "spend": "Spend (R$)", "revenue": "Revenue (R$)", "roas": "ROAS",
        "roas_wow": "ROAS WoW%", "cpm": "CPM (R$)", "cpm_wow": "CPM WoW%",
        "ctr": "CTR (%)", "ctr_wow": "CTR WoW%", "cvr": "CVR (%)", "cvr_wow": "CVR WoW%",
        "aov": "AOV (R$)", "aov_wow": "AOV WoW%", "conversions": "Orders",
    })

    df_to_sheet(ws2, weekly_display)
    ws2.freeze_panes = "D2"
    auto_width(ws2)

    # ── Sheet 3: Monthly Summary ──────────────────────────────
    ws3 = wb.create_sheet("Monthly Summary")
    monthly = aggregate_by_period(filtered, "monthly", group_cols=["platform", "campaign_type"])
    monthly = monthly.sort_values(["period", "platform", "campaign_type"]).reset_index(drop=True)
    monthly["month"] = monthly["period"].dt.strftime("%b %Y")

    for kpi in ["roas", "cpm", "ctr", "cvr", "aov"]:
        monthly[f"{kpi}_mom"] = monthly.groupby(["platform", "campaign_type"])[kpi].pct_change() * 100

    monthly_display_cols = [
        "month", "platform", "campaign_type", "spend", "revenue", "roas",
        "roas_mom", "cpm", "ctr", "cvr", "aov", "conversions",
    ]
    monthly_display = monthly[[c for c in monthly_display_cols if c in monthly.columns]].copy()
    for col in monthly_display.select_dtypes(include=[np.number]).columns:
        monthly_display[col] = monthly_display[col].round(2)
    monthly_display = monthly_display.rename(columns={
        "month": "Month", "platform": "Platform", "campaign_type": "Type",
        "spend": "Spend (R$)", "revenue": "Revenue (R$)", "roas": "ROAS",
        "roas_mom": "ROAS MoM%", "cpm": "CPM (R$)", "ctr": "CTR (%)",
        "cvr": "CVR (%)", "aov": "AOV (R$)", "conversions": "Orders",
    })

    df_to_sheet(ws3, monthly_display)
    ws3.freeze_panes = "D2"
    auto_width(ws3)

    # ── Sheet 4: Baselines ────────────────────────────────────
    ws4 = wb.create_sheet("Baselines")
    ref_date = pd.Timestamp(end_date)
    baseline_rows = []

    for platform in filtered["platform"].unique():
        for ctype in filtered[filtered["platform"] == platform]["campaign_type"].unique():
            b = calculate_baselines(filtered, ref_date, platform=platform, campaign_type=ctype)
            baseline_rows.append({
                "Platform": platform,
                "Type": ctype,
                "AOV 60d": round(b.get("aov", 0), 2) if not pd.isna(b.get("aov")) else None,
                "CPM 14d": round(b.get("cpm", 0), 2) if not pd.isna(b.get("cpm")) else None,
                "CTR 14d": round(b.get("ctr", 0), 2) if not pd.isna(b.get("ctr")) else None,
                "CVR 14d": round(b.get("cvr", 0), 2) if not pd.isna(b.get("cvr")) else None,
                "ROAS 7d": round(b.get("roas_7d", 0), 1) if not pd.isna(b.get("roas_7d")) else None,
                "ROAS 30d": round(b.get("roas_30d", 0), 1) if not pd.isna(b.get("roas_30d")) else None,
            })

    if baseline_rows:
        df_to_sheet(ws4, pd.DataFrame(baseline_rows))
        auto_width(ws4)

    # ── Optional: ROAS Chart ──────────────────────────────────
    if include_charts and not daily.empty:
        ws_chart = wb.create_sheet("ROAS Chart Data")
        # Pivot daily data for chart
        pivot = daily.pivot_table(
            index="period", columns="platform", values="roas", aggfunc="mean"
        ).reset_index()
        pivot["date"] = pivot["period"].dt.strftime("%d/%m/%Y")
        pivot = pivot.drop(columns=["period"])
        cols = ["date"] + [c for c in pivot.columns if c != "date"]
        pivot = pivot[cols]

        df_to_sheet(ws_chart, pivot)
        auto_width(ws_chart)

        chart = LineChart()
        chart.title = "ROAS Trend by Platform"
        chart.y_axis.title = "ROAS"
        chart.x_axis.title = "Date"
        chart.style = 10
        chart.width = 20
        chart.height = 12

        data_ref = Reference(ws_chart, min_col=2, min_row=1, max_col=len(pivot.columns), max_row=len(pivot) + 1)
        cats = Reference(ws_chart, min_col=1, min_row=2, max_row=len(pivot) + 1)
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats)
        ws_chart.add_chart(chart, "A" + str(len(pivot) + 4))

    # Save
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
