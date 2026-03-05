"""Performance Marketing Command Center — Main entry point."""

import streamlit as st
import pandas as pd
from pathlib import Path

from utils.data_loader import (
    process_uploaded_file,
    load_all_data,
    save_merged_data,
    get_data_summary,
)
from utils.constants import PLATFORMS, COLORS, PROCESSED_DIR, load_settings
from utils.theme import inject_objectif_lune_css, render_header, render_sidebar_brand, render_welcome_rocket

st.set_page_config(
    page_title="Objectif Lune — Command Center",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialize Session State ──────────────────────────────────
if "data" not in st.session_state:
    st.session_state.data = load_all_data()
if "settings" not in st.session_state:
    st.session_state.settings = load_settings()
if "upload_counter" not in st.session_state:
    st.session_state.upload_counter = 0


def main():
    inject_objectif_lune_css()

    # ── Sidebar ─────────────────────────────────────────────────
    with st.sidebar:
        render_sidebar_brand()

        # Data status — always visible, compact
        df = st.session_state.data
        if df.empty:
            st.caption("No data loaded")
        else:
            summary = get_data_summary(df)
            st.caption(
                f"**{summary['total_rows']:,} rows** · "
                f"{summary['date_range'][0].strftime('%d/%m/%Y')} – "
                f"{summary['date_range'][1].strftime('%d/%m/%Y')}"
            )

        st.divider()

        # File upload — inside expander to save vertical space
        expand_upload = df.empty  # auto-expand when no data loaded
        with st.expander("Upload Data", expanded=expand_upload):
            platform_choice = st.selectbox(
                "Platform",
                ["Auto-detect"] + PLATFORMS,
                key="platform_select",
                label_visibility="collapsed",
            )
            uploaded_files = st.file_uploader(
                "CSV files",
                type=["csv"],
                accept_multiple_files=True,
                label_visibility="collapsed",
                key=f"uploader_{st.session_state.upload_counter}",
            )

            if uploaded_files:
                if st.button("Process", type="primary", use_container_width=True):
                    all_new = []
                    for file in uploaded_files:
                        with st.spinner(f"{file.name}..."):
                            override = None if platform_choice == "Auto-detect" else platform_choice
                            result_df, detected, warnings = process_uploaded_file(file, override)

                            if not result_df.empty:
                                all_new.append(result_df)
                                st.success(f"✅ {file.name} ({len(result_df)} rows)")
                            else:
                                st.error(f"❌ {file.name}")
                            for w in warnings:
                                st.warning(w)

                    if all_new:
                        new_data = pd.concat(all_new, ignore_index=True)
                        if not st.session_state.data.empty:
                            combined = pd.concat(
                                [st.session_state.data, new_data], ignore_index=True
                            )
                            dedup_cols_full = ["date", "platform", "campaign_name", "adset_name", "campaign_type"]
                            dedup_cols = [c for c in dedup_cols_full if c in combined.columns]
                            combined = combined.drop_duplicates(subset=dedup_cols, keep="last")
                        else:
                            combined = new_data
                        st.session_state.data = combined
                        save_merged_data(combined)
                        st.session_state.upload_counter += 1
                        st.rerun()

        # Clear data button — only when data is loaded
        if not st.session_state.data.empty:
            if st.button("Clear All Data", type="secondary", use_container_width=True):
                st.session_state.data = pd.DataFrame()
                processed_file = PROCESSED_DIR / "merged_data.parquet"
                if processed_file.exists():
                    processed_file.unlink()
                st.session_state.upload_counter += 1
                st.rerun()

    # ── Main Content ──────────────────────────────────────────
    render_header(
        "Performance Command Center",
        "Daily performance analysis for paid social campaigns — Meta · TikTok · YouTube · Pinterest",
    )

    if st.session_state.data.empty:
        render_welcome_rocket()

        col_l, col_m, col_r = st.columns([1, 2, 1])
        with col_m:
            st.markdown(
                """
                **How to start:**
                1. Upload CSV exports from the sidebar
                2. The app auto-detects the platform format
                3. Navigate to **Morning Ritual** for your daily check

                **Supported formats:**

                Your existing **Excel tracker** (auto-detected) or raw exports from
                **Meta**, **TikTok**, **YouTube**, or **Pinterest**.

                Upload multiple files — they merge automatically.
                """
            )
    else:
        # Show overview dashboard
        df = st.session_state.data
        summary = get_data_summary(df)

        def _fmt_compact(value: float) -> str:
            """Format large currency values compactly: 30.2M, 248.1M, 1.2B."""
            if abs(value) >= 1_000_000_000:
                return f"R$ {value / 1_000_000_000:,.1f}B"
            if abs(value) >= 1_000_000:
                return f"R$ {value / 1_000_000:,.1f}M"
            if abs(value) >= 1_000:
                return f"R$ {value / 1_000:,.1f}K"
            return f"R$ {value:,.2f}"

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Spend", _fmt_compact(summary['total_spend']))
        with col2:
            st.metric("Total Revenue", _fmt_compact(summary['total_revenue']))
        with col3:
            blended_roas = summary["total_revenue"] / summary["total_spend"] if summary["total_spend"] > 0 else 0
            st.metric("Blended ROAS", f"{blended_roas:.1f}")
        with col4:
            total_orders = df["conversions"].sum()
            st.metric("Total Orders", f"{total_orders:,.0f}")

        st.markdown("---")

        # Data breakdown
        st.subheader("Data Overview")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**By Platform:**")
            platform_summary = (
                df.groupby("platform")
                .agg(spend=("spend", "sum"), revenue=("revenue", "sum"), rows=("spend", "count"))
                .reset_index()
            )
            platform_summary["roas"] = (
                platform_summary["revenue"] / platform_summary["spend"]
            ).round(1)
            platform_summary["spend"] = platform_summary["spend"].apply(lambda x: f"R$ {x:,.0f}")
            platform_summary["revenue"] = platform_summary["revenue"].apply(lambda x: f"R$ {x:,.0f}")
            platform_summary.columns = ["Platform", "Spend", "Revenue", "Rows", "ROAS"]
            st.dataframe(platform_summary, use_container_width=True, hide_index=True)

        with col_b:
            st.markdown("**By Campaign Type:**")
            type_summary = (
                df.groupby("campaign_type")
                .agg(spend=("spend", "sum"), revenue=("revenue", "sum"), rows=("spend", "count"))
                .reset_index()
            )
            type_summary["roas"] = (
                type_summary["revenue"] / type_summary["spend"]
            ).round(1)
            type_summary["spend"] = type_summary["spend"].apply(lambda x: f"R$ {x:,.0f}")
            type_summary["revenue"] = type_summary["revenue"].apply(lambda x: f"R$ {x:,.0f}")
            type_summary.columns = ["Campaign Type", "Spend", "Revenue", "Rows", "ROAS"]
            st.dataframe(type_summary, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("##### Navigate")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                """
                **☀️ Morning Ritual**
                Daily vital signs & anomaly detection

                **🔬 Deep Analysis**
                4-question structured method
                """
            )
        with c2:
            st.markdown(
                """
                **🔭 Pattern Finder**
                Historical pattern scanning & logging

                **🧭 Forecasting**
                Bottom-up forecast with stress tests
                """
            )
        with c3:
            st.markdown(
                """
                **📖 Strategy Playbook**
                Scenario-based strategy reference

                **📡 Export Center**
                Excel, PowerPoint, Power BI
                """
            )


if __name__ == "__main__":
    main()
