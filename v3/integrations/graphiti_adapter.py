"""
GraphitiAdapter — temporal knowledge graph memory backend.

Implements MemoryAdapter interface.
OUTSIDE kernel boundary. LLM allowed (entity/edge extraction).

Dependencies: pip install graphiti-core, falkordb (or neo4j)
Status: Phase 2 — adapter skeleton (backend wiring in Phase 2b)

Architecture:
  Kernel → MemoryGateway.emit()
         → MemoryGateway.subscriber
         → GraphitiAdapter.handle_event()
         → graphiti add_episode() / search()

Key feature: Bi-temporal edges (valid_at / invalid_at) preserve
historical fact lineage without data deletion.
"""

from __future__ import annotations

import sys
import os
from typing import Optional

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.memory.memory_adapter_base import MemoryAdapter
from v3.kernel.memory_gateway import MemoryEvent, MemoryQuery, MemoryQueryResult


class GraphitiAdapter(MemoryAdapter):
    """Temporal knowledge graph memory adapter.

    Backend: Neo4j or FalkorDB (graph database)
    Write:  Episode → entity extraction(LLM) → edge resolution → graph store
    Read:   Hybrid search: semantic + BM25 + graph traversal (zero LLM)

    Config:
      {
        "graph_db": "falkordb",    # falkordb | neo4j
        "db_uri": "redis://localhost:6379",
        "db_user": "",
        "db_password": "",
        "llm_model": "claude-haiku-4-5",  # for entity extraction (write only)
      }
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__("graphiti")
        self.config = config or {}
        self._client = None

    def connect(self) -> bool:
        """Connect to graphiti backend. Returns False if dependencies missing."""
        try:
            from graphiti_core import Graphiti
            db = self.config.get("graph_db", "falkordb")
            uri = self.config.get("db_uri", "redis://localhost:6379")

            self._client = Graphiti(
                uri=uri,
                user=self.config.get("db_user", ""),
                password=self.config.get("db_password", ""),
            )
            self._connected = True
            return True
        except ImportError:
            # graphiti not installed — adapter runs degraded
            self._connected = False
            return False
        except Exception:
            self._connected = False
            return False

    def handle_event(self, event: MemoryEvent) -> bool:
        """Write event to graphiti as an episode.

        Each kernel event becomes a graphiti Episode.
        Entity/edge extraction uses LLM (isolated to write path).
        """
        if not self._connected or self._client is None:
            return False
        try:
            from graphiti_core.types import EpisodeType

            payload = event.payload or {}
            content = payload.get("content", "") or self._event_to_text(event)
            episode_type = self._map_event_type(event.type.value)

            self._client.add_episode(
                name=f"kernel_{event.event_id[:8]}",
                content=content,
                source=EpisodeType.message,
                group_id=payload.get("metadata", {}).get(
                    "thread_id", "default"
                ),
            )
            return True
        except Exception:
            return False

    def handle_query(self, query: MemoryQuery) -> Optional[MemoryQueryResult]:
        """Query graphiti. ZERO LLM — hybrid semantic+BM25+graph search."""
        if not self._connected or self._client is None:
            return None
        try:
            results = self._client.search(
                query=query.query_text,
                group_ids=[query.filters.get("thread_id", "default")],
                num_results=query.top_k,
            )
            entries = []
            scores = []
            for r in results:
                entries.append({
                    "entry_id": r.get("uuid", ""),
                    "content": r.get("content", ""),
                    "metadata": {"entities": r.get("entities", []),
                                 "relationships": r.get("relationships", [])},
                    "score": r.get("score", 0.0),
                })
                scores.append(r.get("score", 0.0))
            if not entries:
                return None
            return MemoryQueryResult(
                query_id=query.query_id,
                entries=tuple(entries),
                scores=tuple(scores),
                duration_ms=0,
            )
        except Exception:
            return None

    def close(self) -> None:
        """Close graphiti client connection."""
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass
        self._client = None
        self._connected = False

    def _event_to_text(self, event: MemoryEvent) -> str:
        """Convert a kernel event to text for graphiti ingestion."""
        return (
            f"Kernel[{event.source.value}] Stage[{event.source_stage}] "
            f"Execution[{event.execution_id[:8]}] "
            f"Payload: {str(event.payload)[:1000]}"
        )

    def _map_event_type(self, event_type: str) -> str:
        mapping = {
            "write": "message",
            "update": "message",
            "delete": "text",
            "query": "text",
        }
        return mapping.get(event_type, "message")
