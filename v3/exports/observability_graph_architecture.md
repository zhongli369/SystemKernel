# Observability Graph Architecture — Phase 4C

## Objective

Build a **deterministic runtime observability projection** from the event
stream — without introducing Memory, LLM, or external visualization dependencies.

Phase 4C produces three pure-functional projections:

```
Events (source of truth) → RuntimeGraph → Metrics → Telemetry
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     EVENT STREAM (immutable)                     │
│              Tuple[ExecutionEvent, ...]                          │
│              Source of truth. Append-only.                       │
└────────────┬───────────────┬────────────────┬───────────────────┘
             │               │                │
             ▼               ▼                ▼
     ┌──────────────┐ ┌─────────────┐ ┌──────────────┐
     │ build_graph()│ │compute_     │ │compute_      │
     │              │ │metrics()    │ │telemetry()   │
     └──────┬───────┘ └──────┬──────┘ └──────┬───────┘
            │                │                │
            ▼                ▼                ▼
     ┌──────────────┐ ┌─────────────┐ ┌──────────────┐
     │ RuntimeGraph │ │RuntimeMetrics│ │Invariant     │
     │              │ │              │ │Telemetry     │
     │ - nodes      │ │ - counts     │ │ - purity     │
     │ - edges      │ │ - durations  │ │ - invariants │
     │ - graph_hash │ │ - status     │ │ - score      │
     └──────────────┘ └─────────────┘ └──────────────┘
```

### Data Flow

1. **Events** are the immutable source of truth
2. **RuntimeGraph** is a structural projection (nodes + edges)
3. **Metrics** is a numeric aggregation projection
4. **Telemetry** is an invariant health projection

All three projections are:
- **Pure functions** — same inputs → same outputs, always
- **Deterministic** — no randomness, no wall clock dependency
- **Reconstructable** — can be rebuilt from events alone
- **Zero LLM** — no AI/ML imports anywhere in the pipeline

## Why This Is NOT Memory

| Property | Memory | Observability Graph |
|----------|--------|---------------------|
| Stores learned data | Yes | No |
| Accumulates across runs | Yes | No |
| Requires external DB/API | Often | Never |
| Can influence decisions | Yes | No |
| Is source of truth | Sometimes | **Never** |
| Reconstructable from events | No | **Yes** |
| Lives in kernel/ | No | **Yes** (but pure function) |

The observability graph is a **read-only projection**, not a memory system.
It derives entirely from events and holds no state across runs.

## Why This Does NOT Break PURE KERNEL

1. **Zero LLM imports** — no `openai`, `anthropic`, `langchain`, `crewai`, `mem0`, `graphiti`
2. **Pure functions only** — no side effects, no file I/O in graph/metrics/telemetry
3. **Events remain source of truth** — graph/metrics/telemetry are projections, not authorities
4. **Checkpoints are snapshots** — `is_truth_source: false` on all checkpoint nodes
5. **No memory dependency** — `no_memory_dependency: true` in telemetry
6. **Execution model unchanged** — single loop, no hidden re-execution
7. **Deterministic graph_hash** — same events → same hash, always

## Module Dependencies

```
observability_graph.py  → v3.kernel.events (ExecutionEvent, EventType)
telemetry.py            → v3.kernel.events + v3.kernel.observability_graph
metrics.py              → v3.kernel.events
replay.py (updated)     → observability_graph + telemetry + metrics
```

No circular dependencies. All imports flow inward toward `events.py` (leaf module).

## Test Coverage

12 tests in `test_observability_graph.py`:
- Graph construction and determinism (4 tests)
- Telemetry purity scoring (1 test)
- Metrics aggregation (1 test)
- Error/retry/checkpoint node types (3 tests)
- Replay-to-* projection functions (1 test)
- LLM boundary enforcement (1 test)
- Integration with Phase 4A/4B (1 test)

## Purity Verdict

```
purity_score = 100/100
verdict = PURE KERNEL
```
