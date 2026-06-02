"""
Tool Dedup — Jaccard-similarity-based duplicate detection for the L2 Tool Interface.

Compares all enabled tool descriptions pairwise using Jaccard similarity
of their description text + capability_type. Score >= 0.7 → duplicate pair.

Deterministic. No LLM. Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple

from v3.external.capability_registry import (
    CapabilityRegistry,
    CapabilityRegistryEntry,
    list_enabled,
)

# Threshold for duplicate detection (Jaccard score)
DUPLICATE_THRESHOLD = 0.7


# ═══════════════════════════════════════════════════════════════════════
# Jaccard similarity
# ═══════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercase words for Jaccard comparison."""
    return set(text.lower().split())


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity: |A ∩ B| / |A ∪ B|. Returns 0.0 if union is empty."""
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return round(intersection / union, 4)


def _build_description(entry: CapabilityRegistryEntry) -> str:
    """Build a comparison string from an entry's spec + notes."""
    parts = []
    if entry.spec:
        parts.append(entry.spec.name or "")
        parts.append(entry.spec.capability_type or "")
    parts.append(entry.notes or "")
    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# DedupReport
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DedupReport:
    """Result of tool deduplication analysis.

    Attributes:
        duplicates: Pairs of overlapping adapter_ids (a, b)
        unique_tools: adapter_ids not in any duplicate pair
        overlap_scores: (a, b) → Jaccard score (0.0-1.0)
        report_hash: deterministic hash of the report
    """
    duplicates: Tuple[Tuple[str, str], ...]
    unique_tools: Tuple[str, ...]
    overlap_scores: dict
    report_hash: str

    def to_dict(self) -> dict:
        return {
            "duplicates": [list(d) for d in self.duplicates],
            "unique_tools": list(self.unique_tools),
            "overlap_scores": {
                f"{a}|{b}": score
                for (a, b), score in self.overlap_scores.items()
            },
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Detection logic
# ═══════════════════════════════════════════════════════════════════════

def _compute_report_hash(
    duplicates: Tuple[Tuple[str, str], ...],
    unique_tools: Tuple[str, ...],
) -> str:
    data = json.dumps({
        "duplicates": [sorted(list(d)) for d in duplicates],
        "unique_tools": sorted(unique_tools),
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def detect_duplicates(
    registry: Optional[CapabilityRegistry] = None,
    *,
    threshold: float = DUPLICATE_THRESHOLD,
) -> DedupReport:
    """Compare all enabled tool descriptions pairwise.

    Overlap score = Jaccard similarity of their description + capability_type.
    Score >= threshold → duplicate pair.

    Deterministic. No LLM. Same inputs → same outputs.

    Args:
        registry: CapabilityRegistry (builds default if None)
        threshold: Jaccard score threshold for duplicate detection

    Returns:
        DedupReport with duplicates, unique_tools, and overlap_scores
    """
    if registry is None:
        from v3.external.default_capabilities import build_default_registry
        registry = build_default_registry()

    enabled = list_enabled(registry)
    n = len(enabled)

    duplicates: list[Tuple[str, str]] = []
    overlap_scores: dict[Tuple[str, str], float] = {}
    in_duplicate: set[str] = set()

    for i in range(n):
        for j in range(i + 1, n):
            a = enabled[i]
            b = enabled[j]

            desc_a = _build_description(a)
            desc_b = _build_description(b)

            tokens_a = _tokenize(desc_a)
            tokens_b = _tokenize(desc_b)

            score = _jaccard(tokens_a, tokens_b)
            pair = (a.adapter_id, b.adapter_id)
            overlap_scores[pair] = score

            if score >= threshold:
                duplicates.append(pair)
                in_duplicate.add(a.adapter_id)
                in_duplicate.add(b.adapter_id)

    unique_tools = tuple(
        e.adapter_id for e in enabled
        if e.adapter_id not in in_duplicate
    )

    dup_tuple = tuple(duplicates)
    report_hash = _compute_report_hash(dup_tuple, unique_tools)

    return DedupReport(
        duplicates=dup_tuple,
        unique_tools=unique_tools,
        overlap_scores=overlap_scores,
        report_hash=report_hash,
    )
