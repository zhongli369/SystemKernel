"""
MemoryContract — Formal write/read contract between kernel and memory subsystem.

Phase 4D-1: Defines the protocol boundary. Kernel emits typed requests;
memory subsystem responds with typed results. No implementation here —
this is the interface specification only.

Rules:
  - ZERO dependency on mem0, graphiti, vector DBs, LLM SDK
  - ZERO file I/O, ZERO network calls
  - Events are the ONLY source of truth — memory is a cache/projection
  - All types are frozen (immutable, hashable)
  - Memory is removable — kernel MUST work with memory_backend=None
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# MemoryWriteRequest
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryWriteRequest:
    """A request from kernel → memory to store a candidate.

    Contains the full context needed for storage: the candidate data,
    the execution context (graph, metrics, telemetry), and metadata.
    Memory subsystem decides HOW to store — kernel only declares WHAT.

    Contract:
      - request_id is deterministic (derived from event stream)
      - same event stream → same request_id always
      - memory may accept or reject (rejection is not an error)
    """

    request_id: str
    execution_id: str
    candidate_type: str              # e.g. "execution_summary", "stage_error", "pipeline_result"
    content: dict                    # the actual data to store
    context: dict = field(default_factory=dict)  # graph/metrics/telemetry context
    priority: int = 0                # 0=background, 1=normal, 2=important
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "candidate_type": self.candidate_type,
            "content": dict(self.content),
            "context": dict(self.context),
            "priority": self.priority,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def compute_request_id(
        execution_id: str,
        candidate_type: str,
        content_keys: Tuple[str, ...],
    ) -> str:
        """Deterministic request_id from execution + type + content structure."""
        parts = [execution_id, candidate_type, "|".join(sorted(content_keys))]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# MemoryWriteResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryWriteResult:
    """Result from memory → kernel after a write attempt.

    accepted=True means the memory subsystem stored the candidate.
    accepted=False means it was dropped/ignored (e.g., no backend,
    duplicate, rate-limited). Either way, execution continues unchanged.
    """

    request_id: str
    accepted: bool
    reason: str = ""              # e.g. "stored", "no_backend", "duplicate", "rate_limited"
    storage_id: str = ""          # backend-specific ID if stored
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "accepted": self.accepted,
            "reason": self.reason,
            "storage_id": self.storage_id,
            "duration_ms": self.duration_ms,
        }


# ═══════════════════════════════════════════════════════════════════════
# MemoryReadRequest
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryReadRequest:
    """A request from kernel → memory to retrieve stored context.

    The kernel asks memory for relevant past execution context.
    Memory subsystem returns results or empty — kernel treats this
    as advisory only, never as truth.

    Contract:
      - query_id is unique per request
      - results are advisory (NOT authoritative)
      - empty results is always valid (graceful degradation)
    """

    query_id: str
    query_text: str
    query_type: str = "general"    # e.g. "general", "error_lookup", "stage_context"
    top_k: int = 10
    min_score: float = 0.5
    filters: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)   # current execution context for better retrieval
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "query_type": self.query_type,
            "top_k": self.top_k,
            "min_score": self.min_score,
            "filters": dict(self.filters),
            "context": dict(self.context),
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════════════
# MemoryReadResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryReadResult:
    """Result from memory → kernel after a read/query.

    entries and scores are parallel tuples. Empty tuples mean no results
    were found — this is always valid and MUST NOT cause errors.

    metadata contains backend-specific info (e.g., retrieval method,
    backend type, latency breakdown). For debugging only — kernel
    MUST NOT make decisions based on metadata.
    """

    query_id: str
    entries: Tuple[dict, ...] = ()
    scores: Tuple[float, ...] = ()
    duration_ms: int = 0
    backend: str = ""              # e.g. "none", "stub", "mem0", "graphiti"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "entries": list(self.entries),
            "scores": list(self.scores),
            "duration_ms": self.duration_ms,
            "backend": self.backend,
            "metadata": dict(self.metadata),
        }

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0


# ═══════════════════════════════════════════════════════════════════════
# Empty / No-op Results (singleton patterns for "no backend" case)
# ═══════════════════════════════════════════════════════════════════════

def empty_write_result(request_id: str) -> MemoryWriteResult:
    """Factory for "no backend connected" write result."""
    return MemoryWriteResult(
        request_id=request_id,
        accepted=False,
        reason="no_backend",
    )


def empty_read_result(query_id: str) -> MemoryReadResult:
    """Factory for "no backend connected" read result."""
    return MemoryReadResult(
        query_id=query_id,
        backend="none",
        metadata={"status": "no_backend_connected"},
    )


# ═══════════════════════════════════════════════════════════════════════
# Contract Invariants (documented, not enforced at runtime)
# ═══════════════════════════════════════════════════════════════════════

MEMORY_CONTRACT_INVARIANTS = (
    "1. Events are the ONLY source of truth — never memory",
    "2. Memory write failures MUST NOT affect execution",
    "3. Memory read results are ADVISORY only",
    "4. Empty read results are ALWAYS valid",
    "5. Same event stream → same write candidates (deterministic)",
    "6. Memory is removable — delete the memory/ directory and kernel still works",
    "7. Memory adapters live OUTSIDE kernel/ — kernel has zero impl deps",
    "8. Write/read contract uses frozen types — no mutation across boundary",
)


def compute_contract_hash() -> str:
    """Deterministic hash of the contract invariants (immutable)."""
    return hashlib.sha256(
        "|".join(MEMORY_CONTRACT_INVARIANTS).encode()
    ).hexdigest()[:16]
