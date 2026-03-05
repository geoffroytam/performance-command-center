"""Strategy Playbook — Scenario-based strategy reference and CBO test tracker."""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from utils.data_loader import load_all_data
from utils.recommendations import generate_playbook_recommendations, analyze_platform_health, INDUSTRY_BENCHMARKS
from utils.constants import COLORS, ROAS_TARGETS, load_settings
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Strategy Playbook", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Strategy Playbook", "Scenario-based strategies and platform-specific best practices")

settings = load_settings()

# ── Load Data ─────────────────────────────────────────────────
if "data" not in st.session_state or st.session_state.data.empty:
    df = load_all_data()
    if df.empty:
        df = pd.DataFrame()
    else:
        st.session_state.data = df
else:
    df = st.session_state.data

# ═══════════════════════════════════════════════════════════════
# DATA-DRIVEN RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════
st.subheader("Data-Driven Recommendations")
st.caption("Recommendations generated from your actual performance data and industry benchmarks")

if not df.empty:
    playbook_recs = generate_playbook_recommendations(df, lookback_days=30)

    if playbook_recs:
        priority_colors = {
            "P1": COLORS["red"],
            "P2": COLORS["orange"],
            "P3": COLORS["blue"],
        }
        priority_labels = {
            "P1": "High Priority",
            "P2": "Medium Priority",
            "P3": "Opportunity",
        }

        for rec in playbook_recs:
            p_color = priority_colors.get(rec["priority"], COLORS["gray"])
            p_label = priority_labels.get(rec["priority"], rec["priority"])
            st.html(
                f'<div style="background:{COLORS["light_gray"]}; padding:14px 16px; border-radius:8px; '
                f'margin-bottom:10px; border-left:4px solid {p_color};">'
                f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">'
                f'<span style="background:{p_color}; color:white; padding:2px 8px; border-radius:4px; '
                f'font-size:0.7rem; font-weight:700;">{p_label}</span>'
                f'<span style="font-size:0.75rem; color:{COLORS["gray"]};">{rec["category"]}</span>'
                f'</div>'
                f'<div style="font-weight:700; font-size:0.95rem; color:#2D3E50; margin-bottom:4px;">'
                f'{rec["title"]}</div>'
                f'<div style="font-size:0.85rem; color:#403833; margin-bottom:6px;">{rec["detail"]}</div>'
                f'<div style="font-size:0.85rem; color:{p_color}; font-weight:600;">'
                f'Action: {rec["action"]}</div>'
                f'</div>'
            )

        st.caption(f"Based on the last 30 days of data. {len(playbook_recs)} recommendation(s) generated.")
    else:
        st.success("No critical recommendations. Performance is healthy across all segments.")

    # ── Platform Health Scorecard ─────────────────────────────────
    st.markdown("---")
    st.subheader("Platform Health Scorecard")
    st.caption("Current health assessment based on the last 30 days vs industry benchmarks")

    health_rows = []
    for platform in sorted(df["platform"].unique()):
        for ctype in sorted(df[df["platform"] == platform]["campaign_type"].unique()):
            health = analyze_platform_health(df, platform, ctype, lookback_days=30)
            if health["health_score"] == 0:
                continue

            score = health["health_score"]
            kpis = health["kpi_values"]
            trends = health["kpi_trends"]
            vs_bench = health["vs_benchmark"]

            # Score emoji
            if score >= 70:
                score_emoji = "🟢"
            elif score >= 45:
                score_emoji = "🟡"
            else:
                score_emoji = "🔴"

            # Trend arrows
            _trend_arrows = {"rising": "↑", "falling": "↓", "stable": "→", "unknown": "—", "insufficient_data": "—"}

            health_rows.append({
                "Platform": platform,
                "Type": ctype,
                "Score": f"{score_emoji} {score}/100",
                "ROAS": f"{kpis.get('roas', 0):.1f}" if not pd.isna(kpis.get("roas")) else "—",
                "CPM Trend": _trend_arrows.get(trends.get("cpm", "unknown"), "—"),
                "CTR Trend": _trend_arrows.get(trends.get("ctr", "unknown"), "—"),
                "CVR Trend": _trend_arrows.get(trends.get("cvr", "unknown"), "—"),
                "CPM vs Bench": vs_bench.get("cpm", "—"),
                "CVR vs Bench": vs_bench.get("cvr", "—"),
                "Issues": str(len(health["issues"])),
            })

    if health_rows:
        st.dataframe(pd.DataFrame(health_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Trends: ↑ rising, ↓ falling, → stable. "
            "Benchmark status: excellent / normal / below_range / above_range."
        )
else:
    st.info("Upload data to see data-driven recommendations. Use the scenario map below as a reference.")


# ── Scenario-Based Strategy Map ───────────────────────────────
st.markdown("---")
st.subheader("Scenario-Based Strategy Map")
st.caption("Select the business situation to see recommended campaign actions")

scenarios = {
    "Private Sale / Flash Sale": {
        "Prospecting": [
            "Reduce prospecting spend by 20-30% during the sale",
            "Shift budget to retargeting where warm audiences convert better",
            "Pause broad audience testing during promotional periods",
            "Front-load prospecting spend in the week BEFORE the sale to build retargeting pools",
        ],
        "Retargeting": [
            "Scale retargeting spend by 30-50% during the sale",
            "Create urgency-based creatives (countdown, limited stock)",
            "Layer retargeting audiences: website visitors (7d), add-to-cart (14d), past purchasers (180d)",
            "Increase frequency cap slightly — users expect to see sale ads more often",
        ],
        "Creative Direction": [
            "Lead with the offer: % off, R$ savings, or bundle value",
            "Countdown timers and scarcity elements",
            "Before/after pricing comparisons",
            "Social proof: 'X sold in the last 24h'",
        ],
    },
    "Peak Seasonality (March, November)": {
        "Prospecting": [
            "Start scaling spend 2-3 weeks before the peak",
            "Monitor CPM inflation trajectory — compare to last year's pattern",
            "Broad audiences may outperform during high-intent periods",
            "Budget for 40-60% more than normal trading period",
        ],
        "Retargeting": [
            "Build retargeting pools aggressively in the 2 weeks before peak",
            "Deploy sequential messaging: awareness → consideration → conversion",
            "Include past purchasers for repurchase campaigns (mattress accessories, pillows)",
            "Prepare creative variants for retargeting fatigue during extended peaks",
        ],
        "Creative Direction": [
            "Seasonal hooks: sleep quality for back-to-school (March), gift-giving (November)",
            "Higher production value justifiable during peak periods",
            "A/B test promotional vs. value-led messaging",
            "Lifestyle imagery: bedrooms, wellness, sleep setups",
        ],
    },
    "Normal Trading Period": {
        "Prospecting": [
            "Maintain steady prospecting spend — this is where you build the funnel",
            "Run creative tests: 3-5 new variants per week per campaign",
            "Test new audiences and interest groups at small budgets",
            "Monitor CPM baselines — this period sets your benchmark",
        ],
        "Retargeting": [
            "Standard retargeting at baseline budget",
            "Focus on website visitors (7-14d window) and cart abandoners",
            "Keep frequency in check — fatigue is a bigger risk in non-peak periods",
            "Test different retargeting windows (7d vs 14d vs 30d)",
        ],
        "Creative Direction": [
            "UGC-style content for authenticity",
            "Product education: mattress technology, sleep science, material quality",
            "Customer testimonials and reviews",
            "Lifestyle content that builds brand association with quality sleep",
        ],
    },
    "Post-Peak Recovery": {
        "Prospecting": [
            "Reduce prospecting spend to 70-80% of normal for 1-2 weeks",
            "Audiences are saturated post-peak — give the algorithm time to reset",
            "Monitor CPM normalization — wait until CPM returns to baseline before scaling back up",
            "Use this period to analyze peak performance data and extract patterns",
        ],
        "Retargeting": [
            "Maintain retargeting for non-converters from the peak period",
            "Deploy 'missed it?' messaging for people who engaged but didn't buy",
            "Gradually reduce retargeting budget as the pool depletes (7-14 day wind-down)",
            "Capture learnings: which retargeting audiences converted best during peak?",
        ],
        "Creative Direction": [
            "Transition from promotional to value-based messaging",
            "No more urgency/scarcity — switch to benefit-led content",
            "Introduce new creative concepts to combat post-peak fatigue",
            "Plan the next quarter's creative pipeline based on peak learnings",
        ],
    },
    "ROAS Below Target for 3+ Days": {
        "Diagnostic Steps": [
            "Step 1: Check if it's happening across ALL platforms or just one (market-level vs platform-level)",
            "Step 2: Run the sub-KPI waterfall: CPM → CTR → CVR → AOV — find the broken link",
            "Step 3: Compare to YoY day-of-week data — is this historically expected?",
            "Step 4: Check platform status pages for outages or algorithm updates",
        ],
        "Actions by Root Cause": [
            "If CPM spike → shift budget to lower-CPM ad sets or platforms; refresh creatives",
            "If CTR drop → creative fatigue; rotate new creatives; check frequency metrics",
            "If CVR drop → landing page issue, offer mismatch, or audience quality decline",
            "If AOV drop → promotional pricing effect; may be intentional; check against orders volume",
            "If all metrics down → likely market-level event; hold steady and wait 48-72h before reacting",
        ],
        "Escalation Thresholds": [
            "Day 3: Internal review — document the situation and root cause analysis",
            "Day 5: Present to manager with data and proposed action plan",
            "Day 7: Strategy adjustment — if not recovering, implement budget reallocation",
        ],
    },
}

for scenario_name, sections in scenarios.items():
    with st.expander(f"**{scenario_name}**", expanded=False):
        for section_name, items in sections.items():
            st.markdown(f"**{section_name}:**")
            for item in items:
                st.markdown(f"- {item}")
            st.markdown("")

# ── Advantage+ CBO Test Tracker ───────────────────────────────
st.markdown("---")
st.subheader("Advantage+ CBO Test Tracker")

if settings.get("cbo_test_active", False):
    st.success("CBO test is currently **active**")

    start_date_str = settings.get("cbo_test_start_date")
    min_roas = settings.get("cbo_test_min_roas", 7.0)
    duration_weeks = settings.get("cbo_test_duration_weeks", 4)

    if start_date_str:
        start_date = pd.Timestamp(start_date_str)
        weeks_elapsed = max(0, (pd.Timestamp(datetime.now()) - start_date).days // 7)
        st.markdown(f"**Start Date:** {start_date.strftime('%d/%m/%Y')}")
        st.markdown(f"**Weeks Elapsed:** {weeks_elapsed} of {duration_weeks}")

        # Progress bar
        progress = min(weeks_elapsed / duration_weeks, 1.0)
        st.progress(progress, text=f"Week {weeks_elapsed}/{duration_weeks}")

    st.markdown("---")
    st.markdown("**Decision Framework:**")

    decision_data = [
        {"Condition": "ROAS >= 7.5 + good volume", "Decision": "SCALE", "Action": "Increase CBO budget gradually; consider shifting more ABO budget"},
        {"Condition": "ROAS 7.0 - 7.5", "Decision": "EXTEND TEST", "Action": "Continue test for 1-2 more weeks to gather more data"},
        {"Condition": "ROAS 7.0 - 8.0 but low volume", "Decision": "INVESTIGATE", "Action": "Check if CBO is spending on a narrow subset; review auction insights"},
        {"Condition": "ROAS < 7.0 after 4 weeks", "Decision": "KILL", "Action": "End test; document learnings; plan retest with different creative set"},
    ]
    st.dataframe(pd.DataFrame(decision_data), use_container_width=True, hide_index=True)

    # Weekly log input
    st.markdown("---")
    st.markdown("**Weekly CBO Log:**")

    if "cbo_log" not in st.session_state:
        st.session_state.cbo_log = []

    with st.form("cbo_log_form"):
        cbo_col1, cbo_col2, cbo_col3 = st.columns(3)
        with cbo_col1:
            cbo_week = st.number_input("Week #", min_value=1, max_value=12, value=1)
            cbo_roas = st.number_input("CBO ROAS", min_value=0.0, step=0.1)
        with cbo_col2:
            abo_roas = st.number_input("ABO Benchmark ROAS", min_value=0.0, step=0.1)
            cbo_spend = st.number_input("CBO Spend (R$)", min_value=0.0, step=100.0)
        with cbo_col3:
            cbo_orders = st.number_input("CBO Orders", min_value=0, step=1)
            cbo_notes = st.text_input("Notes")

        if st.form_submit_button("Log Week"):
            entry = {
                "week": cbo_week,
                "cbo_roas": cbo_roas,
                "abo_roas": abo_roas,
                "cbo_spend": cbo_spend,
                "cbo_orders": cbo_orders,
                "notes": cbo_notes,
                "timestamp": datetime.now().isoformat(),
            }
            st.session_state.cbo_log.append(entry)
            st.success(f"Week {cbo_week} logged.")

    if st.session_state.cbo_log:
        log_df = pd.DataFrame(st.session_state.cbo_log)
        st.dataframe(log_df, use_container_width=True, hide_index=True)
else:
    st.info(
        "No CBO test currently active. Enable it in Settings to start tracking."
    )

# ── Platform-Specific Notes ───────────────────────────────────
st.markdown("---")
st.subheader("Platform-Specific Notes")

platform_tabs = st.tabs(["Meta (Andromeda)", "TikTok", "YouTube", "Pinterest"])

with platform_tabs[0]:
    st.markdown("""
    **Meta — Andromeda Algorithm Update**

    - **Creative volume is the new targeting lever.** Aim for 3-5 new creative variants per week per campaign.
    Each variant should test one variable: hook, format, offer framing, or CTA.
    - **Broad audiences become more viable for prospecting.** Consider testing one campaign with minimal
    targeting (age/gender/location only) and letting the algorithm's creative-based matching work.
    - **Ad-level tracking matters more than ad set-level.** Track top 3 and bottom 3 ads by ROAS weekly.
    This becomes your creative scoreboard.
    - **Advantage+ Shopping campaigns** use machine learning across the full funnel. Test head-to-head
    against ABO with identical assets before scaling.
    """)

with platform_tabs[1]:
    st.markdown("""
    **TikTok**

    - **Creative refresh cycle: 7-10 days.** Fatigue hits faster than Meta. Plan for it in your weekly review.
    - **Native-feeling content outperforms polished ads.** UGC-style, quick-cut, vertical video with text overlays.
    - **Monitor view-through conversions alongside click-through.** TikTok's attribution can undercount
    if you only look at last-click.
    - **Trending sounds and formats** can boost distribution. Check TikTok Creative Center weekly.
    """)

with platform_tabs[2]:
    st.markdown("""
    **YouTube**

    - **Video Action Campaigns (VAC)** for conversion focus. This is your conversion-optimized format.
    - **First 5 seconds are everything.** Front-load the value proposition and product shot before the skip button.
    - **Retargeting on YouTube:** Customer lists and website visitor audiences. Short (15s) reminder-style
    ads with direct CTA.
    - **Bumper ads (6s)** work well for brand reinforcement in retargeting sequences.
    """)

with platform_tabs[3]:
    st.markdown("""
    **Pinterest (Prospecting Only)**

    - **Longer consideration cycle.** Users plan ahead. Expect lower direct ROAS but potential contribution
    to assisted conversions.
    - **Lifestyle imagery works best:** Bedrooms, sleep setups, wellness aesthetics. Less promotional,
    more aspirational.
    - **Seasonal pins:** Launch seasonal content 4-6 weeks before the event to build organic traction
    alongside paid.
    - **Track view-through conversions** if available — Pinterest's path to purchase is longer than other platforms.
    """)
