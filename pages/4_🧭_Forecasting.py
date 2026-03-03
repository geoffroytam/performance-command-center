"""Forecasting Engine — Bottom-up forecasting following the 6-step method."""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

from utils.data_loader import load_all_data
from utils.calculations import calculate_baselines, format_currency, format_number
from utils.forecasting import (
    get_last_month_actuals,
    compute_yoy_growth_ratio,
    project_revenue,
    stress_test,
    load_forecast_log,
    save_forecast_log,
    compute_forecast_accuracy,
)
from utils.pattern_engine import get_patterns_for_month
from utils.constants import COLORS, PLATFORMS, ROAS_TARGETS, load_settings
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Forecasting", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Forecasting Engine", "Bottom-up forecasting with stress testing and pattern log cross-check")

# ── Load Data ─────────────────────────────────────────────────
if "data" not in st.session_state or st.session_state.data.empty:
    df = load_all_data()
    if df.empty:
        st.warning("No data loaded. Upload CSV files from the main page.")
        st.stop()
    st.session_state.data = df

df = st.session_state.data
settings = load_settings()

# Target month selector
target_month = st.date_input(
    "Forecast Target Month (select any day in the target month)",
    value=datetime.now().date().replace(day=1),
)
target_month_str = target_month.strftime("%Y-%m")
ref_date = pd.Timestamp(target_month)

# ── Step 1: Total Cost Envelope ───────────────────────────────
st.markdown("---")
st.subheader("Step 1: Total Cost Envelope")

last_month = get_last_month_actuals(df, ref_date)
yoy_growth = compute_yoy_growth_ratio(df, ref_date)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Last Month Actual Spend", format_currency(last_month["total_spend"]))
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

# ── Step 2: Platform Allocation ───────────────────────────────
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

# Display table
alloc_rows = []
for p in available_platforms:
    alloc_rows.append({
        "Platform": p,
        "Last Month %": f"{last_month.get('platform_pcts', {}).get(p, 0):.1f}%",
        "Forecast %": f"{platform_alloc[p]:.1f}%",
        "Forecast Spend": format_currency(platform_forecast_spend[p]),
    })
st.dataframe(pd.DataFrame(alloc_rows), use_container_width=True, hide_index=True)

# ── Step 3: Prospecting / Retargeting Split ───────────────────
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

# ── Step 4: Revenue Projection ───────────────────────────────
st.markdown("---")
st.subheader("Step 4: Revenue Projection")
st.caption("Using current baselines: 60-day AOV, 14-day CTR (LPV) / CVR (LPV) / CPM")

projection_rows = []
for platform in available_platforms:
    for ctype in ["Prospecting", "Retargeting"]:
        spend_key = "prospecting_spend" if ctype == "Prospecting" else "retargeting_spend"
        spend = pr_splits[platform].get(spend_key, 0)

        if spend <= 0:
            continue

        baselines = calculate_baselines(df, ref_date, platform=platform, campaign_type=ctype)

        proj = project_revenue(
            spend,
            baselines.get("cpm", np.nan),
            baselines.get("ctr", np.nan),
            baselines.get("cvr", np.nan),
            baselines.get("aov", np.nan),
        )

        projection_rows.append({
            "Platform": platform,
            "Type": ctype,
            "Spend": format_currency(spend),
            "CPM": format_currency(baselines.get("cpm", np.nan)),
            "Impressions": format_number(proj["impressions"], 0),
            "CTR (LPV)": f"{baselines.get('ctr', 0):.2f}%",
            "Clicks (LPV)": format_number(proj["clicks"], 0),
            "CVR (LPV)": f"{baselines.get('cvr', 0):.2f}%",
            "Orders": format_number(proj["orders"], 0),
            "AOV": format_currency(baselines.get("aov", np.nan)),
            "Revenue": format_currency(proj["revenue"]),
            "ROAS": format_number(proj["roas"], 1),
            "_spend": spend,
            "_baselines": baselines,
            "_proj": proj,
        })

if projection_rows:
    display_cols = [c for c in projection_rows[0].keys() if not c.startswith("_")]
    st.dataframe(
        pd.DataFrame(projection_rows)[display_cols],
        use_container_width=True,
        hide_index=True,
    )

    # ── Transparent Calculation Breakdown ─────────────────────
    st.markdown("---")
    st.markdown("#### 🔍 How These Numbers Are Calculated")
    cpm_days = settings.get("cpm_baseline_days", 14)
    aov_days = settings.get("aov_baseline_days", 60)

    st.markdown(
f"""The revenue projection follows a **bottom-up funnel model**. Each step feeds into the next,
using your actual baseline metrics from the data. Here is the exact formula chain:

```
Spend ÷ CPM × 1,000 = Impressions
Impressions × CTR (LPV) = Landing Page Views (Clicks)
Landing Page Views × CVR (LPV) = Orders (Purchases)
Orders × AOV = Revenue
Revenue ÷ Spend = ROAS
```

**Baseline sources:**
- **CPM** — {cpm_days}-day rolling average (weighted: total spend ÷ total impressions × 1000)
- **CTR (LPV)** — {cpm_days}-day rolling average (weighted: total LPV ÷ total impressions × 100)
- **CVR (LPV)** — {cpm_days}-day rolling average (weighted: total purchases ÷ total LPV × 100)
- **AOV** — {aov_days}-day rolling average (weighted: total revenue ÷ total purchases)"""
    )

    # Detailed step-by-step for each platform/type
    for row in projection_rows:
        platform = row["Platform"]
        ctype = row["Type"]
        spend = row["_spend"]
        baselines = row["_baselines"]
        proj = row["_proj"]

        b_cpm = baselines.get("cpm", np.nan)
        b_ctr = baselines.get("ctr", np.nan)
        b_cvr = baselines.get("cvr", np.nan)
        b_aov = baselines.get("aov", np.nan)

        with st.expander(f"📐 {platform} — {ctype} — Step-by-step calculation"):
            st.markdown(f"**Input Spend:** {format_currency(spend)}")
            st.markdown("")

            # Step 1: Impressions
            if not pd.isna(b_cpm) and b_cpm > 0:
                impressions_calc = spend / b_cpm * 1000
                st.markdown(
                    f"**Step 1 — Impressions:**  \n"
                    f"`{format_currency(spend)} ÷ {format_currency(b_cpm)} (CPM) × 1,000 = "
                    f"{impressions_calc:,.0f} impressions`"
                )
            else:
                impressions_calc = 0
                st.warning("CPM baseline not available — cannot compute impressions.")

            # Step 2: Clicks (LPV)
            if not pd.isna(b_ctr) and impressions_calc > 0:
                clicks_calc = impressions_calc * (b_ctr / 100)
                st.markdown(
                    f"**Step 2 — Landing Page Views (Clicks):**  \n"
                    f"`{impressions_calc:,.0f} impressions × {b_ctr:.2f}% (CTR) = "
                    f"{clicks_calc:,.0f} LPV`"
                )
            else:
                clicks_calc = 0
                st.warning("CTR baseline not available — cannot compute clicks.")

            # Step 3: Orders
            if not pd.isna(b_cvr) and clicks_calc > 0:
                orders_calc = clicks_calc * (b_cvr / 100)
                st.markdown(
                    f"**Step 3 — Orders (Purchases):**  \n"
                    f"`{clicks_calc:,.0f} LPV × {b_cvr:.2f}% (CVR) = "
                    f"{orders_calc:,.0f} orders`"
                )
            else:
                orders_calc = 0
                st.warning("CVR baseline not available — cannot compute orders.")

            # Step 4: Revenue
            if not pd.isna(b_aov) and orders_calc > 0:
                revenue_calc = orders_calc * b_aov
                st.markdown(
                    f"**Step 4 — Revenue:**  \n"
                    f"`{orders_calc:,.0f} orders × {format_currency(b_aov)} (AOV) = "
                    f"{format_currency(revenue_calc)}`"
                )
            else:
                revenue_calc = 0
                st.warning("AOV baseline not available — cannot compute revenue.")

            # Step 5: ROAS
            if spend > 0 and revenue_calc > 0:
                roas_calc = revenue_calc / spend
                st.markdown(
                    f"**Step 5 — ROAS:**  \n"
                    f"`{format_currency(revenue_calc)} ÷ {format_currency(spend)} = "
                    f"{roas_calc:.1f}`"
                )

            # Baseline period reference
            st.markdown("---")
            st.markdown(
                f"**Baseline reference date:** {ref_date.strftime('%d/%m/%Y')}  \n"
                f"**CPM / CTR / CVR window:** {cpm_days} days before reference  \n"
                f"**AOV window:** {aov_days} days before reference"
            )

# ── Step 5: Stress Test ──────────────────────────────────────
st.markdown("---")
st.subheader("Step 5: Stress Test")

col_a, col_b = st.columns(2)

stress_rows = []
for row in projection_rows:
    baselines = row["_baselines"]
    spend = row["_spend"]
    platform = row["Platform"]
    ctype = row["Type"]

    stress_a = stress_test(
        spend, baselines.get("cpm"), baselines.get("ctr"),
        baselines.get("cvr"), baselines.get("aov"), "A"
    )
    stress_b = stress_test(
        spend, baselines.get("cpm"), baselines.get("ctr"),
        baselines.get("cvr"), baselines.get("aov"), "B"
    )

    base_roas = row["_proj"]["roas"]
    flag_a = "🔴" if stress_a["roas"] < 6 else "✅"
    flag_b = "🔴" if stress_b["roas"] < 6 else "✅"

    stress_rows.append({
        "Platform": platform,
        "Type": ctype,
        "Base ROAS": format_number(base_roas, 1),
        "Scenario A (CPM +15%)": f"{flag_a} {format_number(stress_a['roas'], 1)}",
        "Scenario B (CVR -10%)": f"{flag_b} {format_number(stress_b['roas'], 1)}",
    })

if stress_rows:
    st.dataframe(pd.DataFrame(stress_rows), use_container_width=True, hide_index=True)
    any_flags = any("🔴" in r["Scenario A (CPM +15%)"] or "🔴" in r["Scenario B (CVR -10%)"] for r in stress_rows)
    if any_flags:
        st.warning("Some platform-type combinations drop below ROAS 6 under stress. Consider reducing allocation for those.")

# ── Step 6: Pattern Log Cross-Check ──────────────────────────
st.markdown("---")
st.subheader("Step 6: Pattern Log Cross-Check")

target_month_num = target_month.month
patterns = get_patterns_for_month(target_month_num)

if patterns:
    st.markdown(f"**Found {len(patterns)} pattern(s) relevant to this month:**")
    for p in patterns:
        with st.expander(f"📌 {p.get('date_observed', '')} — {p.get('what_happened', '')[:80]}"):
            st.markdown(f"**Rule:** {p.get('rule_for_next_time', 'N/A')}")
            st.markdown(f"**True Driver:** {p.get('true_driver', 'N/A')}")
            st.markdown(f"**Should Have Done:** {p.get('what_we_should_have_done', 'N/A')}")
else:
    st.info("No pattern log entries found for this month. Build your pattern log in the Pattern Finder page.")

# ── Forecast Summary ──────────────────────────────────────────
st.markdown("---")
st.subheader("Forecast Summary")

summary_rows = []
for row in projection_rows:
    baselines = row["_baselines"]
    spend = row["_spend"]
    stress_a = stress_test(
        spend, baselines.get("cpm"), baselines.get("ctr"),
        baselines.get("cvr"), baselines.get("aov"), "A"
    )
    stress_b = stress_test(
        spend, baselines.get("cpm"), baselines.get("ctr"),
        baselines.get("cvr"), baselines.get("aov"), "B"
    )

    summary_rows.append({
        "Platform": row["Platform"],
        "Type": row["Type"],
        "Spend": row["Spend"],
        "Projected Revenue": row["Revenue"],
        "Projected ROAS": row["ROAS"],
        "Stress A ROAS": format_number(stress_a["roas"], 1),
        "Stress B ROAS": format_number(stress_b["roas"], 1),
    })

if summary_rows:
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    # Save forecast
    if st.button("Save Forecast", type="primary"):
        forecast_entry = {
            "month": target_month_str,
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
                }
                for r in projection_rows
            ],
            "timestamp": datetime.now().isoformat(),
        }
        log = load_forecast_log()
        # Replace existing forecast for same month
        log = [e for e in log if e.get("month") != target_month_str]
        log.append(forecast_entry)
        save_forecast_log(log)
        st.success(f"Forecast saved for {target_month_str}.")

# ── Forecast Accuracy Tracker ─────────────────────────────────
st.markdown("---")
st.subheader("Forecast Accuracy Tracker")
st.caption("Compare previous forecasts vs actuals")

forecast_log = load_forecast_log()
if forecast_log:
    for entry in sorted(forecast_log, key=lambda x: x.get("month", ""), reverse=True):
        month = entry.get("month", "")
        projections = entry.get("projections", [])
        if not projections:
            continue

        forecast_data = {}
        for proj in projections:
            p = proj["platform"]
            if p not in forecast_data:
                forecast_data[p] = {"spend": 0, "revenue": 0, "roas": 0}
            forecast_data[p]["spend"] += proj.get("spend", 0)
            forecast_data[p]["revenue"] += proj.get("revenue", 0)

        for p in forecast_data:
            if forecast_data[p]["spend"] > 0:
                forecast_data[p]["roas"] = forecast_data[p]["revenue"] / forecast_data[p]["spend"]

        accuracy = compute_forecast_accuracy(df, month, forecast_data)
        if accuracy:
            with st.expander(f"📊 {month} Forecast vs Actuals"):
                acc_df = pd.DataFrame(accuracy)
                for col in ["forecast_spend", "actual_spend", "forecast_revenue", "actual_revenue"]:
                    if col in acc_df.columns:
                        acc_df[col] = acc_df[col].apply(lambda x: format_currency(x))
                for col in ["spend_delta_pct", "revenue_delta_pct", "roas_delta_pct"]:
                    if col in acc_df.columns:
                        acc_df[col] = acc_df[col].apply(
                            lambda x: f"{x:+.1f}%" if not pd.isna(x) else "—"
                        )
                for col in ["forecast_roas", "actual_roas"]:
                    if col in acc_df.columns:
                        acc_df[col] = acc_df[col].apply(lambda x: format_number(x, 1))
                st.dataframe(acc_df, use_container_width=True, hide_index=True)
else:
    st.info("No forecast data yet. Save a forecast above to start tracking accuracy.")
