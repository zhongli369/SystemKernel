"""
Tool Conflicts — Known conflict rule detection for the L2 Tool Interface.

Checks selected tools against a declarative table of known incompatibilities.
Rules are static, not learned. Each rule states WHY two tools conflict.

Deterministic. No LLM. Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════
# Known conflict rules (declarative, not learned)
# ═══════════════════════════════════════════════════════════════════════

# Each entry: (tool_a, tool_b, reason)
# Order within each pair is alphabetical for deterministic lookup.
KNOWN_CONFLICTS: Tuple[Tuple[str, str, str], ...] = (
    (
        "mem0_memory_intelligence",
        "graphiti_temporal_kg",
        "Both provide memory write — pick one to avoid split brain",
    ),
    (
        "crawl4ai",
        "jina-reader",
        "Both fetch web content — redundant network calls",
    ),
    (
        "openhands_agent_worker",
        "autogen_multi_agent",
        "Both provide agent execution — pick one to avoid conflicting task ownership",
    ),
    (
        "letta_memory_agent",
        "mem0_memory_intelligence",
        "Both manage persistent memory — overlapping write paths risk data inconsistency",
    ),
    (
        "letta_memory_agent",
        "graphiti_temporal_kg",
        "Both manage persistent memory — overlapping write paths risk data inconsistency",
    ),
    (
        "openhands_agent_worker",
        "swe_agent_worker",
        "Both execute software engineering tasks — redundant agent workers",
    ),
    (
        "autogen_multi_agent",
        "swe_agent_worker",
        "Both provide autonomous code execution — conflicting orchestration models",
    ),
)


# ═══════════════════════════════════════════════════════════════════════
# ConflictReport
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ConflictReport:
    """Result of conflict detection for a tool selection.

    Attributes:
        conflicts: (tool_a, tool_b, reason) tuples for each conflict found
        safe_pairs: number of pairs that were checked and found safe
        conflict_hash: deterministic hash of the report
    """
    conflicts: Tuple[Tuple[str, str, str], ...]
    safe_pairs: int
    conflict_hash: str

    def to_dict(self) -> dict:
        return {
            "conflicts": [
                {"tool_a": a, "tool_b": b, "reason": r}
                for a, b, r in self.conflicts
            ],
            "safe_pairs": self.safe_pairs,
            "conflict_hash": self.conflict_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Detection logic
# ═══════════════════════════════════════════════════════════════════════

def _build_conflict_index() -> dict[Tuple[str, str], str]:
    """Build a lookup index from the conflict rules.

    Keys are normalized (sorted) pairs so (a, b) and (b, a) both match.
    """
    index: dict[Tuple[str, str], str] = {}
    for tool_a, tool_b, reason in KNOWN_CONFLICTS:
        key = tuple(sorted([tool_a, tool_b]))
        index[key] = reason  # type: ignore[assignment]
    return index


_CONFLICT_INDEX: dict[Tuple[str, str], str] = _build_conflict_index()


def _compute_conflict_hash(
    conflicts: Tuple[Tuple[str, str, str], ...], safe_pairs: int,
) -> str:
    data = json.dumps({
        "conflicts": [
            {"a": a, "b": b, "reason": r} for a, b, r in conflicts
        ],
        "safe_pairs": safe_pairs,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def detect_conflicts(
    selected_tools: Tuple[str, ...],
) -> ConflictReport:
    """Check selected tools against known conflict rules.

    Each pair of selected tools is checked against the KNOWN_CONFLICTS table.
    Returns conflicting pairs with reasons. Deterministic.

    Args:
        selected_tools: Tuple of adapter_ids to check for conflicts

    Returns:
        ConflictReport with conflicts, safe_pairs count, and hash
    """
    conflicts: list[Tuple[str, str, str]] = []
    checked = 0
    safe = 0

    tools = sorted(selected_tools)
    n = len(tools)

    for i in range(n):
        for j in range(i + 1, n):
            checked += 1
            a = tools[i]
            b = tools[j]
            key = (a, b)
            reason = _CONFLICT_INDEX.get(key)
            if reason:
                conflicts.append((a, b, reason))
            else:
                safe += 1

    conflicts_tuple = tuple(conflicts)
    report_hash = _compute_conflict_hash(conflicts_tuple, safe)

    return ConflictReport(
        conflicts=conflicts_tuple,
        safe_pairs=safe,
        conflict_hash=report_hash,
    )
