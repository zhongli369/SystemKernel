"""
Replay — Deterministic execution timeline replay from event streams.

Phase 4B: Primary replay source is the event stream (events -> reducer -> state).
Checkpoints are optimization snapshots, not authoritative.

Loads events (or checkpoints as fallback) for an execution_id and reconstructs
the timeline. Compares against the original to detect nondeterministic drift.

Zero LLM. Pure data reconstruction from append-only JSONL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.kernel.checkpoint import CheckpointStore
    from v3.kernel.event_store import EventStore
    from v3.kernel.events import ExecutionEvent
    from v3.kernel.observability_graph import RuntimeGraph
    from v3.kernel.metrics import RuntimeMetrics
    from v3.kernel.telemetry import InvariantTelemetry


# ═══════════════════════════════════════════════════════════════════════
# ReplayPoint — one point in a replayed timeline
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ReplayPoint:
    """A single point in the replayed execution timeline."""

    stage: str
    stage_index: int
    pipeline_hash: str
    timestamp: str
    lifecycle_snapshot: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════
# ReplayResult — outcome of replaying one execution
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ReplayResult:
    """Result of replaying an execution from checkpoints."""

    execution_id: str
    original_stages: Tuple[str, ...]
    replayed_stages: Tuple[str, ...]
    checkpoint_count: int
    identical: bool
    drift_detected: bool
    diffs: Tuple[str, ...] = ()

    @property
    def stage_count_match(self) -> bool:
        return len(self.original_stages) == len(self.replayed_stages)

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "original_stages": list(self.original_stages),
            "replayed_stages": list(self.replayed_stages),
            "checkpoint_count": self.checkpoint_count,
            "identical": self.identical,
            "drift_detected": self.drift_detected,
            "diffs": list(self.diffs),
        }


# ═══════════════════════════════════════════════════════════════════════
# Replay Execution
# ═══════════════════════════════════════════════════════════════════════

def replay_execution(
    store: "CheckpointStore", execution_id: str
) -> Optional[ReplayResult]:
    """Replay an execution timeline from its checkpoint chain.

    Loads all checkpoints for the given execution_id, reconstructs the
    stage order from the first checkpoint's stage_order field, and
    compares the actual executed stages against the declared order.

    Returns None if no checkpoints exist for this execution_id.
    """
    checkpoints = store.replay(execution_id)
    if not checkpoints:
        return None

    # The first checkpoint declares the intended stage_order
    declared_order = tuple(checkpoints[0].stage_order)

    # Reconstruct actual order from checkpoint stages
    actual_stages = tuple(
        cp.stage for cp in checkpoints
        if cp.stage not in ("__completed__", "__start__")
    )

    # Compare
    diffs: list[str] = []

    if declared_order != actual_stages[:len(declared_order)]:
        diffs.append(
            f"Stage order differs: declared={list(declared_order)} "
            f"vs actual={list(actual_stages)}"
        )

    # Check for pipeline hash consistency across all checkpoints
    base_hash = checkpoints[0].pipeline_hash
    for cp in checkpoints[1:]:
        if cp.pipeline_hash and cp.pipeline_hash != base_hash:
            diffs.append(
                f"Pipeline hash drift at stage '{cp.stage}': "
                f"{cp.pipeline_hash} != {base_hash}"
            )
            break

    # Check parent chain integrity
    for i, cp in enumerate(checkpoints[1:], start=1):
        parent = checkpoints[i - 1]
        if cp.parent_id and cp.parent_id != parent.checkpoint_id:
            diffs.append(
                f"Parent chain broken at stage '{cp.stage}': "
                f"expected parent {parent.checkpoint_id}, got {cp.parent_id}"
            )

    drift_detected = len(diffs) > 0
    identical_declared = declared_order == actual_stages[:len(declared_order)]

    return ReplayResult(
        execution_id=execution_id,
        original_stages=declared_order,
        replayed_stages=actual_stages,
        checkpoint_count=len(checkpoints),
        identical=identical_declared and not drift_detected,
        drift_detected=drift_detected,
        diffs=tuple(diffs),
    )


# ═══════════════════════════════════════════════════════════════════════
# Compare Replays
# ═══════════════════════════════════════════════════════════════════════

def compare_replays(
    original: ReplayResult, current: ReplayResult
) -> Tuple[bool, list[str]]:
    """Compare two ReplayResults. Returns (identical, diffs)."""
    diffs: list[str] = []

    if original.original_stages != current.original_stages:
        diffs.append(
            f"Original stages differ: {list(original.original_stages)} "
            f"vs {list(current.original_stages)}"
        )
    if original.replayed_stages != current.replayed_stages:
        diffs.append(
            f"Replayed stages differ: {list(original.replayed_stages)} "
            f"vs {list(current.replayed_stages)}"
        )
    if original.checkpoint_count != current.checkpoint_count:
        diffs.append(
            f"Checkpoint count differs: {original.checkpoint_count} "
            f"vs {current.checkpoint_count}"
        )
    if original.drift_detected != current.drift_detected:
        diffs.append("Drift detection mismatch")
    if original.identical != current.identical:
        diffs.append("Identical flag mismatch")

    return len(diffs) == 0, diffs


# ═══════════════════════════════════════════════════════════════════════
# Replay Hash
# ═══════════════════════════════════════════════════════════════════════

def compute_replay_hash(points: Tuple[ReplayPoint, ...]) -> str:
    """Deterministic hash of a replay timeline for cross-run comparison."""
    import hashlib
    parts = [
        f"{p.stage}:{p.stage_index}:{p.pipeline_hash}"
        for p in points
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Phase 4B: Event-based Replay
# ═══════════════════════════════════════════════════════════════════════

def replay_from_events(
    events: "Tuple[ExecutionEvent, ...]",
    execution_id: str = "",
) -> "Optional[ReplayResult]":
    """Replay an execution timeline from its event stream.

    Phase 4B: Events are the authoritative source of truth.
    Reduces events to reconstruct ExecutionState at each point.

    Returns None if the event stream is empty.
    """
    if not events:
        return None

    from v3.kernel.events import (
        EventType, reduce_execution_state, event_stream_fingerprint,
    )

    eid = execution_id or events[0].execution_id

    # Reconstruct full state from all events
    final_state = reduce_execution_state(events, eid)

    # Extract stage order from events
    stage_events = [
        e for e in events
        if e.event_type in (EventType.STAGE_COMPLETED, EventType.STAGE_STARTED)
    ]
    replayed_stages = tuple(
        e.payload.get("stage_name", "")
        for e in stage_events
        if e.event_type == EventType.STAGE_COMPLETED
    )

    # Original stages from the first event's declared stage_order
    declared_order: Tuple[str, ...] = ()
    if events[0].event_type == EventType.EXECUTION_STARTED:
        declared_order = tuple(events[0].payload.get("stage_order", []))

    # Compare
    diffs: list[str] = []

    if declared_order and declared_order != replayed_stages:
        diffs.append(
            f"Stage order differs: declared={list(declared_order)} "
            f"vs actual={list(replayed_stages)}"
        )

    # Check event stream integrity
    from v3.kernel.events import validate_event_stream
    is_valid, issues = validate_event_stream(events)
    if not is_valid:
        diffs.extend(issues)

    # Verify final state consistency
    if final_state.status not in ("COMPLETED", "FAILED", "CRASHED"):
        diffs.append(
            f"Final state not terminal: {final_state.status}"
        )

    drift_detected = len(diffs) > 0
    identical = declared_order == replayed_stages and not drift_detected

    return ReplayResult(
        execution_id=eid,
        original_stages=declared_order if declared_order else replayed_stages,
        replayed_stages=replayed_stages,
        checkpoint_count=len(events),  # event_count, kept as checkpoint_count for compat
        identical=identical,
        drift_detected=drift_detected,
        diffs=tuple(diffs),
    )


def replay_execution_events(
    store: "EventStore", execution_id: str,
) -> "Optional[ReplayResult]":
    """Replay from an EventStore. Phase 4B primary replay path."""
    events = store.load_stream(execution_id)
    if not events:
        return None
    return replay_from_events(events, execution_id)


# ═══════════════════════════════════════════════════════════════════════
# Phase 4C: Replay → Observability Projections
# ═══════════════════════════════════════════════════════════════════════

def replay_to_graph(
    events: "Tuple[ExecutionEvent, ...]",
) -> "Optional[RuntimeGraph]":
    """Build a RuntimeGraph from an event stream.

    Returns None if the stream is empty. Events are the source of truth.
    """
    if not events:
        return None
    from v3.kernel.observability_graph import build_graph
    return build_graph(events)


def replay_to_metrics(
    events: "Tuple[ExecutionEvent, ...]",
) -> "Optional[RuntimeMetrics]":
    """Compute RuntimeMetrics from an event stream.

    Returns None if the stream is empty. Events are the source of truth.
    """
    if not events:
        return None
    from v3.kernel.metrics import compute_metrics
    return compute_metrics(events)


def replay_to_telemetry(
    events: "Tuple[ExecutionEvent, ...]",
    graph: "Optional[RuntimeGraph]" = None,
) -> "Optional[InvariantTelemetry]":
    """Compute InvariantTelemetry from an event stream.

    Returns None if the stream is empty. Events are the source of truth.
    If graph is None, it will be built from events internally.
    """
    if not events:
        return None
    from v3.kernel.telemetry import compute_telemetry
    return compute_telemetry(events, graph)
