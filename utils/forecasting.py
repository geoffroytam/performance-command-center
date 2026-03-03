"""Bottom-up forecast model and accuracy tracking."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

from utils.calculations import calculate_baselines
from utils.constants import ROAS_TARGETS, load_settings, DATA_DIR

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


def compute_monthly_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw data into monthly KPIs by platform and campaign_type.

    Returns a DataFrame with columns:
        year, month, platform, campaign_type, spend, impressions, clicks,
        conversions, revenue, cpm, ctr, cvr, aov, roas
    """
    tmp = df.copy()
    tmp["year"] = tmp["date"].dt.year
    tmp["month"] = tmp["date"].dt.month

    agg = (
        tmp.groupby(["year", "month", "platform", "campaign_type"])
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

    return agg.sort_values(["platform", "campaign_type", "year", "month"])


def compute_mom_trends(monthly_kpis: pd.DataFrame) -> pd.DataFrame:
    """Compute month-over-month trends for each KPI by platform/campaign_type.

    For each consecutive pair of months (e.g., Feb → Mar) across all years,
    compute the percentage change in CPM, CTR, CVR, AOV.

    Returns a DataFrame with:
        from_month, to_month, platform, campaign_type,
        cpm_pct_change, ctr_pct_change, cvr_pct_change, aov_pct_change
    Averaged across all years of data available.
    """
    kpi_cols = ["cpm", "ctr", "cvr", "aov"]
    trend_rows = []

    for (platform, ctype), group in monthly_kpis.groupby(["platform", "campaign_type"]):
        group = group.sort_values(["year", "month"])

        for _, row in group.iterrows():
            curr_year = row["year"]
            curr_month = row["month"]
            # Find the next month in the same year, or Jan of next year
            next_month = curr_month + 1 if curr_month < 12 else 1
            next_year = curr_year if curr_month < 12 else curr_year + 1

            next_row = group[
                (group["year"] == next_year) & (group["month"] == next_month)
            ]
            if next_row.empty:
                continue
            next_row = next_row.iloc[0]

            changes = {}
            for kpi in kpi_cols:
                curr_val = row[kpi]
                next_val = next_row[kpi]
                if pd.notna(curr_val) and pd.notna(next_val) and curr_val != 0:
                    changes[f"{kpi}_pct_change"] = (next_val - curr_val) / curr_val * 100
                else:
                    changes[f"{kpi}_pct_change"] = np.nan

            trend_rows.append({
                "from_month": curr_month,
                "to_month": next_month,
                "platform": platform,
                "campaign_type": ctype,
                "year": curr_year,
                **changes,
            })

    if not trend_rows:
        return pd.DataFrame()

    trends_df = pd.DataFrame(trend_rows)

    # Average across all years for each from_month → to_month transition
    avg_trends = (
        trends_df
        .groupby(["from_month", "to_month", "platform", "campaign_type"])
        .agg(
            cpm_pct_change=("cpm_pct_change", "mean"),
            ctr_pct_change=("ctr_pct_change", "mean"),
            cvr_pct_change=("cvr_pct_change", "mean"),
            aov_pct_change=("aov_pct_change", "mean"),
            n_years=("year", "count"),
        )
        .reset_index()
    )

    return avg_trends


def project_baselines_with_trends(
    current_baselines: dict,
    current_month: int,
    target_month: int,
    platform: str,
    campaign_type: str,
    avg_trends: pd.DataFrame,
) -> dict:
    """Project baselines from a known month to a target month using historical MoM trends.

    Walks month-by-month from current_month to target_month, applying the average
    MoM percentage change for each KPI at each step.

    Parameters
    ----------
    current_baselines : dict
        Known baselines with keys: cpm, ctr, cvr, aov
    current_month : int
        The month number (1-12) of the known baselines
    target_month : int
        The month number (1-12) we're projecting to
    platform, campaign_type : str
        Used to look up the correct trends
    avg_trends : pd.DataFrame
        Output of compute_mom_trends()

    Returns
    -------
    dict with keys: cpm, ctr, cvr, aov (projected values)
    plus trend_steps: list of dicts describing each step for transparency
    """
    kpi_cols = ["cpm", "ctr", "cvr", "aov"]
    projected = {k: current_baselines.get(k, np.nan) for k in kpi_cols}
    steps = []

    # Walk month by month
    m = current_month
    while m != target_month:
        next_m = m + 1 if m < 12 else 1

        # Look up the trend for this transition
        trend_row = avg_trends[
            (avg_trends["from_month"] == m)
            & (avg_trends["to_month"] == next_m)
            & (avg_trends["platform"] == platform)
            & (avg_trends["campaign_type"] == campaign_type)
        ]

        step_info = {"from": m, "to": next_m}

        if not trend_row.empty:
            tr = trend_row.iloc[0]
            n_years = int(tr.get("n_years", 0))
            for kpi in kpi_cols:
                pct_change = tr.get(f"{kpi}_pct_change", np.nan)
                if pd.notna(pct_change) and pd.notna(projected[kpi]):
                    old_val = projected[kpi]
                    projected[kpi] = old_val * (1 + pct_change / 100)
                    step_info[f"{kpi}_change"] = f"{pct_change:+.1f}%"
                else:
                    step_info[f"{kpi}_change"] = "no data"
            step_info["n_years_data"] = n_years
        else:
            # No trend data for this transition — keep values unchanged
            for kpi in kpi_cols:
                step_info[f"{kpi}_change"] = "no trend data"
            step_info["n_years_data"] = 0

        steps.append(step_info)
        m = next_m

        # Safety: break if we've gone around the full year
        if len(steps) > 12:
            break

    return {
        **projected,
        "trend_steps": steps,
    }


def get_historical_month_summary(
    df: pd.DataFrame, target_month: int, platform: str, campaign_type: str,
) -> list:
    """Get KPI summary for a specific month across all available years.

    Useful for showing the user what happened in e.g. March 2024, March 2025, etc.
    """
    tmp = df.copy()
    tmp["year"] = tmp["date"].dt.year
    tmp["month"] = tmp["date"].dt.month

    month_data = tmp[
        (tmp["month"] == target_month)
        & (tmp["platform"] == platform)
        & (tmp["campaign_type"] == campaign_type)
    ]

    if month_data.empty:
        return []

    results = []
    for year, grp in month_data.groupby("year"):
        spend = grp["spend"].sum()
        impressions = grp["impressions"].sum()
        clicks = grp["clicks"].sum()
        conversions = grp["conversions"].sum()
        revenue = grp["revenue"].sum()

        results.append({
            "year": int(year),
            "spend": spend,
            "revenue": revenue,
            "orders": conversions,
            "cpm": spend / impressions * 1000 if impressions > 0 else np.nan,
            "ctr": clicks / impressions * 100 if impressions > 0 else np.nan,
            "cvr": conversions / clicks * 100 if clicks > 0 else np.nan,
            "aov": revenue / conversions if conversions > 0 else np.nan,
            "roas": revenue / spend if spend > 0 else np.nan,
        })

    return sorted(results, key=lambda x: x["year"])


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
