# SystemKernel v4.0 — Operational Runbook

Version: 4.0
Hash: 0326046aa79da2f9

---

## Daily Status Check

**Purpose:** Quick health check of all v4 subsystems. Run this daily or after any change.

### Commands

```bash
python v3/cli/systemkernel.py status
```

```bash
python v3/cli/systemkernel.py quality
```

```bash
python v3/cli/systemkernel.py v4 status
```

### Safety Notes

- All commands are read-only — no side effects.
- If any check fails, investigate before running further commands.

---

## Capability Registry Review

**Purpose:** Review registered external capability adapters and their status.

### Commands

```bash
python v3/cli/systemkernel.py capability summary
```

```bash
python v3/cli/systemkernel.py capability list
```

```bash
python v3/cli/systemkernel.py capability show <adapter_id>
```

### Safety Notes

- Registry is the single source of truth for external capability existence.
- Never enable a disabled adapter without passing the trial gate first.
- Do not add registry entries without Phase 2 compliance checks.

---

## Evidence Inspection

**Purpose:** Inspect evidence bundles to verify external adapter outputs are recorded correctly.

### Commands

```bash
python v3/cli/systemkernel.py context-plane evidence <path>
```

```bash
python v3/cli/systemkernel.py memory-intel evidence
```

```bash
python v3/cli/systemkernel.py agent-worker evidence
```

```bash
python v3/cli/systemkernel.py workspace evidence
```

```bash
python v3/cli/systemkernel.py skill-evolution evidence
```

### Safety Notes

- All evidence records have truth_source=False — evidence is NOT truth.
- Evidence is always TRUST_LOW by default.
- Never base kernel decisions on evidence alone.

---

## Context Pack Planning

**Purpose:** Plan context packs for codebase analysis without executing external tools.

### Commands

```bash
python v3/cli/systemkernel.py context-plane plan <target> --output ctx.md
```

```bash
python v3/cli/systemkernel.py context-plane inspect <path>
```

### Safety Notes

- Context pack planning is dry-run by default — no files are read outside budget.
- Use --allow-execute only when you fully trust the target directory.

---

## Usage Report Inspection

**Purpose:** Inspect Claude Code usage reports for operational insights.

### Commands

```bash
python v3/cli/systemkernel.py usage inspect <ccusage.json>
```

```bash
python v3/cli/systemkernel.py usage summarize <ccusage.json> --output report.json
```

### Safety Notes

- Usage reports are external evidence, not kernel truth.
- Do not use usage data for automated decision-making.

---

## Orchestration Dry-Run

**Purpose:** Plan capability adapter orchestration without executing anything.

### Commands

```bash
python v3/cli/systemkernel.py orchestrate policies
```

```bash
python v3/cli/systemkernel.py orchestrate plan --profile safe_context_only
```

```bash
python v3/cli/systemkernel.py orchestrate plan --profile full_external_review
```

```bash
python v3/cli/systemkernel.py orchestrate evidence --profile safe_context_only
```

### Safety Notes

- All orchestration is dry-run only — nothing is executed.
- Orchestration plans are PLANS, not truth sources.
- ECC profile (ecc_harness_review) is disabled and must stay disabled.

---

## Eval / Regression Check

**Purpose:** Run deterministic eval suite and regression matrix to verify v4 integrity.

### Commands

```bash
python v3/cli/systemkernel.py eval suite
```

```bash
python v3/cli/systemkernel.py eval run
```

```bash
python v3/cli/systemkernel.py eval regression
```

```bash
python v3/cli/systemkernel.py eval benefit
```

### Safety Notes

- All evals are deterministic and local — no network, no LLM.
- Regression failures that are 'release blocking' must be fixed before merging.
- Benefit-complexity REJECT means the change adds too much complexity for too little benefit.

---

## Complexity Gate Check

**Purpose:** Verify complexity budget is not exceeded by recent changes.

### Commands

```bash
python v3/cli/systemkernel.py quality
```

### Safety Notes

- Complexity gate REJECT blocks all further changes.
- REVIEW means the change needs justification before proceeding.
- ACCEPT means complexity is within budget for the benefit provided.

---

## What NOT to Do

**Purpose:** Operational boundaries that must not be crossed.

### Safety Notes

- DO NOT execute external tools through the kernel boundary.
- DO NOT enable blocked providers (OpenHands, AutoGen, Mem0, Graphiti, etc.) without a formal trial.
- DO NOT modify v3/kernel/ files — kernel is sealed.
- DO NOT modify v3/memory/ runtime behavior.
- DO NOT add new truth sources — truth_source must always be False for external data.
- DO NOT add LLM/AI imports to kernel modules.
- DO NOT install or clone ECC — it is a future external provider, not a dependency.
- DO NOT modify registry.json or skill files through automation — use proposal-only skill evolution.

---

## How ECC is Treated

**Purpose:** ECC (everything-claude-code) is a FUTURE external harness enhancement provider.

### Commands

```bash
python v3/cli/systemkernel.py orchestrate plan --profile ecc_harness_review
```

```bash
# ECC repo: https://github.com/affaan-m/everything-claude-code
```

```bash
# Status: NOT integrated, NOT cloned, NOT installed
```

### Safety Notes

- ECC is listed as ecc_harness_review profile — disabled, dry-run only.
- ECC capability types: skill, tool, eval, context (4 of 8).
- ECC must never be auto-installed, auto-cloned, or auto-executed.
- ECC integration requires a formal Phase 12+ trial gate.
- SystemKernel must not become an ECC clone or dependency.

---

## How to Propose a Real Provider Trial Safely

**Purpose:** Procedure for graduating a blocked provider to trial status.

### Commands

```bash
# 1. Write a trial proposal documenting:
```

```bash
#    - Provider name and capability type
```

```bash
#    - Why the provider is needed
```

```bash
#    - What safety boundaries apply
```

```bash
#    - What evidence will be collected
```

```bash
# 2. Create a skill evolution proposal (dry-run only):
```

```bash
python v3/cli/systemkernel.py skill-evolution mock
```

```bash
# 3. Run eval suite to verify no regressions:
```

```bash
python v3/cli/systemkernel.py eval run
```

```bash
# 4. Run benefit-complexity check:
```

```bash
python v3/cli/systemkernel.py eval benefit
```

```bash
# 5. If all gates pass, submit proposal for human review
```

### Safety Notes

- Never enable a provider without explicit human approval.
- All trial proposals are dry-run by default.
- Provider enablement requires registry update — do NOT do this automatically.
- ECC requires its own formal trial gate before any integration.

---
