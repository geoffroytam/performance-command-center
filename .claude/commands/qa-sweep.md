Run a full Quality Assurance sweep across the Performance Command Center.

## Steps

### 1. Compilation Check
Run `python3 -m py_compile` on ALL 19 Python files:
- `app.py`
- All 7 files in `pages/`
- All 11 files in `utils/`

Report each as pass/fail.

### 2. Full 14-Point Checklist (from CLAUDE.md Section 4)
Check every file against:
1. No unused imports
2. No dead code
3. No hardcoded values (use constants.py)
4. Division-by-zero guards on every ratio
5. Theme consistency (inject_objectif_lune_css on every page)
6. Plotly consistency (PLOTLY_LAYOUT on every chart)
7. Session state key matching across files
8. CSV column name matching vs PLATFORM_COLUMN_MAPS
9. No unsafe_allow_html (use st.html instead)
10. Entry point app.py preserved
11. Material Icons integrity (no font-family on span/div/li)
12. Metric overflow handling (white-space: normal)
13. Column proportions (metrics >= 1.2x weight)
14. Streamlit Cloud rendering readiness

### 3. Report

```
QA SWEEP REPORT
===============
Compilation: [19/19 pass] or [X failures listed]
Checklist: [X issues found]
- [P1] file.py:line — description
- [P2] file.py:line — description
- [P3] file.py:line — description

Status: CLEAN / [X] ISSUES FOUND
```
