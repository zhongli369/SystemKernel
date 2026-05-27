# SystemKernel v4.0 — Operations Guide

Day-to-day operational reference for SystemKernel v4.0.

## Quick Start

```bash
# Health check (daily)
python v3/cli/systemkernel.py v4 status

# Operational checklist
python v3/cli/systemkernel.py v4 ops-check

# Compact summary
python v3/cli/systemkernel.py v4 summary

# Generate runbook
python v3/cli/systemkernel.py v4 runbook
```

## Operational Status

`v4 status` prints a one-shot health snapshot:

| Field | Meaning |
|-------|---------|
| Kernel purity | Must be 100/100. Lower means LLM import or kernel tampering. |
| Memory removable | Must be YES. Confirms kernel runs without memory subsystem. |
| Registry entries | Total capability adapters registered (enabled + disabled). |
| Evidence model | READY = evidence bundles importable and validated. |
| Orchestration | READY = orchestration policy profiles importable. |
| Eval harness | READY = eval suite importable. |
| Complexity verdict | ACCEPT / REVIEW / REJECT from complexity gate. |

## Operational Checklist

`v4 ops-check` runs a static checklist across 8 categories:

| Category | What it checks |
|----------|---------------|
| daily | Kernel purity, complexity gate, memory removability |
| registry | Entries exist, 8 capability types covered, no disabled required |
| evidence | Evidence model importable, bundles buildable, truth_source=False |
| orchestration | Policies listable, dry-run succeeds, ECC disabled placeholder |
| eval | Suite runs clean, regression passes, benefit-complexity ACCEPT |
| context | Context pack plans work, budget policy exists |
| safety | No LLM in kernel, no external execution, no network |
| ecc | ECC not integrated, no install/repair/hook modification |

## Runbook

`v4 runbook` generates a complete operational runbook (Markdown or JSON). The runbook covers:

1. Daily Status Check
2. Capability Registry Review
3. Evidence Inspection
4. Context Pack Planning
5. Usage Report Inspection
6. Orchestration Dry-Run
7. Eval / Regression Check
8. Complexity Gate Check
9. What NOT to Do
10. How ECC is Treated
11. Provider Trial Proposal Procedure

## Daily Routine

```bash
# 1. Health check
python v3/cli/systemkernel.py v4 status

# 2. Complexity gate
python v3/cli/systemkernel.py quality

# 3. Eval regression
python v3/cli/systemkernel.py eval regression

# 4. Review checklist
python v3/cli/systemkernel.py v4 ops-check
```

## Safety Boundaries

- All v4 ops commands are **read-only** — no side effects
- No external tool execution through the kernel boundary
- No network access in any ops module
- ECC (everything-claude-code) is a **disabled future placeholder** — never integrated, cloned, installed, or executed
- Never enable blocked providers without explicit human approval and a formal trial gate
- Never modify `v3/kernel/` files — kernel is sealed
- Never add new truth sources — `truth_source` must always be `False` for external data

## Provider Trial Procedure

To propose graduating a blocked provider to trial status:

1. Write a trial proposal documenting provider name, capability type, need, safety boundaries, and evidence plan
2. Run `python v3/cli/systemkernel.py skill-evolution mock` (dry-run only)
3. Run `python v3/cli/systemkernel.py eval run` (verify no regressions)
4. Run `python v3/cli/systemkernel.py eval benefit` (benefit-complexity check)
5. If all gates pass, submit for human review

## Files Reference

| File | Purpose |
|------|---------|
| `v3/ops/v4_ops.py` | V4OpsStatus and V4OpsChecklist dataclasses + builders |
| `v3/ops/runbook.py` | V4Runbook dataclass + 11-section runbook builder |
| `v3/ops/__init__.py` | Public exports |
| `v3/cli/systemkernel.py` | CLI with `v4` subparser (status, ops-check, runbook, summary) |
| `v3/tests/test_v4_productization_ops.py` | 44 tests for Phase 11 |
| `v3/exports/v4_ops_status.json` | Generated ops status snapshot |
| `v3/exports/v4_ops_checklist.json` | Generated ops checklist |
| `v3/exports/v4_runbook.json` | Generated runbook (JSON) |
| `v3/exports/v4_runbook.md` | Generated runbook (Markdown) |
| `v3/exports/phase_11_productization_ops_report.md` | Phase 11 completion report |

## Version

v4.0 — Phase 11 Productization + Ops
