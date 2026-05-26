"""
Execution Truth Snapshot — Single source of architectural truth per execution.

Unifies into one structure:
  - Invariant validation results
  - Structural trace data
  - Architecture diff outputs

No duplication across systems. One snapshot, one JSONL file.
"""

from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════
# Execution Truth Snapshot
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ExecutionTruthSnapshot:
    """Complete architectural truth for one execution run.

    Unifies: invariants + structure + diff fingerprint.
    Single serialization target for all post-execution verification.
    """

    # ── Identity ────────────────────────────────────────────────────
    trace_id: str
    timestamp: str = ""

    # ── Execution shape ─────────────────────────────────────────────
    success: bool = False
    failed_stage: Optional[str] = None
    duration_ms: int = 0
    stage_count: int = 0
    stage_order: list[str] = field(default_factory=list)
    pipeline_stages: list[str] = field(default_factory=list)
    pipeline_hash: str = ""

    # ── Invariants ──────────────────────────────────────────────────
    invariant_violations: int = 0
    invariant_critical: bool = False
    invariant_details: list[dict] = field(default_factory=list)

    # ── Structural fingerprint ──────────────────────────────────────
    v3_modules_loaded: list[str] = field(default_factory=list)
    engine_frozen: bool = False
    engine_run_count: int = 0

    # ── Memory ──────────────────────────────────────────────────────
    memory_events_emitted: int = 0
    memory_backend_active: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def fingerprint(self) -> str:
        """Deterministic structural fingerprint for diff comparison."""
        import hashlib
        parts = [
            "|".join(sorted(self.pipeline_stages)),
            "|".join(sorted(self.v3_modules_loaded)),
            str(self.stage_count),
            str(self.memory_backend_active),
            str(self.engine_frozen),
        ]
        return hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Snapshot Capture (replaces separate trace + invariant capture)
# ═══════════════════════════════════════════════════════════════════════

def _snapshot_v3_modules() -> list[str]:
    """List v3 modules currently loaded in sys.modules."""
    return [name for name in sorted(sys.modules) if name.startswith("v3.")]


def capture_truth(
    result: dict,
    engine: Any,
    violations: Optional[list[dict]] = None,
) -> ExecutionTruthSnapshot:
    """Capture a unified truth snapshot from an execution result.

    Args:
        result: Dict from ExecutionEngine.run()
        engine: The ExecutionEngine instance
        violations: Invariant violations from registry (optional, read from result if omitted)

    Returns:
        ExecutionTruthSnapshot ready for serialization or comparison.
    """
    trace_id = result.get("trace_id", "")
    stage_results = result.get("stage_results", [])
    stage_order = [s.get("stage_name", "?") for s in stage_results]

    # Pipeline stages
    pipeline_stages = []
    try:
        for stage in engine.config.pipeline:
            name = getattr(stage, "_name", None) or stage.__class__.__name__
            pipeline_stages.append(name)
    except Exception:
        pass

    # Memory
    memory_count = 0
    memory_active = False
    try:
        gw = engine.config.memory_gateway
        if gw is not None:
            memory_active = True
            if hasattr(gw, "event_count"):
                memory_count = gw.event_count
    except Exception:
        pass

    # Invariants
    if violations is None:
        violations = result.get("invariant_violations", [])
    violation_count = len(violations) if violations else 0
    critical = result.get("invariant_critical", False)

    return ExecutionTruthSnapshot(
        trace_id=trace_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        success=result.get("success", False),
        failed_stage=result.get("failed_stage"),
        duration_ms=result.get("duration_ms", 0),
        stage_count=len(stage_order),
        stage_order=stage_order,
        pipeline_stages=pipeline_stages,
        pipeline_hash=_hash_str("|".join(pipeline_stages)),
        invariant_violations=violation_count,
        invariant_critical=critical,
        invariant_details=list(violations) if violations else [],
        v3_modules_loaded=_snapshot_v3_modules(),
        engine_frozen=getattr(engine, "_frozen", False),
        engine_run_count=getattr(engine, "_run_count", 0),
        memory_events_emitted=memory_count,
        memory_backend_active=memory_active,
    )


# ═══════════════════════════════════════════════════════════════════════
# JSONL I/O (single file, no duplication)
# ═══════════════════════════════════════════════════════════════════════

def write_truth(snapshot: ExecutionTruthSnapshot, directory: str = "./v3/traces/") -> str:
    """Write truth snapshot as JSONL. Returns file path."""
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, "truth_snapshots.jsonl")
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(snapshot.to_json() + "\n")
    except Exception:
        pass
    return filepath


def read_truths(directory: str = "./v3/traces/") -> list[dict]:
    """Read all truth snapshots from JSONL file."""
    filepath = os.path.join(directory, "truth_snapshots.jsonl")
    if not os.path.exists(filepath):
        return []
    truths = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                truths.append(json.loads(line))
    return truths


# ═══════════════════════════════════════════════════════════════════════
# Diff / Comparison
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TruthDiff:
    """Result of comparing two truth snapshots."""
    identical: bool
    snapshot_a_id: str
    snapshot_b_id: str
    differences: list[str] = field(default_factory=list)


def diff_truths(snapshot_a: ExecutionTruthSnapshot, snapshot_b: ExecutionTruthSnapshot) -> TruthDiff:
    """Compare two truth snapshots. Returns detailed structural diff."""
    diffs: list[str] = []

    if snapshot_a.pipeline_stages != snapshot_b.pipeline_stages:
        diffs.append(
            f"Pipeline stages differ: {snapshot_a.pipeline_stages} vs {snapshot_b.pipeline_stages}"
        )
    if snapshot_a.pipeline_hash != snapshot_b.pipeline_hash:
        diffs.append(
            f"Pipeline hash differs: {snapshot_a.pipeline_hash} vs {snapshot_b.pipeline_hash}"
        )
    if snapshot_a.stage_count != snapshot_b.stage_count:
        diffs.append(
            f"Stage count differs: {snapshot_a.stage_count} vs {snapshot_b.stage_count}"
        )
    if snapshot_a.stage_order != snapshot_b.stage_order:
        diffs.append(
            f"Stage order differs: {snapshot_a.stage_order} vs {snapshot_b.stage_order}"
        )

    mods_a = set(snapshot_a.v3_modules_loaded)
    mods_b = set(snapshot_b.v3_modules_loaded)
    if mods_a != mods_b:
        only_a = mods_a - mods_b
        only_b = mods_b - mods_a
        if only_a:
            diffs.append(f"Modules only in snapshot A: {sorted(only_a)}")
        if only_b:
            diffs.append(f"Modules only in snapshot B: {sorted(only_b)}")

    if snapshot_a.engine_frozen != snapshot_b.engine_frozen:
        diffs.append(f"Engine frozen state differs: {snapshot_a.engine_frozen} vs {snapshot_b.engine_frozen}")
    if snapshot_a.memory_backend_active != snapshot_b.memory_backend_active:
        diffs.append(f"Memory backend differs: {snapshot_a.memory_backend_active} vs {snapshot_b.memory_backend_active}")
    if snapshot_a.invariant_critical != snapshot_b.invariant_critical:
        diffs.append(f"Invariant critical state differs: {snapshot_a.invariant_critical} vs {snapshot_b.invariant_critical}")

    return TruthDiff(
        identical=len(diffs) == 0,
        snapshot_a_id=snapshot_a.trace_id,
        snapshot_b_id=snapshot_b.trace_id,
        differences=diffs,
    )


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _hash_str(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()[:16]
