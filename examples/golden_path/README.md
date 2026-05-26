# SystemKernel v3.0 — Golden Path

An end-to-end demonstration of the complete SystemKernel deterministic pipeline.

## What This Example Shows

1. **Events as Source of Truth** — 13 deterministic execution events (init → build → test → deploy)
2. **Observability Graph** — RuntimeGraph + Metrics + Telemetry, all derived from events
3. **Memory Candidates** — Projected from events, preserving provenance
4. **Memory Runtime** — Write → Index → Retrieve → Recall → Compact → Report
5. **Complexity Quality Gate** — Structural check blocking complexity without benefit

## How to Run

```bash
cd SystemKernel
python examples/golden_path/run_golden_path.py
```

## Expected Output

The script runs in ~3 seconds and produces:

```
GOLDEN PATH COMPLETE
  Events created:          13
  Graph hash:              a8e5b63f53a4d25e
  Candidates:              8
  Memory records:          8
  Recall results:          2
  Quality verdict:         REVIEW
  Run hash:                c5bef7ae922816dc
```

## Output Files

All outputs are written to `examples/golden_path/output/`:

| File | Description |
|------|-------------|
| `golden_path_summary.json` | Full deterministic summary with run_hash |
| `memory_system_report.json` | Memory subsystem integrity report |
| `complexity_budget_report.json` | Complexity budget gate report |

## Determinism

The golden path is fully deterministic. Running it twice produces identical:
- Event stream fingerprint
- Graph hash
- Memory runtime hash
- Recall results
- System report hash
- Run hash

If any hash differs between runs, a regression has been introduced.

## Key Architecture

```
Events (SOURCE OF TRUTH)
  |
  +-- RuntimeGraph        (projection — nodes + edges)
  +-- RuntimeMetrics      (projection — retries, durations)
  +-- InvariantTelemetry  (projection — purity score)
  +-- MemoryCandidate[]   (projection — type, content, priority)
       |
       +-- EpisodicMemoryStore  (append-only JSONL)
       +-- SemanticMemoryIndex  (inverted token index)
       +-- TruthLinkedRecall    (provenance-attached search)
       +-- MemoryCompactor      (deterministic dedup)
       +-- MemorySystemReport   (unified integrity)
```

**The golden rule:** Events are the ONLY source of truth.
Every output is a pure projection. If you delete all memory, observability,
and quality data, the kernel still works. Replaying the same events
always produces identical results.
