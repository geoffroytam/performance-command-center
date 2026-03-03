"""Bottom-up forecast model and accuracy tracking."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

from utils.calculations import calculate_baselines, aggregate_by_period
from utils.constants import PLATFORMS, ROAS_TARGETS, load_settings, DATA_DIR

FORECAST_LOG_FILE = DATA_DIR / "forecast_log.json"


def load_forecast_log() -> list:
    if FORECAST_LOG_FILE.exists():
        try:
            with open(FORECAST_LOG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_forecast_log(log: list):
    FORECAST_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FORECAST_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)


def get_last_month_actuals(df: pd.DataFrame, reference_date=None) -> dict:
    """
    Get last month's actual spend per platform and total.
    """
    if reference_date is None:
        reference_date = datetime.now()
    ref = pd.Timestamp(reference_date)

    last_month_start = (ref.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = ref.replace(day=1) - timedelta(days=1)

    mask = df["date"].between(last_month_start, last_month_end)
    month_data = df[mask]

    if month_data.empty:
        return {"total_spend": 0, "platforms": {}, "empty": True}

    total = month_data["spend"].sum()
    platform_spend = month_data.groupby("platform")["spend"].sum().to_dict()
    platform_pcts = {p: s / total * 100 if total > 0 else 0 for p, s in platform_spend.items()}

    # P/R split per platform
    pr_split = {}
    for platform in month_data["platform"].unique():
        plat_data = month_data[month_data["platform"] == platform]
        plat_total = plat_data["spend"].sum()
        if plat_total > 0:
            prosp = plat_data[plat_data["campaign_type"] == "Prospecting"]["spend"].sum()
            retarg = plat_data[plat_data["campaign_type"] == "Retargeting"]["spend"].sum()
            pr_split[platform] = {
                "prospecting_pct": prosp / plat_total * 100,
                "retargeting_pct": retarg / plat_total * 100,
            }
        else:
            pr_split[platform] = {"prospecting_pct": 100, "retargeting_pct": 0}

    return {
        "total_spend": total,
        "platforms": platform_spend,
        "platform_pcts": platform_pcts,
        "pr_split": pr_split,
        "empty": False,
        "period": f"{last_month_start.strftime('%Y-%m-%d')} to {last_month_end.strftime('%Y-%m-%d')}",
    }


def compute_yoy_growth_ratio(df: pd.DataFrame, reference_date=None) -> float:
    """
    Compute the YoY growth ratio for spending (this period last year vs previous period last year).
    """
    if reference_date is None:
        reference_date = datetime.now()
    ref = pd.Timestamp(reference_date)

    # Current month last year
    try:
        curr_ly_start = ref.replace(year=ref.year - 1, day=1)
        curr_ly_end = (curr_ly_start + pd.DateOffset(months=1)) - timedelta(days=1)
        prev_ly_start = (curr_ly_start - timedelta(days=1)).replace(day=1)
        prev_ly_end = curr_ly_start - timedelta(days=1)
    except ValueError:
        return 0

    curr_ly = df[df["date"].between(curr_ly_start, curr_ly_end)]["spend"].sum()
    prev_ly = df[df["date"].between(prev_ly_start, prev_ly_end)]["spend"].sum()

    if prev_ly > 0:
        return (curr_ly - prev_ly) / prev_ly * 100
    return 0


def project_revenue(
    spend: float,
    cpm: float,
    ctr: float,
    cvr: float,
    aov: float,
) -> dict:
    """
    Bottom-up revenue projection.
    Spend -> Impressions -> Clicks -> Orders -> Revenue -> ROAS
    """
    if pd.isna(cpm) or cpm == 0:
        return {"impressions": 0, "clicks": 0, "orders": 0, "revenue": 0, "roas": 0}

    impressions = spend / cpm * 1000
    clicks = impressions * (ctr / 100) if not pd.isna(ctr) else 0
    orders = clicks * (cvr / 100) if not pd.isna(cvr) else 0
    revenue = orders * aov if not pd.isna(aov) else 0
    roas = revenue / spend if spend > 0 else 0

    return {
        "impressions": impressions,
        "clicks": clicks,
        "orders": orders,
        "revenue": revenue,
        "roas": roas,
    }


def stress_test(
    spend: float,
    cpm: float,
    ctr: float,
    cvr: float,
    aov: float,
    scenario: str,
) -> dict:
    """
    Apply stress test scenarios.
    Scenario A: CPM +15%
    Scenario B: CVR -10%
    """
    if scenario == "A":
        stressed_cpm = cpm * 1.15 if not pd.isna(cpm) else cpm
        return project_revenue(spend, stressed_cpm, ctr, cvr, aov)
    elif scenario == "B":
        stressed_cvr = cvr * 0.90 if not pd.isna(cvr) else cvr
        return project_revenue(spend, cpm, ctr, stressed_cvr, aov)
    return project_revenue(spend, cpm, ctr, cvr, aov)


def compute_forecast_accuracy(
    df: pd.DataFrame,
    forecast_month: str,
    forecast_data: dict,
) -> list:
    """
    Compare forecast vs actuals for a given month.
    forecast_data: dict with platform -> {spend, revenue, roas}
    """
    results = []
    # Parse month
    try:
        month_start = pd.Timestamp(forecast_month + "-01")
        month_end = (month_start + pd.DateOffset(months=1)) - timedelta(days=1)
    except Exception:
        return results

    actuals = df[df["date"].between(month_start, month_end)]
    if actuals.empty:
        return results

    for platform, fcast in forecast_data.items():
        plat_actuals = actuals[actuals["platform"] == platform]
        actual_spend = plat_actuals["spend"].sum()
        actual_revenue = plat_actuals["revenue"].sum()
        actual_roas = actual_revenue / actual_spend if actual_spend > 0 else 0

        fcast_spend = fcast.get("spend", 0)
        fcast_revenue = fcast.get("revenue", 0)
        fcast_roas = fcast.get("roas", 0)

        results.append({
            "platform": platform,
            "forecast_spend": fcast_spend,
            "actual_spend": actual_spend,
            "spend_delta_pct": (actual_spend - fcast_spend) / fcast_spend * 100 if fcast_spend > 0 else np.nan,
            "forecast_revenue": fcast_revenue,
            "actual_revenue": actual_revenue,
            "revenue_delta_pct": (actual_revenue - fcast_revenue) / fcast_revenue * 100 if fcast_revenue > 0 else np.nan,
            "forecast_roas": fcast_roas,
            "actual_roas": actual_roas,
            "roas_delta_pct": (actual_roas - fcast_roas) / fcast_roas * 100 if fcast_roas > 0 else np.nan,
        })

    return results
