"""Historical pattern comparison, rate-of-change calculations, and pattern log management."""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from pathlib import Path

from utils.constants import PATTERN_LOG_FILE
from utils.calculations import aggregate_by_period, get_yoy_comparison_date


def load_pattern_log() -> list:
    """Load the pattern log from JSON file."""
    if PATTERN_LOG_FILE.exists():
        try:
            with open(PATTERN_LOG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_pattern_log(log: list):
    """Save the pattern log to JSON file."""
    PATTERN_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PATTERN_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)


def compute_wow_rate_of_change(
    df: pd.DataFrame,
    start_date,
    end_date,
    platform: str,
    campaign_type: str,
) -> pd.DataFrame:
    """
    Compute week-over-week rate of change for all KPIs within a date range.
    Returns a DataFrame with weekly deltas.
    """
    mask = (
        (df["date"] >= pd.Timestamp(start_date))
        & (df["date"] <= pd.Timestamp(end_date))
        & (df["platform"] == platform)
        & (df["campaign_type"] == campaign_type)
    )
    filtered = df[mask]
    if filtered.empty:
        return pd.DataFrame()

    weekly = aggregate_by_period(filtered, "weekly", group_cols=["platform", "campaign_type"])
    if weekly.empty:
        return weekly

    weekly = weekly.sort_values("period").reset_index(drop=True)

    # Week number within the period (1-indexed)
    weekly["week_num"] = range(1, len(weekly) + 1)

    # Generate human-readable week labels like "Feb 3–9"
    week_labels = []
    for _, row in weekly.iterrows():
        week_start = pd.Timestamp(row["period"])
        week_end = week_start + pd.Timedelta(days=6)
        # Cap week_end to the period's actual end date
        if week_end > pd.Timestamp(end_date):
            week_end = pd.Timestamp(end_date)
        start_str = week_start.strftime("%b %d")
        # If same month, just show "Feb 3–9"; if different months, "Feb 27–Mar 5"
        if week_start.month == week_end.month:
            week_labels.append(f"{start_str}–{week_end.strftime('%d')}")
        else:
            week_labels.append(f"{start_str}–{week_end.strftime('%b %d')}")
    weekly["week_label"] = week_labels

    # Compute WoW change (needs at least 2 rows to be meaningful)
    kpis = ["roas", "cpm", "ctr", "cvr", "aov", "spend"]
    for kpi in kpis:
        weekly[f"{kpi}_wow_pct"] = weekly[kpi].pct_change() * 100

    return weekly


def compare_periods(
    df: pd.DataFrame,
    period1_start,
    period1_end,
    period2_start,
    period2_end,
    platform: str,
    campaign_type: str,
) -> dict:
    """
    Compare two time periods side-by-side.
    Returns dict with both periods' WoW rate-of-change DataFrames and summary stats.
    """
    roc1 = compute_wow_rate_of_change(df, period1_start, period1_end, platform, campaign_type)
    roc2 = compute_wow_rate_of_change(df, period2_start, period2_end, platform, campaign_type)

    return {
        "period1": {
            "start": period1_start,
            "end": period1_end,
            "data": roc1,
        },
        "period2": {
            "start": period2_start,
            "end": period2_end,
            "data": roc2,
        },
    }


def find_inflection_points(series: pd.Series) -> list[int]:
    """
    Find indices where the rate of change switches direction (positive to negative or vice versa).
    """
    if len(series) < 3:
        return []

    inflections = []
    for i in range(1, len(series) - 1):
        prev_val = series.iloc[i - 1]
        curr_val = series.iloc[i]
        next_val = series.iloc[i + 1]

        if pd.isna(prev_val) or pd.isna(curr_val) or pd.isna(next_val):
            continue

        # Check for sign change in the rate of change
        diff1 = curr_val - prev_val
        diff2 = next_val - curr_val
        if (diff1 > 0 and diff2 < 0) or (diff1 < 0 and diff2 > 0):
            inflections.append(i)

    return inflections


def get_patterns_for_month(month: int, year: int = None) -> list:
    """
    Get pattern log entries relevant to a specific month.
    Searches across all years unless a specific year is given.
    """
    log = load_pattern_log()
    results = []
    for entry in log:
        period = entry.get("period_affected", "")
        # Check if month name or number appears in the period string
        import calendar
        month_name = calendar.month_name[month].lower()
        month_abbr = calendar.month_abbr[month].lower()

        period_lower = period.lower()
        if month_name in period_lower or month_abbr in period_lower or f"/{month:02d}/" in period:
            if year is None or str(year) in period or str(year - 1) in period:
                results.append(entry)

    return results


def suggest_date_ranges(category: str, reference_date=None) -> tuple:
    """
    Auto-suggest comparison date ranges based on the pattern question category.
    Returns (period1_start, period1_end, period2_start, period2_end).
    """
    if reference_date is None:
        reference_date = datetime.now()
    ref = pd.Timestamp(reference_date)

    if category == "Before peak seasonality":
        # Compare 2 weeks before now vs same period last year
        p1_end = ref
        p1_start = ref - timedelta(days=14)
        p2_end = get_yoy_comparison_date(ref)
        p2_start = p2_end - timedelta(days=14)
    elif category == "After peak seasonality":
        # Compare last 2 weeks vs same period last year
        p1_end = ref
        p1_start = ref - timedelta(days=14)
        p2_end = get_yoy_comparison_date(ref)
        p2_start = p2_end - timedelta(days=14)
    elif category == "Normal trading period":
        # Compare last 4 weeks vs same 4 weeks last year
        p1_end = ref
        p1_start = ref - timedelta(days=28)
        p2_end = get_yoy_comparison_date(ref)
        p2_start = p2_end - timedelta(days=28)
    else:  # Investigating a specific anomaly
        # Compare last 2 weeks vs previous 2 weeks
        p1_end = ref
        p1_start = ref - timedelta(days=14)
        p2_end = ref - timedelta(days=15)
        p2_start = ref - timedelta(days=28)

    return (p1_start.date(), p1_end.date(), p2_start.date(), p2_end.date())
