"""
MemoryAdapterStub — No-op memory adapter. Always connected, stores nothing.

Phase 4D-1: Proves memory is fully removable. This adapter is the simplest
possible backend — it accepts writes (returning True) but stores zero data,
and returns empty results for all queries.

Use this to verify:
  - Kernel works identically with/without memory backend
  - Memory writes are advisory (failure is never an error)
  - Memory reads return empty gracefully
  - Events remain the sole source of truth

Lives OUTSIDE kernel/ boundary. LLM-capable but uses none.
"""

from __future__ import annotations

from typing import Optional

# Cross-boundary import: protocol types only (no kernel implementation)
from v3.kernel.memory_gateway import MemoryEvent, MemoryQuery, MemoryQueryResult


class MemoryAdapterStub:
    """No-op memory adapter. Satisfies the gateway protocol.

    Accepts all events (writes), returns empty for all queries.
    Always connected. Zero storage. Zero side effects.
    """

    def __init__(self):
        self._name = "stub"
        self._connected = True
        self._event_count = 0
        self._query_count = 0

    # ── Gateway protocol ──────────────────────────────────────────────

    def connect(self) -> bool:
        self._connected = True
        return True

    def handle_event(self, event: MemoryEvent) -> bool:
        """Accept all events. Store nothing. Always succeed."""
        self._event_count += 1
        return True

    def handle_query(self, query: MemoryQuery) -> Optional[MemoryQueryResult]:
        """Return empty — no data is ever stored."""
        self._query_count += 1
        return None

    def close(self) -> None:
        self._event_count = 0
        self._query_count = 0
        self._connected = False

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def query_count(self) -> int:
        return self._query_count
