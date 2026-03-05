The user has shared a screenshot of the Performance Command Center app. Analyze it for issues.

## Steps

### 1. Page Identification
Identify which page is shown:
- Morning Ritual (daily snapshot)
- Analysis (deep-dive comparison)
- Pattern Finder (historical patterns)
- Forecasting (budget allocation)
- Strategy Playbook (scenarios)
- Export Center (Excel/PPTX/PBI)
- Settings (configuration)
- Home (app.py upload screen)

### 2. Design Review (Section 2 rules)
Check against the Objectif Lune visual system:
- Color palette compliance (muted tones, no bright/saturated colors)
- Typography (DM Sans, correct weights, uppercase labels)
- Component styling (metric cards, borders, shadows)
- White space and layout proportions
- Material Icons rendering (no raw text like "arrow_right")

### 3. Data Review (Section 6 rules)
Check for data issues:
- Correct currency format (R$ with proper separators)
- Reasonable KPI values (ROAS, CPM, CTR, CVR ranges)
- No NaN, Inf, or missing data visible
- Correct date formatting (DD/MM/YYYY or context-appropriate)

### 4. Component Review (Section 5 rules)
Check for Streamlit component issues:
- Truncated text or values (ellipsis)
- Broken layout or overlapping elements
- Missing or incorrect icons
- Non-functional controls

### 5. Classification & Triage

```
SCREENSHOT REVIEW
=================
Page: [identified page]
Issues Found: [count]
- [severity] [description] — likely cause — suggested fix
- [severity] [description] — likely cause — suggested fix

Recommended Mission: [TYPE]
Pipeline: [Agent 1] -> [Agent 2] -> [Agent 3]
Files affected: [list]
```

Wait for user confirmation before executing any fixes.
