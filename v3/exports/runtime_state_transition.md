# Runtime State Transition Diagram — Phase 4A

## ExecutionState Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING: ExecutionState(execution_id)

    PENDING --> RUNNING: start()

    state RUNNING {
        [*] --> StageStart
        StageStart --> StageRunning: start_stage(name)
        StageRunning --> StageCompleted: advance(name, result)
        StageCompleted --> StageStart: next stage
        StageRunning --> StageRunning: increment_retry()
        StageRunning --> StageFailed: fail(name, error)
    }

    RUNNING --> COMPLETED: complete()
    RUNNING --> FAILED: fail() on last stage
    RUNNING --> CRASHED: crash()

    COMPLETED --> [*]
    FAILED --> [*]
    CRASHED --> [*]

    CRASHED --> RUNNING: start() [crash recovery]
```

## StageProgress per-stage transitions

```mermaid
stateDiagram-v2
    [*] --> PENDING

    PENDING --> RUNNING: start_stage()
    RUNNING --> COMPLETED: advance()
    RUNNING --> FAILED: fail()
    COMPLETED --> [*]
    FAILED --> [*]
```

## ExecutionStatus Enum

| Status | Description |
|--------|-------------|
| PENDING | Execution created but not yet started |
| RUNNING | Pipeline is actively executing stages |
| COMPLETED | All pipeline stages passed successfully |
| FAILED | A stage failed after exhausting retries |
| CRASHED | Unexpected termination (detected via CrashMarker) |

## StageStatus Enum

| Status | Description |
|--------|-------------|
| PENDING | Stage not yet started |
| RUNNING | Stage currently executing |
| COMPLETED | Stage passed |
| FAILED | Stage failed (after retries) |

## Invariant: Immutable Transitions

Every transition returns a NEW `ExecutionState` instance. The original is never modified.

```python
es1 = ExecutionState(execution_id="X")
es2 = es1.start()      # es1.status == PENDING, es2.status == RUNNING
es3 = es2.advance(...) # es2 unchanged, es3 has updated completed_stages
```
