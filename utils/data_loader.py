"""CSV upload, validation, normalization, and campaign name parsing."""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.constants import (
    PLATFORM_COLUMN_MAPS,
    TRACKER_COLUMN_MAP,
    TRACKER_SIGNATURE_COLS,
    PLATFORMS,
    PINTEREST_ALWAYS_PROSPECTING,
    UPLOADS_DIR,
    PROCESSED_DIR,
    load_settings,
)


def detect_tracker_format(df: pd.DataFrame) -> bool:
    """Check if a CSV is from the pre-processed Excel tracker."""
    cols = set(c.strip() for c in df.columns)
    return TRACKER_SIGNATURE_COLS.issubset(cols)


def detect_platform(df: pd.DataFrame) -> Optional[str]:
    """Auto-detect which ad platform a CSV came from based on column names."""
    cols = set(c.strip() for c in df.columns)
    for platform, mapping in PLATFORM_COLUMN_MAPS.items():
        expected = {v for v in mapping.values() if v is not None}
        if expected.issubset(cols):
            return platform
    return None


def detect_date_format(date_series: pd.Series) -> str:
    """Detect whether dates are DD/MM/YYYY or MM/DD/YYYY."""
    sample = date_series.dropna().head(20)
    for val in sample:
        s = str(val).strip()
        parts = None
        for sep in ["/", "-", "."]:
            if sep in s:
                parts = s.split(sep)
                break
        if parts and len(parts) == 3:
            try:
                first = int(parts[0])
                if first > 12:
                    return "dayfirst"
            except ValueError:
                continue
    return "dayfirst"  # Default to Brazilian format


def normalize_tracker_csv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize a pre-processed tracker CSV.
    The tracker has Campaign Type already parsed, uses Landing page views as clicks,
    and has BRL-formatted spend.
    """
    mapping = TRACKER_COLUMN_MAP
    normalized = pd.DataFrame()

    # Map core columns
    for internal_col in ["date", "spend", "impressions", "clicks", "conversions", "revenue"]:
        source_col = mapping.get(internal_col)
        if source_col and source_col in df.columns:
            normalized[internal_col] = df[source_col]
        else:
            normalized[internal_col] = np.nan

    # Campaign type comes directly from the CSV (already parsed)
    ctype_col = mapping.get("campaign_type")
    if ctype_col and ctype_col in df.columns:
        normalized["campaign_type"] = df[ctype_col].str.strip()
    else:
        normalized["campaign_type"] = "Unclassified"

    # The tracker is Meta-only for now
    normalized["platform"] = "Meta"

    # These columns don't exist in tracker format — set to reasonable defaults
    normalized["campaign_name"] = normalized["campaign_type"]  # Use type as name placeholder
    normalized["adset_name"] = ""
    normalized["ad_name"] = ""
    normalized["product_tier"] = "Mixed"

    # Parse dates — tracker uses YYYY-MM-DD format so use format= directly
    normalized["date"] = pd.to_datetime(
        normalized["date"], format="mixed", dayfirst=False, errors="coerce"
    )

    # Convert numeric columns — handle BRL formatting and comma decimals
    numeric_cols = ["spend", "impressions", "clicks", "conversions", "revenue"]
    for col in numeric_cols:
        normalized[col] = (
            pd.to_numeric(
                normalized[col]
                .astype(str)
                .str.replace(",", ".")
                .str.replace(r"[^\d.\-]", "", regex=True),
                errors="coerce",
            )
            .fillna(0)
        )

    # Ensure integer types for count columns
    for col in ["impressions", "clicks", "conversions"]:
        normalized[col] = normalized[col].astype(int)

    # Bring in extra tracker columns if available (reach, frequency, bounce rate)
    for extra in ["reach", "frequency", "bounce_rate"]:
        source_col = mapping.get(extra)
        if source_col and source_col in df.columns:
            normalized[extra] = pd.to_numeric(
                df[source_col].astype(str).str.replace(",", ".").str.replace(r"[^\d.\-]", "", regex=True),
                errors="coerce",
            )

    return normalized


def normalize_csv(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Map platform-specific columns to the normalized internal schema."""
    mapping = PLATFORM_COLUMN_MAPS[platform]
    normalized = pd.DataFrame()

    for internal_col, source_col in mapping.items():
        if source_col is not None and source_col in df.columns:
            normalized[internal_col] = df[source_col]
        else:
            normalized[internal_col] = np.nan

    normalized["platform"] = platform

    # Parse dates
    dayfirst = detect_date_format(normalized["date"]) == "dayfirst"
    normalized["date"] = pd.to_datetime(
        normalized["date"], dayfirst=dayfirst, errors="coerce"
    )

    # Convert numeric columns
    numeric_cols = ["spend", "impressions", "clicks", "conversions", "revenue"]
    for col in numeric_cols:
        normalized[col] = (
            pd.to_numeric(
                normalized[col]
                .astype(str)
                .str.replace(",", ".")
                .str.replace(r"[^\d.\-]", "", regex=True),
                errors="coerce",
            )
            .fillna(0)
        )

    # Ensure integer types for count columns
    for col in ["impressions", "clicks", "conversions"]:
        normalized[col] = normalized[col].astype(int)

    return normalized


def parse_campaign_type(campaign_name: str, platform: str, settings: dict) -> str:
    """Determine Prospecting vs Retargeting from campaign name."""
    if platform == "Pinterest" and settings.get("pinterest_always_prospecting", True):
        return "Prospecting"

    name_lower = str(campaign_name).lower()
    for kw in settings.get("prospecting_keywords", []):
        if kw.lower() in name_lower:
            return "Prospecting"
    for kw in settings.get("retargeting_keywords", []):
        if kw.lower() in name_lower:
            return "Retargeting"
    return "Unclassified"


def parse_product_tier(
    campaign_name: str, adset_name: str, settings: dict
) -> str:
    """Determine product tier from campaign/adset name."""
    combined = f"{campaign_name} {adset_name}".lower()
    for kw in settings.get("premium_keywords", []):
        if kw.lower() in combined:
            return "Premium"
    for kw in settings.get("coupon_keywords", []):
        if kw.lower() in combined:
            return "Coupon"
    for kw in settings.get("non_premium_keywords", []):
        if kw.lower() in combined:
            return "Non-Premium"
    return "Mixed"


def calculate_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Add calculated KPI columns, handling division by zero."""
    df = df.copy()
    df["cpm"] = np.where(df["impressions"] > 0, df["spend"] / df["impressions"] * 1000, np.nan)
    df["ctr"] = np.where(df["impressions"] > 0, df["clicks"] / df["impressions"] * 100, np.nan)
    df["cvr"] = np.where(df["clicks"] > 0, df["conversions"] / df["clicks"] * 100, np.nan)
    df["aov"] = np.where(df["conversions"] > 0, df["revenue"] / df["conversions"], np.nan)
    df["roas"] = np.where(df["spend"] > 0, df["revenue"] / df["spend"], np.nan)
    df["cpa"] = np.where(df["conversions"] > 0, df["spend"] / df["conversions"], np.nan)
    return df


def process_uploaded_file(
    uploaded_file, platform_override: Optional[str] = None
) -> tuple[pd.DataFrame, str, list[str]]:
    """
    Process a single uploaded CSV file.

    Returns:
        (normalized_df, detected_platform, warnings)
    """
    warnings = []
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding="utf-8")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding="latin-1")

    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    # ── Check for tracker format first ────────────────────────
    if detect_tracker_format(df):
        warnings.append("Detected pre-processed tracker format (Meta).")
        normalized = normalize_tracker_csv(df)
        normalized = calculate_kpis(normalized)

        # Check for null dates
        null_dates = normalized["date"].isna().sum()
        if null_dates > 0:
            warnings.append(f"{null_dates} rows have unparseable dates and were dropped.")
            normalized = normalized.dropna(subset=["date"])

        return normalized, "Meta (Tracker)", warnings

    # ── Standard platform detection ───────────────────────────
    if platform_override:
        platform = platform_override
    else:
        platform = detect_platform(df)
        if platform is None:
            return pd.DataFrame(), "Unknown", [
                "Could not auto-detect platform. Column names don't match any known platform format. "
                "Please select the platform manually."
            ]

    # Check for required columns
    mapping = PLATFORM_COLUMN_MAPS[platform]
    missing = []
    for internal, source in mapping.items():
        if source is not None and source not in df.columns:
            missing.append(f"{source} (maps to {internal})")
    if missing:
        warnings.append(f"Missing columns for {platform}: {', '.join(missing)}")

    # Normalize
    normalized = normalize_csv(df, platform)

    # Parse campaign type and product tier
    settings = load_settings()
    normalized["campaign_type"] = normalized["campaign_name"].apply(
        lambda x: parse_campaign_type(x, platform, settings)
    )
    normalized["product_tier"] = normalized.apply(
        lambda row: parse_product_tier(
            str(row.get("campaign_name", "")),
            str(row.get("adset_name", "")),
            settings,
        ),
        axis=1,
    )

    # Calculate KPIs
    normalized = calculate_kpis(normalized)

    # Check for unclassified campaigns
    unclassified = normalized[normalized["campaign_type"] == "Unclassified"]
    if len(unclassified) > 0:
        unique_names = unclassified["campaign_name"].unique()[:5]
        warnings.append(
            f"{len(unclassified)} rows have unclassified campaign type. "
            f"Sample names: {', '.join(str(n) for n in unique_names)}. "
            f"Add keywords in Settings to classify them."
        )

    # Check for null dates
    null_dates = normalized["date"].isna().sum()
    if null_dates > 0:
        warnings.append(f"{null_dates} rows have unparseable dates and were dropped.")
        normalized = normalized.dropna(subset=["date"])

    return normalized, platform, warnings


def load_all_data() -> pd.DataFrame:
    """Load and merge all processed data from session state or files."""
    processed_file = PROCESSED_DIR / "merged_data.parquet"
    if processed_file.exists():
        try:
            return pd.read_parquet(processed_file)
        except Exception:
            pass
    return pd.DataFrame()


def save_merged_data(df: pd.DataFrame):
    """Save merged data to processed directory."""
    processed_file = PROCESSED_DIR / "merged_data.parquet"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(processed_file, index=False)


def get_data_summary(df: pd.DataFrame) -> dict:
    """Return a summary of the loaded data."""
    if df.empty:
        return {"empty": True}
    return {
        "empty": False,
        "date_range": (df["date"].min(), df["date"].max()),
        "platforms": sorted(df["platform"].unique().tolist()),
        "campaign_types": sorted(df["campaign_type"].unique().tolist()),
        "total_rows": len(df),
        "total_spend": df["spend"].sum(),
        "total_revenue": df["revenue"].sum(),
    }


def validate_csv_columns(df: pd.DataFrame, platform: str) -> list[str]:
    """Validate that a CSV has the expected columns for a platform."""
    mapping = PLATFORM_COLUMN_MAPS.get(platform, {})
    missing = []
    for internal_col, source_col in mapping.items():
        if source_col is not None and source_col not in df.columns:
            missing.append(source_col)
    return missing
