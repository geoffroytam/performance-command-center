"""Bottom-up forecast model and accuracy tracking."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

from utils.calculations import calculate_baselines
from utils.constants import ROAS_TARGETS, KPI_DRIVER_TYPE, load_settings, DATA_DIR

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
        "month_name": last_month_start.strftime("%B %Y"),
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


def compute_mom_trends(
    monthly_kpis: pd.DataFrame,
    year_weights: dict = None,
    exclude_months: list = None,
) -> pd.DataFrame:
    """Compute month-over-month trends for each KPI by platform/campaign_type.

    For each consecutive pair of months (e.g., Feb → Mar) across all years,
    compute the percentage change in CPM, CTR, CVR, AOV.

    Parameters
    ----------
    monthly_kpis : pd.DataFrame
        Output of compute_monthly_kpis()
    year_weights : dict, optional
        Mapping of year (str or int) → weight, e.g. {"2025": 0.6, "2024": 0.4}.
        When provided, uses weighted average instead of simple mean.
        If None, falls back to simple mean (backward compatible).
    exclude_months : list, optional
        List of dicts with "year" and "month" keys to exclude from trend
        calculations (e.g. promotional anomalies).

    Returns a DataFrame with:
        from_month, to_month, platform, campaign_type,
        cpm_pct_change, ctr_pct_change, cvr_pct_change, aov_pct_change
    Averaged (optionally weighted) across all years of data available.
    """
    kpi_cols = ["cpm", "ctr", "cvr", "aov"]
    trend_rows = []

    # Build a set of (year, month) tuples to exclude
    excluded_set = set()
    if exclude_months:
        for ex in exclude_months:
            excluded_set.add((int(ex.get("year", 0)), int(ex.get("month", 0))))

    for (platform, ctype), group in monthly_kpis.groupby(["platform", "campaign_type"]):
        group = group.sort_values(["year", "month"])

        for _, row in group.iterrows():
            curr_year = int(row["year"])
            curr_month = int(row["month"])

            # Skip if either the source or destination month is excluded
            next_month = curr_month + 1 if curr_month < 12 else 1
            next_year = curr_year if curr_month < 12 else curr_year + 1

            if (curr_year, curr_month) in excluded_set or (next_year, next_month) in excluded_set:
                continue

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

    # Normalise year_weights keys to int for matching
    norm_weights = {}
    if year_weights:
        for k, v in year_weights.items():
            norm_weights[int(k)] = float(v)

    if norm_weights:
        # Weighted average: join weights, compute weighted mean
        trends_df["weight"] = trends_df["year"].map(norm_weights).fillna(0)

        def _weighted_mean(series, weights):
            """Weighted mean ignoring NaN values."""
            mask = series.notna()
            if mask.sum() == 0 or weights[mask].sum() == 0:
                return np.nan
            return np.average(series[mask], weights=weights[mask])

        avg_rows = []
        for keys, grp in trends_df.groupby(
            ["from_month", "to_month", "platform", "campaign_type"]
        ):
            row_dict = {
                "from_month": keys[0],
                "to_month": keys[1],
                "platform": keys[2],
                "campaign_type": keys[3],
            }
            for kpi in kpi_cols:
                col = f"{kpi}_pct_change"
                row_dict[col] = _weighted_mean(grp[col], grp["weight"])
            row_dict["n_years"] = len(grp)
            avg_rows.append(row_dict)

        avg_trends = pd.DataFrame(avg_rows)
    else:
        # Simple mean (backward compatible)
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


def compute_seasonal_indices(
    monthly_kpis: pd.DataFrame,
    platform: str,
    campaign_type: str,
    year_weights: dict = None,
    exclude_months: list = None,
) -> pd.DataFrame:
    """Compute seasonal indices for each KPI per month using Method B.

    Seasonal index = month_KPI / annual_average_KPI for that year.
    When year_weights are provided, the final index is a weighted average
    across years. Promotional anomaly months are excluded.

    Parameters
    ----------
    monthly_kpis : pd.DataFrame
        Output of compute_monthly_kpis()
    platform, campaign_type : str
        Filter for the specific slice
    year_weights : dict, optional
        e.g. {"2025": 0.6, "2024": 0.4}
    exclude_months : list, optional
        List of dicts with "year" and "month" keys to exclude

    Returns
    -------
    pd.DataFrame with columns: month (1-12), cpm_index, ctr_index, cvr_index, aov_index
    """
    kpi_cols = ["cpm", "ctr", "cvr", "aov"]
    slice_df = monthly_kpis[
        (monthly_kpis["platform"] == platform)
        & (monthly_kpis["campaign_type"] == campaign_type)
    ].copy()

    if slice_df.empty:
        return pd.DataFrame(columns=["month"] + [f"{k}_index" for k in kpi_cols])

    # Build excluded set
    excluded_set = set()
    if exclude_months:
        for ex in exclude_months:
            excluded_set.add((int(ex.get("year", 0)), int(ex.get("month", 0))))

    # Filter out excluded months
    if excluded_set:
        mask = slice_df.apply(
            lambda r: (int(r["year"]), int(r["month"])) not in excluded_set, axis=1
        )
        slice_df = slice_df[mask]

    if slice_df.empty:
        return pd.DataFrame(columns=["month"] + [f"{k}_index" for k in kpi_cols])

    # Normalise year_weights keys
    norm_weights = {}
    if year_weights:
        for k, v in year_weights.items():
            norm_weights[int(k)] = float(v)

    # Compute per-year seasonal indices
    yearly_indices = []
    for year, yr_grp in slice_df.groupby("year"):
        year_int = int(year)
        if yr_grp.shape[0] < 3:
            # Need at least 3 months to compute meaningful seasonal indices
            continue

        annual_avgs = {}
        for kpi in kpi_cols:
            vals = yr_grp[kpi].dropna()
            annual_avgs[kpi] = vals.mean() if len(vals) > 0 else np.nan

        for _, row in yr_grp.iterrows():
            month_idx = {}
            for kpi in kpi_cols:
                if pd.notna(annual_avgs[kpi]) and annual_avgs[kpi] != 0 and pd.notna(row[kpi]):
                    month_idx[f"{kpi}_index"] = row[kpi] / annual_avgs[kpi]
                else:
                    month_idx[f"{kpi}_index"] = np.nan

            yearly_indices.append({
                "year": year_int,
                "month": int(row["month"]),
                "weight": norm_weights.get(year_int, 1.0),
                **month_idx,
            })

    if not yearly_indices:
        return pd.DataFrame(columns=["month"] + [f"{k}_index" for k in kpi_cols])

    idx_df = pd.DataFrame(yearly_indices)

    # Aggregate across years (weighted or simple)
    def _weighted_mean_safe(series, weights):
        mask = series.notna()
        if mask.sum() == 0:
            return np.nan
        w = weights[mask]
        if w.sum() == 0:
            return series[mask].mean()
        return np.average(series[mask], weights=w)

    result_rows = []
    for month, m_grp in idx_df.groupby("month"):
        row = {"month": int(month)}
        for kpi in kpi_cols:
            col = f"{kpi}_index"
            if norm_weights:
                row[col] = _weighted_mean_safe(m_grp[col], m_grp["weight"])
            else:
                row[col] = m_grp[col].mean()
        result_rows.append(row)

    return pd.DataFrame(result_rows).sort_values("month").reset_index(drop=True)


def project_baselines_seasonal(
    df: pd.DataFrame,
    target_month: int,
    target_year: int,
    platform: str,
    campaign_type: str,
    seasonal_indices: pd.DataFrame,
    trailing_days: int = 90,
) -> dict:
    """Project baselines for a target month using Method B (Seasonal Index).

    Uses a trailing N-day weighted average as the reference baseline,
    then multiplies by the seasonal index for the target month.
    Each month is projected independently — no chaining or compounding.

    Parameters
    ----------
    df : pd.DataFrame
        Raw daily data
    target_month : int
        Month (1-12) to project
    target_year : int
        Year of the target month
    platform, campaign_type : str
        Filter for the specific slice
    seasonal_indices : pd.DataFrame
        Output of compute_seasonal_indices()
    trailing_days : int
        Number of days for the reference baseline window (default 90)

    Returns
    -------
    dict with keys: cpm, ctr, cvr, aov, reference_baseline, seasonal_index_used
    """
    kpi_cols = ["cpm", "ctr", "cvr", "aov"]

    # Compute the reference baseline: trailing N-day weighted ratios
    # Use data up to the 1st of target month
    cutoff = pd.Timestamp(year=target_year, month=target_month, day=1)
    window_start = cutoff - timedelta(days=trailing_days)

    slice_df = df[
        (df["platform"] == platform)
        & (df["campaign_type"] == campaign_type)
        & (df["date"] >= window_start)
        & (df["date"] < cutoff)
    ]

    ref_baseline = {}
    if slice_df.empty:
        for kpi in kpi_cols:
            ref_baseline[kpi] = np.nan
    else:
        total_spend = slice_df["spend"].sum()
        total_impressions = slice_df["impressions"].sum()
        total_clicks = slice_df["clicks"].sum()
        total_conversions = slice_df["conversions"].sum()
        total_revenue = slice_df["revenue"].sum()

        ref_baseline["cpm"] = (total_spend / total_impressions * 1000) if total_impressions > 0 else np.nan
        ref_baseline["ctr"] = (total_clicks / total_impressions * 100) if total_impressions > 0 else np.nan
        ref_baseline["cvr"] = (total_conversions / total_clicks * 100) if total_clicks > 0 else np.nan
        ref_baseline["aov"] = (total_revenue / total_conversions) if total_conversions > 0 else np.nan

    # Look up seasonal index for target month
    idx_row = seasonal_indices[seasonal_indices["month"] == target_month]
    index_used = {}
    projected = {}

    for kpi in kpi_cols:
        idx_col = f"{kpi}_index"
        if not idx_row.empty and pd.notna(idx_row.iloc[0].get(idx_col, np.nan)):
            idx_val = idx_row.iloc[0][idx_col]
            index_used[kpi] = idx_val
            if pd.notna(ref_baseline[kpi]):
                projected[kpi] = ref_baseline[kpi] * idx_val
            else:
                projected[kpi] = np.nan
        else:
            index_used[kpi] = 1.0  # Default: no seasonality adjustment
            projected[kpi] = ref_baseline.get(kpi, np.nan)

    return {
        **projected,
        "reference_baseline": ref_baseline,
        "seasonal_index_used": index_used,
        "trailing_days": trailing_days,
        "data_points": len(slice_df),
    }


def compute_confidence_bands(
    base_value: float,
    steps_forward: int,
    kpi_type: str,
    band_config: dict = None,
) -> tuple:
    """Compute confidence band (low, high) for a projected value.

    Width scales with forecast horizon and KPI type:
    - Base widths from config: 10% (1mo), 20% (2mo), 30% (3mo)
    - KPI modifier: market=1.0, account=1.3, product=0.8
    - Beyond 3 months: +5% per additional month, capped at 50%

    Parameters
    ----------
    base_value : float
        The projected value to band around
    steps_forward : int
        How many months ahead this projection is (1, 2, 3, ...)
    kpi_type : str
        One of "cpm", "ctr", "cvr", "aov" — used to look up driver type
    band_config : dict, optional
        e.g. {"1_month": 10, "2_months": 20, "3_months": 30}

    Returns
    -------
    (low, high) tuple
    """
    if pd.isna(base_value) or base_value == 0:
        return (np.nan, np.nan)

    if band_config is None:
        band_config = {"1_month": 10, "2_months": 20, "3_months": 30}

    # Base width by horizon
    if steps_forward <= 1:
        base_pct = band_config.get("1_month", 10)
    elif steps_forward == 2:
        base_pct = band_config.get("2_months", 20)
    elif steps_forward == 3:
        base_pct = band_config.get("3_months", 30)
    else:
        # Beyond 3: start from 3-month band + 5% per extra month, cap at 50%
        base_pct = min(
            band_config.get("3_months", 30) + (steps_forward - 3) * 5,
            50,
        )

    # KPI driver type modifier
    driver_type = KPI_DRIVER_TYPE.get(kpi_type, "account")
    modifier = {"market": 1.0, "account": 1.3, "product": 0.8}.get(driver_type, 1.0)

    width_pct = base_pct * modifier / 100.0

    low = base_value * (1 - width_pct)
    high = base_value * (1 + width_pct)

    return (low, high)


def compute_spend_envelope_warning(
    df: pd.DataFrame,
    planned_spend: float,
    target_month: int,
    target_year: int,
    threshold_pct: float = 20,
) -> dict:
    """Check if planned spend deviates significantly from historical pattern.

    Compares the planned MoM spend change against the historical same-period
    MoM change. Flags if the deviation is larger than threshold_pct.

    Parameters
    ----------
    df : pd.DataFrame
        Raw daily data with spend column
    planned_spend : float
        Total planned spend for the target month
    target_month : int
        Month (1-12) being forecast
    target_year : int
        Year of target month
    threshold_pct : float
        Alert if deviation exceeds this percentage (default 20%)

    Returns
    -------
    dict with keys: warning (bool), message (str), details (dict)
    """
    # Get the month before target
    if target_month == 1:
        prev_month, prev_year = 12, target_year - 1
    else:
        prev_month, prev_year = target_month - 1, target_year

    # Actual spend in the month before target
    prev_start = pd.Timestamp(year=prev_year, month=prev_month, day=1)
    prev_end = pd.Timestamp(year=target_year, month=target_month, day=1) - timedelta(days=1)
    prev_actual = df[df["date"].between(prev_start, prev_end)]["spend"].sum()

    if prev_actual == 0:
        return {
            "warning": False,
            "message": "No previous month data for comparison.",
            "details": {},
        }

    # Planned MoM change
    planned_mom_change = (planned_spend - prev_actual) / prev_actual * 100

    # Historical MoM change for the same transition across available years
    historical_changes = []
    for year_offset in [1, 2]:  # Look at last 1-2 years
        hist_year = target_year - year_offset
        hist_prev_year = prev_year - year_offset

        hist_prev_start = pd.Timestamp(year=hist_prev_year, month=prev_month, day=1)
        try:
            hist_prev_end = pd.Timestamp(year=hist_year, month=target_month, day=1) - timedelta(days=1)
            hist_curr_start = pd.Timestamp(year=hist_year, month=target_month, day=1)
            hist_curr_end = (hist_curr_start + pd.DateOffset(months=1)) - timedelta(days=1)
        except ValueError:
            continue

        hist_prev_spend = df[df["date"].between(hist_prev_start, hist_prev_end)]["spend"].sum()
        hist_curr_spend = df[df["date"].between(hist_curr_start, hist_curr_end)]["spend"].sum()

        if hist_prev_spend > 0 and hist_curr_spend > 0:
            hist_change = (hist_curr_spend - hist_prev_spend) / hist_prev_spend * 100
            historical_changes.append(hist_change)

    if not historical_changes:
        return {
            "warning": False,
            "message": "Not enough historical data to assess spend deviation.",
            "details": {"planned_mom_change_pct": round(planned_mom_change, 1)},
        }

    avg_historical_change = np.mean(historical_changes)
    deviation = abs(planned_mom_change - avg_historical_change)

    warning = deviation > threshold_pct

    msg = ""
    if warning:
        direction = "higher" if planned_mom_change > avg_historical_change else "lower"
        msg = (
            f"Planned spend change ({planned_mom_change:+.1f}% MoM) is "
            f"{deviation:.1f}pp {direction} than historical pattern "
            f"({avg_historical_change:+.1f}% MoM) for this period."
        )

    return {
        "warning": warning,
        "message": msg,
        "details": {
            "planned_mom_change_pct": round(planned_mom_change, 1),
            "historical_mom_change_pct": round(avg_historical_change, 1),
            "deviation_pp": round(deviation, 1),
            "threshold_pct": threshold_pct,
            "years_compared": len(historical_changes),
        },
    }


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
