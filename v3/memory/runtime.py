"""
MemoryRuntime — Unified facade for the complete memory pipeline.

Phase 4D-6: Ties together all Phase 4D-1 through 4D-5 modules into a
single, callable runtime. External callers go through one entry point.

Pipeline:
  Events → Candidates → Episodic Store → Semantic Index → Recall → Compaction → System Report

Every stage is optional and can be disabled via config. All operations are
deterministic. Memory is a pure projection — events remain source of truth.

Properties:
  - Single facade: one call to ingest_events() runs the full pipeline
  - Configurable: each stage can be enabled/disabled independently
  - Deterministic: same inputs + same config = same runtime_hash
  - Projection only: all outputs derive from events
  - Removable: delete v3/memory/ → kernel unchanged
  - Zero LLM: no AI imports, no embeddings, no external services
  - Stdlib only: no mem0, graphiti, langchain, vector DB
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

from v3.kernel.memory_contract import MemoryWriteRequest, MemoryWriteResult, MemoryReadRequest
from v3.kernel.memory_candidate import MemoryCandidate, project_candidates

if TYPE_CHECKING:
    from v3.kernel.events import ExecutionEvent
    from v3.kernel.observability_graph import RuntimeGraph
    from v3.kernel.metrics import RuntimeMetrics
    from v3.kernel.telemetry import InvariantTelemetry
    from v3.memory.compaction import CompactionPolicy, CompactionResult


# ═══════════════════════════════════════════════════════════════════════
# MemoryRuntimeConfig
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryRuntimeConfig:
    """Configuration for the MemoryRuntime facade.

    Fields:
        store_path: Path to episodic JSONL store file
        compaction_path: Path to compaction projection file
        enable_index: Build semantic index after write
        enable_recall: Enable truth-linked recall
        enable_compaction: Run compaction after query pipeline
        compaction_policy: CompactionPolicy to use (default if None)
        deterministic: Enforce deterministic output (same inputs → same hash)
        auto_build_index: Automatically build index after each write
    """

    store_path: str = "v3/memory/data/episodes.jsonl"
    compaction_path: str = "v3/memory/data/compacted_projection.json"
    enable_index: bool = True
    enable_recall: bool = True
    enable_compaction: bool = True
    compaction_policy: Optional["CompactionPolicy"] = None
    deterministic: bool = True
    auto_build_index: bool = True

    def to_dict(self) -> dict:
        return {
            "store_path": self.store_path,
            "compaction_path": self.compaction_path,
            "enable_index": self.enable_index,
            "enable_recall": self.enable_recall,
            "enable_compaction": self.enable_compaction,
            "compaction_policy": self.compaction_policy.to_dict() if self.compaction_policy else {},
            "deterministic": self.deterministic,
            "auto_build_index": self.auto_build_index,
        }

    @staticmethod
    def from_dict(d: dict) -> "MemoryRuntimeConfig":
        from v3.memory.compaction import CompactionPolicy
        policy = None
        if d.get("compaction_policy"):
            policy = CompactionPolicy.from_dict(d["compaction_policy"])
        return MemoryRuntimeConfig(
            store_path=d.get("store_path", "v3/memory/data/episodes.jsonl"),
            compaction_path=d.get("compaction_path", "v3/memory/data/compacted_projection.json"),
            enable_index=d.get("enable_index", True),
            enable_recall=d.get("enable_recall", True),
            enable_compaction=d.get("enable_compaction", True),
            compaction_policy=policy,
            deterministic=d.get("deterministic", True),
            auto_build_index=d.get("auto_build_index", True),
        )

    @staticmethod
    def default() -> "MemoryRuntimeConfig":
        return MemoryRuntimeConfig()


# ═══════════════════════════════════════════════════════════════════════
# MemoryRuntimeResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryRuntimeResult:
    """Result of a full memory pipeline run.

    Fields:
        execution_id: ID of the processed execution
        candidates_count: Number of candidates projected
        written_count: Number of records written to store
        indexed_count: Number of index entries (tokens)
        recall_count: Number of recall results (if query executed)
        compacted_count: Number of compacted records
        integrity_status: "valid" | "partial" | "invalid"
        runtime_hash: Deterministic hash of this entire result
    """

    execution_id: str = ""
    candidates_count: int = 0
    written_count: int = 0
    indexed_count: int = 0
    recall_count: int = 0
    compacted_count: int = 0
    integrity_status: str = "valid"
    runtime_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "candidates_count": self.candidates_count,
            "written_count": self.written_count,
            "indexed_count": self.indexed_count,
            "recall_count": self.recall_count,
            "compacted_count": self.compacted_count,
            "integrity_status": self.integrity_status,
            "runtime_hash": self.runtime_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def compute_runtime_hash(result: MemoryRuntimeResult) -> str:
    """Deterministic hash of a MemoryRuntimeResult (excludes runtime_hash itself)."""
    parts = [
        result.execution_id,
        str(result.candidates_count),
        str(result.written_count),
        str(result.indexed_count),
        str(result.recall_count),
        str(result.compacted_count),
        result.integrity_status,
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# MemoryRuntime
# ═══════════════════════════════════════════════════════════════════════

class MemoryRuntime:
    """Unified memory facade — single entry point for the full pipeline.

    Usage:
        runtime = MemoryRuntime.from_paths(
            store_path="data/episodes.jsonl",
            compaction_path="data/compacted.json",
        )
        events = make_event(...)
        result = runtime.ingest_events(events)

        # Or step by step:
        candidates = project_candidates(events)
        runtime.write_candidates(candidates)
        runtime.build_index()
        bundle = runtime.recall("build error")
        compacted = runtime.compact()

        report = runtime.verify_all()

    All operations are optional — disable index/recall/compaction via config
    for lightweight usage. The store is always written (idempotent).
    """

    def __init__(self, config: MemoryRuntimeConfig):
        self._config = config
        self._store = _lazy_store(config.store_path)
        self._index = None
        self._compactor = None
        self._compaction_result: Optional[CompactionResult] = None
        self._last_candidates: Tuple[MemoryCandidate, ...] = ()
        self._last_result: Optional[MemoryRuntimeResult] = None

    @staticmethod
    def from_paths(
        store_path: str = "v3/memory/data/episodes.jsonl",
        compaction_path: str = "v3/memory/data/compacted_projection.json",
        enable_index: bool = True,
        enable_recall: bool = True,
        enable_compaction: bool = True,
    ) -> "MemoryRuntime":
        """Factory: create a MemoryRuntime from file paths."""
        config = MemoryRuntimeConfig(
            store_path=store_path,
            compaction_path=compaction_path,
            enable_index=enable_index,
            enable_recall=enable_recall,
            enable_compaction=enable_compaction,
        )
        return MemoryRuntime(config)

    # ── Full pipeline: ingest events ────────────────────────────────────

    def ingest_events(
        self,
        events: "Tuple[ExecutionEvent, ...]",
        graph: "Optional[RuntimeGraph]" = None,
        metrics: "Optional[RuntimeMetrics]" = None,
        telemetry: "Optional[InvariantTelemetry]" = None,
    ) -> MemoryRuntimeResult:
        """Run the full memory pipeline on an event stream.

        1. Project candidates from events
        2. Write each candidate as an episodic record
        3. Optionally build semantic index
        4. Optionally compact

        Returns MemoryRuntimeResult with counts and integrity status.
        """
        if not events:
            empty = MemoryRuntimeResult(
                execution_id="",
                candidates_count=0,
                written_count=0,
                integrity_status="valid",
            )
            rhash = compute_runtime_hash(empty)
            self._last_result = MemoryRuntimeResult(
                execution_id=empty.execution_id,
                candidates_count=empty.candidates_count,
                written_count=empty.written_count,
                runtime_hash=rhash,
            )
            return self._last_result

        eid = events[0].execution_id

        # Step 1: Project candidates
        candidates = project_candidates(events, graph, metrics, telemetry)
        self._last_candidates = candidates

        # Derive graph_hash from graph (or build it if not provided)
        from v3.kernel.observability_graph import build_graph as _build_graph
        _g = graph or _build_graph(events)
        _gh = _g.graph_hash

        # Step 2: Write to episodic store
        written = self._write_candidates_impl(candidates, graph_hash=_gh)

        # Step 3: Build index (if enabled)
        indexed = 0
        if self._config.enable_index and self._config.auto_build_index:
            indexed = self._build_index_impl()

        # Step 4: Compact (if enabled)
        compacted = 0
        if self._config.enable_compaction:
            comp_result = self._compact_impl()
            if comp_result is not None:
                compacted = comp_result.output_count

        # Determine integrity
        integrity = "valid"
        if written < len(candidates):
            integrity = "partial"

        result = MemoryRuntimeResult(
            execution_id=eid,
            candidates_count=len(candidates),
            written_count=written,
            indexed_count=indexed,
            compacted_count=compacted,
            integrity_status=integrity,
        )
        rhash = compute_runtime_hash(result)
        result = MemoryRuntimeResult(
            execution_id=result.execution_id,
            candidates_count=result.candidates_count,
            written_count=result.written_count,
            indexed_count=result.indexed_count,
            compacted_count=result.compacted_count,
            integrity_status=result.integrity_status,
            runtime_hash=rhash,
        )
        self._last_result = result
        return result

    # ── Write candidates ─────────────────────────────────────────────────

    def write_candidates(
        self,
        candidates: "Tuple[MemoryCandidate, ...]",
    ) -> int:
        """Write a tuple of MemoryCandidate objects to the episodic store.

        Returns the number of records accepted (written).
        """
        self._last_candidates = candidates
        return self._write_candidates_impl(candidates)

    def _write_candidates_impl(
        self,
        candidates: "Tuple[MemoryCandidate, ...]",
        graph_hash: str = "",
    ) -> int:
        """Internal: write candidates to store, return accepted count."""
        written = 0
        for c in candidates:
            c_ctx = dict(c.context)
            gh = c_ctx.get("graph_hash", graph_hash)
            event_ids = tuple(c_ctx.get("event_ids", []))
            if not event_ids:
                event_ids = (f"ev-{c.execution_id}-{c.candidate_type}",)

            req = MemoryWriteRequest(
                request_id=c.candidate_id,
                execution_id=c.execution_id,
                candidate_type=c.candidate_type,
                content=dict(c.content),
                priority=c.priority,
                context={
                    "candidate_context": c_ctx,
                    "source_sequences": list(c.source_sequences),
                    "graph_hash": gh,
                    "event_ids": list(event_ids),
                },
            )
            result = self._store.append(req)
            if result.accepted:
                written += 1
        return written

    # ── Build index ──────────────────────────────────────────────────────

    def build_index(self) -> int:
        """Build (or rebuild) the semantic index from the episodic store.

        Returns the number of tokens indexed.
        """
        return self._build_index_impl()

    def _build_index_impl(self) -> int:
        """Internal: build semantic index."""
        from v3.memory.semantic_index import SemanticMemoryIndex
        idx = SemanticMemoryIndex()
        count = idx.rebuild_from_store(self._store)
        self._index = idx
        return count

    # ── Retrieve ─────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10,
    ):
        """Search the semantic index and return results.

        If index hasn't been built yet, builds it automatically.
        Returns Tuple[SemanticSearchResult, ...].
        """
        if self._index is None:
            self._build_index_impl()

        if self._index is None:
            return ()

        return self._index.search(query=query, limit=limit, filters=filters)

    # ── Recall ───────────────────────────────────────────────────────────

    def recall(
        self,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ):
        """Execute truth-linked recall with full provenance.

        Returns a RecallBundle where each result carries provenance
        linking back to source events.
        """
        if not self._config.enable_recall:
            return None

        from v3.memory.recall import TruthLinkedRecallRuntime
        recall_rt = TruthLinkedRecallRuntime(self._store)
        return recall_rt.recall(
            query=query,
            filters=filters,
            limit=limit,
            min_score=min_score,
        )

    # ── Compact ──────────────────────────────────────────────────────────

    def compact(
        self,
        policy: "Optional[CompactionPolicy]" = None,
    ) -> "Optional[CompactionResult]":
        """Run deterministic compaction on the episodic store.

        Uses the policy from config or a default policy.
        Writes the compaction projection to disk if configured.

        Returns CompactionResult or None if compaction is disabled.
        """
        if not self._config.enable_compaction:
            return None
        return self._compact_impl(policy)

    def _compact_impl(
        self,
        policy: "Optional[CompactionPolicy]" = None,
    ) -> "Optional[CompactionResult]":
        """Internal: run compaction."""
        from v3.memory.compaction import MemoryCompactor, CompactionPolicy

        p = policy or self._config.compaction_policy or CompactionPolicy()
        compactor = MemoryCompactor()
        result = compactor.compact_store(self._store, p)

        if self._compactor is None:
            self._compactor = compactor

        # Write projection to disk
        if self._config.compaction_path:
            compactor.write_projection(self._config.compaction_path, result, p)

        self._compaction_result = result
        return result

    # ── Verify all ───────────────────────────────────────────────────────

    def verify_all(self) -> dict:
        """Run all integrity checks and return a unified system report dict.

        Checks:
          - Store integrity
          - Index integrity
          - Compaction integrity
          - Removability verdict
          - Projection-only verdict
          - Source-of-truth verdict
        """
        from v3.memory.system_report import generate_system_report
        return generate_system_report(
            store=self._store,
            index=getattr(self, "_index", None),
            compaction_result=self._compaction_result,
        )

    # ── Export summary ───────────────────────────────────────────────────

    def export_summary(self) -> dict:
        """Export a JSON-serializable summary of the runtime state.

        Includes: config, store stats, index stats, compaction stats,
        last result, integrity verdict.
        """
        store_records = self._store.list_records()
        store_integrity = self._store.verify_integrity()

        summary = {
            "runtime_config": self._config.to_dict(),
            "store": {
                "path": self._config.store_path,
                "record_count": len(store_records),
                "integrity_valid": store_integrity.get("valid", False),
            },
            "index": {
                "built": self._index is not None,
                "entries": self._index.entry_count if self._index else 0,
                "records": self._index.record_count if self._index else 0,
                "hash": self._index.index_hash if self._index else "",
            },
            "compaction": {
                "enabled": self._config.enable_compaction,
                "result_hash": self._compaction_result.result_hash if self._compaction_result else "",
                "output_count": self._compaction_result.output_count if self._compaction_result else 0,
            },
            "last_result": self._last_result.to_dict() if self._last_result else {},
            "integrity": self.verify_all(),
        }

        return summary

    # ── Introspection ───────────────────────────────────────────────────

    @property
    def store(self):
        return self._store

    @property
    def config(self) -> MemoryRuntimeConfig:
        return self._config

    @property
    def last_result(self) -> Optional[MemoryRuntimeResult]:
        return self._last_result

    @property
    def compaction_result(self) -> "Optional[CompactionResult]":
        return self._compaction_result

    @property
    def total_records(self) -> int:
        return self._store.record_count


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════

def _lazy_store(path: str):
    """Create an EpisodicMemoryStore, ensuring parent directories exist."""
    from v3.memory.episodic_store import EpisodicMemoryStore
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    return EpisodicMemoryStore(path)
