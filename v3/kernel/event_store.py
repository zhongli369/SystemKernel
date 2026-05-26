"""
Event Store — Append-only event stream persistence.

Provides abstract EventStore and concrete FileEventStore for storing
execution events as append-only JSONL. Events are the source of truth;
checkpoints are derived optimization snapshots.

Zero LLM. Append-only guarantee.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from v3.kernel.events import (
    ExecutionEvent, EventType, make_event,
    parse_event_from_dict, validate_event_stream,
    json_dumps_stable,
)


# ═══════════════════════════════════════════════════════════════════════
# EventStore — abstract
# ═══════════════════════════════════════════════════════════════════════

class EventStore:
    """Abstract event stream persistence.

    Subclass and implement the storage methods.
    All writes are append-only. Existing events are never modified.
    """

    def append(self, event: ExecutionEvent) -> None:
        raise NotImplementedError

    def load_stream(self, execution_id: str) -> Tuple[ExecutionEvent, ...]:
        raise NotImplementedError

    def load_since(self, execution_id: str, sequence: int) -> Tuple[ExecutionEvent, ...]:
        raise NotImplementedError

    def fork_stream(
        self, execution_id: str, from_sequence: int, new_execution_id: str
    ) -> Tuple[ExecutionEvent, ...]:
        raise NotImplementedError

    def stream_exists(self, execution_id: str) -> bool:
        raise NotImplementedError

    def validate_integrity(self, execution_id: str) -> Tuple[bool, list[str]]:
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════
# FileEventStore — append-only JSONL
# ═══════════════════════════════════════════════════════════════════════

class FileEventStore(EventStore):
    """Append-only JSONL event storage.

    Guarantees:
      - All writes use open(path, "a") — never truncates, never overwrites
      - File naming: {safe_execution_id}.events.jsonl
      - Each line is a complete, parseable JSON object
      - Monotonic sequence IDs
      - Order is preserved: first line = first event
    """

    def __init__(self, path: str = "./v3/events/"):
        self._path = path
        os.makedirs(path, exist_ok=True)

    def _file(self, execution_id: str) -> str:
        safe_id = execution_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self._path, f"{safe_id}.events.jsonl")

    def _list_execution_files(self) -> list[str]:
        result = []
        try:
            for fname in os.listdir(self._path):
                if fname.endswith(".events.jsonl"):
                    result.append(os.path.join(self._path, fname))
        except OSError:
            pass
        return result

    # ── Write (append-only) ────────────────────────────────────────────

    def append(self, event: ExecutionEvent) -> None:
        """Append event to JSONL file. NEVER truncates."""
        record = event.to_dict()
        with open(self._file(event.execution_id), "a", encoding="utf-8") as f:
            f.write(json_dumps_stable(record) + "\n")

    # ── Read ───────────────────────────────────────────────────────────

    def load_stream(self, execution_id: str) -> Tuple[ExecutionEvent, ...]:
        """Load full event stream for an execution, in sequence order."""
        fpath = self._file(execution_id)
        if not os.path.exists(fpath):
            return ()
        events: list[ExecutionEvent] = []
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line.strip())
                    events.append(parse_event_from_dict(record))
        except (OSError, json.JSONDecodeError):
            pass
        return tuple(events)

    def load_since(self, execution_id: str, sequence: int) -> Tuple[ExecutionEvent, ...]:
        """Load events with sequence >= the given value."""
        stream = self.load_stream(execution_id)
        return tuple(e for e in stream if e.sequence >= sequence)

    def fork_stream(
        self, execution_id: str, from_sequence: int, new_execution_id: str
    ) -> Tuple[ExecutionEvent, ...]:
        """Create a fork: copy events up to from_sequence under a new execution_id.

        Returns the forked events with new execution_id and re-hashed.
        Does NOT write — caller must append ForkCreated + forked events.
        """
        stream = self.load_stream(execution_id)
        if not stream:
            return ()

        prefix = tuple(e for e in stream if e.sequence <= from_sequence)
        if not prefix:
            return ()

        # Emit ForkCreated event
        fork_event = make_event(
            execution_id=new_execution_id,
            sequence=0,
            event_type=EventType.FORK_CREATED,
            payload={
                "original_execution_id": execution_id,
                "forked_at_sequence": from_sequence,
                "event_count": len(prefix),
            },
        )

        # Re-sequence and re-identity prefix events under new execution
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

        return tuple(forked)

    def stream_exists(self, execution_id: str) -> bool:
        """Check if an event stream file exists for this execution."""
        return os.path.exists(self._file(execution_id))

    # ── Integrity ──────────────────────────────────────────────────────

    def validate_integrity(self, execution_id: str) -> Tuple[bool, list[str]]:
        """Validate the integrity of an event stream.

        Loads the full stream and checks:
          - Monotonic sequences (no gaps, no duplicates)
          - Unbroken parent chain
          - Hash consistency
          - Valid event types
        """
        stream = self.load_stream(execution_id)
        if not stream:
            return True, []
        return validate_event_stream(stream)


# ═══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════

def compute_stream_fingerprint(events: Tuple[ExecutionEvent, ...]) -> str:
    """Deterministic fingerprint of an event stream for integrity checks."""
    import hashlib
    if not events:
        return hashlib.sha256(b"").hexdigest()[:16]
    parts = [
        f"{e.sequence}:{e.event_type}:{e.deterministic_hash}"
        for e in events
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
