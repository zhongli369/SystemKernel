# SystemKernel v4.0 — Phase 0: v3 Baseline Protection Report

**Phase:** 0 | **Status:** COMPLETE
**Date:** 2026-05-26 | **Version:** 4.0.0-alpha

---

## Summary

Phase 0 establishes the v3.0 baseline protection that gates all v4.0
development. Every future v4.0 phase must pass the baseline guard before
proceeding.

## Deliverables

| File | Status | Description |
|------|--------|-------------|
| `Docs/V4_ROADMAP.md` | Created | 12-phase v4.0 roadmap "Pluggable Intelligence Plane" |
| `Docs/V4_INVARIANTS.md` | Created | 10 mandatory invariants with machine-checkable rules |
| `v3/release/v4_baseline_guard.py` | Created | Stdlib-only baseline guard (BaselineGuardResult, builder, CLI) |
| `v3/tests/test_v4_baseline_guard.py` | Created | 19 tests covering all invariants |
| `v3/exports/v4_baseline_guard_report.json` | Generated | Machine-readable invariant check report |

## Invariant Results

| Invariant | Status | Detail |
|-----------|--------|--------|
| INV-01 Kernel Immutability | PASS | 20 files checked, 0 modified |
| INV-02 Memory Removability | PASS | Kernel invariants pass with memory present |
| INV-03 Kernel LLM-Free | PASS | 0 LLM imports in v3/kernel/ |
| INV-04 Protected Paths | PASS | All protected files match baseline hashes |
| INV-05 Forbidden Deps | PASS | 0 forbidden imports in core codebase |
| INV-06 Adapter Contract | PASS | resolve(CapabilityRequest) → CapabilityBinding intact |
| INV-07 Execution Pipeline | PASS | LintStage→PipelineStage tuple; max_retries=1 |
| INV-08 EventBus Routing | PASS | 13 routing rules, all required actions present |
| INV-09 Observability Contract | PASS | Write-only, append-only, zero LLM |
| INV-10 Baseline Tag | PASS | Tag systemkernel-v3.0.0-baseline → 13f2069 |

**Result: 10/10 PASS**

## Protected State

- **Kernel files:** 20 files, SHA-256 verified against baseline
- **Release files:** 8 files, SHA-256 verified (9 including v4_baseline_guard.py itself)
- **Verify script:** `scripts/verify_v3_baseline.py`, SHA-256 verified
- **Memory:** Removable, kernel invariants pass without it
- **Baseline tag:** `systemkernel-v3.0.0-baseline` → `13f2069c8fa6`

## Guard Capabilities

The `v4_baseline_guard.py` provides:

- `BaselineGuardResult` — frozen dataclass with all 10 invariant results
- `build_v4_baseline_guard()` — run all checks, return result
- `check_protected_paths()` — INV-04 standalone check
- `check_forbidden_dependencies()` — INV-05 standalone check
- `write_v4_baseline_guard_report()` — write JSON report
- CLI: `--dry-run` (print only), `--verify` (print + write report)

## Verification

```bash
# Baseline guard
python v3/release/v4_baseline_guard.py --verify

# Baseline guard tests
python v3/tests/test_v4_baseline_guard.py

# Kernel invariants
python v3/tests/test_kernel_invariants.py

# Complexity budget
python v3/tests/test_complexity_budget.py

# External tools wrapup
python v3/tests/test_external_tools_wrapup.py
```

## Hard Exclusions Verified

- [x] No modifications to `v3/kernel/` (20 files unchanged)
- [x] No modifications to `v3/memory/` runtime behavior
- [x] No modifications to event sourcing, checkpoint/replay
- [x] No modifications to `scripts/verify_v3_baseline.py`
- [x] No release baseline tag movement
- [x] No dependency installations
- [x] No network commands executed

## Gate for Phase 1

Phase 1 (Capability Adapter Contract) may proceed when:
- All 19 baseline guard tests pass
- Baseline guard reports 10/10 invariants
- Kernel invariants 100/100
- Complexity gate not REJECT
- External tools wrapup suite passes

---

*SystemKernel v4.0 Phase 0 — v3 Baseline Protection Complete*
