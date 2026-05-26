"""
Mem0Adapter — mem0 vector memory backend.

Implements MemoryAdapter interface.
OUTSIDE kernel boundary. LLM allowed (mem0 extraction pipeline).

Dependencies: pip install mem0ai, qdrant-client
Status: Phase 2 — adapter skeleton (backend wiring in Phase 2b)

Architecture:
  Kernel → MemoryGateway.emit()
         → MemoryGateway.subscriber
         → Mem0Adapter.handle_event()
         → mem0 Memory.add() / search()
"""

from __future__ import annotations

import sys
import os
from typing import Optional

# Adapter base is in memory/
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.memory.memory_adapter_base import MemoryAdapter
from v3.kernel.memory_gateway import MemoryEvent, MemoryQuery, MemoryQueryResult


class Mem0Adapter(MemoryAdapter):
    """mem0 vector memory adapter.

    Backend: Qdrant (vector) + SQLite (metadata)
    Write:  LLM-based extraction pipeline (mem0 internal)
    Read:   Vector similarity search (deterministic, no LLM)

    Config:
      {
        "vector_store": "qdrant",
        "vector_store_config": {"host": "localhost", "port": 6333},
        "embedder": "openai",
        "embedder_config": {"model": "text-embedding-3-small"},
        "history_db_path": "./v3/mem0_history.db",
      }
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__("mem0")
        self.config = config or {}
        self._client = None

    def connect(self) -> bool:
        """Connect to mem0 backend. Returns False if mem0 not installed."""
        try:
            from mem0 import Memory
            self._client = Memory.from_config({
                "vector_store": {
                    "provider": self.config.get("vector_store", "qdrant"),
                    "config": self.config.get("vector_store_config", {
                        "host": "localhost",
                        "port": 6333,
                    }),
                },
                "embedder": {
                    "provider": self.config.get("embedder", "openai"),
                    "config": self.config.get("embedder_config", {
                        "model": "text-embedding-3-small",
                    }),
                },
                "history_db_path": self.config.get(
                    "history_db_path", "./v3/mem0_history.db"
                ),
            })
            self._connected = True
            return True
        except ImportError:
            # mem0 not installed — adapter runs degraded
            self._connected = False
            return False
        except Exception:
            self._connected = False
            return False

    def handle_event(self, event: MemoryEvent) -> bool:
        """Write event to mem0 as a memory entry.

        WRITE/UPDATE events → mem0.add() with LLM extraction pipeline.
        DELETE events → mem0.delete() by metadata filter.
        """
        if not self._connected or self._client is None:
            return False
        try:
            payload = event.payload or {}
            content = payload.get("content", "") or self._event_to_text(event)
            metadata = payload.get("metadata", {})
            metadata["event_id"] = event.event_id
            metadata["execution_id"] = event.execution_id
            metadata["source_stage"] = event.source_stage

            if event.type.value in ("write", "update"):
                self._client.add(
                    messages=[{"role": "user", "content": content}],
                    user_id=metadata.get("thread_id", "default"),
                    metadata=metadata,
                )
            elif event.type.value == "delete":
                self._client.delete(
                    user_id=metadata.get("thread_id", "default"),
                    filters={"event_id": event.event_id},
                )
            return True
        except Exception:
            return False

    def handle_query(self, query: MemoryQuery) -> Optional[MemoryQueryResult]:
        """Query mem0. ZERO LLM — vector similarity search only."""
        if not self._connected or self._client is None:
            return None
        try:
            results = self._client.search(
                query=query.query_text,
                user_id=query.filters.get("thread_id", "default"),
                limit=query.top_k,
            )
            entries = []
            scores = []
            for r in results:
                entries.append({
                    "entry_id": r.get("id", ""),
                    "content": r.get("memory", ""),
                    "metadata": r.get("metadata", {}),
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
        """Close mem0 client connection."""
        self._client = None
        self._connected = False

    def _event_to_text(self, event: MemoryEvent) -> str:
        """Convert a memory event to text for mem0 storage."""
        return (
            f"[{event.source.value}/{event.source_stage}] "
            f"execution={event.execution_id[:8]} "
            f"payload={str(event.payload)[:500]}"
        )
