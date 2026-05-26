# SystemKernel v3.0 — Architecture Report (Phase 4A)

**Generated:** 2026-05-24
**Phase:** 4A — ExecutionState + Checkpoint Runtime

---

## Module Dependency Graph

```
execution_state.py  (stdlib only, zero v3 imports)
      ^
checkpoint.py       (stdlib only, zero v3 imports)
      ^     ^
replay.py           (imports checkpoint + execution_state)
      ^
execution_engine.py (imports execution_state + checkpoint + memory_gateway + truth_model + invariants)
      ^
__init__.py         (imports all)
```

**Zero circular dependencies.** Leaf modules are LLM-free and have no v3 internal deps.

---

## Class Hierarchy

### execution_state.py

```
ExecutionStatus (class with string constants)
  PENDING, RUNNING, COMPLETED, FAILED, CRASHED

StageStatus (class with string constants)
  PENDING, RUNNING, COMPLETED, FAILED

StageProgress (frozen dataclass)
  Fields: stage_name, status, result, started_at, completed_at, duration_ms, error

ExecutionState (frozen dataclass)
  Fields: execution_id, current_stage, current_stage_index, completed_stages,
          stage_progress, event_count, started_at, updated_at, status,
          retry_count, metadata
  Methods: start(), start_stage(), advance(), fail(), complete(), crash(),
           increment_retry(), increment_event(), snapshot(), fingerprint()

compute_pipeline_hash(stages) → str
```

### checkpoint.py

```
Checkpoint (frozen dataclass)
  Fields: checkpoint_id, execution_id, stage, stage_index, state_snapshot,
          lifecycle_snapshot, pipeline_hash, stage_order, truth_fingerprint,
          invariant_status, timestamp, parent_id

CheckpointStore (abstract class)
  Methods: save_checkpoint(), load_latest(), load(), list(), replay()

FileCheckpointStore (CheckpointStore)
  append-only JSONL, keyed by execution_id

CrashMarker (static class)
  Methods: write(), read(), exists(), clear()

compute_truth_fingerprint(truth) → str
```

### replay.py

```
ReplayPoint (frozen dataclass)
  Fields: stage, stage_index, pipeline_hash, timestamp, lifecycle_snapshot

ReplayResult (frozen dataclass)
  Fields: execution_id, original_stages, replayed_stages, checkpoint_count,
          identical, drift_detected, diffs
  Properties: stage_count_match

replay_execution(store, execution_id) → ReplayResult | None
compare_replays(original, current) → (bool, list[str])
compute_replay_hash(points) → str
```

### execution_engine.py

```
MergeStrategy (Enum): REPLACE, APPEND, MERGE, KEEP

StateField (frozen dataclass)
  Fields: name, type_, merge, default

DomainState (immutable reducer-based state)
  Methods: update(), get(), snapshot()

PipelineStage (abstract): run(state) → StageResult
  LintStage, NoopStage

RetryPolicy (Enum): NONE, ONCE, FALLBACK, CIRCUIT_BREAKER

StageResult (frozen dataclass)
  Fields: stage_name, passed, output, duration_ms, error

ExecutionConfig (frozen dataclass)
  Fields: pipeline, retry, max_retries, checkpoint_store, thread_id,
          memory_gateway, freeze_after_init, timeout_s

ExecutionEngineFrozenError (Exception)
ExecutionEngineNestingError (Exception)

ExecutionEngine
  Properties: frozen, run_count, config, lifecycle
  Methods: run(state, resume_from_checkpoint=False, execution_id=None) → dict
```

---

## Import Depth Analysis

| Module | Max Import Depth | Internal Deps |
|--------|-----------------|---------------|
| execution_state.py | 0 (stdlib only) | none |
| checkpoint.py | 0 (stdlib only) | none |
| replay.py | 1 | checkpoint, execution_state |
| execution_engine.py | 2 | execution_state, checkpoint, memory_gateway, truth_model, invariants |
| memory_gateway.py | 0 | none |
| observability.py | 0 | none |

---

## Invariant Status

| Invariant | Status | Detail |
|-----------|--------|--------|
| Zero LLM in kernel | PASS | All leaf modules stdlib only |
| Single loop | PASS | ExecutionEngineNestingError enforced |
| Deterministic | PASS | pipeline_hash, fingerprint, replay all deterministic |
| Append-only | PASS | FileCheckpointStore uses open("a") only |
| Immutable state | PASS | All ExecutionState methods return new frozen instances |
| Memory removable | PASS | MemoryGateway unchanged, still optional |
