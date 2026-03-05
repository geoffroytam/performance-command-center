Analyze the user's most recent input and classify it using Mission Control (CLAUDE.md Section 0).

## Steps

1. **Identify the input type:** screenshot, text description, bug report, feature request, question, or multi-part
2. **Classify the mission type:**
   - `UI_FIX` — visual defect, layout bug, design regression
   - `DATA_FIX` — wrong numbers, NaN values, calculation error
   - `FEATURE` — new capability or enhancement
   - `EXPORT_FIX` — Excel/PPTX/Power BI export issue
   - `DIAGNOSIS` — ROAS/CPM/performance concern needing business analysis
   - `REFACTOR` — code quality, cleanup, performance improvement
   - `DEPLOY` — pre-deployment validation
   - `COMPOUND` — multiple issues, decompose into sub-missions
3. **Map to agent pipeline** using the triage table in Section 0
4. **Identify files likely affected** (2-5 files)
5. **Assess risk** (Low/Medium/High)

## Output Format

Present this mission briefing and WAIT for user confirmation:

```
Mission: [TYPE] — [one-line summary]
Pipeline: [Agent 1] -> [Agent 2] -> [Agent 3]
Files affected: [list]
Risk: [level] — [reason]
```

Do NOT execute any changes. Only present the plan for approval.
