# MT-04: L3 Context Tiering — 7/10 → 8/10

**Status**: PLANNING | **Date**: 2026-06-02 | **Target**: 8/10

## Current State (7/10)

| Asset | Status |
|-------|--------|
| `tier_policy.py` | Tier definitions, TTL rules, importance scoring, compaction logic |
| `tier_store.py` | FileTierStore — JSONL append-only, L1/L2/L3 |
| `tier_retrieval.py` | Progressive loading, Jaccard similarity ranking |
| All deterministic | No LLM, no vector DB, stdlib only |
| Tests | No dedicated test_tiering — old memory tests deleted with v3/memory |

## Gaps to 8/10

### G1: No execution pipeline integration
The tier store is standalone. It does not receive events from the execution
pipeline. Working memory is never populated during execution.

**Fix**: Hook `FileTierStore.save()` into the execution lifecycle via the
existing EventStore → inject pattern. On stage completion, persist an
episodic entry.

### G2: No token/context budget
Progressive loading has no cap — can load unbounded context into the
working window.

**Fix**: Add `max_tokens` parameter to `progressive_load()` and
`retrieve_context()`. Default: 4096 tokens (~8K chars). Truncate lowest
scoring entries when budget exceeded.

### G3: No observability
No Prometheus metrics for tier hit/miss rate, compaction frequency, or
retrieval latency.

**Fix**: Add 3 metrics:
- `context_tier_retrieval_latency_seconds` (histogram)
- `context_tier_hits_total` (counter, labels: tier)
- `context_tier_compaction_runs_total` (counter)

### G4: No dedicated tests
Old `test_episodic_memory_store.py` and `test_semantic_memory_index.py`
were deleted with v3/memory. No replacement tests exist.

**Fix**: Create `v3/tests/test_context_tiering.py` covering:
- TierEntry creation and freezing
- FileTierStore save/load/expire/compact
- Progressive load with budget cap
- Token counting
- Importance score determinism

### G5: No compaction scheduling
`compact()` exists but must be called manually. Episodic entries never
auto-promote to semantic.

**Fix**: Add `auto_compact` flag to `FileTierStore`. On save, if episodic
entries for an entity exceed threshold, trigger compaction inline.

## Implementation Order

1. G4 (tests) — write first, establish baseline
2. G2 (token budget) — add cap to retrieval
3. G1 (execution hook) — wire into pipeline
4. G3 (metrics) — add observability
5. G5 (auto-compaction) — schedule on save

## Constraints

- No LLM, no vector DB, stdlib only
- No v3/kernel/ modification (Core Freeze)
- No api.py modification (FROZEN API)
- No new CapabilityType
- All changes in v3/external/context_tiering/ only
