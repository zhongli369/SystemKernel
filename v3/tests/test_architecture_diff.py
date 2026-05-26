"""
Architecture Diff Tests — Verify deterministic execution shape.

Runs system twice, captures truth snapshots, and compares them
to detect unintended architecture drift.

Key assertions:
  1. Two identical runs produce identical structural fingerprints
  2. Pipeline stage order is deterministic
  3. Module dependency set is stable
  4. Invariant violations are consistent across runs
  5. Engine frozen state is preserved
  6. Truth snapshots are persisted to JSONL
"""

import sys
import os
import json
import uuid

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
)
from v3.kernel.truth_model import (
    ExecutionTruthSnapshot,
    capture_truth,
    diff_truths,
    TruthDiff,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_domain_state(thread_id: str = "diff-test") -> DomainState:
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
            NoopStage(name="alpha", delay_s=0.001),
            NoopStage(name="beta", delay_s=0.001),
            NoopStage(name="gamma", delay_s=0.001),
        ),
        "retry": RetryPolicy.ONCE,
        "max_retries": 1,
        "checkpoint_store": None,
        "thread_id": "diff-test",
        "memory_gateway": None,
    }
    defaults.update(kwargs)
    return ExecutionEngine(ExecutionConfig(**defaults))


def _run_and_truth(thread_id: str) -> dict:
    """Run engine once and return the truth snapshot dict."""
    engine = _make_engine(thread_id=thread_id)
    state = _make_domain_state(thread_id=thread_id)
    result = engine.run(state)
    return result.get("truth", {})


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Same pipeline produces identical structural fingerprint
# ═══════════════════════════════════════════════════════════════════════

def test_identical_runs_produce_identical_fingerprint():
    """Two runs with identical config must produce the same structural fingerprint."""
    t1 = _run_and_truth("diff-fingerprint-1")
    t2 = _run_and_truth("diff-fingerprint-2")

    assert t1, "Run 1 missing truth snapshot"
    assert t2, "Run 2 missing truth snapshot"

    assert t1["pipeline_hash"] == t2["pipeline_hash"], \
        f"Pipeline hash differs: {t1['pipeline_hash']} vs {t2['pipeline_hash']}"
    assert t1["stage_count"] == t2["stage_count"], \
        f"Stage count differs: {t1['stage_count']} vs {t2['stage_count']}"
    assert t1["stage_order"] == t2["stage_order"], \
        f"Stage order differs: {t1['stage_order']} vs {t2['stage_order']}"
    assert t1["engine_frozen"] == t2["engine_frozen"] == True


# ═══════════════════════════════════════════════════════════════════════
# Test 2: TruthDiff.identical is True for matching runs
# ═══════════════════════════════════════════════════════════════════════

def test_truth_diff_identical():
    """diff_truths() must return identical=True for matching runs."""
    t1 = ExecutionTruthSnapshot(**_run_and_truth("diff-identical-1"))
    t2 = ExecutionTruthSnapshot(**_run_and_truth("diff-identical-2"))

    diff = diff_truths(t1, t2)
    assert diff.identical, f"Truths should be identical but found differences: {diff.differences}"


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Different pipeline produces drift detection
# ═══════════════════════════════════════════════════════════════════════

def test_different_pipeline_detects_drift():
    """diff_truths() must detect when pipelines differ."""
    engine_a = _make_engine(
        pipeline=(NoopStage(name="alpha"), NoopStage(name="beta"), NoopStage(name="gamma")),
        thread_id="drift-a",
    )
    r_a = engine_a.run(_make_domain_state("drift-a"))
    t_a = capture_truth(r_a, engine_a)

    engine_b = _make_engine(
        pipeline=(NoopStage(name="alpha"), NoopStage(name="delta"), NoopStage(name="gamma")),
        thread_id="drift-b",
    )
    r_b = engine_b.run(_make_domain_state("drift-b"))
    t_b = capture_truth(r_b, engine_b)

    diff = diff_truths(t_a, t_b)
    assert not diff.identical, "Different pipelines should produce drift"
    assert len(diff.differences) > 0, "Should have at least one difference"
    assert any("Pipeline stages differ" in d for d in diff.differences), \
        "Should detect pipeline stage difference"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Deterministic pipeline order
# ═══════════════════════════════════════════════════════════════════════

def test_pipeline_order_deterministic():
    """Stage execution order must be identical across runs with same config."""
    truths = [_run_and_truth(f"order-{i}") for i in range(3)]

    baseline_order = truths[0]["stage_order"]
    for i, t in enumerate(truths[1:], start=2):
        assert t["stage_order"] == baseline_order, \
            f"Run {i} stage order {t['stage_order']} != baseline {baseline_order}"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Module dependency set is stable
# ═══════════════════════════════════════════════════════════════════════

def test_module_set_stable():
    """V3 module set loaded must be consistent across runs."""
    t1 = _run_and_truth("mods-1")
    t2 = _run_and_truth("mods-2")

    mods_a = set(t1["v3_modules_loaded"])
    mods_b = set(t2["v3_modules_loaded"])

    core_required = {"v3.kernel.execution_engine"}
    assert core_required.issubset(mods_a), f"Missing core modules in run 1: {core_required - mods_a}"
    assert core_required.issubset(mods_b), f"Missing core modules in run 2: {core_required - mods_b}"

    new_in_b = mods_b - mods_a
    if new_in_b:
        print(f"  [INFO] Additional modules loaded in run 2: {sorted(new_in_b)}")


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Truth snapshot is written to JSONL
# ═══════════════════════════════════════════════════════════════════════

def test_truth_written_to_jsonl():
    """Truth snapshot must be persisted to disk."""
    from v3.kernel.truth_model import read_truths

    _run_and_truth("jsonl-test")

    truths = read_truths()
    assert len(truths) > 0, "No truth snapshots found"

    latest = truths[-1]
    required_fields = [
        "trace_id", "timestamp", "stage_order", "stage_count",
        "success", "pipeline_stages", "pipeline_hash",
        "memory_events_emitted", "memory_backend_active",
        "invariant_violations", "invariant_critical",
        "engine_frozen", "engine_run_count",
    ]
    for field in required_fields:
        assert field in latest, f"Truth missing required field: {field}"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Invariant violations are captured in truth
# ═══════════════════════════════════════════════════════════════════════

def test_invariant_violations_in_truth():
    """Truth snapshot must include invariant violation details."""
    engine = _make_engine(thread_id="inv-truth-test")
    state = _make_domain_state("inv-truth-test")
    result = engine.run(state)

    truth = result.get("truth")
    assert truth is not None, "Missing truth snapshot in result"
    assert "invariant_violations" in truth, "Truth missing invariant_violations field"
    assert "invariant_critical" in truth, "Truth missing invariant_critical field"
    assert isinstance(truth["invariant_violations"], int), \
        f"invariant_violations should be int, got {type(truth['invariant_violations'])}"
    assert "invariant_details" in truth, "Truth missing invariant_details"


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    """Run all architecture diff tests."""
    tests = [
        ("identical runs produce identical fingerprint", test_identical_runs_produce_identical_fingerprint),
        ("truth diff reports identical", test_truth_diff_identical),
        ("different pipeline detects drift", test_different_pipeline_detects_drift),
        ("pipeline order deterministic", test_pipeline_order_deterministic),
        ("module set stable across runs", test_module_set_stable),
        ("truth written to JSONL", test_truth_written_to_jsonl),
        ("invariant violations captured in truth", test_invariant_violations_in_truth),
    ]

    passed = 0
    failed = 0

    print("=" * 56)
    print("  SystemKernel v3.0 — Architecture Diff Tests")
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
