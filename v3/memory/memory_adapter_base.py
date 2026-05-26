"""
MemoryAdapter — Unified interface for external memory backends.

This is the interface that ALL memory backends (mem0, graphiti, custom)
MUST implement.

Design:
  - Kernel NEVER imports this directly
  - Kernel talks to MemoryGateway (kernel/memory_gateway.py)
  - MemoryGateway delegates to MemoryAdapter
  - Adapter is initialized OUTSIDE kernel and subscribes to gateway

Lifecycle:
  1. Adapter.connect() → verify backend is available
  2. Adapter handles MemoryEvents from gateway
  3. Adapter responds to MemoryQuery from gateway
  4. Adapter.close() → clean shutdown
"""

from __future__ import annotations

import sys
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

# MemoryAdapter needs types from kernel's memory_gateway
# This is the ONE allowed cross-boundary import (protocol types only, not implementation)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.memory_gateway import MemoryEvent, MemoryQuery, MemoryQueryResult


# ═══════════════════════════════════════════════════════════════════════
# MemoryAdapter — Abstract Base
# ═══════════════════════════════════════════════════════════════════════

class MemoryAdapter(ABC):
    """Abstract interface for external memory backends.

    Concrete implementations:
      - InProcessMemoryAdapter  (default, zero deps, in `memory/memory_service.py`)
      - Mem0Adapter             (integrations/mem0_adapter/)
      - GraphitiAdapter         (integrations/graphiti_adapter/)

    All implementations are OUTSIDE kernel boundary.
    LLM usage is allowed in adapter implementations but isolated to this layer.
    """

    def __init__(self, name: str):
        self._name = name
        self._connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the backend. Returns True on success."""
        ...

    @abstractmethod
    def handle_event(self, event: MemoryEvent) -> bool:
        """Process a memory event (WRITE/UPDATE/DELETE).

        Called by MemoryGateway when kernel emits an event.
        Returns True on success.
        May use LLM for extraction/summarization (backend-specific).
        """
        ...

    @abstractmethod
    def handle_query(self, query: MemoryQuery) -> Optional[MemoryQueryResult]:
        """Process a memory query.

        Called by MemoryGateway when kernel queries memory.
        MUST be deterministic — ZERO LLM at query time.
        Returns None if no results.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Clean shutdown of backend connection."""
        ...

    @property
    def name(self) -> str:
        return self._name

    @property
    def connected(self) -> bool:
        return self._connected


# ═══════════════════════════════════════════════════════════════════════
# InProcessMemoryAdapter — Default (zero external deps)
# ═══════════════════════════════════════════════════════════════════════

class InProcessMemoryAdapter(MemoryAdapter):
    """In-process memory adapter. No external dependencies. Always available.

    Used as the default backend. Swap in Mem0Adapter or GraphitiAdapter
    for persistent/vector/graph memory in Phase 2+.
    """

    def __init__(self):
        super().__init__("in_process")
        self._store: dict[str, dict] = {}

    def connect(self) -> bool:
        self._connected = True
        return True

    def handle_event(self, event: MemoryEvent) -> bool:
        if not self._connected:
            return False
        if event.type.value in ("write", "update"):
            self._store[event.event_id] = {
                "event_id": event.event_id,
                "type": event.type.value,
                "source_stage": event.source_stage,
                "execution_id": event.execution_id,
                "payload": event.payload,
                "timestamp": event.timestamp,
            }
        elif event.type.value == "delete":
            # Delete by execution_id match (simple)
            to_delete = [k for k, v in self._store.items()
                         if v.get("execution_id") == event.execution_id]
            for k in to_delete:
                del self._store[k]
        return True

    def handle_query(self, query: MemoryQuery) -> Optional[MemoryQueryResult]:
        if not self._connected:
            return None
        # Simple substring match (placeholder until vector search)
        results = []
        for entry in self._store.values():
            payload = entry.get("payload", {})
            content = payload.get("content", "")
            if query.query_text.lower() in content.lower():
                results.append((entry, 0.8))
        results = results[:query.top_k]
        if not results:
            return None
        return MemoryQueryResult(
            query_id=query.query_id,
            entries=tuple(r[0] for r in results),
            scores=tuple(r[1] for r in results),
            duration_ms=0,
        )

    def close(self) -> None:
        self._store.clear()
        self._connected = False
