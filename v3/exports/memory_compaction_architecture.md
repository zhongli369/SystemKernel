# Memory Compaction Architecture

## Phase 4D-5 — Deterministic Memory Compaction

### Why Compaction Is Not Summarization

| Aspect | Summarization | Compaction |
|--------|---------------|------------|
| Uses LLM | Yes | No |
| Generates new text | Yes | No |
| Loses provenance | Often | Never |
| Alters truth | Possibly | Never |
| Deterministic | No | Yes |
| Removable | N/A | Yes |

Compaction never generates new semantic content. It only reorganizes
existing records by:
- Detecting duplicates via content fingerprinting
- Merging duplicate sources into single records (with all source hashes preserved)
- Archiving low-importance records
- Grouping by type, tag, execution, or content hash

### Compaction as Projection / Optimization

```
Events (source of truth)
  |
  v
EpisodicMemoryRecord (append-only JSONL)
  |
  +-- SemanticMemoryIndex (built from records)
  |     |
  |     v
  |   MemoryRetrievalRuntime (query)
  |
  +-- MemoryCompactor.compact()
  |     |
  |     v
  |   CompactionResult (in-memory, deterministic)
  |     |
  |     v
  |   Compaction Projection (optional JSON file)
  |     |
  |     v
  |   MemoryRetrievalRuntime(use_compacted=True)
  |
  v
TruthLinkedRecallRuntime (always from store)
```

The compaction projection is an optimization layer. Deleting it has zero
impact on retrieval (falls back to raw store) and zero impact on the
kernel (memory boundary is strictly read-only).

### Provenance Preservation

Every compacted record retains:

| Field | Purpose |
|-------|---------|
| source_memory_ids | Link back to original episodic records |
| source_record_hashes | Content-addressed record verification |
| source_hashes | Traceability to graph + events |
| execution_ids | Which kernel execution produced each record |
| graph_hashes | Hash of RuntimeGraph at write time |

This means:
- Every compacted record is traceable back to source events
- No provenance is lost during compaction
- Compaction is a pure projection — never a truth source

### Original Records Remain Truth-Linked

The original episodic JSONL is NEVER modified by compaction. Compaction
reads from the store but writes to a separate projection file. The
original records retain their:
- Source hashes (linking to events)
- Record hashes (content-addressed integrity)
- Execution IDs (tracing to kernel runs)
- Graph hashes (linking to runtime state)

### Determinism Guarantees

| Operation | Guarantee |
|-----------|-----------|
| Content fingerprint | Same content + type + tags → same fingerprint |
| Compacted hash | Same compacted record → same hash |
| Result hash | Same input + policy → same result_hash |
| Grouping | Same key function → same groups |
| Sorting | Deterministic by compacted_id (or configured sort key) |
| Duplicate handling | Deterministic strategy (keep_first or merge_sources) |
| Archive | Deterministic by importance threshold |

### CompactionPolicy Configuration

```python
CompactionPolicy(
    min_importance=1,           # Records below this are archived
    duplicate_strategy="keep_first",  # or "merge_sources"
    group_by="candidate_type",  # or tag/execution_id/content_hash
    max_records_per_group=50,   # Cap output per group
    archive_low_importance=True, # Archive or skip low-importance
    deterministic_sort="",      # Sort key for output
)
```

### Integrity Checks

The compaction integrity checker verifies:
1. All compacted records reference source_record_hashes
2. All source records accounted for or explicitly archived
3. No provenance loss (source_hashes, execution_ids, graph_hashes)
4. result_hash is stable
5. Compaction is projection only (original records unchanged)
6. Duplicate handling is deterministic
7. No banned imports (stdlib only)
8. Compacted hashes are stable

### File Layout

```
v3/memory/
  compaction.py              — Core compaction engine
  compaction_integrity.py    — Integrity checks
  episodic_store.py          — Original episodic store (unchanged)
  retrieval.py               — Retrieval with optional compacted support
  recall.py                  — Truth-linked recall (always from store)

v3/exports/
  memory_compaction_architecture.md           — This file
  memory_compaction_integrity_report.json     — Integrity report
  compacted_memory_projection.json            — Compaction projection
```

### Summary

Events -> Episodic Records -> [Compaction Projection] -> Index -> Retrieval/Recall

Compaction is a read-only optimization layer. It preserves all provenance,
uses zero LLM calls, and is fully deterministic. The original events remain
the sole source of truth.
