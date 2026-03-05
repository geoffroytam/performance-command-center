"""Data-driven recommendation engine — analyzes patterns and generates actionable insights."""

import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Optional

from utils.constants import ROAS_TARGETS, KPI_DRIVER_TYPE


# ── Brazilian E-commerce Industry Benchmarks ─────────────────────
# Based on typical Brazilian D2C / mattress / home goods verticals.
# These are reference ranges, not hard rules.
INDUSTRY_BENCHMARKS = {
    "Meta": {
        "Prospecting": {"cpm": (15, 35), "ctr": (0.8, 2.5), "cvr": (0.3, 1.5), "roas": (5, 12)},
        "Retargeting": {"cpm": (10, 25), "ctr": (1.5, 4.0), "cvr": (1.0, 5.0), "roas": (10, 25)},
    },
    "TikTok": {
        "Prospecting": {"cpm": (8, 25), "ctr": (0.5, 2.0), "cvr": (0.2, 1.2), "roas": (3, 10)},
        "Retargeting": {"cpm": (6, 20), "ctr": (1.0, 3.0), "cvr": (0.5, 3.0), "roas": (6, 18)},
    },
    "YouTube": {
        "Prospecting": {"cpm": (20, 50), "ctr": (0.3, 1.5), "cvr": (0.2, 1.0), "roas": (3, 8)},
        "Retargeting": {"cpm": (15, 35), "ctr": (0.5, 2.0), "cvr": (0.5, 2.5), "roas": (5, 15)},
    },
    "Pinterest": {
        "Prospecting": {"cpm": (5, 20), "ctr": (0.3, 1.5), "cvr": (0.1, 0.8), "roas": (2, 7)},
        "Retargeting": {"cpm": (5, 15), "ctr": (0.5, 2.0), "cvr": (0.3, 1.5), "roas": (4, 10)},
    },
}


def _safe_pct(a: float, b: float) -> float:
    """Percentage change from b to a, or NaN."""
    if pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return (a - b) / b * 100


def _kpi_trend_direction(values: list) -> str:
    """Determine trend direction from a list of values."""
    if len(values) < 3:
        return "insufficient_data"
    recent = np.mean(values[-2:])
    earlier = np.mean(values[:2])
    if pd.isna(recent) or pd.isna(earlier) or earlier == 0:
        return "unknown"
    pct = (recent - earlier) / earlier * 100
    if pct > 10:
        return "rising"
    elif pct < -10:
        return "falling"
    return "stable"


def analyze_platform_health(
    df: pd.DataFrame,
    platform: str,
    campaign_type: str,
    lookback_days: int = 30,
) -> dict:
    """Analyze recent health of a platform/campaign_type combo.

    Returns dict with:
        kpi_values: dict of current KPIs
        kpi_trends: dict of trend directions
        vs_benchmark: dict of benchmark comparisons
        health_score: float (0-100)
        issues: list of identified issues
    """
    max_date = df["date"].max()
    start_date = max_date - timedelta(days=lookback_days)

    slice_df = df[
        (df["platform"] == platform)
        & (df["campaign_type"] == campaign_type)
        & (df["date"] >= start_date)
    ]

    if slice_df.empty:
        return {"health_score": 0, "issues": ["No data"], "kpi_values": {}, "kpi_trends": {}, "vs_benchmark": {}}

    # Current KPIs (aggregate over lookback)
    total_spend = slice_df["spend"].sum()
    total_impressions = slice_df["impressions"].sum()
    total_clicks = slice_df["clicks"].sum()
    total_conversions = slice_df["conversions"].sum()
    total_revenue = slice_df["revenue"].sum()

    kpis = {
        "spend": total_spend,
        "cpm": total_spend / total_impressions * 1000 if total_impressions > 0 else np.nan,
        "ctr": total_clicks / total_impressions * 100 if total_impressions > 0 else np.nan,
        "cvr": total_conversions / total_clicks * 100 if total_clicks > 0 else np.nan,
        "aov": total_revenue / total_conversions if total_conversions > 0 else np.nan,
        "roas": total_revenue / total_spend if total_spend > 0 else np.nan,
        "orders": total_conversions,
    }

    # Weekly trends (last 4 weeks)
    trends = {}
    for kpi_name in ["cpm", "ctr", "cvr", "aov", "roas"]:
        weekly_vals = []
        for w in range(4):
            w_end = max_date - timedelta(days=w * 7)
            w_start = w_end - timedelta(days=6)
            w_slice = slice_df[slice_df["date"].between(w_start, w_end)]
            if w_slice.empty:
                weekly_vals.append(np.nan)
                continue
            w_spend = w_slice["spend"].sum()
            w_imp = w_slice["impressions"].sum()
            w_clicks = w_slice["clicks"].sum()
            w_conv = w_slice["conversions"].sum()
            w_rev = w_slice["revenue"].sum()

            if kpi_name == "cpm":
                weekly_vals.append(w_spend / w_imp * 1000 if w_imp > 0 else np.nan)
            elif kpi_name == "ctr":
                weekly_vals.append(w_clicks / w_imp * 100 if w_imp > 0 else np.nan)
            elif kpi_name == "cvr":
                weekly_vals.append(w_conv / w_clicks * 100 if w_clicks > 0 else np.nan)
            elif kpi_name == "aov":
                weekly_vals.append(w_rev / w_conv if w_conv > 0 else np.nan)
            elif kpi_name == "roas":
                weekly_vals.append(w_rev / w_spend if w_spend > 0 else np.nan)

        weekly_vals.reverse()  # oldest first
        trends[kpi_name] = _kpi_trend_direction(weekly_vals)

    # Benchmark comparison
    benchmarks = INDUSTRY_BENCHMARKS.get(platform, {}).get(campaign_type, {})
    vs_bench = {}
    for kpi_name in ["cpm", "ctr", "cvr", "roas"]:
        val = kpis.get(kpi_name, np.nan)
        if pd.isna(val) or kpi_name not in benchmarks:
            vs_bench[kpi_name] = "no_data"
            continue
        low, high = benchmarks[kpi_name]
        if kpi_name == "cpm":
            # Lower is better for CPM
            if val < low:
                vs_bench[kpi_name] = "excellent"
            elif val <= high:
                vs_bench[kpi_name] = "normal"
            else:
                vs_bench[kpi_name] = "above_range"
        else:
            # Higher is better
            if val > high:
                vs_bench[kpi_name] = "excellent"
            elif val >= low:
                vs_bench[kpi_name] = "normal"
            else:
                vs_bench[kpi_name] = "below_range"

    # Health score (0-100)
    score = 50  # neutral start
    target_roas = ROAS_TARGETS.get(campaign_type, 8)
    if not pd.isna(kpis["roas"]):
        if kpis["roas"] >= target_roas * 1.2:
            score += 25
        elif kpis["roas"] >= target_roas:
            score += 15
        elif kpis["roas"] >= target_roas * 0.8:
            score += 0
        else:
            score -= 20

    for kpi_name in ["cpm", "ctr", "cvr"]:
        bench_status = vs_bench.get(kpi_name, "no_data")
        if bench_status == "excellent":
            score += 5
        elif bench_status == "below_range" or bench_status == "above_range":
            score -= 5

        trend = trends.get(kpi_name, "unknown")
        if kpi_name == "cpm":
            if trend == "rising":
                score -= 5
            elif trend == "falling":
                score += 5
        else:
            if trend == "rising":
                score += 5
            elif trend == "falling":
                score -= 5

    score = max(0, min(100, score))

    # Identify issues
    issues = []
    if not pd.isna(kpis["roas"]) and kpis["roas"] < target_roas * 0.8:
        issues.append(f"ROAS ({kpis['roas']:.1f}) significantly below target ({target_roas})")
    if trends.get("cpm") == "rising":
        issues.append("CPM trending upward — growing auction pressure")
    if trends.get("ctr") == "falling":
        issues.append("CTR declining — possible creative fatigue")
    if trends.get("cvr") == "falling":
        issues.append("CVR declining — check landing page or audience quality")
    if vs_bench.get("cpm") == "above_range":
        issues.append(f"CPM (R$ {kpis['cpm']:.2f}) above industry range")
    if vs_bench.get("cvr") == "below_range":
        issues.append(f"CVR ({kpis['cvr']:.2f}%) below industry range")

    return {
        "health_score": score,
        "kpi_values": kpis,
        "kpi_trends": trends,
        "vs_benchmark": vs_bench,
        "issues": issues,
    }


def generate_allocation_recommendations(
    df: pd.DataFrame,
    current_allocations: dict,
    forecast_spend: float,
    lookback_days: int = 30,
) -> list:
    """Generate budget allocation recommendations based on platform performance.

    Parameters
    ----------
    df : pd.DataFrame
        Historical data
    current_allocations : dict
        Platform -> pct currently allocated
    forecast_spend : float
        Total planned spend
    lookback_days : int
        Period to analyze

    Returns
    -------
    list of recommendation dicts with keys: priority, category, title, detail, action
    """
    recs = []
    platform_health = {}

    for platform in df["platform"].unique():
        for ctype in df[df["platform"] == platform]["campaign_type"].unique():
            health = analyze_platform_health(df, platform, ctype, lookback_days)
            platform_health[f"{platform}_{ctype}"] = health

    # 1. Find the strongest and weakest performers
    scored = [(k, v["health_score"], v) for k, v in platform_health.items() if v["health_score"] > 0]
    if len(scored) >= 2:
        scored.sort(key=lambda x: x[1], reverse=True)
        best_key, best_score, best_data = scored[0]
        worst_key, worst_score, worst_data = scored[-1]

        best_roas = best_data["kpi_values"].get("roas", 0)
        worst_roas = worst_data["kpi_values"].get("roas", 0)

        if best_score - worst_score > 20 and best_roas > 0 and worst_roas > 0:
            best_label = best_key.replace("_", " ")
            worst_label = worst_key.replace("_", " ")
            recs.append({
                "priority": "P1",
                "category": "Allocation",
                "title": f"Shift budget from {worst_label} to {best_label}",
                "detail": (
                    f"{best_label} (ROAS {best_roas:.1f}, score {best_score}/100) is significantly "
                    f"outperforming {worst_label} (ROAS {worst_roas:.1f}, score {worst_score}/100). "
                    f"Consider reallocating 5-10% of spend."
                ),
                "action": f"Reduce {worst_label} allocation by 5-10% and increase {best_label}.",
            })

    # 2. Platform-specific issues
    for key, health in platform_health.items():
        platform_label = key.replace("_", " ")
        for issue in health["issues"]:
            if "CPM trending upward" in issue:
                recs.append({
                    "priority": "P2",
                    "category": "Cost Management",
                    "title": f"{platform_label}: Rising CPM pressure",
                    "detail": (
                        f"CPM on {platform_label} has been increasing over the past weeks. "
                        f"This reduces impression volume per real spent."
                    ),
                    "action": "Refresh creatives, test broader audiences, or shift budget to lower-CPM placements.",
                })
            if "CTR declining" in issue:
                recs.append({
                    "priority": "P2",
                    "category": "Creative",
                    "title": f"{platform_label}: Creative fatigue detected",
                    "detail": (
                        f"CTR on {platform_label} has been declining, suggesting ad creative fatigue. "
                        f"Users are seeing the same ads too often."
                    ),
                    "action": "Rotate 3-5 new creative variants. Test different formats (video, carousel, UGC).",
                })
            if "CVR declining" in issue:
                recs.append({
                    "priority": "P1",
                    "category": "Conversion",
                    "title": f"{platform_label}: Conversion rate declining",
                    "detail": (
                        f"CVR on {platform_label} is trending downward. This directly impacts order volume "
                        f"and ROAS."
                    ),
                    "action": "Audit landing page (load time, mobile UX, offer clarity). Review audience targeting quality.",
                })

    # 3. Seasonal pattern recommendations
    max_date = df["date"].max()
    target_month = max_date.month
    _seasonal_months = {
        3: ("March peak (back-to-school)", "Scale prospecting 2-3 weeks before. Budget 40-60% above normal."),
        11: ("November peak (Black Friday)", "Build retargeting pools 2 weeks before. Prepare promotional creatives."),
        12: ("December peak (holiday gifting)", "Focus on gift messaging. Extend retargeting windows."),
        1: ("January recovery", "Reduce spend to 70-80% of normal. Audiences are saturated post-holiday."),
    }
    if target_month in _seasonal_months:
        label, action = _seasonal_months[target_month]
        recs.append({
            "priority": "P2",
            "category": "Seasonality",
            "title": f"Seasonal awareness: {label}",
            "detail": f"Historical patterns show this month has specific characteristics. Plan accordingly.",
            "action": action,
        })

    # 4. Overall efficiency recommendations
    total_health = np.mean([v["health_score"] for v in platform_health.values() if v["health_score"] > 0])
    if total_health < 40:
        recs.append({
            "priority": "P1",
            "category": "Strategy",
            "title": "Overall performance below healthy levels",
            "detail": (
                f"Average health score across all platforms is {total_health:.0f}/100. "
                f"Multiple segments are underperforming."
            ),
            "action": "Hold current spend levels. Isolate the weakest segments and fix fundamentals before scaling.",
        })
    elif total_health > 75:
        recs.append({
            "priority": "P3",
            "category": "Growth",
            "title": "Strong performance — scaling opportunity",
            "detail": (
                f"Average health score is {total_health:.0f}/100. Most segments are performing well."
            ),
            "action": "Consider gradual budget increase (+15-20% over 2 weeks) on top-performing segments.",
        })

    # Sort by priority
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 9))

    return recs


def generate_forecast_recommendations(
    projection_rows: list,
    risk_alerts: list,
    trend_details: dict,
    seasonal_details: dict,
    steps_forward: int,
    target_month_name: str,
) -> list:
    """Generate recommendations specific to the forecast output.

    Parameters
    ----------
    projection_rows : list
        The projection rows from Step 4
    risk_alerts : list
        Risk alerts from the stress test
    trend_details : dict
        Method A transparency data
    seasonal_details : dict
        Method B transparency data
    steps_forward : int
        How many months ahead we're forecasting
    target_month_name : str
        Display name for the target month

    Returns
    -------
    list of recommendation dicts
    """
    recs = []

    if not projection_rows:
        return recs

    # 1. Check for segments at risk
    for row in projection_rows:
        roas = row.get("_proj", {}).get("roas", 0)
        target = ROAS_TARGETS.get(row.get("Type", ""), 8)
        if roas < target * 0.8:
            recs.append({
                "priority": "P1",
                "category": "Risk",
                "title": f"{row['Platform']} {row['Type']}: Projected ROAS below threshold",
                "detail": (
                    f"Projected ROAS of {roas:.1f} is well below the target of {target}. "
                    f"This segment may not be profitable in {target_month_name}."
                ),
                "action": "Consider reducing allocation or improving funnel metrics before this month.",
            })

    # 2. Risk alert-based recommendations
    for alert in risk_alerts:
        recs.append({
            "priority": "P1",
            "category": "Stress Test",
            "title": f"{alert['platform']} {alert['type']}: Fails stress test",
            "detail": (
                f"Under adverse conditions (CPM +15%, CVR -10%), ROAS drops to "
                f"{alert['stressed_roas']:.1f} — below the {alert['threshold']:.1f} threshold."
            ),
            "action": "Build contingency plan. Prepare alternative budget allocation if conditions worsen.",
        })

    # 3. Method divergence recommendations
    if trend_details and seasonal_details:
        for key in trend_details:
            if key in seasonal_details:
                a_bl = trend_details[key].get("projected_baselines", {})
                b_bl = seasonal_details[key].get("projected_baselines", {})
                # Check if methods diverge significantly on any KPI
                for kpi in ["cpm", "ctr", "cvr"]:
                    a_val = a_bl.get(kpi, np.nan)
                    b_val = b_bl.get(kpi, np.nan)
                    if pd.notna(a_val) and pd.notna(b_val) and a_val > 0:
                        spread = abs(a_val - b_val) / a_val * 100
                        if spread > 25:
                            label = key.replace("_", " — ", 1)
                            recs.append({
                                "priority": "P2",
                                "category": "Forecast Confidence",
                                "title": f"{label}: High uncertainty on {kpi.upper()}",
                                "detail": (
                                    f"Method A and B disagree by {spread:.0f}% on {kpi.upper()} projection. "
                                    f"This means the forecast has higher uncertainty."
                                ),
                                "action": f"Plan for a wider ROAS range. Monitor {kpi.upper()} closely in the first week.",
                            })
                            break  # One warning per segment is enough

    # 4. Forecast distance recommendations
    if steps_forward >= 3:
        recs.append({
            "priority": "P2",
            "category": "Forecast Distance",
            "title": f"Forecasting {steps_forward} months ahead — higher uncertainty",
            "detail": (
                f"Projections {steps_forward} months ahead have wider confidence bands. "
                f"Market conditions, competition, and seasonality can shift significantly."
            ),
            "action": "Treat these as directional estimates. Re-forecast monthly as new data arrives.",
        })

    # 5. Concentration risk
    spends = [(r["Platform"], r["Type"], r.get("_spend", 0)) for r in projection_rows]
    total = sum(s[2] for s in spends)
    if total > 0:
        for plat, ctype, sp in spends:
            pct = sp / total * 100
            if pct > 60:
                recs.append({
                    "priority": "P2",
                    "category": "Diversification",
                    "title": f"High concentration: {plat} {ctype} = {pct:.0f}% of spend",
                    "detail": (
                        f"Over {pct:.0f}% of your budget is concentrated in one segment. "
                        f"If this segment underperforms, overall results will be heavily impacted."
                    ),
                    "action": "Consider allocating 10-15% to a secondary platform for risk diversification.",
                })

    # Sort by priority
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 9))

    return recs


def generate_playbook_recommendations(
    df: pd.DataFrame,
    lookback_days: int = 30,
) -> list:
    """Generate strategic recommendations for the Strategy Playbook page.

    Analyzes the full dataset and produces high-level strategic recommendations.

    Returns list of recommendation dicts.
    """
    recs = []

    if df.empty:
        return recs

    max_date = df["date"].max()
    platforms = df["platform"].unique()

    # 1. Analyze each platform's health
    all_health = {}
    for platform in platforms:
        for ctype in df[df["platform"] == platform]["campaign_type"].unique():
            health = analyze_platform_health(df, platform, ctype, lookback_days)
            all_health[f"{platform} {ctype}"] = health

    # 2. Find cross-platform patterns
    cpm_trends = {}
    for key, health in all_health.items():
        cpm_trends[key] = health.get("kpi_trends", {}).get("cpm", "unknown")

    rising_cpm_count = sum(1 for v in cpm_trends.values() if v == "rising")
    if rising_cpm_count >= len(cpm_trends) * 0.5 and len(cpm_trends) >= 2:
        recs.append({
            "priority": "P1",
            "category": "Market",
            "title": "Industry-wide CPM inflation detected",
            "detail": (
                f"CPM is rising across {rising_cpm_count} of {len(cpm_trends)} segments. "
                f"This is likely a market-level trend (increased competition, seasonal demand)."
            ),
            "action": (
                "Focus on conversion rate optimization rather than fighting CPM. "
                "Improve landing pages, test new creatives, and optimize for value rather than volume."
            ),
        })

    # 3. Prospecting vs Retargeting balance
    prosp_spend = df[
        (df["campaign_type"] == "Prospecting") & (df["date"] >= max_date - timedelta(days=lookback_days))
    ]["spend"].sum()
    retarg_spend = df[
        (df["campaign_type"] == "Retargeting") & (df["date"] >= max_date - timedelta(days=lookback_days))
    ]["spend"].sum()
    total_spend = prosp_spend + retarg_spend

    if total_spend > 0:
        prosp_pct = prosp_spend / total_spend * 100
        retarg_pct = retarg_spend / total_spend * 100

        if prosp_pct > 80:
            recs.append({
                "priority": "P2",
                "category": "Funnel Balance",
                "title": f"Heavy prospecting tilt ({prosp_pct:.0f}% prospecting)",
                "detail": (
                    f"Only {retarg_pct:.0f}% of spend goes to retargeting. "
                    f"You may be leaving money on the table by not converting warm audiences."
                ),
                "action": "Test increasing retargeting to 25-30% of total spend. Target website visitors (7-14d) and cart abandoners.",
            })
        elif retarg_pct > 50:
            recs.append({
                "priority": "P2",
                "category": "Funnel Balance",
                "title": f"Heavy retargeting tilt ({retarg_pct:.0f}% retargeting)",
                "detail": (
                    f"Over {retarg_pct:.0f}% of spend goes to retargeting. "
                    f"Your prospecting pool may be depleting, limiting future conversion volume."
                ),
                "action": "Increase prospecting to 60-75% of total spend to replenish the top of funnel.",
            })

    # 4. Platform-specific tactical recs
    for key, health in all_health.items():
        kpis = health.get("kpi_values", {})
        benchmarks = health.get("vs_benchmark", {})

        if benchmarks.get("cvr") == "excellent" and benchmarks.get("cpm") == "above_range":
            recs.append({
                "priority": "P2",
                "category": "Efficiency",
                "title": f"{key}: Strong CVR despite high CPM",
                "detail": (
                    f"This segment has excellent conversion rates but pays premium CPM. "
                    f"The high CPM is offset by strong funnel performance."
                ),
                "action": "Maintain current targeting. Test creative refresh to potentially lower CPM without hurting CVR.",
            })

        if benchmarks.get("ctr") == "below_range":
            recs.append({
                "priority": "P2",
                "category": "Creative",
                "title": f"{key}: CTR below industry range",
                "detail": (
                    f"Click-through rate is below typical industry levels. "
                    f"This limits the volume of traffic reaching your site."
                ),
                "action": "Audit ad creatives. Test UGC, video, and carousel formats. Review ad copy and CTAs.",
            })

    # 5. Day-of-week patterns
    recent = df[df["date"] >= max_date - timedelta(days=28)].copy()
    if not recent.empty:
        recent["dow"] = recent["date"].dt.dayofweek
        dow_roas = recent.groupby("dow").apply(
            lambda g: g["revenue"].sum() / g["spend"].sum() if g["spend"].sum() > 0 else np.nan
        )
        if dow_roas.notna().sum() >= 5:
            best_dow = dow_roas.idxmax()
            worst_dow = dow_roas.idxmin()
            dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

            if pd.notna(best_dow) and pd.notna(worst_dow) and best_dow != worst_dow:
                best_val = dow_roas[best_dow]
                worst_val = dow_roas[worst_dow]
                if best_val > 0 and worst_val > 0:
                    spread = (best_val - worst_val) / worst_val * 100
                    if spread > 25:
                        recs.append({
                            "priority": "P3",
                            "category": "Day-of-Week",
                            "title": f"Best day: {dow_names[best_dow]} (ROAS {best_val:.1f}), Worst: {dow_names[worst_dow]} (ROAS {worst_val:.1f})",
                            "detail": (
                                f"There's a {spread:.0f}% ROAS spread between your best and worst days. "
                                f"This day-of-week pattern can inform budget pacing."
                            ),
                            "action": (
                                f"Consider increasing daily budgets on {dow_names[best_dow]}s "
                                f"and reducing on {dow_names[worst_dow]}s."
                            ),
                        })

    # Sort by priority
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 9))

    return recs
