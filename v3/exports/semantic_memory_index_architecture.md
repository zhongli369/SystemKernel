# Semantic Memory Index Architecture — Phase 4D-3

## Overview

Semantic Memory Index is a **deterministic lexical semantic index** built on top
of EpisodicMemoryRecord objects. Despite the name "semantic," this index uses
**zero embeddings, zero vector DBs, and zero LLM calls**. "Semantic" here refers
to content-aware token-based retrieval as opposed to raw key-value lookup.

## Why Deterministic Lexical, Not Embedding/Vector

| Property | Lexical Index (this phase) | Vector/Embedding (future) |
|----------|---------------------------|--------------------------|
| Deterministic | YES — same input → same output | NO — embedding models drift |
| Reproducible | YES — rebuild from JSONL anytime | Requires model version pinning |
| Removable | YES — delete and rebuild | YES — but model costs $ |
| Zero external deps | YES — stdlib only | NO — needs model/SDK |
| Query stability | YES — exact token matching | Approximate — top-k varies |
| Debuggable | YES — `explain()` shows all matches | NO — black-box similarity |

The lexical approach is the correct foundation. A future phase MAY add optional
embedding-based retrieval as a pluggable backend, but the lexical index remains
the deterministic baseline.

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
  │              MemoryCandidate (tuple)
  │                    │
  │                    ▼  (crosses kernel boundary)
  │              MemoryGateway.write_candidates()
  │                    │
  │                    ▼
  │              EpisodicMemoryAdapter.write_candidates()
  │                    │
  │                    ▼
  │              EpisodicMemoryStore.append()
  │                    │
  │                    ▼
  │              EpisodicMemoryRecord → JSONL file
  │                    │
  │                    ▼  (read path: index build)
  │              SemanticMemoryIndex.build(records)
  │                    │
  │                    ▼
  │              Inverted index: token → [memory_ids]
  │                    │
  │                    ▼  (query path)
  │              MemoryRetrievalRuntime.read_request()
  │                    │
  │                    ▼
  │              MemoryReadResult
```

## Relationship Chain

```
Events → MemoryCandidate → EpisodicMemoryRecord → SemanticMemoryIndex → MemoryRetrievalRuntime
  │            │                    │                      │                      │
  │            │                    │                      │                      │
  TRUTH      projection         storage                index               retrieval
  SOURCE     (derived)          (append-only)          (projection)        (query layer)
```

Each layer is a **projection** of the layer above it. The Events layer is the
sole truth source. All downstream layers can be reconstructed from events alone.

## Why Index is Projection Only

1. **Rebuildable** — delete the index, rebuild from JSONL → identical index hash
2. **No new data** — every token, reference, and hash derives from records
3. **No truth** — index entries reference records; records reference events
4. **Deterministic** — same records → same index → same search results
5. **Removable** — deleting the index has zero effect on kernel execution

## Scoring Model

```
score = Σ(token_match / query_token_count) + Σ(tag_boost)

where:
  token_match = 1.0 / N  (N = number of query tokens)
  tag_boost   = 0.2      (per tag matching a query token)
  tie-break   = record_hash ascending (deterministic total order)
```

Filters applied BEFORE scoring:
- `execution_id` — exact match
- `candidate_type` — exact match
- `tag` — exact match
- `min_importance` — >= threshold

## Tokenization

```
text → [^a-zA-Z0-9_一-鿿]+ split → lowercase → filter(len < 2) → tuple
```

- Deterministic: same input always → same tokens
- CJK support: preserves Chinese characters (U+4E00–U+9FFF)
- No stopword removal: keeps the process simple and deterministic
- No stemming/lemmatization: avoids language-specific dependencies

## Integrity Guarantees

| # | Check | Guarantee |
|---|-------|-----------|
| 1 | Builds from episodic records | No external data injection |
| 2 | Valid memory_ids | Every index ref → existing record |
| 3 | Valid record_hashes | Every hash → matching record content |
| 4 | Deterministic ordering | Same query → same results always |
| 5 | Stable index hash | Rebuild from same records → same hash |
| 6 | Projection only | All data derivable from store |
| 7 | No truth source violation | All records have source_hash → events |

## Kernel Boundary

| Layer | Location | What it does |
|-------|----------|--------------|
| Contract | `v3/kernel/memory_contract.py` | Typed protocol: Request/Result |
| Gateway | `v3/kernel/memory_gateway.py` | Routing: kernel ↔ adapter |
| **— boundary —** | | |
| Adapter | `v3/memory/episodic_adapter.py` | Gateway protocol + optional retrieval |
| Store | `v3/memory/episodic_store.py` | Append-only JSONL persistence |
| Index | `v3/memory/semantic_index.py` | Inverted token index |
| Retrieval | `v3/memory/retrieval.py` | Query runtime with scoring |
| Integrity | `v3/memory/integrity.py` | Store integrity (10 checks) |
| Index Integrity | `v3/memory/index_integrity.py` | Index integrity (7 checks) |
