"""Settings page — Configure targets, baselines, campaign parsing rules."""

import streamlit as st
import json

from utils.constants import (
    load_settings,
    save_settings,
    DEFAULT_SETTINGS,
    SETTINGS_FILE,
)
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Settings", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Settings", "Configure targets, baselines, and campaign parsing rules")

# Load current settings
settings = load_settings()

# ── ROAS Targets ──────────────────────────────────────────────
st.header("ROAS Targets")
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

st.divider()

# ── Baseline Windows ──────────────────────────────────────────
st.header("Baseline Windows")
st.caption("Number of days used to calculate rolling baselines")

col1, col2, col3, col4 = st.columns(4)
with col1:
    settings["aov_baseline_days"] = st.number_input(
        "AOV Baseline (days)",
        min_value=7,
        max_value=180,
        value=int(settings.get("aov_baseline_days", 60)),
        help="Long window for AOV to smooth promotional spikes",
    )
with col2:
    settings["cpm_baseline_days"] = st.number_input(
        "CPM Baseline (days)",
        min_value=7,
        max_value=60,
        value=int(settings.get("cpm_baseline_days", 14)),
    )
with col3:
    settings["ctr_baseline_days"] = st.number_input(
        "CTR Baseline (days)",
        min_value=7,
        max_value=60,
        value=int(settings.get("ctr_baseline_days", 14)),
    )
with col4:
    settings["cvr_baseline_days"] = st.number_input(
        "CVR Baseline (days)",
        min_value=7,
        max_value=60,
        value=int(settings.get("cvr_baseline_days", 14)),
    )

st.divider()

# ── Anomaly Threshold ─────────────────────────────────────────
st.header("Anomaly Detection")
settings["anomaly_threshold_pct"] = st.slider(
    "Anomaly Threshold (%)",
    min_value=5,
    max_value=50,
    value=int(settings.get("anomaly_threshold_pct", 15)),
    step=1,
    help="Flag KPIs that deviate more than this percentage from baseline",
)

st.divider()

# ── Campaign Name Parsing ─────────────────────────────────────
st.header("Campaign Name Parsing Keywords")
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

st.divider()

# ── Platform Rules ────────────────────────────────────────────
st.header("Platform-Specific Rules")
settings["pinterest_always_prospecting"] = st.checkbox(
    "Pinterest: Always classify as Prospecting (no retargeting)",
    value=settings.get("pinterest_always_prospecting", True),
)

st.divider()

# ── Advantage+ CBO Test ──────────────────────────────────────
st.header("Advantage+ CBO Test Tracking")
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

st.divider()

# ── Display Settings ──────────────────────────────────────────
st.header("Display")
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

st.divider()

# ── Save / Reset ──────────────────────────────────────────────
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
