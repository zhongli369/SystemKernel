# Episodic Memory Architecture — Phase 4D-2

## Overview

Episodic Memory Store is a deterministic, append-only JSONL file store that lives
**outside** the kernel boundary (`v3/memory/`). It consumes `MemoryWriteRequest`
objects projected by the kernel's `project_candidates()` function and stores them
as `EpisodicMemoryRecord` objects.

## Data Flow

```
ExecutionEngine
  │
  ├──→ ExecutionEvent stream (source of truth)
  │      │
  │      ├──→ build_graph()     → RuntimeGraph
  │      ├──→ compute_metrics() → RuntimeMetrics
  │      └──→ compute_telemetry() → InvariantTelemetry
  │             │
  │             └──→ project_candidates(events, graph, metrics, telemetry)
  │                    │
  │                    ▼
  │              Tuple[MemoryCandidate, ...]
  │                    │
  │                    ▼  (crosses kernel boundary)
  │              MemoryGateway.write_candidates()
  │                    │
  │                    ▼
  │              EpisodicMemoryAdapter.write_candidates()
  │                    │
  │                    ▼
  │              EpisodicMemoryStore.append(MemoryWriteRequest)
  │                    │
  │                    ▼
  │              EpisodicMemoryRecord → JSONL file
  │
  └──→ ExecutionResult (unchanged — memory is non-interfering)
```

## Kernel Boundary

| Layer | Location | What it does |
|-------|----------|--------------|
| Contract | `v3/kernel/memory_contract.py` | Typed protocol: Request/Result types |
| Candidates | `v3/kernel/memory_candidate.py` | Pure projection: events → candidates |
| Gateway | `v3/kernel/memory_gateway.py` | Routing: kernel ↔ adapter |
| **— boundary —** | | |
| Adapter | `v3/memory/episodic_adapter.py` | Implements gateway protocol |
| Store | `v3/memory/episodic_store.py` | Append-only JSONL persistence |
| Integrity | `v3/memory/integrity.py` | Structural validation |

## Candidate → Write Request → Episodic Record

```
MemoryCandidate            MemoryWriteRequest        EpisodicMemoryRecord
───────────────            ──────────────────        ────────────────────
candidate_id       →       request_id          →     candidate_id
execution_id       →       execution_id        →     execution_id
candidate_type     →       candidate_type      →     candidate_type
content            →       content             →     content
priority           →       priority            →     importance
context            →       context             →     event_ids, graph_hash
                                                  + memory_id (deterministic)
                                                  + tags (derived from type + content)
                                                  + source_hash (traceability link)
                                                  + record_hash (content-addressed)
                                                  + created_at
```

## Why Episodic Memory is External

1. **Removability** — delete `v3/memory/` and kernel tests still pass with purity_score=100
2. **No kernel dependency** — store uses only `memory_contract.py` types (no engine, no events, no graph)
3. **Independence** — store can be swapped for mem0/graphiti in the future without touching kernel
4. **LLM isolation** — memory module MAY use LLM for write-time extraction (future); kernel NEVER uses LLM

## Why It Does NOT Violate PURE KERNEL

| Invariant | Status |
|-----------|--------|
| Zero LLM imports in kernel/ | PASS — 0 violations across 19 files |
| Memory is removable | PASS — kernel runs identically with memory_gateway=None |
| Events are source of truth | PASS — all records have source_hash linking to events |
| Memory is advisory | PASS — write failures don't affect execution |
| Deterministic records | PASS — same candidate → same record_hash |
| Append-only | PASS — records never modified, only appended |
| No truth source | PASS — integrity check confirms memory_not_truth_source |
| Contract boundary | PASS — adapter uses MemoryWriteRequest/Result types |

## Storage Format

One JSON object per line in `episodes.jsonl`:

```json
{"memory_id":"abc123...","candidate_id":"def456...","execution_id":"exec-001",...}
```

- Each record is a single JSON line
- Append-only: new records go to end of file
- Immutable: records are never modified
- Idempotent: same candidate_id replayed → no duplicate
- Source-traced: every record has source_hash linking to events + graph

## Integrity Checks

10 structural checks (no AI, no heuristics):
1. Every record has execution_id
2. Every record has source_hash
3. All record_hashes are valid (deterministic recomputation)
4. No duplicate record_hashes
5. All records JSON serializable
6. Append-only ordering valid
7. All records trace-linked (source_hash correct)
8. Memory is not truth source (all records have upstream source)
9. All records have candidate_id
10. All records have content
