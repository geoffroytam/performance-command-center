"""Power BI-ready file generation with fact and dimension tables."""

import pandas as pd
import numpy as np
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from utils.calculations import calculate_baselines, aggregate_by_period
from utils.forecasting import load_forecast_log
from utils.constants import ROAS_TARGETS, load_settings

HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="1B4F72", end_color="1B4F72", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="D5D8DC"),
    right=Side(style="thin", color="D5D8DC"),
    top=Side(style="thin", color="D5D8DC"),
    bottom=Side(style="thin", color="D5D8DC"),
)


def generate_powerbi_export(
    df: pd.DataFrame,
    start_date=None,
    end_date=None,
    platforms: list = None,
) -> BytesIO:
    """
    Generate a Power BI-ready Excel file with fact and dimension tables.

    Sheets:
    - fact_daily: One row per date x platform x campaign_type
    - dim_platform: Platform dimension table
    - dim_baselines: Current baseline values
    - fact_forecast: Forecast data
    """
    wb = Workbook()
    settings = load_settings()

    # Filter data
    filtered = df.copy()
    if start_date is not None:
        filtered = filtered[filtered["date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        filtered = filtered[filtered["date"] <= pd.Timestamp(end_date)]
    if platforms:
        filtered = filtered[filtered["platform"].isin(platforms)]

    # ── Sheet 1: fact_daily ───────────────────────────────────
    ws1 = wb.active
    ws1.title = "fact_daily"

    # Aggregate to daily x platform x campaign_type level
    if not filtered.empty:
        fact = (
            filtered.groupby(["date", "platform", "campaign_type", "product_tier"])
            .agg(
                spend=("spend", "sum"),
                impressions=("impressions", "sum"),
                clicks=("clicks", "sum"),
                conversions=("conversions", "sum"),
                revenue=("revenue", "sum"),
            )
            .reset_index()
        )

        # Recalculate KPIs
        fact["cpm"] = np.where(fact["impressions"] > 0, fact["spend"] / fact["impressions"] * 1000, np.nan)
        fact["ctr"] = np.where(fact["impressions"] > 0, fact["clicks"] / fact["impressions"] * 100, np.nan)
        fact["cvr"] = np.where(fact["clicks"] > 0, fact["conversions"] / fact["clicks"] * 100, np.nan)
        fact["aov"] = np.where(fact["conversions"] > 0, fact["revenue"] / fact["conversions"], np.nan)
        fact["roas"] = np.where(fact["spend"] > 0, fact["revenue"] / fact["spend"], np.nan)
        fact["cpa"] = np.where(fact["conversions"] > 0, fact["spend"] / fact["conversions"], np.nan)

        # Clean column names for Power BI
        fact["date"] = fact["date"].dt.strftime("%Y-%m-%d")

        # Round numeric columns
        numeric_cols = ["spend", "revenue", "cpm", "ctr", "cvr", "aov", "roas", "cpa"]
        for col in numeric_cols:
            if col in fact.columns:
                fact[col] = fact[col].round(4)

        # Write headers
        headers = list(fact.columns)
        for c_idx, header in enumerate(headers, 1):
            cell = ws1.cell(row=1, column=c_idx, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center")

        # Write data
        for r_idx, row in enumerate(fact.values, 2):
            for c_idx, value in enumerate(row, 1):
                cell = ws1.cell(row=r_idx, column=c_idx)
                if isinstance(value, float) and np.isnan(value):
                    cell.value = None
                else:
                    cell.value = value
                cell.border = THIN_BORDER

    # ── Sheet 2: dim_platform ─────────────────────────────────
    ws2 = wb.create_sheet("dim_platform")

    dim_platform_headers = [
        "platform", "roas_target_prospecting", "roas_target_retargeting"
    ]
    for c_idx, header in enumerate(dim_platform_headers, 1):
        cell = ws2.cell(row=1, column=c_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    all_platforms = sorted(filtered["platform"].unique()) if not filtered.empty else []
    for r_idx, platform in enumerate(all_platforms, 2):
        ws2.cell(row=r_idx, column=1, value=platform).border = THIN_BORDER
        ws2.cell(row=r_idx, column=2, value=settings.get("roas_target_prospecting", 8)).border = THIN_BORDER
        ws2.cell(row=r_idx, column=3, value=settings.get("roas_target_retargeting", 14)).border = THIN_BORDER

    # ── Sheet 3: dim_baselines ────────────────────────────────
    ws3 = wb.create_sheet("dim_baselines")

    baseline_headers = [
        "platform", "campaign_type",
        "baseline_aov_60d", "baseline_cpm_14d",
        "baseline_ctr_14d", "baseline_cvr_14d",
    ]
    for c_idx, header in enumerate(baseline_headers, 1):
        cell = ws3.cell(row=1, column=c_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    if not filtered.empty:
        ref_date = filtered["date"].max()
        r_idx = 2
        for platform in all_platforms:
            for ctype in sorted(filtered[filtered["platform"] == platform]["campaign_type"].unique()):
                baselines = calculate_baselines(filtered, ref_date, platform=platform, campaign_type=ctype)
                ws3.cell(row=r_idx, column=1, value=platform).border = THIN_BORDER
                ws3.cell(row=r_idx, column=2, value=ctype).border = THIN_BORDER

                aov = baselines.get("aov")
                ws3.cell(row=r_idx, column=3, value=round(aov, 2) if not pd.isna(aov) else None).border = THIN_BORDER
                cpm = baselines.get("cpm")
                ws3.cell(row=r_idx, column=4, value=round(cpm, 2) if not pd.isna(cpm) else None).border = THIN_BORDER
                ctr = baselines.get("ctr")
                ws3.cell(row=r_idx, column=5, value=round(ctr, 4) if not pd.isna(ctr) else None).border = THIN_BORDER
                cvr = baselines.get("cvr")
                ws3.cell(row=r_idx, column=6, value=round(cvr, 4) if not pd.isna(cvr) else None).border = THIN_BORDER
                r_idx += 1

    # ── Sheet 4: fact_forecast ────────────────────────────────
    ws4 = wb.create_sheet("fact_forecast")

    forecast_headers = [
        "month", "platform", "campaign_type",
        "forecast_spend", "forecast_revenue", "forecast_roas",
        "actual_spend", "actual_revenue", "actual_roas",
        "delta_pct",
    ]
    for c_idx, header in enumerate(forecast_headers, 1):
        cell = ws4.cell(row=1, column=c_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    forecast_log = load_forecast_log()
    r_idx = 2
    for entry in forecast_log:
        month = entry.get("month", "")
        for proj in entry.get("projections", []):
            ws4.cell(row=r_idx, column=1, value=month).border = THIN_BORDER
            ws4.cell(row=r_idx, column=2, value=proj.get("platform", "")).border = THIN_BORDER
            ws4.cell(row=r_idx, column=3, value=proj.get("type", "")).border = THIN_BORDER
            ws4.cell(row=r_idx, column=4, value=round(proj.get("spend", 0), 2)).border = THIN_BORDER
            ws4.cell(row=r_idx, column=5, value=round(proj.get("revenue", 0), 2)).border = THIN_BORDER
            ws4.cell(row=r_idx, column=6, value=round(proj.get("roas", 0), 2)).border = THIN_BORDER

            # Try to find actuals
            if not filtered.empty:
                try:
                    month_start = pd.Timestamp(month + "-01")
                    month_end = month_start + pd.DateOffset(months=1) - pd.Timedelta(days=1)
                    actuals = filtered[
                        (filtered["date"].between(month_start, month_end))
                        & (filtered["platform"] == proj.get("platform", ""))
                        & (filtered["campaign_type"] == proj.get("type", ""))
                    ]
                    actual_spend = actuals["spend"].sum()
                    actual_revenue = actuals["revenue"].sum()
                    actual_roas = actual_revenue / actual_spend if actual_spend > 0 else 0

                    ws4.cell(row=r_idx, column=7, value=round(actual_spend, 2)).border = THIN_BORDER
                    ws4.cell(row=r_idx, column=8, value=round(actual_revenue, 2)).border = THIN_BORDER
                    ws4.cell(row=r_idx, column=9, value=round(actual_roas, 2)).border = THIN_BORDER

                    fcast_roas = proj.get("roas", 0)
                    if fcast_roas > 0:
                        delta = (actual_roas - fcast_roas) / fcast_roas * 100
                        ws4.cell(row=r_idx, column=10, value=round(delta, 1)).border = THIN_BORDER
                except Exception:
                    pass

            r_idx += 1

    # Auto-width all sheets
    for ws in wb.worksheets:
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

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
