"""Deep Analysis — 4-question structured analysis method."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

from utils.data_loader import load_all_data
from utils.calculations import (
    calculate_baselines,
    aggregate_by_period,
    compute_delta,
    format_currency,
    format_pct,
    format_number,
    format_delta,
    load_action_log,
    save_action_log,
)
from utils.anomaly_detection import diagnose
from utils.constants import COLORS, PLATFORM_COLORS, PLATFORMS, ROAS_TARGETS, load_settings
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Deep Analysis", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Deep Analysis", "The 4-question method for structured performance analysis")


# ── Load Data ─────────────────────────────────────────────────
if "data" not in st.session_state or st.session_state.data.empty:
    df = load_all_data()
    if df.empty:
        st.warning("No data loaded. Upload CSV files from the main page.")
        st.stop()
    st.session_state.data = df

df = st.session_state.data
settings = load_settings()

# ── Filters ───────────────────────────────────────────────────
st.subheader("Filters")

max_date = df["date"].max().date()
min_date = df["date"].min().date()

col_plat, col_type, col_gran = st.columns(3)

with col_plat:
    available_platforms = sorted(df["platform"].unique().tolist())
    selected_platform = st.selectbox("Platform", available_platforms)

with col_type:
    available_types = sorted(
        df[df["platform"] == selected_platform]["campaign_type"].unique().tolist()
    )
    selected_type = st.selectbox("Campaign Type", available_types)

with col_gran:
    granularity = st.selectbox("Granularity", ["Daily", "Weekly", "Monthly"])

# ── Date Range Selection ──────────────────────────────────────
st.markdown("**Date Ranges**")
st.caption("Select any two periods to compare — e.g., Jan 2026 vs Jan 2025, or Feb 2026 vs Jun 2025")

col_current, col_compare = st.columns(2)

with col_current:
    st.markdown("**Current Period**")
    current_range = st.date_input(
        "Current period dates",
        value=(max_date - timedelta(days=29), max_date),
        min_value=min_date,
        max_value=max_date,
        key="analysis_current",
        label_visibility="collapsed",
    )
    if isinstance(current_range, tuple) and len(current_range) == 2:
        start_date, end_date = current_range
    else:
        start_date = end_date = current_range

with col_compare:
    st.markdown("**Comparison Period**")
    # Default: same length period immediately before current period
    current_length_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
    default_comp_end = start_date - timedelta(days=1)
    default_comp_start = default_comp_end - timedelta(days=current_length_days)
    # Ensure defaults are within data range
    default_comp_start = max(default_comp_start, min_date)
    default_comp_end = max(default_comp_end, min_date)

    compare_range = st.date_input(
        "Comparison period dates",
        value=(default_comp_start, default_comp_end),
        min_value=min_date,
        max_value=max_date,
        key="analysis_compare",
        label_visibility="collapsed",
    )
    if isinstance(compare_range, tuple) and len(compare_range) == 2:
        comp_start, comp_end = compare_range
    else:
        comp_start = comp_end = compare_range

# Show period summary
curr_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
comp_days = (pd.Timestamp(comp_end) - pd.Timestamp(comp_start)).days + 1
period_info = f"**Current:** {start_date.strftime('%d/%m/%Y')} → {end_date.strftime('%d/%m/%Y')} ({curr_days} days) &nbsp;&nbsp;|&nbsp;&nbsp; **Comparison:** {comp_start.strftime('%d/%m/%Y')} → {comp_end.strftime('%d/%m/%Y')} ({comp_days} days)"
st.caption(period_info)

# Filter data
mask = (
    (df["date"] >= pd.Timestamp(start_date))
    & (df["date"] <= pd.Timestamp(end_date))
    & (df["platform"] == selected_platform)
    & (df["campaign_type"] == selected_type)
)
filtered = df[mask].copy()

if filtered.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# Aggregate
period_map = {"Daily": "daily", "Weekly": "weekly", "Monthly": "monthly"}
agg = aggregate_by_period(filtered, period_map[granularity], group_cols=["platform", "campaign_type"])

# ── Compute baseline & comparison period ──────────────────────
end_ts = pd.Timestamp(end_date)
baseline = calculate_baselines(df, end_ts, platform=selected_platform, campaign_type=selected_type)

# Use the user-selected comparison period
prev_start = pd.Timestamp(comp_start)
prev_end = pd.Timestamp(comp_end)

prev_mask = (
    (df["date"] >= prev_start)
    & (df["date"] <= prev_end)
    & (df["platform"] == selected_platform)
    & (df["campaign_type"] == selected_type)
)
prev_filtered = df[prev_mask]

# Current period totals
curr_spend = filtered["spend"].sum()
curr_revenue = filtered["revenue"].sum()
curr_orders = filtered["conversions"].sum()
curr_roas = curr_revenue / curr_spend if curr_spend > 0 else np.nan

prev_spend = prev_filtered["spend"].sum() if not prev_filtered.empty else np.nan
prev_revenue = prev_filtered["revenue"].sum() if not prev_filtered.empty else np.nan
prev_roas = prev_revenue / prev_spend if (not pd.isna(prev_spend) and prev_spend > 0) else np.nan

_, roas_pct = compute_delta(curr_roas, prev_roas)
direction = "up" if (not pd.isna(roas_pct) and roas_pct > 0) else "down"

# ── QUESTION 1: What Happened? ────────────────────────────────
st.markdown("---")
st.subheader("Question 1: What Happened?")

if not pd.isna(roas_pct):
    summary = (
        f"**{selected_platform} {selected_type}** ROAS was **{curr_roas:.1f}** "
        f"({start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}), "
        f"**{direction} {abs(roas_pct):.1%}** vs comparison period "
        f"({comp_start.strftime('%d/%m/%Y')} – {comp_end.strftime('%d/%m/%Y')}, ROAS {format_number(prev_roas, 1)})."
    )
else:
    summary = (
        f"**{selected_platform} {selected_type}** ROAS was **{curr_roas:.1f}** "
        f"({start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}). "
        f"No data in comparison period for comparison."
    )
st.markdown(summary)

# ROAS over time with baseline overlay
if not agg.empty and "period" in agg.columns:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=agg["period"],
            y=agg["roas"],
            mode="lines+markers",
            name="ROAS",
            line=dict(color=PLATFORM_COLORS.get(selected_platform, COLORS["blue"]), width=2),
            marker=dict(size=6),
        )
    )
    # Baseline overlay
    base_roas = baseline.get("roas_14d", np.nan)
    if not pd.isna(base_roas):
        fig.add_hline(
            y=base_roas,
            line_dash="dash",
            line_color=COLORS["gray"],
            annotation_text=f"14d Baseline: {base_roas:.1f}",
        )
    # Target line
    target = ROAS_TARGETS.get(selected_type, 8)
    fig.add_hline(
        y=target,
        line_dash="dot",
        line_color=COLORS["orange"],
        annotation_text=f"Target: {target}",
    )

    fig.update_layout(
        title=f"ROAS Trend — {selected_platform} {selected_type}",
        yaxis_title="ROAS",
        xaxis_title="",
        height=350,
        plot_bgcolor=COLORS["white"],
        margin=dict(t=50, b=20),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E8E4DB")
    fig.update_yaxes(showgrid=True, gridcolor="#E8E4DB")
    st.plotly_chart(fig, use_container_width=True)

# ── QUESTION 2: What Drove the Change? ───────────────────────
st.markdown("---")
st.subheader("Question 2: What Drove the Change?")

st.markdown("**Sub-KPI Waterfall: Current Period vs Rolling Baseline**")
st.caption("Baselines use the 14-day rolling average before your current period end date — independent of the comparison period above.")

# Compute aggregate KPIs for current period
curr_impressions = filtered["impressions"].sum()
curr_clicks = filtered["clicks"].sum()
curr_cpm = curr_spend / curr_impressions * 1000 if curr_impressions > 0 else np.nan
curr_ctr = curr_clicks / curr_impressions * 100 if curr_impressions > 0 else np.nan
curr_cvr = curr_orders / curr_clicks * 100 if curr_clicks > 0 else np.nan
curr_aov = curr_revenue / curr_orders if curr_orders > 0 else np.nan

kpi_names = ["CPM", "CTR", "CVR", "AOV"]
current_vals = [curr_cpm, curr_ctr, curr_cvr, curr_aov]
baseline_vals = [baseline.get("cpm"), baseline.get("ctr"), baseline.get("cvr"), baseline.get("aov")]

deltas_pct = []
for c, b in zip(current_vals, baseline_vals):
    if pd.isna(c) or pd.isna(b) or b == 0:
        deltas_pct.append(0)
    else:
        deltas_pct.append((c - b) / b * 100)

col_chart, col_table = st.columns([3, 2])

with col_chart:
    fig = go.Figure(
        go.Bar(
            x=kpi_names,
            y=deltas_pct,
            marker_color=[COLORS["green"] if d >= 0 else COLORS["red"] for d in deltas_pct],
            text=[f"{d:+.1f}%" for d in deltas_pct],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Sub-KPI Delta vs Baseline (%)",
        yaxis_title="% Change",
        height=300,
        plot_bgcolor=COLORS["white"],
        margin=dict(t=40, b=20),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#E8E4DB")
    st.plotly_chart(fig, use_container_width=True)

with col_table:
    table_data = []
    for name, curr, base, dpct in zip(kpi_names, current_vals, baseline_vals, deltas_pct):
        abs_d = curr - base if (not pd.isna(curr) and not pd.isna(base)) else np.nan
        table_data.append({
            "KPI": name,
            "Current": f"{curr:.2f}" if not pd.isna(curr) else "—",
            "Baseline": f"{base:.2f}" if not pd.isna(base) else "—",
            "Abs Delta": f"{abs_d:+.2f}" if not pd.isna(abs_d) else "—",
            "% Delta": f"{dpct:+.1f}%",
        })
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

# ── QUESTION 3: Expected or Anomalous? ───────────────────────
st.markdown("---")
st.subheader("Question 3: Expected or Anomalous?")

# Comparison period trend overlay
comp_agg = aggregate_by_period(prev_filtered, period_map[granularity], group_cols=["platform", "campaign_type"]) if not prev_filtered.empty else pd.DataFrame()

current_dates = []
current_roas_series = []
comp_dates = []
comp_roas_series = []

if not agg.empty:
    for _, r in agg.iterrows():
        current_dates.append(r["period"])
        current_roas_series.append(r["roas"])

if not comp_agg.empty:
    for _, r in comp_agg.iterrows():
        comp_dates.append(r["period"])
        comp_roas_series.append(r["roas"])

has_comparison = len(comp_roas_series) > 0 and any(not pd.isna(v) for v in comp_roas_series)

if has_comparison:
    fig = go.Figure()
    # Current period
    curr_labels = [d.strftime("%d/%m") if hasattr(d, "strftime") else str(d) for d in current_dates]
    fig.add_trace(
        go.Scatter(
            x=list(range(len(current_dates))),
            y=current_roas_series,
            mode="lines+markers",
            name=f"Current ({start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')})",
            line=dict(color=COLORS["blue"], width=2),
            text=curr_labels,
            hovertemplate="%{text}: ROAS %{y:.1f}<extra></extra>",
        )
    )
    # Comparison period
    comp_labels = [d.strftime("%d/%m") if hasattr(d, "strftime") else str(d) for d in comp_dates]
    fig.add_trace(
        go.Scatter(
            x=list(range(len(comp_dates))),
            y=comp_roas_series,
            mode="lines+markers",
            name=f"Comparison ({comp_start.strftime('%d/%m/%Y')} – {comp_end.strftime('%d/%m/%Y')})",
            line=dict(color=COLORS["gray"], width=2, dash="dash"),
            text=comp_labels,
            hovertemplate="%{text}: ROAS %{y:.1f}<extra></extra>",
        )
    )
    tick_labels = curr_labels
    fig.update_layout(
        title=f"ROAS: Current vs Comparison Period",
        xaxis=dict(tickvals=list(range(len(tick_labels))), ticktext=tick_labels),
        yaxis_title="ROAS",
        height=350,
        plot_bgcolor=COLORS["white"],
        margin=dict(t=50, b=20),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#E8E4DB")
    st.plotly_chart(fig, use_container_width=True)

    # Summary text
    avg_comp = np.nanmean(comp_roas_series)
    avg_current = np.nanmean(current_roas_series)
    if not pd.isna(avg_comp) and avg_comp > 0:
        period_diff = (avg_current - avg_comp) / avg_comp
        match_text = "matches" if abs(period_diff) < 0.15 else "does not match"
        st.markdown(
            f"During the comparison period ({comp_start.strftime('%d/%m/%Y')} – {comp_end.strftime('%d/%m/%Y')}), "
            f"average ROAS was **{avg_comp:.1f}** ({period_diff:+.1%} vs current **{avg_current:.1f}**). "
            f"This **{match_text}** the current trend."
        )
else:
    st.info("No data in the comparison period. Adjust the comparison dates in the filters above.")

# ── QUESTION 4: What Should We Do? ───────────────────────────
st.markdown("---")
st.subheader("Question 4: What Should We Do?")

# Auto-suggestion
curr_row = {
    "roas": curr_roas,
    "cpm": curr_cpm,
    "ctr": curr_ctr,
    "cvr": curr_cvr,
    "aov": curr_aov,
    "conversions": curr_orders,
}
diag_title, diag_suggestion = diagnose(curr_row, baseline)

st.markdown(f"**Auto-Diagnosis:** {diag_title}")
st.markdown(f"**Suggested Action:** {diag_suggestion}")

st.markdown("---")

# User recommendation input
with st.form("recommendation_form"):
    user_rec = st.text_area(
        "Your recommendation",
        placeholder="Write your analysis conclusion and recommended action...",
        height=100,
    )
    save_btn = st.form_submit_button("Save to Action Log", type="primary")
    if save_btn and user_rec:
        log = load_action_log()
        entry = {
            "date": str(end_date),
            "action": user_rec,
            "source": "deep_analysis",
            "platform": selected_platform,
            "campaign_type": selected_type,
            "timestamp": datetime.now().isoformat(),
        }
        log.append(entry)
        save_action_log(log)
        st.success("Recommendation saved to action log.")
