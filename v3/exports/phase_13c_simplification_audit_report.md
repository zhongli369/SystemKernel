# Phase 13C — v4 Simplification / API Surface Reduction Audit

**Date:** 2026-05-27
**Status:** COMPLETE

## Audit Results

- Modules analyzed: 90
- Total LOC in audit scope: 45365
- Total public API functions: 428
- Total public exports: 475

## Risk Assessment

- Ability+10% Complexity+300% risk: **MEDIUM**
- Safe simplification candidates: 0
- Deferred candidates: 46
- Do not touch: 0

## Top Opportunities

1. **[oversized_module]** Module exceeds 600 lines (3076 LOC). Consider extracting helper modules. — risk=medium, action=simplify_later
2. **[oversized_module]** Module exceeds 600 lines (851 LOC). Consider extracting helper modules. — risk=medium, action=simplify_later
3. **[excessive_exports]** Module exports 347 public symbols. Reduce to core API surface. — risk=medium, action=simplify_later
4. **[cli_surface_sprawl]** CLI module has 57 subcommands. Consider grouping or removing rarely used commands. — risk=medium, action=simplify_later
5. **[duplicated_policy_logic]** Multiple policy modules detected (7 files). Consider consolidating shared policy logic. — risk=medium, action=simplify_later
6. **[oversized_module]** Module exceeds 600 lines (735 LOC). Consider extracting helper modules. — risk=medium, action=simplify_later
7. **[excessive_exports]** Module exports 52 public symbols. Reduce to core API surface. — risk=medium, action=simplify_later
8. **[oversized_module]** Module exceeds 600 lines (686 LOC). Consider extracting helper modules. — risk=medium, action=simplify_later
9. **[oversized_module]** Module exceeds 600 lines (680 LOC). Consider extracting helper modules. — risk=medium, action=simplify_later
10. **[oversized_module]** Module exceeds 600 lines (644 LOC). Consider extracting helper modules. — risk=medium, action=simplify_later

## Recommendation

**proceed_to_ecc_intake** — Risk is medium. Proceed with caution; consider simplification before intake.
simplify_first: MAYBE (defer opportunities exist)
stop: NO