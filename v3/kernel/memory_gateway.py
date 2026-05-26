"""
MemoryGateway — Kernel-side Memory Isolation Boundary.

This is the ONLY interface between kernel and the memory subsystem.

Rules:
  - ZERO dependency on mem0, graphiti, or any external memory library
  - ZERO LLM calls
  - Protocol definition ONLY — no implementation
  - Event-driven: kernel writes events, memory subsystem consumes them
  - Removable: if no backend is connected, events are no-ops
  - Deterministic: same execution → same events emitted

Public API: write() + read() only.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.kernel.memory_contract import (
        MemoryWriteRequest, MemoryWriteResult,
        MemoryReadRequest, MemoryReadResult,
    )
    from v3.kernel.memory_candidate import MemoryCandidate


# ═══════════════════════════════════════════════════════════════════════
# Memory Event Protocol
# ═══════════════════════════════════════════════════════════════════════

class MemoryEventType(Enum):
    WRITE = "write"
    UPDATE = "update"
    DELETE = "delete"
    QUERY = "query"
    QUERY_RESULT = "query_result"


class MemoryEventSource(Enum):
    EXECUTION_ENGINE = "execution_engine"
    EVENT_BUS = "event_bus"
    TASK_SYSTEM = "task_system"
    ADAPTER = "adapter"


@dataclass(frozen=True)
class MemoryEvent:
    """Unified memory event emitted by kernel."""
    event_id: str
    timestamp: str
    type: MemoryEventType
    source: MemoryEventSource
    source_stage: str
    execution_id: str
    payload: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "type": self.type.value,
            "source": self.source.value,
            "source_stage": self.source_stage,
            "execution_id": self.execution_id,
            "payload": self.payload,
        }, ensure_ascii=False)


@dataclass(frozen=True)
class MemoryQuery:
    """Query sent through the gateway (kernel → memory)."""
    query_id: str
    query_text: str
    top_k: int = 10
    min_score: float = 0.5
    filters: dict = field(default_factory=dict)
    timestamp: str = ""


@dataclass(frozen=True)
class MemoryQueryResult:
    """Query result returned through the gateway (memory → kernel)."""
    query_id: str
    entries: Tuple[dict, ...]
    scores: Tuple[float, ...]
    duration_ms: int = 0


# ═══════════════════════════════════════════════════════════════════════
# Memory Gateway — simplified: write() + read()
# ═══════════════════════════════════════════════════════════════════════

MemoryEventHandler = Callable[[MemoryEvent], None]
MemoryQueryHandler = Callable[[MemoryQuery], Optional[MemoryQueryResult]]


class MemoryGateway:
    """Kernel-side memory isolation boundary.

    Public API is two methods:
      - write() — emit a memory event, fan out to connected adapters
      - read()  — query the memory system, returns results or None

    Adapters connect via connect() which wires both event and query handlers.
    """

    def __init__(self):
        self._handlers: list[MemoryEventHandler] = []
        self._query_handler: Optional[MemoryQueryHandler] = None
        self._event_count: int = 0

    # ── Public API ──────────────────────────────────────────────────

    def connect(self, adapter: Any) -> None:
        """Wire an adapter for both events and queries.

        Adapter must have handle_event(MemoryEvent) and handle_query(MemoryQuery).
        """
        if hasattr(adapter, "handle_event") and adapter.handle_event not in self._handlers:
            self._handlers.append(adapter.handle_event)
        if hasattr(adapter, "handle_query") and self._query_handler is None:
            self._query_handler = adapter.handle_query

    def write(
        self,
        event_type: MemoryEventType,
        source: MemoryEventSource,
        source_stage: str,
        execution_id: str,
        payload: Optional[dict] = None,
    ) -> None:
        """Emit a memory event. Non-blocking. No return. Never raises.

        Args:
            event_type: WRITE, UPDATE, DELETE, or QUERY
            source: Which kernel subsystem
            source_stage: Pipeline stage name
            execution_id: trace_id from execution engine
            payload: Arbitrary data
        """
        try:
            event = MemoryEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc).isoformat(),
                type=event_type,
                source=source,
                source_stage=source_stage,
                execution_id=execution_id,
                payload=payload or {},
            )
            self._event_count += 1

            for handler in self._handlers:
                try:
                    handler(event)
                except Exception:
                    pass
        except Exception:
            pass

    def write_candidates(
        self,
        candidates: "Tuple[MemoryCandidate, ...]",
    ) -> "Tuple[Any, ...]":
        """Write a batch of MemoryCandidates through the gateway.

        Each candidate is converted to a MemoryWriteRequest and dispatched.
        Returns a tuple of MemoryWriteResult (or empty tuple if no backend).

        This is the recommended path for memory writes: compute candidates
        via project_candidates(), then pass them here.
        """
        from v3.kernel.memory_contract import (
            MemoryWriteRequest, MemoryWriteResult, empty_write_result,
        )

        if not candidates:
            return ()

        results: list[MemoryWriteResult] = []
        for c in candidates:
            req = MemoryWriteRequest(
                request_id=c.candidate_id,
                execution_id=c.execution_id,
                candidate_type=c.candidate_type,
                content=c.content,
                context=c.context,
                priority=c.priority,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            result = self.write_request(req)
            results.append(result)

        return tuple(results)

    def write_request(
        self,
        request: "MemoryWriteRequest",
    ) -> "MemoryWriteResult":
        """Write a single MemoryWriteRequest through the gateway.

        Returns MemoryWriteResult. If no backend is connected, returns
        an empty result (accepted=False, reason="no_backend").
        """
        from v3.kernel.memory_contract import MemoryWriteResult, empty_write_result

        self._event_count += 1

        if not self._handlers:
            return empty_write_result(request.request_id)

        # Emit as legacy MemoryEvent for backward compat
        try:
            event = MemoryEvent(
                event_id=request.request_id,
                timestamp=request.timestamp or datetime.now(timezone.utc).isoformat(),
                type=MemoryEventType.WRITE,
                source=MemoryEventSource.EXECUTION_ENGINE,
                source_stage=request.candidate_type,
                execution_id=request.execution_id,
                payload={
                    "candidate_type": request.candidate_type,
                    "content": request.content,
                    "context": request.context,
                    "priority": request.priority,
                },
            )
        except Exception:
            return MemoryWriteResult(
                request_id=request.request_id,
                accepted=False,
                reason="event_construction_failed",
            )

        accepted = False
        for handler in self._handlers:
            try:
                handler(event)
                accepted = True
            except Exception:
                pass

        return MemoryWriteResult(
            request_id=request.request_id,
            accepted=accepted,
            reason="stored" if accepted else "handler_error",
        )

    def read_request(
        self,
        request: "MemoryReadRequest",
    ) -> "MemoryReadResult":
        """Read through the gateway using a formal MemoryReadRequest.

        Returns MemoryReadResult. If no backend is connected, returns
        empty result (entries=(), backend="none").
        """
        from v3.kernel.memory_contract import MemoryReadResult, empty_read_result

        if self._query_handler is None:
            return empty_read_result(request.query_id)

        try:
            q = MemoryQuery(
                query_id=request.query_id,
                query_text=request.query_text,
                top_k=request.top_k,
                min_score=request.min_score,
                filters=request.filters,
                timestamp=request.timestamp or datetime.now(timezone.utc).isoformat(),
            )
            result = self._query_handler(q)
        except Exception:
            return MemoryReadResult(
                query_id=request.query_id,
                backend="error",
                metadata={"error": "query_handler_raised"},
            )

        if result is None:
            return MemoryReadResult(
                query_id=request.query_id,
                backend="none",
                metadata={"status": "handler_returned_none"},
            )

        return MemoryReadResult(
            query_id=request.query_id,
            entries=result.entries,
            scores=result.scores,
            duration_ms=result.duration_ms,
            backend="connected",
            metadata={"backend": "connected"},
        )

    def read(
        self,
        query_text: str,
        top_k: int = 10,
        min_score: float = 0.5,
        filters: Optional[dict] = None,
    ) -> Optional[MemoryQueryResult]:
        """Query the memory system. Returns None if no backend connected."""
        if self._query_handler is None:
            return None
        try:
            q = MemoryQuery(
                query_id=str(uuid.uuid4()),
                query_text=query_text,
                top_k=top_k,
                min_score=min_score,
                filters=filters or {},
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            return self._query_handler(q)
        except Exception:
            return None

    # ── Introspection (read-only) ───────────────────────────────────

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def is_connected(self) -> bool:
        return self._query_handler is not None
