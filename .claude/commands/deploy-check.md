Run a pre-deployment validation sweep to determine GO / NO-GO status.

## Steps

### 1. Full QA Sweep
Run the complete qa-sweep (compilation + 14-point checklist).

### 2. Deployment-Specific Checks
- Verify `app.py` entry point exists and is intact
- Verify `.streamlit/config.toml` exists and is valid
- Verify all session state keys are consistent across files
- Verify all imports resolve (no missing modules)
- Check that no `data/` runtime files are accidentally staged
- Verify `requirements.txt` or equivalent lists all dependencies

### 3. Recent Changes Audit
- List files modified in the last commit (`git diff HEAD~1 --stat`)
- Flag any risky changes (constants, entry point, theme, data loader)

### 4. Export Validation
- Verify `utils/export_excel.py`, `utils/export_pptx.py`, `utils/export_powerbi.py` all compile
- Check for any new dependencies not in requirements

### 5. Decision

```
DEPLOY CHECK REPORT
===================
QA Status: [CLEAN / X issues]
Entry Point: [OK / MISSING]
Config: [OK / INVALID]
Dependencies: [OK / MISSING: list]
Recent Changes: [X files in last commit]
Risk Assessment: [Low / Medium / High]

DECISION: GO / NO-GO
Reason: [explanation if NO-GO]
```
