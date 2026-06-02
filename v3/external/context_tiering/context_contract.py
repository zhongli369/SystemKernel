"""
Context Contract — Formal interface between L3 Context Tiering and L4 Lifecycle.

Defines the contract: what execution stages need from context, and what the
context system can provide. ContextBroker is the single integration point.

Stdlib only. No LLM. No external dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Tuple

from v3.external.context_tiering.tier_policy import MemoryTier
from v3.external.context_tiering.tier_store import FileTierStore
from v3.external.context_tiering.tier_retrieval import (
    RetrievalResult,
    progressive_load,
)
from v3.external.context_tiering.execution_hook import (
    TierContextHook,
    promote_working_to_episodic,
)


@dataclass(frozen=True)
class ContextRequest:
    """Lifecycle → Context: what the execution stage needs.

    Args:
        stage_name: Name of the lifecycle stage (init, build, test, deploy...)
        query: Natural language description of needed context
        entity_types: Limit to specific entity types (empty = all)
        max_tokens: Token budget for this request
        min_importance: Minimum importance threshold
        required: If True, abort stage when no context found
    """
    stage_name: str
    query: str
    entity_types: Tuple[str, ...] = ()
    max_tokens: int = 4096
    min_importance: float = 0.0
    required: bool = False


@dataclass(frozen=True)
class ContextFulfillment:
    """Context → Lifecycle: what was retrieved."""
    request: ContextRequest
    result: RetrievalResult
    fulfilled: bool
    duration_ms: int


class ContextBroker:
    """Mediates between lifecycle stages and the tiered memory store.

    This is the ONLY integration point lifecycle code should use.
    Lifecycle creates ContextRequest objects, ContextBroker handles
    retrieval + recording transparently.

    Usage:
        broker = ContextBroker(store, hook)
        request = ContextRequest(stage_name="init", query="pipeline setup")
        fulfillment = broker.fulfill(request)
        if fulfillment.fulfilled:
            context = fulfillment.result.entries
        # ... execute stage ...
        broker.record_stage("exec-01", "init", {"ok": True, "duration_ms": 50})
        broker.flush_execution("exec-01")
    """

    def __init__(self, store: Optional[FileTierStore] = None,
                 hook: Optional[TierContextHook] = None):
        from v3.external.context_tiering.tier_store import create_tier_store
        self._store = store or create_tier_store()
        self._hook = hook or TierContextHook(self._store)

    @property
    def store(self) -> FileTierStore:
        return self._store

    @property
    def hook(self) -> TierContextHook:
        return self._hook

    def fulfill(self, request: ContextRequest) -> ContextFulfillment:
        """Execute retrieval against the tier store.

        If request.required and no results found, fulfilled=False.
        Lifecycle should check this before proceeding.
        """
        t0 = time.time()
        result = progressive_load(
            query=request.query,
            store=self._store,
            max_results=20,
            min_score=0.0,
            max_tokens=request.max_tokens,
        )
        duration_ms = int((time.time() - t0) * 1000)
        fulfilled = len(result.entries) > 0

        if request.required and not fulfilled:
            return ContextFulfillment(
                request=request, result=result,
                fulfilled=False, duration_ms=duration_ms,
            )

        return ContextFulfillment(
            request=request, result=result,
            fulfilled=fulfilled, duration_ms=duration_ms,
        )

    def record_stage(self, execution_id: str, stage_name: str,
                     result: Optional[dict] = None) -> None:
        """After stage completion, write to memory via hook."""
        self._hook.on_stage_start(execution_id, stage_name)
        self._hook.on_stage_complete(execution_id, stage_name, result)

    def flush_execution(self, execution_id: str,
                        min_importance: float = 0.0) -> int:
        """Promote all working entries to episodic."""
        return self._hook.flush(execution_id, min_importance=min_importance)
