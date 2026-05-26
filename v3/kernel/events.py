"""
Execution Events — Immutable event types for event-sourced runtime.

Every state transition in the execution engine is represented as a
frozen event. ExecutionState becomes a pure projection derived entirely
from event history via reduce_execution_state().

Zero LLM. Zero side effects. Pure functional reducers.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Event Type Constants
# ═══════════════════════════════════════════════════════════════════════

class EventType:
    EXECUTION_STARTED = "execution_started"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CRASHED = "execution_crashed"
    RETRY_INCREMENTED = "retry_incremented"
    EVENT_RECORDED = "event_recorded"
    FORK_CREATED = "fork_created"
    REPLAY_STARTED = "replay_started"
    REPLAY_COMPLETED = "replay_completed"

    ALL = {
        EXECUTION_STARTED, STAGE_STARTED, STAGE_COMPLETED, STAGE_FAILED,
        EXECUTION_COMPLETED, EXECUTION_FAILED, EXECUTION_CRASHED,
        RETRY_INCREMENTED, EVENT_RECORDED, FORK_CREATED,
        REPLAY_STARTED, REPLAY_COMPLETED,
    }


# ═══════════════════════════════════════════════════════════════════════
# ExecutionEvent — base frozen event
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExecutionEvent:
    """Immutable execution event. All state transitions are events.

    Fields:
        event_id: Unique identifier for this event
        execution_id: Which execution this event belongs to
        timestamp: ISO-8601 when event was created
        sequence: Monotonic counter within this execution
        event_type: One of EventType values
        payload: Event-specific data dict
        parent_event_id: Links to preceding event (for chain integrity)
        deterministic_hash: SHA-256 of event content (set after construction)
    """

    event_id: str
    execution_id: str
    timestamp: str
    sequence: int
    event_type: str
    payload: dict = field(default_factory=dict)
    parent_event_id: Optional[str] = None
    deterministic_hash: str = ""

    def with_hash(self) -> "ExecutionEvent":
        """Return a copy with deterministic_hash computed."""
        return ExecutionEvent(
            event_id=self.event_id,
            execution_id=self.execution_id,
            timestamp=self.timestamp,
            sequence=self.sequence,
            event_type=self.event_type,
            payload=dict(self.payload),
            parent_event_id=self.parent_event_id,
            deterministic_hash=compute_event_hash(self),
        )

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "payload": self.payload,
            "parent_event_id": self.parent_event_id,
            "deterministic_hash": self.deterministic_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Event factory functions (convenience constructors)
# ═══════════════════════════════════════════════════════════════════════

def make_event(
    execution_id: str,
    sequence: int,
    event_type: str,
    payload: Optional[dict] = None,
    parent_event_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> ExecutionEvent:
    """Create an ExecutionEvent with auto-generated event_id and hash."""
    evt = ExecutionEvent(
        event_id=str(uuid.uuid4()),
        execution_id=execution_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        sequence=sequence,
        event_type=event_type,
        payload=payload or {},
        parent_event_id=parent_event_id,
    )
    return evt.with_hash()


# ═══════════════════════════════════════════════════════════════════════
# Pure Functional Reducer
# ═══════════════════════════════════════════════════════════════════════

def reduce_execution_state(
    events: Tuple[ExecutionEvent, ...],
    target_execution_id: str = "",
) -> "ExecutionState":
    """Pure functional reducer: events -> ExecutionState.

    Takes an ordered tuple of ExecutionEvents and produces the
    corresponding ExecutionState projection. Fully deterministic:
    same events always produce the same ExecutionState.

    Must be importable from execution_state — use lazy import to
    avoid circular deps (events.py is a leaf module).
    """
    from v3.kernel.execution_state import ExecutionState, ExecutionStatus

    if not events:
        return ExecutionState(execution_id=target_execution_id or "")

    eid = target_execution_id or events[0].execution_id
    es = ExecutionState(execution_id=eid)

    for event in events:
        es = _apply_event(es, event)

    return es


def _apply_event(es: "ExecutionState", event: ExecutionEvent) -> "ExecutionState":
    """Apply a single event to an ExecutionState, returning new state."""
    from v3.kernel.execution_state import ExecutionState, ExecutionStatus

    etype = event.event_type
    payload = event.payload

    if etype == EventType.EXECUTION_STARTED:
        return es.start()

    elif etype == EventType.STAGE_STARTED:
        return es.start_stage(payload.get("stage_name", ""))

    elif etype == EventType.STAGE_COMPLETED:
        return es.advance(
            payload.get("stage_name", ""),
            payload.get("result"),
            payload.get("duration_ms", 0),
        )

    elif etype == EventType.STAGE_FAILED:
        return es.fail(
            payload.get("stage_name", ""),
            payload.get("error", ""),
        )

    elif etype == EventType.EXECUTION_COMPLETED:
        return es.complete()

    elif etype == EventType.EXECUTION_FAILED:
        return es.fail(
            payload.get("stage_name", ""),
            payload.get("error", ""),
        )

    elif etype == EventType.EXECUTION_CRASHED:
        return es.crash()

    elif etype == EventType.RETRY_INCREMENTED:
        return es.increment_retry()

    elif etype == EventType.EVENT_RECORDED:
        return es.increment_event()

    else:
        # Unknown event types are no-ops (forward compatibility)
        return es


# ═══════════════════════════════════════════════════════════════════════
# Event Hashing
# ═══════════════════════════════════════════════════════════════════════

def compute_event_hash(event: ExecutionEvent) -> str:
    """Deterministic SHA-256 hash of event content (excluding the hash itself)."""
    parts = [
        event.event_id,
        event.execution_id,
        event.timestamp,
        str(event.sequence),
        event.event_type,
        json_dumps_stable(event.payload),
        event.parent_event_id or "",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def json_dumps_stable(obj: dict) -> str:
    """Deterministic JSON serialization with sorted keys."""
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════
# Event Stream Validation
# ═══════════════════════════════════════════════════════════════════════

def validate_event_stream(
    events: Tuple[ExecutionEvent, ...]
) -> Tuple[bool, list[str]]:
    """Validate event stream integrity.

    Checks:
      - Sequences are monotonic and gapless
      - Parent chain is unbroken
      - All events share the same execution_id
      - Hashes are consistent
      - Stream starts with execution_started (if non-empty)

    Returns (is_valid, list_of_issues).
    """
    issues: list[str] = []

    if not events:
        return True, issues

    eid = events[0].execution_id

    # Check first event is execution_started
    if events[0].event_type != EventType.EXECUTION_STARTED:
        issues.append(
            f"Stream must start with execution_started, got {events[0].event_type}"
        )

    for i, event in enumerate(events):
        # Execution ID consistency
        if event.execution_id != eid:
            issues.append(
                f"Event {i}: execution_id mismatch {event.execution_id} != {eid}"
            )

        # Sequence monotonic
        if event.sequence != i:
            issues.append(
                f"Event {i}: expected sequence {i}, got {event.sequence}"
            )

        # Parent chain
        if i > 0 and event.parent_event_id:
            expected_parent = events[i - 1].event_id
            if event.parent_event_id != expected_parent:
                issues.append(
                    f"Event {i}: parent chain broken — "
                    f"expected {expected_parent}, got {event.parent_event_id}"
                )

        # Hash consistency (if hash is present)
        if event.deterministic_hash:
            expected_hash = compute_event_hash(event)
            if event.deterministic_hash != expected_hash:
                issues.append(
                    f"Event {i}: hash mismatch — "
                    f"stored={event.deterministic_hash}, computed={expected_hash}"
                )

        # Event type validity
        if event.event_type not in EventType.ALL:
            issues.append(
                f"Event {i}: unknown event_type '{event.event_type}'"
            )

    # Check terminal event
    if len(events) > 1:
        terminal = events[-1].event_type
        valid_terminals = {
            EventType.EXECUTION_COMPLETED,
            EventType.EXECUTION_FAILED,
            EventType.EXECUTION_CRASHED,
        }
        if terminal not in valid_terminals:
            issues.append(
                f"Stream must end with a terminal event, got {terminal}"
            )

    return len(issues) == 0, issues


def event_stream_fingerprint(events: Tuple[ExecutionEvent, ...]) -> str:
    """Deterministic fingerprint of an entire event stream."""
    parts = [
        f"{e.sequence}:{e.event_type}:{json_dumps_stable(e.payload)}"
        for e in events
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Event Parsing
# ═══════════════════════════════════════════════════════════════════════

def parse_event_from_dict(record: dict) -> ExecutionEvent:
    """Reconstruct an ExecutionEvent from a serialized dict."""
    return ExecutionEvent(
        event_id=record.get("event_id", ""),
        execution_id=record.get("execution_id", ""),
        timestamp=record.get("timestamp", ""),
        sequence=record.get("sequence", 0),
        event_type=record.get("event_type", ""),
        payload=record.get("payload", {}),
        parent_event_id=record.get("parent_event_id"),
        deterministic_hash=record.get("deterministic_hash", ""),
    )
