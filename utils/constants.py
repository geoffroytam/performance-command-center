"""Default configuration, targets, colors, and constants."""

import os
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
SETTINGS_FILE = DATA_DIR / "settings.json"
PATTERN_LOG_FILE = DATA_DIR / "pattern_log.json"
ACTION_LOG_FILE = DATA_DIR / "action_log.json"

# Ensure directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ── ROAS Targets ──────────────────────────────────────────────
ROAS_TARGETS = {
    "Prospecting": 8,
    "Retargeting": 14,
}

# ── Baseline Windows (days) ───────────────────────────────────
BASELINE_WINDOWS = {
    "aov": 60,
    "cpm": 14,
    "ctr": 14,
    "cvr": 14,
}

# ── Anomaly Threshold ─────────────────────────────────────────
ANOMALY_THRESHOLD_PCT = 15  # Flag if >15% deviation from baseline

# ── Campaign Name Parsing Keywords ────────────────────────────
PROSPECTING_KEYWORDS = ["prospecting", "prosp", "pros"]
RETARGETING_KEYWORDS = ["retargeting", "retarg", "rmkt", "remarketing"]
PREMIUM_KEYWORDS = ["premium", "prem"]
COUPON_KEYWORDS = ["coupon", "cupom", "desconto", "discount"]
NON_PREMIUM_KEYWORDS = ["non-premium", "standard", "regular"]

# ── Platform Config ───────────────────────────────────────────
PLATFORMS = ["Meta", "TikTok", "YouTube", "Pinterest"]
PINTEREST_ALWAYS_PROSPECTING = True

# ── Column Mappings per Platform ──────────────────────────────
# "Meta Tracker" is for pre-processed Excel tracker CSVs (already has Campaign Type, etc.)
TRACKER_COLUMN_MAP = {
    "date": "Day",
    "campaign_type": "Campaign Type",
    "spend": "Amount spent (BRL)",
    "impressions": "Impressions",
    "clicks": "Landing page views",
    "conversions": "Purchases",
    "revenue": "Purchases conversion value",
    # Pre-calculated KPIs available in the tracker:
    "roas_raw": "ROAS",
    "cpm_raw": "CPM (cost per 1,000 impressions)",
    "ctr_raw": "CTR - LPV",
    "cvr_raw": "CR - LPV",
    "aov_raw": "AOV",
    "reach": "Reach",
    "frequency": "Frequency",
    "bounce_rate": "Bounce Rate",
}

# Columns that identify a CSV as a "Tracker" format
TRACKER_SIGNATURE_COLS = {"Campaign Type", "Day", "Amount spent (BRL)", "Purchases conversion value"}

PLATFORM_COLUMN_MAPS = {
    "Meta": {
        "date": "Date",
        "campaign_name": "Campaign name",
        "adset_name": "Ad set name",
        "ad_name": "Ad name",
        "spend": "Amount spent",
        "impressions": "Impressions",
        "clicks": "Link clicks",
        "conversions": "Purchases",
        "revenue": "Purchase conversion value",
    },
    "TikTok": {
        "date": "Date",
        "campaign_name": "Campaign name",
        "adset_name": "Ad Group name",
        "ad_name": "Ad name",
        "spend": "Cost",
        "impressions": "Impression",
        "clicks": "Click",
        "conversions": "Conversions",
        "revenue": "Conversion value",
    },
    "YouTube": {
        "date": "Day",
        "campaign_name": "Campaign",
        "adset_name": "Ad group",
        "ad_name": None,
        "spend": "Cost",
        "impressions": "Impressions",
        "clicks": "Clicks",
        "conversions": "Conversions",
        "revenue": "Conv. value",
    },
    "Pinterest": {
        "date": "Date",
        "campaign_name": "Campaign name",
        "adset_name": "Ad group name",
        "ad_name": None,
        "spend": "Spend",
        "impressions": "Impressions",
        "clicks": "Clicks",
        "conversions": "Conversions",
        "revenue": "Conversion value",
    },
}

# ── Colors — Objectif Lune / Tintin palette ──────────────────
# Inspired by Hergé's ligne claire: soft, warm, readable, never heavy
COLORS = {
    "green": "#6B8F71",      # Tournesol's muted green
    "red": "#C45C4A",        # Rocket checkered red, softened
    "orange": "#C78B52",     # Haddock's warm coat
    "blue": "#4A6FA5",       # Tintin's sweater blue
    "gray": "#7A7A72",       # Lunar surface warm grey
    "light_gray": "#F0EDE6", # Parchment off-white
    "white": "#FAFAF7",      # Warm paper white
    "dark_blue": "#2D3E50",  # Night sky, muted
    "midnight": "#1C2A3A",   # Deep space
    "cream": "#F5F0E8",      # Syldavian sand
}

PLATFORM_COLORS = {
    "Meta": "#4A6FA5",       # Slate blue (Tintin's sweater)
    "TikTok": "#2D3E50",     # Dark blue-grey (night sky)
    "YouTube": "#C45C4A",    # Warm red (rocket)
    "Pinterest": "#C78B52",  # Warm amber (Haddock)
}

# ── Number Formatting ─────────────────────────────────────────
CURRENCY_PREFIX = "R$"
DATE_FORMAT_DISPLAY = "%d/%m/%Y"
DATE_FORMAT_ISO = "%Y-%m-%d"

# ── CBO Test Defaults ─────────────────────────────────────────
CBO_TEST_DEFAULTS = {
    "active": False,
    "start_date": None,
    "min_roas": 7.0,
    "duration_weeks": 4,
}

# ── Pattern Questions ─────────────────────────────────────────
PATTERN_QUESTIONS = {
    "Before peak seasonality": [
        "What was the CPM trajectory in the 2 weeks leading up to last year's same event?",
        "What was the optimal day to start scaling spend? (First day CVR was above baseline)",
        "Did we run specific promotions during this period? What was the AOV vs order volume mix?",
        "When did auction pressure (CPM inflation) start? How many days before the peak?",
    ],
    "After peak seasonality": [
        "How quickly did performance normalize after the peak? 3 days? 7 days?",
        "Was there a retargeting opportunity with non-converters from peak traffic?",
        "Did any platform recover faster than others?",
        "What was the spend reduction curve? Did we reduce too fast or too slow?",
    ],
    "Normal trading period": [
        "What is the typical WoW ROAS variance on this platform during non-promotional weeks?",
        "Are there day-of-week patterns? (e.g., CVR dips on Mondays, peaks on Thursdays?)",
        "What creative formats performed best during similar non-peak periods last year?",
        "What is the baseline CPM range for this platform in non-peak months?",
    ],
    "Investigating a specific anomaly": [
        "Did the same anomaly happen last year around this time?",
        "Was this driven by one metric or multiple metrics shifting simultaneously?",
        "Did this affect one platform or all platforms? (market-level vs platform-level)",
        "How long did it take to recover last time this happened?",
    ],
}

# ── Default Settings (full) ───────────────────────────────────
DEFAULT_SETTINGS = {
    "roas_target_prospecting": 8,
    "roas_target_retargeting": 14,
    "aov_baseline_days": 60,
    "ctr_baseline_days": 14,
    "cvr_baseline_days": 14,
    "cpm_baseline_days": 14,
    "anomaly_threshold_pct": 15,
    "prospecting_keywords": PROSPECTING_KEYWORDS,
    "retargeting_keywords": RETARGETING_KEYWORDS,
    "premium_keywords": PREMIUM_KEYWORDS,
    "coupon_keywords": COUPON_KEYWORDS,
    "non_premium_keywords": NON_PREMIUM_KEYWORDS,
    "pinterest_always_prospecting": True,
    "cbo_test_active": False,
    "cbo_test_start_date": None,
    "cbo_test_min_roas": 7.0,
    "cbo_test_duration_weeks": 4,
    "currency": "BRL",
    "date_format": "DD/MM/YYYY",
    "language": "en",
}


def load_settings() -> dict:
    """Load settings from JSON file, falling back to defaults."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
            merged = {**DEFAULT_SETTINGS, **saved}
            return merged
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    """Persist settings to JSON file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2, default=str)
