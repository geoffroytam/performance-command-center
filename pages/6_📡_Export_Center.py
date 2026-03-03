"""Export Center — Generate downloadable reports in Excel, PowerPoint, and Power BI formats."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from utils.data_loader import load_all_data
from utils.export_excel import generate_excel_report
from utils.export_pptx import generate_pptx_report
from utils.export_powerbi import generate_powerbi_export
from utils.constants import PLATFORMS, COLORS, load_settings
from utils.theme import inject_objectif_lune_css, render_header

st.set_page_config(page_title="Export Center", page_icon="🚀", layout="wide")
inject_objectif_lune_css()

render_header("Export Center", "Generate downloadable reports — Excel, PowerPoint, Power BI")

# ── Load Data ─────────────────────────────────────────────────
if "data" not in st.session_state or st.session_state.data.empty:
    df = load_all_data()
    if df.empty:
        st.warning("No data loaded. Upload CSV files from the main page.")
        st.stop()
    st.session_state.data = df

df = st.session_state.data

# ── Export Filters ────────────────────────────────────────────
st.subheader("Filters")

col1, col2, col3 = st.columns(3)

with col1:
    max_date = df["date"].max().date()
    min_date = df["date"].min().date()
    date_range = st.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="export_dates",
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

with col2:
    available_platforms = sorted(df["platform"].unique().tolist())
    selected_platforms = st.multiselect(
        "Platforms",
        available_platforms,
        default=available_platforms,
    )

with col3:
    campaign_filter = st.selectbox(
        "Campaign Type",
        ["All", "Prospecting", "Retargeting"],
    )

# Apply campaign type filter
export_df = df.copy()
if campaign_filter != "All":
    export_df = export_df[export_df["campaign_type"] == campaign_filter]

# Preview
filtered_mask = (
    (export_df["date"] >= pd.Timestamp(start_date))
    & (export_df["date"] <= pd.Timestamp(end_date))
    & (export_df["platform"].isin(selected_platforms))
)
preview_count = filtered_mask.sum()
days_count = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1

st.caption(
    f"**{preview_count:,}** rows · **{len(selected_platforms)}** platforms · "
    f"**{days_count}** days ({start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')})"
)

# ── Export Cards ──────────────────────────────────────────────
st.markdown("---")

col_excel, col_pptx, col_pbi = st.columns(3)

# ── Excel ─────────────────────────────────────────────────────
with col_excel:
    st.markdown("#### Excel Report")
    st.caption(
        "Executive summary, daily/weekly/monthly data with conditional formatting, "
        "baselines, and ROAS charts. Ready to share with your team."
    )

    if st.button("Generate Excel", type="primary", use_container_width=True, key="gen_excel"):
        with st.spinner("Building Excel report..."):
            try:
                excel_buffer = generate_excel_report(
                    export_df,
                    start_date,
                    end_date,
                    platforms=selected_platforms,
                )
                filename = f"Performance_Report_{start_date}_{end_date}.xlsx"
                st.download_button(
                    label="Download .xlsx",
                    data=excel_buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Error: {e}")

# ── PowerPoint ────────────────────────────────────────────────
with col_pptx:
    st.markdown("#### PowerPoint Deck")
    st.caption(
        "Presentation-ready slides: executive summary, platform breakdown, "
        "per-platform deep dives, and auto-generated key takeaways."
    )

    if st.button("Generate PowerPoint", type="primary", use_container_width=True, key="gen_pptx"):
        with st.spinner("Building PowerPoint deck..."):
            try:
                pptx_buffer = generate_pptx_report(
                    export_df,
                    start_date,
                    end_date,
                    platforms=selected_platforms,
                )
                filename = f"Performance_Report_{start_date}_{end_date}.pptx"
                st.download_button(
                    label="Download .pptx",
                    data=pptx_buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Error: {e}")

# ── Power BI ─────────────────────────────────────────────────
with col_pbi:
    st.markdown("#### Power BI Model")
    st.caption(
        "Structured data model with fact tables (daily/weekly/monthly), "
        "dimension tables (date, platform, baselines), and forecast vs actuals."
    )

    if st.button("Generate Power BI", type="primary", use_container_width=True, key="gen_pbi"):
        with st.spinner("Building Power BI data model..."):
            try:
                pbi_buffer = generate_powerbi_export(
                    export_df,
                    start_date,
                    end_date,
                    platforms=selected_platforms,
                )
                filename = f"PowerBI_Model_{start_date}_{end_date}.xlsx"
                st.download_button(
                    label="Download .xlsx",
                    data=pbi_buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Error: {e}")

# ── Schema Reference ─────────────────────────────────────────
st.markdown("---")
with st.expander("Power BI Schema & Relationships"):
    st.markdown("""**Fact Tables:**
- `fact_daily` — date × platform × campaign_type (spend, revenue, impressions, clicks, conversions, KPIs)
- `fact_weekly` — week × platform × campaign_type (pre-aggregated)
- `fact_monthly` — month × platform × campaign_type (pre-aggregated)
- `fact_forecast` — forecast vs actuals by month × platform

**Dimension Tables:**
- `dim_date` — calendar dimension (year, quarter, month, week, day, weekend flag)
- `dim_platform` — platform + ROAS targets
- `dim_campaign_type` — campaign type + ROAS target
- `dim_baselines` — current rolling baselines per platform × type

**Relationships:**
- `fact_daily.date` → `dim_date.date`
- `fact_daily.platform` → `dim_platform.platform`
- `fact_daily.campaign_type` → `dim_campaign_type.campaign_type`
- `fact_daily.platform + campaign_type` → `dim_baselines.platform + campaign_type`""")
