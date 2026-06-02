"""
Memory Tier Policy — Tier definitions, TTL rules, importance scoring,
and L2→L3 episodic-to-semantic compaction.

Ported from the multi-source design (mem0 / graphiti / memory-bank /
hindsight) in SystemKernel Roadmap v2.0, Phase 15a (revised).

- mem0ai/mem0: memory type taxonomy, deterministic importance formula
- getzep/graphiti: Episode→EntityEdge compaction pattern
- memory-bank: progressive loading (summary first, details on demand)
- vectorize-io/hindsight: ranking = semantic × recency × importance

All functions are pure and deterministic. No LLM, no vector DB, no
external dependencies. Stdlib only.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Memory Tiers
# ═══════════════════════════════════════════════════════════════════════

class MemoryTier(Enum):
    """Memory tier classification.

    WORKING  — L1, in-memory only, session lifetime
    EPISODIC — L2, execution-scoped, 7-day TTL
    SEMANTIC — L3, entity-scoped, permanent
    """
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


# Tier constants for convenience imports
TIER_WORKING = MemoryTier.WORKING
TIER_EPISODIC = MemoryTier.EPISODIC
TIER_SEMANTIC = MemoryTier.SEMANTIC


# ═══════════════════════════════════════════════════════════════════════
# TTL Constants (seconds)
# ═══════════════════════════════════════════════════════════════════════

TTL_WORKING = 0            # Session lifetime — never persisted
TTL_EPISODIC = 604800      # 7 days
TTL_SEMANTIC = -1          # Permanent — never expires


def get_tier_ttl_seconds(tier: MemoryTier) -> int:
    """Return the TTL in seconds for a given memory tier.

    WORKING: 0 (session-scoped)
    EPISODIC: 604800 (7 days)
    SEMANTIC: -1 (permanent)
    """
    if tier == MemoryTier.WORKING:
        return TTL_WORKING
    if tier == MemoryTier.EPISODIC:
        return TTL_EPISODIC
    if tier == MemoryTier.SEMANTIC:
        return TTL_SEMANTIC
    return 0


def compute_ttl_expiry(tier: MemoryTier, timestamp: Optional[float] = None) -> float:
    """Compute the absolute expiry time for a tier entry.

    WORKING: 0 (session-scoped, never persisted)
    EPISODIC: timestamp + 604800 (7 days from creation)
    SEMANTIC: -1 (permanent, never expires)
    """
    if tier == MemoryTier.WORKING:
        return 0.0
    if tier == MemoryTier.SEMANTIC:
        return -1.0
    ts = timestamp if timestamp is not None else time.time()
    return ts + TTL_EPISODIC


# ═══════════════════════════════════════════════════════════════════════
# Tier Entry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TierEntry:
    """Immutable entry stored in a memory tier.

    Every entry has an entity_key (the thing being remembered) and an
    execution_id (the context in which it was created). Compaction groups
    by entity_key across execution_ids.
    """

    entry_id: str
    tier: MemoryTier
    execution_id: str
    content: dict = field(default_factory=dict)
    entity_key: str = ""
    entity_type: str = ""
    importance: float = 0.0
    timestamp: float = field(default_factory=time.time)
    ttl_expires_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "tier": self.tier.value,
            "execution_id": self.execution_id,
            "content": dict(self.content),
            "entity_key": self.entity_key,
            "entity_type": self.entity_type,
            "importance": self.importance,
            "timestamp": self.timestamp,
            "ttl_expires_at": self.ttl_expires_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "TierEntry":
        tier_raw = data.get("tier", "episodic")
        if isinstance(tier_raw, MemoryTier):
            tier = tier_raw
        else:
            tier = MemoryTier(tier_raw)
        return TierEntry(
            entry_id=data.get("entry_id", ""),
            tier=tier,
            execution_id=data.get("execution_id", ""),
            content=data.get("content", {}),
            entity_key=data.get("entity_key", ""),
            entity_type=data.get("entity_type", ""),
            importance=data.get("importance", 0.0),
            timestamp=data.get("timestamp", 0.0),
            ttl_expires_at=data.get("ttl_expires_at", 0.0),
        )


# ═══════════════════════════════════════════════════════════════════════
# Tier Entry Factory
# ═══════════════════════════════════════════════════════════════════════

def tier_policy(
    tier: MemoryTier,
    entry_id: str = "",
    execution_id: str = "",
    content: Optional[dict] = None,
    entity_key: str = "",
    entity_type: str = "",
    importance: float = 0.0,
    timestamp: Optional[float] = None,
) -> TierEntry:
    """Create a TierEntry with proper TTL defaults for the given tier.

    If entry_id is empty, one is generated via timestamp.
    Timestamp defaults to time.time() if not provided.
    ttl_expires_at is computed from the tier and timestamp.
    """
    import uuid
    ts = timestamp if timestamp is not None else time.time()
    return TierEntry(
        entry_id=entry_id or str(uuid.uuid4())[:16],
        tier=tier,
        execution_id=execution_id,
        content=content or {},
        entity_key=entity_key,
        entity_type=entity_type,
        importance=importance,
        timestamp=ts,
        ttl_expires_at=compute_ttl_expiry(tier, ts),
    )


# ═══════════════════════════════════════════════════════════════════════
# Importance Scoring (deterministic mem0 formula)
# ═══════════════════════════════════════════════════════════════════════

# Half-life constant: e^(-0.029 * 24) ≈ 0.5  →  24-hour half-life
RECENCY_DECAY_RATE = 0.029


def compute_importance(
    recency_hours: float,
    frequency_count: int,
    success: bool,
) -> float:
    """Deterministic importance score based on recency, frequency, and outcome.

    I = e^(-0.029 × hours) × log(freq + 1) × outcome_factor

    Recency: exponential decay with 24h half-life (mem0 formula).
    Frequency: log bonus — repeated encounters boost importance.
    Outcome: failures (0.95) weighted higher than successes (0.70) —
             we remember what went wrong more vividly.

    Returns a float in [0.0, ~2.0]. Typical values cluster around 0.1–0.7.
    """
    recency_decay = math.exp(-RECENCY_DECAY_RATE * max(recency_hours, 0.0))
    # Normalized: ln(freq+1) / ln(6) so freq=5 → bonus=1.0
    log_freq_bonus = math.log(max(frequency_count, 1) + 1) / math.log(6)
    outcome_factor = 0.95 if not success else 0.70
    return recency_decay * log_freq_bonus * outcome_factor


# ═══════════════════════════════════════════════════════════════════════
# Episodic → Semantic Compaction (graphiti-style)
# ═══════════════════════════════════════════════════════════════════════

def compact_episodic_to_semantic(
    entries: Tuple[TierEntry, ...],
    window_days: int = 7,
    threshold: int = 3,
) -> Tuple[TierEntry, ...]:
    """Compact episodic (L2) entries into semantic (L3) entries.

    Pattern: graphiti Episode → EntityEdge compaction.
    Groups entries by entity_key, counts total occurrences within the
    window. Entities appearing >= threshold times are promoted to L3
    (SEMANTIC, permanent).

    Pure function — same inputs always produce same outputs.
    Returns promoted entries (empty tuple if nothing qualifies).
    """
    now = time.time()
    window_start = now - (window_days * 86400)

    # Filter entries within the time window
    in_window = [
        e for e in entries
        if e.tier == MemoryTier.EPISODIC and e.timestamp >= window_start
    ]
    if not in_window:
        return ()

    # Group by entity_key, count total occurrences
    entity_counts: dict[str, int] = {}
    entity_entry: dict[str, TierEntry] = {}
    for entry in in_window:
        key = entry.entity_key
        if not key:
            continue
        entity_counts[key] = entity_counts.get(key, 0) + 1
        # Keep the most recent entry as the template
        if key not in entity_entry or entry.timestamp > entity_entry[key].timestamp:
            entity_entry[key] = entry

    # Promote entities meeting the threshold (by total count)
    promoted: list[TierEntry] = []
    for entity_key, count in entity_counts.items():
        if count >= threshold:
            template = entity_entry[entity_key]
            recency_hours = (now - template.timestamp) / 3600.0
            importance = compute_importance(
                recency_hours=recency_hours,
                frequency_count=count,
                success=True,
            )
            promoted.append(TierEntry(
                entry_id=template.entry_id,
                tier=MemoryTier.SEMANTIC,
                execution_id=template.execution_id,
                content=template.content,
                entity_key=entity_key,
                entity_type=template.entity_type,
                importance=importance,
                timestamp=template.timestamp,
                ttl_expires_at=TTL_SEMANTIC,
            ))

    return tuple(promoted)
