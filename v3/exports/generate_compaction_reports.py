"""Generate Phase 4D-5 compaction export reports."""
import sys, os, json, hashlib
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _root)

from v3.kernel.memory_contract import MemoryWriteRequest, MemoryReadRequest
from v3.memory.episodic_store import (
    EpisodicMemoryRecord, EpisodicMemoryStore,
    compute_record_hash, compute_source_hash, derive_tags,
)
from v3.memory.compaction import (
    CompactionPolicy, CompactedMemoryRecord, CompactionResult,
    MemoryCompactor, compute_result_hash,
)
from v3.memory.compaction_integrity import (
    check_compaction_integrity, generate_compaction_integrity_report_json,
)

# ── Build sample records ──────────────────────────────────────────────

def _make_record(memory_id, candidate_id, execution_id, graph_hash,
                 candidate_type, content, importance=1,
                 event_ids=("ev-1", "ev-2")):
    source_hash = compute_source_hash(execution_id, graph_hash, event_ids)
    tags = derive_tags(candidate_type, content)
    record = EpisodicMemoryRecord(
        memory_id=memory_id, candidate_id=candidate_id,
        execution_id=execution_id, event_ids=event_ids,
        graph_hash=graph_hash, candidate_type=candidate_type,
        content=content, importance=importance, tags=tags,
        created_at="2025-05-25T10:00:00Z", source_hash=source_hash,
    )
    rhash = compute_record_hash(record)
    return EpisodicMemoryRecord(
        memory_id=record.memory_id, candidate_id=record.candidate_id,
        execution_id=record.execution_id, event_ids=record.event_ids,
        graph_hash=record.graph_hash, candidate_type=record.candidate_type,
        content=record.content, importance=record.importance,
        tags=record.tags, created_at=record.created_at,
        source_hash=record.source_hash, record_hash=rhash,
    )

records = (
    _make_record("mem-001", "cid-001", "exec-A", "gh-aaa", "execution_summary",
                 {"status": "completed", "duration_ms": 500}, importance=2),
    _make_record("mem-002", "cid-002", "exec-A", "gh-aaa", "stage_result",
                 {"stage_name": "build", "status": "passed"}, importance=1),
    _make_record("mem-003", "cid-003", "exec-A", "gh-aaa", "stage_result",
                 {"stage_name": "test", "status": "passed"}, importance=1),
    _make_record("mem-004", "cid-004", "exec-A", "gh-aaa", "error_detail",
                 {"error": "minor warning", "stage_name": "lint"}, importance=1),
    _make_record("mem-005", "cid-005", "exec-B", "gh-bbb", "stage_result",
                 {"stage_name": "build", "status": "passed"}, importance=1),
    _make_record("mem-006", "cid-006", "exec-B", "gh-bbb", "execution_summary",
                 {"status": "completed", "duration_ms": 500}, importance=2),
    _make_record("mem-007", "cid-007", "exec-C", "gh-ccc", "stage_result",
                 {"stage_name": "deploy", "status": "passed"}, importance=1),
    _make_record("mem-008", "cid-008", "exec-C", "gh-ccc", "background",
                 {"info": "cache warmed"}, importance=0),
    _make_record("mem-009", "cid-009", "exec-C", "gh-ccc", "background",
                 {"info": "heartbeat check"}, importance=0),
    _make_record("mem-010", "cid-010", "exec-B", "gh-bbb", "error_detail",
                 {"error": "failed assertion", "stage_name": "build"}, importance=2),
)

# ── Run compaction ─────────────────────────────────────────────────────

exports_dir = os.path.dirname(os.path.abspath(__file__))

policy = CompactionPolicy(
    min_importance=1,
    duplicate_strategy="merge_sources",
    group_by="candidate_type",
    archive_low_importance=True,
)
compactor = MemoryCompactor()
result = compactor.compact(records, policy)

# ── 1. Compacted memory projection ─────────────────────────────────────

proj_path = os.path.join(exports_dir, "compacted_memory_projection.json")
compactor.write_projection(proj_path, result, policy)
print(f"[OK] compacted_memory_projection.json written")

# ── 2. Compaction integrity report ─────────────────────────────────────

report_path = os.path.join(exports_dir, "memory_compaction_integrity_report.json")
report = generate_compaction_integrity_report_json(result, records, policy, report_path)
print(f"[OK] memory_compaction_integrity_report.json written (valid={report.valid})")

# ── 3. Architecture markdown ───────────────────────────────────────────

md_path = os.path.join(exports_dir, "memory_compaction_architecture.md")
md_content = """# Memory Compaction Architecture

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
"""

with open(md_path, "w", encoding="utf-8") as f:
    f.write(md_content)
print(f"[OK] memory_compaction_architecture.md written")

# ── Stats ──────────────────────────────────────────────────────────────

print(f"\nCompaction stats:")
print(f"  Input:   {result.input_count}")
print(f"  Output:  {result.output_count}")
print(f"  Dups:    {result.duplicate_count}")
print(f"  Archived:{result.archived_count}")
print(f"  Hash:    {result.result_hash}")
print(f"  Integrity: {report.valid}")
print(f"\nAll reports generated.")
