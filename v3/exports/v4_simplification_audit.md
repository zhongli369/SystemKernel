# SystemKernel v4.0 — Simplification Audit Report

**Phase:** 13C — v4 Simplification / API Surface Reduction Audit
**Modules analyzed:** 90
**Total LOC:** 45365
**Total public API functions:** 428
**Total exports:** 475
**Ability+10% Complexity+300% risk:** **MEDIUM**

## Summary

- Safe to simplify now: **0**
- Defer to later: **46**
- Do not touch: **0**

## Do Not Touch (Protected)

- `scripts/verify_v3_baseline.py`
- `scripts/verify_v4_baseline.py`
- `v3/kernel`
- `v3/memory/compaction.py`
- `v3/memory/compaction_integrity.py`
- `v3/memory/episodic_adapter.py`
- `v3/memory/episodic_store.py`
- `v3/memory/index_integrity.py`
- `v3/memory/integrity.py`
- `v3/memory/memory_adapter_base.py`
- `v3/memory/memory_service.py`
- `v3/memory/provenance.py`
- `v3/memory/recall.py`
- `v3/memory/retrieval.py`
- `v3/memory/runtime.py`
- `v3/memory/semantic_index.py`
- `v3/memory/system_report.py`
- `v3/release`

## Simplification Opportunities

### SIMPLIFY-001: oversized_module — [simplify_later]
- **Target:** `v3/cli/systemkernel.py`
- **Description:** Module exceeds 600 lines (3076 LOC). Consider extracting helper modules.
- **Complexity reduction:** 57.37
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-002: oversized_module — [simplify_later]
- **Target:** `v3/external/__init__.py`
- **Description:** Module exceeds 600 lines (851 LOC). Consider extracting helper modules.
- **Complexity reduction:** 54.2
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-033: excessive_exports — [simplify_later]
- **Target:** `v3/external/__init__.py`
- **Description:** Module exports 347 public symbols. Reduce to core API surface.
- **Complexity reduction:** 52.05
- **Risk:** medium
- **Reason:** Large __all__ inflates API surface. Audit which exports are actually consumed.

### SIMPLIFY-037: cli_surface_sprawl — [simplify_later]
- **Target:** `v3/cli/systemkernel.py`
- **Description:** CLI module has 57 subcommands. Consider grouping or removing rarely used commands.
- **Complexity reduction:** 14.25
- **Risk:** medium
- **Reason:** 57 CLI subcommands is a large surface. Audit which are used and which are scaffolding.

### SIMPLIFY-038: duplicated_policy_logic — [simplify_later]
- **Target:** `v3/external/`
- **Description:** Multiple policy modules detected (7 files). Consider consolidating shared policy logic.
- **Complexity reduction:** 8.4
- **Risk:** medium
- **Reason:** Policy files (v3/external/agent_worker_policy.py, v3/external/evidence_policy.py, v3/external/memory_intelligence_policy.py, v3/external/orchestration_policy.py, v3/external/skill_evolution_policy.py) may share validation patterns. Consolidate into shared base.

### SIMPLIFY-003: oversized_module — [simplify_later]
- **Target:** `v3/external/skill_evolution.py`
- **Description:** Module exceeds 600 lines (735 LOC). Consider extracting helper modules.
- **Complexity reduction:** 7.8
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-034: excessive_exports — [simplify_later]
- **Target:** `v3/release/__init__.py`
- **Description:** Module exports 52 public symbols. Reduce to core API surface.
- **Complexity reduction:** 7.8
- **Risk:** medium
- **Reason:** Large __all__ inflates API surface. Audit which exports are actually consumed.

### SIMPLIFY-004: oversized_module — [simplify_later]
- **Target:** `v3/external/workspace_context.py`
- **Description:** Module exceeds 600 lines (686 LOC). Consider extracting helper modules.
- **Complexity reduction:** 7.46
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-005: oversized_module — [simplify_later]
- **Target:** `v3/external/context_plane.py`
- **Description:** Module exceeds 600 lines (680 LOC). Consider extracting helper modules.
- **Complexity reduction:** 6.31
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-006: oversized_module — [simplify_later]
- **Target:** `v3/external/orchestration_policy.py`
- **Description:** Module exceeds 600 lines (644 LOC). Consider extracting helper modules.
- **Complexity reduction:** 6.28
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-007: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_v4_release_freeze.py`
- **Description:** Module exceeds 600 lines (832 LOC). Consider extracting helper modules.
- **Complexity reduction:** 5.97
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-035: excessive_exports — [simplify_later]
- **Target:** `v3/evals/__init__.py`
- **Description:** Module exports 37 public symbols. Reduce to core API surface.
- **Complexity reduction:** 5.55
- **Risk:** medium
- **Reason:** Large __all__ inflates API surface. Audit which exports are actually consumed.

### SIMPLIFY-008: oversized_module — [simplify_later]
- **Target:** `v3/evals/evaluation_harness.py`
- **Description:** Module exceeds 600 lines (634 LOC). Consider extracting helper modules.
- **Complexity reduction:** 4.77
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-009: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_release_freeze.py`
- **Description:** Module exceeds 600 lines (653 LOC). Consider extracting helper modules.
- **Complexity reduction:** 4.01
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-039: duplicate_helper — [simplify_later]
- **Target:** `v3/external/`
- **Description:** Multiple profiles modules (5 files). Consider unifying profile loading.
- **Complexity reduction:** 4.0
- **Risk:** low
- **Reason:** Profile modules (v3/external/agent_worker_profiles.py, v3/external/memory_intelligence_profiles.py, v3/external/orchestration_profiles.py, v3/external/skill_evolution_profiles.py, v3/external/workspace_context_profiles.py) follow similar patterns. A shared loader reduces duplication.

### SIMPLIFY-010: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_external_tool_registry.py`
- **Description:** Module exceeds 600 lines (844 LOC). Consider extracting helper modules.
- **Complexity reduction:** 3.94
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-011: oversized_module — [simplify_later]
- **Target:** `v3/release/v4_baseline_guard.py`
- **Description:** Module exceeds 600 lines (797 LOC). Consider extracting helper modules.
- **Complexity reduction:** 3.9
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-012: oversized_module — [simplify_later]
- **Target:** `v3/quality/v4_simplification_audit.py`
- **Description:** Module exceeds 600 lines (705 LOC). Consider extracting helper modules.
- **Complexity reduction:** 3.4
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-036: excessive_exports — [simplify_later]
- **Target:** `v3/quality/__init__.py`
- **Description:** Module exports 19 public symbols. Reduce to core API surface.
- **Complexity reduction:** 2.85
- **Risk:** medium
- **Reason:** Large __all__ inflates API surface. Audit which exports are actually consumed.

### SIMPLIFY-013: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_kernel_invariants.py`
- **Description:** Module exceeds 600 lines (713 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.8
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-014: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_orchestration_policy.py`
- **Description:** Module exceeds 600 lines (665 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.7
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-015: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_memory_runtime_finalization.py`
- **Description:** Module exceeds 600 lines (1016 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.65
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-016: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_repo_intake.py`
- **Description:** Module exceeds 600 lines (748 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.65
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-017: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_evaluation_harness.py`
- **Description:** Module exceeds 600 lines (877 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.65
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-018: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_semantic_memory_index.py`
- **Description:** Module exceeds 600 lines (695 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.54
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-019: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_memory_compaction.py`
- **Description:** Module exceeds 600 lines (1074 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.53
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-020: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_skill_evolution_plane.py`
- **Description:** Module exceeds 600 lines (806 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.47
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-021: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_truth_linked_recall.py`
- **Description:** Module exceeds 600 lines (684 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.42
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-040: redundant_report — [simplify_later]
- **Target:** `v3/cli/systemkernel.py`
- **Description:** Module generates 6 report functions. Audit for overlap in generated reports.
- **Complexity reduction:** 2.4
- **Risk:** low
- **Reason:** Multiple report generators may produce overlapping output. Consolidate where safe.

### SIMPLIFY-042: redundant_report — [simplify_later]
- **Target:** `v3/tests/test_developer_cli.py`
- **Description:** Module generates 6 report functions. Audit for overlap in generated reports.
- **Complexity reduction:** 2.4
- **Risk:** low
- **Reason:** Multiple report generators may produce overlapping output. Consolidate where safe.

### SIMPLIFY-043: redundant_report — [simplify_later]
- **Target:** `v3/tests/test_golden_path.py`
- **Description:** Module generates 6 report functions. Audit for overlap in generated reports.
- **Complexity reduction:** 2.4
- **Risk:** low
- **Reason:** Multiple report generators may produce overlapping output. Consolidate where safe.

### SIMPLIFY-044: redundant_report — [simplify_later]
- **Target:** `v3/tests/test_v4_simplification_audit.py`
- **Description:** Module generates 6 report functions. Audit for overlap in generated reports.
- **Complexity reduction:** 2.4
- **Risk:** low
- **Reason:** Multiple report generators may produce overlapping output. Consolidate where safe.

### SIMPLIFY-022: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_v4_productization_ops.py`
- **Description:** Module exceeds 600 lines (665 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.28
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-023: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_episodic_memory_store.py`
- **Description:** Module exceeds 600 lines (826 LOC). Consider extracting helper modules.
- **Complexity reduction:** 2.24
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-041: redundant_report — [simplify_later]
- **Target:** `v3/tests/test_context_engineering_plane.py`
- **Description:** Module generates 5 report functions. Audit for overlap in generated reports.
- **Complexity reduction:** 2.0
- **Risk:** low
- **Reason:** Multiple report generators may produce overlapping output. Consolidate where safe.

### SIMPLIFY-045: docs_overlap — [simplify_later]
- **Target:** `Docs/ + v3/exports/*.md`
- **Description:** Documentation exists in both Docs/ (26) and v3/exports/ (59 .md files). Consider consolidating.
- **Complexity reduction:** 2.0
- **Risk:** low
- **Reason:** Two documentation directories create maintenance burden. Consolidate into one location.

### SIMPLIFY-024: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_observability_graph.py`
- **Description:** Module exceeds 600 lines (683 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.94
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-025: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_complexity_budget.py`
- **Description:** Module exceeds 600 lines (932 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.86
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-026: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_agent_worker_plane.py`
- **Description:** Module exceeds 600 lines (985 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.79
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-027: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_memory_boundary.py`
- **Description:** Module exceeds 600 lines (707 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.78
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-028: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_workspace_context_plane.py`
- **Description:** Module exceeds 600 lines (810 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.57
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-029: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_developer_cli.py`
- **Description:** Module exceeds 600 lines (616 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.4
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-030: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_context_engineering_plane.py`
- **Description:** Module exceeds 600 lines (687 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.16
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-031: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_external_evidence.py`
- **Description:** Module exceeds 600 lines (684 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.16
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-032: oversized_module — [simplify_later]
- **Target:** `v3/tests/test_memory_intelligence_plane.py`
- **Description:** Module exceeds 600 lines (609 LOC). Consider extracting helper modules.
- **Complexity reduction:** 1.03
- **Risk:** medium
- **Reason:** Large modules increase cognitive load. Safe to split if public API preserved.

### SIMPLIFY-046: fixture_overlap — [simplify_later]
- **Target:** `v3/tests/fixtures/`
- **Description:** 6 JSON test fixtures. Audit for unused or overlapping fixture data.
- **Complexity reduction:** 1.0
- **Risk:** low
- **Reason:** Test fixtures may accumulate cruft. Safe to audit and prune unused ones.

### SIMPLIFY-047: no_action — [keep]
- **Target:** `v3/tests/__init__.py`
- **Description:** Module v3/tests/__init__.py is already lean (3 LOC, complexity 0.01). No simplification needed.
- **Complexity reduction:** 0.0
- **Risk:** low
- **Reason:** Module is already minimal. No action recommended.

## Appendix: Audit Target Directories

- `v3/external/`
- `v3/evals/`
- `v3/ops/`
- `v3/release/`
- `v3/cli/`
- `v3/tests/`
- `v3/quality/`