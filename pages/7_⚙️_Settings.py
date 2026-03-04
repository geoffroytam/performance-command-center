"""Settings page — Configure targets, baselines, campaign parsing rules, and forecasting."""

import streamlit as st
import json
import calendar as cal_module

from utils.constants import (
    load_settings,
    save_settings,
    DEFAULT_SETTINGS,
    SETTINGS_FILE,
)
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Settings", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Settings", "Configure targets, baselines, campaign parsing, and forecasting")

# Load current settings
settings = load_settings()

# ── Tabbed Layout ────────────────────────────────────────────
tab_targets, tab_baselines, tab_parsing, tab_platform, tab_forecast, tab_display = st.tabs([
    "ROAS Targets",
    "Baselines & Anomaly",
    "Campaign Parsing",
    "Platform Rules",
    "Forecasting",
    "Display",
])

# ═══════════════════════════════════════════════════════════════
# TAB 1: ROAS TARGETS
# ═══════════════════════════════════════════════════════════════
with tab_targets:
    st.subheader("ROAS Targets")
    st.caption("Target ROAS for each campaign type, used across forecasting and diagnosis.")

    col1, col2 = st.columns(2)
    with col1:
        settings["roas_target_prospecting"] = st.number_input(
            "Prospecting ROAS Target",
            min_value=0.0,
            max_value=100.0,
            value=float(settings.get("roas_target_prospecting", 8)),
            step=0.5,
            help="Target ROAS for prospecting campaigns across all platforms",
        )
    with col2:
        settings["roas_target_retargeting"] = st.number_input(
            "Retargeting ROAS Target",
            min_value=0.0,
            max_value=100.0,
            value=float(settings.get("roas_target_retargeting", 14)),
            step=0.5,
            help="Target ROAS for retargeting campaigns across all platforms",
        )

# ═══════════════════════════════════════════════════════════════
# TAB 2: BASELINES & ANOMALY
# ═══════════════════════════════════════════════════════════════
with tab_baselines:
    st.subheader("Baseline Windows")
    st.caption("Number of days used to calculate rolling baselines")

    col1, col2 = st.columns(2)
    with col1:
        settings["aov_baseline_days"] = st.number_input(
            "AOV Baseline (days)",
            min_value=7,
            max_value=180,
            value=int(settings.get("aov_baseline_days", 60)),
            help="Long window for AOV — smooths out promotional spikes",
        )
    with col2:
        cpm_days_val = st.number_input(
            "CPM / CTR / CVR / ROAS Baseline (days)",
            min_value=7,
            max_value=60,
            value=int(settings.get("cpm_baseline_days", 14)),
            help="Short window used for CPM, CTR (LPV), CVR (LPV), and ROAS baselines",
        )
        settings["cpm_baseline_days"] = cpm_days_val
        settings["ctr_baseline_days"] = cpm_days_val
        settings["cvr_baseline_days"] = cpm_days_val

    st.markdown("---")
    st.subheader("Anomaly Detection")
    settings["anomaly_threshold_pct"] = st.slider(
        "Anomaly Threshold (%)",
        min_value=5,
        max_value=50,
        value=int(settings.get("anomaly_threshold_pct", 15)),
        step=1,
        help="Flag KPIs that deviate more than this percentage from baseline",
    )

# ═══════════════════════════════════════════════════════════════
# TAB 3: CAMPAIGN PARSING
# ═══════════════════════════════════════════════════════════════
with tab_parsing:
    st.subheader("Campaign Name Parsing Keywords")
    st.caption(
        "These keywords are used to classify campaigns from their names. "
        "Enter comma-separated values."
    )

    col1, col2 = st.columns(2)
    with col1:
        prosp_text = st.text_input(
            "Prospecting Keywords",
            value=", ".join(settings.get("prospecting_keywords", [])),
            help="Keywords in campaign names that indicate prospecting",
        )
        settings["prospecting_keywords"] = [
            k.strip() for k in prosp_text.split(",") if k.strip()
        ]

        retarg_text = st.text_input(
            "Retargeting Keywords",
            value=", ".join(settings.get("retargeting_keywords", [])),
            help="Keywords in campaign names that indicate retargeting",
        )
        settings["retargeting_keywords"] = [
            k.strip() for k in retarg_text.split(",") if k.strip()
        ]

    with col2:
        premium_text = st.text_input(
            "Premium Product Keywords",
            value=", ".join(settings.get("premium_keywords", [])),
        )
        settings["premium_keywords"] = [
            k.strip() for k in premium_text.split(",") if k.strip()
        ]

        coupon_text = st.text_input(
            "Coupon/Discount Keywords",
            value=", ".join(settings.get("coupon_keywords", [])),
        )
        settings["coupon_keywords"] = [
            k.strip() for k in coupon_text.split(",") if k.strip()
        ]

        non_prem_text = st.text_input(
            "Non-Premium Product Keywords",
            value=", ".join(settings.get("non_premium_keywords", [])),
        )
        settings["non_premium_keywords"] = [
            k.strip() for k in non_prem_text.split(",") if k.strip()
        ]

# ═══════════════════════════════════════════════════════════════
# TAB 4: PLATFORM RULES
# ═══════════════════════════════════════════════════════════════
with tab_platform:
    st.subheader("Platform-Specific Rules")
    settings["pinterest_always_prospecting"] = st.checkbox(
        "Pinterest: Always classify as Prospecting (no retargeting)",
        value=settings.get("pinterest_always_prospecting", True),
    )

    st.markdown("---")
    st.subheader("Advantage+ CBO Test Tracking")
    settings["cbo_test_active"] = st.checkbox(
        "CBO test currently active",
        value=settings.get("cbo_test_active", False),
    )

    if settings["cbo_test_active"]:
        col1, col2, col3 = st.columns(3)
        with col1:
            settings["cbo_test_start_date"] = st.date_input(
                "Test Start Date",
                value=None,
            )
            if settings["cbo_test_start_date"]:
                settings["cbo_test_start_date"] = str(settings["cbo_test_start_date"])
        with col2:
            settings["cbo_test_min_roas"] = st.number_input(
                "Minimum ROAS Threshold",
                min_value=0.0,
                max_value=50.0,
                value=float(settings.get("cbo_test_min_roas", 7.0)),
                step=0.5,
            )
        with col3:
            settings["cbo_test_duration_weeks"] = st.number_input(
                "Test Duration (weeks)",
                min_value=1,
                max_value=12,
                value=int(settings.get("cbo_test_duration_weeks", 4)),
            )

# ═══════════════════════════════════════════════════════════════
# TAB 5: FORECASTING
# ═══════════════════════════════════════════════════════════════
with tab_forecast:
    st.subheader("Forecasting Configuration")

    # ── Year Weights ──────────────────────────────────────────
    st.markdown("**Year Weights for Trend Calculation**")
    st.caption(
        "Weight recent years more heavily when computing MoM trends. "
        "Weights are relative — they don't need to sum to 1."
    )
    year_weights = settings.get("forecast_year_weights", {"2025": 0.6, "2024": 0.4})
    col1, col2 = st.columns(2)
    with col1:
        w_2025 = st.number_input(
            "2025 Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(year_weights.get("2025", year_weights.get(2025, 0.6))),
            step=0.1,
            key="yw_2025",
        )
    with col2:
        w_2024 = st.number_input(
            "2024 Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(year_weights.get("2024", year_weights.get(2024, 0.4))),
            step=0.1,
            key="yw_2024",
        )
    settings["forecast_year_weights"] = {"2025": w_2025, "2024": w_2024}

    st.markdown("---")

    # ── Promotional Anomaly Exclusions ────────────────────────
    st.markdown("**Promotional Anomaly Exclusions**")
    st.caption(
        "Mark months to exclude from baseline/trend calculations — "
        "e.g., Black Friday spikes, flash sales that won't repeat."
    )

    existing_anomalies = list(settings.get("forecast_promotional_anomalies", []))

    # Display existing anomalies
    if existing_anomalies:
        for i, anomaly in enumerate(existing_anomalies):
            month_name = cal_module.month_name[anomaly.get("month", 1)]
            acol1, acol2 = st.columns([4, 1])
            with acol1:
                st.markdown(
                    f"- **{anomaly.get('year', '')} {month_name}** — {anomaly.get('label', 'No label')}"
                )
            with acol2:
                if st.button("Remove", key=f"rm_anomaly_{i}"):
                    existing_anomalies.pop(i)
                    settings["forecast_promotional_anomalies"] = existing_anomalies
                    st.rerun()
    else:
        st.caption("No exclusions defined.")

    # Add new anomaly
    with st.expander("Add exclusion"):
        acol1, acol2, acol3 = st.columns(3)
        with acol1:
            anomaly_year = st.number_input("Year", min_value=2020, max_value=2030, value=2025, key="new_anom_yr")
        with acol2:
            anomaly_month = st.selectbox(
                "Month",
                range(1, 13),
                format_func=lambda m: cal_module.month_name[m],
                key="new_anom_month",
            )
        with acol3:
            anomaly_label = st.text_input("Label", placeholder="e.g., Black Friday", key="new_anom_label")

        if st.button("Add Exclusion", type="primary"):
            if anomaly_label:
                existing_anomalies.append({
                    "year": int(anomaly_year),
                    "month": int(anomaly_month),
                    "label": anomaly_label,
                })
                settings["forecast_promotional_anomalies"] = existing_anomalies
                st.success(f"Added: {anomaly_year} {cal_module.month_name[anomaly_month]} — {anomaly_label}")
            else:
                st.warning("Please enter a label for the exclusion.")

    settings["forecast_promotional_anomalies"] = existing_anomalies

    st.markdown("---")

    # ── Confidence Band Widths ────────────────────────────────
    st.markdown("**Confidence Band Widths**")
    st.caption("How wide the forecast uncertainty bands should be at different horizons.")
    bands = settings.get("forecast_confidence_bands", {"1_month": 10, "2_months": 20, "3_months": 30})
    col1, col2, col3 = st.columns(3)
    with col1:
        band_1m = st.number_input(
            "1 Month Out (+/- %)",
            min_value=1,
            max_value=50,
            value=int(bands.get("1_month", 10)),
            step=1,
            key="band_1m",
        )
    with col2:
        band_2m = st.number_input(
            "2 Months Out (+/- %)",
            min_value=1,
            max_value=50,
            value=int(bands.get("2_months", 20)),
            step=1,
            key="band_2m",
        )
    with col3:
        band_3m = st.number_input(
            "3+ Months Out (+/- %)",
            min_value=1,
            max_value=50,
            value=int(bands.get("3_months", 30)),
            step=1,
            key="band_3m",
        )
    settings["forecast_confidence_bands"] = {
        "1_month": band_1m,
        "2_months": band_2m,
        "3_months": band_3m,
    }

    st.markdown("---")

    # ── Risk Thresholds ───────────────────────────────────────
    st.markdown("**Risk Thresholds**")
    col1, col2 = st.columns(2)
    with col1:
        settings["forecast_stressed_roas_threshold"] = st.number_input(
            "Stressed ROAS Alert Threshold",
            min_value=0.0,
            max_value=50.0,
            value=float(settings.get("forecast_stressed_roas_threshold", 6.0)),
            step=0.5,
            help="Alert when stressed (conservative) ROAS falls below this value",
            key="stressed_roas",
        )
    with col2:
        settings["forecast_spend_warning_threshold"] = st.number_input(
            "Spend Deviation Warning (%)",
            min_value=5,
            max_value=100,
            value=int(settings.get("forecast_spend_warning_threshold", 20)),
            step=5,
            help="Warn if planned spend deviates more than this % from historical pattern",
            key="spend_warning",
        )

# ═══════════════════════════════════════════════════════════════
# TAB 6: DISPLAY
# ═══════════════════════════════════════════════════════════════
with tab_display:
    st.subheader("Display Settings")
    col1, col2 = st.columns(2)
    with col1:
        settings["currency"] = st.selectbox(
            "Currency",
            ["BRL", "USD", "EUR"],
            index=["BRL", "USD", "EUR"].index(settings.get("currency", "BRL")),
        )
    with col2:
        settings["date_format"] = st.selectbox(
            "Date Format",
            ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"],
            index=["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"].index(
                settings.get("date_format", "DD/MM/YYYY")
            ),
        )

# ═══════════════════════════════════════════════════════════════
# SAVE / RESET / EXPORT (outside tabs — applies to all)
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    if st.button("Save Settings", type="primary", use_container_width=True):
        save_settings(settings)
        st.session_state.settings = settings
        st.success("Settings saved successfully.")
with col2:
    if st.button("Reset to Defaults", use_container_width=True):
        save_settings(DEFAULT_SETTINGS)
        st.session_state.settings = DEFAULT_SETTINGS.copy()
        st.success("Settings reset to defaults.")
        st.rerun()
with col3:
    if st.button("Export Settings JSON", use_container_width=True):
        st.download_button(
            "Download",
            data=json.dumps(settings, indent=2, default=str),
            file_name="settings.json",
            mime="application/json",
        )

# ── Current Settings Preview ──────────────────────────────────
with st.expander("View current settings (JSON)"):
    st.json(settings)
