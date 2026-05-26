"""
Truth-Linked Recall — Auditable memory recall with full provenance.

Phase 4D-4: Wraps MemoryRetrievalRuntime to attach a provenance chain
to every recall result. Each result can be independently verified and
traced back through the memory stack to source events.

Recall vs Retrieval:
  - Retrieval returns search results with scores
  - Recall returns the same results PLUS provenance, explanation, and
    integrity verification — making every result auditable

Chain: RecallResult → EpisodicMemoryRecord → MemoryCandidate → source events

All hashes (recall_hash, bundle_hash) are deterministic. All provenance
is independently verifiable. Recall is a projection — never a truth source.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

from v3.kernel.memory_contract import MemoryReadRequest, MemoryReadResult
from v3.memory.semantic_index import SemanticSearchResult
from v3.memory.provenance import (
    RecallProvenance,
    extract_provenance,
    verify_provenance,
    verify_provenance_chain,
    compute_provenance_hash,
)

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryStore, EpisodicMemoryRecord
    from v3.memory.retrieval import MemoryRetrievalRuntime


# ═══════════════════════════════════════════════════════════════════════
# RecallResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RecallResult:
    """A single recall result with full provenance and explanation.

    Fields:
        memory_id: Episodic memory record ID
        content: The record's content dict
        score: Relevance score from semantic search
        matched_tokens: Which query tokens matched
        provenance: Full traceability chain
        explanation: Human-readable scoring breakdown
        recall_hash: Deterministic hash of this recall result
    """

    memory_id: str
    content: dict
    score: float
    matched_tokens: Tuple[str, ...]
    provenance: RecallProvenance
    explanation: dict = field(default_factory=dict)
    recall_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "content": dict(self.content),
            "score": self.score,
            "matched_tokens": list(self.matched_tokens),
            "provenance": self.provenance.to_dict(),
            "explanation": dict(self.explanation),
            "recall_hash": self.recall_hash,
        }

    @staticmethod
    def from_dict(d: dict) -> "RecallResult":
        return RecallResult(
            memory_id=d.get("memory_id", ""),
            content=d.get("content", {}),
            score=d.get("score", 0.0),
            matched_tokens=tuple(d.get("matched_tokens", [])),
            provenance=RecallProvenance.from_dict(d.get("provenance", {})),
            explanation=d.get("explanation", {}),
            recall_hash=d.get("recall_hash", ""),
        )


# ═══════════════════════════════════════════════════════════════════════
# RecallBundle
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RecallBundle:
    """A complete recall response including query, results, and integrity.

    Fields:
        query: The original query text
        results: Tuple of RecallResult
        total: Total results count
        bundle_hash: Deterministic hash of the entire bundle
        integrity_status: "valid" | "partial" | "invalid"
    """

    query: str
    results: Tuple[RecallResult, ...]
    total: int
    bundle_hash: str = ""
    integrity_status: str = "valid"

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total": self.total,
            "bundle_hash": self.bundle_hash,
            "integrity_status": self.integrity_status,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Hash functions
# ═══════════════════════════════════════════════════════════════════════

def compute_recall_hash(result: RecallResult) -> str:
    """Deterministic hash of a recall result (excludes recall_hash itself)."""
    parts = [
        result.memory_id,
        json.dumps(result.content, sort_keys=True, ensure_ascii=False, default=str),
        str(result.score),
        "|".join(sorted(result.matched_tokens)),
        result.provenance.provenance_hash,
        json.dumps(result.explanation, sort_keys=True, ensure_ascii=False, default=str),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def compute_bundle_hash(bundle: RecallBundle) -> str:
    """Deterministic hash of a recall bundle (excludes bundle_hash itself)."""
    parts = [
        bundle.query,
        "|".join(r.recall_hash for r in bundle.results),
        str(bundle.total),
        bundle.integrity_status,
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# TruthLinkedRecallRuntime
# ═══════════════════════════════════════════════════════════════════════

class TruthLinkedRecallRuntime:
    """Recall runtime that wraps retrieval with provenance tracking.

    Every recall() call returns a RecallBundle where each result carries
    a full provenance chain. Results are independently verifiable via
    verify_provenance() and verify_bundle().

    Usage:
        store = EpisodicMemoryStore("data/episodes.jsonl")
        recall = TruthLinkedRecallRuntime(store)
        bundle = recall.recall("build error")
        for result in bundle.results:
            assert recall.verify_provenance(result)

        # Or through the MemoryReadRequest interface:
        read_result = recall.recall_from_read_request(MemoryReadRequest(...))

    The recall runtime:
      - Builds a MemoryRetrievalRuntime (semantic index)
      - For each search result, extracts provenance from the source record
      - Builds explanation with matched tokens, score components, source linkage
      - Computes deterministic recall_hash and bundle_hash
      - Supports verification of individual results and entire bundles
    """

    def __init__(self, store: "EpisodicMemoryStore"):
        from v3.memory.retrieval import MemoryRetrievalRuntime
        self._store = store
        self._retrieval = MemoryRetrievalRuntime(store)
        self._recall_count: int = 0

    # ── Recall (primary API) ────────────────────────────────────────────

    def recall(
        self,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> RecallBundle:
        """Execute a recall query and return a RecallBundle with provenance.

        Args:
            query: Search query text
            filters: Optional filters (execution_id, candidate_type, tag, min_importance)
            limit: Max results to return
            min_score: Minimum score threshold

        Returns:
            RecallBundle with full provenance on every result.
        """
        self._recall_count += 1

        # Search via semantic index
        search_results = self._retrieval.index.search(
            query=query,
            limit=limit,
            filters=filters,
        )

        # Filter by min_score
        filtered = [r for r in search_results if r.score >= min_score]

        # Build RecallResult for each match
        results: list[RecallResult] = []
        for sr in filtered:
            record = self._store.get(sr.memory_id)
            if record is None:
                continue

            # Extract provenance from the source record
            provenance = extract_provenance(record)
            # Verify the provenance chain
            trace_valid = verify_provenance(provenance)
            # Rebuild with trace_valid set
            provenance = RecallProvenance(
                memory_id=provenance.memory_id,
                record_hash=provenance.record_hash,
                source_hash=provenance.source_hash,
                execution_id=provenance.execution_id,
                graph_hash=provenance.graph_hash,
                event_ids=provenance.event_ids,
                candidate_id=provenance.candidate_id,
                candidate_type=provenance.candidate_type,
                trace_valid=trace_valid,
                provenance_hash=provenance.provenance_hash,
            )

            # Build explanation
            explanation = self._build_explanation(query, sr, record)

            # Build recall result
            result = RecallResult(
                memory_id=sr.memory_id,
                content=dict(record.content),
                score=sr.score,
                matched_tokens=sr.matched_tokens,
                provenance=provenance,
                explanation=explanation,
            )

            # Compute recall hash
            rhash = compute_recall_hash(result)
            result = RecallResult(
                memory_id=result.memory_id,
                content=result.content,
                score=result.score,
                matched_tokens=result.matched_tokens,
                provenance=result.provenance,
                explanation=result.explanation,
                recall_hash=rhash,
            )

            results.append(result)

        # Determine integrity status
        if not results:
            integrity = "valid"  # Empty bundle is valid (no broken results)
        elif all(r.provenance.trace_valid for r in results):
            integrity = "valid"
        elif any(r.provenance.trace_valid for r in results):
            integrity = "partial"
        else:
            integrity = "invalid"

        bundle = RecallBundle(
            query=query,
            results=tuple(results),
            total=len(results),
            integrity_status=integrity,
        )

        # Compute bundle hash
        bhash = compute_bundle_hash(bundle)
        bundle = RecallBundle(
            query=bundle.query,
            results=bundle.results,
            total=bundle.total,
            bundle_hash=bhash,
            integrity_status=bundle.integrity_status,
        )

        return bundle

    def _build_explanation(
        self,
        query: str,
        search_result: "SemanticSearchResult",
        record: "EpisodicMemoryRecord",
    ) -> dict:
        """Build an explanation dict for a recall result."""
        return {
            "query": query,
            "matched_tokens": list(search_result.matched_tokens),
            "score": search_result.score,
            "score_components": {
                "token_match": {
                    "matched": list(search_result.matched_tokens),
                    "count": len(search_result.matched_tokens),
                },
                "candidate_type": search_result.candidate_type,
                "tags": list(search_result.tags),
            },
            "source_linkage": {
                "execution_id": record.execution_id,
                "graph_hash": record.graph_hash,
                "event_ids": list(record.event_ids),
                "source_hash": record.source_hash,
                "record_hash": record.record_hash,
            },
            "trace_valid": verify_provenance(extract_provenance(record)),
        }

    # ── Recall from MemoryReadRequest ────────────────────────────────────

    def recall_from_read_request(
        self,
        request: MemoryReadRequest,
    ) -> MemoryReadResult:
        """Execute a MemoryReadRequest and return MemoryReadResult.

        Uses recall() internally and formats results as MemoryReadResult
        with provenance metadata attached.
        """
        start = time.perf_counter()

        bundle = self.recall(
            query=request.query_text,
            filters=request.filters if request.filters else None,
            limit=request.top_k if request.top_k > 0 else 10,
            min_score=request.min_score,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)

        if not bundle.results:
            return MemoryReadResult(
                query_id=request.query_id,
                backend="recall",
                duration_ms=duration_ms,
                metadata={
                    "bundle_hash": bundle.bundle_hash,
                    "integrity_status": bundle.integrity_status,
                    "matched_results": 0,
                },
            )

        entries = tuple(r.to_dict() for r in bundle.results)
        scores = tuple(r.score for r in bundle.results)

        return MemoryReadResult(
            query_id=request.query_id,
            entries=entries,
            scores=scores,
            duration_ms=duration_ms,
            backend="recall",
            metadata={
                "bundle_hash": bundle.bundle_hash,
                "integrity_status": bundle.integrity_status,
                "matched_results": len(bundle.results),
                "total_records": self._store.record_count,
                "index_hash": self._retrieval.index_hash,
            },
        )

    # ── Verification ────────────────────────────────────────────────────

    def verify_provenance(self, result: RecallResult) -> bool:
        """Verify a single recall result's provenance chain."""
        return result.provenance.trace_valid and verify_provenance(result.provenance)

    def verify_result_against_record(self, result: RecallResult) -> dict:
        """Deep verification: check result provenance against the source record."""
        record = self._store.get(result.memory_id)
        if record is None:
            return {
                "checks": {"record_exists": False},
                "issues": ["record not found in store"],
                "valid": False,
                "provenance_hash": "",
            }
        return verify_provenance_chain(result.provenance, record)

    def verify_bundle(self, bundle: RecallBundle) -> bool:
        """Verify an entire recall bundle.

        Returns True if:
          - All results have valid provenance
          - Bundle hash matches recomputation
          - Integrity status is consistent with results
        """
        if not bundle.results:
            return True

        # All results must have valid provenance
        for r in bundle.results:
            if not self.verify_provenance(r):
                return False

        # Bundle hash must match
        expected_bhash = compute_bundle_hash(bundle)
        if bundle.bundle_hash != expected_bhash:
            return False

        # Integrity status must be consistent
        all_valid = all(r.provenance.trace_valid for r in bundle.results)
        any_valid = any(r.provenance.trace_valid for r in bundle.results)
        if all_valid and bundle.integrity_status != "valid":
            return False
        if not all_valid and any_valid and bundle.integrity_status != "partial":
            return False
        if not any_valid and bundle.integrity_status != "invalid":
            return False

        return True

    # ── Explain ─────────────────────────────────────────────────────────

    def explain_result(self, memory_id: str) -> Optional[dict]:
        """Get detailed explanation for a single result by memory_id."""
        record = self._store.get(memory_id)
        if record is None:
            return None
        provenance = extract_provenance(record)
        return {
            "memory_id": memory_id,
            "content": record.content,
            "provenance": provenance.to_dict(),
            "trace_valid": verify_provenance(provenance),
            "source_linkage": {
                "execution_id": record.execution_id,
                "graph_hash": record.graph_hash,
                "event_ids": list(record.event_ids),
                "source_hash": record.source_hash,
                "record_hash": record.record_hash,
                "candidate_id": record.candidate_id,
            },
        }

    def explain_query(self, query: str) -> dict:
        """Explain the retrieval side of a query (tokenization, matching)."""
        return self._retrieval.explain(query)

    # ── Rebuild ─────────────────────────────────────────────────────────

    def rebuild(self) -> int:
        """Rebuild the underlying retrieval index from the store."""
        return self._retrieval.rebuild()

    # ── Introspection ───────────────────────────────────────────────────

    @property
    def store(self) -> "EpisodicMemoryStore":
        return self._store

    @property
    def retrieval(self) -> "MemoryRetrievalRuntime":
        return self._retrieval

    @property
    def recall_count(self) -> int:
        return self._recall_count

    @property
    def index_hash(self) -> str:
        return self._retrieval.index_hash
