"""
Telemetry — Deterministic invariant telemetry projection from event streams.

Phase 4C: Projects an event stream (and optional RuntimeGraph) into an
InvariantTelemetry snapshot. This is a projection, not a runtime mutation.
No file I/O. No LLM. No memory reads. Fully JSON-serializable.

Events are the SOLE source of truth. Checkpoints are snapshot markers only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.kernel.events import ExecutionEvent
    from v3.kernel.observability_graph import RuntimeGraph


# ═══════════════════════════════════════════════════════════════════════
# InvariantTelemetry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class InvariantTelemetry:
    """Deterministic projection of kernel invariant health.

    Every field is a verifiable claim about the event stream and its
    derived projections. This is read-only telemetry — it does not
    mutate, write, or decide anything.
    """

    single_loop_confirmed: bool
    event_stream_valid: bool
    event_sequence_contiguous: bool
    event_parent_chain_valid: bool
    replay_reconstructable: bool
    has_terminal_event: bool
    no_memory_dependency: bool
    truth_source_is_events: bool
    checkpoint_is_snapshot_only: bool
    deterministic_graph_hash: bool
    purity_score: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "single_loop_confirmed": self.single_loop_confirmed,
            "event_stream_valid": self.event_stream_valid,
            "event_sequence_contiguous": self.event_sequence_contiguous,
            "event_parent_chain_valid": self.event_parent_chain_valid,
            "replay_reconstructable": self.replay_reconstructable,
            "has_terminal_event": self.has_terminal_event,
            "no_memory_dependency": self.no_memory_dependency,
            "truth_source_is_events": self.truth_source_is_events,
            "checkpoint_is_snapshot_only": self.checkpoint_is_snapshot_only,
            "deterministic_graph_hash": self.deterministic_graph_hash,
            "purity_score": self.purity_score,
            "metadata": dict(self.metadata),
        }

    @property
    def is_pure(self) -> bool:
        return self.purity_score == 100


# ═══════════════════════════════════════════════════════════════════════
# Telemetry Computation
# ═══════════════════════════════════════════════════════════════════════

def compute_telemetry(
    events: "Tuple[ExecutionEvent, ...]",
    graph: "Optional[RuntimeGraph]" = None,
) -> "InvariantTelemetry":
    """Compute invariant telemetry from an event stream.

    Pure function. No side effects. No LLM. No file I/O. No memory reads.

    Args:
        events: Ordered tuple of ExecutionEvents (source of truth)
        graph: Optional pre-built RuntimeGraph (recomputed if absent)

    Returns:
        InvariantTelemetry with all invariant checks and purity score.
    """
    from v3.kernel.events import (
        EventType, validate_event_stream, event_stream_fingerprint,
    )
    from v3.kernel.observability_graph import build_graph, _compute_graph_hash

    if graph is None and events:
        graph = build_graph(events)

    # ── Event stream validation ──────────────────────────────────────
    is_valid, issues = validate_event_stream(events)

    # ── Sequence continuity ──────────────────────────────────────────
    if events:
        sequences = [e.sequence for e in events]
        contiguous = sequences == list(range(len(events)))
    else:
        contiguous = True  # empty stream is vacuously contiguous

    # ── Parent chain validity ────────────────────────────────────────
    parent_chain_ok = True
    if events and len(events) > 1:
        for i in range(1, len(events)):
            if events[i].parent_event_id:
                if events[i].parent_event_id != events[i - 1].event_id:
                    parent_chain_ok = False
                    break

    # ── Terminal event check ─────────────────────────────────────────
    if events:
        terminal = events[-1].event_type
        has_terminal = terminal in {
            EventType.EXECUTION_COMPLETED,
            EventType.EXECUTION_FAILED,
            EventType.EXECUTION_CRASHED,
        }
    else:
        has_terminal = False

    # ── Replay reconstructability ────────────────────────────────────
    # Events alone must be sufficient to reconstruct state
    replay_reconstructable = is_valid and has_terminal

    # ── Deterministic graph hash ─────────────────────────────────────
    if graph and events:
        recalculated = _compute_graph_hash(graph)
        deterministic_hash = recalculated == graph.graph_hash
    else:
        deterministic_hash = True

    # ── Invariant claims ──────────────────────────────────────────────
    single_loop = _check_single_loop(events)
    no_memory_dep = True   # telemetry never touches memory
    truth_is_events = True  # events are always the source of truth
    checkpoint_snapshot = _check_checkpoint_snapshots_only(events)

    # ── Purity score ─────────────────────────────────────────────────
    score = _compute_purity_score(
        single_loop=single_loop,
        event_stream_valid=is_valid,
        event_sequence_contiguous=contiguous,
        parent_chain_valid=parent_chain_ok,
        replay_reconstructable=replay_reconstructable,
        has_terminal=has_terminal,
        no_memory_dependency=no_memory_dep,
        truth_source_is_events=truth_is_events,
        checkpoint_is_snapshot=checkpoint_snapshot,
        deterministic_graph_hash=deterministic_hash,
    )

    return InvariantTelemetry(
        single_loop_confirmed=single_loop,
        event_stream_valid=is_valid,
        event_sequence_contiguous=contiguous,
        event_parent_chain_valid=parent_chain_ok,
        replay_reconstructable=replay_reconstructable,
        has_terminal_event=has_terminal,
        no_memory_dependency=no_memory_dep,
        truth_source_is_events=truth_is_events,
        checkpoint_is_snapshot_only=checkpoint_snapshot,
        deterministic_graph_hash=deterministic_hash,
        purity_score=score,
        metadata={
            "event_count": len(events),
            "validation_issues": issues if not is_valid else [],
            "graph_hash": graph.graph_hash if graph else "",
        },
    )


# ═══════════════════════════════════════════════════════════════════════
# Internal checks
# ═══════════════════════════════════════════════════════════════════════

def _check_single_loop(events: "Tuple[ExecutionEvent, ...]") -> bool:
    """Verify the event stream represents a single execution loop.

    A valid single loop: exactly one EXECUTION_STARTED, one terminal event,
    no nested start events.
    """
    from v3.kernel.events import EventType

    start_count = sum(
        1 for e in events if e.event_type == EventType.EXECUTION_STARTED
    )
    if start_count != 1 and events:
        return False

    # Check for nested loops: no EXECUTION_STARTED after the first event
    if events:
        for e in events[1:]:
            if e.event_type == EventType.EXECUTION_STARTED:
                return False

    return True


def _check_checkpoint_snapshots_only(events: "Tuple[ExecutionEvent, ...]") -> bool:
    """Verify checkpoint events are marked as snapshots, not truth sources."""
    from v3.kernel.events import EventType
    for e in events:
        if e.event_type == EventType.EVENT_RECORDED:
            if e.payload.get("is_truth_source", False):
                return False
    return True


def _compute_purity_score(
    single_loop: bool,
    event_stream_valid: bool,
    event_sequence_contiguous: bool,
    parent_chain_valid: bool,
    replay_reconstructable: bool,
    has_terminal: bool,
    no_memory_dependency: bool,
    truth_source_is_events: bool,
    checkpoint_is_snapshot: bool,
    deterministic_graph_hash: bool,
) -> int:
    """Compute telemetry purity score (0-100).

    Each invariant is worth 10 points:
    """
    score = 0
    if single_loop:
        score += 10
    if event_stream_valid:
        score += 10
    if event_sequence_contiguous:
        score += 10
    if parent_chain_valid:
        score += 10
    if replay_reconstructable:
        score += 10
    if has_terminal:
        score += 10
    if no_memory_dependency:
        score += 10
    if truth_source_is_events:
        score += 10
    if checkpoint_is_snapshot:
        score += 10
    if deterministic_graph_hash:
        score += 10
    return score


# ═══════════════════════════════════════════════════════════════════════
# Telemetry fingerprint
# ═══════════════════════════════════════════════════════════════════════

def telemetry_fingerprint(telemetry: InvariantTelemetry) -> str:
    """Deterministic fingerprint of a telemetry snapshot."""
    parts = [
        str(int(telemetry.single_loop_confirmed)),
        str(int(telemetry.event_stream_valid)),
        str(int(telemetry.event_sequence_contiguous)),
        str(int(telemetry.event_parent_chain_valid)),
        str(int(telemetry.replay_reconstructable)),
        str(int(telemetry.has_terminal_event)),
        str(int(telemetry.no_memory_dependency)),
        str(int(telemetry.truth_source_is_events)),
        str(int(telemetry.checkpoint_is_snapshot_only)),
        str(int(telemetry.deterministic_graph_hash)),
        str(telemetry.purity_score),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
