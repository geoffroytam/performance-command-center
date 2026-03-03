"""Anomaly flagging and auto-diagnosis logic."""

import numpy as np
import pandas as pd
from utils.constants import load_settings


def check_anomaly(current_value: float, baseline_value: float, threshold_pct: float = None) -> bool:
    """Check if a value deviates from baseline beyond threshold."""
    if threshold_pct is None:
        settings = load_settings()
        threshold_pct = settings.get("anomaly_threshold_pct", 15)
    if pd.isna(current_value) or pd.isna(baseline_value) or baseline_value == 0:
        return False
    pct_change = abs((current_value - baseline_value) / baseline_value) * 100
    return pct_change > threshold_pct


def diagnose(row: dict, baseline: dict) -> tuple[str, str]:
    """
    Takes a platform-campaign_type row and its baseline values.
    Returns (diagnosis_title, suggested_action).
    """
    def safe_delta(key):
        curr = row.get(key, np.nan)
        base = baseline.get(key, np.nan)
        if pd.isna(curr) or pd.isna(base) or base == 0:
            return np.nan
        return (curr - base) / base

    cpm_delta = safe_delta("cpm")
    ctr_delta = safe_delta("ctr")
    cvr_delta = safe_delta("cvr")
    aov_delta = safe_delta("aov")
    roas_delta = safe_delta("roas")
    orders_delta = safe_delta("conversions")

    # Handle case where deltas can't be computed
    if pd.isna(roas_delta):
        return ("Insufficient data", "Not enough data to diagnose. Check baseline period coverage.")

    if roas_delta < -0.15 and not pd.isna(cpm_delta) and cpm_delta > 0.10 and not pd.isna(cvr_delta) and abs(cvr_delta) < 0.10:
        return (
            "Auction pressure",
            f"CPM up {cpm_delta:.0%} while CVR stable. Shift budget to lower-CPM ad sets or refresh creatives.",
        )

    if roas_delta < -0.15 and not pd.isna(cpm_delta) and abs(cpm_delta) < 0.10 and not pd.isna(cvr_delta) and cvr_delta < -0.10:
        return (
            "Conversion issue",
            f"CVR down {cvr_delta:.0%} with stable CPM. Check landing page, offer relevance, or audience mismatch.",
        )

    if (
        roas_delta < -0.15
        and not pd.isna(ctr_delta)
        and ctr_delta < -0.10
        and not pd.isna(cpm_delta)
        and abs(cpm_delta) < 0.10
        and not pd.isna(cvr_delta)
        and abs(cvr_delta) < 0.10
    ):
        return (
            "Creative fatigue",
            f"CTR down {ctr_delta:.0%}. Rotate new creatives; check frequency; pause highest-frequency ads.",
        )

    if (
        roas_delta > 0.15
        and not pd.isna(aov_delta)
        and aov_delta > 0.15
        and not pd.isna(orders_delta)
        and orders_delta < 0.05
    ):
        return (
            "False positive — DO NOT SCALE",
            f"ROAS driven by AOV spike (+{aov_delta:.0%}) not order volume. Hold spend flat; wait 48-72h to confirm trend.",
        )

    if roas_delta < -0.15:
        return (
            "Below target",
            f"ROAS down {roas_delta:.0%}. Run sub-KPI waterfall to identify the broken link.",
        )

    if (
        roas_delta > 0.15
        and not pd.isna(orders_delta)
        and orders_delta > 0.10
        and not pd.isna(aov_delta)
        and abs(aov_delta) < 0.15
    ):
        return (
            "True positive — safe to scale",
            "ROAS up with healthy order volume. Scale gradually (+15-20%/day max). Document the winning combination.",
        )

    return ("Within normal range", "No action required. Performance is within baseline tolerance.")


def flag_anomalies_for_row(row: dict, baseline: dict, threshold_pct: float = 15) -> list[dict]:
    """
    Check all KPIs in a row against baseline and return list of anomalies.
    Each anomaly: {'kpi': str, 'current': float, 'baseline': float, 'pct_change': float, 'direction': str}
    """
    anomalies = []
    kpis = ["roas", "cpm", "ctr", "cvr", "aov", "spend", "conversions"]

    for kpi in kpis:
        current = row.get(kpi, np.nan)
        base = baseline.get(kpi, np.nan)
        if pd.isna(current) or pd.isna(base) or base == 0:
            continue
        pct_change = (current - base) / base * 100
        if abs(pct_change) > threshold_pct:
            anomalies.append({
                "kpi": kpi.upper(),
                "current": current,
                "baseline": base,
                "pct_change": pct_change,
                "direction": "up" if pct_change > 0 else "down",
            })

    return anomalies
