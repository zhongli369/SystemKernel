# SystemKernel v4.0 — Mandatory Invariants

**Version:** 4.0.0 | **Baseline:** v3.0.0 (commit `13f2069`)
**Enforcement:** `v3/release/v4_baseline_guard.py` | **Date:** 2026-05-26

---

These 10 invariants MUST hold for every v4.0 phase. Each invariant is
machine-checkable by `v4_baseline_guard.py`. A single invariant failure
blocks the phase from proceeding.

---

## INV-01: Kernel Source Immutability

**Rule:** No file under `v3/kernel/` may be modified by any v4.0 phase.

**Check:** SHA-256 hash of every `v3/kernel/*.py` file matches the v3.0.0
baseline commit (`13f2069`).

**Rationale:** The kernel is the deterministic foundation. Any modification
risks breaking the execution contract that all intelligence modules depend on.

---

## INV-02: Memory Folder Removability

**Rule:** Deleting `v3/memory/` entirely must not change kernel execution
behavior. All 6 kernel invariant tests must pass with memory folder missing.

**Check:** Move `v3/memory/` to temp location, run kernel invariants, verify
purity_score == 100.

**Rationale:** Memory is outside the kernel boundary. Intelligence-plane memory
(v4.0) must be equally removable.

---

## INV-03: Zero LLM Imports in Kernel

**Rule:** No file under `v3/kernel/` may import `openai`, `anthropic`,
`langchain`, `crewai`, `autogen`, or any LLM-related package.

**Check:** AST scan of all `v3/kernel/*.py` files for banned import patterns.

**Rationale:** The kernel is deterministic. LLM imports would make it
non-deterministic and violate the purity contract.

---

## INV-04: Protected Path Integrity

**Rule:** These paths must not be modified by any v4.0 phase:
- `v3/kernel/` — kernel source
- `v3/memory/` — memory runtime
- `v3/release/` — release tooling
- `scripts/verify_v3_baseline.py` — baseline verification

**Check:** Compare file hashes against baseline. Any difference is a violation.

**Rationale:** These paths constitute the v3.0 certified baseline. v4.0
phases are additive only — they must not rewrite history.

---

## INV-05: Forbidden Dependency Absence

**Rule:** No Python file in the repository may add a runtime dependency on:
`openai`, `anthropic`, `langchain`, `crewai`, `autogen`, `mem0`, `graphiti`,
`chromadb`, `qdrant`, `milvus`.

**Check:** AST scan of all `*.py` files (excluding `v4/` intelligence plane)
for banned imports.

**Rationale:** These are intelligence-plane dependencies. They belong in
`v4/intelligence/` (which is removable), never in the core repository.

---

## INV-06: Adapter Contract Stability

**Rule:** `SkillsManagementSystem/core/adapter.py` resolve() signature,
return type (CapabilityBinding), and empty-binding contract must not change.

**Check:** Verify `resolve(CapabilityRequest) → CapabilityBinding` signature
preserved. Empty binding still returns `skill_id=""`, `confidence=0.0`.

**Rationale:** All v4.0 intelligence routing decorates this interface.
If the contract changes, all intelligence modules break.

---

## INV-07: Execution Pipeline Immutability

**Rule:** The ExecutionLoop pipeline order (lint → typecheck → test → [custom]
→ report) must not change. Retry policy (max 2 attempts) must not change.

**Check:** Verify pipeline order in ExecutionLoop source. Verify retry count
in execution config.

**Rationale:** Intelligence modules depend on predictable execution semantics.
A changed pipeline means changed behavior for every skill.

---

## INV-08: EventBus Routing Table Stability

**Rule:** The 13 deterministic EventBus routing rules must not be removed
or altered. New rules may only be added at the END of the table.

**Check:** Verify all 13 original rules present and unchanged.

**Rationale:** Event-driven task creation is the backbone of automated
workflows. Changing rules breaks existing automations.

---

## INV-09: Observability Write-Only Contract

**Rule:** Observability must remain write-only, append-only, and removable.
Zero LLM imports. Zero decision-making function calls.

**Check:** Verify Observability/ has no LLM imports. Verify all hooks
use `try: except Exception: pass` pattern.

**Rationale:** Observability records behavior. Intelligence-plane
observability (Phase 6) is separate and removable.

---

## INV-10: Baseline Tag Immutability

**Rule:** Git tag `systemkernel-v3.0.0-baseline` must point to commit
`13f2069` and must not be moved or deleted.

**Check:** `git rev-list -n 1 systemkernel-v3.0.0-baseline` == `13f2069...`

**Rationale:** The baseline tag is the anchor point for all v4.0 verification.
Without it, there is no way to prove that v4.0 work hasn't damaged v3.0.

---

## Invariant Verification Matrix

| Invariant | Scope | Check Method | Blocker |
|-----------|-------|-------------|---------|
| INV-01 | `v3/kernel/` | SHA-256 hash comparison | YES |
| INV-02 | `v3/memory/` | Delete-and-test | YES |
| INV-03 | `v3/kernel/` | AST import scan | YES |
| INV-04 | Protected paths | Hash comparison | YES |
| INV-05 | All `*.py` | AST import scan | YES |
| INV-06 | Adapter module | Signature check | YES |
| INV-07 | ExecutionLoop | Source analysis | YES |
| INV-08 | EventBus | Rule count check | YES |
| INV-09 | Observability | Import + hook scan | YES |
| INV-10 | Git tag | rev-list comparison | YES |

---

## Enforcement

```bash
# Run baseline guard (dry-run — checks only, no modifications)
python v3/release/v4_baseline_guard.py --dry-run

# Run baseline guard (verify — full check with report)
python v3/release/v4_baseline_guard.py --verify

# Run baseline guard tests
python v3/tests/test_v4_baseline_guard.py
```

A single invariant failure produces a non-zero exit code and a detailed
JSON report at `v3/exports/v4_baseline_guard_report.json`.
