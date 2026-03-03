"""KPI calculations, baselines, deltas, and aggregation helpers."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

from utils.constants import load_settings


def calculate_baselines(
    df: pd.DataFrame,
    reference_date: datetime,
    platform: Optional[str] = None,
    campaign_type: Optional[str] = None,
) -> dict:
    """
    Calculate rolling baselines for a given date.
    AOV: 60-day rolling average
    CTR, CVR, CPM: 14-day rolling average
    ROAS: 7-day and 30-day
    """
    settings = load_settings()
    aov_days = settings.get("aov_baseline_days", 60)
    short_days = settings.get("cpm_baseline_days", 14)

    subset = df.copy()
    if platform:
        subset = subset[subset["platform"] == platform]
    if campaign_type:
        subset = subset[subset["campaign_type"] == campaign_type]

    if isinstance(reference_date, str):
        reference_date = pd.to_datetime(reference_date)

    ref_date = pd.Timestamp(reference_date)

    aov_window = subset[
        subset["date"].between(
            ref_date - timedelta(days=aov_days), ref_date - timedelta(days=1)
        )
    ]
    short_window = subset[
        subset["date"].between(
            ref_date - timedelta(days=short_days), ref_date - timedelta(days=1)
        )
    ]
    week_window = subset[
        subset["date"].between(
            ref_date - timedelta(days=7), ref_date - timedelta(days=1)
        )
    ]
    month_window = subset[
        subset["date"].between(
            ref_date - timedelta(days=30), ref_date - timedelta(days=1)
        )
    ]

    def safe_mean(series):
        if series.empty:
            return np.nan
        return series.mean()

    def weighted_ratio(num_col, den_col, window, multiplier=1):
        """Compute aggregate ratio from raw sums (more accurate than averaging ratios)."""
        num = window[num_col].sum()
        den = window[den_col].sum()
        if den == 0:
            return np.nan
        return num / den * multiplier

    return {
        "aov": weighted_ratio("revenue", "conversions", aov_window),
        "cpm": weighted_ratio("spend", "impressions", short_window, 1000),
        "ctr": weighted_ratio("clicks", "impressions", short_window, 100),
        "cvr": weighted_ratio("conversions", "clicks", short_window, 100),
        "roas_7d": weighted_ratio("revenue", "spend", week_window),
        "roas_30d": weighted_ratio("revenue", "spend", month_window),
        "roas_14d": weighted_ratio("revenue", "spend", short_window),
        "spend": safe_mean(short_window.groupby("date")["spend"].sum()) if not short_window.empty else np.nan,
        "conversions": safe_mean(short_window.groupby("date")["conversions"].sum()) if not short_window.empty else np.nan,
    }


def compute_delta(current: float, baseline: float) -> tuple[float, float]:
    """
    Compute absolute and percentage delta.
    Returns (absolute_delta, pct_delta).
    """
    if pd.isna(current) or pd.isna(baseline):
        return np.nan, np.nan
    abs_delta = current - baseline
    if baseline == 0:
        pct_delta = np.nan
    else:
        pct_delta = abs_delta / baseline
    return abs_delta, pct_delta


def aggregate_by_period(
    df: pd.DataFrame,
    period: str = "daily",
    group_cols: Optional[list] = None,
) -> pd.DataFrame:
    """
    Aggregate data by time period (daily, weekly, monthly).
    """
    if group_cols is None:
        group_cols = ["platform", "campaign_type"]

    agg_df = df.copy()

    if period == "weekly":
        agg_df["period"] = agg_df["date"].dt.to_period("W").apply(lambda r: r.start_time)
    elif period == "monthly":
        agg_df["period"] = agg_df["date"].dt.to_period("M").apply(lambda r: r.start_time)
    else:
        agg_df["period"] = agg_df["date"]

    agg = (
        agg_df.groupby(["period"] + group_cols)
        .agg(
            spend=("spend", "sum"),
            impressions=("impressions", "sum"),
            clicks=("clicks", "sum"),
            conversions=("conversions", "sum"),
            revenue=("revenue", "sum"),
        )
        .reset_index()
    )

    # Recalculate KPIs from aggregated raw values
    agg["cpm"] = np.where(agg["impressions"] > 0, agg["spend"] / agg["impressions"] * 1000, np.nan)
    agg["ctr"] = np.where(agg["impressions"] > 0, agg["clicks"] / agg["impressions"] * 100, np.nan)
    agg["cvr"] = np.where(agg["clicks"] > 0, agg["conversions"] / agg["clicks"] * 100, np.nan)
    agg["aov"] = np.where(agg["conversions"] > 0, agg["revenue"] / agg["conversions"], np.nan)
    agg["roas"] = np.where(agg["spend"] > 0, agg["revenue"] / agg["spend"], np.nan)
    agg["cpa"] = np.where(agg["conversions"] > 0, agg["spend"] / agg["conversions"], np.nan)

    return agg


def aggregate_for_date(
    df: pd.DataFrame, target_date, group_by: Optional[list] = None
) -> pd.DataFrame:
    """
    Aggregate all rows for a specific date, grouped by platform and campaign_type.
    """
    if group_by is None:
        group_by = ["platform", "campaign_type"]

    target = pd.Timestamp(target_date)
    day_data = df[df["date"] == target]

    if day_data.empty:
        return pd.DataFrame()

    agg = (
        day_data.groupby(group_by)
        .agg(
            spend=("spend", "sum"),
            impressions=("impressions", "sum"),
            clicks=("clicks", "sum"),
            conversions=("conversions", "sum"),
            revenue=("revenue", "sum"),
        )
        .reset_index()
    )

    agg["cpm"] = np.where(agg["impressions"] > 0, agg["spend"] / agg["impressions"] * 1000, np.nan)
    agg["ctr"] = np.where(agg["impressions"] > 0, agg["clicks"] / agg["impressions"] * 100, np.nan)
    agg["cvr"] = np.where(agg["clicks"] > 0, agg["conversions"] / agg["clicks"] * 100, np.nan)
    agg["aov"] = np.where(agg["conversions"] > 0, agg["revenue"] / agg["conversions"], np.nan)
    agg["roas"] = np.where(agg["spend"] > 0, agg["revenue"] / agg["spend"], np.nan)
    agg["cpa"] = np.where(agg["conversions"] > 0, agg["spend"] / agg["conversions"], np.nan)

    return agg


def get_previous_period_date(current_date, period: str = "day"):
    """Get the comparison date for a given period type."""
    current = pd.Timestamp(current_date)
    if period == "day":
        return current - timedelta(days=1)
    elif period == "week":
        return current - timedelta(weeks=1)
    elif period == "month":
        return current - pd.DateOffset(months=1)
    elif period == "year":
        return get_yoy_comparison_date(current)
    return current - timedelta(days=1)


def get_yoy_comparison_date(current_date):
    """
    Find the same day-of-week from the previous year.
    Example: Monday March 2, 2026 -> Monday March 3, 2025
    """
    current = pd.Timestamp(current_date)
    target_weekday = current.weekday()
    last_year_date = current.replace(year=current.year - 1)
    days_diff = (target_weekday - last_year_date.weekday()) % 7
    if days_diff > 3:
        days_diff -= 7
    return last_year_date + timedelta(days=days_diff)


def compute_period_deltas(
    df: pd.DataFrame,
    current_date,
    platform: str,
    campaign_type: str,
) -> dict:
    """
    Compute DoD, WoW, MoM, YoY deltas for all KPIs.
    Returns dict with keys like 'dod_roas', 'wow_cpm', etc.
    """
    current = aggregate_for_date(df, current_date)
    row = current[
        (current["platform"] == platform) & (current["campaign_type"] == campaign_type)
    ]
    if row.empty:
        return {}

    row = row.iloc[0]
    kpis = ["spend", "revenue", "roas", "cpm", "ctr", "cvr", "aov", "conversions"]
    periods = {
        "dod": get_previous_period_date(current_date, "day"),
        "wow": get_previous_period_date(current_date, "week"),
    }

    results = {f"current_{k}": row.get(k, np.nan) for k in kpis}

    for period_name, comp_date in periods.items():
        comp = aggregate_for_date(df, comp_date)
        comp_row = comp[
            (comp["platform"] == platform) & (comp["campaign_type"] == campaign_type)
        ]
        if comp_row.empty:
            for k in kpis:
                results[f"{period_name}_{k}_delta"] = np.nan
                results[f"{period_name}_{k}_pct"] = np.nan
        else:
            comp_row = comp_row.iloc[0]
            for k in kpis:
                abs_d, pct_d = compute_delta(row.get(k, np.nan), comp_row.get(k, np.nan))
                results[f"{period_name}_{k}_delta"] = abs_d
                results[f"{period_name}_{k}_pct"] = pct_d

    return results


def format_currency(value: float) -> str:
    """Format value as BRL currency."""
    if pd.isna(value):
        return "—"
    return f"R$ {value:,.2f}"


def format_pct(value: float) -> str:
    """Format value as percentage."""
    if pd.isna(value):
        return "—"
    return f"{value:.1f}%"


def format_number(value: float, decimals: int = 1) -> str:
    """Format a number with specified decimals."""
    if pd.isna(value):
        return "—"
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"


def format_delta(pct_delta: float) -> str:
    """Format a delta percentage with arrow."""
    if pd.isna(pct_delta):
        return "—"
    arrow = "+" if pct_delta >= 0 else ""
    return f"{arrow}{pct_delta:.1%}"
