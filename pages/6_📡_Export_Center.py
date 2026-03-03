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
st.subheader("Export Filters")

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
st.info(f"Export will include **{preview_count:,}** rows from **{len(selected_platforms)}** platforms")

# ── Export Buttons ────────────────────────────────────────────
st.markdown("---")

col_excel, col_pptx, col_pbi = st.columns(3)

with col_excel:
    st.markdown("### Excel Report")
    st.markdown(
        "Full report with daily, weekly, and monthly sheets. "
        "Includes conditional formatting, baselines, and embedded charts."
    )
    include_charts = st.checkbox("Include charts in Excel", value=True, key="excel_charts")

    if st.button("Generate Excel", type="primary", use_container_width=True, key="gen_excel"):
        with st.spinner("Generating Excel report..."):
            try:
                excel_buffer = generate_excel_report(
                    export_df,
                    start_date,
                    end_date,
                    platforms=selected_platforms,
                    include_charts=include_charts,
                )
                filename = f"Performance_Report_{start_date}_{end_date}.xlsx"
                st.download_button(
                    label="Download Excel",
                    data=excel_buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
                st.success("Excel report generated.")
            except Exception as e:
                st.error(f"Error generating Excel report: {e}")

with col_pptx:
    st.markdown("### PowerPoint Report")
    st.markdown(
        "Presentation-ready slides with executive summary, "
        "platform breakdowns, and trend charts."
    )
    st.caption("Charts require `kaleido` package for image export")

    if st.button("Generate PowerPoint", type="primary", use_container_width=True, key="gen_pptx"):
        with st.spinner("Generating PowerPoint report..."):
            try:
                pptx_buffer = generate_pptx_report(
                    export_df,
                    start_date,
                    end_date,
                    platforms=selected_platforms,
                )
                filename = f"Performance_Report_{start_date}_{end_date}.pptx"
                st.download_button(
                    label="Download PowerPoint",
                    data=pptx_buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
                st.success("PowerPoint report generated.")
            except Exception as e:
                st.error(f"Error generating PowerPoint report: {e}")

with col_pbi:
    st.markdown("### Power BI Data Model")
    st.markdown(
        "Structured Excel file with fact and dimension tables. "
        "Ready for Power BI import with relationships."
    )
    st.caption("Sheets: fact_daily, dim_platform, dim_baselines, fact_forecast")

    if st.button("Generate Power BI File", type="primary", use_container_width=True, key="gen_pbi"):
        with st.spinner("Generating Power BI data model..."):
            try:
                pbi_buffer = generate_powerbi_export(
                    export_df,
                    start_date,
                    end_date,
                    platforms=selected_platforms,
                )
                filename = f"PowerBI_DataModel_{start_date}_{end_date}.xlsx"
                st.download_button(
                    label="Download Power BI File",
                    data=pbi_buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
                st.success("Power BI data model generated.")
            except Exception as e:
                st.error(f"Error generating Power BI file: {e}")

# ── Export Schema Reference ───────────────────────────────────
st.markdown("---")
with st.expander("Power BI Schema Reference"):
    st.markdown("""
    **fact_daily** — One row per date x platform x campaign_type x product_tier
    - `date`, `platform`, `campaign_type`, `product_tier`
    - `spend`, `impressions`, `clicks`, `conversions`, `revenue`
    - `cpm`, `ctr`, `cvr`, `aov`, `roas`, `cpa`

    **dim_platform** — Platform dimension table
    - `platform`, `roas_target_prospecting`, `roas_target_retargeting`

    **dim_baselines** — Current baseline values per platform x campaign_type
    - `platform`, `campaign_type`
    - `baseline_aov_60d`, `baseline_cpm_14d`, `baseline_ctr_14d`, `baseline_cvr_14d`

    **fact_forecast** — Forecast vs actuals
    - `month`, `platform`, `campaign_type`
    - `forecast_spend`, `forecast_revenue`, `forecast_roas`
    - `actual_spend`, `actual_revenue`, `actual_roas`, `delta_pct`

    **Relationships:**
    - `fact_daily.platform` → `dim_platform.platform`
    - `fact_daily.platform + campaign_type` → `dim_baselines.platform + campaign_type`
    """)
