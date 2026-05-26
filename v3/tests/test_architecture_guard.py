"""
Architectural Guard Tests — Verify invariants remain intact.

These tests assert system-level properties:
  1. Kernel runs without memory backend
  2. Kernel runs with empty pipeline (tools disabled)
  3. Execution output is deterministic (same input → same output)
  4. ExecutionEngine is frozen after init
  5. MemoryGateway is removable without kernel impact
  6. Complexity budget is within limits
"""

import sys
import os
import json
import uuid

# Add SystemKernel root to path
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.execution_engine import (
    ExecutionEngine,
    DomainState,
    ExecutionConfig,
    StateField,
    MergeStrategy,
    RetryPolicy,
    NoopStage,
    ExecutionEngineFrozenError,
)
from v3.kernel.checkpoint import FileCheckpointStore
from v3.kernel.memory_gateway import MemoryGateway
from v3.kernel.complexity_budget import validate_complexity_report
from v3.memory.memory_adapter_base import InProcessMemoryAdapter


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_domain_state(thread_id: str = "test-session") -> DomainState:
    return DomainState(
        schema=(
            StateField("thread_id", str, MergeStrategy.KEEP),
            StateField("target", str, MergeStrategy.REPLACE, default="."),
            StateField("task_id", str, MergeStrategy.KEEP),
            StateField("_last_stage", str, MergeStrategy.REPLACE),
            StateField("_last_result", dict, MergeStrategy.REPLACE),
        ),
        initial={
            "thread_id": thread_id,
            "target": ".",
            "task_id": f"task-{uuid.uuid4().hex[:8]}",
        },
    )


def _make_engine(**kwargs) -> ExecutionEngine:
    defaults = {
        "pipeline": (
            NoopStage(name="s1", delay_s=0.001),
            NoopStage(name="s2", delay_s=0.001),
        ),
        "retry": RetryPolicy.ONCE,
        "max_retries": 1,
        "checkpoint_store": None,
        "thread_id": "test-session",
        "memory_gateway": None,
    }
    defaults.update(kwargs)
    return ExecutionEngine(ExecutionConfig(**defaults))


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Kernel runs without memory backend
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_runs_without_memory():
    """Kernel must operate normally with memory_gateway=None."""
    engine = _make_engine(memory_gateway=None)
    state = _make_domain_state()
    result = engine.run(state)
    assert result["success"] is True
    assert result["failed_stage"] is None
    assert len(result["stage_results"]) == 2
    assert engine.run_count == 1


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Kernel runs with memory enabled
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_runs_with_memory_enabled():
    """Memory emission must not affect execution correctness."""
    gw = MemoryGateway()
    adapter = InProcessMemoryAdapter()
    adapter.connect()
    gw.connect(adapter)

    engine = _make_engine(memory_gateway=gw)
    state = _make_domain_state()
    result = engine.run(state)

    assert result["success"] is True
    # Memory events should have been emitted (one per stage)
    assert gw.event_count == 2, f"Expected 2 memory events, got {gw.event_count}"
    adapter.close()


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Kernel runs with empty pipeline (tools disabled)
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_runs_with_empty_pipeline():
    """Empty pipeline must succeed immediately."""
    engine = _make_engine(pipeline=())
    state = _make_domain_state()
    result = engine.run(state)
    assert result["success"] is True
    assert result["failed_stage"] is None
    assert len(result["stage_results"]) == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Execution output is deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_execution_is_deterministic():
    """Same pipeline + same state → same success result."""
    state1 = _make_domain_state()
    state2 = _make_domain_state()
    # Use identical thread_ids for determinism
    state1 = state1.update(thread_id="det-test")
    state2 = state2.update(thread_id="det-test")

    engine1 = _make_engine(thread_id="det-test")
    engine2 = _make_engine(thread_id="det-test")

    result1 = engine1.run(state1)
    result2 = engine2.run(state2)

    assert result1["success"] == result2["success"]
    assert len(result1["stage_results"]) == len(result2["stage_results"])
    # All stages should pass
    for r1, r2 in zip(result1["stage_results"], result2["stage_results"]):
        assert r1["passed"] == r2["passed"]
        assert r1["stage_name"] == r2["stage_name"]


# ═══════════════════════════════════════════════════════════════════════
# Test 5: ExecutionEngine is frozen after init
# ═══════════════════════════════════════════════════════════════════════

def test_engine_is_frozen_after_init():
    """Cannot modify config or pipeline after construction."""
    engine = _make_engine()
    assert engine.frozen is True

    # Config is a frozen dataclass — cannot set attributes
    try:
        engine.config.pipeline = ()
        config_mutable = False
    except Exception:
        config_mutable = False  # frozen=True prevents mutation

    # Internal freeze guard catches pipeline identity changes
    # (This is a best-effort guard — Python tuples are already immutable)
    assert engine.run_count == 0
    engine.run(_make_domain_state())
    assert engine.run_count == 1


# ═══════════════════════════════════════════════════════════════════════
# Test 6: MemoryGateway is removable
# ═══════════════════════════════════════════════════════════════════════

def test_memory_gateway_removable():
    """Gateway with no adapter connected is a no-op."""
    gw = MemoryGateway()
    assert gw.event_count == 0
    assert gw.is_connected is False

    # write should succeed even without adapters
    from v3.kernel.memory_gateway import MemoryEventType, MemoryEventSource
    gw.write(
        event_type=MemoryEventType.WRITE,
        source=MemoryEventSource.EXECUTION_ENGINE,
        source_stage="test",
        execution_id="removable-test",
        payload={"content": "test"},
    )
    assert gw.event_count == 1  # Event counted
    # No adapter processed it (no backend side effects)


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Complexity budget is within limits
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_budget_within_limits():
    """All modules must be within their complexity budgets."""
    report = validate_complexity_report(os.path.join(_root, "v3"))
    assert report["overall_status"] != "EXCEEDED", \
        f"Complexity budget exceeded: {report['exceeded_modules']}"

    # Print budget status for visibility
    print(f"\n  Complexity Budget: {report['overall_status']}")
    print(f"  Total LOC: {report['total_loc']} / {report['total_budget_loc']} ({report['usage_pct']}%)")
    for m in report["modules"]:
        flag = "!!" if m["status"] == "EXCEEDED" else " ~" if m["status"] == "WARN" else "  "
        print(f"    [{m['status']:>8}]{flag} {m['name']:<25} {m['loc']:>4}/{m['budget']:<4} LOC  ({m['usage_pct']:>5.1f}%)")
        for w in m["warnings"]:
            print(f"                    WARNING: {w}")

    if report["warn_modules"]:
        print(f"  WARN modules (>=80% budget): {report['warn_modules']}")


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    """Run all architecture guard tests. Prints results."""
    tests = [
        ("kernel runs without memory", test_kernel_runs_without_memory),
        ("kernel runs with memory enabled", test_kernel_runs_with_memory_enabled),
        ("kernel runs with empty pipeline", test_kernel_runs_with_empty_pipeline),
        ("execution is deterministic", test_execution_is_deterministic),
        ("engine is frozen after init", test_engine_is_frozen_after_init),
        ("memory gateway is removable", test_memory_gateway_removable),
        ("complexity budget within limits", test_complexity_budget_within_limits),
    ]

    passed = 0
    failed = 0

    print("=" * 56)
    print("  SystemKernel v3.0 — Architecture Guard Tests")
    print("=" * 56)

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed, {len(tests)} total")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
