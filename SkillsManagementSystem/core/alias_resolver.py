"""
alias_resolver.py — Alias Resolution Engine (v4.0)

Matches user query against skill aliases with exact, phrase, and token-overlap
matching. Returns (skill_name, match_type, match_score).

Matching levels (in priority order):
  1. EXACT alias match → whole query matches an alias exactly
  2. PHRASE match → a multi-word alias phrase appears in the query
  3. TOKEN_OVERLAP → significant token overlap between query and alias

All functions are pure — no side effects, no disk I/O.
"""

import re
from typing import Optional

from . import CapabilityEntry


# ═══════════════════════════════════════════════════════════════════════════════
# Tokenization (shared utility)
# ═══════════════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> set[str]:
    """Tokenize into lowercase keywords (unigrams + bigrams)."""
    text = re.sub(r"[^a-z0-9\s]", " ", str(text).lower())
    words = text.split()
    tokens = set()
    for w in words:
        w = w.strip()
        if len(w) >= 2:
            tokens.add(w)
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if len(bigram) >= 4:
            tokens.add(bigram)
    return tokens


# ═══════════════════════════════════════════════════════════════════════════════
# Alias matching
# ═══════════════════════════════════════════════════════════════════════════════

def match_alias(query: str, entry: CapabilityEntry) -> Optional[dict]:
    """Match a query against a single capability entry's aliases.

    Returns None if no match, or a dict with match details.
    """
    if not entry.aliases:
        return None

    query_lower = query.lower().strip()

    # Level 1: exact alias match
    for alias in entry.aliases:
        if alias.lower() == query_lower:
            return {
                "entry": entry,
                "match_type": "alias",
                "match_level": "exact",
                "matched_tokens": (alias,),
                "score": 1.0,
            }

    query_tokens = _tokenize(query_lower)
    if not query_tokens:
        return None

    # Level 2: phrase match — an alias phrase appears as substring in query
    for alias in entry.aliases:
        alias_lower = alias.lower()
        if len(alias_lower) >= 4 and alias_lower in query_lower:
            return {
                "entry": entry,
                "match_type": "alias",
                "match_level": "phrase",
                "matched_tokens": (alias,),
                "score": 0.85,
            }

    # Level 3: token overlap
    best_overlap = 0
    best_alias = ""
    best_tokens: tuple[str, ...] = ()

    for alias in entry.aliases:
        alias_tokens = _tokenize(alias)
        if not alias_tokens:
            continue
        overlap = query_tokens & alias_tokens
        if len(overlap) > best_overlap:
            # Jaccard-based score
            jaccard = len(overlap) / max(len(query_tokens | alias_tokens), 1)
            best_overlap = len(overlap)
            best_alias = alias
            best_tokens = tuple(overlap)

    if best_overlap >= 2:
        return {
            "entry": entry,
            "match_type": "alias",
            "match_level": "token_overlap",
            "matched_tokens": best_tokens,
            "score": min(0.45 + best_overlap * 0.10, 0.80),
        }

    return None


def resolve_aliases(query: str, entries: list[CapabilityEntry]) -> list[dict]:
    """Match query against all capability entries' aliases.

    Returns list of match dicts sorted by score descending.
    """
    results = []
    for entry in entries:
        match = match_alias(query, entry)
        if match:
            results.append(match)

    # Sort by score descending, then by match_level priority:
    # exact > phrase > token_overlap, then alphabetical
    level_priority = {"exact": 0, "phrase": 1, "token_overlap": 2}

    results.sort(
        key=lambda r: (
            -r["score"],
            level_priority.get(r["match_level"], 9),
            r["entry"].skill,
        )
    )
    return results
