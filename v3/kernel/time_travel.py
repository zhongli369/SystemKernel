"""
Time Travel — Rewind, fork, and diff execution timelines.

Operates on event streams to provide:
  - Historical state reconstruction at any sequence point
  - Execution forking from any point in the timeline
  - Timeline comparison and diffing

Zero LLM. Pure functional operations on immutable event streams.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple

from v3.kernel.events import (
    ExecutionEvent, EventType, make_event,
    reduce_execution_state, event_stream_fingerprint,
)
from v3.kernel.execution_state import ExecutionState


# ═══════════════════════════════════════════════════════════════════════
# TimelinePoint — one point in a timeline
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TimelinePoint:
    """A single point in an execution timeline, reconstructed from events."""

    sequence: int
    event_type: str
    event_id: str
    timestamp: str
    stage_name: str = ""
    status: str = ""
    state_fingerprint: str = ""

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "stage_name": self.stage_name,
            "status": self.status,
            "state_fingerprint": self.state_fingerprint,
        }


# ═══════════════════════════════════════════════════════════════════════
# TimelineBranch — a forked execution branch
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TimelineBranch:
    """A forked execution timeline with its own event stream."""

    branch_id: str
    execution_id: str
    parent_execution_id: str
    fork_sequence: int
    events: Tuple[ExecutionEvent, ...]
    state_at_fork: Optional[dict] = None

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def fingerprint(self) -> str:
        return event_stream_fingerprint(self.events)

    def to_dict(self) -> dict:
        return {
            "branch_id": self.branch_id,
            "execution_id": self.execution_id,
            "parent_execution_id": self.parent_execution_id,
            "fork_sequence": self.fork_sequence,
            "event_count": self.event_count,
            "fingerprint": self.fingerprint,
            "state_at_fork": self.state_at_fork,
        }


# ═══════════════════════════════════════════════════════════════════════
# TimeTravelResult — outcome of a time-travel operation
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TimeTravelResult:
    """Result of a time-travel operation (rewind, fork, or reconstruct)."""

    operation: str  # "rewind", "fork", "reconstruct"
    execution_id: str
    target_sequence: int
    events_before: int
    events_after: int
    state: ExecutionState
    timeline: Tuple[TimelinePoint, ...] = ()
    branch: Optional[TimelineBranch] = None
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "execution_id": self.execution_id,
            "target_sequence": self.target_sequence,
            "events_before": self.events_before,
            "events_after": self.events_after,
            "state": self.state.snapshot(),
            "timeline": [p.to_dict() for p in self.timeline],
            "branch": self.branch.to_dict() if self.branch else None,
            "success": self.success,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════════════
# Time Travel Operations
# ═══════════════════════════════════════════════════════════════════════

def rewind_to_sequence(
    events: Tuple[ExecutionEvent, ...], target_sequence: int
) -> Tuple[ExecutionEvent, ...]:
    """Rewind event stream to a specific sequence number (inclusive).

    Returns events from 0..target_sequence. If target is beyond the
    stream length, returns all events unchanged.
    """
    if target_sequence < 0:
        return ()
    return tuple(e for e in events if e.sequence <= target_sequence)


def reconstruct_state_at(
    events: Tuple[ExecutionEvent, ...], target_sequence: int
) -> TimeTravelResult:
    """Reconstruct ExecutionState as it was at a given sequence number.

    Rewinds to the target sequence and reduces events to produce the
    historical state. Useful for debugging and inspection.
    """
    execution_id = events[0].execution_id if events else ""
    rewinded = rewind_to_sequence(events, target_sequence)

    if not rewinded:
        return TimeTravelResult(
            operation="reconstruct",
            execution_id=execution_id,
            target_sequence=target_sequence,
            events_before=len(events),
            events_after=0,
            state=ExecutionState(execution_id=execution_id),
            success=False,
            error="No events at or before target sequence",
        )

    state = reduce_execution_state(rewinded, execution_id)

    # Build timeline points
    timeline = tuple(
        TimelinePoint(
            sequence=e.sequence,
            event_type=e.event_type,
            event_id=e.event_id,
            timestamp=e.timestamp,
            stage_name=e.payload.get("stage_name", ""),
            status=_status_for_event(e.event_type),
            state_fingerprint=state.fingerprint() if e.sequence == target_sequence else "",
        )
        for e in rewinded
    )

    return TimeTravelResult(
        operation="reconstruct",
        execution_id=execution_id,
        target_sequence=target_sequence,
        events_before=len(events),
        events_after=len(rewinded),
        state=state,
        timeline=timeline,
    )


def fork_execution(
    events: Tuple[ExecutionEvent, ...], at_sequence: int
) -> TimelineBranch:
    """Create an execution fork at a specific sequence point.

    The fork copies all events up to at_sequence under a new execution_id.
    The caller can then continue executing from this point independently.
    """
    execution_id = events[0].execution_id if events else ""
    branch_id = str(uuid.uuid4())
    new_execution_id = f"{execution_id}.fork.{branch_id[:8]}"

    prefix = tuple(e for e in events if e.sequence <= at_sequence)

    # Reconstruct state at fork point
    state_at_fork = None
    if prefix:
        reduced = reduce_execution_state(prefix, execution_id)
        state_at_fork = reduced.snapshot()

    # Emit ForkCreated event
    fork_event = make_event(
        execution_id=new_execution_id,
        sequence=0,
        event_type=EventType.FORK_CREATED,
        payload={
            "original_execution_id": execution_id,
            "forked_at_sequence": at_sequence,
            "event_count": len(prefix),
            "branch_id": branch_id,
        },
    )

    # Re-sequence and re-identity prefix events under new execution_id
    forked: list[ExecutionEvent] = [fork_event]
    for i, event in enumerate(prefix, start=1):
        new_evt = ExecutionEvent(
            event_id=str(uuid.uuid4()),
            execution_id=new_execution_id,
            timestamp=event.timestamp,
            sequence=i,
            event_type=event.event_type,
            payload=dict(event.payload),
            parent_event_id=forked[-1].event_id,
        ).with_hash()
        forked.append(new_evt)

    return TimelineBranch(
        branch_id=branch_id,
        execution_id=new_execution_id,
        parent_execution_id=execution_id,
        fork_sequence=at_sequence,
        events=tuple(forked),
        state_at_fork=state_at_fork,
    )


def diff_timelines(
    branch_a: TimelineBranch, branch_b: TimelineBranch
) -> Tuple[bool, list[str]]:
    """Compare two forked timelines. Returns (identical, diffs).

    Computes the event stream fingerprints and compares state at fork point.
    Two branches are identical if their event sequences produce the same
    reduced state at each point.
    """
    diffs: list[str] = []

    if branch_a.fingerprint == branch_b.fingerprint:
        return True, diffs

    # Compare event counts
    if branch_a.event_count != branch_b.event_count:
        diffs.append(
            f"Event count differs: {branch_a.event_count} vs {branch_b.event_count}"
        )

    # Compare state at fork point
    if branch_a.state_at_fork != branch_b.state_at_fork:
        diffs.append("State at fork point differs")

    # Per-event comparison (up to min length)
    # Compare structural content (event_type + payload), not identity fields
    min_len = min(branch_a.event_count, branch_b.event_count)
    for i in range(min_len):
        ea = branch_a.events[i]
        eb = branch_b.events[i]
        if ea.event_type != eb.event_type:
            diffs.append(
                f"Event {i}: type differs — {ea.event_type} vs {eb.event_type}"
            )
        elif _structural_hash(ea) != _structural_hash(eb):
            diffs.append(
                f"Event {i}: content differs — "
                f"type={ea.event_type}, seq={i}"
            )

    return len(diffs) == 0, diffs


def mergeable(
    branch_a: TimelineBranch, branch_b: TimelineBranch
) -> Tuple[bool, str]:
    """Check if two branches can be merged back together.

    Branches are mergeable if they share a common ancestor prefix
    and their divergent states are compatible (no conflicting stage
    completions at the same sequence).

    Returns (is_mergeable, reason).
    """
    if branch_a.parent_execution_id != branch_b.parent_execution_id:
        return False, "Branches have different parent executions"

    if branch_a.fork_sequence != branch_b.fork_sequence:
        return False, "Branches forked at different sequences"

    # Check that fork point states are identical
    if branch_a.state_at_fork != branch_b.state_at_fork:
        return False, "State at fork point differs between branches"

    # Branches from same fork point with same ancestor state are mergeable
    # if they don't conflict (different completed stages at same sequence)
    min_len = min(branch_a.event_count, branch_b.event_count)
    for i in range(min_len):
        ea = branch_a.events[i]
        eb = branch_b.events[i]
        if (ea.event_type != eb.event_type
                and ea.event_type == EventType.STAGE_COMPLETED
                and eb.event_type == EventType.STAGE_COMPLETED
                and ea.payload.get("stage_name") != eb.payload.get("stage_name")):
            return False, (
                f"Conflicting stage completions at sequence {i}: "
                f"{ea.payload.get('stage_name')} vs {eb.payload.get('stage_name')}"
            )

    return True, "Branches are mergeable"


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _structural_hash(event: ExecutionEvent) -> str:
    """Hash of event structure (type + payload), excluding identity fields.
    Two events with same type and payload will have the same structural hash
    even if they have different event_ids, execution_ids, or branch_ids."""
    import hashlib
    # Normalize payload: exclude branch_id (metadata, not structural)
    payload = dict(event.payload)
    payload.pop("branch_id", None)
    parts = [
        event.event_type,
        json_dumps_stable(payload),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def json_dumps_stable(obj: dict) -> str:
    """Deterministic JSON serialization with sorted keys."""
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _status_for_event(event_type: str) -> str:
    """Derive lifecycle status string from event type."""
    status_map = {
        EventType.EXECUTION_STARTED: "RUNNING",
        EventType.STAGE_STARTED: "RUNNING",
        EventType.STAGE_COMPLETED: "RUNNING",
        EventType.STAGE_FAILED: "FAILED",
        EventType.EXECUTION_COMPLETED: "COMPLETED",
        EventType.EXECUTION_FAILED: "FAILED",
        EventType.EXECUTION_CRASHED: "CRASHED",
        EventType.RETRY_INCREMENTED: "RUNNING",
        EventType.EVENT_RECORDED: "RUNNING",
        EventType.FORK_CREATED: "RUNNING",
        EventType.REPLAY_STARTED: "RUNNING",
        EventType.REPLAY_COMPLETED: "RUNNING",
    }
    return status_map.get(event_type, "UNKNOWN")


def build_timeline(events: Tuple[ExecutionEvent, ...]) -> Tuple[TimelinePoint, ...]:
    """Build a TimelinePoint sequence from an event stream."""
    points: list[TimelinePoint] = []
    current_state = ExecutionState(
        execution_id=events[0].execution_id if events else ""
    )

    for event in events:
        current_state = _apply_event_light(current_state, event)
        points.append(TimelinePoint(
            sequence=event.sequence,
            event_type=event.event_type,
            event_id=event.event_id,
            timestamp=event.timestamp,
            stage_name=event.payload.get("stage_name", ""),
            status=current_state.status if current_state else "",
            state_fingerprint=current_state.fingerprint() if current_state else "",
        ))

    return tuple(points)


def _apply_event_light(es: ExecutionState, event: ExecutionEvent) -> ExecutionState:
    """Lightweight event application (duplicated from events.py to avoid circular import)."""
    # Re-use the reduce logic — this is a convenience wrapper
    return reduce_execution_state(
        (ExecutionEvent(
            event_id="__sentinel__",
            execution_id=es.execution_id or event.execution_id,
            timestamp="",
            sequence=0,
            event_type=EventType.EXECUTION_STARTED,
        ), event),
        es.execution_id,
    ) if es.status == "" else _apply_single(es, event)


def _apply_single(es: ExecutionState, event: ExecutionEvent) -> ExecutionState:
    """Apply a single event. Avoids full reduce overhead."""
    from v3.kernel.execution_state import ExecutionState as ES
    etype = event.event_type
    p = event.payload

    if etype == EventType.STAGE_STARTED:
        return es.start_stage(p.get("stage_name", ""))
    elif etype == EventType.STAGE_COMPLETED:
        return es.advance(p.get("stage_name", ""), p.get("result"), p.get("duration_ms", 0))
    elif etype == EventType.STAGE_FAILED:
        return es.fail(p.get("stage_name", ""), p.get("error", ""))
    elif etype == EventType.EXECUTION_COMPLETED:
        return es.complete()
    elif etype == EventType.EXECUTION_FAILED:
        return es.fail(p.get("stage_name", ""), p.get("error", ""))
    elif etype == EventType.EXECUTION_CRASHED:
        return es.crash()
    elif etype == EventType.RETRY_INCREMENTED:
        return es.increment_retry()
    elif etype == EventType.EVENT_RECORDED:
        return es.increment_event()
    return es
