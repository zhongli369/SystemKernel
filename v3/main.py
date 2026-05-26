#!/usr/bin/env python3
"""
SystemKernel v3.0 — Runnable Entry Point (Phase 2).

Phase 2: Memory Isolation Boundary wired.
  - MemoryGateway (kernel-side protocol, zero deps)
  - InProcessMemoryAdapter (default backend, swappable)
  - ExecutionEngine emits memory events via gateway
  - Memory query demo at end of execution

Usage:
    python v3/main.py
    python v3/main.py --target ./my_project
    python v3/main.py --verbose
"""

import sys
import os
import json
import uuid
import time
from datetime import datetime, timezone

# Force UTF-8 encoding for Windows GBK terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add SystemKernel root to path so 'v3' package is importable
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.execution_engine import (
    ExecutionEngine,
    ExecutionState,
    ExecutionConfig,
    StateField,
    MergeStrategy,
    RetryPolicy,
    FileCheckpointStore,
    NoopStage,
)
from v3.kernel.memory_gateway import (
    MemoryGateway,
    MemoryEventType,
    MemoryEventSource,
)
from v3.kernel.observability import (
    ObservabilityService,
    ObservabilityConfig,
    CostSnapshot,
)
from v3.memory.memory_adapter_base import InProcessMemoryAdapter


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    target = "."
    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i + 1 < len(sys.argv):
            target = sys.argv[i + 1]
            break

    print("=" * 56)
    print("  SystemKernel v3.0 — Phase 2 (Memory Isolation)")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 56)

    # ── Initialize Observability ──────────────────────────────────
    print("\n[1/6] Initializing ObservabilityService...")
    obs = ObservabilityService(ObservabilityConfig(
        traces_path="./v3/traces/",
        metrics_path="./v3/metrics/",
        cost_tracking=True,
        cost_budget_usd=0.0,
    ))
    trace_id = str(uuid.uuid4())
    print(f"  trace_id: {trace_id}")

    # ── Initialize MemoryGateway ──────────────────────────────────
    print("[2/6] Initializing MemoryGateway...")
    memory_gateway = MemoryGateway()
    print(f"  gateway ready (connected: {memory_gateway.is_connected})")

    print("[3/6] Wiring InProcessMemoryAdapter...")
    adapter = InProcessMemoryAdapter()
    adapter.connect()
    memory_gateway.connect(adapter)
    print(f"  adapter '{adapter.name}' wired (connected: {memory_gateway.is_connected})")

    # ── Initialize Checkpoint Store ───────────────────────────────
    print("[4/6] Initializing CheckpointStore...")
    checkpoint_store = FileCheckpointStore("./v3/checkpoints/")

    # ── Initialize ExecutionState ─────────────────────────────────
    print("[5/6] Initializing ExecutionState + Engine (with memory_gateway)...")
    state = ExecutionState(
        schema=(
            StateField("thread_id", str, MergeStrategy.KEEP),
            StateField("target", str, MergeStrategy.REPLACE, default=target),
            StateField("task_id", str, MergeStrategy.KEEP),
            StateField("skill_id", str, MergeStrategy.KEEP),
            StateField("_last_stage", str, MergeStrategy.REPLACE),
            StateField("_last_result", dict, MergeStrategy.REPLACE),
        ),
        initial={
            "thread_id": f"session-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "target": target,
            "task_id": f"task-{uuid.uuid4().hex[:8]}",
            "skill_id": "demo-skill",
        },
    )

    engine = ExecutionEngine(ExecutionConfig(
        pipeline=(
            NoopStage(name="stage_init", delay_s=0.01),
            NoopStage(name="stage_execute", delay_s=0.02),
            NoopStage(name="stage_verify", delay_s=0.01),
            NoopStage(name="stage_report", delay_s=0.01),
        ),
        retry=RetryPolicy.ONCE,
        max_retries=1,
        checkpoint_store=checkpoint_store,
        thread_id=state.get("thread_id"),
        memory_gateway=memory_gateway,  # ★ Phase 2: memory hook
    ))

    # ── Execute ───────────────────────────────────────────────────
    print("[6/6] Running execution pipeline...\n")
    start = time.monotonic()
    result = engine.run(state)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    # ── Report ────────────────────────────────────────────────────
    print("─" * 56)
    print(f"  Execution {'PASSED' if result['success'] else 'FAILED'}")
    print(f"  Duration: {elapsed_ms}ms")
    print(f"  Stages: {len(result['stage_results'])}")
    for r in result["stage_results"]:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"    [{status}] {r['stage_name']} ({r['duration_ms']}ms)")
    print("─" * 56)

    # ── Memory Event Summary ───────────────────────────────────────
    print(f"\n  Memory Events Written: {memory_gateway.event_count}")

    # ── Memory Query Demo ─────────────────────────────────────────
    print("\n  Memory Query Demo:")
    qr = memory_gateway.read("stage_init", top_k=5)
    if qr:
        print(f"    Query 'stage_init' → {len(qr.entries)} results")
    else:
        print("    Query 'stage_init' → no results (empty store)")
    qr2 = memory_gateway.read("stage_execute", top_k=5)
    if qr2:
        print(f"    Query 'stage_execute' → {len(qr2.entries)} results")

    # ── Write Trace ───────────────────────────────────────────────
    obs.log_event(
        stage="execution",
        data={
            "task_id": state.get("task_id"),
            "target": target,
            "success": result["success"],
            "duration_ms": elapsed_ms,
            "stages": result["stage_results"],
            "memory_events": memory_gateway.event_count,
        },
        trace_id=trace_id,
    )
    obs.emit_metrics("execution_latency_ms", float(elapsed_ms), tags={"task": state.get("task_id")}, trace_id=trace_id)
    obs.emit_metrics("validation_passed", 1.0 if result["success"] else 0.0, tags={}, trace_id=trace_id)

    # ── Write ccusage-compatible cost stub ────────────────────────
    obs.log_cost(CostSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_tokens=120,
        output_tokens=45,
        cost_usd=0.0,
        model="skeleton",
    ))

    # ── Export ccusage bridge ─────────────────────────────────────
    export_path = obs.ccusage_bridge_stub("./v3/exports/usage_sample.jsonl")

    # ── Write Execution Report JSON ───────────────────────────────
    report = {
        "v": "3.0.0-phase2",
        "trace_id": trace_id,
        "task_id": state.get("task_id"),
        "thread_id": state.get("thread_id"),
        "target": target,
        "success": result["success"],
        "duration_ms": elapsed_ms,
        "stage_count": len(result["stage_results"]),
        "stages": result["stage_results"],
        "state_snapshot": result["state_snapshot"],
        "memory_events_emitted": memory_gateway.event_count,
        "memory_backend": adapter.name,
        "memory_connected": memory_gateway.is_connected,
    }
    report_path = "./v3/exports/execution_report.json"
    os.makedirs("./v3/exports/", exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n  Report: {os.path.abspath(report_path)}")
    print(f"  Traces: {os.path.abspath(obs.config.traces_path)}")
    print(f"  Metrics: {os.path.abspath(obs.config.metrics_path)}")
    print(f"  Checkpoints: {os.path.abspath('./v3/checkpoints/')}")
    print(f"  ccusage export: {os.path.abspath(export_path)}")
    print(f"\n  Memory Gateway:")
    print(f"    Backend:  {adapter.name}")
    print(f"    Events:   {memory_gateway.event_count} written")
    print(f"    Queries:  2 performed")
    print(f"\n  [OK] SystemKernel v3.0 Phase 2 is operational.")
    print(f"  Memory isolation boundary active.")
    print(f"  Kernel runs {'WITH' if memory_gateway.is_connected else 'WITHOUT'} memory backend.")
    print(f"  Next: Phase 3 - ExecutionEngine upgrade (retry policies + time-travel)")

    # ── Clean shutdown ────────────────────────────────────────────
    adapter.close()

    if verbose:
        print(f"\n  Full result:")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
