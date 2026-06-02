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

import json
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
    total_tokens    — estimated token count of all returned entries
    """

    entries: Tuple[TierEntry, ...] = ()
    scores: Tuple[float, ...] = ()
    tiers_consulted: Tuple[str, ...] = ()
    duration_ms: int = 0
    query: str = ""
    total_tokens: int = 0


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


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union


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
# Token Estimation
# ═══════════════════════════════════════════════════════════════════════

def _estimate_tokens(entry: TierEntry) -> int:
    """Estimate token count for a TierEntry.

    Simple heuristic: serialize content dict to JSON, divide by 4
    (rough approximation: 1 token ≈ 4 characters). Add overhead for
    metadata fields (entry_id, entity_key, entity_type).

    Stdlib only. No tokenizer dependency.
    """
    try:
        content_str = json.dumps(entry.content, ensure_ascii=False)
    except (TypeError, ValueError):
        content_str = str(entry.content)
    # ~4 chars per token for English text
    content_tokens = max(1, len(content_str) // 4)
    # Metadata overhead: entry_id, entity_key, entity_type
    meta_tokens = len(entry.entry_id) // 4 + len(entry.entity_key) // 4 + len(entry.entity_type) // 4
    return max(1, content_tokens + meta_tokens)


# ═══════════════════════════════════════════════════════════════════════
# Progressive Load
# ═══════════════════════════════════════════════════════════════════════

def progressive_load(
    query: str,
    store: FileTierStore,
    *,
    max_results: int = 20,
    min_score: float = 0.1,
    max_tokens: int = 8192,
) -> RetrievalResult:
    """Progressive tier loading — cheapest tier first, short-circuit.

    Strategy "l1_first":
      1. Check L1 (WORKING). Rank results. If enough above min_score, return.
      2. Check L2 (EPISODIC). Rank results.
      3. Check L3 (SEMANTIC). Rank results.
      4. Merge L2 + L3, deduplicate by entry_id, filter by min_score,
         truncate to max_results, then apply token budget.

    max_tokens limits total estimated tokens in returned entries.
    Entries are included in score order until the budget is exceeded.
    All ranking is deterministic. No LLM, no random.
    """
    t0 = time.time()
    tiers_consulted: list[str] = []

    def _token_truncate(entries, scores, max_tok):
        """Truncate entries to fit within token budget."""
        if not entries:
            return entries, scores, 0
        kept_e = []
        kept_s = []
        total = 0
        for e, s in zip(entries, scores):
            tok = _estimate_tokens(e)
            if total + tok > max_tok:
                break
            total += tok
            kept_e.append(e)
            kept_s.append(s)
        return tuple(kept_e), tuple(kept_s), total

    # Phase 1: L1 — working memory (fastest, short-circuit)
    l1_entries = store.load_by_tier(MemoryTier.WORKING)
    if l1_entries:
        l1_ranked, l1_scores = rank_by_relevance(l1_entries, query)
        l1_filtered = _filter_by_score(l1_ranked, l1_scores, min_score)
        if l1_filtered[0]:
            tiers_consulted.append("L1")
            truncated_e, truncated_s, total_tok = _token_truncate(
                l1_filtered[0], l1_filtered[1], max_tokens,
            )
            final_e = _truncate(truncated_e, max_results)
            final_s = _truncate(truncated_s, max_results)
            duration = int((time.time() - t0) * 1000)
            return RetrievalResult(
                entries=final_e,
                scores=final_s,
                tiers_consulted=tuple(tiers_consulted),
                duration_ms=duration,
                query=query,
                total_tokens=total_tok,
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

    # Filter by min_score
    filtered_entries, filtered_scores = _filter_by_score(
        merged_entries, merged_scores, min_score,
    )

    # Apply result count limit first, then token budget
    capped_entries = _truncate(filtered_entries, max_results)
    capped_scores = _truncate(filtered_scores, max_results)

    truncated_e, truncated_s, total_tok = _token_truncate(
        capped_entries, capped_scores, max_tokens,
    )

    duration = int((time.time() - t0) * 1000)

    if not tiers_consulted:
        tiers_consulted.append("none")

    return RetrievalResult(
        entries=truncated_e,
        scores=truncated_s,
        tiers_consulted=tuple(tiers_consulted),
        duration_ms=duration,
        query=query,
        total_tokens=total_tok,
    )


# ═══════════════════════════════════════════════════════════════════════
# Cross-entity fuzzy association
# ═══════════════════════════════════════════════════════════════════════

def find_related_entries(
    entry: TierEntry,
    store: FileTierStore,
    threshold: float = 0.4,
    max_results: int = 5,
) -> Tuple[TierEntry, ...]:
    """Find entries from OTHER executions that relate to this entry.

    Uses Jaccard similarity on content text representation.
    Cross-entity_key matching — does NOT require entity_key to match.
    Searches L2 (EPISODIC) and L3 (SEMANTIC) only.

    Returns entries sorted by similarity descending.
    """
    query_text = _content_to_text(entry.content)
    query_text += f" {entry.entity_key} {entry.entity_type}"
    query_tokens = _tokenize(query_text)

    if not query_tokens:
        return ()

    # Gather candidates from L2 + L3 (exclude same entry_id)
    candidates: list[TierEntry] = []
    for tier in (MemoryTier.EPISODIC, MemoryTier.SEMANTIC):
        for cand in store.load_by_tier(tier):
            if cand.entry_id != entry.entry_id:
                candidates.append(cand)

    if not candidates:
        return ()

    # Score by Jaccard similarity
    scored = []
    for cand in candidates:
        cand_text = _content_to_text(cand.content)
        cand_text += f" {cand.entity_key} {cand.entity_type}"
        cand_tokens = _tokenize(cand_text)
        sim = _jaccard(query_tokens, cand_tokens)
        if sim >= threshold:
            scored.append((cand, sim))

    scored.sort(key=lambda p: p[1], reverse=True)
    return tuple(c for c, _ in scored[:max_results])


# ═══════════════════════════════════════════════════════════════════════
# Fuzzy-enhanced compaction
# ═══════════════════════════════════════════════════════════════════════

def compact_with_fuzzy(
    store: FileTierStore,
    window_days: int = 7,
    threshold: int = 3,
    fuzzy_threshold: float = 0.4,
) -> int:
    """Compact L2→L3 with cross-entity fuzzy matching.

    Extends compact_episodic_to_semantic by:
    1. Running standard exact entity_key compaction first
    2. For entity_keys below threshold, checking if related entries exist
    3. Merging related entries' frequencies to reach threshold

    Returns total entries promoted (exact + fuzzy).
    """
    from v3.external.context_tiering.tier_policy import (
        compact_episodic_to_semantic, TierEntry,
    )

    # Phase 1: Standard exact compaction
    standard_promoted = store.compact(window_days=window_days,
                                      threshold=threshold)
    total = standard_promoted

    # Phase 2: Fuzzy — find low-frequency entities and check for related
    all_l2 = list(store.load_by_tier(MemoryTier.EPISODIC))
    if len(all_l2) < threshold:
        return total

    # Count by entity_key
    from collections import Counter
    key_counts = Counter(e.entity_key for e in all_l2 if e.entity_key)
    below_threshold = {k for k, c in key_counts.items() if c < threshold}

    if not below_threshold:
        return total

    # For each below-threshold entity, try to find related entries
    fuzzy_promoted = 0
    seen_keys: set[str] = set()

    for key in sorted(below_threshold):
        if key in seen_keys:
            continue
        entries_for_key = [e for e in all_l2 if e.entity_key == key]
        if not entries_for_key:
            continue
        template = entries_for_key[0]

        related = find_related_entries(
            template, store, threshold=fuzzy_threshold, max_results=10,
        )
        # Group related by entity_key and count
        related_keys = set(e.entity_key for e in related
                          if e.entity_key in below_threshold
                          and e.entity_key != key)
        related_keys.add(key)

        total_count = sum(key_counts[k] for k in related_keys)
        if total_count >= threshold:
            # Promote one entry for the group
            from v3.external.context_tiering.tier_policy import (
                compute_importance, TIER_SEMANTIC, TTL_SEMANTIC,
            )
            now = time.time()
            recency_hours = (now - template.timestamp) / 3600.0
            importance = compute_importance(
                recency_hours=recency_hours,
                frequency_count=total_count,
                success=True,
            )
            promoted_entry = TierEntry(
                entry_id=template.entry_id,
                tier=TIER_SEMANTIC,
                execution_id=template.execution_id,
                content=template.content,
                entity_key=f"fuzzy:{key}",
                entity_type=template.entity_type,
                importance=importance,
                timestamp=template.timestamp,
                ttl_expires_at=TTL_SEMANTIC,
            )
            store.save(promoted_entry)
            fuzzy_promoted += 1
            seen_keys.update(related_keys)

    return total + fuzzy_promoted


# ═══════════════════════════════════════════════════════════════════════
# Convenience wrapper
# ═══════════════════════════════════════════════════════════════════════

def retrieve_context(
    query: str,
    store: Optional[FileTierStore] = None,
    *,
    max_results: int = 20,
    max_tokens: int = 8192,
) -> RetrievalResult:
    """Convenience wrapper for progressive_load.

    Creates a default FileTierStore at ./v3/context_tiers/ if none provided.
    Empty store -> empty results (no crash).
    """
    if store is None:
        store = create_tier_store()
    return progressive_load(
        query=query, store=store, max_results=max_results, max_tokens=max_tokens,
    )


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
