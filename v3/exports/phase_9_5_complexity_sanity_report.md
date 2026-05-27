# Phase 9.5 — Complexity Sanity Check — Report

- **Date:** 2026-05-27
- **Phase:** 9.5
- **Status:** COMPLETE
- **Verdict:** ACCEPT
- **Risk Level:** LOW

## Summary

Phase 9.5 audits Phase 9 (Orchestration Policy Layer) for overengineering,
dead abstractions, duplication, and complexity bloat. No code changes were
made. The analysis is purely observational.

## Metrics

| Metric | orchestration_policy.py | orchestration_profiles.py | Total |
|--------|------------------------|--------------------------|-------|
| LOC | 645 | 309 | 954 |
| Dataclasses | 6 | 1 | 7 |
| Public functions | 7 | 9 | 16 |
| Private helpers | 2 | 2 | 4 |
| Module-level constants | 6 | 0 | 6 |
| Cross-plane imports | 1 (evidence) | 1 (orchestration_policy) | 2 |
| External dependencies | 0 | 0 | 0 |

## Dataclass Inventory

| Dataclass | Fields | File | Purpose |
|-----------|--------|------|---------|
| OrchestrationPolicy | 15 | orchestration_policy.py | Policy governing what can be planned together |
| OrchestrationRequest | 7 | orchestration_policy.py | Dry-run request to plan orchestration |
| OrchestrationStep | 11 | orchestration_policy.py | One planned/blocked step |
| OrchestrationPlan | 7 | orchestration_policy.py | Deterministic dry-run plan |
| OrchestrationPolicyReport | 6 | orchestration_policy.py | Combined policy + request + plan report |
| OrchestrationValidationResult | 4 | orchestration_policy.py | Validation outcome |
| OrchestrationProfileStatus | 4 | orchestration_profiles.py | Profile summary |

## Duplication Analysis

| Check | Result |
|-------|--------|
| _compute_hash vs _compute_policy_hash | DISTINCT — different hash-key stripping logic |
| _build pattern vs other profile modules | CONSISTENT — follows established architecture |
| to_dict() on every dataclass | CONSISTENT — project-wide pattern, not duplication |
| Policy profile factories (×6) | NECESSARY — each has different allowed/forbidden types |
| Validator functions (×2) | DISTINCT — step validation ≠ plan validation |

## Simplification Opportunities

| Opportunity | Action |
|-------------|--------|
| Unify _compute_hash / _compute_policy_hash | REJECTED — different purposes, unification adds complexity |
| Mixin for to_dict() | REJECTED — adds abstraction for 1-line methods, not worth it |
| Merge validators | REJECTED — step-level and plan-level validation serve different callers |
| Reduce profile count | REJECTED — each profile gates a distinct capability set |
| ECC profile minimality | ALREADY MINIMAL — 4 types, disabled, dry-run only |

## Dead Code Check

| Check | Result |
|-------|--------|
| Unused functions | 0 — all called by CLI, tests, or internal callers |
| Unused dataclasses | 0 — all instantiated in plan_orchestration or report builders |
| Unused constants | 0 — ALL_STATUSES used in tests, status constants used in validators |
| Dead code paths | 0 — all branches exercised by tests |
| Unreachable code | 0 |

## Invariant Verification

| Invariant | Status |
|-----------|--------|
| truth_source always False | PASS — all 7 dataclasses enforce this |
| dry_run only | PASS — no execution, no file mod, no network |
| Kernel purity (100/100) | PASS — test_kernel_invariants.py |
| Memory removable | PASS |
| No LLM imports | PASS — stdlib only |
| No new runtime loop | PASS |
| No registry mutation | PASS |
| No external execution | PASS |
| Deterministic hashing | PASS — all hashes SHA-256, sort_keys=True |

## Cross-Plane Dependencies

| From | To | Type | Risk |
|------|----|------|------|
| orchestration_policy.py | v3.external.evidence | Lazy import in orchestration_plan_to_evidence() | LOW — evidence model is stable |
| orchestration_profiles.py | v3.external.orchestration_policy | Lazy import in _build() | LOW — same-phase sibling |

No circular dependencies. Both imports are lazy (inside function bodies).

## Complexity Budget

| Factor | Score |
|--------|-------|
| Ability gain estimate | +30 (multi-adapter planning, policy enforcement, evidence mapping) |
| Complexity growth estimate | +15 (954 LOC, 7 dataclasses, 16 functions) |
| Net value | +15 (positive — ability exceeds complexity) |
| Risk ratio | 0.5 (LOW) |

## Test Results

| Test Suite | Result |
|------------|--------|
| test_orchestration_policy.py | 71/71 (1 skipped) |
| test_complexity_budget.py | 41/41 |
| test_kernel_invariants.py | 6/6 (100/100 purity) |

## Verdict

- **Complexity Gate:** ACCEPT
- **Risk Level:** LOW
- **Overengineering Detected:** NO
- **Recommended Action:** PROCEED to Phase 10
- **Kernel Protected:** YES
- **Memory Removable:** YES
