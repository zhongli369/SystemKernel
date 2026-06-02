"""
Execution Hook — Lifecycle integration for context tiering.

Provides TierContextHook that captures execution lifecycle events and
writes them into the tiered memory store (L1 → L2 promotion).

Stdlib only. No LLM. No external dependencies.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from v3.external.context_tiering.tier_policy import (
    MemoryTier,
    TIER_WORKING,
    TIER_EPISODIC,
    TierEntry,
    tier_policy,
    compute_importance,
)
from v3.external.context_tiering.tier_store import FileTierStore


class TierContextHook:
    """Lifecycle hook that captures execution events into tiered memory.

    Usage:
        store = create_tier_store()
        hook = TierContextHook(store)

        # On stage start
        hook.on_stage_start("exec-01", "init")

        # On stage complete
        hook.on_stage_complete("exec-01", "init", {"ok": True, "duration_ms": 50})

        # Promote L1 → L2
        promoted = hook.flush("exec-01")
    """

    def __init__(self, store: Optional[FileTierStore] = None):
        from v3.external.context_tiering.tier_store import create_tier_store
        self._store = store or create_tier_store()

    @property
    def store(self) -> FileTierStore:
        return self._store

    def on_stage_start(self, execution_id: str, stage_name: str) -> TierEntry:
        """Create a WORKING memory entry when a stage begins.

        The entry is stored in-memory (L1 only). It will be promoted to
        episodic (L2) when the stage completes successfully.
        """
        entry = tier_policy(
            TIER_WORKING,
            execution_id=execution_id,
            content={
                "stage_name": stage_name,
                "status": "started",
                "started_at": time.time(),
            },
            entity_key=f"stage_{stage_name}",
            entity_type="execution_stage",
            importance=0.0,  # Updated on completion
        )
        self._store.save(entry)
        return entry

    def on_stage_complete(
        self,
        execution_id: str,
        stage_name: str,
        result: Optional[dict] = None,
    ) -> Optional[TierEntry]:
        """Update the WORKING entry with stage completion data.

        Sets status, duration, and success flag. The entry stays in L1
        until flush() promotes it to L2.
        """
        # Find the matching L1 entry
        l1_entries = self._store.load_by_tier(TIER_WORKING)
        for entry in l1_entries:
            content = entry.content
            if (entry.execution_id == execution_id and
                    content.get("stage_name") == stage_name and
                    content.get("status") == "started"):
                # Create updated entry with completion data
                result = result or {}
                duration_ms = result.get("duration_ms", 0)
                success = result.get("ok", result.get("success", True))
                recency_hours = 0.0  # Just completed
                importance = compute_importance(
                    recency_hours=recency_hours,
                    frequency_count=1,
                    success=success,
                )
                updated = TierEntry(
                    entry_id=entry.entry_id,
                    tier=TIER_WORKING,
                    execution_id=execution_id,
                    content={
                        "stage_name": stage_name,
                        "status": "completed",
                        "started_at": content.get("started_at", 0),
                        "completed_at": time.time(),
                        "duration_ms": duration_ms,
                        "success": success,
                        **(result or {}),
                    },
                    entity_key=f"stage_{stage_name}",
                    entity_type="execution_stage",
                    importance=importance,
                    timestamp=time.time(),
                    ttl_expires_at=0.0,  # Still WORKING until flush
                )
                self._store.save(updated)
                return updated
        return None

    def flush(self, execution_id: str, min_importance: float = 0.0) -> int:
        """Promote WORKING entries to EPISODIC for an execution.

        All L1 entries matching the execution_id are promoted to L2.
        Entries with importance >= min_importance are persisted to disk.
        L1 entries are removed after promotion.

        Returns number of entries promoted.
        """
        return promote_working_to_episodic(
            self._store, execution_id, min_importance=min_importance,
        )


def promote_working_to_episodic(
    store: FileTierStore,
    execution_id: str,
    min_importance: float = 0.0,
) -> int:
    """Promote L1 (WORKING) entries to L2 (EPISODIC) for an execution.

    Each matching L1 entry is saved as an EPISODIC entry with proper TTL
    (7 days), then removed from L1.

    Entries with importance below min_importance are skipped (session ends,
    they're discarded).

    Returns number of entries promoted.
    """
    l1_entries = store.load_by_tier(TIER_WORKING)
    promoted = 0

    for entry in l1_entries:
        if entry.execution_id != execution_id:
            continue
        if entry.importance < min_importance:
            continue

        # Create EPISODIC copy
        episodic = TierEntry(
            entry_id=entry.entry_id,
            tier=TIER_EPISODIC,
            execution_id=entry.execution_id,
            content=dict(entry.content),
            entity_key=entry.entity_key,
            entity_type=entry.entity_type,
            importance=entry.importance,
            timestamp=entry.timestamp,
            ttl_expires_at=entry.timestamp + 604800,  # 7 days
        )
        store.save(episodic)
        promoted += 1

    # Remove promoted AND skipped entries from L1
    # (all execution-scoped L1 entries are cleaned up on flush)
    _remove_l1_entries(store, execution_id)

    return promoted


def _remove_l1_entries(store: FileTierStore, execution_id: str) -> None:
    """Remove all L1 entries for an execution from the in-memory store."""
    l1_dict = store._l1_store
    to_remove = [
        eid for eid, e in l1_dict.items()
        if e.execution_id == execution_id
    ]
    for eid in to_remove:
        del l1_dict[eid]
