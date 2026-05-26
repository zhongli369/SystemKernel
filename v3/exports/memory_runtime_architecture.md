# Memory Runtime Architecture

## Phase 4D-6 — Full 4D Memory Subsystem Architecture

### Overview

The Memory Runtime is a unified facade over the complete memory pipeline.
It ties together all Phase 4D modules into a single, callable entry point.

### Pipeline

```
Events (source of truth)
  |
  v
MemoryCandidate (projection from events, Phase 4D-1)
  |
  v
EpisodicMemoryStore (append-only JSONL, Phase 4D-2)
  |
  +-- SemanticMemoryIndex (inverted token index, Phase 4D-3)
  |     |
  |     v
  |   MemoryRetrievalRuntime (structured query)
  |     |
  |     v
  |   TruthLinkedRecallRuntime (provenance-attached recall, Phase 4D-4)
  |
  +-- MemoryCompactor (deterministic compaction, Phase 4D-5)
  |     |
  |     v
  |   CompactionResult (compacted projection)
  |
  v
MemoryRuntime (unified facade, Phase 4D-6)
  |
  v
MemorySystemReport (unified integrity, Phase 4D-6)
```

### Boundary Contract

The memory subsystem communicates with the kernel through three contract modules
only:
- `v3/kernel/memory_contract.py` — Write/Read request/result types
- `v3/kernel/memory_candidate.py` — Candidate projection from events
- `v3/kernel/memory_gateway.py` — Gateway with pluggable adapter

All memory implementation lives in `v3/memory/`, outside `v3/kernel/`.
The kernel NEVER imports from `v3/memory/`.

### Why Memory Is External

1. Kernel purity: the kernel must be deterministic without any memory
2. Removability: deleting `v3/memory/` must have zero kernel impact
3. Testability: memory can be tested independently of kernel execution
4. Replaceability: memory backend can be swapped without touching kernel

### Why Memory Is Removable

All memory operations are optional. The kernel runs with or without memory.
Memory writes are advisory (write failures do not affect execution).
Memory reads are advisory (empty results are always valid).

### Why Events Remain Source of Truth

1. Candidates are a pure projection of events (no new information created)
2. Episodic records reference event IDs and execution IDs
3. Every record has a traceable source_hash linking to graph + events
4. Compacted records preserve all source hashes
5. Recall provenance chains trace back to events
6. Memory is never queried to make decisions — it provides context only

### MemoryRuntime API

```python
from v3.memory.runtime import MemoryRuntime

# Construction
runtime = MemoryRuntime.from_paths(
    store_path="data/episodes.jsonl",
    compaction_path="data/compacted.json",
)

# Full pipeline
events = make_event(...)
result = runtime.ingest_events(events)

# Individual stages
runtime.write_candidates(candidates)
runtime.build_index()
runtime.retrieve("query text")
runtime.recall("query text")
runtime.compact(policy=CompactionPolicy())

# Verification
runtime.verify_all()        # Full system report
runtime.export_summary()    # JSON summary
```

### Configuration

```python
MemoryRuntimeConfig(
    store_path="...",        # Episodic JSONL path
    compaction_path="...",   # Compaction projection path
    enable_index=True,       # Build semantic index
    enable_recall=True,      # Enable truth-linked recall
    enable_compaction=True,  # Run compaction
    compaction_policy=None,  # Custom CompactionPolicy
    deterministic=True,      # Enforce deterministic output
)
```

### Integrity Guarantees

| Property | Guarantee |
|----------|-----------|
| Determinism | Same events + same config → same runtime_hash |
| Idempotency | Replaying same events → 0 writes (duplicate detection) |
| Provenance | Every recall result trace-linkable to source events |
| Projection-only | No memory output is a truth source |
| Removability | Delete v3/memory/ → kernel unchanged |
| Zero LLM | No AI imports anywhere in the pipeline |
| Stdlib only | No external services, vector DBs, or frameworks |
