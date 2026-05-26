"""
MemoryService v3.0 — Unified memory abstraction over mem0 + graphiti.

OUTSIDE kernel boundary. LLM allowed for write operations.
Removable: delete this directory → kernel behavior unchanged.

Memory types:
  WORKING  — in-process dict, session lifetime, LIFO
  EPISODIC — mem0 vector store (Qdrant)
  SEMANTIC — graphiti knowledge graph (Neo4j/FalkorDB)

Communication:
  Write: EventBus → MemoryService.add()
  Read:  MemoryService.search() → deterministic query (zero LLM for query)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class MemoryType(Enum):
    WORKING = "working"      # ~10MB, session-lifetime, LIFO cache
    EPISODIC = "episodic"    # ~1GB, 7-day TTL, vector search
    SEMANTIC = "semantic"    # Unlimited, permanent, knowledge graph


@dataclass(frozen=True)
class MemoryEntry:
    entry_id: str
    memory_type: MemoryType
    content: str
    metadata: dict = field(default_factory=dict)
    timestamp: str = ""      # ISO-8601
    ttl_s: Optional[int] = None  # None = use default TTL


@dataclass(frozen=True)
class MemoryQuery:
    query: str
    memory_types: Tuple[MemoryType, ...] = (MemoryType.EPISODIC,)
    top_k: int = 10
    min_score: float = 0.5
    filters: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryResult:
    entries: Tuple[MemoryEntry, ...]
    scores: Tuple[float, ...]
    query_duration_ms: int = 0


class MemoryService(ABC):
    """Unified memory abstraction.

    Write: LLM allowed (mem0 extraction pipeline, graphiti entity resolution).
    Read:  ZERO LLM (deterministic search only).
    """

    @abstractmethod
    def add(self, entry: MemoryEntry) -> bool:
        """Store a memory entry. May trigger async LLM extraction."""
        ...

    @abstractmethod
    def search(self, query: MemoryQuery) -> MemoryResult:
        """Search memories. ZERO LLM — deterministic search only."""
        ...

    @abstractmethod
    def forget(self, entry_id: str) -> bool:
        """Remove a memory entry."""
        ...

    @abstractmethod
    def snapshot(
        self,
        memory_types: Tuple[MemoryType, ...] = (MemoryType.EPISODIC,),
    ) -> list[MemoryEntry]:
        """List all entries of given types."""
        ...


class InProcessMemoryService(MemoryService):
    """In-process memory implementation (no external deps).

    Used as default until mem0/graphiti adapters are wired (Phase 2).
    """

    def __init__(self):
        self._store: dict[str, MemoryEntry] = {}

    def add(self, entry: MemoryEntry) -> bool:
        self._store[entry.entry_id] = entry
        return True

    def search(self, query: MemoryQuery) -> MemoryResult:
        # Simple substring match (placeholder until vector search)
        results = []
        for entry in self._store.values():
            if entry.memory_type in query.memory_types:
                if query.query.lower() in entry.content.lower():
                    results.append((entry, 0.8))
        results = results[:query.top_k]
        entries = tuple(r[0] for r in results)
        scores = tuple(r[1] for r in results)
        return MemoryResult(entries=entries, scores=scores, query_duration_ms=0)

    def forget(self, entry_id: str) -> bool:
        if entry_id in self._store:
            del self._store[entry_id]
            return True
        return False

    def snapshot(
        self,
        memory_types: Tuple[MemoryType, ...] = (MemoryType.EPISODIC,),
    ) -> list[MemoryEntry]:
        return [e for e in self._store.values() if e.memory_type in memory_types]
