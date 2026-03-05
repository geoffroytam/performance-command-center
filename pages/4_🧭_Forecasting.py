"""Forecasting Engine — Monthly forecast with weekly steering breakdown."""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import calendar

from utils.data_loader import load_all_data
from utils.calculations import calculate_baselines, format_currency, format_number
from utils.forecasting import (
    get_last_month_actuals,
    compute_yoy_growth_ratio,
    project_revenue,
    load_forecast_log,
    save_forecast_log,
    compute_monthly_kpis,
    compute_mom_trends,
    project_baselines_with_trends,
    get_historical_month_summary,
    compute_seasonal_indices,
    project_baselines_seasonal,
    compute_confidence_bands,
    compute_spend_envelope_warning,
)
from utils.pattern_engine import get_patterns_for_month
from utils.constants import COLORS, ROAS_TARGETS, KPI_DRIVER_TYPE, load_settings
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Forecasting", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Forecasting Engine", "Monthly forecast with weekly steering and scenario planning")

# ── Load Data ─────────────────────────────────────────────────
if "data" not in st.session_state or st.session_state.data.empty:
    df = load_all_data()
    if df.empty:
        st.warning("No data loaded. Upload CSV files from the main page.")
        st.stop()
    st.session_state.data = df

df = st.session_state.data
settings = load_settings()
max_data_date = df["date"].max()
min_data_date = df["date"].min()

# Target month selector — allow future months for upcoming forecasts
target_month = st.date_input(
    "Forecast Target Month (select any day in the target month)",
    value=datetime.now().date().replace(day=1),
)
target_month_str = target_month.strftime("%Y-%m")

# For baselines: use the latest date with actual data, not a future date
ref_date = min(pd.Timestamp(target_month), max_data_date)

# ── Determine how many months forward we need to project ──────
# The "last complete month" in data is the baseline anchor
last_complete_month_end = max_data_date
last_complete_month_num = last_complete_month_end.month
last_complete_year = last_complete_month_end.year

target_month_num = target_month.month
target_year = target_month.year

# How many month steps from the last data month to the target month
steps_forward = (target_year - last_complete_year) * 12 + (target_month_num - last_complete_month_num)

if steps_forward > 0:
    st.info(
        f"📈 Forecasting **{steps_forward} month(s) ahead** of latest data "
        f"({max_data_date.strftime('%B %Y')}). Baselines will be projected forward "
        f"using historical month-over-month trends from your data "
        f"({min_data_date.strftime('%b %Y')} – {max_data_date.strftime('%b %Y')})."
    )
elif steps_forward == 0:
    st.caption(
        f"Target month matches the latest data month. Using actual baselines from "
        f"recent data (up to {max_data_date.strftime('%d/%m/%Y')})."
    )
else:
    st.caption(
        f"Target month is in the past. Using actual baselines from the data."
    )

# Get number of days and weeks in target month
year = target_month.year
month = target_month.month
days_in_month = calendar.monthrange(year, month)[1]
month_start = pd.Timestamp(f"{year}-{month:02d}-01")
month_end = pd.Timestamp(f"{year}-{month:02d}-{days_in_month}")


# ── Build week boundaries (Mon-Sun, clipped to target month only) ──
def build_month_weeks(m_start: pd.Timestamp, m_end: pd.Timestamp) -> list:
    """Build Mon-Sun weeks clipped to month boundaries.

    If the month starts mid-week (e.g., Wednesday), W1 = Wed to Sun.
    If the month ends mid-week (e.g., Thursday), last week = Mon to Thu.
    Only includes days that belong to the target month.
    """
    weeks = []
    current = m_start
    wk = 1
    while current <= m_end:
        w_start = current
        # Find next Sunday (weekday 6) or month end
        days_until_sunday = (6 - current.weekday()) % 7
        w_end = min(current + timedelta(days=days_until_sunday), m_end)
        n_days = (w_end - w_start).days + 1
        day_names = ""
        if n_days < 7:
            start_name = w_start.strftime("%a")
            end_name = w_end.strftime("%a")
            day_names = f" ({start_name}-{end_name})"
        weeks.append({
            "week": f"W{wk}",
            "start": w_start,
            "end": w_end,
            "days": n_days,
            "label": f"W{wk} ({w_start.strftime('%d/%m')} – {w_end.strftime('%d/%m')}){day_names}",
        })
        current = w_end + timedelta(days=1)
        wk += 1
    return weeks


week_boundaries = build_month_weeks(month_start, month_end)
num_weeks = len(week_boundaries)
st.caption(
    f"Target: **{target_month.strftime('%B %Y')}** — {days_in_month} days, {num_weeks} weeks (Mon-Sun)"
)


# ── Forecast Method Selection ────────────────────────────────────
st.markdown("---")
default_method_idx = 2 if steps_forward >= 3 else 0  # "Both" for 3+ months, "Method A" otherwise
method_options = [
    "Method A (MoM Trends)",
    "Method B (Seasonal Index)",
    "Both (Show Range)",
]
forecast_method = st.radio(
    "Forecast Method",
    method_options,
    index=default_method_idx,
    horizontal=True,
    help=(
        "**Method A** chains month-over-month trend changes — best for 1-2 months ahead. "
        "**Method B** uses seasonal indices with a 90-day trailing baseline — best for 3+ months. "
        "**Both** runs both and shows the range."
    ),
)
use_method_a = forecast_method in [method_options[0], method_options[2]]
use_method_b = forecast_method in [method_options[1], method_options[2]]

# ═══════════════════════════════════════════════════════════════
# PRE-COMPUTE: Historical MoM Trends + Seasonal Indices
# ═══════════════════════════════════════════════════════════════
year_weights = settings.get("forecast_year_weights", None)
exclude_months = settings.get("forecast_promotional_anomalies", [])
band_config = settings.get("forecast_confidence_bands", {"1_month": 10, "2_months": 20, "3_months": 30})
stressed_roas_threshold = settings.get("forecast_stressed_roas_threshold", 6.0)
spend_warning_threshold = settings.get("forecast_spend_warning_threshold", 20)

monthly_kpis = compute_monthly_kpis(df)
avg_trends = compute_mom_trends(monthly_kpis, year_weights=year_weights, exclude_months=exclude_months)


# ═══════════════════════════════════════════════════════════════
# STEP 1: TOTAL COST ENVELOPE
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 1: Total Cost Envelope")

# Determine baseline spend for the total cost envelope.
# Priority: (1) actual M-1 of target, (2) projected M-1 via MoM trends,
# (3) latest actual month as fallback.
last_month = {"total_spend": 0, "platforms": {}, "platform_pcts": {}, "pr_split": {}, "empty": True}
baseline_is_projected = False

# Attempt 1: M-1 of target month (actual data)
try:
    target_m1_actuals = get_last_month_actuals(df, month_start)
    if target_m1_actuals.get("total_spend", 0) > 0:
        last_month = target_m1_actuals
except Exception:
    pass

# Attempt 2: If forecasting ahead and M-1 has no data, PROJECT M-1 using MoM trends
if (last_month.get("empty", False) or last_month["total_spend"] == 0) and steps_forward > 0:
    try:
        # Get the latest actual month's total spend as anchor
        anchor_ref = max_data_date.replace(day=1) + timedelta(days=32)
        anchor_ref = anchor_ref.replace(day=1)
        anchor_actuals = get_last_month_actuals(df, anchor_ref)
        if anchor_actuals.get("total_spend", 0) > 0:
            anchor_spend = anchor_actuals["total_spend"]
            anchor_month_num = last_complete_month_num

            # Compute aggregate spend MoM % changes from historical data
            spend_by_month = monthly_kpis.groupby(["year", "month"])["spend"].sum().reset_index()
            spend_by_month = spend_by_month.sort_values(["year", "month"])
            spend_mom = {}
            for _, row in spend_by_month.iterrows():
                yr, mo, sp = int(row["year"]), int(row["month"]), row["spend"]
                nxt_mo = mo + 1 if mo < 12 else 1
                nxt_yr = yr if mo < 12 else yr + 1
                nxt = spend_by_month[
                    (spend_by_month["year"] == nxt_yr) & (spend_by_month["month"] == nxt_mo)
                ]
                if not nxt.empty and sp > 0:
                    pct = (nxt.iloc[0]["spend"] - sp) / sp * 100
                    spend_mom.setdefault((mo, nxt_mo), []).append(pct)

            # Walk forward from anchor month to M-1 of target
            target_m1_num = target_month_num - 1 if target_month_num > 1 else 12
            projected_spend = anchor_spend
            m = anchor_month_num
            safety = 0
            while m != target_m1_num and safety < 13:
                nxt_m = m + 1 if m < 12 else 1
                key = (m, nxt_m)
                if key in spend_mom:
                    projected_spend *= (1 + np.mean(spend_mom[key]) / 100)
                m = nxt_m
                safety += 1

            target_m1_label = (month_start - timedelta(days=1)).strftime("%b %Y")
            last_month = {
                "total_spend": projected_spend,
                "platforms": anchor_actuals.get("platforms", {}),
                "platform_pcts": anchor_actuals.get("platform_pcts", {}),
                "pr_split": anchor_actuals.get("pr_split", {}),
                "empty": False,
                "month_name": target_m1_label,
            }
            baseline_is_projected = True
    except Exception:
        pass

# Attempt 3: M-1 of latest data date (fallback to actual)
if last_month.get("empty", False) or last_month["total_spend"] == 0:
    try:
        last_month = get_last_month_actuals(df, ref_date)
    except Exception:
        pass

# Attempt 4: use the month containing the latest data itself
if last_month.get("empty", False) or last_month["total_spend"] == 0:
    fallback_ref = max_data_date.replace(day=1) + timedelta(days=32)
    fallback_ref = fallback_ref.replace(day=1)
    try:
        last_month = get_last_month_actuals(df, fallback_ref)
    except Exception:
        last_month = {"total_spend": 0, "platforms": {}, "platform_pcts": {}, "pr_split": {}, "empty": True}

# Dynamic baseline label
baseline_label = last_month.get("month_name", "N/A")
if baseline_label == "N/A" and last_month.get("period"):
    try:
        baseline_label = pd.Timestamp(last_month["period"].split(" to ")[0]).strftime("%b %Y")
    except Exception:
        baseline_label = "N/A"

try:
    yoy_growth = compute_yoy_growth_ratio(df, ref_date)
except Exception:
    yoy_growth = 0.0

col1, col2, col3, col4 = st.columns([1.3, 1, 1, 1.3])

with col1:
    _base_type = "Projected" if baseline_is_projected else "Actual"
    st.metric(
        f"Baseline Spend ({baseline_label})",
        format_currency(last_month["total_spend"]),
        help=f"{_base_type} spend for {baseline_label}. "
        + ("Projected from historical MoM trends." if baseline_is_projected
           else "Actual data from the most recent complete month."),
    )
with col2:
    yoy_pct = st.number_input(
        "YoY Growth Ratio (%)",
        value=round(yoy_growth, 1),
        step=1.0,
        help="Auto-suggested from historical data",
    )
with col3:
    manual_adj = st.number_input(
        "Manual Adjustment (%)",
        value=0.0,
        step=1.0,
        help="+/- for known events (promotions, etc.)",
    )
with col4:
    base = last_month["total_spend"]
    forecasted_total = base * (1 + yoy_pct / 100) * (1 + manual_adj / 100)
    st.metric("Forecasted Total Spend", format_currency(forecasted_total))

# ── Spend Envelope Warning ──────────────────────────────────────
if forecasted_total > 0:
    envelope = compute_spend_envelope_warning(
        df,
        planned_spend=forecasted_total,
        target_month=target_month_num,
        target_year=target_year,
        threshold_pct=spend_warning_threshold,
    )
    if envelope["warning"]:
        st.warning(f"⚠️ **Spend Envelope Alert:** {envelope['message']}")
        details = envelope.get("details", {})
        if details:
            st.caption(
                f"Planned MoM change: {details.get('planned_mom_change_pct', 0):+.1f}% | "
                f"Historical pattern: {details.get('historical_mom_change_pct', 0):+.1f}% | "
                f"Deviation: {details.get('deviation_pp', 0):.1f}pp | "
                f"Based on {details.get('years_compared', 0)} year(s) of data"
            )


# ═══════════════════════════════════════════════════════════════
# STEP 2: PLATFORM ALLOCATION
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 2: Platform Allocation")
st.caption("Adjust platform share — must sum to 100%")

platform_alloc = {}
platform_forecast_spend = {}
rationale = {}

available_platforms = sorted(df["platform"].unique().tolist())

cols = st.columns(len(available_platforms))
for idx, platform in enumerate(available_platforms):
    with cols[idx]:
        last_pct = last_month.get("platform_pcts", {}).get(platform, 0)
        if last_pct == 0 and len(available_platforms) > 0:
            last_pct = 100 / len(available_platforms)
        pct = st.number_input(
            f"{platform} (%)",
            min_value=0.0,
            max_value=100.0,
            value=round(last_pct, 1),
            step=1.0,
            key=f"alloc_{platform}",
        )
        platform_alloc[platform] = pct
        platform_forecast_spend[platform] = forecasted_total * pct / 100
        rationale[platform] = st.text_input(
            "Rationale",
            placeholder="Why this allocation?",
            key=f"rat_{platform}",
        )

total_alloc = sum(platform_alloc.values())
if abs(total_alloc - 100) > 0.1:
    st.warning(f"Platform allocations sum to {total_alloc:.1f}%. They should sum to 100%.")
else:
    st.success("Allocations sum to 100%.")

alloc_rows = []
for p in available_platforms:
    alloc_rows.append({
        "Platform": p,
        "Last Month %": f"{last_month.get('platform_pcts', {}).get(p, 0):.1f}%",
        "Forecast %": f"{platform_alloc[p]:.1f}%",
        "Forecast Spend": format_currency(platform_forecast_spend[p]),
    })
st.dataframe(pd.DataFrame(alloc_rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# STEP 3: PROSPECTING / RETARGETING SPLIT
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 3: Prospecting / Retargeting Split")

pr_splits = {}
for platform in available_platforms:
    last_pr = last_month.get("pr_split", {}).get(platform, {"prospecting_pct": 70, "retargeting_pct": 30})

    is_pinterest = platform == "Pinterest" and settings.get("pinterest_always_prospecting", True)

    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(f"**{platform}**")
    with col2:
        if is_pinterest:
            st.info("Pinterest locked to 100% Prospecting")
            prosp_pct = 100.0
        else:
            prosp_pct = st.slider(
                f"Prospecting %",
                min_value=0.0,
                max_value=100.0,
                value=round(last_pr["prospecting_pct"], 0),
                step=5.0,
                key=f"pr_{platform}",
                label_visibility="collapsed",
            )

    pr_splits[platform] = {
        "prospecting_pct": prosp_pct,
        "retargeting_pct": 100 - prosp_pct,
        "prospecting_spend": platform_forecast_spend[platform] * prosp_pct / 100,
        "retargeting_spend": platform_forecast_spend[platform] * (100 - prosp_pct) / 100,
    }


# ═══════════════════════════════════════════════════════════════
# STEP 4: MONTHLY REVENUE PROJECTION (Dual Method)
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 4: Monthly Revenue Projection")

method_label = {
    method_options[0]: "Method A (MoM Trends)",
    method_options[1]: "Method B (Seasonal Index)",
    method_options[2]: "Both Methods",
}[forecast_method]

if steps_forward > 0:
    st.caption(
        f"Projecting from {max_data_date.strftime('%B %Y')} → "
        f"{target_month.strftime('%B %Y')} using **{method_label}**."
    )
else:
    cpm_days = settings.get("cpm_baseline_days", 14)
    aov_days = settings.get("aov_baseline_days", 60)
    st.caption(f"Using current baselines: {aov_days}-day AOV, {cpm_days}-day CTR/CVR/CPM")

projection_rows = []
missing_baselines = []
trend_details = {}  # Method A transparency
seasonal_details = {}  # Method B transparency
risk_alerts = []  # Risk alerts for stressed ROAS

for platform in available_platforms:
    # Pre-compute seasonal indices for Method B (per platform × campaign type)
    seasonal_cache = {}
    if use_method_b:
        for ct in ["Prospecting", "Retargeting"]:
            seasonal_cache[ct] = compute_seasonal_indices(
                monthly_kpis, platform, ct,
                year_weights=year_weights,
                exclude_months=exclude_months,
            )

    for ctype in ["Prospecting", "Retargeting"]:
        spend_key = "prospecting_spend" if ctype == "Prospecting" else "retargeting_spend"
        spend = pr_splits[platform].get(spend_key, 0)

        if spend <= 0:
            continue

        # ── Get current baselines from the latest data ──────────────
        try:
            current_baselines = calculate_baselines(df, ref_date, platform=platform, campaign_type=ctype)
        except Exception:
            current_baselines = {}

        cpm_val = current_baselines.get("cpm", np.nan)
        ctr_val = current_baselines.get("ctr", np.nan)
        cvr_val = current_baselines.get("cvr", np.nan)
        aov_val = current_baselines.get("aov", np.nan)

        if pd.isna(cpm_val) or cpm_val == 0:
            missing_baselines.append(f"{platform} {ctype}: no CPM baseline")
            continue

        # ── METHOD A: Chained MoM Trends ────────────────────────────
        method_a_proj = None
        method_a_baselines = {}
        if use_method_a and steps_forward > 0 and not avg_trends.empty:
            anchor_month = last_complete_month_num
            projected_a = project_baselines_with_trends(
                current_baselines={"cpm": cpm_val, "ctr": ctr_val, "cvr": cvr_val, "aov": aov_val},
                current_month=anchor_month,
                target_month=target_month_num,
                platform=platform,
                campaign_type=ctype,
                avg_trends=avg_trends,
            )
            a_cpm = projected_a["cpm"] if pd.notna(projected_a["cpm"]) and projected_a["cpm"] > 0 else cpm_val
            a_ctr = projected_a["ctr"] if pd.notna(projected_a["ctr"]) else ctr_val
            a_cvr = projected_a["cvr"] if pd.notna(projected_a["cvr"]) else cvr_val
            a_aov = projected_a["aov"] if pd.notna(projected_a["aov"]) else aov_val
            method_a_baselines = {"cpm": a_cpm, "ctr": a_ctr, "cvr": a_cvr, "aov": a_aov}
            method_a_proj = project_revenue(spend, a_cpm, a_ctr, a_cvr, a_aov)

            trend_details[f"{platform}_{ctype}"] = {
                "anchor_baselines": {"cpm": cpm_val, "ctr": ctr_val, "cvr": cvr_val, "aov": aov_val},
                "projected_baselines": method_a_baselines,
                "steps": projected_a["trend_steps"],
            }
        elif use_method_a:
            # No forward steps — use current baselines as Method A
            method_a_baselines = {"cpm": cpm_val, "ctr": ctr_val, "cvr": cvr_val, "aov": aov_val}
            method_a_proj = project_revenue(spend, cpm_val, ctr_val, cvr_val, aov_val)

        # ── METHOD B: Seasonal Index ────────────────────────────────
        method_b_proj = None
        method_b_baselines = {}
        if use_method_b:
            s_indices = seasonal_cache.get(ctype, pd.DataFrame())
            if not s_indices.empty:
                seasonal_result = project_baselines_seasonal(
                    df, target_month_num, target_year,
                    platform, ctype, s_indices, trailing_days=90,
                )
                b_cpm = seasonal_result.get("cpm", np.nan)
                b_ctr = seasonal_result.get("ctr", np.nan)
                b_cvr = seasonal_result.get("cvr", np.nan)
                b_aov = seasonal_result.get("aov", np.nan)

                # Fall back to current baselines where seasonal data is missing
                if pd.isna(b_cpm) or b_cpm <= 0:
                    b_cpm = cpm_val
                if pd.isna(b_ctr):
                    b_ctr = ctr_val
                if pd.isna(b_cvr):
                    b_cvr = cvr_val
                if pd.isna(b_aov):
                    b_aov = aov_val

                method_b_baselines = {"cpm": b_cpm, "ctr": b_ctr, "cvr": b_cvr, "aov": b_aov}
                method_b_proj = project_revenue(spend, b_cpm, b_ctr, b_cvr, b_aov)

                seasonal_details[f"{platform}_{ctype}"] = {
                    "reference_baseline": seasonal_result.get("reference_baseline", {}),
                    "seasonal_index_used": seasonal_result.get("seasonal_index_used", {}),
                    "trailing_days": seasonal_result.get("trailing_days", 90),
                    "data_points": seasonal_result.get("data_points", 0),
                    "projected_baselines": method_b_baselines,
                }

        # ── Choose primary projection for display ───────────────────
        # If both methods, use midpoint; otherwise use whichever is active
        if method_a_proj and method_b_proj:
            # Midpoint of the two methods
            mid_cpm = (method_a_baselines["cpm"] + method_b_baselines["cpm"]) / 2
            mid_ctr = (method_a_baselines["ctr"] + method_b_baselines["ctr"]) / 2
            mid_cvr = (method_a_baselines["cvr"] + method_b_baselines["cvr"]) / 2
            mid_aov = (method_a_baselines["aov"] + method_b_baselines["aov"]) / 2
            primary_baselines = {"cpm": mid_cpm, "ctr": mid_ctr, "cvr": mid_cvr, "aov": mid_aov}
            primary_proj = project_revenue(spend, mid_cpm, mid_ctr, mid_cvr, mid_aov)
        elif method_a_proj:
            primary_baselines = method_a_baselines
            primary_proj = method_a_proj
        elif method_b_proj:
            primary_baselines = method_b_baselines
            primary_proj = method_b_proj
        else:
            # Fallback: use current baselines
            primary_baselines = {"cpm": cpm_val, "ctr": ctr_val, "cvr": cvr_val, "aov": aov_val}
            primary_proj = project_revenue(spend, cpm_val, ctr_val, cvr_val, aov_val)

        roas_val = primary_proj["roas"]
        target_roas = ROAS_TARGETS.get(ctype, 8)
        roas_status = "above" if roas_val >= target_roas else ("near" if roas_val >= target_roas * 0.8 else "below")

        # ── Confidence bands on ROAS ────────────────────────────────
        steps_for_band = max(steps_forward, 1)
        roas_low, roas_high = compute_confidence_bands(
            roas_val, steps_for_band, "cvr", band_config
        )
        roas_range_str = f"{roas_low:.1f} – {roas_high:.1f}" if pd.notna(roas_low) else "—"

        # ── Build projection row ────────────────────────────────────
        row_data = {
            "Platform": platform,
            "Type": ctype,
            "Spend": format_currency(spend),
            "CPM": format_currency(primary_baselines["cpm"]),
            "Impressions": format_number(primary_proj["impressions"], 0),
            "CTR (LPV)": f"{primary_baselines['ctr']:.2f}%" if not pd.isna(primary_baselines["ctr"]) else "—",
            "Clicks (LPV)": format_number(primary_proj["clicks"], 0),
            "CVR (LPV)": f"{primary_baselines['cvr']:.2f}%" if not pd.isna(primary_baselines["cvr"]) else "—",
            "Orders": format_number(primary_proj["orders"], 0),
            "AOV": format_currency(primary_baselines["aov"]) if not pd.isna(primary_baselines["aov"]) else "—",
            "Revenue": format_currency(primary_proj["revenue"]),
            "ROAS": format_number(roas_val, 1),
            "ROAS Range": roas_range_str,
            "_spend": spend,
            "_baselines": primary_baselines,
            "_proj": primary_proj,
            "_roas_status": roas_status,
            "_method_a_proj": method_a_proj,
            "_method_b_proj": method_b_proj,
            "_method_a_baselines": method_a_baselines,
            "_method_b_baselines": method_b_baselines,
        }

        # Method comparison columns when using Both
        if method_a_proj and method_b_proj:
            row_data["A ROAS"] = format_number(method_a_proj["roas"], 1)
            row_data["B ROAS"] = format_number(method_b_proj["roas"], 1)

        projection_rows.append(row_data)

        # ── Risk Alert: stressed ROAS ───────────────────────────────
        # Stress test: CPM +15%, CVR -10%
        stress_proj = project_revenue(
            spend,
            primary_baselines["cpm"] * 1.15 if not pd.isna(primary_baselines["cpm"]) else np.nan,
            primary_baselines["ctr"],
            primary_baselines["cvr"] * 0.90 if not pd.isna(primary_baselines["cvr"]) else np.nan,
            primary_baselines["aov"],
        )
        if stress_proj["roas"] < stressed_roas_threshold:
            risk_alerts.append({
                "platform": platform,
                "type": ctype,
                "stressed_roas": stress_proj["roas"],
                "threshold": stressed_roas_threshold,
                "base_roas": roas_val,
            })

if missing_baselines:
    for msg in missing_baselines:
        st.warning(f"Missing baseline: {msg} — skipped from projection.")

if projection_rows:
    display_cols = [c for c in projection_rows[0].keys() if not c.startswith("_")]
    st.dataframe(
        pd.DataFrame(projection_rows)[display_cols],
        use_container_width=True,
        hide_index=True,
    )

    # Monthly totals summary
    total_spend = sum(r["_spend"] for r in projection_rows)
    total_revenue = sum(r["_proj"]["revenue"] for r in projection_rows)
    total_orders = sum(r["_proj"]["orders"] for r in projection_rows)
    total_roas = total_revenue / total_spend if total_spend > 0 else 0

    st.html(
        f'<div style="background:{COLORS["light_gray"]}; padding:14px; border-radius:8px; margin-top:8px;">'
        f'<b>Monthly Totals:</b> Spend {format_currency(total_spend)} '
        f'| Revenue {format_currency(total_revenue)} '
        f'| Orders {format_number(total_orders, 0)} '
        f'| Blended ROAS {total_roas:.1f}'
        f'</div>'
    )

    # ── Risk Alerts ──────────────────────────────────────────────
    if risk_alerts:
        st.markdown("#### ⚠️ Risk Alerts")
        for alert in risk_alerts:
            st.error(
                f"**{alert['platform']} {alert['type']}** — "
                f"Stressed ROAS ({alert['stressed_roas']:.1f}) falls below "
                f"threshold ({alert['threshold']:.1f}). "
                f"Base case ROAS is {alert['base_roas']:.1f}. "
                f"Consider reducing allocation or reviewing creative performance."
            )

    # ── YoY Comparison ─────────────────────────────────────────────
    with st.expander(f"📊 YoY Comparison — {target_month.strftime('%B %Y')} vs Last Year"):
        yoy_rows = []
        for row in projection_rows:
            plat = row["Platform"]
            ct = row["Type"]
            history = get_historical_month_summary(df, target_month_num, plat, ct)
            # Find the most recent year's data for comparison
            last_year_data = None
            for h in reversed(history):
                if h["year"] < target_year:
                    last_year_data = h
                    break

            proj_rev = row["_proj"]["revenue"]
            proj_roas = row["_proj"]["roas"]
            if last_year_data:
                ly_rev = last_year_data["revenue"]
                ly_roas = last_year_data["roas"]
                rev_yoy = ((proj_rev - ly_rev) / ly_rev * 100) if ly_rev > 0 else np.nan
                roas_yoy = ((proj_roas - ly_roas) / ly_roas * 100) if ly_roas > 0 else np.nan
                yoy_rows.append({
                    "Platform": plat,
                    "Type": ct,
                    f"Projected Rev ({target_year})": format_currency(proj_rev),
                    f"Last Year Rev ({last_year_data['year']})": format_currency(ly_rev),
                    "Revenue YoY": f"{rev_yoy:+.1f}%" if pd.notna(rev_yoy) else "—",
                    f"Projected ROAS ({target_year})": format_number(proj_roas, 1),
                    f"Last Year ROAS ({last_year_data['year']})": format_number(ly_roas, 1),
                    "ROAS YoY": f"{roas_yoy:+.1f}%" if pd.notna(roas_yoy) else "—",
                })
            else:
                yoy_rows.append({
                    "Platform": plat,
                    "Type": ct,
                    f"Projected Rev ({target_year})": format_currency(proj_rev),
                    f"Last Year Rev": "No data",
                    "Revenue YoY": "—",
                    f"Projected ROAS ({target_year})": format_number(proj_roas, 1),
                    f"Last Year ROAS": "No data",
                    "ROAS YoY": "—",
                })

        if yoy_rows:
            st.dataframe(pd.DataFrame(yoy_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No projection data for YoY comparison.")

    # ── Method A: Trend Projection Transparency ────────────────────
    if trend_details:
        with st.expander("📈 Method A — How Baselines Were Projected (MoM Trends)"):
            st.markdown(
                "Baselines are projected forward month-by-month using **weighted historical "
                "month-over-month percentage changes** observed in your data."
            )
            if year_weights:
                weight_desc = ", ".join(f"{k}: {v}" for k, v in year_weights.items())
                st.caption(f"Year weights: {weight_desc}")
            if exclude_months:
                ex_desc = ", ".join(f"{e.get('year')}/{e.get('month')} ({e.get('label', '')})" for e in exclude_months)
                st.caption(f"Excluded months: {ex_desc}")

            for key, details in trend_details.items():
                platform_label = key.replace("_", " — ", 1)
                anchor = details["anchor_baselines"]
                projected_bl = details["projected_baselines"]
                steps_list = details["steps"]

                st.markdown(f"**{platform_label}**")

                comparison_data = []
                for kpi in ["cpm", "ctr", "cvr", "aov"]:
                    a_val = anchor[kpi]
                    p_val = projected_bl[kpi]
                    if pd.notna(a_val) and pd.notna(p_val) and a_val != 0:
                        change_pct = (p_val - a_val) / a_val * 100
                        change_str = f"{change_pct:+.1f}%"
                    else:
                        change_str = "—"

                    fmt_a = format_currency(a_val) if kpi in ["cpm", "aov"] else (f"{a_val:.2f}%" if pd.notna(a_val) else "—")
                    fmt_p = format_currency(p_val) if kpi in ["cpm", "aov"] else (f"{p_val:.2f}%" if pd.notna(p_val) else "—")

                    comparison_data.append({
                        "KPI": kpi.upper(),
                        f"Anchor ({max_data_date.strftime('%b %Y')})": fmt_a,
                        f"Projected ({target_month.strftime('%b %Y')})": fmt_p,
                        "Net Change": change_str,
                    })

                st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)

                if steps_list:
                    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    step_rows = []
                    for s in steps_list:
                        from_name = month_names[s["from"] - 1]
                        to_name = month_names[s["to"] - 1]
                        step_rows.append({
                            "Transition": f"{from_name} → {to_name}",
                            "CPM Δ": s.get("cpm_change", "—"),
                            "CTR Δ": s.get("ctr_change", "—"),
                            "CVR Δ": s.get("cvr_change", "—"),
                            "AOV Δ": s.get("aov_change", "—"),
                            "Years of Data": s.get("n_years_data", 0),
                        })
                    st.dataframe(pd.DataFrame(step_rows), use_container_width=True, hide_index=True)

                st.markdown("---")

    # ── Method B: Seasonal Index Transparency ──────────────────────
    if seasonal_details:
        with st.expander("🌊 Method B — Seasonal Index Details"):
            st.markdown(
                "Seasonal indices represent each month's KPI as a fraction of the annual average. "
                "These are applied to a **trailing 90-day baseline** to project forward independently."
            )

            for key, details in seasonal_details.items():
                platform_label = key.replace("_", " — ", 1)
                ref_bl = details.get("reference_baseline", {})
                idx_used = details.get("seasonal_index_used", {})
                proj_bl = details.get("projected_baselines", {})

                st.markdown(f"**{platform_label}**")
                st.caption(
                    f"Trailing {details.get('trailing_days', 90)}-day baseline "
                    f"({details.get('data_points', 0)} data points)"
                )

                idx_rows = []
                for kpi in ["cpm", "ctr", "cvr", "aov"]:
                    ref_v = ref_bl.get(kpi, np.nan)
                    idx_v = idx_used.get(kpi, 1.0)
                    prj_v = proj_bl.get(kpi, np.nan)

                    fmt_ref = format_currency(ref_v) if kpi in ["cpm", "aov"] else (f"{ref_v:.2f}%" if pd.notna(ref_v) else "—")
                    fmt_prj = format_currency(prj_v) if kpi in ["cpm", "aov"] else (f"{prj_v:.2f}%" if pd.notna(prj_v) else "—")

                    idx_rows.append({
                        "KPI": kpi.upper(),
                        "90d Baseline": fmt_ref,
                        "Seasonal Index": f"{idx_v:.3f}" if pd.notna(idx_v) else "—",
                        f"Projected ({target_month.strftime('%b %Y')})": fmt_prj,
                        "Driver Type": KPI_DRIVER_TYPE.get(kpi, "unknown").title(),
                    })

                st.dataframe(pd.DataFrame(idx_rows), use_container_width=True, hide_index=True)
                st.markdown("---")

    # ── Historical Context ─────────────────────────────────────────
    with st.expander(f"📊 Historical Performance for {target_month.strftime('%B')} (Past Years)"):
        st.markdown(
            f"What happened in **{target_month.strftime('%B')}** in previous years? "
            f"Use this to validate whether the projections make sense."
        )
        for platform in available_platforms:
            for ctype in ["Prospecting", "Retargeting"]:
                history = get_historical_month_summary(df, target_month_num, platform, ctype)
                if history:
                    st.markdown(f"**{platform} — {ctype}**")
                    hist_rows = []
                    for h in history:
                        hist_rows.append({
                            "Year": h["year"],
                            "Spend": format_currency(h["spend"]),
                            "Revenue": format_currency(h["revenue"]),
                            "Orders": format_number(h["orders"], 0),
                            "ROAS": format_number(h["roas"], 1),
                            "CPM": format_currency(h["cpm"]),
                            "CTR": f"{h['ctr']:.2f}%" if pd.notna(h["ctr"]) else "—",
                            "CVR": f"{h['cvr']:.2f}%" if pd.notna(h["cvr"]) else "—",
                            "AOV": format_currency(h["aov"]),
                        })
                    st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)

    # ── Calculation breakdown (collapsible) ────────────────────────
    with st.expander("How These Numbers Are Calculated"):
        st.markdown(
f"""**Bottom-up funnel model:**

```
Spend / CPM x 1,000 = Impressions
Impressions x CTR (LPV) = Landing Page Views
LPV x CVR (LPV) = Orders
Orders x AOV = Revenue
Revenue / Spend = ROAS
```

**Baseline sources:**
- **Current month or past month:** Uses rolling averages from actual data (CPM/CTR/CVR: {settings.get('cpm_baseline_days', 14)}-day, AOV: {settings.get('aov_baseline_days', 60)}-day).
- **Method A (MoM Trends):** Starts from the latest rolling averages, then chains historical month-over-month trends forward.
- **Method B (Seasonal Index):** Uses a 90-day trailing baseline multiplied by the seasonal index for the target month.
- **Both:** Shows midpoint when both methods are selected.
- Confidence bands widen with forecast distance and KPI driver type (market / account / product)."""
        )

        for row in projection_rows:
            b = row["_baselines"]
            p = row["_proj"]
            s = row["_spend"]
            with st.expander(f"{row['Platform']} — {row['Type']}"):
                st.markdown(
                    f"1. {format_currency(s)} / {format_currency(b.get('cpm', 0))} x 1,000 = **{p['impressions']:,.0f}** impressions\n"
                    f"2. {p['impressions']:,.0f} x {b.get('ctr', 0):.2f}% = **{p['clicks']:,.0f}** clicks\n"
                    f"3. {p['clicks']:,.0f} x {b.get('cvr', 0):.2f}% = **{p['orders']:,.0f}** orders\n"
                    f"4. {p['orders']:,.0f} x {format_currency(b.get('aov', 0))} = **{format_currency(p['revenue'])}**\n"
                    f"5. {format_currency(p['revenue'])} / {format_currency(s)} = **ROAS {p['roas']:.1f}**"
                )
else:
    st.warning("No projections could be calculated. Check that baseline data is available.")


# ═══════════════════════════════════════════════════════════════
# STEP 5: WEEKLY STEERING PLAN
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 5: Weekly Steering Plan")
st.caption(
    "Break the monthly forecast into weekly targets (Mon-Sun). "
    "Adjust weekly weights for seasonality or promotions."
)

if projection_rows:
    # Default: distribute proportionally by number of days in each week
    default_week_pcts = [wb["days"] / days_in_month * 100 for wb in week_boundaries]

    st.markdown("**Weekly spend distribution (%)**")
    st.caption("Default is proportional to days. Adjust if you expect heavier spend in certain weeks.")

    week_pcts = []
    week_cols = st.columns(num_weeks)
    for i, wb in enumerate(week_boundaries):
        with week_cols[i]:
            pct = st.number_input(
                wb["label"],
                min_value=0.0,
                max_value=100.0,
                value=round(default_week_pcts[i], 1),
                step=1.0,
                key=f"week_pct_{i}",
            )
            week_pcts.append(pct)

    total_week_pct = sum(week_pcts)
    if abs(total_week_pct - 100) > 0.5:
        st.warning(f"Weekly weights sum to {total_week_pct:.1f}%. Should sum to 100%.")

    # Build weekly steering table
    weekly_steering = []
    for i, wb in enumerate(week_boundaries):
        w_factor = week_pcts[i] / 100 if total_week_pct > 0 else 1 / num_weeks
        w_spend = total_spend * w_factor
        w_revenue = total_revenue * w_factor
        w_orders = total_orders * w_factor
        w_roas = w_revenue / w_spend if w_spend > 0 else 0

        weekly_steering.append({
            "Week": wb["label"],
            "Days": wb["days"],
            "Weight": f"{week_pcts[i]:.1f}%",
            "Spend Target": format_currency(w_spend),
            "Daily Spend": format_currency(w_spend / wb["days"]) if wb["days"] > 0 else "—",
            "Revenue Target": format_currency(w_revenue),
            "Orders Target": format_number(w_orders, 0),
            "ROAS Target": format_number(w_roas, 1),
            "_spend": w_spend,
            "_revenue": w_revenue,
        })

    st.dataframe(
        pd.DataFrame(weekly_steering)[[c for c in weekly_steering[0] if not c.startswith("_")]],
        use_container_width=True,
        hide_index=True,
    )

    # Weekly steering guidance
    st.markdown("**Steering Rules:**")
    st.markdown(
        f"- If weekly spend is **ahead of target by >10%**, reduce daily budgets to pace back\n"
        f"- If weekly spend is **behind target by >10%**, evaluate whether to increase or let it ride\n"
        f"- If ROAS drops below **{min(ROAS_TARGETS.values()) * 0.8:.0f}** mid-week, pause lowest-performing ad sets\n"
        f"- Review performance every **Monday** and adjust budgets for the upcoming week"
    )


# ═══════════════════════════════════════════════════════════════
# STEP 6: SCENARIO PLANNING (Conservative / Base / Optimistic)
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 6: Scenario Planning")
st.caption(
    "Three scenarios to prepare for different market conditions. "
    "Conservative = costs rise & conversion drops. Optimistic = costs drop & conversion improves."
)

if projection_rows:
    col_con, col_base, col_opt = st.columns(3)

    with col_con:
        st.html(
            f'<div style="text-align:center; padding:8px; background:#FDF6F0; border-radius:8px; '
            f'border-top:3px solid {COLORS["red"]};">'
            f'<b>Conservative</b><br/><span style="font-size:0.8rem;">CPM +15%, CVR -10%</span></div>'
        )
    with col_base:
        st.html(
            f'<div style="text-align:center; padding:8px; background:{COLORS["light_gray"]}; border-radius:8px; '
            f'border-top:3px solid {COLORS["blue"]};">'
            f'<b>Base Case</b><br/><span style="font-size:0.8rem;">Current baselines</span></div>'
        )
    with col_opt:
        st.html(
            f'<div style="text-align:center; padding:8px; background:#F0F5F1; border-radius:8px; '
            f'border-top:3px solid {COLORS["green"]};">'
            f'<b>Optimistic</b><br/><span style="font-size:0.8rem;">CPM -10%, CVR +10%</span></div>'
        )

    scenario_rows = []
    totals = {"conservative": {"spend": 0, "revenue": 0, "orders": 0},
              "base": {"spend": 0, "revenue": 0, "orders": 0},
              "optimistic": {"spend": 0, "revenue": 0, "orders": 0}}

    for row in projection_rows:
        b = row["_baselines"]
        spend = row["_spend"]
        cpm = b.get("cpm", np.nan)
        ctr = b.get("ctr", np.nan)
        cvr = b.get("cvr", np.nan)
        aov = b.get("aov", np.nan)

        cons = project_revenue(
            spend,
            cpm * 1.15 if not pd.isna(cpm) else cpm,
            ctr,
            cvr * 0.90 if not pd.isna(cvr) else cvr,
            aov,
        )
        base_proj = row["_proj"]
        opt = project_revenue(
            spend,
            cpm * 0.90 if not pd.isna(cpm) else cpm,
            ctr,
            cvr * 1.10 if not pd.isna(cvr) else cvr,
            aov,
        )

        target_roas = ROAS_TARGETS.get(row["Type"], 8)
        flag_cons = "!!" if cons["roas"] < target_roas * 0.75 else ("!" if cons["roas"] < target_roas else "")

        scenario_rows.append({
            "Platform": row["Platform"],
            "Type": row["Type"],
            "Conservative ROAS": f"{'** ' if flag_cons else ''}{format_number(cons['roas'], 1)}{' **' if flag_cons else ''}",
            "Conservative Rev.": format_currency(cons["revenue"]),
            "Base ROAS": format_number(base_proj["roas"], 1),
            "Base Revenue": format_currency(base_proj["revenue"]),
            "Optimistic ROAS": format_number(opt["roas"], 1),
            "Optimistic Rev.": format_currency(opt["revenue"]),
        })

        for scenario, proj in [("conservative", cons), ("base", base_proj), ("optimistic", opt)]:
            totals[scenario]["spend"] += spend
            totals[scenario]["revenue"] += proj["revenue"]
            totals[scenario]["orders"] += proj["orders"]

    st.dataframe(pd.DataFrame(scenario_rows), use_container_width=True, hide_index=True)

    # Scenario totals
    col1, col2, col3 = st.columns(3)
    for col, scenario, bg, color in [
        (col1, "conservative", "#FDF6F0", COLORS["red"]),
        (col2, "base", COLORS["light_gray"], COLORS["blue"]),
        (col3, "optimistic", "#F0F5F1", COLORS["green"]),
    ]:
        s_roas = totals[scenario]["revenue"] / totals[scenario]["spend"] if totals[scenario]["spend"] > 0 else 0
        label = scenario.title().replace("Base", "Base Case")
        with col:
            st.html(
                f'<div style="background:{bg}; padding:12px; border-radius:8px; text-align:center;">'
                f'<div style="color:{color}; font-weight:700;">{label}</div>'
                f'<div style="font-size:1.2rem; font-weight:700;">ROAS {s_roas:.1f}</div>'
                f'<div style="font-size:0.85rem;">{format_currency(totals[scenario]["revenue"])} revenue</div>'
                f'<div style="font-size:0.85rem;">{totals[scenario]["orders"]:,.0f} orders</div>'
                f'</div>'
            )


# ═══════════════════════════════════════════════════════════════
# STEP 7: PATTERN LOG CROSS-CHECK
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 7: Pattern Log Cross-Check")

patterns = get_patterns_for_month(target_month.month)
if patterns:
    st.markdown(f"**Found {len(patterns)} pattern(s) relevant to {target_month.strftime('%B')}:**")
    for p in patterns:
        with st.expander(f"{p.get('date_observed', '')} — {p.get('what_happened', '')[:80]}"):
            st.markdown(f"**Rule:** {p.get('rule_for_next_time', 'N/A')}")
            st.markdown(f"**True Driver:** {p.get('true_driver', 'N/A')}")
            st.markdown(f"**Should Have Done:** {p.get('what_we_should_have_done', 'N/A')}")
else:
    st.info("No pattern log entries found for this month. Build your pattern log in the Pattern Finder page.")


# ═══════════════════════════════════════════════════════════════
# FORECAST SUMMARY & SAVE
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Forecast Summary")

if projection_rows:
    summary_rows = []
    for row in projection_rows:
        b = row["_baselines"]
        cpm = b.get("cpm", np.nan)
        cvr = b.get("cvr", np.nan)

        cons_roas = project_revenue(
            row["_spend"],
            cpm * 1.15 if not pd.isna(cpm) else np.nan,
            b.get("ctr", np.nan),
            cvr * 0.90 if not pd.isna(cvr) else np.nan,
            b.get("aov", np.nan),
        )["roas"]

        opt_roas = project_revenue(
            row["_spend"],
            cpm * 0.90 if not pd.isna(cpm) else np.nan,
            b.get("ctr", np.nan),
            cvr * 1.10 if not pd.isna(cvr) else np.nan,
            b.get("aov", np.nan),
        )["roas"]

        summary_rows.append({
            "Platform": row["Platform"],
            "Type": row["Type"],
            "Spend": row["Spend"],
            "Projected Revenue": row["Revenue"],
            "Projected ROAS": row["ROAS"],
            "Conservative ROAS": format_number(cons_roas, 1),
            "Optimistic ROAS": format_number(opt_roas, 1),
        })

    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # Save forecast
    if st.button("Save Forecast", type="primary"):
        forecast_entry = {
            "month": target_month_str,
            "method": forecast_method,
            "total_spend": forecasted_total,
            "platform_allocation": platform_alloc,
            "pr_splits": {p: {"prospecting_pct": s["prospecting_pct"]} for p, s in pr_splits.items()},
            "projections": [
                {
                    "platform": r["Platform"],
                    "type": r["Type"],
                    "spend": r["_spend"],
                    "revenue": r["_proj"]["revenue"],
                    "roas": r["_proj"]["roas"],
                    "orders": r["_proj"]["orders"],
                    "method_a_roas": r["_method_a_proj"]["roas"] if r.get("_method_a_proj") else None,
                    "method_b_roas": r["_method_b_proj"]["roas"] if r.get("_method_b_proj") else None,
                }
                for r in projection_rows
            ],
            "weekly_steering": [
                {
                    "week": wb["label"],
                    "weight_pct": week_pcts[i] if i < len(week_pcts) else 0,
                    "spend_target": total_spend * (week_pcts[i] if i < len(week_pcts) else 0) / 100,
                }
                for i, wb in enumerate(week_boundaries)
            ] if 'week_pcts' in locals() else [],
            "trend_details": {
                k: {
                    "anchor": v["anchor_baselines"],
                    "projected": v["projected_baselines"],
                }
                for k, v in trend_details.items()
            } if trend_details else {},
            "seasonal_details": {
                k: {
                    "reference_baseline": v.get("reference_baseline", {}),
                    "seasonal_index_used": v.get("seasonal_index_used", {}),
                }
                for k, v in seasonal_details.items()
            } if seasonal_details else {},
            "risk_alerts": [
                {
                    "platform": a["platform"],
                    "type": a["type"],
                    "stressed_roas": round(a["stressed_roas"], 2),
                }
                for a in risk_alerts
            ] if risk_alerts else [],
            "timestamp": datetime.now().isoformat(),
        }
        log = load_forecast_log()
        log = [e for e in log if e.get("month") != target_month_str]
        log.append(forecast_entry)
        save_forecast_log(log)
        st.success(f"Forecast saved for {target_month_str}.")


# ═══════════════════════════════════════════════════════════════
# FORECAST vs ACTUALS — Manual Input + Auto-comparison
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Forecast vs Actuals")
st.caption(
    "When the month is complete, enter actual values here to compare against your forecast. "
    "If the data is already uploaded, actuals are calculated automatically."
)

forecast_log = load_forecast_log()
saved_months = sorted(set(e.get("month", "") for e in forecast_log if e.get("month")), reverse=True)

if saved_months:
    selected_fcast_month = st.selectbox("Select forecast month", saved_months)
    fcast_entry = next((e for e in forecast_log if e.get("month") == selected_fcast_month), None)

    if fcast_entry:
        projections = fcast_entry.get("projections", [])

        # Auto-calculate actuals from uploaded data
        try:
            month_start_ts = pd.Timestamp(selected_fcast_month + "-01")
            month_end_ts = (month_start_ts + pd.DateOffset(months=1)) - timedelta(days=1)
            actuals_df = df[df["date"].between(month_start_ts, month_end_ts)]
            has_actuals_data = not actuals_df.empty
        except Exception:
            has_actuals_data = False

        if has_actuals_data:
            st.markdown("**Auto-calculated from uploaded data:**")
            comparison_rows = []
            for proj in projections:
                plat = proj["platform"]
                plat_actuals = actuals_df[actuals_df["platform"] == plat]
                actual_spend = plat_actuals["spend"].sum()
                actual_revenue = plat_actuals["revenue"].sum()
                actual_roas = actual_revenue / actual_spend if actual_spend > 0 else 0

                fcast_spend = proj.get("spend", 0)
                fcast_revenue = proj.get("revenue", 0)
                fcast_roas = proj.get("roas", 0)

                comparison_rows.append({
                    "Platform": plat,
                    "Type": proj.get("type", ""),
                    "Forecast Spend": format_currency(fcast_spend),
                    "Actual Spend": format_currency(actual_spend),
                    "Spend Delta": f"{(actual_spend - fcast_spend) / fcast_spend * 100:+.1f}%" if fcast_spend > 0 else "—",
                    "Forecast Revenue": format_currency(fcast_revenue),
                    "Actual Revenue": format_currency(actual_revenue),
                    "Rev. Delta": f"{(actual_revenue - fcast_revenue) / fcast_revenue * 100:+.1f}%" if fcast_revenue > 0 else "—",
                    "Forecast ROAS": format_number(fcast_roas, 1),
                    "Actual ROAS": format_number(actual_roas, 1),
                })

            st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True, hide_index=True)
        else:
            st.info(f"No actual data uploaded yet for {selected_fcast_month}. Upload the month's data or enter actuals manually below.")

        # Manual actuals input
        with st.expander("Enter Actuals Manually"):
            st.caption("Use this if the month is complete but data hasn't been uploaded yet.")
            for proj in projections:
                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.markdown(f"**{proj['platform']} {proj.get('type', '')}**")
                with col_b:
                    m_spend = st.number_input(
                        "Actual Spend",
                        value=0.0,
                        step=100.0,
                        key=f"man_spend_{proj['platform']}_{proj.get('type', '')}",
                    )
                with col_c:
                    m_revenue = st.number_input(
                        "Actual Revenue",
                        value=0.0,
                        step=100.0,
                        key=f"man_rev_{proj['platform']}_{proj.get('type', '')}",
                    )
                with col_d:
                    m_roas = m_revenue / m_spend if m_spend > 0 else 0
                    st.metric("Actual ROAS", format_number(m_roas, 1))
else:
    st.info("No forecasts saved yet. Save a forecast above to start tracking accuracy.")
