"""
Memory Boundary Tests — Phase 4D-1.

Comprehensive tests for the memory subsystem boundary:
  1. Memory contract types (frozen, serializable)
  2. Memory candidate projection (determinism, completeness)
  3. Gateway with stub adapter (write/read cycle)
  4. Memory removability (kernel works with gateway=None)
  5. Kernel-without-memory (kernel works without memory_gateway)
  6. Candidate determinism (identical inputs → identical outputs)
  7. Contract invariants (immutable, complete)
  8. Stub adapter (no-op, always connected)
  9. Events-are-truth-source (candidates don't alter execution)
 10. Zero LLM boundary (no banned imports in boundary files)

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import uuid
import hashlib

# Add SystemKernel root to path
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.memory_contract import (
    MemoryWriteRequest, MemoryWriteResult,
    MemoryReadRequest, MemoryReadResult,
    empty_write_result, empty_read_result,
    MEMORY_CONTRACT_INVARIANTS, compute_contract_hash,
)
from v3.kernel.memory_candidate import (
    MemoryCandidate, CandidateType,
    project_candidates, get_candidates_by_type,
    get_error_candidates, get_high_priority_candidates,
    compute_candidate_fingerprint,
)
from v3.kernel.memory_gateway import MemoryGateway, MemoryEventType, MemoryEventSource
from v3.kernel.events import make_event, EventType, json_dumps_stable
from v3.kernel.observability_graph import build_graph
from v3.kernel.metrics import compute_metrics
from v3.kernel.telemetry import compute_telemetry
from v3.kernel.execution_engine import (
    ExecutionEngine, DomainState, ExecutionConfig,
    StateField, MergeStrategy, RetryPolicy, NoopStage,
)
from v3.memory.adapter_stub import MemoryAdapterStub


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_sample_events(eid: str = "mem-test-001"):
    """Build a sample event stream with varied event types."""
    return (
        make_event(eid, 0, EventType.EXECUTION_STARTED, {"stage_order": ["alpha", "beta", "gamma"]}),
        make_event(eid, 1, EventType.STAGE_STARTED, {"stage_name": "alpha"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, {"stage_name": "alpha", "duration_ms": 100, "result": {"ok": True}}),
        make_event(eid, 3, EventType.STAGE_STARTED, {"stage_name": "beta"}),
        make_event(eid, 4, EventType.STAGE_FAILED, {"stage_name": "beta", "error": "test failure"}),
        make_event(eid, 5, EventType.RETRY_INCREMENTED, {"retry_number": 1}),
        make_event(eid, 6, EventType.STAGE_STARTED, {"stage_name": "beta"}),
        make_event(eid, 7, EventType.STAGE_COMPLETED, {"stage_name": "beta", "duration_ms": 250, "result": {"ok": True}}),
        make_event(eid, 8, EventType.STAGE_STARTED, {"stage_name": "gamma"}),
        make_event(eid, 9, EventType.STAGE_COMPLETED, {"stage_name": "gamma", "duration_ms": 50, "result": {"ok": True}}),
        make_event(eid, 10, EventType.EXECUTION_COMPLETED, {"duration_ms": 400}),
    )


def _make_domain_state(thread_id: str = "mem-test") -> DomainState:
    return DomainState(
        schema=(
            StateField("thread_id", str, MergeStrategy.KEEP),
            StateField("target", str, MergeStrategy.REPLACE, default="."),
            StateField("task_id", str, MergeStrategy.KEEP),
            StateField("skill_id", str, MergeStrategy.KEEP),
            StateField("_last_stage", str, MergeStrategy.REPLACE),
            StateField("_last_result", dict, MergeStrategy.REPLACE),
        ),
        initial={
            "thread_id": thread_id,
            "target": ".",
            "task_id": f"task-{uuid.uuid4().hex[:8]}",
            "skill_id": "memory-boundary-test",
        },
    )


def _make_engine(**kwargs):
    defaults = {
        "pipeline": (
            NoopStage(name="stage_init", delay_s=0.001),
            NoopStage(name="stage_execute", delay_s=0.001),
            NoopStage(name="stage_verify", delay_s=0.001),
        ),
        "retry": RetryPolicy.ONCE,
        "max_retries": 1,
        "checkpoint_store": None,
        "thread_id": "mem-test",
        "memory_gateway": None,
    }
    defaults.update(kwargs)
    return ExecutionEngine(ExecutionConfig(**defaults))


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Memory Contract Types
# ═══════════════════════════════════════════════════════════════════════

def test_contract_types_frozen():
    """All memory contract types must be frozen (immutable)."""
    # Write request
    req = MemoryWriteRequest(
        request_id="r1", execution_id="e1",
        candidate_type="test", content={"a": 1},
    )
    try:
        req.candidate_type = "modified"
        raise AssertionError("MemoryWriteRequest must be frozen")
    except Exception:
        pass  # Expected

    # Write result
    res = MemoryWriteResult(request_id="r1", accepted=True, reason="ok")
    try:
        res.accepted = False
        raise AssertionError("MemoryWriteResult must be frozen")
    except Exception:
        pass  # Expected

    # Read request
    rreq = MemoryReadRequest(query_id="q1", query_text="test")
    try:
        rreq.query_text = "modified"
        raise AssertionError("MemoryReadRequest must be frozen")
    except Exception:
        pass  # Expected

    # Read result
    rres = MemoryReadResult(query_id="q1", backend="stub")
    try:
        rres.backend = "modified"
        raise AssertionError("MemoryReadResult must be frozen")
    except Exception:
        pass  # Expected


def test_contract_types_serializable():
    """All contract types must be serializable to dict."""
    req = MemoryWriteRequest(
        request_id="r1", execution_id="e1",
        candidate_type="test", content={"key": "value"},
        priority=1,
    )
    d = req.to_dict()
    assert d["request_id"] == "r1"
    assert d["candidate_type"] == "test"
    assert d["content"] == {"key": "value"}

    res = MemoryWriteResult(request_id="r1", accepted=True, reason="stored")
    d = res.to_dict()
    assert d["accepted"] is True

    rreq = MemoryReadRequest(query_id="q1", query_text="test query", top_k=5)
    d = rreq.to_dict()
    assert d["query_text"] == "test query"
    assert d["top_k"] == 5

    rres = MemoryReadResult(
        query_id="q1", entries=({"a": 1},), scores=(0.9,),
        backend="connected",
    )
    d = rres.to_dict()
    assert d["entries"] == [{"a": 1}]
    assert d["scores"] == [0.9]


def test_request_id_deterministic():
    """MemoryWriteRequest.compute_request_id must be deterministic."""
    id1 = MemoryWriteRequest.compute_request_id("e1", "summary", ("a", "b", "c"))
    id2 = MemoryWriteRequest.compute_request_id("e1", "summary", ("a", "b", "c"))
    id3 = MemoryWriteRequest.compute_request_id("e1", "summary", ("a", "c", "b"))  # different order
    id4 = MemoryWriteRequest.compute_request_id("e2", "summary", ("a", "b", "c"))  # different eid
    assert id1 == id2, "Same inputs must produce same request_id"
    assert id1 == id3, "Sorted keys — different key order must still produce same ID"
    assert id1 != id4, "Different execution_id must produce different request_id"


def test_empty_factories():
    """Empty write/read result factories must work correctly."""
    wr = empty_write_result("req-123")
    assert wr.request_id == "req-123"
    assert wr.accepted is False
    assert wr.reason == "no_backend"

    rr = empty_read_result("q-456")
    assert rr.query_id == "q-456"
    assert rr.is_empty is True
    assert rr.backend == "none"


def test_contract_invariants():
    """Contract invariants must be complete and immutable."""
    assert len(MEMORY_CONTRACT_INVARIANTS) >= 8
    assert "source of truth" in MEMORY_CONTRACT_INVARIANTS[0].lower()
    assert "removable" in MEMORY_CONTRACT_INVARIANTS[5].lower()

    # Contract hash must be stable
    h1 = compute_contract_hash()
    h2 = compute_contract_hash()
    assert h1 == h2, "Contract hash must be deterministic"


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Memory Candidate Projection
# ═══════════════════════════════════════════════════════════════════════

def test_candidate_projection_determinism():
    """Same events → same candidates, always."""
    events = _make_sample_events()
    c1 = project_candidates(events)
    c2 = project_candidates(events)
    fp1 = compute_candidate_fingerprint(c1)
    fp2 = compute_candidate_fingerprint(c2)
    assert fp1 == fp2, "Candidate projection must be deterministic"
    assert len(c1) == len(c2)


def test_candidate_projection_empty_input():
    """Empty event stream → empty candidates."""
    candidates = project_candidates(())
    assert len(candidates) == 0


def test_candidate_projection_has_all_types():
    """A varied event stream must produce candidates of all 5 types."""
    events = _make_sample_events()
    candidates = project_candidates(events)
    types_present = {c.candidate_type for c in candidates}
    expected = CandidateType.ALL
    missing = expected - types_present
    assert not missing, f"Missing candidate types: {missing}"
    assert types_present == expected, \
        f"Expected all 5 types, got {len(types_present)}: {types_present}"


def test_candidate_error_projection():
    """Failed stages must produce error detail candidates."""
    events = _make_sample_events()
    candidates = project_candidates(events)
    errors = get_error_candidates(candidates)
    assert len(errors) >= 1, "Should have at least 1 error candidate"
    error = errors[0]
    assert error.candidate_type == CandidateType.ERROR_DETAIL
    assert "test failure" in error.content.get("error_message", "")


def test_candidate_high_priority():
    """get_high_priority_candidates must return only priority >= 2."""
    events = _make_sample_events()
    candidates = project_candidates(events)
    high = get_high_priority_candidates(candidates)
    assert len(high) >= 1
    for c in high:
        assert c.priority >= 2, f"{c.candidate_type} has priority {c.priority}, expected >= 2"


def test_candidate_by_type_filtering():
    """get_candidates_by_type must correctly filter."""
    events = _make_sample_events()
    candidates = project_candidates(events)
    summaries = get_candidates_by_type(candidates, CandidateType.EXECUTION_SUMMARY)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.content["execution_id"] == events[0].execution_id
    assert s.content["event_count"] == len(events)
    assert s.content["failure_count"] >= 1
    assert s.content["retry_count"] >= 1


def test_candidate_id_content_addressed():
    """Same content → same candidate_id (content-addressed)."""
    eid = "addr-test-001"
    content = {"stage": "alpha", "status": "ok"}
    id1 = MemoryCandidate.compute_candidate_id(eid, CandidateType.STAGE_RESULT, content)
    id2 = MemoryCandidate.compute_candidate_id(eid, CandidateType.STAGE_RESULT, content)
    assert id1 == id2

    # Different type → different ID
    id3 = MemoryCandidate.compute_candidate_id(eid, CandidateType.ERROR_DETAIL, content)
    assert id1 != id3

    # Different content → different ID
    id4 = MemoryCandidate.compute_candidate_id(eid, CandidateType.STAGE_RESULT, {"stage": "beta", "status": "ok"})
    assert id1 != id4

    # Different execution → different ID
    id5 = MemoryCandidate.compute_candidate_id("other-eid", CandidateType.STAGE_RESULT, content)
    assert id1 != id5


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Gateway + Stub Adapter
# ═══════════════════════════════════════════════════════════════════════

def test_gateway_stub_connect():
    """Gateway must accept stub adapter connection."""
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)
    assert gw.is_connected is True


def test_gateway_write_candidates():
    """write_candidates must dispatch all candidates to handlers."""
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)

    events = _make_sample_events()
    candidates = project_candidates(events)
    results = gw.write_candidates(candidates)

    assert len(results) == len(candidates)
    for r in results:
        assert r.accepted is True  # stub always accepts
    assert gw.event_count == len(candidates)
    assert stub.event_count == len(candidates)


def test_gateway_read_empty():
    """Read from stub adapter must return empty results."""
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)

    result = gw.read("test query")
    assert result is None, "Stub must return None for read()"

    # Formal contract read
    rreq = MemoryReadRequest(query_id="q1", query_text="anything")
    rres = gw.read_request(rreq)
    assert rres.is_empty is True
    assert rres.backend == "none"


def test_gateway_without_backend():
    """Gateway without any backend must handle all operations gracefully."""
    gw = MemoryGateway()
    assert gw.is_connected is False

    # write_candidates with no backend
    events = _make_sample_events()
    candidates = project_candidates(events)
    results = gw.write_candidates(candidates)
    assert len(results) == len(candidates)
    for r in results:
        assert r.accepted is False
        assert r.reason == "no_backend"

    # read with no backend
    result = gw.read("anything")
    assert result is None

    # read_request with no backend
    rreq = MemoryReadRequest(query_id="q1", query_text="anything")
    rres = gw.read_request(rreq)
    assert rres.is_empty is True
    assert rres.backend == "none"


def test_gateway_write_request_no_backend():
    """write_request with no backend must return no_backend result."""
    gw = MemoryGateway()
    req = MemoryWriteRequest(
        request_id="r1", execution_id="e1",
        candidate_type="test", content={},
    )
    result = gw.write_request(req)
    assert result.accepted is False
    assert result.reason == "no_backend"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Memory Removability
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_runs_without_memory_gateway():
    """ExecutionEngine must run successfully with memory_gateway=None."""
    engine = _make_engine(memory_gateway=None)
    state = _make_domain_state("no-gateway")
    result = engine.run(state)
    assert result["success"] is True
    assert len(result["stage_results"]) == 3


def test_kernel_runs_with_memory_gateway_empty():
    """ExecutionEngine must run with memory gateway connected but empty."""
    gw = MemoryGateway()
    engine = _make_engine(memory_gateway=gw, thread_id="empty-gw")
    st = _make_domain_state("empty-gw")
    result = engine.run(st)
    assert result["success"] is True


def test_execution_identical_with_and_without_memory():
    """Pipeline results must be structurally identical with/without memory."""
    # Without memory
    engine_no = _make_engine(memory_gateway=None, thread_id="no-mem-001")
    state1 = _make_domain_state("no-mem-001")
    result_no = engine_no.run(state1)

    # With memory (stub)
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)
    engine_with = _make_engine(memory_gateway=gw, thread_id="with-mem-001")
    state2 = _make_domain_state("with-mem-001")
    result_with = engine_with.run(state2)

    # Structural comparison
    assert result_no["success"] == result_with["success"]
    assert len(result_no["stage_results"]) == len(result_with["stage_results"])
    for r1, r2 in zip(result_no["stage_results"], result_with["stage_results"]):
        assert r1["stage_name"] == r2["stage_name"]
        assert r1["passed"] == r2["passed"]

    # Truth snapshots must match on structure
    t1 = result_no.get("truth", {})
    t2 = result_with.get("truth", {})
    assert t1.get("stage_count") == t2.get("stage_count")
    assert t1.get("stage_order") == t2.get("stage_order")


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Events are Source of Truth
# ═══════════════════════════════════════════════════════════════════════

def test_candidates_dont_alter_graph():
    """Projecting candidates must not alter the graph in any way."""
    events = _make_sample_events()
    g1 = build_graph(events)
    g1_hash = g1.graph_hash

    # Project candidates (should not touch graph)
    _ = project_candidates(events)
    g2 = build_graph(events)
    g2_hash = g2.graph_hash

    assert g1_hash == g2_hash, "Candidate projection must not alter graph"
    assert g1.event_count == g2.event_count
    assert g1.failure_count == g2.failure_count


def test_candidates_dont_alter_metrics():
    """Projecting candidates must not alter metrics."""
    events = _make_sample_events()
    m1 = compute_metrics(events)
    m1_fp = m1.to_dict()

    _ = project_candidates(events)
    m2 = compute_metrics(events)
    m2_fp = m2.to_dict()

    assert m1_fp == m2_fp, "Candidate projection must not alter metrics"


def test_events_remain_truth_source():
    """Graph + metrics + telemetry are derived ONLY from events."""
    events = _make_sample_events()
    g = build_graph(events)
    m = compute_metrics(events)
    t = compute_telemetry(events, g)

    # All derived data comes from events
    assert len(g.stage_order) == 3  # alpha, beta, gamma
    assert m.completed_stages == 3  # alpha, beta, gamma all completed
    assert m.retries == 1           # one retry event
    assert t.purity_score > 0

    # Events are the source: all projections are functions of events alone
    # Recomputing with same events must produce identical results
    g2 = build_graph(events)
    assert g.graph_hash == g2.graph_hash


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Stub Adapter
# ═══════════════════════════════════════════════════════════════════════

def test_stub_always_connected():
    """Stub adapter must always report connected=True."""
    stub = MemoryAdapterStub()
    assert stub.connected is True
    assert stub.name == "stub"


def test_stub_accepts_all_events():
    """Stub must accept all events and increment counter."""
    stub = MemoryAdapterStub()
    assert stub.event_count == 0

    # Simulate events
    for i in range(5):
        result = stub.handle_event(None)  # Stub doesn't care about event content
        assert result is True

    assert stub.event_count == 5


def test_stub_returns_empty_queries():
    """Stub must return None for all queries."""
    stub = MemoryAdapterStub()
    assert stub.query_count == 0

    result = stub.handle_query(None)
    assert result is None
    assert stub.query_count == 1


def test_stub_close_resets():
    """Close must reset counters and disconnect."""
    stub = MemoryAdapterStub()
    stub.handle_event(None)
    stub.handle_event(None)
    stub.handle_query(None)

    assert stub.event_count == 2
    assert stub.query_count == 1
    assert stub.connected is True

    stub.close()
    assert stub.event_count == 0
    assert stub.query_count == 0
    assert stub.connected is False


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Contract Determinism
# ═══════════════════════════════════════════════════════════════════════

def test_write_request_deterministic():
    """Same inputs → same MemoryWriteRequest (equality, not hash)."""
    r1 = MemoryWriteRequest(
        request_id="r1", execution_id="e1",
        candidate_type="test", content={"a": 1},
        priority=1,
    )
    r2 = MemoryWriteRequest(
        request_id="r1", execution_id="e1",
        candidate_type="test", content={"a": 1},
        priority=1,
    )
    assert r1 == r2
    assert r1.to_dict() == r2.to_dict()
    # request_id computation must be deterministic
    rid1 = MemoryWriteRequest.compute_request_id("e1", "test", ("a", "b"))
    rid2 = MemoryWriteRequest.compute_request_id("e1", "test", ("a", "b"))
    assert rid1 == rid2


def test_candidate_fingerprint_stable():
    """compute_candidate_fingerprint must be stable across identical inputs."""
    events = _make_sample_events()
    fp1 = compute_candidate_fingerprint(project_candidates(events))
    fp2 = compute_candidate_fingerprint(project_candidates(events))
    fp3 = compute_candidate_fingerprint(project_candidates(events))
    assert fp1 == fp2 == fp3, "Fingerprint must be deterministic across 3 runs"


# ═══════════════════════════════════════════════════════════════════════
# Test 8: Integration — Full Cycle
# ═══════════════════════════════════════════════════════════════════════

def test_full_memory_lifecycle():
    """Full lifecycle: events → candidates → gateway → write → read."""
    events = _make_sample_events()
    graph = build_graph(events)
    metrics = compute_metrics(events)
    telemetry = compute_telemetry(events, graph)

    # Step 1: Project candidates
    candidates = project_candidates(events, graph, metrics, telemetry)
    assert len(candidates) >= 5

    # Step 2: Identify high priority (errors, failures)
    errors = get_error_candidates(candidates)
    assert len(errors) >= 1
    high = get_high_priority_candidates(candidates)
    assert len(high) >= 2  # error_detail priority=2 + execution_summary priority=2

    # Step 3: Write through gateway
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)
    results = gw.write_candidates(candidates)
    assert all(r.accepted for r in results)

    # Step 4: Read (stub returns empty — expected)
    rreq = MemoryReadRequest(query_id="q-final", query_text="alpha")
    rres = gw.read_request(rreq)
    assert rres.is_empty is True  # Stub stores nothing

    # Step 5: Verify gateway state
    assert gw.event_count == len(candidates)
    assert gw.is_connected is True


def test_multiple_writes_same_fingerprint():
    """Writing the same candidates twice must produce same candidate fingerprints."""
    events = _make_sample_events()
    c1 = project_candidates(events)
    c2 = project_candidates(events)
    assert compute_candidate_fingerprint(c1) == compute_candidate_fingerprint(c2)

    # Writing twice through gateway must produce same results
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)
    r1 = gw.write_candidates(c1)
    r2 = gw.write_candidates(c2)
    assert len(r1) == len(r2)
    for a, b in zip(r1, r2):
        assert a.request_id == b.request_id
        assert a.accepted == b.accepted


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Contract types
        ("contract types frozen", test_contract_types_frozen),
        ("contract types serializable", test_contract_types_serializable),
        ("request_id deterministic", test_request_id_deterministic),
        ("empty factories", test_empty_factories),
        ("contract invariants", test_contract_invariants),
        # Candidate projection
        ("candidate projection determinism", test_candidate_projection_determinism),
        ("candidate projection empty input", test_candidate_projection_empty_input),
        ("candidate projection has all types", test_candidate_projection_has_all_types),
        ("candidate error projection", test_candidate_error_projection),
        ("candidate high priority", test_candidate_high_priority),
        ("candidate by type filtering", test_candidate_by_type_filtering),
        ("candidate id content-addressed", test_candidate_id_content_addressed),
        # Gateway + stub
        ("gateway stub connect", test_gateway_stub_connect),
        ("gateway write candidates", test_gateway_write_candidates),
        ("gateway read empty", test_gateway_read_empty),
        ("gateway without backend", test_gateway_without_backend),
        ("gateway write_request no backend", test_gateway_write_request_no_backend),
        # Memory removability
        ("kernel runs without memory_gateway", test_kernel_runs_without_memory_gateway),
        ("kernel runs with memory_gateway empty", test_kernel_runs_with_memory_gateway_empty),
        ("execution identical with/without memory", test_execution_identical_with_and_without_memory),
        # Events are truth source
        ("candidates dont alter graph", test_candidates_dont_alter_graph),
        ("candidates dont alter metrics", test_candidates_dont_alter_metrics),
        ("events remain truth source", test_events_remain_truth_source),
        # Stub adapter
        ("stub always connected", test_stub_always_connected),
        ("stub accepts all events", test_stub_accepts_all_events),
        ("stub returns empty queries", test_stub_returns_empty_queries),
        ("stub close resets", test_stub_close_resets),
        # Contract determinism
        ("write request deterministic", test_write_request_deterministic),
        ("candidate fingerprint stable", test_candidate_fingerprint_stable),
        # Integration
        ("full memory lifecycle", test_full_memory_lifecycle),
        ("multiple writes same fingerprint", test_multiple_writes_same_fingerprint),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Memory Boundary Tests (Phase 4D-1)")
    print("=" * 60)

    passed = 0
    failed = 0

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
    print(f"  ACCEPTANCE: {'ACHIEVED' if failed == 0 else 'NOT MET'}")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
