"""
MemoryRetrievalRuntime — Retrieval layer using SemanticMemoryIndex.

Phase 4D-3: Wraps the semantic index for structured read operations.
Handles MemoryReadRequest with filtering, scoring, and result formatting.

Phase 4D-5: Optional support for compacted projections. When use_compacted=True
and a compaction projection file exists, the index is built from compacted
records instead of raw episodic records. Default behavior is unchanged.

Lives OUTSIDE kernel/. Does not depend on ExecutionEngine.
Does not affect kernel.run(). Can rebuild index from store at any time.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Optional, Tuple, TYPE_CHECKING

from v3.kernel.memory_contract import MemoryReadRequest, MemoryReadResult
from v3.memory.semantic_index import SemanticMemoryIndex, SemanticSearchResult

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryStore, EpisodicMemoryRecord
    from v3.memory.recall import RecallBundle


class MemoryRetrievalRuntime:
    """Retrieval runtime for querying episodic memory via the semantic index.

    Usage:
        store = EpisodicMemoryStore("data/episodes.jsonl")
        retrieval = MemoryRetrievalRuntime(store)
        result = retrieval.read_request(MemoryReadRequest(...))
        retrieval.rebuild()  # Rebuild index from store if needed

        # Optional: use compacted projection
        retrieval = MemoryRetrievalRuntime(store, use_compacted=True,
                                           compaction_path="data/compacted.json")

    The retrieval runtime:
      - Loads all records from the episodic store (or compacted projection)
      - Builds a SemanticMemoryIndex
      - Executes read_request() using the index
      - Returns MemoryReadResult with scores and entries
    """

    def __init__(
        self,
        store: "EpisodicMemoryStore",
        use_compacted: bool = False,
        compaction_path: str = "",
    ):
        self._store = store
        self._index = SemanticMemoryIndex()
        self._use_compacted = use_compacted
        self._compaction_path = compaction_path
        self._compaction_loaded: bool = False
        self._compacted_records: Tuple["EpisodicMemoryRecord", ...] = ()

        if use_compacted and compaction_path and os.path.exists(compaction_path):
            self._build_from_compaction()
        else:
            self._index.rebuild_from_store(store)

        self._rebuild_count: int = 1

    # ── Compaction support (Phase 4D-5) ─────────────────────────────────

    def _build_from_compaction(self) -> None:
        """Build semantic index from a compacted projection file.

        Loads the compaction projection, converts each CompactedMemoryRecord
        into an EpisodicMemoryRecord-like object, and builds the index.

        Falls back to store if the projection file is missing or invalid.
        """
        try:
            with open(self._compaction_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._index.rebuild_from_store(self._store)
            return

        compacted_list = data.get("compacted_records", [])
        if not compacted_list:
            self._index.rebuild_from_store(self._store)
            return

        records = self._compacted_to_episodic_records(compacted_list)
        self._compacted_records = tuple(records)
        self._compaction_loaded = True
        self._index.build(self._compacted_records)

    def _compacted_to_episodic_records(
        self,
        compacted_list: list,
    ) -> list:
        """Convert CompactedMemoryRecord dicts to EpisodicMemoryRecord objects.

        Each compacted record becomes one synthetic EpisodicMemoryRecord
        whose memory_id = compacted_id, and whose provenance fields come
        from the compacted record's source linkage.
        """
        from v3.memory.episodic_store import EpisodicMemoryRecord

        records: list[EpisodicMemoryRecord] = []
        for cd in compacted_list:
            source_memory_ids = cd.get("source_memory_ids", [])
            source_record_hashes = cd.get("source_record_hashes", [])
            source_hashes = cd.get("source_hashes", [])
            execution_ids = cd.get("execution_ids", [])
            graph_hashes = cd.get("graph_hashes", [])

            record = EpisodicMemoryRecord(
                memory_id=cd.get("compacted_id", ""),
                candidate_id=source_memory_ids[0] if source_memory_ids else "",
                execution_id=execution_ids[0] if execution_ids else "",
                event_ids=tuple(),
                graph_hash=graph_hashes[0] if graph_hashes else "",
                candidate_type=(
                    cd.get("candidate_types", ["unknown"])[0]
                    if cd.get("candidate_types")
                    else "unknown"
                ),
                content=cd.get("content", {}),
                importance=cd.get("importance", 1),
                tags=tuple(cd.get("tags", [])),
                created_at="",
                source_hash=source_hashes[0] if source_hashes else "",
                record_hash=source_record_hashes[0] if source_record_hashes else "",
            )
            records.append(record)
        return records

    def load_compaction(self, path: str) -> bool:
        """Load a compaction projection file and rebuild the index from it.

        Returns True if the projection was loaded successfully.
        """
        self._compaction_path = path
        self._use_compacted = True

        if not os.path.exists(path):
            return False

        self._build_from_compaction()
        return self._compaction_loaded

    def unload_compaction(self) -> None:
        """Revert to using the raw episodic store for index building."""
        self._use_compacted = False
        self._compaction_loaded = False
        self._compacted_records = ()
        self._index.rebuild_from_store(self._store)

    @property
    def use_compacted(self) -> bool:
        return self._use_compacted

    @property
    def compaction_loaded(self) -> bool:
        return self._compaction_loaded

    # ── Read ───────────────────────────────────────────────────────────

    def read_request(self, request: MemoryReadRequest) -> MemoryReadResult:
        """Execute a MemoryReadRequest using the semantic index.

        Supports filters:
          - execution_id: str
          - candidate_type: str
          - tag: str
          - min_importance: int

        Falls back to store.read() if index is not built.
        """
        start = time.perf_counter()

        if not self._index.is_built:
            if self._use_compacted and self._compaction_loaded:
                self._index.build(self._compacted_records)
            else:
                self._index.rebuild_from_store(self._store)

        results = self._index.search(
            query=request.query_text,
            limit=request.top_k if request.top_k > 0 else 10,
            filters=request.filters if request.filters else None,
        )

        # Filter by min_score
        filtered: list[SemanticSearchResult] = [
            r for r in results if r.score >= request.min_score
        ]

        duration_ms = int((time.perf_counter() - start) * 1000)

        backend = "semantic_compacted" if self._use_compacted else "semantic"

        if not filtered:
            return MemoryReadResult(
                query_id=request.query_id,
                backend=backend,
                duration_ms=duration_ms,
                metadata={
                    "index_hash": self._index.index_hash,
                    "total_indexed": self._index.entry_count,
                    "total_records": self._index.record_count,
                    "matched_results": 0,
                    "use_compacted": self._use_compacted,
                },
            )

        entries = tuple(self._result_to_entry(r) for r in filtered)
        scores = tuple(r.score for r in filtered)

        return MemoryReadResult(
            query_id=request.query_id,
            entries=entries,
            scores=scores,
            duration_ms=duration_ms,
            backend=backend,
            metadata={
                "index_hash": self._index.index_hash,
                "total_indexed": self._index.entry_count,
                "total_records": self._index.record_count,
                "matched_results": len(filtered),
                "use_compacted": self._use_compacted,
            },
        )

    def _result_to_entry(self, result: SemanticSearchResult) -> dict:
        """Convert a search result to a dict entry compatible with MemoryReadResult."""
        return {
            "memory_id": result.memory_id,
            "score": result.score,
            "matched_tokens": list(result.matched_tokens),
            "candidate_type": result.candidate_type,
            "tags": list(result.tags),
            "source_hash": result.source_hash,
            "record_hash": result.record_hash,
        }

    # ── Retrieve with provenance (Phase 4D-4) ──────────────────────────

    def retrieve_with_provenance(
        self,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> "RecallBundle":
        """Retrieve results with full provenance chains attached.

        This is the bridge between retrieval (Phase 4D-3) and recall (Phase 4D-4).
        It delegates to TruthLinkedRecallRuntime internally.

        Returns a RecallBundle where each result carries provenance linking
        back to source events.
        """
        from v3.memory.recall import TruthLinkedRecallRuntime
        recall = TruthLinkedRecallRuntime(self._store)
        return recall.recall(
            query=query,
            filters=filters,
            limit=limit,
            min_score=min_score,
        )

    # ── Rebuild ────────────────────────────────────────────────────────

    def rebuild(self) -> int:
        """Rebuild the semantic index from the episodic store (or compacted projection).

        Returns the number of tokens indexed.
        """
        self._rebuild_count += 1
        if self._use_compacted and self._compaction_loaded:
            return self._index.build(self._compacted_records)
        return self._index.rebuild_from_store(self._store)

    # ── Query helpers ──────────────────────────────────────────────────

    def explain(self, query: str) -> dict:
        """Explain a query's tokenization and matching process."""
        return self._index.explain(query)

    def get(self, memory_id: str) -> Optional[dict]:
        """Get a record by memory_id."""
        rec = self._store.get(memory_id)
        if rec is None:
            return None
        return rec.to_dict()

    # ── Introspection ──────────────────────────────────────────────────

    @property
    def index(self) -> SemanticMemoryIndex:
        return self._index

    @property
    def store(self) -> "EpisodicMemoryStore":
        return self._store

    @property
    def index_hash(self) -> str:
        return self._index.index_hash

    @property
    def rebuild_count(self) -> int:
        return self._rebuild_count
