"""
L5 Observability Smoke Test — End-to-end kernel execution with full
observability pipeline verification.

Exercises:
  - ExecutionEngine with 3-stage NoopStage pipeline
  - ObservabilityService trace spans (JSONL disk storage)
  - ObservabilityService cost snapshots (ccusage-compatible JSONL)
  - MetricsExporter singleton (Prometheus-compatible in-memory metrics)
  - CLI: systemkernel v4 metrics, systemkernel v4 cost
  - check_budget() budget enforcement

The test is self-contained: no Docker, no network, no external services.
All verification is read-only on observability output files.

Stdlib only. Does NOT modify v3/kernel/ or api.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from datetime import datetime, timezone

# Ensure SystemKernel root is on sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_V3_ROOT = os.path.join(_ROOT, "v3")
_CLI_PATH = os.path.join(_V3_ROOT, "cli", "systemkernel.py")
_PYTHON = sys.executable


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_jsonl(path: str) -> list[dict]:
    """Read all records from a JSONL file. Returns [] if file missing."""
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _count_trace_spans(obs_service, date_str: str) -> int:
    """Count trace spans for today by reading the trace JSONL file."""
    trace_dir = os.path.join(obs_service.config.traces_path, date_str)
    fpath = os.path.join(trace_dir, "trace.jsonl")
    return len(_read_jsonl(fpath))


def _count_cost_records(obs_service, date_str: str) -> int:
    """Count cost snapshots for today."""
    cost_dir = os.path.join(obs_service.config.traces_path, "cost")
    fpath = os.path.join(cost_dir, f"{date_str}.jsonl")
    return len(_read_jsonl(fpath))


# ═══════════════════════════════════════════════════════════════════════
# Main Smoke Test
# ═══════════════════════════════════════════════════════════════════════

def run_smoke_test() -> tuple[bool, str]:
    """Run the full L5 observability smoke test.

    Returns (passed, summary_string).
    """
    failures: list[str] = []
    trace_count = 0
    metric_count = 0
    cost_total = 0.0

    # ── Setup: temp directory for observability output ─────────────────
    tmpdir = tempfile.mkdtemp(prefix="sk_smoke_")
    traces_path = os.path.join(tmpdir, "traces")
    metrics_path = os.path.join(tmpdir, "metrics")

    try:
        # ═══════════════════════════════════════════════════════════════
        # Step 1: Create ExecutionEngine with 3 NoopStages
        # ═══════════════════════════════════════════════════════════════
        from v3.kernel.execution_engine import (
            ExecutionEngine, ExecutionConfig, NoopStage, DomainState, StateField,
        )

        pipeline = (
            NoopStage(name="stage_init", delay_s=0.01),
            NoopStage(name="stage_process", delay_s=0.01),
            NoopStage(name="stage_finalize", delay_s=0.01),
        )

        schema = (StateField(name="task_id", type_=str, default="smoke-test"),)
        config = ExecutionConfig(pipeline=pipeline, thread_id="l5-smoke-test")
        engine = ExecutionEngine(config)
        initial_state = DomainState(schema, {"task_id": "l5-smoke-001"})

        # ═══════════════════════════════════════════════════════════════
        # Step 2: Create ObservabilityService with temp storage
        # ═══════════════════════════════════════════════════════════════
        from v3.kernel.observability import (
            ObservabilityService, ObservabilityConfig, CostSnapshot,
        )

        obs_config = ObservabilityConfig(
            traces_path=traces_path,
            metrics_path=metrics_path,
            cost_tracking=True,
            cost_budget_usd=0.0,  # unlimited — check_budget() returns None
        )
        obs = ObservabilityService(config=obs_config)

        # ═══════════════════════════════════════════════════════════════
        # Step 3: Run pipeline
        # ═══════════════════════════════════════════════════════════════
        exec_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        result = engine.run(initial_state, execution_id=exec_id)

        if not result.get("success"):
            failures.append(f"Pipeline failed: {result.get('failed_stage')}")
            return False, "L5 Smoke Test: FAIL — pipeline execution failed"

        # ═══════════════════════════════════════════════════════════════
        # Step 4: Record observability data from execution
        # ═══════════════════════════════════════════════════════════════

        # 4a. Log trace spans for each stage
        for i, stage_result in enumerate(result.get("stage_results", [])):
            stage_name = stage_result.get("stage_name", f"stage_{i}")
            obs.log_event(
                stage=stage_name,
                data={
                    "execution_id": exec_id,
                    "stage_index": i,
                    "passed": stage_result.get("passed", False),
                    "duration_ms": stage_result.get("duration_ms", 0),
                },
                trace_id=trace_id,
                metadata={"thread_id": "l5-smoke-test"},
            )

        # Log a final execution-complete span
        obs.log_event(
            stage="execution_complete",
            data={
                "execution_id": exec_id,
                "duration_ms": result.get("duration_ms", 0),
                "stage_count": len(result.get("stage_results", [])),
            },
            trace_id=trace_id,
        )

        # 4b. Emit metrics via MetricsExporter singleton (CLI reads from this)
        from v3.external.observability.metrics_exporter import get_exporter

        exporter = get_exporter()
        exporter.inc_executions(1.0)
        exporter.add_cost("deepseek-v4-pro", 1500, 0.0001)
        exporter.add_cost("claude-sonnet-4-6", 800, 0.0001)
        exporter.record_latency(result.get("duration_ms", 0) / 1000.0)
        exporter.set_complexity(6.7)
        exporter.set_stability(96.0)
        exporter.inc_routes("l5-smoke-test", 1.0)

        metric_count = 5  # executions, cost_usd, latency, complexity, stability

        # 4c. Log cost snapshot via ObservabilityService (disk-based)
        cost_snapshot = CostSnapshot(
            timestamp=_iso_now(),
            input_tokens=2000,
            output_tokens=500,
            cache_create_tokens=0,
            cache_read_tokens=100,
            cost_usd=0.0002,
            model="deepseek-v4-pro",
        )
        obs.log_cost(cost_snapshot)

        # Log a second cost snapshot for good measure
        cost_snapshot2 = CostSnapshot(
            timestamp=_iso_now(),
            input_tokens=800,
            output_tokens=200,
            cache_create_tokens=0,
            cache_read_tokens=0,
            cost_usd=0.0001,
            model="claude-sonnet-4-6",
        )
        obs.log_cost(cost_snapshot2)

        cost_total = cost_snapshot.cost_usd + cost_snapshot2.cost_usd

        # ═══════════════════════════════════════════════════════════════
        # Step 5: Verify trace spans on disk
        # ═══════════════════════════════════════════════════════════════
        today = _today_str()
        trace_count = _count_trace_spans(obs, today)

        if trace_count == 0:
            failures.append("No trace spans found on disk")
        elif trace_count < 4:
            failures.append(f"Expected >= 4 trace spans, got {trace_count}")

        # Verify trace content: all spans share the same trace_id
        trace_dir = os.path.join(traces_path, today)
        trace_file = os.path.join(trace_dir, "trace.jsonl")
        spans = _read_jsonl(trace_file)
        for span in spans:
            if span.get("trace_id") != trace_id:
                failures.append(f"Span has wrong trace_id: {span.get('trace_id')}")

        # ═══════════════════════════════════════════════════════════════
        # Step 6: Verify cost snapshots on disk
        # ═══════════════════════════════════════════════════════════════
        cost_count = _count_cost_records(obs, today)
        if cost_count < 2:
            failures.append(f"Expected >= 2 cost snapshots, got {cost_count}")

        cost_records = _read_jsonl(
            os.path.join(traces_path, "cost", f"{today}.jsonl")
        )
        for rec in cost_records:
            if rec.get("input_tokens", 0) <= 0:
                failures.append(f"Cost snapshot has zero input_tokens: {rec}")

        # ═══════════════════════════════════════════════════════════════
        # Step 7: Verify MetricsExporter has non-zero values
        # ═══════════════════════════════════════════════════════════════
        exported = exporter.export_json()
        m = exported["metrics"]

        if m["systemkernel_executions_total"] <= 0:
            failures.append("systemkernel_executions_total is zero")
        if m["systemkernel_cost_usd_total"] <= 0:
            failures.append("systemkernel_cost_usd_total is zero")
        latency = m.get("systemkernel_execution_latency_seconds", {})
        if latency.get("count", 0) <= 0:
            failures.append("systemkernel_execution_latency_seconds count is zero")
        if m["systemkernel_complexity_score"] <= 0:
            failures.append("systemkernel_complexity_score is zero")
        if m["systemkernel_stability_freeze_score"] <= 0:
            failures.append("systemkernel_stability_freeze_score is zero")

        # ═══════════════════════════════════════════════════════════════
        # Step 8: check_budget() — should return None (unlimited)
        # ═══════════════════════════════════════════════════════════════
        budget_result = obs.check_budget()
        if budget_result is not None:
            # If budget is 0 (unlimited), check_budget returns None
            failures.append(f"check_budget() expected None for unlimited budget, got: {budget_result}")

        # Also test with a budget set (should return warning)
        obs2_config = ObservabilityConfig(
            traces_path=os.path.join(tmpdir, "traces2"),
            metrics_path=os.path.join(tmpdir, "metrics2"),
            cost_tracking=True,
            cost_budget_usd=100.0,
        )
        obs2 = ObservabilityService(config=obs2_config)
        obs2.log_cost(CostSnapshot(
            timestamp=_iso_now(),
            input_tokens=50_000_000,
            output_tokens=10_000_000,
            cost_usd=85.0,
            model="claude-opus-4-7",
        ))
        budget_warning = obs2.check_budget()
        if budget_warning is None:
            failures.append("check_budget() should warn at 85% of budget")
        elif "85" not in budget_warning and "WARNING" not in budget_warning:
            failures.append(f"Unexpected budget message: {budget_warning}")

        # ═══════════════════════════════════════════════════════════════
        # Step 9: Verify CLI commands work (no crash, produce output)
        # ═══════════════════════════════════════════════════════════════

        # 9a. CLI v4 metrics
        metrics_proc = subprocess.run(
            [_PYTHON, _CLI_PATH, "v4", "metrics"],
            capture_output=True, text=True, timeout=30,
            cwd=_ROOT,
        )
        if metrics_proc.returncode != 0:
            failures.append(f"CLI 'v4 metrics' exited {metrics_proc.returncode}: {metrics_proc.stderr[:200]}")
        elif not metrics_proc.stdout.strip():
            failures.append("CLI 'v4 metrics' produced no output")

        # 9b. CLI v4 cost
        cost_proc = subprocess.run(
            [_PYTHON, _CLI_PATH, "v4", "cost"],
            capture_output=True, text=True, timeout=30,
            cwd=_ROOT,
        )
        if cost_proc.returncode != 0:
            failures.append(f"CLI 'v4 cost' exited {cost_proc.returncode}: {cost_proc.stderr[:200]}")
        elif "Total cost:" not in cost_proc.stdout:
            failures.append("CLI 'v4 cost' missing 'Total cost:' header")

        # 9c. CLI v4 dashboard
        dash_proc = subprocess.run(
            [_PYTHON, _CLI_PATH, "v4", "dashboard"],
            capture_output=True, text=True, timeout=30,
            cwd=_ROOT,
        )
        if dash_proc.returncode != 0:
            failures.append(f"CLI 'v4 dashboard' exited {dash_proc.returncode}: {dash_proc.stderr[:200]}")

        # 9d. CLI v4 alerts
        alerts_proc = subprocess.run(
            [_PYTHON, _CLI_PATH, "v4", "alerts"],
            capture_output=True, text=True, timeout=30,
            cwd=_ROOT,
        )
        if alerts_proc.returncode != 0:
            failures.append(f"CLI 'v4 alerts' exited {alerts_proc.returncode}: {alerts_proc.stderr[:200]}")

    except Exception:
        tb = traceback.format_exc()
        return False, f"L5 Smoke Test: FAIL — exception\n{tb}"

    finally:
        # Cleanup temp directory
        import shutil
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════
    # Final verdict
    # ═══════════════════════════════════════════════════════════════════
    if failures:
        reasons = "; ".join(failures[:5])  # cap at 5
        return False, f"L5 Smoke Test: FAIL — {reasons}"

    summary = (
        f"L5 Smoke Test: PASS "
        f"({trace_count} traces, {metric_count} metrics, ${cost_total:.4f} cost)"
    )
    return True, summary


# ═══════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    passed, msg = run_smoke_test()
    print(msg)
    sys.exit(0 if passed else 1)
