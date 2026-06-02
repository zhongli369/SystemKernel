"""
Tier Retrieval — Progressive loading with deterministic ranking.

Progressive loading follows the memory-bank pattern: consult L1 (working)
first, then L2 (episodic), then L3 (semantic). Short-circuit when enough
results are found — cheapest tier wins.

Ranking is deterministic (hindsight-inspired): score = text_match x
recency_decay x importance. No embedding model, no LLM, no randomness.
Uses Jaccard similarity for token overlap (no numpy needed).

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from v3.external.context_tiering.tier_policy import (
    MemoryTier,
    TierEntry,
    RECENCY_DECAY_RATE,
)
from v3.external.context_tiering.tier_store import (
    FileTierStore,
    create_tier_store,
)


# ═══════════════════════════════════════════════════════════════════════
# Retrieval Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RetrievalResult:
    """Result from a progressive load across memory tiers.

    entries         — deduplicated, ranked, best-first
    scores          — parallel tuple of relevance scores
    tiers_consulted — which tiers were actually searched (e.g. ("L1", "L2"))
    duration_ms     — wall-clock duration of the retrieval (integer ms)
    query           — the original query string
    """

    entries: Tuple[TierEntry, ...] = ()
    scores: Tuple[float, ...] = ()
    tiers_consulted: Tuple[str, ...] = ()
    duration_ms: int = 0
    query: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Text Match Scoring (Jaccard similarity — deterministic, no numpy)
# ═══════════════════════════════════════════════════════════════════════

def _content_to_text(content: dict) -> str:
    """Flatten a content dict to a single searchable string."""
    parts: list[str] = []
    for key, value in content.items():
        if isinstance(value, str):
            parts.append(key)
            parts.append(value)
        elif isinstance(value, (int, float, bool)):
            parts.append(key)
            parts.append(str(value))
        elif isinstance(value, (list, tuple)):
            parts.append(key)
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
    return " ".join(parts)


def _tokenize(text: str) -> set[str]:
    """Simple whitespace + punctuation tokenization.

    Splits on whitespace and common punctuation, lowercases,
    and filters out tokens shorter than 2 characters.
    """
    for ch in ".,;:!?()[]{}'\"<>-/\\|@#$%^&*+=~`":
        text = text.replace(ch, " ")
    tokens = text.lower().split()
    return {t for t in tokens if len(t) >= 2}


def _jaccard_similarity(entry: TierEntry, query_tokens: set[str]) -> float:
    """Jaccard similarity between query tokens and entry content tokens.

    score = |query_tokens  entry_tokens| / |query_tokens  entry_tokens|

    Returns 0.0 if no overlap or both sets empty, 1.0 if identical.
    No numpy needed — pure set operations.
    """
    if not query_tokens:
        return 0.0
    entry_text = _content_to_text(entry.content)
    entry_text += f" {entry.entity_key} {entry.entity_type}"
    entry_tokens = _tokenize(entry_text)

    intersection = len(query_tokens & entry_tokens)
    union = len(query_tokens | entry_tokens)
    if union == 0:
        return 0.0
    return intersection / union


# ═══════════════════════════════════════════════════════════════════════
# Relevance Ranking (deterministic)
# ═══════════════════════════════════════════════════════════════════════

def rank_by_relevance(
    entries: Tuple[TierEntry, ...],
    query: str,
) -> Tuple[Tuple[TierEntry, ...], Tuple[float, ...]]:
    """Rank entries by deterministic relevance score.

    score = token_overlap(entry, query) x recency_decay x importance

    - token_overlap: Jaccard similarity (lowercase token set  / )
    - recency_decay: e^(-0.029 x hours_ago), half-life = 24h
    - importance: entry.importance (from tier_policy.compute_importance)

    Returns (sorted_entries, sorted_scores) both descending by score.
    Entries with score 0.0 are excluded.
    All functions are pure given the same inputs.
    """
    if not entries or not query.strip():
        return entries, tuple(0.0 for _ in entries)

    query_tokens = _tokenize(query)
    now = time.time()

    scored: list[tuple[TierEntry, float]] = []
    for entry in entries:
        jaccard = _jaccard_similarity(entry, query_tokens)
        if jaccard <= 0.0:
            continue

        hours_ago = max((now - entry.timestamp) / 3600.0, 0.0)
        recency = math.exp(-RECENCY_DECAY_RATE * hours_ago)
        importance = max(entry.importance, 0.01)

        score = jaccard * recency * importance
        if score > 0.0:
            scored.append((entry, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return (
        tuple(e for e, _ in scored),
        tuple(round(s, 6) for _, s in scored),
    )


# ═══════════════════════════════════════════════════════════════════════
# Progressive Load
# ═══════════════════════════════════════════════════════════════════════

def progressive_load(
    query: str,
    store: FileTierStore,
    *,
    max_results: int = 20,
    min_score: float = 0.1,
) -> RetrievalResult:
    """Progressive tier loading — cheapest tier first, short-circuit.

    Strategy "l1_first":
      1. Check L1 (WORKING). Rank results. If enough above min_score, return.
      2. Check L2 (EPISODIC). Rank results.
      3. Check L3 (SEMANTIC). Rank results.
      4. Merge L2 + L3, deduplicate by entry_id, filter by min_score,
         truncate to max_results.

    All ranking is deterministic. No LLM, no random.
    """
    t0 = time.time()
    tiers_consulted: list[str] = []

    # Phase 1: L1 — working memory (fastest, short-circuit)
    l1_entries = store.load_by_tier(MemoryTier.WORKING)
    if l1_entries:
        l1_ranked, l1_scores = rank_by_relevance(l1_entries, query)
        l1_filtered = _filter_by_score(l1_ranked, l1_scores, min_score)
        if l1_filtered[0]:
            tiers_consulted.append("L1")
            duration = int((time.time() - t0) * 1000)
            return RetrievalResult(
                entries=_truncate(l1_filtered[0], max_results),
                scores=_truncate(l1_filtered[1], max_results),
                tiers_consulted=tuple(tiers_consulted),
                duration_ms=duration,
                query=query,
            )

    # Phase 2: L2 — episodic memory
    l2_entries = store.load_by_tier(MemoryTier.EPISODIC)
    l2_ranked: Tuple[TierEntry, ...] = ()
    l2_scores: Tuple[float, ...] = ()
    if l2_entries:
        l2_ranked, l2_scores = rank_by_relevance(l2_entries, query)
        tiers_consulted.append("L2")

    # Phase 3: L3 — semantic memory
    l3_entries = store.load_by_tier(MemoryTier.SEMANTIC)
    l3_ranked: Tuple[TierEntry, ...] = ()
    l3_scores: Tuple[float, ...] = ()
    if l3_entries:
        l3_ranked, l3_scores = rank_by_relevance(l3_entries, query)
        tiers_consulted.append("L3")

    # Merge L2 + L3, deduplicate by entry_id
    merged_entries, merged_scores = _merge_dedup_with_scores(
        l2_ranked, l2_scores, l3_ranked, l3_scores,
    )

    # Filter by min_score and truncate
    filtered_entries, filtered_scores = _filter_by_score(
        merged_entries, merged_scores, min_score,
    )

    duration = int((time.time() - t0) * 1000)

    if not tiers_consulted:
        tiers_consulted.append("none")

    return RetrievalResult(
        entries=_truncate(filtered_entries, max_results),
        scores=_truncate(filtered_scores, max_results),
        tiers_consulted=tuple(tiers_consulted),
        duration_ms=duration,
        query=query,
    )


# ═══════════════════════════════════════════════════════════════════════
# Convenience wrapper
# ═══════════════════════════════════════════════════════════════════════

def retrieve_context(
    query: str,
    store: Optional[FileTierStore] = None,
    *,
    max_results: int = 20,
) -> RetrievalResult:
    """Convenience wrapper for progressive_load.

    Creates a default FileTierStore at ./v3/context_tiers/ if none provided.
    Empty store -> empty results (no crash).
    """
    if store is None:
        store = create_tier_store()
    return progressive_load(query=query, store=store, max_results=max_results)


# ═══════════════════════════════════════════════════════════════════════
# Merge + Filter + Truncate Helpers
# ═══════════════════════════════════════════════════════════════════════

def _merge_dedup_with_scores(
    entries_a: Tuple[TierEntry, ...],
    scores_a: Tuple[float, ...],
    entries_b: Tuple[TierEntry, ...],
    scores_b: Tuple[float, ...],
) -> Tuple[Tuple[TierEntry, ...], Tuple[float, ...]]:
    """Merge two ranked sequences, keeping first occurrence of each entry_id."""
    seen: set[str] = set()
    entries: list[TierEntry] = []
    scores: list[float] = []
    for e, s in zip(entries_a + entries_b, scores_a + scores_b):
        if e.entry_id not in seen:
            seen.add(e.entry_id)
            entries.append(e)
            scores.append(s)
    return tuple(entries), tuple(scores)


def _filter_by_score(
    entries: Tuple[TierEntry, ...],
    scores: Tuple[float, ...],
    min_score: float,
) -> Tuple[Tuple[TierEntry, ...], Tuple[float, ...]]:
    """Filter entries by minimum score threshold."""
    filtered_e: list[TierEntry] = []
    filtered_s: list[float] = []
    for e, s in zip(entries, scores):
        if s >= min_score:
            filtered_e.append(e)
            filtered_s.append(s)
    return tuple(filtered_e), tuple(filtered_s)


def _truncate(
    items: Tuple,
    max_results: int,
) -> Tuple:
    """Truncate a tuple to max_results items."""
    if len(items) <= max_results:
        return items
    return items[:max_results]
