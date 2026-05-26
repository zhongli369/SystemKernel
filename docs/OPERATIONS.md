# SystemKernel v3.0 — Operations Guide

**Version:** 3.0.0
**Status:** STABLE BASELINE — Feature Freeze
**Date:** 2026-05-26

---

## How to Verify the v3.0 Baseline

Run the single verification script:

```bash
python scripts/verify_v3_baseline.py
```

This checks:
- All required source files exist
- All export reports exist and are valid JSON
- Kernel invariants test suite passes
- Release freeze test suite passes
- CLI doctor health checks pass
- CLI reports summary works
- Golden path runs end-to-end
- Kernel purity remains at 100/100
- Memory remains removable
- Complexity gate is not REJECT
- Release validation matrix reports release_ready

Expected output: All checks PASS, exit code 0.

### Individual Verification Commands

| What | Command |
|------|---------|
| Kernel invariants | `python v3/tests/test_kernel_invariants.py` |
| Release freeze | `python v3/tests/test_release_freeze.py` |
| Baseline packaging | `python v3/tests/test_baseline_packaging.py` |
| Golden path | `python v3/tests/test_golden_path.py` |
| Complexity budget | `python v3/tests/test_complexity_budget.py` |
| Developer CLI | `python v3/tests/test_developer_cli.py` |
| CLI doctor | `python v3/cli/systemkernel.py doctor` |
| CLI status | `python v3/cli/systemkernel.py status` |
| Reports summary | `python v3/cli/systemkernel.py reports summary` |
| Golden path (live) | `python examples/golden_path/run_golden_path.py` |

---

## How to Run the CLI

The CLI is at `v3/cli/systemkernel.py`. All commands:

```bash
# System status (purity, tests, memory, complexity)
python v3/cli/systemkernel.py status

# Complexity budget gate
python v3/cli/systemkernel.py quality

# Memory system report
python v3/cli/systemkernel.py memory report

# List all export reports
python v3/cli/systemkernel.py reports list

# Summary of key reports
python v3/cli/systemkernel.py reports summary

# Health checks (19 checks)
python v3/cli/systemkernel.py doctor

# Repo intake — profile for a specific repo
python v3/cli/systemkernel.py intake profile Repomix

# Repo intake — list all known profiles
python v3/cli/systemkernel.py intake list

# Repo intake — summarize all profiles with decisions
python v3/cli/systemkernel.py intake summarize

# Repo intake — generate external tool registry
python v3/cli/systemkernel.py intake registry

# Repo intake — generate GitHub clone plan (JSON + MD)
python v3/cli/systemkernel.py intake clone-plan

# Repo intake — print recommended clone order (PLAN ONLY)
python v3/cli/systemkernel.py intake clone-list
```

---

## How to Regenerate Reports

Reports live in `v3/exports/`. To regenerate:

```bash
# Regenerate complexity budget report
python v3/cli/systemkernel.py quality

# Regenerate memory system report
python v3/cli/systemkernel.py memory report

# Regenerate external tool registry
python v3/cli/systemkernel.py intake registry

# Regenerate clone plan
python v3/cli/systemkernel.py intake clone-plan

# Regenerate package manifest
python -c "from v3.release.package_manifest import build_package_manifest, write_package_manifest; m=build_package_manifest(); write_package_manifest(m, 'v3/exports/package_manifest.json')"

# Regenerate operational handoff
python -c "from v3.release.handoff import build_handoff, write_handoff_json, write_handoff_md; h=build_handoff(); write_handoff_json(h, 'v3/exports/operational_handoff.json'); write_handoff_md(h, 'v3/exports/operational_handoff.md')"
```

---

## What NOT to Modify After Freeze

The following are **FROZEN**. Modifying them requires a new major version (v4.0):

### Kernel Pipeline
- Execution order: lint → typecheck → test → [custom] → report
- This order is immutable. Do not reorder, skip, or add stages.

### EventBus Routing
- 13 deterministic rules in the routing table
- No new event types without a major version bump
- No LLM-based classification

### Adapter Semantics
- `resolve()` is the single entry point for routing
- Empty binding on no match (no fallback, no default)
- Same input must always produce same output

### TaskSystem State Machine
- Valid transitions: backlog → active → done (reopen: done → active)
- No other transitions are valid

### Registry Schema
- 9 required fields per skill entry
- Registry is the sole source of truth for skill existence

### ExecutionLoop Retry Policy
- Maximum 2 attempts (initial + 1 correction based on error log)
- No AI-based correction decisions

### Observability Contract
- Write-only (records behavior, never drives it)
- Append-only (no modification after write)
- Removable (delete Observability/ → kernel behavior unchanged)

### Memory Boundary
- Kernel files must NOT import from `v3.memory`
- Allowed exceptions: `memory_contract.py`, `memory_candidate.py`, `memory_gateway.py`

---

## How to Add Future Phases Safely

Allowed additions (do not require v4.0):

1. **New test files** — add to `v3/tests/`, prefix with `test_`
2. **New export reports** — add to `v3/exports/`
3. **New documentation** — add to `docs/` or `v3/exports/`
4. **New examples** — add to `examples/`
5. **New CLI commands** — add to `v3/cli/systemkernel.py` (must not modify kernel behavior)
6. **New external tool profiles** — add to `v3/intake/repo_profiles.py`
7. **New release artifacts** — add to `v3/release/`

Safety checklist for any addition:

- [ ] Does not add an LLM import to kernel/, memory/, quality/, or cli/
- [ ] Does not add a vector database import
- [ ] Does not add network access (no urllib, requests, httpx, socket)
- [ ] Does not modify the kernel execution pipeline
- [ ] Does not modify the EventBus routing table
- [ ] Does not modify Adapter.resolve() semantics
- [ ] Does not change the TaskSystem state machine
- [ ] Does not import v3.memory from kernel/ (outside allowed files)
- [ ] Complexity gate remains REVIEW or better (not REJECT)
- [ ] Kernel purity remains 100/100
- [ ] Memory remains removable (YES)
- [ ] All existing tests still pass (no regressions)

---

## Rollback Guidance

SystemKernel v3.0 is a baseline release. To roll back:

### Git Rollback

```bash
# Find the pre-v3.0 commit
git log --oneline -20

# Detach to that commit
git checkout <commit-hash>

# Or create revert commits
git revert <range-of-v3-commits>
```

### Data Safety

- Memory data is in `v3/checkpoints/` — append-only JSONL, no data loss on rollback
- Traces are in `v3/traces/` — append-only
- Metrics are in `v3/metrics/` — append-only
- Kernel source is unchanged by operation
- Deleting `v3/` and reverting to v2.0 is safe

### What Rollback Does NOT Affect

- External tool installations (separate repositories)
- Git history (immutable)
- System configuration outside this repository

### Safe Rollback Procedure

1. `python scripts/verify_v3_baseline.py` — confirm current state
2. Note the current commit hash
3. `git checkout <target-commit>`
4. `python scripts/verify_v3_baseline.py` — confirm restored state
5. Validate that expected behavior is restored

---

## Complexity Gate Policy

The complexity gate evaluates whether the codebase's complexity is justified
by its benefit. It runs automatically via `python v3/cli/systemkernel.py quality`.

### Verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| ACCEPT | Complexity within budget | Proceed freely |
| REVIEW | Complexity exceeds benefit threshold | Manual review recommended; does not block |
| REJECT | Complexity severely exceeds budget | Release blocked; must reduce complexity |

### Current Policy

- **REVIEW is a warning, not a gate.** Only REJECT blocks.
- The v3.0 baseline targets REVIEW at worst.
- If the gate shows REJECT, reduce module complexity before proceeding.
- The gate uses AST-based analysis (no LLM, no network).

---

## External Tool Clone Policy

External tools referenced in the registry and clone plan are **NOT** part of
SystemKernel. They are separate repositories with their own licenses,
maintainers, and security postures.

### Rules

1. Clone external tools into `F:/Claude/Github/` — outside kernel boundary.
2. Do NOT integrate external tools into the kernel source tree.
3. All clone operations require manual review and execution.
4. No automated `git clone` in any kernel module.
5. External tools must be separately audited before any integration.

### Clone Plan

The clone plan (`v3/exports/github_clone_plan.md`) is a **recommendation** only.
Review each item before executing. The plan is generated by:

```bash
python v3/cli/systemkernel.py intake clone-plan
```

No actual cloning is performed by any SystemKernel module. All clone commands
must be run manually.

---

*SystemKernel v3.0 Operations Guide — Phase 6A*
