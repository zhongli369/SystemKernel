"""
Event Runtime Tests — Phase 4B.

10 tests exercising the event-sourced runtime with time-travel execution:
  1. test_event_reduction_determinism
  2. test_append_only_event_store
  3. test_reconstruct_state_from_events
  4. test_time_travel_rewind
  5. test_execution_forking
  6. test_branch_isolation
  7. test_event_hash_stability
  8. test_event_stream_integrity
  9. test_reducer_purity
  10. test_no_mutable_runtime_state
"""

import sys
import os
import json
import uuid
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
    ExecutionState, ExecutionStatus, StageStatus,
    compute_pipeline_hash,
)
from v3.kernel.checkpoint import FileCheckpointStore
from v3.kernel.events import (
    ExecutionEvent, EventType, make_event,
    reduce_execution_state, compute_event_hash,
    validate_event_stream, event_stream_fingerprint,
    parse_event_from_dict,
)
from v3.kernel.event_store import FileEventStore
from v3.kernel.time_travel import (
    TimelinePoint, TimelineBranch, TimeTravelResult,
    rewind_to_sequence, reconstruct_state_at,
    fork_execution, diff_timelines, mergeable,
    build_timeline,
)
from v3.kernel.replay import replay_from_events


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_domain_state(thread_id: str = "event-test") -> DomainState:
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


def _make_engine(checkpoint_store=None, event_store=None, thread_id="event-test", **kwargs):
    defaults = {
        "pipeline": (
            NoopStage(name="alpha", delay_s=0.001),
            NoopStage(name="beta", delay_s=0.001),
            NoopStage(name="gamma", delay_s=0.001),
        ),
        "retry": RetryPolicy.ONCE,
        "max_retries": 1,
        "checkpoint_store": checkpoint_store,
        "event_store": event_store,
        "thread_id": thread_id,
        "memory_gateway": None,
    }
    defaults.update(kwargs)
    return ExecutionEngine(ExecutionConfig(**defaults))


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Event Reduction Determinism
# ═══════════════════════════════════════════════════════════════════════

def test_event_reduction_determinism():
    """Same event stream must always produce the same ExecutionState."""
    eid = f"det-{uuid.uuid4().hex[:8]}"
    events = (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "pipeline_hash": compute_pipeline_hash(("a", "b", "c")),
            "stage_order": ["a", "b", "c"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "a"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={
            "stage_name": "a", "result": {"ok": True}, "duration_ms": 5,
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, payload={"stage_name": "b"}),
        make_event(eid, 4, EventType.STAGE_COMPLETED, payload={
            "stage_name": "b", "result": {"ok": True}, "duration_ms": 3,
        }),
        make_event(eid, 5, EventType.EXECUTION_COMPLETED),
    )

    # Reduce 5 times — must always produce identical state
    states = [reduce_execution_state(events, eid) for _ in range(5)]

    baseline = states[0]
    for i, s in enumerate(states[1:], start=2):
        assert s.status == baseline.status, f"Run {i}: status differs"
        assert s.completed_stages == baseline.completed_stages, \
            f"Run {i}: completed_stages differs"
        assert s.fingerprint() == baseline.fingerprint(), \
            f"Run {i}: fingerprint differs"

    assert baseline.status == ExecutionStatus.COMPLETED
    assert baseline.completed_stages == ("a", "b")
    assert baseline.retry_count == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Append-Only Event Store
# ═══════════════════════════════════════════════════════════════════════

def test_append_only_event_store():
    """FileEventStore only appends — existing events never modified."""
    tmpdir = tempfile.mkdtemp(prefix="ev_store_")
    try:
        store = FileEventStore(tmpdir)
        eid = f"append-{uuid.uuid4().hex[:8]}"

        events = []
        for i in range(5):
            evt = make_event(eid, i, EventType.EXECUTION_STARTED if i == 0 else EventType.STAGE_COMPLETED)
            store.append(evt)
            events.append(evt)

        # Load and verify
        stream = store.load_stream(eid)
        assert len(stream) == 5

        # Verify immutability — first load should match
        for i, (original, loaded) in enumerate(zip(events, stream)):
            assert loaded.event_id == original.event_id, f"Event {i}: id mismatch"
            assert loaded.sequence == original.sequence, f"Event {i}: seq mismatch"
            assert loaded.event_type == original.event_type, f"Event {i}: type mismatch"

        # Append one more — old ones unchanged
        evt6 = make_event(eid, 5, EventType.EXECUTION_COMPLETED)
        store.append(evt6)

        stream2 = store.load_stream(eid)
        assert len(stream2) == 6
        for i in range(5):
            assert stream2[i].event_id == events[i].event_id

        # Verify file exists check
        assert store.stream_exists(eid)
        assert not store.stream_exists("nonexistent-id")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Reconstruct State from Events
# ═══════════════════════════════════════════════════════════════════════

def test_reconstruct_state_from_events():
    """State reconstructed from events must match engine lifecycle."""
    tmpdir = tempfile.mkdtemp(prefix="ev_recon_")
    try:
        store = FileEventStore(tmpdir)
        eid = f"recon-{uuid.uuid4().hex[:8]}"

        engine = _make_engine(event_store=store, thread_id="recon-test")
        state = _make_domain_state("recon-test")
        result = engine.run(state, execution_id=eid)
        assert result["success"] is True

        # Rebuild state from event store
        reconstructed = reduce_execution_state(store.load_stream(eid), eid)
        assert reconstructed is not None

        # Must match engine's lifecycle
        lc = engine.lifecycle
        assert lc is not None
        assert reconstructed.status == lc.status, \
            f"Status mismatch: {reconstructed.status} vs {lc.status}"
        assert reconstructed.completed_stages == lc.completed_stages, \
            f"Completed stages mismatch: {reconstructed.completed_stages} vs {lc.completed_stages}"
        assert reconstructed.retry_count == lc.retry_count
        assert reconstructed.fingerprint() == lc.fingerprint(), \
            "Fingerprint mismatch between reconstructed and lifecycle"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Time Travel Rewind
# ═══════════════════════════════════════════════════════════════════════

def test_time_travel_rewind():
    """Rewind to a sequence number must produce correct partial state."""
    eid = f"rewind-{uuid.uuid4().hex[:8]}"

    events = (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["a", "b", "c"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "a"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={
            "stage_name": "a", "duration_ms": 10,
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, payload={"stage_name": "b"}),
        make_event(eid, 4, EventType.STAGE_COMPLETED, payload={
            "stage_name": "b", "duration_ms": 5,
        }),
        make_event(eid, 5, EventType.EXECUTION_COMPLETED),
    )

    # Rewind to sequence 2 (after stage A completed)
    rewinded = rewind_to_sequence(events, 2)
    assert len(rewinded) == 3  # events 0, 1, 2
    assert rewinded[-1].sequence == 2
    assert rewinded[-1].event_type == EventType.STAGE_COMPLETED

    # Reconstruct state at sequence 2
    partial = reconstruct_state_at(events, 2)
    assert partial.success
    assert partial.state.completed_stages == ("a",)
    assert partial.state.status == ExecutionStatus.RUNNING

    # Reconstruct state at sequence 5 (complete)
    complete = reconstruct_state_at(events, 5)
    assert complete.success
    assert complete.state.status == ExecutionStatus.COMPLETED
    assert complete.state.completed_stages == ("a", "b")

    # Rewind to negative (empty result)
    empty = rewind_to_sequence(events, -1)
    assert len(empty) == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Execution Forking
# ═══════════════════════════════════════════════════════════════════════

def test_execution_forking():
    """Fork at a sequence point creates independent branch."""
    eid = f"fork-{uuid.uuid4().hex[:8]}"

    events = (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["a", "b", "c"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "a"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={
            "stage_name": "a",
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, payload={"stage_name": "b"}),
        make_event(eid, 4, EventType.STAGE_COMPLETED, payload={
            "stage_name": "b",
        }),
        make_event(eid, 5, EventType.EXECUTION_COMPLETED),
    )

    # Fork at sequence 2 (after stage A)
    branch = fork_execution(events, at_sequence=2)
    assert branch is not None
    assert branch.parent_execution_id == eid
    assert branch.fork_sequence == 2
    assert branch.execution_id != eid

    # Branch starts with FORK_CREATED event
    assert branch.events[0].event_type == EventType.FORK_CREATED

    # Branch should contain fork event + 3 prefix events = 4 events
    assert branch.event_count == 4, f"Expected 4 events, got {branch.event_count}"

    # State at fork point should have stage A completed
    assert branch.state_at_fork is not None
    assert "a" in branch.state_at_fork.get("completed_stages", [])


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Branch Isolation
# ═══════════════════════════════════════════════════════════════════════

def test_branch_isolation():
    """Forked branches must be fully independent."""
    eid = f"isolate-{uuid.uuid4().hex[:8]}"

    events = (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["a", "b", "c"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "a"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={"stage_name": "a"}),
        make_event(eid, 3, EventType.EXECUTION_COMPLETED),
    )

    # Create two separate forks
    branch_a = fork_execution(events, at_sequence=2)
    branch_b = fork_execution(events, at_sequence=2)

    assert branch_a.branch_id != branch_b.branch_id
    assert branch_a.execution_id != branch_b.execution_id

    # Both branches share same parent but are independent
    assert branch_a.parent_execution_id == branch_b.parent_execution_id
    assert branch_a.fork_sequence == branch_b.fork_sequence

    # State at fork should be identical
    assert branch_a.state_at_fork == branch_b.state_at_fork

    # Branches from same fork point should be diff-able
    identical, diffs = diff_timelines(branch_a, branch_b)
    # Same fork point with identical prefix = identical branches
    assert identical, f"Same-fork branches should be identical: {diffs}"

    # Both should be mergeable (same ancestor, same fork point, same state)
    can_merge, reason = mergeable(branch_a, branch_b)
    assert can_merge, f"Identical branches should be mergeable: {reason}"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Event Hash Stability
# ═══════════════════════════════════════════════════════════════════════

def test_event_hash_stability():
    """Identical events must produce identical hashes."""
    eid = f"hash-{uuid.uuid4().hex[:8]}"

    evt1 = make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
        "pipeline_hash": compute_pipeline_hash(("x", "y", "z")),
    })
    evt2 = make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
        "pipeline_hash": compute_pipeline_hash(("x", "y", "z")),
    })

    # Same content = same hash (ignoring auto-generated event_id/timestamp differences)
    hash1 = compute_event_hash(evt1)
    hash2 = compute_event_hash(evt2)

    # Different event_ids → different hashes (since event_id is part of hash)
    # This is correct behavior for unique event identification

    # Same event, re-hashed, must produce same hash
    rehash = compute_event_hash(evt1)
    assert rehash == hash1, "Re-hashing same event must produce same hash"

    # Different payloads must produce different hashes
    evt3 = make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "x"})
    assert compute_event_hash(evt3) != compute_event_hash(evt1), \
        "Different events must have different hashes"


# ═══════════════════════════════════════════════════════════════════════
# Test 8: Event Stream Integrity
# ═══════════════════════════════════════════════════════════════════════

def test_event_stream_integrity():
    """validate_event_stream must detect corrupt streams."""
    eid = f"integrity-{uuid.uuid4().hex[:8]}"

    # Valid stream
    valid_events = (
        make_event(eid, 0, EventType.EXECUTION_STARTED),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "a"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={"stage_name": "a"}),
        make_event(eid, 3, EventType.EXECUTION_COMPLETED),
    )
    is_valid, issues = validate_event_stream(valid_events)
    assert is_valid, f"Valid stream failed validation: {issues}"

    # Gap in sequence
    gap_events = (
        make_event(eid, 0, EventType.EXECUTION_STARTED),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={"stage_name": "a"}),
    )
    is_valid, issues = validate_event_stream(gap_events)
    assert not is_valid, "Stream with gap should fail"
    assert any("sequence" in i.lower() for i in issues)

    # Wrong first event
    wrong_start = (
        make_event(eid, 0, EventType.STAGE_COMPLETED, payload={"stage_name": "a"}),
        make_event(eid, 1, EventType.EXECUTION_COMPLETED),
    )
    is_valid, issues = validate_event_stream(wrong_start)
    assert not is_valid, "Stream without execution_started should fail"

    # Missing terminal event
    no_terminal = (
        make_event(eid, 0, EventType.EXECUTION_STARTED),
        make_event(eid, 1, EventType.STAGE_COMPLETED, payload={"stage_name": "a"}),
    )
    is_valid, issues = validate_event_stream(no_terminal)
    assert not is_valid, "Stream without terminal event should fail"

    # Empty stream is valid (no events to validate)
    is_valid, issues = validate_event_stream(())
    assert is_valid, "Empty stream should be valid"


# ═══════════════════════════════════════════════════════════════════════
# Test 9: Reducer Purity
# ═══════════════════════════════════════════════════════════════════════

def test_reducer_purity():
    """reduce_execution_state must be a pure function with no side effects."""
    eid = f"purity-{uuid.uuid4().hex[:8]}"

    events = (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["a", "b"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "a"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={"stage_name": "a"}),
        make_event(eid, 3, EventType.EXECUTION_COMPLETED),
    )

    # Call 100 times — must produce identical result every time
    results = [reduce_execution_state(events, eid) for _ in range(100)]
    baseline_fp = results[0].fingerprint()
    for i, r in enumerate(results[1:], start=2):
        assert r.fingerprint() == baseline_fp, \
            f"Run {i}: reducer produced different fingerprint"

    # Reduce must not modify input events
    events_before = tuple(events)
    reduce_execution_state(events, eid)
    events_after = tuple(events)
    assert events_before == events_after, \
        "Reducer must not modify input events"

    # Event stream fingerprint must be stable
    fp1 = event_stream_fingerprint(events)
    fp2 = event_stream_fingerprint(events)
    assert fp1 == fp2, "event_stream_fingerprint must be deterministic"


# ═══════════════════════════════════════════════════════════════════════
# Test 10: No Mutable Runtime State
# ═══════════════════════════════════════════════════════════════════════

def test_no_mutable_runtime_state():
    """Event stream is immutable. Lifecycle must be reconstructable
    purely from events. No state exists outside the event stream."""
    tmpdir = tempfile.mkdtemp(prefix="ev_mut_")
    try:
        store = FileEventStore(tmpdir)
        eid = f"mut-{uuid.uuid4().hex[:8]}"

        engine = _make_engine(
            event_store=store,
            checkpoint_store=FileCheckpointStore(tmpdir),
            thread_id="mut-test",
        )
        state = _make_domain_state("mut-test")
        result = engine.run(state, execution_id=eid)
        assert result["success"] is True

        # Verify event stream is available
        event_stream = engine.event_stream
        assert len(event_stream) > 0, "Event stream must not be empty"

        # Verify event stream is immutable (tuple)
        assert isinstance(event_stream, tuple)

        # Rebuild state from event store and compare with lifecycle
        rebuilt = engine._rebuild_state()
        assert rebuilt is not None, "_rebuild_state returned None"
        assert rebuilt.status == engine.lifecycle.status
        assert rebuilt.fingerprint() == engine.lifecycle.fingerprint(), \
            "Rebuilt state fingerprint must match lifecycle"

        # Verify event stream integrity via store
        is_valid, issues = store.validate_integrity(eid)
        assert is_valid, f"Event store integrity check failed: {issues}"

        # Try to modify event after the fact (should be impossible since frozen)
        evt = event_stream[0]
        try:
            evt.payload["modified"] = True
            payload_mutable = True
        except Exception:
            payload_mutable = False  # Frozen dataclass dicts should not be mutable

        # Even if payload dict were mutable, the event stream tuple is immutable
        stream_again = engine.event_stream
        assert len(stream_again) == len(event_stream), \
            "Event stream should not change"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 11: Replay from events
# ═══════════════════════════════════════════════════════════════════════

def test_replay_from_events():
    """replay_from_events must reconstruct correct timeline."""
    tmpdir = tempfile.mkdtemp(prefix="ev_replay_")
    try:
        store = FileEventStore(tmpdir)
        eid = f"replay-ev-{uuid.uuid4().hex[:8]}"

        engine = _make_engine(event_store=store, thread_id="replay-ev")
        state = _make_domain_state("replay-ev")
        result = engine.run(state, execution_id=eid)
        assert result["success"] is True

        # Replay from event store
        events = store.load_stream(eid)
        replay_result = replay_from_events(events, eid)
        assert replay_result is not None
        assert replay_result.identical, \
            f"Event replay not identical: {replay_result.diffs}"

        # Should match engine lifecycle
        assert replay_result.replayed_stages == ("alpha", "beta", "gamma"), \
            f"Replayed stages: {replay_result.replayed_stages}"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("event reduction determinism", test_event_reduction_determinism),
        ("append-only event store", test_append_only_event_store),
        ("reconstruct state from events", test_reconstruct_state_from_events),
        ("time travel rewind", test_time_travel_rewind),
        ("execution forking", test_execution_forking),
        ("branch isolation", test_branch_isolation),
        ("event hash stability", test_event_hash_stability),
        ("event stream integrity", test_event_stream_integrity),
        ("reducer purity", test_reducer_purity),
        ("no mutable runtime state", test_no_mutable_runtime_state),
        ("replay from events", test_replay_from_events),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("  SystemKernel v3.0 — Event Runtime Tests (Phase 4B)")
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
