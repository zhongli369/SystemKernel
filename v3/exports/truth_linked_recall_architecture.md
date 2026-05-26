# Truth-Linked Recall Architecture — Phase 4D-4

## Overview

Truth-Linked Recall adds a full provenance chain to every memory retrieval
result. Each RecallResult carries a RecallProvenance that links back through
the entire memory stack to source events in the kernel.

## Retrieval vs Recall

| Aspect | Retrieval (4D-3) | Recall (4D-4) |
|--------|-----------------|---------------|
| Returns | Scored search results | Scored results + provenance |
| Traceability | Partial (record_hash) | Full chain to events |
| Audit trail | No | Yes — every field verifiable |
| Explanation | Token-level | Token + source linkage |
| Integrity check | Index-level | Per-result + per-bundle |
| Backend label | "semantic" | "recall" |

## Provenance Chain

```
RecallResult
  └──→ RecallProvenance
         ├── memory_id       → EpisodicMemoryRecord
         ├── record_hash     → content-addressed record identity
         ├── source_hash     → links record to graph + events + execution
         ├── execution_id    → kernel execution that produced the record
         ├── graph_hash      → RuntimeGraph at write time
         ├── event_ids       → source events (TRUTH SOURCE)
         ├── candidate_id    → original MemoryCandidate
         ├── candidate_type  → from CandidateType enum
         ├── trace_valid     → all links verified intact
         └── provenance_hash → deterministic hash of above fields
```

## Why Recall is Projection Only

1. **Rebuildable** — all provenance data comes from EpisodicMemoryRecord
2. **No new data** — every provenance field is extracted, not generated
3. **No truth** — provenance references records → events (truth source)
4. **Deterministic** — same record → same provenance → same hash
5. **Removable** — delete recall runtime, kernel behavior unchanged

## Why Events Remain Truth Source

Every provenance record carries a `source_hash` computed from:
  SHA-256(execution_id + graph_hash + event_ids)

This guarantees:
  - source_hash is derivable from the event stream only
  - source_hash can be independently verified
  - events are the ONLY path to reconstruct source_hash
  - memory/recall are downstream projections, never truth sources

## Integrity Model

Two levels of integrity:
  1. **Per-result**: `verify_provenance(result)` checks all links
  2. **Per-bundle**: `verify_bundle(bundle)` checks all results + hash

Integrity status: `valid` | `partial` | `invalid`
