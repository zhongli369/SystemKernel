"""
EpisodicMemoryAdapter — Gateway adapter for EpisodicMemoryStore.

Phase 4D-2: Bridges the kernel MemoryGateway protocol to the episodic store.
Implements handle_event() and handle_query() for gateway integration, plus
convenience methods for write_candidates, querying by execution_id,
candidate_type, and tag.

Lives OUTSIDE kernel/. Uses only memory_contract.py types for kernel interaction.
"""

from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

from v3.kernel.memory_contract import (
    MemoryWriteRequest, MemoryWriteResult,
    MemoryReadRequest, MemoryReadResult,
    empty_write_result, empty_read_result,
)
from v3.kernel.memory_gateway import MemoryEvent, MemoryQuery, MemoryQueryResult

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryStore, EpisodicMemoryRecord
    from v3.kernel.memory_candidate import MemoryCandidate
    from v3.kernel.memory_gateway import MemoryGateway


# ═══════════════════════════════════════════════════════════════════════
# EpisodicMemoryAdapter
# ═══════════════════════════════════════════════════════════════════════

class EpisodicMemoryAdapter:
    """Adapter that connects MemoryGateway to EpisodicMemoryStore.

    Implements the gateway protocol (handle_event, handle_query) for
    seamless integration with the kernel's MemoryGateway. Also provides
    direct contract-based methods for explicit write/read operations.

    Supports optional MemoryRetrievalRuntime for semantic index queries
    and TruthLinkedRecallRuntime for provenance-tracked recall.

    When retrieval is enabled, read operations use the semantic index.
    When recall is enabled, read operations use truth-linked recall.
    When both are disabled, the original store.read() behavior is used.

    Usage:
        store = EpisodicMemoryStore("data/episodes.jsonl")
        adapter = EpisodicMemoryAdapter(store)

        # With retrieval runtime (Phase 4D-3):
        adapter = EpisodicMemoryAdapter(store, use_retrieval=True)

        # With truth-linked recall (Phase 4D-4):
        adapter = EpisodicMemoryAdapter(store, use_recall=True)

        gateway.connect(adapter)

        # Or use directly:
        result = adapter.write_request(write_req)
        result = adapter.read_request(read_req)
    """

    def __init__(
        self,
        store: "EpisodicMemoryStore",
        use_retrieval: bool = False,
        use_recall: bool = False,
    ):
        self._store = store
        self._name = "episodic"
        self._connected = True
        self._retrieval: Optional[Any] = None
        self._recall: Optional[Any] = None

        if use_recall:
            from v3.memory.recall import TruthLinkedRecallRuntime
            self._recall = TruthLinkedRecallRuntime(store)
            self._name = "episodic+recall"
        elif use_retrieval:
            from v3.memory.retrieval import MemoryRetrievalRuntime
            self._retrieval = MemoryRetrievalRuntime(store)
            self._name = "episodic+semantic"

    # ── Gateway protocol (handle_event / handle_query) ─────────────────

    def connect(self) -> bool:
        self._connected = True
        return True

    def handle_event(self, event: MemoryEvent) -> bool:
        """Process a MemoryEvent from the gateway.

        Converts legacy MemoryEvent to MemoryWriteRequest and appends to store.
        """
        try:
            req = MemoryWriteRequest(
                request_id=event.event_id,
                execution_id=event.execution_id,
                candidate_type=event.source_stage,
                content=event.payload.get("content", event.payload),
                context=event.payload.get("context", {}),
                priority=event.payload.get("priority", 1),
                timestamp=event.timestamp,
            )
            result = self._store.append(req)
            return result.accepted
        except Exception:
            return False

    def handle_query(self, query: MemoryQuery) -> Optional[MemoryQueryResult]:
        """Process a MemoryQuery from the gateway.

        Uses recall runtime if configured, then retrieval, then store.read().
        """
        try:
            req = MemoryReadRequest(
                query_id=query.query_id,
                query_text=query.query_text,
                top_k=query.top_k,
                min_score=query.min_score,
                filters=query.filters,
            )
            if self._recall is not None:
                result = self._recall.recall_from_read_request(req)
            elif self._retrieval is not None:
                result = self._retrieval.read_request(req)
            else:
                result = self._store.read(req)
            if result.is_empty:
                return None
            return MemoryQueryResult(
                query_id=query.query_id,
                entries=result.entries,
                scores=result.scores,
                duration_ms=result.duration_ms,
            )
        except Exception:
            return None

    # ── Contract-based methods ────────────────────────────────────────

    def write_request(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        """Write a single MemoryWriteRequest to the store."""
        if not self._connected:
            return empty_write_result(request.request_id)
        return self._store.append(request)

    def read_request(self, request: MemoryReadRequest) -> MemoryReadResult:
        """Read from the store using a MemoryReadRequest.

        Uses recall runtime if configured, then retrieval, then store.read().
        """
        if not self._connected:
            return empty_read_result(request.query_id)
        if self._recall is not None:
            return self._recall.recall_from_read_request(request)
        if self._retrieval is not None:
            return self._retrieval.read_request(request)
        return self._store.read(request)

    def write_candidates(
        self, candidates: "Tuple[MemoryCandidate, ...]"
    ) -> "Tuple[MemoryWriteResult, ...]":
        """Write a batch of MemoryCandidates to the store.

        Each candidate is converted to a MemoryWriteRequest.
        """
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
            )
            results.append(self._store.append(req))

        return tuple(results)

    def query_by_execution_id(
        self, execution_id: str
    ) -> "Tuple[EpisodicMemoryRecord, ...]":
        """Query store for all records matching an execution_id."""
        return self._store.query_by_execution_id(execution_id)

    def query_by_candidate_type(
        self, candidate_type: str
    ) -> "Tuple[EpisodicMemoryRecord, ...]":
        """Query store for all records matching a candidate_type."""
        return self._store.query_by_candidate_type(candidate_type)

    def query_by_tag(self, tag: str) -> "Tuple[EpisodicMemoryRecord, ...]":
        """Query store for all records matching a tag."""
        return self._store.query_by_tag(tag)

    def list_all(self) -> "Tuple[EpisodicMemoryRecord, ...]":
        """Return all records in the store."""
        return self._store.list_records()

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def record_count(self) -> int:
        return self._store.record_count

    @property
    def store(self) -> "EpisodicMemoryStore":
        return self._store

    @property
    def retrieval(self) -> Optional[Any]:
        """Return the retrieval runtime, or None if not configured."""
        return self._retrieval

    @property
    def recall_runtime(self) -> Optional[Any]:
        """Return the recall runtime, or None if not configured."""
        return self._recall

    @property
    def has_retrieval(self) -> bool:
        """Whether retrieval runtime is configured."""
        return self._retrieval is not None

    @property
    def has_recall(self) -> bool:
        """Whether recall runtime is configured."""
        return self._recall is not None

    @property
    def retrieval_index_hash(self) -> str:
        """Return the retrieval index hash, or empty string."""
        if self._recall is not None:
            return self._recall.index_hash
        if self._retrieval is not None:
            return self._retrieval.index_hash
        return ""

    def close(self) -> None:
        self._connected = False
        self._retrieval = None
        self._recall = None
