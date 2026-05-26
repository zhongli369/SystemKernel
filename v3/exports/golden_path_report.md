# Golden Path Report

## SystemKernel v3.0 — End-to-End Demonstration

### Command Used

```bash
python examples/golden_path/run_golden_path.py
```

### Pipeline

```
Events (13, deterministic)
  → RuntimeGraph (8 nodes, 13 edges, hash: a8e5b63f53a4d25e)
  → RuntimeMetrics (retries=1)
  → InvariantTelemetry (purity=100)
  → MemoryCandidates (8 candidates, 4 types)
  → EpisodicMemoryStore (8 records, JSONL)
  → SemanticMemoryIndex (73 tokens)
  → TruthLinkedRecall (2 results, provenance-attached)
  → MemoryCompaction (8→4, 3 duplicates merged, 1 archived)
  → MemorySystemReport (removable=YES, projection=YES, truth=YES)
  → ComplexityQualityGate (36 modules, verdict=REVIEW)
```

### Output Files

| File | Size | Content |
|------|------|---------|
| `golden_path_summary.json` | ~1KB | Full deterministic summary |
| `memory_system_report.json` | ~1KB | Memory subsystem integrity |
| `complexity_budget_report.json` | ~36KB | Complexity budget analysis |

### Summary

| Field | Value |
|-------|-------|
| event_count | 13 |
| graph_hash | a8e5b63f53a4d25e |
| candidates_count | 8 |
| memory_records | 8 |
| recall_results | 2 |
| run_hash | c5bef7ae922816dc |

### Deterministic Verdict

**YES** — Running the golden path twice produces identical:
- Event stream fingerprint: `b017af7a2798da0c`
- Graph hash: `a8e5b63f53a4d25e`
- Memory runtime hash: `4dee79904877b2e2`
- Recall results: 2
- System report hash: `a78c8649b917f74a`
- Run hash: `c5bef7ae922816dc`

### What Developer Learns

1. **Events are truth** — 13 events encode the entire execution history
2. **Projections derive from events** — graph, metrics, telemetry, memory are all pure projections
3. **Memory is external** — episodic store, index, recall, compaction operate outside kernel
4. **Provenance is preserved** — recall results link back to source events
5. **Quality gate protects complexity** — REVIEW verdict shows gate is active
6. **Everything is deterministic** — same events always produce same results
