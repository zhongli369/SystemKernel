"""
tag_matcher.py — Tag-Based Matching Engine (v4.0)

Matches user query against skill tags using token overlap scoring.

Scoring:
  - TAG_MATCH base: +0.45 per matched tag
  - Multiple tag matches compound
  - Domain matches: +0.25 (lower weight)
  - Capability matches: +0.75 (higher weight, bridges tag <-> alias)

All functions are pure — no side effects, no disk I/O.
"""

import re
from typing import Optional

from . import CapabilityEntry


# ═══════════════════════════════════════════════════════════════════════════════
# Tokenization
# ═══════════════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> set[str]:
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
# Tag matching
# ═══════════════════════════════════════════════════════════════════════════════

# Scoring model
TAG_SCORE_PER_MATCH = 0.45
DOMAIN_SCORE_PER_MATCH = 0.25
CAPABILITY_SCORE_PER_MATCH = 0.75
MAX_TAG_SCORE = 0.90
MAX_CAPABILITY_SCORE = 0.85
MAX_DOMAIN_SCORE = 0.50


def _match_field(query_tokens: set[str], field_values: tuple[str, ...],
                 score_per_match: float, max_score: float) -> tuple[float, list[str]]:
    """Match query tokens against a tuple of field values.

    Returns (score, matched_values).
    """
    matched = []
    total_score = 0.0

    for value in field_values:
        value_tokens = _tokenize(value)
        if not value_tokens:
            continue

        # If value is multi-word phrase, check if it appears as substring in query
        query_text = " ".join(sorted(query_tokens))
        value_text = value.lower()
        if " " in value_text and len(value_text) >= 4:
            if value_text in query_text:
                matched.append(value)
                total_score += score_per_match
                continue

        # Token overlap
        overlap = value_tokens & query_tokens
        if len(overlap) >= 1:
            # For single-word tags, require stronger overlap
            if " " not in value_text:
                if len(overlap) >= 1:
                    matched.append(value)
                    total_score += score_per_match
            else:
                # Multi-word: require majority of words to match
                if len(overlap) >= max(len(value_tokens) // 2, 1):
                    matched.append(value)
                    total_score += score_per_match * (len(overlap) / len(value_tokens))

    return min(total_score, max_score), matched


def match_tags(query: str, entry: CapabilityEntry) -> Optional[dict]:
    """Match query against a single entry's tags, domains, and capabilities.

    Returns None if no match, or a dict with combined score.
    """
    query_tokens = _tokenize(query.lower())
    if not query_tokens:
        return None

    # Match tags
    tag_score, matched_tags = _match_field(
        query_tokens, entry.tags, TAG_SCORE_PER_MATCH, MAX_TAG_SCORE
    )

    # Match domains
    domain_score, matched_domains = _match_field(
        query_tokens, entry.domains, DOMAIN_SCORE_PER_MATCH, MAX_DOMAIN_SCORE
    )

    # Match capabilities
    cap_score, matched_capabilities = _match_field(
        query_tokens, entry.capabilities, CAPABILITY_SCORE_PER_MATCH, MAX_CAPABILITY_SCORE
    )

    # Combined score: capability has highest weight, then tags, then domains
    combined = cap_score + tag_score + domain_score

    if combined <= 0.01:
        return None

    all_matched = matched_capabilities + matched_tags + matched_domains

    return {
        "entry": entry,
        "match_type": "tag",
        "matched_tokens": tuple(all_matched[:10]),
        "score": min(combined, 0.92),
        "detail": {
            "tag_score": round(tag_score, 4),
            "domain_score": round(domain_score, 4),
            "capability_score": round(cap_score, 4),
            "matched_tags": matched_tags,
            "matched_domains": matched_domains,
            "matched_capabilities": matched_capabilities,
        },
    }


def match_all_tags(query: str, entries: list[CapabilityEntry]) -> list[dict]:
    """Match query against all entries' tags/domains/capabilities.

    Returns list of match dicts sorted by score descending.
    """
    results = []
    for entry in entries:
        match = match_tags(query, entry)
        if match:
            results.append(match)

    results.sort(key=lambda r: (-r["score"], r["entry"].skill))
    return results
