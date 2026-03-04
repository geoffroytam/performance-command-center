"""Deep Analysis — KPI tree decomposition with senior analyst narrative."""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from utils.data_loader import load_all_data
from utils.calculations import (
    calculate_baselines,
    format_currency,
    format_number,
    load_action_log,
    save_action_log,
)
from utils.anomaly_detection import diagnose
from utils.constants import COLORS, ROAS_TARGETS, load_settings
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Deep Analysis", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Deep Analysis", "KPI tree decomposition — understand what changed, why, and what to do")


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
max_date = df["date"].max().date()
min_date = df["date"].min().date()

col_plat, col_type = st.columns(2)

with col_plat:
    available_platforms = sorted(df["platform"].unique().tolist())
    selected_platform = st.selectbox("Platform", available_platforms)

with col_type:
    available_types = sorted(
        df[df["platform"] == selected_platform]["campaign_type"].unique().tolist()
    )
    selected_type = st.selectbox("Campaign Type", available_types)

# ── Date Range Selection ──────────────────────────────────────
st.caption("Select two periods to compare — e.g., this month vs last month, or vs same period last year")

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
    current_length_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days
    default_comp_end = start_date - timedelta(days=1)
    default_comp_start = default_comp_end - timedelta(days=current_length_days)
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

curr_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
comp_days = (pd.Timestamp(comp_end) - pd.Timestamp(comp_start)).days + 1
st.caption(
    f"**Current:** {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')} ({curr_days}d) "
    f"| **Comparison:** {comp_start.strftime('%d/%m/%Y')} to {comp_end.strftime('%d/%m/%Y')} ({comp_days}d)"
)

# ── Filter data ───────────────────────────────────────────────
mask_curr = (
    (df["date"] >= pd.Timestamp(start_date))
    & (df["date"] <= pd.Timestamp(end_date))
    & (df["platform"] == selected_platform)
    & (df["campaign_type"] == selected_type)
)
filtered = df[mask_curr].copy()

if filtered.empty:
    st.warning("No data for the selected filters.")
    st.stop()

mask_comp = (
    (df["date"] >= pd.Timestamp(comp_start))
    & (df["date"] <= pd.Timestamp(comp_end))
    & (df["platform"] == selected_platform)
    & (df["campaign_type"] == selected_type)
)
comp_filtered = df[mask_comp].copy()

# ── Compute period KPIs ──────────────────────────────────────
def compute_period_kpis(data: pd.DataFrame) -> dict:
    """Compute all KPIs from aggregated raw values for a period."""
    spend = data["spend"].sum()
    revenue = data["revenue"].sum()
    impressions = data["impressions"].sum()
    clicks = data["clicks"].sum()
    orders = data["conversions"].sum()
    return {
        "spend": spend,
        "revenue": revenue,
        "impressions": impressions,
        "clicks": clicks,
        "orders": orders,
        "roas": revenue / spend if spend > 0 else np.nan,
        "cpm": spend / impressions * 1000 if impressions > 0 else np.nan,
        "ctr": clicks / impressions * 100 if impressions > 0 else np.nan,
        "cvr": orders / clicks * 100 if clicks > 0 else np.nan,
        "aov": revenue / orders if orders > 0 else np.nan,
        "cpa": spend / orders if orders > 0 else np.nan,
    }


curr = compute_period_kpis(filtered)
comp = compute_period_kpis(comp_filtered) if not comp_filtered.empty else None


def pct_change(current_val, comparison_val):
    """Compute % change between two values."""
    if pd.isna(current_val) or pd.isna(comparison_val) or comparison_val == 0:
        return np.nan
    return (current_val - comparison_val) / comparison_val * 100


def delta_arrow(pct, invert=False):
    """Return colored arrow text for a delta. invert=True means lower is better (e.g., CPM, CPA)."""
    if pd.isna(pct):
        return "—"
    is_good = pct < 0 if invert else pct > 0
    color = COLORS["green"] if is_good else COLORS["red"]
    arrow = "+" if pct > 0 else ""
    return f'<span style="color:{color}; font-weight:600;">{arrow}{pct:.1f}%</span>'


def format_kpi_value(kpi_name, value):
    """Format a KPI value appropriately based on its type."""
    if pd.isna(value):
        return "—"
    if kpi_name in ("spend", "revenue", "cpm", "aov", "cpa"):
        return format_currency(value)
    if kpi_name in ("ctr", "cvr"):
        return f"{value:.2f}%"
    if kpi_name == "roas":
        return f"{value:.1f}"
    if kpi_name in ("orders", "impressions", "clicks"):
        return f"{value:,.0f}"
    return f"{value:.2f}"


# ═══════════════════════════════════════════════════════════════
# SECTION 1: EXECUTIVE SUMMARY — What Happened?
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("1. Executive Summary")

target = ROAS_TARGETS.get(selected_type, 8)

# Top-level KPI cards
kpi_cards = [
    ("ROAS", "roas", False),
    ("Spend", "spend", True),
    ("Revenue", "revenue", False),
    ("Orders", "orders", False),
    ("AOV", "aov", False),
    ("CPM", "cpm", True),
]

cols = st.columns(len(kpi_cards))
for idx, (label, key, invert) in enumerate(kpi_cards):
    with cols[idx]:
        curr_val = curr[key]
        delta = pct_change(curr_val, comp[key]) if comp else np.nan
        formatted = format_kpi_value(key, curr_val)
        arrow_html = delta_arrow(delta, invert=invert)
        # Show target comparison for ROAS card
        target_line = ""
        if key == "roas" and not pd.isna(curr_val):
            t_color = COLORS["green"] if curr_val >= target else COLORS["red"]
            t_label = "above" if curr_val >= target else "below"
            target_line = f'<div style="font-size:0.75rem; color:{t_color};">{t_label} target {target}</div>'
        st.html(
            f'<div style="background:{COLORS["light_gray"]}; padding:12px 16px; border-radius:8px; text-align:center;">'
            f'<div style="font-size:0.8rem; color:{COLORS["gray"]};">{label}</div>'
            f'<div style="font-size:1.3rem; font-weight:700; color:#2D3E50;">{formatted}</div>'
            f'{target_line}'
            f'<div style="font-size:0.85rem;">{arrow_html} vs comparison</div>'
            f'</div>'
        )


# ═══════════════════════════════════════════════════════════════
# SECTION 2: KPI TREE DECOMPOSITION — Why Did It Change?
# Following: ROAS = Revenue / Cost
#   Revenue = Orders × AOV
#     Orders = Clicks × CVR
#       Clicks = Impressions × CTR
#         Impressions = Reach × Frequency (not available, so Spend / CPM × 1000)
#   Cost = Impressions × CPM / 1000
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("2. KPI Tree Decomposition — Why Did ROAS Change?")

if comp is None:
    st.info("No comparison period data. Select a comparison period to see the decomposition.")
    st.stop()

st.caption(
    "Following the performance marketing KPI tree: ROAS is driven by Cost and Revenue. "
    "Each sub-metric is decomposed to identify the root cause."
)

# ── Level 0: ROAS ────────────────────────────────────────────
roas_delta = pct_change(curr["roas"], comp["roas"])
spend_delta = pct_change(curr["spend"], comp["spend"])
revenue_delta = pct_change(curr["revenue"], comp["revenue"])

st.html(
    f'<h4 style="font-weight:600;color:#2D3E50;font-family:\'DM Sans\',sans-serif;">'
    f'ROAS: {format_kpi_value("roas", curr["roas"])} '
    f'({delta_arrow(roas_delta)} vs comparison {format_kpi_value("roas", comp["roas"])})'
    f'</h4>'
)

# Determine primary driver at ROAS level
roas_narrative = ""
if not pd.isna(roas_delta):
    direction = "improved" if roas_delta > 0 else "declined"
    if abs(roas_delta) < 5:
        roas_narrative = f"ROAS is **stable** ({roas_delta:+.1f}%). No significant change between periods."
    else:
        # Check what drove it
        cost_impact = ""
        rev_impact = ""
        if not pd.isna(spend_delta):
            if abs(spend_delta) > 5:
                cost_impact = f"costs {'increased' if spend_delta > 0 else 'decreased'} by {abs(spend_delta):.1f}%"
        if not pd.isna(revenue_delta):
            if abs(revenue_delta) > 5:
                rev_impact = f"revenue {'increased' if revenue_delta > 0 else 'decreased'} by {abs(revenue_delta):.1f}%"

        if cost_impact and rev_impact:
            roas_narrative = f"ROAS **{direction} {abs(roas_delta):.1f}%** because {rev_impact} while {cost_impact}."
        elif rev_impact:
            roas_narrative = f"ROAS **{direction} {abs(roas_delta):.1f}%** primarily because {rev_impact} (costs were stable)."
        elif cost_impact:
            roas_narrative = f"ROAS **{direction} {abs(roas_delta):.1f}%** primarily because {cost_impact} (revenue was stable)."
        else:
            roas_narrative = f"ROAS **{direction} {abs(roas_delta):.1f}%**."

st.markdown(roas_narrative)

# ── Level 1: Cost side vs Revenue side ────────────────────────
col_cost, col_rev = st.columns(2)

with col_cost:
    st.html(
        f'<div style="background:#FDF6F0; padding:16px; border-radius:8px; border-left:4px solid {COLORS["orange"]};">'
        f'<div style="font-weight:700; font-size:1.1rem; margin-bottom:8px;">Cost Side</div>'
        f'<table style="width:100%; font-size:0.9rem;">'
        f'<tr><td><b>Total Spend</b></td><td style="text-align:right;">{format_kpi_value("spend", curr["spend"])}</td>'
        f'<td style="text-align:right;">{delta_arrow(spend_delta, invert=True)}</td></tr>'
        f'<tr><td>CPM</td><td style="text-align:right;">{format_kpi_value("cpm", curr["cpm"])}</td>'
        f'<td style="text-align:right;">{delta_arrow(pct_change(curr["cpm"], comp["cpm"]), invert=True)}</td></tr>'
        f'<tr><td>Impressions</td><td style="text-align:right;">{format_kpi_value("impressions", curr["impressions"])}</td>'
        f'<td style="text-align:right;">{delta_arrow(pct_change(curr["impressions"], comp["impressions"]))}</td></tr>'
        f'</table></div>'
    )

with col_rev:
    st.html(
        f'<div style="background:#F0F5F1; padding:16px; border-radius:8px; border-left:4px solid {COLORS["green"]};">'
        f'<div style="font-weight:700; font-size:1.1rem; margin-bottom:8px;">Revenue Side</div>'
        f'<table style="width:100%; font-size:0.9rem;">'
        f'<tr><td><b>Total Revenue</b></td><td style="text-align:right;">{format_kpi_value("revenue", curr["revenue"])}</td>'
        f'<td style="text-align:right;">{delta_arrow(revenue_delta)}</td></tr>'
        f'<tr><td>Orders</td><td style="text-align:right;">{format_kpi_value("orders", curr["orders"])}</td>'
        f'<td style="text-align:right;">{delta_arrow(pct_change(curr["orders"], comp["orders"]))}</td></tr>'
        f'<tr><td>AOV</td><td style="text-align:right;">{format_kpi_value("aov", curr["aov"])}</td>'
        f'<td style="text-align:right;">{delta_arrow(pct_change(curr["aov"], comp["aov"]))}</td></tr>'
        f'</table></div>'
    )

# ── Level 2: Deeper decomposition ────────────────────────────
st.markdown("")
st.markdown("##### Funnel Decomposition")

# Build the full decomposition table
decomp_rows = [
    ("**ROAS**", "roas", curr["roas"], comp["roas"], False, "Revenue / Spend"),
    ("Spend", "spend", curr["spend"], comp["spend"], True, "Impressions x CPM / 1000"),
    ("Revenue", "revenue", curr["revenue"], comp["revenue"], False, "Orders x AOV"),
    ("CPM", "cpm", curr["cpm"], comp["cpm"], True, "Cost per 1,000 impressions"),
    ("Impressions", "impressions", curr["impressions"], comp["impressions"], False, "Reach x Frequency"),
    ("CTR (LPV)", "ctr", curr["ctr"], comp["ctr"], False, "Clicks / Impressions"),
    ("Clicks (LPV)", "clicks", curr["clicks"], comp["clicks"], False, "Impressions x CTR"),
    ("CVR (LPV)", "cvr", curr["cvr"], comp["cvr"], False, "Orders / Clicks"),
    ("Orders", "orders", curr["orders"], comp["orders"], False, "Clicks x CVR"),
    ("AOV", "aov", curr["aov"], comp["aov"], False, "Revenue / Orders"),
    ("CPA", "cpa", curr["cpa"], comp["cpa"], True, "Spend / Orders"),
]

decomp_html = (
    '<table style="width:100%; border-collapse:collapse; font-size:0.9rem;">'
    '<tr style="border-bottom:2px solid #2D3E50;">'
    '<th style="text-align:left; padding:8px;">KPI</th>'
    '<th style="text-align:right; padding:8px;">Current</th>'
    '<th style="text-align:right; padding:8px;">Comparison</th>'
    '<th style="text-align:right; padding:8px;">Change</th>'
    '<th style="text-align:left; padding:8px;">Formula</th>'
    '</tr>'
)

for label, key, curr_val, comp_val, invert, formula in decomp_rows:
    pct = pct_change(curr_val, comp_val)
    arrow = delta_arrow(pct, invert=invert)
    bg = ""
    if not pd.isna(pct) and abs(pct) > 15:
        bg = f' style="background:#FFF3F0;"' if (pct > 0 and invert) or (pct < 0 and not invert) else f' style="background:#F0F8F0;"'

    decomp_html += (
        f'<tr{bg}>'
        f'<td style="padding:6px 8px;">{label}</td>'
        f'<td style="text-align:right; padding:6px 8px;">{format_kpi_value(key, curr_val)}</td>'
        f'<td style="text-align:right; padding:6px 8px;">{format_kpi_value(key, comp_val)}</td>'
        f'<td style="text-align:right; padding:6px 8px;">{arrow}</td>'
        f'<td style="padding:6px 8px; color:{COLORS["gray"]}; font-size:0.8rem;">{formula}</td>'
        f'</tr>'
    )

decomp_html += '</table>'
st.html(decomp_html)

st.caption("Rows highlighted in red indicate a negative impact on performance. Green = positive impact.")


# ═══════════════════════════════════════════════════════════════
# SECTION 3: ANALYST NARRATIVE — Root Cause Analysis
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("3. Root Cause Analysis")

# Build the waterfall narrative following the KPI tree
cpm_delta = pct_change(curr["cpm"], comp["cpm"])
ctr_delta = pct_change(curr["ctr"], comp["ctr"])
cvr_delta = pct_change(curr["cvr"], comp["cvr"])
aov_delta = pct_change(curr["aov"], comp["aov"])
orders_delta = pct_change(curr["orders"], comp["orders"])
impressions_delta = pct_change(curr["impressions"], comp["impressions"])
clicks_delta = pct_change(curr["clicks"], comp["clicks"])

# Identify the primary and secondary drivers
drivers = []

if not pd.isna(cpm_delta) and abs(cpm_delta) > 10:
    impact = "negative" if cpm_delta > 0 else "positive"
    drivers.append({
        "kpi": "CPM",
        "delta": cpm_delta,
        "impact": impact,
        "explanation": f"CPM {'increased' if cpm_delta > 0 else 'decreased'} by {abs(cpm_delta):.1f}% — "
                       f"{'higher auction pressure means each impression costs more, reducing efficiency' if cpm_delta > 0 else 'lower auction costs mean more impressions per real spent, improving efficiency'}.",
    })

if not pd.isna(ctr_delta) and abs(ctr_delta) > 10:
    impact = "positive" if ctr_delta > 0 else "negative"
    drivers.append({
        "kpi": "CTR",
        "delta": ctr_delta,
        "impact": impact,
        "explanation": f"CTR {'improved' if ctr_delta > 0 else 'declined'} by {abs(ctr_delta):.1f}% — "
                       f"{'creatives are generating more engagement per impression' if ctr_delta > 0 else 'creatives are less engaging, consider refreshing ads or checking frequency'}.",
    })

if not pd.isna(cvr_delta) and abs(cvr_delta) > 10:
    impact = "positive" if cvr_delta > 0 else "negative"
    drivers.append({
        "kpi": "CVR",
        "delta": cvr_delta,
        "impact": impact,
        "explanation": f"CVR {'improved' if cvr_delta > 0 else 'declined'} by {abs(cvr_delta):.1f}% — "
                       f"{'more visitors are converting, indicating better audience quality or landing page performance' if cvr_delta > 0 else 'fewer visitors are converting, check landing page, offer relevance, or audience targeting'}.",
    })

if not pd.isna(aov_delta) and abs(aov_delta) > 10:
    impact = "positive" if aov_delta > 0 else "negative"
    drivers.append({
        "kpi": "AOV",
        "delta": aov_delta,
        "impact": impact,
        "explanation": f"AOV {'increased' if aov_delta > 0 else 'decreased'} by {abs(aov_delta):.1f}% — "
                       f"{'customers are spending more per order (upsell/cross-sell working or product mix shift)' if aov_delta > 0 else 'customers are spending less per order (possible discount dependency or product mix shift)'}.",
    })

if drivers:
    # Sort by absolute impact
    drivers.sort(key=lambda d: abs(d["delta"]), reverse=True)

    st.markdown("**Key Drivers Identified:**")
    for i, d in enumerate(drivers, 1):
        color = COLORS["green"] if d["impact"] == "positive" else COLORS["red"]
        st.html(
            f'<div style="background:{COLORS["light_gray"]}; padding:10px 14px; border-radius:6px; '
            f'margin-bottom:8px; border-left:4px solid {color};">'
            f'<b>{d["kpi"]}</b> ({d["delta"]:+.1f}% — {d["impact"]} impact)<br/>'
            f'{d["explanation"]}'
            f'</div>'
        )

    # Build a summary narrative
    st.markdown("")
    st.markdown("**Summary:**")

    narrative_parts = []

    # Cost side story
    cost_drivers = [d for d in drivers if d["kpi"] in ("CPM",)]
    revenue_drivers = [d for d in drivers if d["kpi"] in ("CTR", "CVR", "AOV")]

    if cost_drivers and revenue_drivers:
        cost_story = " and ".join([f"{d['kpi']} {d['delta']:+.1f}%" for d in cost_drivers])
        rev_story = " and ".join([f"{d['kpi']} {d['delta']:+.1f}%" for d in revenue_drivers])
        narrative_parts.append(
            f"On the **cost side**, {cost_story}. On the **revenue side**, {rev_story}."
        )
    elif cost_drivers:
        cost_story = " and ".join([f"{d['kpi']} {d['delta']:+.1f}%" for d in cost_drivers])
        narrative_parts.append(f"The change is primarily **cost-driven**: {cost_story}. Revenue-side metrics are stable.")
    elif revenue_drivers:
        rev_story = " and ".join([f"{d['kpi']} {d['delta']:+.1f}%" for d in revenue_drivers])
        narrative_parts.append(f"The change is primarily **revenue-driven**: {rev_story}. Cost metrics are stable.")

    # Check for problematic combinations
    if not pd.isna(aov_delta) and aov_delta > 15 and not pd.isna(orders_delta) and orders_delta < 5:
        narrative_parts.append(
            f"**Warning:** AOV is up {aov_delta:.1f}% but orders only changed {orders_delta:+.1f}%. "
            f"This could be a false positive — revenue growth is driven by ticket size, not volume."
        )

    if not pd.isna(cpm_delta) and cpm_delta > 15 and not pd.isna(ctr_delta) and ctr_delta < -10:
        narrative_parts.append(
            f"**Alert:** CPM up {cpm_delta:.1f}% combined with CTR down {abs(ctr_delta):.1f}% "
            f"suggests creative fatigue or audience saturation."
        )

    for part in narrative_parts:
        st.markdown(part)

    # ── Senior analyst paragraph ──────────────────────────────────
    st.markdown("")
    st.markdown("**Analyst Interpretation:**")

    # Build a professional narrative paragraph
    period_label = f"{start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')}"
    comp_label = f"{comp_start.strftime('%d/%m/%Y')} – {comp_end.strftime('%d/%m/%Y')}"

    para_parts = []

    # Opening context
    roas_status = "above" if curr["roas"] >= target else "below"
    para_parts.append(
        f"During the period {period_label}, {selected_platform} {selected_type} delivered a ROAS of "
        f"{curr['roas']:.1f}, which is {roas_status} the target of {target}. "
        f"Compared to the reference period ({comp_label}), ROAS moved {roas_delta:+.1f}%."
    )

    # Funnel narrative following the KPI tree
    neg_drivers = [d for d in drivers if d["impact"] == "negative"]
    pos_drivers = [d for d in drivers if d["impact"] == "positive"]

    if neg_drivers and not pos_drivers:
        kpis = ", ".join([d["kpi"] for d in neg_drivers])
        para_parts.append(
            f"The performance deterioration is driven by {kpis}. "
            f"This points to a structural challenge in the funnel that needs to be addressed before scaling."
        )
    elif pos_drivers and not neg_drivers:
        kpis = ", ".join([d["kpi"] for d in pos_drivers])
        para_parts.append(
            f"The improvement is driven by {kpis}, indicating healthy funnel dynamics. "
            f"This creates an opportunity for controlled scaling if the trend is sustained."
        )
    elif neg_drivers and pos_drivers:
        neg_kpis = ", ".join([d["kpi"] for d in neg_drivers])
        pos_kpis = ", ".join([d["kpi"] for d in pos_drivers])
        para_parts.append(
            f"The picture is mixed: {pos_kpis} improved, but {neg_kpis} deteriorated. "
            f"The net effect on ROAS depends on which side dominates."
        )

    # Specific funnel stories
    if not pd.isna(cpm_delta) and cpm_delta > 15:
        para_parts.append(
            f"The significant CPM increase (+{cpm_delta:.1f}%) suggests growing auction pressure. "
            f"This could be driven by increased competition, seasonal demand, or audience overlap across ad sets."
        )
    if not pd.isna(ctr_delta) and ctr_delta < -15:
        para_parts.append(
            f"CTR has declined substantially ({ctr_delta:.1f}%), which typically signals creative fatigue "
            f"or a mismatch between the ad message and the target audience. "
            f"Consider refreshing creative assets and reviewing frequency caps."
        )
    if not pd.isna(cvr_delta) and cvr_delta < -15:
        para_parts.append(
            f"The drop in conversion rate ({cvr_delta:.1f}%) is concerning as it directly impacts order volume. "
            f"Common causes include landing page issues, offer relevance, or targeting audiences with lower purchase intent."
        )
    if not pd.isna(aov_delta) and abs(aov_delta) > 15:
        direction = "increase" if aov_delta > 0 else "decrease"
        para_parts.append(
            f"AOV showed a notable {direction} ({aov_delta:+.1f}%). "
            f"{'This may be driven by product mix changes, promotions, or one-off high-value orders that could revert.' if aov_delta > 0 else 'This could indicate a shift toward lower-priced products or increased discount dependency.'}"
        )

    # Closing recommendation
    if not pd.isna(roas_delta) and roas_delta < -15:
        para_parts.append(
            "The recommendation is to hold current spend levels, isolate the underperforming segments, "
            "and focus on fixing the weakest link in the funnel before attempting to scale."
        )
    elif not pd.isna(roas_delta) and roas_delta > 15:
        if not pd.isna(orders_delta) and orders_delta > 10:
            para_parts.append(
                "With volume growth supporting the ROAS improvement, controlled scaling is advisable. "
                "Increase daily budgets gradually (15-20% max) while monitoring the sub-metrics for any sign of regression."
            )
        else:
            para_parts.append(
                "While ROAS has improved, the lack of proportional volume growth warrants caution. "
                "Monitor for 48-72 hours before scaling to confirm the trend is sustainable and not driven by outlier orders."
            )
    else:
        para_parts.append(
            "Performance is within normal operating range. Continue with the current strategy "
            "and focus on incremental improvements to the weakest funnel metrics."
        )

    analyst_text = " ".join(para_parts)
    st.html(
        f'<div style="background:{COLORS["light_gray"]}; padding:16px; border-radius:8px; '
        f'line-height:1.6; font-size:0.92rem; color:#403833;">'
        f'{analyst_text}'
        f'</div>'
    )

else:
    st.markdown(
        "All sub-KPIs are within normal range (less than 10% change). "
        "Performance is stable between the two periods. Continue monitoring and focus on incremental "
        "improvements to conversion rate and creative performance."
    )


# ═══════════════════════════════════════════════════════════════
# SECTION 4: AUTO-DIAGNOSIS & RECOMMENDATION
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("4. Diagnosis & Recommendation")

# Run the automated diagnosis engine
end_ts = pd.Timestamp(end_date)
baseline = calculate_baselines(df, end_ts, platform=selected_platform, campaign_type=selected_type)

curr_row = {
    "roas": curr["roas"],
    "cpm": curr["cpm"],
    "ctr": curr["ctr"],
    "cvr": curr["cvr"],
    "aov": curr["aov"],
    "conversions": curr["orders"],
}
diag_title, diag_suggestion = diagnose(curr_row, baseline)

# Determine color based on diagnosis
diag_color = COLORS["green"]
if "below" in diag_title.lower() or "issue" in diag_title.lower() or "fatigue" in diag_title.lower() or "pressure" in diag_title.lower():
    diag_color = COLORS["red"]
elif "false positive" in diag_title.lower():
    diag_color = COLORS["orange"]

st.html(
    f'<div style="background:{COLORS["light_gray"]}; padding:16px; border-radius:8px; '
    f'border-left:4px solid {diag_color};">'
    f'<div style="font-weight:700; font-size:1.1rem; color:{diag_color};">{diag_title}</div>'
    f'<div style="margin-top:8px;">{diag_suggestion}</div>'
    f'</div>'
)

# Build specific action recommendations based on the analysis
st.markdown("")
st.markdown("**Recommended Actions:**")

recommendations = []

if not pd.isna(roas_delta):
    if roas_delta < -15:
        # ROAS declined significantly
        if not pd.isna(cpm_delta) and cpm_delta > 10:
            recommendations.append("Audit ad placements and shift budget to lower-CPM ad sets or placements.")
            recommendations.append("Review audience overlap — consolidate ad sets to reduce internal auction competition.")
        if not pd.isna(ctr_delta) and ctr_delta < -10:
            recommendations.append("Refresh creatives — test new formats (carousel, video, UGC).")
            recommendations.append("Check ad frequency — pause ads with frequency above 3.")
        if not pd.isna(cvr_delta) and cvr_delta < -10:
            recommendations.append("Audit landing page performance (load time, mobile UX, offer clarity).")
            recommendations.append("Check audience quality — review lookalike or interest targeting.")
        if not pd.isna(aov_delta) and aov_delta < -10:
            recommendations.append("Review product mix — check if lower-priced items are cannibalizing.")
            recommendations.append("Consider upsell/cross-sell strategies or bundle offers.")
        if not recommendations:
            recommendations.append("Run a detailed sub-KPI waterfall to isolate the specific broken link in the funnel.")
    elif roas_delta > 15:
        # ROAS improved significantly
        if not pd.isna(orders_delta) and orders_delta > 10 and (pd.isna(aov_delta) or abs(aov_delta) < 15):
            recommendations.append("Scale gradually — increase daily budget by 15-20% max to avoid resetting learning.")
            recommendations.append("Document the winning creative/audience combination for replication.")
        elif not pd.isna(aov_delta) and aov_delta > 15 and (pd.isna(orders_delta) or orders_delta < 5):
            recommendations.append("Hold spend flat — the improvement is driven by AOV, not volume. Wait 48-72h to confirm.")
            recommendations.append("Monitor for one-off high-value orders skewing the data.")
        else:
            recommendations.append("Performance is improving. Document what changed and consider cautious scaling.")
    else:
        recommendations.append("Performance is stable. Maintain current strategy and monitor for emerging trends.")

if recommendations:
    for i, rec in enumerate(recommendations, 1):
        st.markdown(f"{i}. {rec}")
else:
    st.markdown("Performance is within normal range. Continue monitoring.")

# ── Action Log ─────────────────────────────────────────────────
st.markdown("---")
with st.form("recommendation_form"):
    user_rec = st.text_area(
        "Your notes / recommendation",
        placeholder="Write your analysis conclusion and recommended action...",
        height=80,
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
            "diagnosis": diag_title,
            "roas_current": round(curr["roas"], 2) if not pd.isna(curr["roas"]) else None,
            "roas_comparison": round(comp["roas"], 2) if comp and not pd.isna(comp["roas"]) else None,
            "timestamp": datetime.now().isoformat(),
        }
        log.append(entry)
        save_action_log(log)
        st.success("Recommendation saved to action log.")
