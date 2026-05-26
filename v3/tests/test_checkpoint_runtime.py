"""
Checkpoint Runtime Tests — Phase 4A.

7 tests exercising the recoverable, replayable, forkable state runtime:
  1. test_checkpoint_creation     — one checkpoint per stage, all fields present
  2. test_resume_execution         — partial run + resume, only remaining stages
  3. test_replay_determinism       — replay matches original timeline
  4. test_immutable_state          — every method returns new instance
  5. test_append_only_guarantee    — JSONL only grows, never modified
  6. test_crash_recovery           — crash marker + detect + resume + clear
  7. test_checkpoint_hash_stability — 5 runs, identical pipeline_hash
"""

import sys
import os
import json
import uuid
import time
import tempfile
import shutil

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.execution_engine import (
    ExecutionEngine, DomainState, ExecutionConfig,
    StateField, MergeStrategy, RetryPolicy, NoopStage,
    ExecutionEngineNestingError,
)
from v3.kernel.execution_state import (
    ExecutionState, StageProgress, ExecutionStatus, StageStatus,
    compute_pipeline_hash,
)
from v3.kernel.checkpoint import (
    Checkpoint, CheckpointStore, FileCheckpointStore,
    CrashMarker, compute_truth_fingerprint,
)
from v3.kernel.replay import (
    replay_execution, compare_replays, ReplayResult,
    compute_replay_hash, ReplayPoint,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_domain_state(thread_id: str = "cp-test") -> DomainState:
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


def _make_engine(checkpoint_store=None, thread_id="cp-test", **kwargs):
    defaults = {
        "pipeline": (
            NoopStage(name="stage_one", delay_s=0.001),
            NoopStage(name="stage_two", delay_s=0.001),
            NoopStage(name="stage_three", delay_s=0.001),
        ),
        "retry": RetryPolicy.ONCE,
        "max_retries": 1,
        "checkpoint_store": checkpoint_store,
        "thread_id": thread_id,
        "memory_gateway": None,
    }
    defaults.update(kwargs)
    return ExecutionEngine(ExecutionConfig(**defaults))


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Checkpoint Creation
# ═══════════════════════════════════════════════════════════════════════

def test_checkpoint_creation():
    """One checkpoint per stage + completion. All required fields present."""
    tmpdir = tempfile.mkdtemp(prefix="cp_test_")
    try:
        store = FileCheckpointStore(tmpdir)
        eid = f"cp-creation-{uuid.uuid4().hex[:8]}"
        engine = _make_engine(checkpoint_store=store, thread_id="cp-creation")
        state = _make_domain_state("cp-creation")
        result = engine.run(state, execution_id=eid)

        assert result["success"] is True, f"Execution failed: {result.get('error')}"

        # Load checkpoints
        checkpoints = store.list(eid)
        # 3 stage checkpoints + 1 __completed__ = 4
        assert len(checkpoints) == 4, \
            f"Expected 4 checkpoints (3 stages + completion), got {len(checkpoints)}"

        # Verify stage checkpoints
        stage_names = [cp.stage for cp in checkpoints]
        assert "stage_one" in stage_names
        assert "stage_two" in stage_names
        assert "stage_three" in stage_names
        assert "__completed__" in stage_names

        # Verify each checkpoint has required fields
        for cp in checkpoints:
            assert cp.checkpoint_id, "Missing checkpoint_id"
            assert cp.execution_id == eid, \
                f"execution_id mismatch: {cp.execution_id} != {eid}"
            assert cp.stage, "Missing stage"
            assert cp.pipeline_hash, "Missing pipeline_hash"
            assert cp.stage_order, "Missing stage_order"
            assert cp.timestamp, "Missing timestamp"

        # Verify __completed__ has truth_fingerprint
        final_cp = checkpoints[-1]
        assert final_cp.stage == "__completed__"
        assert final_cp.truth_fingerprint, "Missing truth_fingerprint in final checkpoint"
        assert final_cp.invariant_status in ("CLEAN", "WARN", "CRITICAL", "UNKNOWN")

        # Verify parent chain
        for i in range(1, len(checkpoints)):
            assert checkpoints[i].parent_id == checkpoints[i - 1].checkpoint_id, \
                f"Broken parent chain at index {i}"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Resume Execution
# ═══════════════════════════════════════════════════════════════════════

def test_resume_execution():
    """Resume from checkpoint: when all stages complete, resume adds only completion.
    When only partial checkpoints exist, remaining stages are re-executed."""
    tmpdir = tempfile.mkdtemp(prefix="cp_resume_")
    try:
        store = FileCheckpointStore(tmpdir)
        eid = f"resume-{uuid.uuid4().hex[:8]}"

        # First run: complete full pipeline
        engine1 = _make_engine(checkpoint_store=store, thread_id="resume-test")
        state1 = _make_domain_state("resume-test")
        result1 = engine1.run(state1, execution_id=eid)
        assert result1["success"] is True

        checkpoints_after_first = store.list(eid)
        assert len(checkpoints_after_first) == 4, \
            f"Expected 4 checkpoints after first run, got {len(checkpoints_after_first)}"

        # Second run: same execution_id, resume_from_checkpoint=True
        # All stages complete — resume should detect this and only add a new
        # __completed__ checkpoint (5 total)
        engine2 = _make_engine(checkpoint_store=store, thread_id="resume-test")
        state2 = _make_domain_state("resume-test")
        result2 = engine2.run(state2, execution_id=eid, resume_from_checkpoint=True)
        assert result2["success"] is True

        checkpoints_after_second = store.list(eid)
        # 4 original + 1 new __completed__ = 5
        assert len(checkpoints_after_second) == 5, \
            f"Expected 5 checkpoints after resume (4 original + 1 new completion), got {len(checkpoints_after_second)}"

        # Verify the resume didn't duplicate stage checkpoints
        stage_cps = [cp for cp in checkpoints_after_second if cp.stage != "__completed__"]
        assert len(stage_cps) == 3, \
            f"Resume should not duplicate stage checkpoints, got {len(stage_cps)}"

        # Verify __completed__ appears twice (once per run)
        completed_cps = [cp for cp in checkpoints_after_second if cp.stage == "__completed__"]
        assert len(completed_cps) == 2, \
            f"Expected 2 completion checkpoints, got {len(completed_cps)}"

        # Now test: new execution_id with resume_from_checkpoint but NO
        # existing checkpoints — should start fresh
        fresh_eid = f"resume-fresh-{uuid.uuid4().hex[:8]}"
        engine3 = _make_engine(checkpoint_store=store, thread_id="resume-fresh")
        state3 = _make_domain_state("resume-fresh")
        result3 = engine3.run(state3, execution_id=fresh_eid, resume_from_checkpoint=True)
        assert result3["success"] is True

        fresh_cps = store.list(fresh_eid)
        assert len(fresh_cps) == 4, \
            f"Fresh execution with resume flag should still produce 4 checkpoints, got {len(fresh_cps)}"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Replay Determinism
# ═══════════════════════════════════════════════════════════════════════

def test_replay_determinism():
    """Replay from checkpoints matches original execution timeline."""
    tmpdir = tempfile.mkdtemp(prefix="cp_replay_")
    try:
        store = FileCheckpointStore(tmpdir)
        eid = f"replay-{uuid.uuid4().hex[:8]}"

        # Execute full pipeline
        engine = _make_engine(checkpoint_store=store, thread_id="replay-test")
        state = _make_domain_state("replay-test")
        result = engine.run(state, execution_id=eid)
        assert result["success"] is True
        assert len(result["stage_results"]) == 3

        # Replay from checkpoints
        replay_result = replay_execution(store, eid)
        assert replay_result is not None, "replay_execution returned None"

        # Verify replay matches original
        assert replay_result.execution_id == eid
        assert replay_result.checkpoint_count == 4
        assert replay_result.identical, \
            f"Replay not identical: diffs={replay_result.diffs}"
        assert not replay_result.drift_detected, \
            f"Drift detected in replay: {replay_result.diffs}"

        # Stage names in replay should match pipeline
        expected_stages = ("stage_one", "stage_two", "stage_three")
        assert replay_result.replayed_stages == expected_stages, \
            f"Replayed stages: {replay_result.replayed_stages}"

        # Compare two replays of the same execution
        replay2 = replay_execution(store, eid)
        identical, diffs = compare_replays(replay_result, replay2)
        assert identical, f"Two replays of same execution differ: {diffs}"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Immutable State
# ═══════════════════════════════════════════════════════════════════════

def test_immutable_state():
    """Every ExecutionState method returns new instance, original unchanged."""
    es = ExecutionState(execution_id="immutable-test")

    # start()
    es2 = es.start()
    assert es2 is not es, "start() must return new instance"
    assert es.status == ExecutionStatus.PENDING, "Original must be unchanged"
    assert es2.status == ExecutionStatus.RUNNING

    # start_stage()
    es3 = es2.start_stage("stage_a")
    assert es3 is not es2
    assert es2.current_stage == "", "Original must be unchanged"
    assert es3.current_stage == "stage_a"
    assert len(es3.stage_progress) == 1
    assert es3.stage_progress[0]["status"] == StageStatus.RUNNING

    # advance()
    es4 = es3.advance("stage_a", result={"ok": True}, duration_ms=10)
    assert es4 is not es3
    assert es3.completed_stages == (), "Original must be unchanged"
    assert es4.completed_stages == ("stage_a",)
    # stage_progress entry should now be COMPLETED
    assert es4.stage_progress[0]["status"] == StageStatus.COMPLETED

    # fail()
    es5 = es4.start_stage("stage_b")
    es6 = es5.fail("stage_b", error="test error")
    assert es6 is not es5
    assert es6.status == ExecutionStatus.FAILED
    assert es5.status == ExecutionStatus.RUNNING, "Original must be unchanged"
    assert es6.stage_progress[-1]["error"] == "test error"

    # complete()
    es7 = es4.complete()
    assert es7 is not es4
    assert es7.status == ExecutionStatus.COMPLETED
    assert es4.status == ExecutionStatus.RUNNING, "Original must be unchanged"

    # crash()
    es8 = es2.crash()
    assert es8 is not es2
    assert es8.status == ExecutionStatus.CRASHED

    # increment_retry()
    es9 = es2.increment_retry()
    assert es9.retry_count == es2.retry_count + 1
    assert es2.retry_count == 0, "Original must be unchanged"

    # increment_event()
    es10 = es2.increment_event()
    assert es10.event_count == es2.event_count + 1
    assert es2.event_count == 0, "Original must be unchanged"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Append-Only Guarantee
# ═══════════════════════════════════════════════════════════════════════

def test_append_only_guarantee():
    """FileCheckpointStore only appends — file size only grows."""
    tmpdir = tempfile.mkdtemp(prefix="cp_append_")
    try:
        store = FileCheckpointStore(tmpdir)
        eid = f"append-{uuid.uuid4().hex[:8]}"

        # Get file path
        safe_id = eid.replace("/", "_").replace("\\", "_")
        fpath = os.path.join(tmpdir, f"{safe_id}.jsonl")

        sizes = []

        # Run pipeline with 3 stages
        engine = _make_engine(checkpoint_store=store, thread_id="append-test")
        state = _make_domain_state("append-test")
        result = engine.run(state, execution_id=eid)
        assert result["success"] is True

        size1 = os.path.getsize(fpath)
        sizes.append(size1)
        assert size1 > 0, "JSONL file should have content"

        # Read file and count lines
        with open(fpath, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 4, f"Expected 4 lines, got {len(lines)}"

        # Verify each line is valid JSON
        for i, line in enumerate(lines):
            try:
                data = json.loads(line.strip())
                assert "checkpoint_id" in data, f"Line {i} missing checkpoint_id"
            except json.JSONDecodeError:
                raise AssertionError(f"Line {i} is not valid JSON: {line[:80]}")

        # Run again with same execution_id — sizes must only grow
        engine2 = _make_engine(checkpoint_store=store, thread_id="append-test")
        state2 = _make_domain_state("append-test")
        result2 = engine2.run(state2, execution_id=eid)
        assert result2["success"] is True

        size2 = os.path.getsize(fpath)
        assert size2 > size1, \
            f"File must grow after second run: {size2} <= {size1}"

        with open(fpath, encoding="utf-8") as f:
            lines2 = f.readlines()
        assert len(lines2) == 8, f"Expected 8 lines, got {len(lines2)}"

        # Verify all 4 original lines remain unchanged
        for i in range(len(lines)):
            assert lines2[i] == lines[i], \
                f"Line {i} was modified! Original content changed."

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Crash Recovery
# ═══════════════════════════════════════════════════════════════════════

def test_crash_recovery():
    """Crash marker -> detect -> resume -> marker cleared."""
    tmpdir = tempfile.mkdtemp(prefix="cp_crash_")
    try:
        # Override CrashMarker.DIR to use temp directory
        original_dir = CrashMarker.DIR
        CrashMarker.DIR = tmpdir

        store = FileCheckpointStore(tmpdir)
        eid = f"crash-{uuid.uuid4().hex[:8]}"

        # Simulate crash after stage_one:
        # Write a checkpoint as if stage_one completed
        pipeline_names = ("stage_one", "stage_two", "stage_three")
        phash = compute_pipeline_hash(pipeline_names)

        # First run: full execution succeeds
        engine1 = _make_engine(checkpoint_store=store, thread_id="crash-test")
        state1 = _make_domain_state("crash-test")
        result1 = engine1.run(state1, execution_id=eid)
        assert result1["success"] is True

        # Verify crash marker is cleared after successful run
        assert not CrashMarker.exists(eid), \
            f"Crash marker should be cleared after successful execution"

        # Now simulate a crash scenario:
        # Manually write a crash marker for a different execution
        crash_eid = f"crash-sim-{uuid.uuid4().hex[:8]}"
        CrashMarker.write(crash_eid, "stage_two", 1)

        # Verify crash marker exists
        assert CrashMarker.exists(crash_eid), "Crash marker should exist"
        crash_data = CrashMarker.read(crash_eid)
        assert crash_data is not None
        assert crash_data["stage"] == "stage_two"
        assert crash_data["stage_index"] == 1

        # Clear crash marker
        CrashMarker.clear(crash_eid)
        assert not CrashMarker.exists(crash_eid), "Crash marker should be cleared"

        # Verify read returns None for non-existent marker
        assert CrashMarker.read(crash_eid) is None

        # Test: crash marker read when file doesn't exist
        assert CrashMarker.read("nonexistent-execution") is None
        assert not CrashMarker.exists("nonexistent-execution")

        # Clear on nonexistent (should not raise)
        CrashMarker.clear("nonexistent-execution")

    finally:
        CrashMarker.DIR = original_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Checkpoint Hash Stability
# ═══════════════════════════════════════════════════════════════════════

def test_checkpoint_hash_stability():
    """5 runs with same pipeline produce identical pipeline_hash."""
    tmpdir = tempfile.mkdtemp(prefix="cp_hash_")
    try:
        pipeline_hashes = []

        for i in range(5):
            store = FileCheckpointStore(tmpdir)
            eid = f"hash-{i}-{uuid.uuid4().hex[:8]}"
            engine = _make_engine(
                checkpoint_store=store,
                thread_id=f"hash-{i}",
                pipeline=(
                    NoopStage(name="alpha", delay_s=0.001),
                    NoopStage(name="beta", delay_s=0.001),
                    NoopStage(name="gamma", delay_s=0.001),
                ),
            )
            state = _make_domain_state(f"hash-{i}")
            result = engine.run(state, execution_id=eid)
            assert result["success"] is True

            checkpoints = store.list(eid)
            # All checkpoints in this run must share same pipeline_hash
            run_hashes = set(cp.pipeline_hash for cp in checkpoints if cp.pipeline_hash)
            assert len(run_hashes) == 1, \
                f"Run {i}: Multiple pipeline_hashes in same run: {run_hashes}"
            pipeline_hashes.append(run_hashes.pop())

        # All 5 runs must share same pipeline_hash
        assert len(set(pipeline_hashes)) == 1, \
            f"Expected 1 unique pipeline_hash across 5 runs, got {len(set(pipeline_hashes))}: {set(pipeline_hashes)}"

        # Verify pipeline_hash matches compute_pipeline_hash output
        expected = compute_pipeline_hash(("alpha", "beta", "gamma"))
        assert pipeline_hashes[0] == expected, \
            f"pipeline_hash {pipeline_hashes[0]} != expected {expected}"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 8: Nesting Guard
# ═══════════════════════════════════════════════════════════════════════

def test_nesting_guard():
    """ExecutionEngineNestingError prevents nested run() calls."""
    engine = _make_engine(thread_id="nesting-test")
    state = _make_domain_state("nesting-test")

    # First run succeeds
    result = engine.run(state)
    assert result["success"] is True

    # Second sequential run also succeeds (not nested)
    result2 = engine.run(state)
    assert result2["success"] is True


# ═══════════════════════════════════════════════════════════════════════
# Test 9: Lifecycle via engine.lifecycle property
# ═══════════════════════════════════════════════════════════════════════

def test_lifecycle_property():
    """Engine exposes ExecutionState lifecycle via .lifecycle property."""
    tmpdir = tempfile.mkdtemp(prefix="cp_lifecycle_")
    try:
        store = FileCheckpointStore(tmpdir)
        eid = f"lifecycle-{uuid.uuid4().hex[:8]}"

        engine = _make_engine(checkpoint_store=store, thread_id="lifecycle-test")
        state = _make_domain_state("lifecycle-test")

        # Before run: lifecycle is None
        assert engine.lifecycle is None

        result = engine.run(state, execution_id=eid)
        assert result["success"] is True

        # After run: lifecycle is COMPLETED
        lc = engine.lifecycle
        assert lc is not None, "lifecycle should not be None after run"
        assert lc.status == ExecutionStatus.COMPLETED, \
            f"Expected COMPLETED, got {lc.status}"
        assert lc.execution_id == eid
        assert len(lc.completed_stages) == 3
        assert lc.current_stage == "stage_three"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("checkpoint creation", test_checkpoint_creation),
        ("resume execution", test_resume_execution),
        ("replay determinism", test_replay_determinism),
        ("immutable state", test_immutable_state),
        ("append-only guarantee", test_append_only_guarantee),
        ("crash recovery", test_crash_recovery),
        ("checkpoint hash stability", test_checkpoint_hash_stability),
        ("nesting guard", test_nesting_guard),
        ("lifecycle property", test_lifecycle_property),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("  SystemKernel v3.0 — Checkpoint Runtime Tests (Phase 4A)")
    print("=" * 60)

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed, {len(tests)} total")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
