# Phase 13D — CLI Surface Compression

**Date:** 2026-05-27 | **Status:** COMPLETE

---

## Summary

Split the 3076-LOC monolithic `v3/cli/systemkernel.py` into 6 files using direct
module extraction. All CLI behavior preserved. Backward compatibility
maintained — `__init__.py` and `test_v4_productization_ops.py` imports still
work unchanged.

## Results

| Metric | Before | After |
|--------|--------|-------|
| Entrypoint LOC | 3076 | 541 |
| Entrypoint reduction | — | **82.4%** |
| Total files | 1 | 6 |
| Max single-file LOC | 3076 | 1078 |
| Import compatibility | — | 100% |

## File Structure

```
v3/cli/
  systemkernel.py          541 LOC  Entrypoint (build_parser + main + re-exports)
  _helpers.py              194 LOC  Shared path resolution + utilities
  core_commands.py         291 LOC  status, quality, memory, reports, doctor
  external_commands.py     599 LOC  intake, context-pack, usage
  intelligence_commands.py 1078 LOC context-plane, memory-intel, workspace,
                                   agent-worker, skill-evolution, orchestrate
  eval_ops_commands.py     442 LOC  capability, eval, v4
```

## Test Results

- **test_developer_cli.py:** 24/26 pass (2 pre-existing failures: v3/memory/ deleted from working tree)
- **test_v4_productization_ops.py:** 44/44 pass
- **Doctor:** 19/19 HEALTH OK
- **CLI smoke checks:** status, v4 status, capability summary, eval run, orchestrate policies, context-plane plan — all pass

## Key Decisions

1. **Direct module extraction** — no CLI framework, no plugin loading, no dynamic dispatch
2. **Thin entrypoint** — `systemkernel.py` re-exports all `cmd_*` functions for backward compatibility
3. **Domain grouping** — modules grouped by function domain (core, external, intelligence, eval/ops)
4. **Shared helpers** — `_helpers.py` eliminates duplicate utility definitions

## Next Phase

Phase 14 — Real Provider Trial (post-compression, complexity risk is now lower).
