# Performance Command Center — Agent Orchestration Guide

## What This Is

The Performance Command Center uses Claude Code with a team of **10 specialized AI agents**.
A meta-agent called **Mission Control** automatically triages your input, selects the right agents,
sequences them in the correct order, and reports progress — you don't need to specify which agent does what.

## How It Works

1. You share something: a screenshot, a bug report, a feature request, a question
2. **Mission Control** classifies it (UI fix, data fix, feature, export fix, diagnosis, etc.)
3. Mission Control selects the right agent pipeline (e.g., Design -> Streamlit -> QA)
4. Mission Control presents a brief plan for your confirmation
5. Each agent runs in sequence, producing outputs that feed the next agent
6. **QA Agent** runs last and reports any issues
7. Mission Control gives you a completion summary

## The Agent Team

| # | Agent | Role | When It Activates |
|---|-------|------|-------------------|
| 0 | **Mission Control** | Triage + orchestration | Every interaction |
| 1 | Project Identity | Architecture reference | Always (passive) |
| 2 | Design Agent | Ligne Claire visual system | UI changes |
| 3 | Domain Agent | Brazilian e-commerce expertise | Business logic |
| 4 | QA Agent | Quality assurance (14-point checklist) | After every change |
| 5 | Streamlit Agent | App architecture + implementation | Pages, layout, state |
| 6 | Data Integrity Agent | Calculations + data pipeline | Math, CSV, forecasting |
| 7 | Excel Export Agent | Excel workbook specialist | export_excel.py changes |
| 8 | PPTX Export Agent | PowerPoint specialist | export_pptx.py changes |
| 9 | Power BI Export Agent | Power BI data model specialist | export_powerbi.py changes |

## Mission Types

| Type | Trigger | Agent Pipeline |
|------|---------|----------------|
| `UI_FIX` | Broken UI, visual regression | Design -> Streamlit -> QA |
| `DATA_FIX` | Wrong numbers, NaN values | Data Integrity -> Streamlit -> QA |
| `FEATURE` | New capability | Domain -> Design -> Streamlit -> Data Integrity -> QA |
| `EXPORT_FIX` | Export broken | [Excel/PPTX/PBI] -> QA |
| `DIAGNOSIS` | Performance concern | Domain -> Data Integrity |
| `REFACTOR` | Code quality | Streamlit -> QA |
| `DEPLOY` | Pre-deployment validation | QA -> [all 3 exports parallel] |
| `COMPOUND` | Multi-part request | Decompose -> run sub-missions |

## Slash Commands

| Command | What It Does |
|---------|-------------|
| `/triage` | Classify input and present agent plan without executing |
| `/qa-sweep` | Run full quality check (14-point checklist + compile all 19 files) |
| `/deploy-check` | Pre-deployment validation with GO/NO-GO result |
| `/screenshot-review` | Analyze a screenshot for issues and propose fix pipeline |

## Setup for New Team Members

### 1. Clone the repo
```bash
git clone https://github.com/geoffroytam/performance-command-center.git
```

All `.claude/` configuration is committed to the repo and will be available immediately.

### 2. Set the environment variable

Add to your **user-level** Claude settings (`~/.claude/settings.json`):
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

If you already have a `settings.json`, just add the `env` block.

### 3. Open in Claude Code

Open the project folder in Claude Code. Mission Control activates automatically. That's it!

## File Structure

```
performance-command-center/
  .claude/
    settings.json              # Project-level permissions and env vars
    agents/
      mission-control.md       # Orchestrator (triage + delegation)
      design-agent.md          # Ligne Claire visual system
      domain-agent.md          # Brazilian e-commerce expertise (read-only)
      qa-agent.md              # Quality assurance (14-point checklist)
      streamlit-agent.md       # App architecture + implementation
      data-integrity-agent.md  # Calculations + data pipeline
      excel-export-agent.md    # Excel workbook specialist
      pptx-export-agent.md     # PowerPoint specialist
      powerbi-export-agent.md  # Power BI data model specialist
    commands/
      triage.md                # /triage slash command
      qa-sweep.md              # /qa-sweep slash command
      deploy-check.md          # /deploy-check slash command
      screenshot-review.md     # /screenshot-review slash command
  CLAUDE.md                    # Full agent knowledge base (Section 0-9)
  docs/
    ORCHESTRATION.md           # This file
```

## Architecture Decisions

**Why Opus for the orchestrator, Sonnet for specialists?**
Mission Control needs strong reasoning for triage and multi-agent coordination. Specialists handle focused,
well-scoped tasks where Sonnet is faster and more cost-effective.

**Why is the Domain Agent read-only?**
The Domain Agent provides business context and rules — it never modifies code directly.
Other agents implement its recommendations, maintaining clear separation of concerns.

**Why does QA always run last?**
QA validates the combined output of all preceding agents. Running it mid-pipeline would miss
cross-agent integration issues.

**Why are export agents parallelizable?**
Each export agent owns exactly one file (`export_excel.py`, `export_pptx.py`, `export_powerbi.py`)
with no shared state between them. They can safely run simultaneously.

**Why CLAUDE.md over standalone config files?**
Both are used. CLAUDE.md contains the full agent knowledge base that the main thread AND all subagents
inherit. The `.claude/agents/` files are thin routing wrappers that point to the relevant CLAUDE.md sections.
This avoids drift between definitions.

## Patterns and Templates

This orchestration system is inspired by patterns from the
[claude-code-templates](https://github.com/davila7/claude-code-templates) repository:
- `multi-agent-coordinator` — distributed workflow coordination
- `research-orchestrator` — multi-agent research with defined handoffs
- `development-team` — 18-specialist pipeline with architect -> developer -> reviewer flow
- AI Maestro skill suite — agent management, messaging, planning capabilities
