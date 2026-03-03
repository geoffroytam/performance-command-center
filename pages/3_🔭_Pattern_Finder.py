"""Pattern Finder — Historical pattern scanning and logging."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json

from utils.data_loader import load_all_data
from utils.pattern_engine import (
    load_pattern_log,
    save_pattern_log,
    compute_wow_rate_of_change,
    compare_periods,
    find_inflection_points,
    suggest_date_ranges,
)
from utils.constants import PATTERN_QUESTIONS, COLORS, PLATFORM_COLORS, PLATFORMS, load_settings
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Pattern Finder", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Pattern Finder", "Historical pattern scanning — disciplined inquiry over unstructured exploration")

# ── Load Data ─────────────────────────────────────────────────
if "data" not in st.session_state or st.session_state.data.empty:
    df = load_all_data()
    if df.empty:
        st.warning("No data loaded. Upload CSV files from the main page.")
        st.stop()
    st.session_state.data = df

df = st.session_state.data
settings = load_settings()

# ── Step 1: Define Your Question ──────────────────────────────
st.subheader("Step 1: Define Your Question")

category = st.selectbox(
    "Question Category",
    list(PATTERN_QUESTIONS.keys()),
)

questions = PATTERN_QUESTIONS[category]
question_choice = st.selectbox("Pre-built Question", ["Custom question..."] + questions)

if question_choice == "Custom question...":
    question_text = st.text_input("Write your question", placeholder="What pattern are you investigating?")
else:
    question_text = question_choice

# ── Step 2: Select Comparison Windows ─────────────────────────
st.markdown("---")
st.subheader("Step 2: Select Comparison Windows")

# Auto-suggest based on category
suggested = suggest_date_ranges(category)
min_date = df["date"].min().date()
max_date = df["date"].max().date()

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Period 1 (Current / Recent)**")
    p1_range = st.date_input(
        "Period 1",
        value=(
            max(suggested[0], min_date),
            min(suggested[1], max_date),
        ),
        min_value=min_date,
        max_value=max_date,
        key="p1",
    )
    if isinstance(p1_range, tuple) and len(p1_range) == 2:
        p1_start, p1_end = p1_range
    else:
        p1_start = p1_end = p1_range

with col2:
    st.markdown("**Period 2 (Comparison / Last Year)**")
    p2_range = st.date_input(
        "Period 2",
        value=(
            max(suggested[2], min_date),
            min(suggested[3], max_date),
        ),
        min_value=min_date,
        max_value=max_date,
        key="p2",
    )
    if isinstance(p2_range, tuple) and len(p2_range) == 2:
        p2_start, p2_end = p2_range
    else:
        p2_start = p2_end = p2_range

col_plat, col_type = st.columns(2)
with col_plat:
    available_platforms = sorted(df["platform"].unique().tolist())
    selected_platform = st.selectbox("Platform", available_platforms, key="pat_platform")
with col_type:
    available_types = sorted(
        df[df["platform"] == selected_platform]["campaign_type"].unique().tolist()
    )
    selected_type = st.selectbox("Campaign Type", available_types, key="pat_type")

# ── Step 3: Weekly KPI Comparison ─────────────────────────────
st.markdown("---")
st.subheader("Step 3: Weekly KPI Comparison")

if st.button("Run Comparison", type="primary"):
    result = compare_periods(
        df, p1_start, p1_end, p2_start, p2_end, selected_platform, selected_type
    )

    d1 = result["period1"]["data"]
    d2 = result["period2"]["data"]

    if d1.empty and d2.empty:
        st.warning("Not enough data in either period for a weekly comparison.")
    else:
        # Build period labels for the legend
        p1_label = f"Period 1 ({p1_start.strftime('%b %d')}–{p1_end.strftime('%b %d')})"
        p2_label = f"Period 2 ({p2_start.strftime('%b %d')}–{p2_end.strftime('%b %d')})"

        # Build aligned x-axis using "Week 1", "Week 2", etc.
        # Actual date ranges go into hover text
        hover_labels_1 = d1["week_label"].tolist() if (not d1.empty and "week_label" in d1.columns) else []
        hover_labels_2 = d2["week_label"].tolist() if (not d2.empty and "week_label" in d2.columns) else []
        weeks_1 = [f"Week {i}" for i in range(1, len(d1) + 1)] if not d1.empty else []
        weeks_2 = [f"Week {i}" for i in range(1, len(d2) + 1)] if not d2.empty else []

        # ── Chart 1: Actual KPI Values (always has data for every week) ──
        kpis_to_plot = ["roas", "cpm", "ctr", "cvr", "aov", "spend"]
        kpi_labels = ["ROAS", "CPM (R$)", "CTR (%)", "CVR (%)", "AOV (R$)", "Spend (R$)"]
        kpi_formats = [".1f", ",.0f", ".2f", ".2f", ",.0f", ",.0f"]

        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=kpi_labels,
            vertical_spacing=0.12,
            horizontal_spacing=0.1,
        )

        for idx, (kpi, label, fmt) in enumerate(zip(kpis_to_plot, kpi_labels, kpi_formats)):
            row = idx // 2 + 1
            col = idx % 2 + 1

            if not d1.empty and kpi in d1.columns:
                series1 = d1[kpi].tolist()
                hover1 = [
                    f"{hover_labels_1[i]}<br>{label}: {series1[i]:{fmt}}" if i < len(hover_labels_1) and pd.notna(series1[i])
                    else f"Week {i+1}"
                    for i in range(len(series1))
                ]
                fig.add_trace(
                    go.Scatter(
                        x=weeks_1, y=series1,
                        mode="lines+markers",
                        name=p1_label,
                        line=dict(color=COLORS["blue"], width=2.5),
                        marker=dict(size=8),
                        hovertext=hover1, hoverinfo="text",
                        showlegend=(idx == 0),
                    ),
                    row=row, col=col,
                )
                # Inflection points on the actual values
                inflections = find_inflection_points(d1[kpi])
                for ip in inflections:
                    fig.add_annotation(
                        x=weeks_1[ip], y=series1[ip],
                        text="↕", showarrow=False,
                        font=dict(size=14, color=COLORS["orange"]),
                        row=row, col=col,
                    )

            if not d2.empty and kpi in d2.columns:
                series2 = d2[kpi].tolist()
                hover2 = [
                    f"{hover_labels_2[i]}<br>{label}: {series2[i]:{fmt}}" if i < len(hover_labels_2) and pd.notna(series2[i])
                    else f"Week {i+1}"
                    for i in range(len(series2))
                ]
                fig.add_trace(
                    go.Scatter(
                        x=weeks_2, y=series2,
                        mode="lines+markers",
                        name=p2_label,
                        line=dict(color=COLORS["gray"], width=2.5, dash="dash"),
                        marker=dict(size=8, symbol="diamond"),
                        hovertext=hover2, hoverinfo="text",
                        showlegend=(idx == 0),
                    ),
                    row=row, col=col,
                )

        fig.update_layout(
            height=750,
            title_text=f"Weekly KPIs — {selected_platform} {selected_type}",
            plot_bgcolor=COLORS["white"],
            paper_bgcolor=COLORS["white"],
            margin=dict(t=80, b=30),
            font=dict(family="DM Sans, sans-serif", color=COLORS["dark_blue"]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        )
        fig.update_yaxes(showgrid=True, gridcolor="#E8E4DB")
        fig.update_xaxes(showgrid=False)
        st.plotly_chart(fig, use_container_width=True)

        # ── WoW Change Summary Table ──
        # Show a compact table with WoW % changes when there are enough weeks
        has_wow_1 = not d1.empty and len(d1) >= 2
        has_wow_2 = not d2.empty and len(d2) >= 2

        if has_wow_1 or has_wow_2:
            with st.expander("WoW % Change Detail"):
                wow_kpis = ["roas", "cpm", "ctr", "cvr", "aov", "spend"]
                wow_labels = ["ROAS", "CPM", "CTR", "CVR", "AOV", "Spend"]

                if has_wow_1:
                    st.markdown(f"**{p1_label}**")
                    wow_rows_1 = []
                    for _, row_data in d1.iterrows():
                        r = {"Week": row_data.get("week_label", "")}
                        for kpi_key, kpi_lbl in zip(wow_kpis, wow_labels):
                            wow_val = row_data.get(f"{kpi_key}_wow_pct")
                            r[kpi_lbl] = f"{wow_val:+.1f}%" if pd.notna(wow_val) else "—"
                        wow_rows_1.append(r)
                    st.dataframe(pd.DataFrame(wow_rows_1), use_container_width=True, hide_index=True)

                if has_wow_2:
                    st.markdown(f"**{p2_label}**")
                    wow_rows_2 = []
                    for _, row_data in d2.iterrows():
                        r = {"Week": row_data.get("week_label", "")}
                        for kpi_key, kpi_lbl in zip(wow_kpis, wow_labels):
                            wow_val = row_data.get(f"{kpi_key}_wow_pct")
                            r[kpi_lbl] = f"{wow_val:+.1f}%" if pd.notna(wow_val) else "—"
                        wow_rows_2.append(r)
                    st.dataframe(pd.DataFrame(wow_rows_2), use_container_width=True, hide_index=True)

        # Raw data tables
        with st.expander("View Raw Period Data"):
            tab1, tab2 = st.tabs([p1_label, p2_label])
            with tab1:
                if not d1.empty:
                    st.dataframe(d1, use_container_width=True, hide_index=True)
                else:
                    st.info("No data for Period 1.")
            with tab2:
                if not d2.empty:
                    st.dataframe(d2, use_container_width=True, hide_index=True)
                else:
                    st.info("No data for Period 2.")

# ── Step 4: Extract the Rule ─────────────────────────────────
st.markdown("---")
st.subheader("Step 4: Extract the Rule")

st.markdown(
    """
    **How this works:** After analyzing the rate-of-change comparison above, document
    the pattern you found as a reusable **IF → THEN → THEREFORE** rule. This turns
    one-time observations into actionable playbook rules you can reference next time
    the same situation occurs.

    **Fill in the three parts below:**
    - **IF** — The observable trigger or condition (what you see in the data)
    - **THEN** — The expected consequence (what will likely happen as a result)
    - **THEREFORE** — The action to take (what you should do next time)
    """
)

with st.expander("💡 See examples to help you write your rule"):
    st.markdown(
        """
        | IF | THEN | THEREFORE |
        |---|---|---|
        | CPM rises >15% two weeks before Black Friday | ROAS drops below target and CPA spikes | Start scaling spend 3 weeks before peak instead of 2 |
        | CVR drops >20% on Monday after a long weekend | Retargeting pool is exhausted from weekend traffic | Reduce retargeting spend by 30% on post-holiday Mondays |
        | AOV jumps >25% during a flash sale | Revenue overshoots forecast, masking poor efficiency | Use pre-sale AOV baseline for mid-campaign ROAS evaluation |
        | CTR drops >10% WoW for 2 consecutive weeks | Creative fatigue has set in | Rotate creatives before the 14-day mark |
        """
    )

col_if, col_then, col_therefore = st.columns(3)
with col_if:
    rule_if = st.text_input("IF", placeholder="e.g., CPM rises >15% two weeks before peak")
with col_then:
    rule_then = st.text_input("THEN", placeholder="e.g., ROAS will drop below target")
with col_therefore:
    rule_therefore = st.text_input("THEREFORE", placeholder="e.g., Start scaling spend 3 weeks early")

if rule_if and rule_then and rule_therefore:
    st.success(f"**Your Rule:** IF {rule_if}, THEN {rule_then}, THEREFORE {rule_therefore}.")
    st.caption("This rule will be pre-filled in Step 5 below. Save it to your Pattern Log so you can reference it in future forecasts.")

# ── Step 5: Save to Pattern Log ──────────────────────────────
st.markdown("---")
st.subheader("Step 5: Save to Pattern Log")

with st.form("pattern_form"):
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        date_observed = st.date_input("Date Observed", value=datetime.now().date())
        period_affected = st.text_input(
            "Period Affected", placeholder="e.g., March 2026, Black Friday 2025"
        )
        what_happened = st.text_area("What Happened", height=80)
        true_driver = st.text_area("True Driver", height=80)
    with pcol2:
        what_we_did = st.text_area("What We Did", height=80)
        should_have_done = st.text_area("What We Should Have Done", height=80)
        rule_text = st.text_input(
            "Rule for Next Time",
            value=f"IF {rule_if}, THEN {rule_then}, THEREFORE {rule_therefore}" if (rule_if and rule_then and rule_therefore) else "",
        )
        related_pattern = st.text_input("Related Pattern (optional)")

    save_pattern = st.form_submit_button("Save Pattern", type="primary")
    if save_pattern:
        log = load_pattern_log()
        entry = {
            "date_observed": str(date_observed),
            "period_affected": period_affected,
            "what_happened": what_happened,
            "true_driver": true_driver,
            "what_we_did": what_we_did,
            "what_we_should_have_done": should_have_done,
            "rule_for_next_time": rule_text,
            "related_pattern": related_pattern,
            "platform": selected_platform,
            "campaign_type": selected_type,
            "question": question_text,
            "timestamp": datetime.now().isoformat(),
        }
        log.append(entry)
        save_pattern_log(log)
        st.success("Pattern saved to log.")

# ── Pattern Log Table ─────────────────────────────────────────
st.markdown("---")
st.subheader("Pattern Log")

pattern_log = load_pattern_log()

if pattern_log:
    # Filters
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        filter_platform = st.multiselect(
            "Filter by Platform",
            available_platforms,
            default=[],
            key="log_platform_filter",
        )
    with fcol2:
        search_text = st.text_input("Search patterns", placeholder="keyword...", key="log_search")

    filtered_log = pattern_log.copy()
    if filter_platform:
        filtered_log = [p for p in filtered_log if p.get("platform") in filter_platform]
    if search_text:
        search_lower = search_text.lower()
        filtered_log = [
            p for p in filtered_log
            if search_lower in json.dumps(p).lower()
        ]

    # Display newest first
    filtered_log = sorted(filtered_log, key=lambda x: x.get("date_observed", ""), reverse=True)

    for entry in filtered_log:
        with st.expander(
            f"{entry.get('date_observed', 'N/A')} — {entry.get('platform', '')} — "
            f"{entry.get('what_happened', '')[:60]}..."
        ):
            st.markdown(f"**Period Affected:** {entry.get('period_affected', '')}")
            st.markdown(f"**What Happened:** {entry.get('what_happened', '')}")
            st.markdown(f"**True Driver:** {entry.get('true_driver', '')}")
            st.markdown(f"**What We Did:** {entry.get('what_we_did', '')}")
            st.markdown(f"**Should Have Done:** {entry.get('what_we_should_have_done', '')}")
            st.markdown(f"**Rule:** {entry.get('rule_for_next_time', '')}")
            if entry.get("related_pattern"):
                st.markdown(f"**Related Pattern:** {entry.get('related_pattern', '')}")
else:
    st.info("No patterns logged yet. Complete a pattern scan above and save it.")
