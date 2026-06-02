"""Context Tiering — L3 Context Management for SystemKernel v4.1.

Three-tier memory retrieval: Working (session) -> Episodic (7-day) -> Semantic (permanent).
Freeze-compatible. Stdlib only. No LLM. No vector DB.
"""

from v3.external.context_tiering.tier_policy import (
    MemoryTier, TIER_WORKING, TIER_EPISODIC, TIER_SEMANTIC,
    TierEntry, tier_policy, compact_episodic_to_semantic,
    compute_importance, get_tier_ttl_seconds,
)
from v3.external.context_tiering.tier_store import (
    TierStore, FileTierStore, create_tier_store,
)
from v3.external.context_tiering.tier_retrieval import (
    RetrievalResult, progressive_load, rank_by_relevance, retrieve_context,
)

__all__ = [
    "MemoryTier", "TIER_WORKING", "TIER_EPISODIC", "TIER_SEMANTIC",
    "TierEntry", "tier_policy", "compact_episodic_to_semantic",
    "compute_importance", "get_tier_ttl_seconds",
    "TierStore", "FileTierStore", "create_tier_store",
    "RetrievalResult", "progressive_load", "rank_by_relevance", "retrieve_context",
]
