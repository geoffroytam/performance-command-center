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
    compute_forecast_accuracy,
)
from utils.pattern_engine import get_patterns_for_month
from utils.constants import COLORS, PLATFORMS, ROAS_TARGETS, load_settings
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

# Target month selector
target_month = st.date_input(
    "Forecast Target Month (select any day in the target month)",
    value=datetime.now().date().replace(day=1),
)
target_month_str = target_month.strftime("%Y-%m")
ref_date = pd.Timestamp(target_month)

# Get number of days and weeks in target month
year = target_month.year
month = target_month.month
days_in_month = calendar.monthrange(year, month)[1]
month_start = pd.Timestamp(f"{year}-{month:02d}-01")
month_end = pd.Timestamp(f"{year}-{month:02d}-{days_in_month}")

# Build week boundaries for the target month
week_boundaries = []
current_day = month_start
week_num = 1
while current_day <= month_end:
    # Each week is Mon-Sun, clipped to month boundaries
    week_start = current_day
    # Find the end of this week (Sunday) or end of month
    days_to_sunday = (6 - current_day.weekday()) % 7
    week_end = min(current_day + timedelta(days=days_to_sunday), month_end)
    n_days = (week_end - week_start).days + 1
    week_boundaries.append({
        "week": f"W{week_num}",
        "start": week_start,
        "end": week_end,
        "days": n_days,
        "label": f"W{week_num} ({week_start.strftime('%d/%m')} – {week_end.strftime('%d/%m')})",
    })
    current_day = week_end + timedelta(days=1)
    week_num += 1

num_weeks = len(week_boundaries)
st.caption(
    f"Target: **{target_month.strftime('%B %Y')}** — {days_in_month} days, {num_weeks} weeks"
)


# ═══════════════════════════════════════════════════════════════
# STEP 1: TOTAL COST ENVELOPE
# ═══════════════════════════════════════════════════════════════
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
# STEP 4: MONTHLY REVENUE PROJECTION
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 4: Monthly Revenue Projection")
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

        target_roas = ROAS_TARGETS.get(ctype, 8)
        roas_val = proj["roas"]
        roas_status = ""
        if roas_val >= target_roas:
            roas_status = "above"
        elif roas_val >= target_roas * 0.8:
            roas_status = "near"
        else:
            roas_status = "below"

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
            "ROAS": format_number(roas_val, 1),
            "_spend": spend,
            "_baselines": baselines,
            "_proj": proj,
            "_roas_status": roas_status,
        })

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

    st.markdown(
        f'<div style="background:{COLORS["light_gray"]}; padding:14px; border-radius:8px; margin-top:8px;">'
        f'<b>Monthly Totals:</b> Spend {format_currency(total_spend)} '
        f'| Revenue {format_currency(total_revenue)} '
        f'| Orders {format_number(total_orders, 0)} '
        f'| Blended ROAS {total_roas:.1f}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Calculation breakdown (collapsible)
    cpm_days = settings.get("cpm_baseline_days", 14)
    aov_days = settings.get("aov_baseline_days", 60)

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

**Baseline sources:** CPM/CTR/CVR use {cpm_days}-day rolling average. AOV uses {aov_days}-day rolling average.
All baselines are weighted ratios computed from raw sums (not averaged daily ratios)."""
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


# ═══════════════════════════════════════════════════════════════
# STEP 5: WEEKLY STEERING PLAN
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 5: Weekly Steering Plan")
st.caption(
    "Break the monthly forecast into weekly targets. Adjust weekly weights based on "
    "seasonality, promotions, or historical patterns."
)

if projection_rows:
    # Default: distribute proportionally by number of days in each week
    default_week_pcts = [wb["days"] / days_in_month * 100 for wb in week_boundaries]

    st.markdown("**Weekly spend distribution (%)**")
    st.caption("Default is proportional to days. Adjust if you expect heavier spend in certain weeks (e.g., promotions).")

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

    st.dataframe(pd.DataFrame(weekly_steering)[[c for c in weekly_steering[0] if not c.startswith("_")]], use_container_width=True, hide_index=True)

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
        st.markdown(
            f'<div style="text-align:center; padding:8px; background:#FDF6F0; border-radius:8px; '
            f'border-top:3px solid {COLORS["red"]};">'
            f'<b>Conservative</b><br/><span style="font-size:0.8rem;">CPM +15%, CVR -10%</span></div>',
            unsafe_allow_html=True,
        )
    with col_base:
        st.markdown(
            f'<div style="text-align:center; padding:8px; background:{COLORS["light_gray"]}; border-radius:8px; '
            f'border-top:3px solid {COLORS["blue"]};">'
            f'<b>Base Case</b><br/><span style="font-size:0.8rem;">Current baselines</span></div>',
            unsafe_allow_html=True,
        )
    with col_opt:
        st.markdown(
            f'<div style="text-align:center; padding:8px; background:#F0F5F1; border-radius:8px; '
            f'border-top:3px solid {COLORS["green"]};">'
            f'<b>Optimistic</b><br/><span style="font-size:0.8rem;">CPM -10%, CVR +10%</span></div>',
            unsafe_allow_html=True,
        )

    scenario_rows = []
    totals = {"conservative": {"spend": 0, "revenue": 0, "orders": 0},
              "base": {"spend": 0, "revenue": 0, "orders": 0},
              "optimistic": {"spend": 0, "revenue": 0, "orders": 0}}

    for row in projection_rows:
        b = row["_baselines"]
        spend = row["_spend"]
        platform = row["Platform"]
        ctype = row["Type"]

        cpm = b.get("cpm", np.nan)
        ctr = b.get("ctr", np.nan)
        cvr = b.get("cvr", np.nan)
        aov = b.get("aov", np.nan)

        # Conservative: CPM +15%, CVR -10%
        cons = project_revenue(
            spend,
            cpm * 1.15 if not pd.isna(cpm) else cpm,
            ctr,
            cvr * 0.90 if not pd.isna(cvr) else cvr,
            aov,
        )

        # Base case
        base_proj = row["_proj"]

        # Optimistic: CPM -10%, CVR +10%
        opt = project_revenue(
            spend,
            cpm * 0.90 if not pd.isna(cpm) else cpm,
            ctr,
            cvr * 1.10 if not pd.isna(cvr) else cvr,
            aov,
        )

        target_roas = ROAS_TARGETS.get(ctype, 8)
        flag_cons = "!!" if cons["roas"] < target_roas * 0.75 else ("!" if cons["roas"] < target_roas else "")

        scenario_rows.append({
            "Platform": platform,
            "Type": ctype,
            "Conservative ROAS": f"{'** ' if flag_cons else ''}{format_number(cons['roas'], 1)}{' **' if flag_cons else ''}",
            "Conservative Rev.": format_currency(cons["revenue"]),
            "Base ROAS": format_number(base_proj["roas"], 1),
            "Base Revenue": format_currency(base_proj["revenue"]),
            "Optimistic ROAS": format_number(opt["roas"], 1),
            "Optimistic Rev.": format_currency(opt["revenue"]),
        })

        totals["conservative"]["spend"] += spend
        totals["conservative"]["revenue"] += cons["revenue"]
        totals["conservative"]["orders"] += cons["orders"]
        totals["base"]["spend"] += spend
        totals["base"]["revenue"] += base_proj["revenue"]
        totals["base"]["orders"] += base_proj["orders"]
        totals["optimistic"]["spend"] += spend
        totals["optimistic"]["revenue"] += opt["revenue"]
        totals["optimistic"]["orders"] += opt["orders"]

    st.dataframe(pd.DataFrame(scenario_rows), use_container_width=True, hide_index=True)

    # Scenario totals
    cons_roas = totals["conservative"]["revenue"] / totals["conservative"]["spend"] if totals["conservative"]["spend"] > 0 else 0
    base_roas = totals["base"]["revenue"] / totals["base"]["spend"] if totals["base"]["spend"] > 0 else 0
    opt_roas = totals["optimistic"]["revenue"] / totals["optimistic"]["spend"] if totals["optimistic"]["spend"] > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f'<div style="background:#FDF6F0; padding:12px; border-radius:8px; text-align:center;">'
            f'<div style="color:{COLORS["red"]}; font-weight:700;">Conservative</div>'
            f'<div style="font-size:1.2rem; font-weight:700;">ROAS {cons_roas:.1f}</div>'
            f'<div style="font-size:0.85rem;">{format_currency(totals["conservative"]["revenue"])} revenue</div>'
            f'<div style="font-size:0.85rem;">{totals["conservative"]["orders"]:,.0f} orders</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div style="background:{COLORS["light_gray"]}; padding:12px; border-radius:8px; text-align:center;">'
            f'<div style="color:{COLORS["blue"]}; font-weight:700;">Base Case</div>'
            f'<div style="font-size:1.2rem; font-weight:700;">ROAS {base_roas:.1f}</div>'
            f'<div style="font-size:0.85rem;">{format_currency(totals["base"]["revenue"])} revenue</div>'
            f'<div style="font-size:0.85rem;">{totals["base"]["orders"]:,.0f} orders</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div style="background:#F0F5F1; padding:12px; border-radius:8px; text-align:center;">'
            f'<div style="color:{COLORS["green"]}; font-weight:700;">Optimistic</div>'
            f'<div style="font-size:1.2rem; font-weight:700;">ROAS {opt_roas:.1f}</div>'
            f'<div style="font-size:0.85rem;">{format_currency(totals["optimistic"]["revenue"])} revenue</div>'
            f'<div style="font-size:0.85rem;">{totals["optimistic"]["orders"]:,.0f} orders</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Risk flags
    if cons_roas < min(ROAS_TARGETS.values()) * 0.75:
        st.warning(
            f"Conservative scenario drops blended ROAS to {cons_roas:.1f}, well below targets. "
            f"Consider reducing allocation to underperforming platforms or building a contingency budget."
        )


# ═══════════════════════════════════════════════════════════════
# STEP 7: PATTERN LOG CROSS-CHECK
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Step 7: Pattern Log Cross-Check")

target_month_num = target_month.month
patterns = get_patterns_for_month(target_month_num)

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
        summary_rows.append({
            "Platform": row["Platform"],
            "Type": row["Type"],
            "Spend": row["Spend"],
            "Projected Revenue": row["Revenue"],
            "Projected ROAS": row["ROAS"],
            "Conservative ROAS": format_number(
                project_revenue(
                    row["_spend"],
                    row["_baselines"].get("cpm", np.nan) * 1.15 if not pd.isna(row["_baselines"].get("cpm")) else np.nan,
                    row["_baselines"].get("ctr", np.nan),
                    row["_baselines"].get("cvr", np.nan) * 0.90 if not pd.isna(row["_baselines"].get("cvr")) else np.nan,
                    row["_baselines"].get("aov", np.nan),
                )["roas"], 1),
            "Optimistic ROAS": format_number(
                project_revenue(
                    row["_spend"],
                    row["_baselines"].get("cpm", np.nan) * 0.90 if not pd.isna(row["_baselines"].get("cpm")) else np.nan,
                    row["_baselines"].get("ctr", np.nan),
                    row["_baselines"].get("cvr", np.nan) * 1.10 if not pd.isna(row["_baselines"].get("cvr")) else np.nan,
                    row["_baselines"].get("aov", np.nan),
                )["roas"], 1),
        })

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
                    "orders": r["_proj"]["orders"],
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
            ],
            "timestamp": datetime.now().isoformat(),
        }
        log = load_forecast_log()
        log = [e for e in log if e.get("month") != target_month_str]
        log.append(forecast_entry)
        save_forecast_log(log)
        st.success(f"Forecast saved for {target_month_str}.")


# ═══════════════════════════════════════════════════════════════
# FORECAST ACCURACY TRACKER
# ═══════════════════════════════════════════════════════════════
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
            with st.expander(f"{month} Forecast vs Actuals"):
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
