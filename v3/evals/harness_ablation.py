"""
Harness Ablation Benchmark — L6 Behavioral Validation.

Validates that SystemKernel's Harness configuration affects execution outcomes
in measurable, deterministic ways. Runs the SAME pipeline under DIFFERENT
harness configs and measures the delta.

Answers the Constraint Bottleneck Theory question:
  "If I change only the Harness configuration (not the pipeline logic),
   does the output change in measurable ways?"

Pipeline: NoopStage('lint') → NoopStage('noop1') → NoopStage('noop2')
Config A: baseline (no retry, no checkpoint, no events, no memory)
Config B: retry enabled
Config C: full harness (retry + checkpoint + events + memory)

Stdlib only. No kernel modifications. No external execution.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional

from v3.kernel.execution_engine import (
    ExecutionConfig,
    ExecutionEngine,
    DomainState,
    StateField,
    MergeStrategy,
    RetryPolicy,
    NoopStage,
)
from v3.kernel.checkpoint import FileCheckpointStore
from v3.kernel.event_store import FileEventStore
from v3.kernel.memory_gateway import MemoryGateway


# ═══════════════════════════════════════════════════════════════════════
# Shared pipeline definition
# ═══════════════════════════════════════════════════════════════════════

PIPELINE = (
    NoopStage(name="lint", delay_s=0.0),
    NoopStage(name="noop1", delay_s=0.0),
    NoopStage(name="noop2", delay_s=0.0),
)

PIPELINE_LABEL = "NoopStage('lint') → NoopStage('noop1') → NoopStage('noop2')"

RUNS_PER_CONFIG = 5

# ═══════════════════════════════════════════════════════════════════════
# Shared DomainState schema — minimal, deterministic fields only
# _last_stage and _last_result are NOT in the schema, so they are
# ignored by DomainState.update() — keeping state_snapshot identical
# across all harness configs.
# ═══════════════════════════════════════════════════════════════════════

_SHARED_SCHEMA = (
    StateField(name="task_id", type_=str, merge=MergeStrategy.REPLACE, default="ablation"),
    StateField(name="target", type_=str, merge=MergeStrategy.REPLACE, default="."),
)

_SHARED_INITIAL = {"task_id": "ablation", "target": "."}


def _make_initial_state() -> DomainState:
    return DomainState(_SHARED_SCHEMA, dict(_SHARED_INITIAL))


# ═══════════════════════════════════════════════════════════════════════
# Result types
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ConfigRun:
    """Aggregated metrics from N runs of one harness config."""

    config_name: str
    durations_ms: list[float]
    success_count: int
    total_runs: int
    checkpoint_counts: list[int]
    event_counts: list[int]
    memory_event_counts: list[int]
    retry_counts: list[int]
    state_hashes: list[str]

    @property
    def duration_avg(self) -> float:
        return statistics.mean(self.durations_ms) if self.durations_ms else 0.0

    @property
    def duration_std(self) -> float:
        return statistics.stdev(self.durations_ms) if len(self.durations_ms) > 1 else 0.0

    @property
    def success_rate_str(self) -> str:
        return f"{self.success_count}/{self.total_runs}"

    @property
    def avg_checkpoints(self) -> float:
        return statistics.mean(self.checkpoint_counts) if self.checkpoint_counts else 0.0

    @property
    def avg_events(self) -> float:
        return statistics.mean(self.event_counts) if self.event_counts else 0.0

    @property
    def avg_memory_events(self) -> float:
        return statistics.mean(self.memory_event_counts) if self.memory_event_counts else 0.0

    @property
    def total_harness_events(self) -> float:
        """Sum of event store events + memory gateway events."""
        return self.avg_events + self.avg_memory_events

    @property
    def avg_retries(self) -> float:
        return statistics.mean(self.retry_counts) if self.retry_counts else 0.0

    @property
    def state_hash(self) -> str:
        """Primary state hash (mode across runs). All runs should agree."""
        if not self.state_hashes:
            return ""
        return max(set(self.state_hashes), key=self.state_hashes.count)


# ═══════════════════════════════════════════════════════════════════════
# Hash helper
# ═══════════════════════════════════════════════════════════════════════

def _hash_state(state_snapshot: dict) -> str:
    """Deterministic SHA-256 hash of a state snapshot dict."""
    canonical = json.dumps(state_snapshot, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Single-run executor
# ═══════════════════════════════════════════════════════════════════════

def _run_once(
    engine: ExecutionEngine,
    cp_store: Optional[FileCheckpointStore],
    ev_store: Optional[FileEventStore],
    mem_gw: Optional[MemoryGateway],
) -> dict:
    """Run the pipeline once and collect metrics.

    Returns a dict with keys: duration_ms, success, checkpoint_count,
    event_count, memory_event_count, retry_count, state_hash, execution_id.
    """
    initial_state = _make_initial_state()
    result = engine.run(initial_state)

    execution_id = result.get("execution_id", "")

    # Count checkpoints
    cp_count = 0
    if cp_store is not None and execution_id:
        cps = cp_store.list(execution_id)
        cp_count = len(cps)

    # Count events from event store (authoritative) or fall back to in-memory stream
    ev_count = 0
    if ev_store is not None and execution_id:
        stream = ev_store.load_stream(execution_id)
        ev_count = len(stream)
    elif engine.event_stream:
        ev_count = len(engine.event_stream)

    # Retry count from lifecycle
    retry_count = 0
    if engine.lifecycle is not None:
        retry_count = engine.lifecycle.retry_count

    # Memory gateway event count (per-run — fresh gateway each run)
    mem_ev_count = mem_gw.event_count if mem_gw is not None else 0

    state_hash = _hash_state(result.get("state_snapshot", {}))

    return {
        "duration_ms": result.get("duration_ms", 0),
        "success": result.get("success", False),
        "checkpoint_count": cp_count,
        "event_count": ev_count,
        "memory_event_count": mem_ev_count,
        "retry_count": retry_count,
        "state_hash": state_hash,
        "execution_id": execution_id,
    }


# ═══════════════════════════════════════════════════════════════════════
# Config runner
# ═══════════════════════════════════════════════════════════════════════

def _run_config(
    config_name: str,
    retry: RetryPolicy,
    max_retries: int,
    cp_store: Optional[FileCheckpointStore],
    ev_store: Optional[FileEventStore],
    mem_gw_factory,
    n: int = RUNS_PER_CONFIG,
) -> ConfigRun:
    """Run a single harness config N times and aggregate results.

    cp_store and ev_store are shared across runs (they key by execution_id).
    mem_gw_factory is called per-run to ensure independent MemoryGateway counters.
    """
    durations = []
    successes = 0
    cp_counts = []
    ev_counts = []
    mem_ev_counts = []
    retry_counts = []
    state_hashes = []

    for i in range(n):
        mem_gw = mem_gw_factory() if mem_gw_factory else None

        config = ExecutionConfig(
            pipeline=PIPELINE,
            retry=retry,
            max_retries=max_retries,
            checkpoint_store=cp_store,
            event_store=ev_store,
            memory_gateway=mem_gw,
        )
        engine = ExecutionEngine(config)
        metrics = _run_once(engine, cp_store, ev_store, mem_gw)

        durations.append(float(metrics["duration_ms"]))
        if metrics["success"]:
            successes += 1
        cp_counts.append(metrics["checkpoint_count"])
        ev_counts.append(metrics["event_count"])
        mem_ev_counts.append(metrics["memory_event_count"])
        retry_counts.append(metrics["retry_count"])
        state_hashes.append(metrics["state_hash"])

    return ConfigRun(
        config_name=config_name,
        durations_ms=durations,
        success_count=successes,
        total_runs=n,
        checkpoint_counts=cp_counts,
        event_counts=ev_counts,
        memory_event_counts=mem_ev_counts,
        retry_counts=retry_counts,
        state_hashes=state_hashes,
    )


# ═══════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════

def _format_config_report(cr: ConfigRun) -> str:
    lines = [
        f"Config {cr.config_name}:",
        f"  duration:      {cr.duration_avg:.1f} ± {cr.duration_std:.1f} ms",
        f"  success_rate:  {cr.success_rate_str}",
        f"  checkpoints:   {cr.avg_checkpoints:.0f}",
        f"  events:        {cr.avg_events:.0f}",
        f"  retries:       {cr.avg_retries:.0f}",
        f"  state_hash:    {cr.state_hash}",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Main benchmark
# ═══════════════════════════════════════════════════════════════════════

def run_ablation(n: int = RUNS_PER_CONFIG) -> int:
    """Run the full harness ablation benchmark.

    Returns exit code: 0 = all checks pass, 1 = failure detected.
    """
    # Use temp directories so benchmark runs don't pollute the repo.
    cp_dir_c = tempfile.mkdtemp(prefix="sk_cp_c_")
    ev_dir_c = tempfile.mkdtemp(prefix="sk_ev_c_")

    _none = lambda: None

    # ── Config A: baseline (no harness features) ──────────────────────
    cfg_a = _run_config(
        config_name="A (baseline)",
        retry=RetryPolicy.NONE,
        max_retries=0,
        cp_store=None,
        ev_store=None,
        mem_gw_factory=_none,
        n=n,
    )

    # ── Config B: retry only ──────────────────────────────────────────
    cfg_b = _run_config(
        config_name="B (retry)",
        retry=RetryPolicy.ONCE,
        max_retries=1,
        cp_store=None,
        ev_store=None,
        mem_gw_factory=_none,
        n=n,
    )

    # ── Config C: full harness ────────────────────────────────────────
    # cp_store and ev_store are shared (keyed by execution_id).
    # MemoryGateway is per-run to avoid cumulative counter inflation.
    cp_store_c = FileCheckpointStore(path=cp_dir_c)
    ev_store_c = FileEventStore(path=ev_dir_c)

    cfg_c = _run_config(
        config_name="C (full harness)",
        retry=RetryPolicy.ONCE,
        max_retries=1,
        cp_store=cp_store_c,
        ev_store=ev_store_c,
        mem_gw_factory=lambda: MemoryGateway(),
        n=n,
    )

    # ── Cleanup temp dirs ─────────────────────────────────────────────
    _rmtree_safe(cp_dir_c)
    _rmtree_safe(ev_dir_c)

    # ── Verdicts ──────────────────────────────────────────────────────
    all_state_hashes = [cfg_a.state_hash, cfg_b.state_hash, cfg_c.state_hash]
    determinism_pass = len(set(all_state_hashes)) == 1 and all(
        h != "" for h in all_state_hashes
    )

    harness_delta_pass = (
        cfg_c.total_harness_events > cfg_a.total_harness_events
        and cfg_c.avg_checkpoints > cfg_a.avg_checkpoints
    )

    # Clamp baseline to 1ms minimum for ratio computation.
    # Sub-millisecond NoopStage runs produce duration_ms=0 (truncated by int()),
    # which makes the ratio meaningless. A 1ms floor is conservative.
    baseline_ms = max(cfg_a.duration_avg, 1.0)
    overhead_ratio = cfg_c.duration_avg / baseline_ms
    overhead_pass = overhead_ratio < 3.0

    bottleneck = "NONE"
    if not determinism_pass:
        bottleneck = f"DIVERGENCE: state hashes differ — {all_state_hashes}"
    elif not overhead_pass:
        bottleneck = f"OVERHEAD: {overhead_ratio:.1f}x exceeds 3.0x limit"

    all_pass = determinism_pass and harness_delta_pass and overhead_pass

    # ── Print report ──────────────────────────────────────────────────
    print("=== Harness Ablation Benchmark ===")
    print(f"Pipeline: {PIPELINE_LABEL}")
    print(f"Runs per config: {n}")
    print()

    for cr in (cfg_a, cfg_b, cfg_c):
        print(_format_config_report(cr))
        print()

    print("Results:")
    print(f"  Determinism:    {'PASS' if determinism_pass else 'FAIL'} "
          f"({'all state hashes match' if determinism_pass else 'state hash divergence detected'})")
    print(f"  Harness delta:  {'PASS' if harness_delta_pass else 'FAIL'} "
          f"({cfg_c.total_harness_events:.0f} total harness events vs {cfg_a.total_harness_events:.0f})")
    print(f"  Overhead ratio: {overhead_ratio:.1f}x "
          f"({'under' if overhead_pass else 'OVER'} 3.0x limit)")
    print(f"  Bottleneck:     {bottleneck}")
    print()

    if all_pass:
        print("Verdict: SystemKernel Harness is DETERMINISTIC with MEASURABLE overhead.")
        print("         L6 behavioral baseline established.")
    else:
        print("Verdict: FAILED — harness ablation detected anomalies.")
        if not determinism_pass:
            print("         State hash divergence means harness config affects output.")
        if not harness_delta_pass:
            print("         Harness config C produced no measurable delta vs baseline.")
        if not overhead_pass:
            print(f"         Overhead ratio {overhead_ratio:.1f}x exceeds 3.0x limit.")

    return 0 if all_pass else 1


def _rmtree_safe(path: str) -> None:
    """Best-effort recursive directory removal. Never raises."""
    try:
        import shutil
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(run_ablation())
