"""
Tool Pipeline — Gating pipeline for L2 Tool Interface.

Orchestrates tool_selector → tool_dedup → tool_conflicts into a single
deterministic pipeline. Resolves conflicts by removing the lower-priority
tool. Produces a final filtered, deduped, conflict-free tool set.

Stdlib only. No LLM. Deterministic.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from v3.external.capability_registry import CapabilityRegistry
from v3.external.tool_selector import (
    ToolSelection,
    select_tools,
)
from v3.external.tool_dedup import (
    DedupReport,
    detect_duplicates,
)
from v3.external.tool_conflicts import (
    ConflictReport,
    detect_conflicts,
)


@dataclass(frozen=True)
class ToolGateResult:
    """Result of the complete tool gating pipeline.

    selected: final adapter_ids after filtering, dedup, and conflict resolution.
    selection: raw ToolSelection from tool_selector.
    dedup: DedupReport from tool_dedup.
    conflicts: ConflictReport from tool_conflicts.
    resolved_conflicts: tools removed due to conflict resolution.
    pipeline_hash: deterministic hash of the entire pipeline result.
    duration_ms: wall-clock duration of the pipeline execution.
    """
    selected: Tuple[str, ...]
    selection: ToolSelection
    dedup: DedupReport
    conflicts: ConflictReport
    resolved_conflicts: Tuple[str, ...]
    pipeline_hash: str
    duration_ms: int

    def to_dict(self) -> dict:
        return {
            "selected": list(self.selected),
            "selection": self.selection.to_dict(),
            "dedup": self.dedup.to_dict(),
            "conflicts": self.conflicts.to_dict(),
            "resolved_conflicts": list(self.resolved_conflicts),
            "pipeline_hash": self.pipeline_hash,
            "duration_ms": self.duration_ms,
        }


def _compute_pipeline_hash(
    selected: Tuple[str, ...],
    selection_hash: str,
    dedup_hash: str,
    conflict_hash: str,
) -> str:
    data = json.dumps({
        "selected": sorted(selected),
        "selection_hash": selection_hash,
        "dedup_hash": dedup_hash,
        "conflict_hash": conflict_hash,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def _resolve_conflicts(
    selected: Tuple[str, ...],
    conflict_report: ConflictReport,
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Remove one tool from each conflicting pair.

    Strategy: for each conflicting pair, remove the tool that appears
    second in alphabetical order (deterministic). Both tools are removed
    from the conflict set if present in selected.

    Returns (clean_selected, resolved_tools).
    """
    resolved: list[str] = []
    remaining = list(selected)

    # Collect all tools involved in conflicts
    conflict_ids: set[str] = set()
    for a, b, _ in conflict_report.conflicts:
        conflict_ids.add(a)
        conflict_ids.add(b)

    # For each pair, remove the alphabetically second one
    removed: set[str] = set()
    for a, b, _ in conflict_report.conflicts:
        if a in remaining and b in remaining:
            # Remove the one that comes second alphabetically
            to_remove = b if a < b else a
            removed.add(to_remove)

    clean = tuple(t for t in selected if t not in removed)
    resolved_tuple = tuple(sorted(removed))
    return clean, resolved_tuple


class ToolPipeline:
    """Gating pipeline: select → dedup → resolve conflicts.

    Usage:
        pipeline = ToolPipeline()
        result = pipeline.gate("code", max_tools=5)
        print(result.selected)  # final tool set
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None,
                 metrics: Optional[dict] = None):
        if registry is None:
            from v3.external.default_capabilities import build_default_registry
            registry = build_default_registry()
        self.registry = registry
        self.metrics = metrics

    def gate(self, task_type: str, max_tools: int = 5) -> ToolGateResult:
        """Run the complete tool gating pipeline.

        1. select_tools(task_type) — filter by task relevance
        2. detect_duplicates(selected) — find overlapping tools
        3. detect_conflicts(selected) — find conflicting tool pairs
        4. resolve conflicts — remove one tool from each conflicting pair
        """
        t0 = time.time()

        # Step 1: Select
        selection = select_tools(task_type, self.registry, max_tools=max_tools)

        # Step 2: Dedup on selected tools (subset of registry)
        dedup = detect_duplicates(self.registry)

        # Step 3: Conflict detection on selected
        conflicts = detect_conflicts(selection.selected)

        # Step 4: Resolve conflicts
        clean_selected, resolved = _resolve_conflicts(
            selection.selected, conflicts,
        )

        # Build hash
        pipeline_hash = _compute_pipeline_hash(
            clean_selected, selection.selection_hash,
            dedup.report_hash, conflicts.conflict_hash,
        )

        duration_ms = int((time.time() - t0) * 1000)

        if self.metrics is not None:
            self.metrics.setdefault("pipeline_runs", 0)
            self.metrics["pipeline_runs"] += 1
            self.metrics.setdefault("pipeline_duration_ms_total", 0)
            self.metrics["pipeline_duration_ms_total"] += duration_ms
            self.metrics.setdefault("tools_before", len(selection.selected))
            self.metrics.setdefault("tools_after", len(clean_selected))

        return ToolGateResult(
            selected=clean_selected,
            selection=selection,
            dedup=dedup,
            conflicts=conflicts,
            resolved_conflicts=resolved,
            pipeline_hash=pipeline_hash,
            duration_ms=duration_ms,
        )
