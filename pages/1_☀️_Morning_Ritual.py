"""Morning Ritual Dashboard — Daily vital signs, anomaly detection, auto-diagnosis."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

from utils.data_loader import load_all_data
from utils.calculations import (
    calculate_baselines,
    aggregate_for_date,
    compute_delta,
    format_currency,
    format_pct,
    format_number,
    format_delta,
    load_action_log,
    save_action_log,
)
from utils.anomaly_detection import diagnose, flag_anomalies_for_row
from utils.constants import (
    COLORS,
    PLATFORM_COLORS,
    ROAS_TARGETS,
    load_settings,
)
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Morning Ritual", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Morning Ritual", "Yesterday's vital signs — anomaly detection and auto-diagnosis")


# ── Load Data ─────────────────────────────────────────────────
if "data" not in st.session_state or st.session_state.data.empty:
    df = load_all_data()
    if df.empty:
        st.warning("No data loaded. Upload CSV files from the main page to get started.")
        st.stop()
    st.session_state.data = df

df = st.session_state.data
settings = load_settings()

# ── Date Selector ─────────────────────────────────────────────
max_date = df["date"].max().date()
min_date = df["date"].min().date()
default_date = max_date  # Defaults to most recent day

selected_date = st.date_input(
    "Select date",
    value=default_date,
    min_value=min_date,
    max_value=max_date,
    help="Defaults to the most recent date in your data",
)

selected_ts = pd.Timestamp(selected_date)

# ── KPI Summary Cards ─────────────────────────────────────────
st.markdown("---")
st.subheader("Daily Summary")

day_data = df[df["date"] == selected_ts]
if day_data.empty:
    st.warning(f"No data available for {selected_date.strftime('%d/%m/%Y')}. Select a different date.")
    st.stop()

total_spend = day_data["spend"].sum()
total_revenue = day_data["revenue"].sum()
total_orders = day_data["conversions"].sum()
total_impressions = day_data["impressions"].sum()
total_lpv = day_data["clicks"].sum()  # clicks = Landing Page Views in tracker
blended_roas = total_revenue / total_spend if total_spend > 0 else 0

# Previous day for delta
prev_date = selected_ts - timedelta(days=1)
prev_data = df[df["date"] == prev_date]
prev_spend = prev_data["spend"].sum() if not prev_data.empty else np.nan
prev_revenue = prev_data["revenue"].sum() if not prev_data.empty else np.nan
prev_orders = prev_data["conversions"].sum() if not prev_data.empty else np.nan
prev_lpv = prev_data["clicks"].sum() if not prev_data.empty else np.nan
prev_roas = prev_revenue / prev_spend if (not pd.isna(prev_spend) and prev_spend > 0) else np.nan

# 14-day baseline for blended
baseline_14d = df[df["date"].between(selected_ts - timedelta(days=14), selected_ts - timedelta(days=1))]
if not baseline_14d.empty:
    base_spend = baseline_14d.groupby("date")["spend"].sum().mean()
    base_revenue = baseline_14d.groupby("date")["revenue"].sum().mean()
    base_orders = baseline_14d.groupby("date")["conversions"].sum().mean()
    base_lpv = baseline_14d.groupby("date")["clicks"].sum().mean()
    base_roas = base_revenue / base_spend if base_spend > 0 else np.nan
else:
    base_spend = base_revenue = base_orders = base_lpv = base_roas = np.nan


def delta_str(current, previous):
    if pd.isna(previous) or previous == 0:
        return None
    return f"{(current - previous) / previous:+.1%} vs prev day"


# Row 1: Core financial KPIs
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Spend",
        f"R$ {total_spend:,.2f}",
        delta=delta_str(total_spend, prev_spend),
    )
    if not pd.isna(base_spend) and base_spend > 0:
        pct = (total_spend - base_spend) / base_spend
        st.caption(f"vs 14d baseline: {pct:+.1%}")

with col2:
    st.metric(
        "Total Revenue",
        f"R$ {total_revenue:,.2f}",
        delta=delta_str(total_revenue, prev_revenue),
    )
    if not pd.isna(base_revenue) and base_revenue > 0:
        pct = (total_revenue - base_revenue) / base_revenue
        st.caption(f"vs 14d baseline: {pct:+.1%}")

with col3:
    st.metric(
        "Blended ROAS",
        f"{blended_roas:.1f}",
        delta=delta_str(blended_roas, prev_roas),
    )
    if not pd.isna(base_roas) and base_roas > 0:
        pct = (blended_roas - base_roas) / base_roas
        st.caption(f"vs 14d baseline: {pct:+.1%}")

with col4:
    st.metric(
        "Purchases",
        f"{total_orders:,.0f}",
        delta=delta_str(total_orders, prev_orders),
    )
    if not pd.isna(base_orders) and base_orders > 0:
        pct = (total_orders - base_orders) / base_orders
        st.caption(f"vs 14d baseline: {pct:+.1%}")

# Row 2: Traffic KPIs
col5, col6, col7, col8 = st.columns(4)

with col5:
    st.metric("Impressions", f"{total_impressions:,.0f}")

with col6:
    st.metric(
        "Landing Page Views",
        f"{total_lpv:,.0f}",
        delta=delta_str(total_lpv, prev_lpv),
    )
    if not pd.isna(base_lpv) and base_lpv > 0:
        pct = (total_lpv - base_lpv) / base_lpv
        st.caption(f"vs 14d baseline: {pct:+.1%}")

with col7:
    # CTR = LPV / Impressions
    blended_ctr = total_lpv / total_impressions * 100 if total_impressions > 0 else 0
    st.metric("CTR (LPV)", f"{blended_ctr:.2f}%")

with col8:
    # CVR = Purchases / LPV
    blended_cvr = total_orders / total_lpv * 100 if total_lpv > 0 else 0
    st.metric("CVR (LPV)", f"{blended_cvr:.2f}%")

# ── Platform Breakdown Table ──────────────────────────────────
st.markdown("---")
st.subheader("Platform Breakdown")

day_agg = aggregate_for_date(df, selected_ts)
if day_agg.empty:
    st.info("No aggregated data for this date.")
    st.stop()

threshold = settings.get("anomaly_threshold_pct", 15)
rows = []
anomaly_details = []

for _, row in day_agg.iterrows():
    platform = row["platform"]
    ctype = row["campaign_type"]

    # Calculate baseline for this platform-type combo
    baseline = calculate_baselines(df, selected_ts, platform=platform, campaign_type=ctype)

    # ROAS target
    target = ROAS_TARGETS.get(ctype, 8)
    roas_val = row.get("roas", np.nan)
    roas_color = "🟢" if (not pd.isna(roas_val) and roas_val >= target) else "🔴"

    # Check for anomalies
    row_dict = row.to_dict()
    anomalies = flag_anomalies_for_row(row_dict, baseline, threshold)
    flag = "🔴" if anomalies else "✅"

    # Baseline ROAS for comparison
    base_roas_val = baseline.get("roas_14d", np.nan)
    _, roas_pct = compute_delta(roas_val, base_roas_val)

    rows.append({
        "Platform": platform,
        "Type": ctype,
        "Spend": format_currency(row["spend"]),
        "Revenue": format_currency(row["revenue"]),
        "ROAS": f"{roas_color} {format_number(roas_val, 1)}",
        "Impressions": format_number(row.get("impressions", 0), 0),
        "LPV (Traffic)": format_number(row.get("clicks", 0), 0),
        "Purchases": format_number(row.get("conversions", 0), 0),
        "CPM": format_currency(row.get("cpm", np.nan)),
        "CTR (LPV)": format_pct(row.get("ctr", np.nan)),
        "CVR (LPV)": format_pct(row.get("cvr", np.nan)),
        "AOV": format_currency(row.get("aov", np.nan)),
        "vs Baseline": format_delta(roas_pct),
        "Flag": flag,
    })

    if anomalies:
        diagnosis_title, suggestion = diagnose(row_dict, baseline)
        anomaly_details.append({
            "platform": platform,
            "campaign_type": ctype,
            "anomalies": anomalies,
            "diagnosis": diagnosis_title,
            "suggestion": suggestion,
            "row": row_dict,
            "baseline": baseline,
        })

if rows:
    display_df = pd.DataFrame(rows)
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

# ── Anomaly Detail Panel ─────────────────────────────────────
if anomaly_details:
    st.markdown("---")
    st.subheader("Anomaly Details")

    for detail in anomaly_details:
        with st.expander(
            f"🔴 {detail['platform']} {detail['campaign_type']} — {detail['diagnosis']}",
            expanded=True,
        ):
            # Anomaly list
            for a in detail["anomalies"]:
                direction_icon = "📈" if a["direction"] == "up" else "📉"
                # Use friendly KPI names
                kpi_display = a["kpi"]
                if kpi_display == "CTR":
                    kpi_display = "CTR (LPV)"
                elif kpi_display == "CVR":
                    kpi_display = "CVR (LPV)"
                st.markdown(
                    f"- {direction_icon} **{kpi_display}**: {a['current']:.2f} "
                    f"(baseline: {a['baseline']:.2f}, {a['pct_change']:+.1f}%)"
                )

            st.markdown(f"**Diagnosis:** {detail['diagnosis']}")
            st.markdown(f"**Suggested Action:** {detail['suggestion']}")

            # Sub-KPI waterfall chart
            row_d = detail["row"]
            base_d = detail["baseline"]
            kpi_names = ["CPM", "CTR (LPV)", "CVR (LPV)", "AOV"]
            kpi_keys = ["cpm", "ctr", "cvr", "aov"]
            deltas = []
            for k in kpi_keys:
                curr = row_d.get(k, np.nan)
                base = base_d.get(k, np.nan)
                if pd.isna(curr) or pd.isna(base) or base == 0:
                    deltas.append(0)
                else:
                    deltas.append((curr - base) / base * 100)

            fig = go.Figure(
                go.Bar(
                    x=kpi_names,
                    y=deltas,
                    marker_color=[
                        COLORS["green"] if d >= 0 else COLORS["red"]
                        for d in deltas
                    ],
                    text=[f"{d:+.1f}%" for d in deltas],
                    textposition="outside",
                )
            )
            fig.update_layout(
                title="Sub-KPI Waterfall (% vs Baseline)",
                yaxis_title="% Change",
                xaxis_title="",
                height=300,
                margin=dict(t=40, b=20),
                plot_bgcolor=COLORS["white"],
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor="#E8E4DB")
            st.plotly_chart(fig, use_container_width=True)
else:
    st.success("No anomalies detected. All platforms performing within baseline tolerance.")

# ── Daily Action Log ──────────────────────────────────────────
st.markdown("---")
st.subheader("Daily Action Log")

action_log = load_action_log()

with st.form("action_form"):
    action_text = st.text_input(
        "What is your one action for today?",
        placeholder="e.g., Pause underperforming ad set in Meta retargeting",
    )
    submitted = st.form_submit_button("Save Action", type="primary")
    if submitted and action_text:
        entry = {
            "date": str(selected_date),
            "action": action_text,
            "timestamp": datetime.now().isoformat(),
        }
        action_log.append(entry)
        save_action_log(action_log)
        st.success("Action logged.")

# Show last 7 days of actions
if action_log:
    st.markdown("**Recent Actions:**")
    recent = sorted(action_log, key=lambda x: x.get("date", ""), reverse=True)[:7]
    for entry in recent:
        st.markdown(f"- **{entry.get('date', 'N/A')}**: {entry.get('action', '')}")
