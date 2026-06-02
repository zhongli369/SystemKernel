"""
Tool Selector — Context-aware tool filtering for the L2 Tool Interface.

Filters enabled capability adapters by task type so every tool isn't
exposed at once. Inspired by cline/cline "fewer better tools" philosophy:
expose only the tools relevant to what the user is actually doing.

Always includes 'context' tools (every task needs context).
Caps at max_tools. Excludes with deterministic reasons.

Stdlib only. No LLM. Deterministic.
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

# ═══════════════════════════════════════════════════════════════════════
# Task → capability type mapping (cline-inspired)
# ═══════════════════════════════════════════════════════════════════════

TASK_TYPE_MAP = {
    "code":     ("context", "skill", "tool"),
    "review":   ("context", "quality", "tool"),
    "research": ("context", "direction", "tool"),
    "build":    ("context", "tool", "agent", "sandbox"),
    "security": ("tool", "eval", "quality"),
}

# Extended mapping for existing TASK_TYPES compatibility
TASK_TYPE_MAP.update({
    "code_generation":          ("context", "skill", "tool", "agent"),
    "context_gathering":        ("context", "tool", "usage"),
    "security_scan":            ("tool", "eval", "quality"),
    "memory_query":             ("memory", "agent", "context"),
    "cost_analysis":            ("usage", "tool"),
    "execution_orchestration":  ("agent", "tool", "eval", "lifecycle"),
})

ALL_TASK_TYPES = tuple(sorted(TASK_TYPE_MAP.keys()))

# Context tools are always included (every task needs context)
ALWAYS_INCLUDE_TYPES = ("context",)


# ═══════════════════════════════════════════════════════════════════════
# ToolSelection
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ToolSelection:
    """Result of context-aware tool filtering.

    Attributes:
        selected: adapter_ids to expose for this task
        excluded: adapter_ids filtered out
        reason_map: adapter_id → human-readable reason for exclusion
        selection_hash: deterministic hash of the selection
    """
    selected: Tuple[str, ...]
    excluded: Tuple[str, ...]
    reason_map: dict
    selection_hash: str

    def to_dict(self) -> dict:
        return {
            "selected": list(self.selected),
            "excluded": list(self.excluded),
            "reason_map": dict(self.reason_map),
            "selection_hash": self.selection_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Selection logic
# ═══════════════════════════════════════════════════════════════════════

def _compute_selection_hash(
    selected: Tuple[str, ...], excluded: Tuple[str, ...], task_type: str,
) -> str:
    data = json.dumps({
        "task_type": task_type,
        "selected": sorted(selected),
        "excluded": sorted(excluded),
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def select_tools(
    task_type: str,
    registry: Optional[CapabilityRegistry] = None,
    *,
    max_tools: int = 5,
) -> ToolSelection:
    """Filter enabled tools to only those relevant to the task type.

    Mapping (cline "fewer better tools" philosophy):
        code     → context, skill, tool
        review   → context, quality, tool
        research → context, direction, tool
        build    → context, tool, agent, sandbox
        security → tool, eval, quality

    Always includes 'context' capability types.
    Caps at max_tools. Deterministic — same inputs → same outputs.

    Args:
        task_type: One of ALL_TASK_TYPES
        registry: CapabilityRegistry (builds default if None)
        max_tools: Maximum tools to select

    Returns:
        ToolSelection with selected/excluded/reason_map
    """
    if registry is None:
        from v3.external.default_capabilities import build_default_registry
        registry = build_default_registry()

    if task_type not in TASK_TYPE_MAP:
        raise ValueError(
            f"Unknown task_type: {task_type}. Must be one of {ALL_TASK_TYPES}"
        )

    relevant_types = set(TASK_TYPE_MAP[task_type])
    relevant_types.update(ALWAYS_INCLUDE_TYPES)

    enabled = list_enabled(registry)
    selected: list[str] = []
    excluded: list[str] = []
    reason_map: dict[str, str] = {}

    for entry in enabled:
        if not entry.spec:
            excluded.append(entry.adapter_id)
            reason_map[entry.adapter_id] = "No spec"
            continue

        ctype = entry.spec.capability_type

        # Deterministic ordering: sort enabled entries by (priority_type_match, adapter_id)
        # so selection is stable across runs

    # Sort enabled entries deterministically, then filter
    def _sort_key(e: CapabilityRegistryEntry) -> tuple:
        if not e.spec:
            return (2, e.adapter_id)
        ctype = e.spec.capability_type
        in_relevant = 0 if ctype in relevant_types else 1
        return (in_relevant, e.adapter_id)

    sorted_entries = sorted(enabled, key=_sort_key)

    for entry in sorted_entries:
        if not entry.spec:
            continue

        ctype = entry.spec.capability_type

        if ctype in relevant_types:
            if len(selected) < max_tools:
                selected.append(entry.adapter_id)
            else:
                excluded.append(entry.adapter_id)
                reason_map[entry.adapter_id] = (
                    f"Relevant type ({ctype}) but max_tools={max_tools} reached"
                )
        else:
            excluded.append(entry.adapter_id)
            reason_map[entry.adapter_id] = (
                f"Type '{ctype}' not relevant for task '{task_type}'"
            )

    sel_tuple = tuple(selected)
    excl_tuple = tuple(excluded)
    sel_hash = _compute_selection_hash(sel_tuple, excl_tuple, task_type)

    return ToolSelection(
        selected=sel_tuple,
        excluded=excl_tuple,
        reason_map=reason_map,
        selection_hash=sel_hash,
    )
