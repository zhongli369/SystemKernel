# Time Travel Runtime — Phase 4B

## Capabilities

1. **Rewind** — Go back to any sequence point in execution history
2. **Reconstruct** — Rebuild ExecutionState at any point in time
3. **Fork** — Create independent execution branches from any point
4. **Diff** — Compare two forked timelines
5. **Merge check** — Determine if branches can be merged

---

## Rewind to Sequence

```mermaid
sequenceDiagram
    participant User
    participant TT as TimeTravel
    participant ES as EventStream
    participant State as ExecutionState

    User->>TT: rewind_to_sequence(events, seq=2)
    TT->>ES: filter events where sequence <= 2
    ES-->>TT: prefix events (0, 1, 2)
    TT->>TT: reconstruct_state_at(events, 2)
    TT->>State: reduce_execution_state(prefix)
    State-->>TT: ExecutionState at seq=2
    TT-->>User: TimeTravelResult{state, timeline}
```

## Execution Fork

```mermaid
sequenceDiagram
    participant User
    participant TT as TimeTravel
    participant Branch as TimelineBranch

    User->>TT: fork_execution(events, at_sequence=2)
    TT->>TT: Copy prefix events (0..2)
    TT->>TT: Generate new execution_id + branch_id
    TT->>TT: Create FORK_CREATED event (seq=0)
    TT->>TT: Re-sequence prefix events under new id
    TT-->>User: TimelineBranch{events, state_at_fork}
    User->>Branch: Continue execution independently
```

## Timeline Comparison

```mermaid
flowchart TD
    A[Parent Execution] -->|fork at seq=2| B[Branch A]
    A -->|fork at seq=2| C[Branch B]
    B -->|diff| D{Compare}
    C -->|diff| D
    D -->|identical| E[Same event types + hashes]
    D -->|different| F[diffs list with details]
    D -->|mergeable| G[Same ancestor + compatible states]
```

## State Transition (event-driven)

```mermaid
stateDiagram-v2
    [*] --> PENDING: ExecutionState(id)

    PENDING --> RUNNING: EXECUTION_STARTED

    state RUNNING {
        [*] --> Idle
        Idle --> StageActive: STAGE_STARTED
        StageActive --> Idle: STAGE_COMPLETED
        StageActive --> StageActive: RETRY_INCREMENTED
        StageActive --> FAILED: STAGE_FAILED
    }

    RUNNING --> COMPLETED: EXECUTION_COMPLETED
    RUNNING --> FAILED: EXECUTION_FAILED
    RUNNING --> CRASHED: EXECUTION_CRASHED

    COMPLETED --> [*]
    FAILED --> [*]
    CRASHED --> [*]

    CRASHED --> RUNNING: replay + resume
```
