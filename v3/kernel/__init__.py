"""
SystemKernel v3.0 — Kernel Boundary.

5 subsystems:
  - execution_engine  (★ v3: Event-Sourced DomainState + Checkpoint + Replay)
  - memory_gateway    (★ v3: Memory isolation boundary)
  - observability     (★ v3: ccusage integration)
  - adapter           (→ v2 SkillsManagementSystem.core.adapter, unchanged)
  - task_system       (→ v2 TaskSystem.core.task_manager, unchanged)
  - event_bus         (→ v2 EventBus.event_bus, unchanged)

Phase 4B: Event-sourced runtime with time-travel execution.
Phase 4A: Recoverable, replayable, forkable state runtime.
ZERO LLM imports in this package. Enforced by architecture_guard.py.
"""

from v3.kernel.execution_engine import (
    ExecutionEngine, DomainState, ExecutionConfig,
    StateField, MergeStrategy, RetryPolicy, NoopStage,
    ExecutionEngineFrozenError, ExecutionEngineNestingError,
)
from v3.kernel.execution_state import (
    ExecutionState, StageProgress, ExecutionStatus, StageStatus,
    compute_pipeline_hash,
)
from v3.kernel.checkpoint import (
    Checkpoint, CheckpointStore, FileCheckpointStore,
    CrashMarker, compute_truth_fingerprint,
)
from v3.kernel.replay import (
    replay_execution, replay_from_events, replay_execution_events,
    compare_replays, ReplayResult, ReplayPoint,
    compute_replay_hash,
    replay_to_graph, replay_to_metrics, replay_to_telemetry,
)
# Phase 4C: Observability graph
from v3.kernel.observability_graph import (
    RuntimeGraph, RuntimeNode, RuntimeEdge,
    NodeType, EdgeType,
    build_graph, get_nodes_by_type, get_edges_by_type,
    get_error_nodes, is_deterministic,
)
# Phase 4C: Telemetry
from v3.kernel.telemetry import (
    InvariantTelemetry, compute_telemetry, telemetry_fingerprint,
)
# Phase 4C: Metrics
from v3.kernel.metrics import (
    RuntimeMetrics, compute_metrics, metrics_fingerprint,
)
# Phase 4D-1: Memory boundary
from v3.kernel.memory_contract import (
    MemoryWriteRequest, MemoryWriteResult,
    MemoryReadRequest, MemoryReadResult,
    empty_write_result, empty_read_result,
    MEMORY_CONTRACT_INVARIANTS, compute_contract_hash,
)
from v3.kernel.memory_candidate import (
    MemoryCandidate, CandidateType,
    project_candidates, get_candidates_by_type,
    get_error_candidates, get_high_priority_candidates,
    compute_candidate_fingerprint,
)
# Phase 4B: Event sourcing
from v3.kernel.events import (
    ExecutionEvent, EventType, make_event,
    reduce_execution_state, compute_event_hash,
    validate_event_stream, event_stream_fingerprint,
)
from v3.kernel.event_store import (
    EventStore, FileEventStore, compute_stream_fingerprint,
)
from v3.kernel.time_travel import (
    TimelinePoint, TimelineBranch, TimeTravelResult,
    rewind_to_sequence, reconstruct_state_at,
    fork_execution, diff_timelines, mergeable,
    build_timeline,
)
from v3.kernel.memory_gateway import MemoryGateway, MemoryEvent, MemoryEventType, MemoryEventSource
from v3.kernel.observability import ObservabilityService

__all__ = [
    # Execution engine
    "ExecutionEngine",
    "DomainState",
    "ExecutionConfig",
    "StateField",
    "MergeStrategy",
    "RetryPolicy",
    "NoopStage",
    "ExecutionEngineFrozenError",
    "ExecutionEngineNestingError",
    # Lifecycle tracker (Phase 4A)
    "ExecutionState",
    "StageProgress",
    "ExecutionStatus",
    "StageStatus",
    "compute_pipeline_hash",
    # Checkpoint (Phase 4A)
    "Checkpoint",
    "CheckpointStore",
    "FileCheckpointStore",
    "CrashMarker",
    "compute_truth_fingerprint",
    # Replay (Phase 4A + 4B + 4C)
    "replay_execution",
    "replay_from_events",
    "replay_execution_events",
    "compare_replays",
    "ReplayResult",
    "ReplayPoint",
    "compute_replay_hash",
    "replay_to_graph",
    "replay_to_metrics",
    "replay_to_telemetry",
    # Event sourcing (Phase 4B)
    "ExecutionEvent",
    "EventType",
    "make_event",
    "reduce_execution_state",
    "compute_event_hash",
    "validate_event_stream",
    "event_stream_fingerprint",
    # Event store (Phase 4B)
    "EventStore",
    "FileEventStore",
    "compute_stream_fingerprint",
    # Time travel (Phase 4B)
    "TimelinePoint",
    "TimelineBranch",
    "TimeTravelResult",
    "rewind_to_sequence",
    "reconstruct_state_at",
    "fork_execution",
    "diff_timelines",
    "mergeable",
    "build_timeline",
    # Memory
    "MemoryGateway",
    "MemoryEvent",
    "MemoryEventType",
    "MemoryEventSource",
    # Observability
    "ObservabilityService",
    # Phase 4C: Observability Graph
    "RuntimeGraph",
    "RuntimeNode",
    "RuntimeEdge",
    "NodeType",
    "EdgeType",
    "build_graph",
    "get_nodes_by_type",
    "get_edges_by_type",
    "get_error_nodes",
    "is_deterministic",
    # Phase 4C: Telemetry
    "InvariantTelemetry",
    "compute_telemetry",
    "telemetry_fingerprint",
    # Phase 4C: Metrics
    "RuntimeMetrics",
    "compute_metrics",
    "metrics_fingerprint",
    # Phase 4D-1: Memory boundary
    "MemoryWriteRequest",
    "MemoryWriteResult",
    "MemoryReadRequest",
    "MemoryReadResult",
    "empty_write_result",
    "empty_read_result",
    "MEMORY_CONTRACT_INVARIANTS",
    "compute_contract_hash",
    "MemoryCandidate",
    "CandidateType",
    "project_candidates",
    "get_candidates_by_type",
    "get_error_candidates",
    "get_high_priority_candidates",
    "compute_candidate_fingerprint",
]
