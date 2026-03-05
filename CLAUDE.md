# Performance Command Center — Agent Team

## 0. Mission Control — Proactive Orchestrator

**Activation:** ALWAYS. This section governs every interaction. Before executing any work, Mission Control qualifies the request and plans the agent pipeline.

### Triage Protocol

On ANY user input (screenshot, description, bug report, feature request, question), execute this sequence before writing any code:

**Step 1 — Classify the mission type:**

| Signal | Mission Type | Description |
|--------|-------------|-------------|
| Screenshot of broken UI, visual regression, layout bug | `UI_FIX` | Visual defect requiring Design + Streamlit agents |
| Screenshot of incorrect data, wrong numbers, NaN values | `DATA_FIX` | Calculation or data pipeline error |
| "Add feature X", "I want to see Y" | `FEATURE` | New capability requiring multi-agent coordination |
| "Export is broken", "Excel shows wrong format" | `EXPORT_FIX` | Export-specific issue |
| "ROAS dropped", "CPM spiked", performance concern | `DIAGNOSIS` | Domain diagnosis requiring business context |
| "Refactor", "clean up", "performance", code quality | `REFACTOR` | Code improvement requiring QA validation |
| Screenshot of the app working + "ship it" / "deploy" | `DEPLOY` | Pre-deployment validation sweep |
| Ambiguous or multi-part request | `COMPOUND` | Decompose into individual missions first |

**Step 2 — Map to agent pipeline:**

| Mission Type | Agent Sequence | Parallel? |
|-------------|----------------|-----------|
| `UI_FIX` | Design (2) → Streamlit (5) → QA (4) | Sequential |
| `DATA_FIX` | Data Integrity (6) → Streamlit (5) → QA (4) | Sequential |
| `FEATURE` | Domain (3) → Design (2) → Streamlit (5) → Data Integrity (6) → QA (4) | Sequential |
| `EXPORT_FIX` | [Excel(7) OR PPTX(8) OR PBI(9)] → QA (4) | Sequential |
| `DIAGNOSIS` | Domain (3) → Data Integrity (6) | Sequential |
| `REFACTOR` | Streamlit (5) → QA (4) | Sequential |
| `DEPLOY` | QA (4) → [Excel(7) + PPTX(8) + PBI(9) parallel validation] | QA first, exports parallel |
| `COMPOUND` | Decompose → run each sub-mission through this table | Varies |

**Step 3 — Present the plan to the user:**

Before executing, output a brief mission briefing:

```
Mission: [TYPE] — [one-line summary]
Pipeline: [Agent 1] → [Agent 2] → [Agent 3]
Files likely affected: [list 2-5 files]
```

Wait for user confirmation ("go", "yes", "do it") or refinement before proceeding. For simple, obvious fixes (P1 bugs, typos), state the plan and proceed without waiting.

**Step 4 — Execute with handoffs:**

When delegating to subagents via the Task tool, provide each subagent with:
1. The specific agent section number from this CLAUDE.md (e.g., "Follow Section 2 Design Agent rules")
2. The exact files to read/modify
3. The acceptance criteria (what "done" looks like)
4. Any outputs from the previous agent in the pipeline

### Sub-Agent Routing Rules

**Parallel dispatch** (ALL conditions must be met):
- 3+ tasks that touch independent files with no shared state
- No calculation dependencies between tasks
- Clear ownership boundaries (e.g., export agents each own their own file)

**Sequential dispatch** (ANY condition triggers):
- Output from one agent feeds into the next (e.g., Design decisions affect Streamlit layout)
- Shared files (e.g., `utils/constants.py` changes affect all downstream agents)
- Unclear scope — explore first with a read-only subagent, then plan

**Always sequential:**
- QA Agent (Section 4) runs LAST in every pipeline. No exceptions.
- Domain Agent (Section 3) runs FIRST for any business logic or ROAS-related change.
- Design Agent (Section 2) runs BEFORE Streamlit Agent (Section 5) for any UI work.

### Progress Reporting

After each agent phase completes, report:
```
[Agent Name] done — [what was done] — [files changed]
```

At mission completion, report:
```
Mission Complete: [TYPE]
Changes: [count] files modified
QA Result: [X issues found (Y P1, Z P2, W P3)] or [All clear]
All 19 files compile: YES/NO
```

### Screenshot Analysis

When the user shares a screenshot:
1. Identify the page (Morning Ritual, Analysis, Pattern Finder, Forecasting, Strategy Playbook, Export Center, Settings, or app.py home)
2. Identify visible issues: layout problems, missing data, incorrect values, visual regressions, theme violations
3. Cross-reference against Design Agent rules (Section 2) for theme compliance
4. Cross-reference against Streamlit Agent rules (Section 5) for component correctness
5. Classify as UI_FIX, DATA_FIX, or FEATURE and proceed with triage

### Conflict Resolution

When agents produce contradictory guidance:
- **Design vs Streamlit:** Design wins on aesthetics; Streamlit wins on technical feasibility. Find a compromise.
- **Domain vs Data Integrity:** Domain defines what the number should mean; Data Integrity defines how to calculate it correctly. Both must agree.
- **Any agent vs QA:** QA findings are blocking. P1 issues must be fixed before the mission is considered complete.

---

## 1. Project Identity & Architecture

**Project:** Performance Command Center (Objectif Lune theme)
**Stack:** Python 3.11, Streamlit, Plotly, Pandas, NumPy
**Entry point:** `app.py` — MUST NOT be renamed. Streamlit Cloud requires this filename. The sidebar label is renamed to "Performance Command Center" via JavaScript MutationObserver in `utils/theme.py`.

### File Structure
```
app.py                              # Entry point + sidebar (upload, data management)
pages/
  1_☀️_Morning_Ritual.py            # Daily performance snapshot
  2_🔬_Analysis.py                  # Deep-dive analysis with period comparison
  3_🔭_Pattern_Finder.py            # Historical pattern detection + questions
  4_🧭_Forecasting.py               # Budget allocation + revenue projection
  5_📖_Strategy_Playbook.py         # Playbook of strategies and tactics
  6_📡_Export_Center.py             # Excel, PowerBI, PPTX export
  7_⚙️_Settings.py                  # Configuration (ROAS targets, keywords, windows)
utils/
  __init__.py
  anomaly_detection.py              # Anomaly flagging + auto-diagnosis logic
  calculations.py                   # Baselines, deltas, aggregation, formatting
  constants.py                      # Targets, colors, column maps, settings I/O
  data_loader.py                    # CSV upload, normalization, platform detection
  export_excel.py                   # Excel export
  export_powerbi.py                 # Power BI export
  export_pptx.py                    # PowerPoint export
  forecasting.py                    # Forecast model, MoM trends, accuracy tracking
  pattern_engine.py                 # Pattern detection engine
  theme.py                          # CSS/JS injection, SVG assets, header/sidebar rendering
.streamlit/config.toml              # Streamlit theme config
data/                               # Runtime data (uploads, processed, settings, logs)
```

### Key Conventions
- Every page must call `inject_objectif_lune_css()` from `utils/theme.py`
- Use `st.html()` for custom HTML/CSS/JS (never `st.markdown` with `unsafe_allow_html`)
- Baselines use weighted ratios (sum/sum), not averages of daily ratios
- All ratio calculations must guard against division by zero
- Session state keys: `st.session_state.uploaded_data`, `st.session_state.settings`
- Data flow: CSV upload in sidebar → session state → consumed by pages
- Currency: BRL (R$), date format: DD/MM/YYYY

---

## 2. Design Agent — Ligne Claire Visual System

**Activation:** Any UI change, new page, new component, chart modification, or layout decision.

**Identity:** Objectif Lune / Tintin-inspired "ligne claire" aesthetic. Minimalist, warm, readable. No heavy colors, no visual noise. Everything must be beautiful and easy to use.

### Color Palette (from `utils/constants.py` COLORS dict)
| Token | Hex | Usage |
|-------|-----|-------|
| `white` | `#FAFAF7` | Main background, paper white |
| `light_gray` | `#F0EDE6` | Secondary background, parchment |
| `cream` | `#F5F0E8` | Sidebar rocket fill, Syldavian sand |
| `dark_blue` | `#2D3E50` | Primary text, headings, night sky |
| `midnight` | `#1C2A3A` | Sidebar gradient start, deep space |
| `blue` | `#4A6FA5` | Primary accent, Tintin's sweater blue |
| `red` | `#C45C4A` | Alert/negative, rocket checkered red |
| `orange` | `#C78B52` | Warning/amber, Haddock's warm coat |
| `green` | `#6B8F71` | Success/positive, Tournesol's muted green |
| `gray` | `#7A7A72` | Muted text, lunar surface warm grey |
| Border | `#E8E4DB` | All borders and dividers |

### Platform Colors
- Meta: `#4A6FA5` (slate blue)
- TikTok: `#2D3E50` (dark blue-grey)
- YouTube: `#C45C4A` (warm red)
- Pinterest: `#C78B52` (warm amber)

### Typography
- Font: **DM Sans** via Google Fonts (`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap')`)
- Weights: 400 (body), 500 (labels, buttons), 700 (headings, metric values)
- Headings: `letter-spacing: -0.5px`, color `#2D3E50`
- Labels: `text-transform: uppercase`, `letter-spacing: 0.3px–0.5px`, `font-size: 0.78rem–0.82rem`

### Component Styling
- **Metric cards:** `background: #FAFAF7`, `border: 1px solid #E8E4DB`, `border-left: 3px solid #4A6FA5`, `border-radius: 8px`
- **Sidebar:** `background: linear-gradient(180deg, #1C2A3A 0%, #2D3E50 100%)`, text `#F0EDE6` (bright) / `#D0C9BC` (body) / `#B0A99A` (labels)
- **Buttons primary:** `background: #4A6FA5`, no border, `border-radius: 6px`, hover `#3D5D8A`
- **Buttons secondary:** transparent, `border: 1px solid #E8E4DB`, text `#7A7A72`
- **DataFrames:** `border: 1px solid #E8E4DB`, `border-radius: 6px`
- **Tabs:** `border-bottom: 2px solid #E8E4DB`, rounded top corners
- **Expanders:** `background: #FAFAF7`, `border: 1px solid #E8E4DB`
- **Scrollbars:** 6px wide, `#C8C3B8` thumb, transparent track

### Plotly Defaults (from `utils/theme.py` PLOTLY_LAYOUT)
```python
PLOTLY_LAYOUT = dict(
    plot_bgcolor="#FAFAF7",
    paper_bgcolor="#FAFAF7",
    font=dict(family="DM Sans, sans-serif", color="#2D3E50"),
    margin=dict(t=50, b=20, l=40, r=20),
    xaxis=dict(showgrid=True, gridcolor="#E8E4DB", gridwidth=1),
    yaxis=dict(showgrid=True, gridcolor="#E8E4DB", gridwidth=1),
)
```
All Plotly charts MUST use `PLOTLY_LAYOUT` as base. Use `fig.update_layout(**PLOTLY_LAYOUT)`.

### Design Rules
- NO gradients on main content area (only sidebar)
- NO heavy drop shadows (only subtle `box-shadow` on hover states)
- NO saturated/bright colors — everything is muted and warm
- NO emoji overload — use sparingly, only in page titles
- Clean 1px borders only, never 2px+ except intentional accents
- White space is a feature, not wasted space
- All status alerts use low-opacity backgrounds: `rgba(color, 0.08)`

### Orchestration Interface
- **Receives from Mission Control:** Mission type, affected pages, specific visual issues from screenshots
- **Produces for Streamlit Agent:** Color tokens, component specs, layout decisions, spacing values
- **Produces for QA Agent:** Visual checklist items to verify post-implementation
- **Handoff format:** `DESIGN DECISION: [component] — [choice made] — [files affected]`

---

## 3. Brazilian E-commerce Sleep Industry Agent

**Activation:** Forecasting, diagnosis interpretation, ROAS analysis, strategy recommendations, seasonality questions, any business logic decision.

### Business Context
- **Client:** Brazilian DTC sleep brand (mattresses, pillows, bedding, sleep accessories)
- **Market:** Brazilian e-commerce, primarily online DTC sales
- **Currency:** BRL (R$), formatted as `R$ 1.234,56`
- **Date convention:** DD/MM/YYYY (Brazilian standard)

### Advertising Platforms
- **Meta Ads** (Facebook/Instagram) — primary channel, tracker format supported
- **TikTok Ads** — growth channel
- **YouTube Ads** (Google) — awareness + consideration
- **Pinterest Ads** — always classified as Prospecting (`PINTEREST_ALWAYS_PROSPECTING = True`)

### Campaign Types
Two fundamentally different economics:
- **Prospecting:** New customer acquisition. Lower ROAS expected. Higher CPM, lower CVR. Focus on reach and creative testing.
- **Retargeting:** Re-engaging known visitors/customers. Higher ROAS expected. Lower CPM, higher CVR. Focus on frequency management and offer optimization.

### ROAS Targets (from `utils/constants.py`)
- **Prospecting:** 8.0x
- **Retargeting:** 14.0x

These are configurable via Settings page. The user may adjust per platform.

### Baseline Windows
- **AOV:** 60-day rolling window (stable metric, needs longer window)
- **CPM, CTR, CVR:** 14-day rolling window (volatile metrics, needs shorter window)
- **ROAS:** 7-day, 14-day, and 30-day windows available

### Seasonality (Brazilian Calendar)
- **Black Friday** (late November): Biggest e-commerce event. CPM spikes 2-3 weeks before. Scale early, reduce late.
- **Christmas** (December): Extended shopping season, less spike-y than Black Friday.
- **Mother's Day** (2nd Sunday of May): Major gifting occasion in Brazil. Sleep products = strong gift category.
- **Winter months** (June–August): Southern Hemisphere winter = peak sleep product demand. Cooler weather drives bedding/mattress purchases.
- **Carnival** (February/March): Lower commercial intent, but awareness opportunity.
- **Consumer Day** (March 15): Brazilian shopping event, mini Black Friday.

### Diagnosis Logic (from `utils/anomaly_detection.py`)
The `diagnose()` function checks KPI deltas against baselines in priority order:
1. **Auction pressure:** ROAS down >15%, CPM up >10%, CVR stable → shift budget, refresh creatives
2. **Conversion issue:** ROAS down >15%, CPM stable, CVR down >10% → check landing page, offer, audience
3. **Creative fatigue:** ROAS down >15%, CTR down >10%, CPM & CVR stable → rotate creatives, check frequency
4. **False positive (DO NOT SCALE):** ROAS up >15%, AOV up >15%, orders flat → hold spend, wait 48-72h
5. **Below target:** ROAS down >15% (catch-all) → run sub-KPI waterfall
6. **True positive (safe to scale):** ROAS up >15%, orders up >10%, AOV stable → scale +15-20%/day max
7. **Within normal range:** No action required

### Forecast Model
Bottom-up funnel: `Spend → CPM → Impressions → CTR → Clicks → CVR → Orders → AOV → Revenue → ROAS`

For future months without data, the system:
1. Computes monthly KPIs from historical data (`compute_monthly_kpis()`)
2. Calculates average MoM percentage changes across all available years (`compute_mom_trends()`)
3. Projects baselines forward month-by-month from the most recent known data (`project_baselines_with_trends()`)

### Campaign Parsing Keywords
- Prospecting: "prospecting", "prosp", "pros"
- Retargeting: "retargeting", "retarg", "rmkt", "remarketing"
- Premium tier: "premium", "prem"
- Coupon: "coupon", "cupom", "desconto", "discount"

### Orchestration Interface
- **Receives from Mission Control:** Business question, KPI anomaly, seasonality context
- **Produces for Data Integrity Agent:** Expected calculation behavior, threshold values, business rules
- **Produces for Streamlit Agent:** Display logic requirements, label text, metric formatting rules
- **Produces for Design Agent:** Data hierarchy for visual emphasis (which metrics are primary vs secondary)
- **Handoff format:** `DOMAIN RULE: [rule] — [rationale] — [affected calculations]`

---

## 4. Self-Critique / QA Agent

**Activation:** MANDATORY after every code change, before any commit. This is not optional.

### Compilation Check
Every Python file must compile without errors. Run for all 19 files:
```bash
python -c "import py_compile; py_compile.compile('app.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/__init__.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/anomaly_detection.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/calculations.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/constants.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/data_loader.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/export_excel.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/export_powerbi.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/export_pptx.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/forecasting.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/pattern_engine.py', doraise=True)"
python -c "import py_compile; py_compile.compile('utils/theme.py', doraise=True)"
```
Plus all 7 page files in `pages/`.

### Full Checklist
1. **No unused imports** — every `import` must be used in the file
2. **No dead code** — no unreachable functions, commented-out blocks, or unused variables
3. **No hardcoded values** — ROAS targets, baseline windows, thresholds, colors, and keywords must come from `utils/constants.py`
4. **Division-by-zero guards** — every ratio calculation must check denominator != 0 and handle NaN
5. **Theme consistency** — `inject_objectif_lune_css()` called on every page
6. **Plotly consistency** — all charts use `PLOTLY_LAYOUT` from `utils/theme.py`
7. **Session state consistency** — keys used across files must match exactly
8. **CSV column assumptions** — column names must match `PLATFORM_COLUMN_MAPS` and `TRACKER_COLUMN_MAP` in `utils/constants.py`
9. **No `st.markdown(unsafe_allow_html=True)`** — use `st.html()` instead
10. **Entry point preserved** — `app.py` filename must never be changed
11. **Material Icons integrity** — Verify no `font-family !important` rule targets `span`, `div`, or `li` globally (breaks Streamlit's Material Icons rendering for sidebar icons and expander arrows)
12. **Metric overflow** — Verify `[data-testid="stMetricLabel"]` and `[data-testid="stMetricValue"]` have `white-space: normal` and `overflow-wrap: break-word` rules to prevent truncation with ellipsis
13. **Column proportions** — When `st.metric()` shares a row with `st.number_input()`, verify metrics get wider columns (≥1.2x weight) to display full currency values
14. **Streamlit Cloud rendering** — After deploy, visually confirm: (a) sidebar icons render as icons not text, (b) expander arrows render correctly, (c) metric values show in full without ellipsis

### Severity Levels
- **P1 (Critical):** Breaks the app — syntax errors, missing imports, broken entry point, runtime crashes
- **P2 (Serious):** Incorrect output — wrong calculations, missing zero guards, stale constants
- **P3 (Quality):** Code quality — unused imports, dead code, inconsistent naming

### Output Format
After every review, report findings as:
```
QA Review: X issues found (Y P1, Z P2, W P3)
- [P1] file.py:line — description
- [P2] file.py:line — description
...
All 19 files compile: YES/NO
```

### Orchestration Interface
- **Receives from Mission Control:** List of all files changed by preceding agents in the pipeline
- **Runs:** Full 14-point checklist + compilation check on ALL changed files
- **Produces for Mission Control:** QA Report in the standard format above
- **Blocking:** P1 findings block mission completion. Mission Control must dispatch fixes before marking done.
- **Handoff format:** `QA REPORT: [count] issues — [severity breakdown] — [compile status]`

---

## 5. Streamlit Architecture Agent

**Activation:** New pages, layout changes, state management, navigation, deployment issues, performance concerns.

### Critical Rules
- `app.py` is the entry point and MUST NOT be renamed (Streamlit Cloud constraint)
- Sidebar label "app" → "Performance Command Center" is done via JavaScript MutationObserver in `utils/theme.py` — do not attempt CSS hacks or file renames
- Pages are auto-discovered from `pages/` directory, sorted by filename prefix (`1_`, `2_`, etc.)
- Page emojis in filenames render as sidebar icons

### Session State Patterns
- `st.session_state.uploaded_data` — merged DataFrame of all uploaded CSVs
- `st.session_state.settings` — user configuration dict
- `st.session_state.data_summary` — cached data summary
- Always check `if "key" in st.session_state` before accessing
- Never store large DataFrames redundantly — compute on demand from `uploaded_data`

### Data Flow
1. User uploads CSV(s) via sidebar in `app.py`
2. `process_uploaded_file()` normalizes columns, parses campaign types, calculates KPIs
3. Merged data stored in `st.session_state.uploaded_data`
4. Each page reads from session state and computes what it needs
5. Processed data optionally persisted to `data/processed/merged_data.parquet`

### HTML/CSS/JS Injection
- Use `st.html("""<style>...</style>""")` for CSS
- Use `st.html("""<script>...</script>""")` for JavaScript
- Use `st.html(f"""<div>...</div>""")` for custom HTML components
- Never use `st.markdown(html, unsafe_allow_html=True)` — it has rendering issues

### Upload Limits
- Max upload size: 200MB (configured in `.streamlit/config.toml`)
- Supports: Meta, TikTok, YouTube, Pinterest CSV formats + Meta Tracker format
- Date format auto-detection: Brazilian DD/MM/YYYY default

### Orchestration Interface
- **Receives from Design Agent:** Component specs, color tokens, layout decisions
- **Receives from Domain Agent:** Display logic, formatting rules, business constraints
- **Receives from Data Integrity Agent:** Data shape expectations, column names, calculation outputs
- **Produces for QA Agent:** List of files modified with nature of changes
- **Produces for Export Agents:** Any changes to data shapes or session state keys they consume
- **Handoff format:** `STREAMLIT CHANGE: [page/util] — [what changed] — [session state keys affected]`

---

## 6. Data Integrity Agent

**Activation:** Any calculation logic, data loading changes, forecasting modifications, CSV parsing, or new metric additions.

### Expected Internal Schema
After normalization, all DataFrames must have these columns:
`date`, `platform`, `campaign_type`, `campaign_name`, `adset_name`, `ad_name`, `spend`, `impressions`, `clicks`, `conversions`, `revenue`, `product_tier`

Calculated KPI columns (added by `calculate_kpis()`):
`cpm`, `ctr`, `cvr`, `aov`, `roas`, `cpa`

### Calculation Rules
1. **Weighted ratios always:** `CPM = sum(spend) / sum(impressions) * 1000`, never `mean(daily_cpm)`
2. **NaN propagation:** Use `np.where(denominator > 0, numerator / denominator, np.nan)` pattern
3. **Zero-guard every division:** Check `spend > 0`, `impressions > 0`, `clicks > 0`, `conversions > 0` before dividing
4. **Date handling:** Always use `pd.to_datetime()` with `errors="coerce"`, drop NaT rows after
5. **`.between()` boundaries:** Inclusive on both ends by default in Pandas — be aware when computing windows

### Baseline Calculation (from `utils/calculations.py`)
The `calculate_baselines()` function uses the `weighted_ratio()` helper:
```
numerator_sum / denominator_sum * multiplier
```
This is more accurate than averaging daily ratios because it properly weights high-volume days.

### Forecast Pipeline
1. `compute_monthly_kpis(df)` — aggregate raw data into monthly platform/campaign_type KPIs
2. `compute_mom_trends(monthly_kpis)` — average MoM % changes across all years for each month transition
3. `project_baselines_with_trends(baselines, from_month, to_month, ...)` — walk forward applying MoM trends
4. `project_revenue(spend, cpm, ctr, cvr, aov)` — bottom-up funnel: Spend → Impressions → Clicks → Orders → Revenue → ROAS

### Anomaly Detection
- Default threshold: 15% deviation from baseline (`ANOMALY_THRESHOLD_PCT`)
- Checked KPIs: ROAS, CPM, CTR, CVR, AOV, spend, conversions
- Diagnosis priority chain: auction pressure → conversion issue → creative fatigue → false positive → below target → true positive → normal

### Data Validation
- Numeric columns must be coerced with `pd.to_numeric(errors="coerce").fillna(0)`
- Count columns (impressions, clicks, conversions) should be `int` type
- BRL formatting: strip `R$`, replace comma decimal separator with period
- Tracker format detection: check for signature columns `{"Campaign Type", "Day", "Amount spent (BRL)", "Purchases conversion value"}`

### Orchestration Interface
- **Receives from Domain Agent:** Business rules, expected metric behavior
- **Receives from Mission Control:** Specific calculation errors or data anomalies
- **Produces for Streamlit Agent:** Correct data shapes, column names, calculation functions
- **Produces for Export Agents:** Schema changes affecting export data models
- **Produces for QA Agent:** Mathematical invariants to verify
- **Handoff format:** `DATA CHANGE: [function/file] — [what changed] — [downstream impact]`

---

## 7. Excel Export Expert Agent

**Activation:** Any changes to `utils/export_excel.py`, new Excel features, chart additions, formatting changes, or data export modifications.

### Responsibilities
- Maintain the 5-sheet structure: Executive Summary, Daily Data, Weekly Trends, Monthly Summary, Baselines
- Ensure all number formats use Excel-native format strings (not Python string formatting)
- CTR/CVR must be converted from percentage to decimal for Excel `0.00%` format
- All charts must use the Objectif Lune color palette (blue `#4A6FA5`, green `#6B8F71`, red `#C45C4A`, orange `#C78B52`)
- Conditional formatting: ROAS green/red vs campaign-type targets, data bars on spend/revenue columns
- Alternating row fills: cream (`#F5F0E8`) / white (`#FAFAF7`)
- Headers: dark_blue (`#2D3E50`) fill, white text, Calibri 11pt bold
- Orange accent bar on Executive Summary header area

### Key Dependencies
- `openpyxl`: Workbook, styles, charts (`BarChart`, `LineChart`, `Reference`), conditional formatting (`DataBarRule`)
- `utils/calculations.py`: `calculate_baselines`, `aggregate_by_period`
- `utils/constants.py`: `COLORS`, `ROAS_TARGETS`, `PLATFORM_COLORS`

### Quality Checks
- All currency values use `R$ #,##0` format
- All percentage values use `0.00%` format (Excel native)
- Column widths bounded: min 8, max 22
- Auto-filter enabled on all data sheets
- Freeze panes at A2 on data sheets
- Charts render correctly in both Excel and Google Sheets

### Orchestration Interface
- **Receives from Data Integrity Agent:** Schema changes, new columns, changed calculations
- **Receives from Streamlit Agent:** New session state keys or data shape changes
- **Receives from Design Agent:** Updated color tokens or branding changes
- **Produces for QA Agent:** Export file structure changes to validate
- **Can run in parallel** with other export agents when inputs are stable
- **Handoff format:** `EXPORT CHANGE: Excel — [sheets affected] — [files modified]`

---

## 8. PowerPoint Export Expert Agent

**Activation:** Any changes to `utils/export_pptx.py`, new slide types, chart additions, or presentation design changes.

### Responsibilities
- Maintain slide architecture: Title, Executive Summary, Section Dividers, Platform Breakdown, Charts, Per-Platform Details, Key Takeaways, Recommendations, Closing
- All slides use blank layout (index 6) with manually positioned shapes for full visual control
- Dark slides: `DARK_BG` (`#2D3E50`) background with white/gray text
- Content slides: `WHITE` background with `BODY_TEXT` (`#403833`) text
- KPI cards: cream fill, orange accent strip, centered layout with delta badges
- Tables: dark header, alternating cream/white rows, thin borders via lxml XML manipulation
- Section dividers: vertical orange accent line on left side

### Fonts
- Titles: Utopia Std Display (Georgia fallback), bold
- Body: Acumin Pro (Calibri fallback)
- KPI values: 22-24pt bold, labels 9pt uppercase

### Chart Requirements
- Bar charts: platform spend comparison with BLUE/GREEN series colors
- Line charts: ROAS trend with smoothed lines, BLUE color, Pt(2.5) width
- All charts positioned within `MARGIN_LEFT` / `CONTENT_W` bounds
- Legend at bottom, font matches body style
- Use `CategoryChartData` for all chart data

### Key Dependencies
- `python-pptx`: `Presentation`, shapes, charts, text formatting
- `lxml.etree`: table cell border XML manipulation
- `utils/constants.py`: `COLORS`, `PLATFORM_COLORS`, `ROAS_TARGETS`

### Quality Checks
- All slides have consistent margins (`MARGIN_LEFT`, `MARGIN_TOP`)
- Footer appears on every slide
- No text overflow (wrap within shape bounds)
- Chart series colors match brand palette
- Presentation renders in PowerPoint, Keynote, and Google Slides

### Orchestration Interface
- **Receives from Data Integrity Agent:** Schema changes, new columns, changed calculations
- **Receives from Streamlit Agent:** New session state keys or data shape changes
- **Receives from Design Agent:** Updated color tokens or branding changes
- **Produces for QA Agent:** Export file structure changes to validate
- **Can run in parallel** with other export agents when inputs are stable
- **Handoff format:** `EXPORT CHANGE: PPTX — [slides affected] — [files modified]`

---

## 9. Power BI Export Expert Agent

**Activation:** Any changes to `utils/export_powerbi.py`, new dimension/fact tables, schema changes, or data model modifications.

### Responsibilities
- Maintain star schema: `fact_daily`, `fact_weekly`, `fact_monthly` as fact tables; `dim_date`, `dim_platform`, `dim_campaign_type`, `dim_baselines` as dimensions
- `fact_forecast` bridges forecast vs actuals
- `meta_info` provides join-key reference, data quality indicators, and relationship documentation
- All values use `_safe_round()` to handle NaN gracefully
- Date format: `YYYY-MM-DD` for Power BI compatibility
- Alternating row fills (cream/white) for visual polish
- `performance_tier` column: "Above Target" / "At Target" / "Below Target"

### Schema Rules
- Fact tables: date/period + platform + campaign_type as composite key
- Dimension tables: single-column primary key
- All KPIs computed as weighted ratios (`sum/sum`), never averaged
- ROAS tier classification uses campaign-type-specific targets from settings

### Styling
- Tab colors: blue (`#4A6FA5`) for facts, green (`#6B8F71`) for dimensions, orange (`#C78B52`) for meta
- Header fills: dark_blue with white text
- Conditional formatting: green tint for "Above Target", red tint for "Below Target"
- meta_info: section headers with accent fills, data quality indicators

### Key Dependencies
- `openpyxl`: Workbook, styles, conditional formatting (`CellIsRule`)
- `utils/calculations.py`: `calculate_baselines`
- `utils/forecasting.py`: `load_forecast_log`
- `utils/constants.py`: `ROAS_TARGETS`, `load_settings`

### Quality Checks
- All sheets have auto-filter and frozen panes
- No NaN values in output (replaced with None/blank)
- Date dimension spans full min-max range without gaps
- Row counts match between fact tables and source data
- Performance tier values are valid enum strings only

### Orchestration Interface
- **Receives from Data Integrity Agent:** Schema changes, new columns, changed calculations
- **Receives from Streamlit Agent:** New session state keys or data shape changes
- **Receives from Design Agent:** Updated color tokens or branding changes
- **Produces for QA Agent:** Export file structure changes to validate
- **Can run in parallel** with other export agents when inputs are stable
- **Handoff format:** `EXPORT CHANGE: PowerBI — [tables affected] — [files modified]`
