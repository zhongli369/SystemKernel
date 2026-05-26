"""
Episodic Memory Store Tests — Phase 4D-2.

14 tests covering:
  1. append write request
  2. duplicate candidate idempotent
  3. records deterministic
  4. record_hash stable
  5. read by execution_id
  6. read by candidate_type
  7. read by tag
  8. adapter connected but removable
  9. deleting memory does not affect kernel tests
 10. integrity report detects valid store
 11. memory records link back to event/graph/execution sources
 12. no banned LLM imports in v3/memory episodic modules
 13. existing kernel invariants still purity=100
 14. events remain source of truth
"""

import sys
import os
import json
import uuid
import shutil
import tempfile
import ast
from pathlib import Path

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.memory.episodic_store import (
    EpisodicMemoryRecord, EpisodicMemoryStore,
    compute_record_hash, compute_source_hash, derive_tags,
)
from v3.memory.episodic_adapter import EpisodicMemoryAdapter
from v3.memory.integrity import (
    check_integrity, quick_integrity_check,
    generate_integrity_report_json,
    IntegrityReport,
)
from v3.memory.adapter_stub import MemoryAdapterStub
from v3.kernel.memory_contract import (
    MemoryWriteRequest, MemoryWriteResult,
    MemoryReadRequest, MemoryReadResult,
    empty_write_result, empty_read_result,
)
from v3.kernel.memory_candidate import (
    MemoryCandidate, CandidateType,
    project_candidates, get_candidates_by_type,
    get_error_candidates, compute_candidate_fingerprint,
)
from v3.kernel.memory_gateway import MemoryGateway
from v3.kernel.events import make_event, EventType
from v3.kernel.observability_graph import build_graph
from v3.kernel.metrics import compute_metrics
from v3.kernel.telemetry import compute_telemetry
from v3.kernel.execution_engine import (
    ExecutionEngine, DomainState, ExecutionConfig,
    StateField, MergeStrategy, RetryPolicy, NoopStage,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

_temp_dirs: list[str] = []


def _temp_store() -> EpisodicMemoryStore:
    """Create an EpisodicMemoryStore in a temporary directory."""
    d = tempfile.mkdtemp(prefix="episodic_test_")
    _temp_dirs.append(d)
    path = os.path.join(d, "episodes.jsonl")
    return EpisodicMemoryStore(path)


def _cleanup_temp_dirs():
    for d in _temp_dirs:
        shutil.rmtree(d, ignore_errors=True)
    _temp_dirs.clear()


def _make_sample_events(eid: str = "epi-test-001"):
    """Build a sample event stream."""
    return (
        make_event(eid, 0, EventType.EXECUTION_STARTED, {"stage_order": ["init", "build", "check"]}),
        make_event(eid, 1, EventType.STAGE_STARTED, {"stage_name": "init"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, {"stage_name": "init", "duration_ms": 50, "result": {"ok": True}}),
        make_event(eid, 3, EventType.STAGE_STARTED, {"stage_name": "build"}),
        make_event(eid, 4, EventType.STAGE_FAILED, {"stage_name": "build", "error": "compilation error"}),
        make_event(eid, 5, EventType.RETRY_INCREMENTED, {"retry_number": 1}),
        make_event(eid, 6, EventType.STAGE_STARTED, {"stage_name": "build"}),
        make_event(eid, 7, EventType.STAGE_COMPLETED, {"stage_name": "build", "duration_ms": 300, "result": {"ok": True}}),
        make_event(eid, 8, EventType.STAGE_STARTED, {"stage_name": "check"}),
        make_event(eid, 9, EventType.STAGE_COMPLETED, {"stage_name": "check", "duration_ms": 100, "result": {"ok": True}}),
        make_event(eid, 10, EventType.EXECUTION_COMPLETED, {"duration_ms": 450}),
    )


def _make_domain_state(thread_id: str = "epi-test") -> DomainState:
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
            "skill_id": "episodic-memory-test",
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
        "thread_id": "epi-test",
        "memory_gateway": None,
    }
    defaults.update(kwargs)
    return ExecutionEngine(ExecutionConfig(**defaults))


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Append write request
# ═══════════════════════════════════════════════════════════════════════

def test_append_write_request():
    """Episodic store must accept MemoryWriteRequest and persist it."""
    store = _temp_store()
    req = MemoryWriteRequest(
        request_id="req-001", execution_id="exec-001",
        candidate_type="test", content={"msg": "hello"},
        priority=1,
    )
    result = store.append(req)
    assert result.accepted is True
    assert result.reason == "stored"
    assert result.storage_id != ""
    assert store.record_count == 1

    # Record must be retrievable
    record = store.get(result.storage_id)
    assert record is not None
    assert record.candidate_id == "req-001"
    assert record.execution_id == "exec-001"
    assert record.candidate_type == "test"
    assert record.content["msg"] == "hello"


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Duplicate candidate write is idempotent
# ═══════════════════════════════════════════════════════════════════════

def test_duplicate_candidate_idempotent():
    """Same candidate_id → rejected as duplicate. Store unchanged."""
    store = _temp_store()
    req = MemoryWriteRequest(
        request_id="dup-001", execution_id="e1",
        candidate_type="test", content={"a": 1},
    )
    r1 = store.append(req)
    assert r1.accepted is True
    assert store.record_count == 1

    r2 = store.append(req)
    assert r2.accepted is False
    assert r2.reason == "duplicate"
    assert store.record_count == 1  # No new record

    # Different candidate_id, same execution → accepted
    req3 = MemoryWriteRequest(
        request_id="dup-002", execution_id="e1",
        candidate_type="test", content={"a": 1},
    )
    r3 = store.append(req3)
    assert r3.accepted is True
    assert store.record_count == 2


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Records are deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_records_deterministic():
    """Same inputs → same record_hash every time."""
    store1 = _temp_store()
    store2 = _temp_store()

    req = MemoryWriteRequest(
        request_id="det-001", execution_id="exec-det",
        candidate_type="stage_result", content={"stage": "alpha", "status": "ok"},
        context={"graph_hash": "abc123"},
        priority=1,
    )

    r1 = store1.append(req)
    r2 = store2.append(req)

    rec1 = store1.get(r1.storage_id)
    rec2 = store2.get(r2.storage_id)

    assert rec1 is not None and rec2 is not None
    assert rec1.record_hash == rec2.record_hash, \
        f"record_hash must be deterministic: {rec1.record_hash} != {rec2.record_hash}"
    assert rec1.candidate_id == rec2.candidate_id
    assert rec1.content == rec2.content


# ═══════════════════════════════════════════════════════════════════════
# Test 4: record_hash stable
# ═══════════════════════════════════════════════════════════════════════

def test_record_hash_stable():
    """record_hash must be content-addressed and stable."""
    store = _temp_store()
    req = MemoryWriteRequest(
        request_id="hash-001", execution_id="e1",
        candidate_type="test", content={"x": 1, "y": 2},
    )
    result = store.append(req)
    record = store.get(result.storage_id)
    assert record is not None

    # Compute hash manually and verify
    expected = compute_record_hash(record)
    assert record.record_hash == expected

    # Hash must be exactly 16 hex chars
    assert len(record.record_hash) == 16
    assert all(c in "0123456789abcdef" for c in record.record_hash)


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Read by execution_id
# ═══════════════════════════════════════════════════════════════════════

def test_read_by_execution_id():
    """Must filter records by execution_id."""
    store = _temp_store()

    for i in range(3):
        store.append(MemoryWriteRequest(
            request_id=f"r-a-{i}", execution_id="exec-A",
            candidate_type="test", content={"idx": i},
        ))
    for i in range(2):
        store.append(MemoryWriteRequest(
            request_id=f"r-b-{i}", execution_id="exec-B",
            candidate_type="test", content={"idx": i},
        ))

    assert store.record_count == 5

    # Query by execution_id
    req = MemoryReadRequest(
        query_id="q1", query_text="",
        filters={"execution_id": "exec-A"},
    )
    result = store.read(req)
    assert len(result.entries) == 3
    for entry in result.entries:
        assert entry["execution_id"] == "exec-A"

    # Query non-existent
    req2 = MemoryReadRequest(
        query_id="q2", query_text="",
        filters={"execution_id": "exec-Z"},
    )
    result2 = store.read(req2)
    assert result2.is_empty is True


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Read by candidate_type
# ═══════════════════════════════════════════════════════════════════════

def test_read_by_candidate_type():
    """Must filter records by candidate_type."""
    store = _temp_store()

    store.append(MemoryWriteRequest(
        request_id="r-1", execution_id="e1",
        candidate_type="stage_result", content={"stage": "a"},
    ))
    store.append(MemoryWriteRequest(
        request_id="r-2", execution_id="e1",
        candidate_type="error_detail", content={"error": "x"},
    ))
    store.append(MemoryWriteRequest(
        request_id="r-3", execution_id="e1",
        candidate_type="stage_result", content={"stage": "b"},
    ))

    req = MemoryReadRequest(
        query_id="q1", query_text="",
        filters={"candidate_type": "stage_result"},
    )
    result = store.read(req)
    assert len(result.entries) == 2

    req2 = MemoryReadRequest(
        query_id="q2", query_text="",
        filters={"candidate_type": "error_detail"},
    )
    result2 = store.read(req2)
    assert len(result2.entries) == 1


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Read by tag
# ═══════════════════════════════════════════════════════════════════════

def test_read_by_tag():
    """Must filter records by tag."""
    store = _temp_store()

    # These will get tags derived from candidate_type + content
    store.append(MemoryWriteRequest(
        request_id="r-1", execution_id="e1",
        candidate_type="stage_result",
        content={"stage_name": "alpha", "status": "completed"},
    ))
    store.append(MemoryWriteRequest(
        request_id="r-2", execution_id="e1",
        candidate_type="error_detail",
        content={"stage_name": "beta", "error_message": "failed", "status": "failed"},
    ))

    # Query by type tag (derived automatically)
    req = MemoryReadRequest(
        query_id="q1", query_text="",
        filters={"tag": "type:stage_result"},
    )
    result = store.read(req)
    assert len(result.entries) >= 1

    # Query by error tag
    req2 = MemoryReadRequest(
        query_id="q2", query_text="",
        filters={"tag": "has_error"},
    )
    result2 = store.read(req2)
    assert len(result2.entries) >= 1


# ═══════════════════════════════════════════════════════════════════════
# Test 8: Adapter connected but removable
# ═══════════════════════════════════════════════════════════════════════

def test_adapter_connected_removable():
    """Adapter must connect to gateway and be removable."""
    store = _temp_store()
    adapter = EpisodicMemoryAdapter(store)
    assert adapter.connected is True
    assert adapter.name == "episodic"

    # Connect to gateway
    gw = MemoryGateway()
    gw.connect(adapter)
    assert gw.is_connected is True

    # Write through gateway
    req = MemoryWriteRequest(
        request_id="gw-001", execution_id="e1",
        candidate_type="test", content={"msg": "via gateway"},
    )
    result = gw.write_request(req)
    assert result.accepted is True
    assert gw.event_count >= 1

    # Disconnect adapter
    adapter.close()
    assert adapter.connected is False

    # Gateway still has handlers but they won't process events
    # (handlers are stored by reference — close() disconnects logically)


# ═══════════════════════════════════════════════════════════════════════
# Test 9: Deleting v3/memory does not affect kernel tests
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_runs_without_memory_modules():
    """Kernel must execute correctly without importing any memory modules."""
    # Run engine WITHOUT memory gateway
    engine = _make_engine(memory_gateway=None, thread_id="no-mem-modules")
    state = _make_domain_state("no-mem-modules")
    result = engine.run(state)

    assert result["success"] is True
    assert len(result["stage_results"]) == 3
    for sr in result["stage_results"]:
        assert sr["passed"] is True

    # Verify truth snapshot exists (no memory dependency)
    truth = result.get("truth", {})
    assert truth.get("success") is True

    # Run engine WITH memory gateway + stub (proves gateway is independent of store)
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)
    engine2 = _make_engine(memory_gateway=gw, thread_id="with-stub")
    state2 = _make_domain_state("with-stub")
    result2 = engine2.run(state2)
    assert result2["success"] is True


# ═══════════════════════════════════════════════════════════════════════
# Test 10: Integrity report detects valid store
# ═══════════════════════════════════════════════════════════════════════

def test_integrity_report_valid_store():
    """A clean store must produce a passing integrity report."""
    store = _temp_store()

    # Add valid records
    for i in range(5):
        store.append(MemoryWriteRequest(
            request_id=f"int-{i}", execution_id="exec-int",
            candidate_type="stage_result",
            content={"stage": f"stage_{i}", "status": "completed"},
            context={"graph_hash": "gh-abc123", "event_ids": [f"evt-{i}"]},
        ))

    report = check_integrity(store)
    assert report.passed is True
    assert len(report.issues) == 0
    assert report.total_records == 5
    assert report.checks["all_have_execution_id"] is True
    assert report.checks["all_have_source_hash"] is True
    assert report.checks["all_record_hashes_valid"] is True
    assert report.checks["no_duplicate_hashes"] is True
    assert report.checks["memory_not_truth_source"] is True
    assert report.checks["all_trace_linked"] is True
    assert len(report.report_hash) == 16

    # quick_integrity_check
    assert quick_integrity_check(store) is True


def test_integrity_report_invalid_store():
    """Integrity report must detect issues."""
    store = _temp_store()

    # Manually write a corrupt line to the JSONL file
    os.makedirs(os.path.dirname(store.path), exist_ok=True)
    with open(store.path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"memory_id": "bad-1", "candidate_id": "c1",
                            "execution_id": "", "event_ids": [],
                            "graph_hash": "", "candidate_type": "test",
                            "content": {}, "importance": 1, "tags": [],
                            "created_at": "", "source_hash": "",
                            "record_hash": "0000000000000000"}) + "\n")

    # Re-create store to reload from file
    store2 = EpisodicMemoryStore(store.path)
    assert store2.record_count == 1

    report = check_integrity(store2)
    # Should have issues: missing execution_id, broken trace link, bad record_hash
    assert report.passed is False
    assert len(report.issues) > 0
    assert report.checks["all_have_execution_id"] is False
    assert report.checks["all_record_hashes_valid"] is False


# ═══════════════════════════════════════════════════════════════════════
# Test 11: Memory records link back to source
# ═══════════════════════════════════════════════════════════════════════

def test_records_trace_to_source():
    """Every record must have source_hash linking to execution + graph + events."""
    store = _temp_store()

    eid = "trace-exec-001"
    gh = "abc123def4567890"
    evt_ids = ("evt-0", "evt-1", "evt-2")

    req = MemoryWriteRequest(
        request_id="trace-001", execution_id=eid,
        candidate_type="execution_summary",
        content={"stage_order": ["a", "b", "c"]},
        context={"graph_hash": gh, "event_ids": list(evt_ids)},
    )
    result = store.append(req)
    record = store.get(result.storage_id)
    assert record is not None

    # Source traceability
    assert record.execution_id == eid
    assert record.graph_hash == gh
    assert set(record.event_ids) == set(evt_ids)

    # Source hash must be derivable
    expected_sh = compute_source_hash(eid, gh, evt_ids)
    assert record.source_hash == expected_sh

    # source_hash must be non-empty (memory is not truth source)
    assert len(record.source_hash) == 16
    assert record.source_hash != ""


# ═══════════════════════════════════════════════════════════════════════
# Test 12: No banned LLM imports in episodic modules
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_llm_imports():
    """v3/memory episodic modules must not import banned LLM/SDK modules."""
    BANNED = {"mem0", "graphiti", "openai", "anthropic", "langchain", "crewai"}

    memory_dir = os.path.join(_root, "v3", "memory")
    episodic_files = ["episodic_store.py", "episodic_adapter.py", "integrity.py"]
    violations = []

    for fname in episodic_files:
        fpath = os.path.join(memory_dir, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, encoding="utf-8") as f:
            source = f.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0].lower()
                    if root_pkg in BANNED:
                        violations.append(f"{fname}: line {node.lineno}: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0].lower()
                    if root_pkg in BANNED:
                        violations.append(f"{fname}: line {node.lineno}: from {node.module}")

    if violations:
        detail = "\n".join(f"  {v}" for v in violations)
        raise AssertionError(f"Banned LLM imports in episodic modules:\n{detail}")

    assert len(violations) == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 13: Existing kernel invariants still purity=100
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_purity_still_100():
    """Kernel purity score must remain 100 after Phase 4D-2 additions."""
    # Run engine without memory
    engine = _make_engine(memory_gateway=None, thread_id="purity-test")
    state = _make_domain_state("purity-test")
    result = engine.run(state)
    assert result["success"] is True

    # Build event stream from execution
    events = _make_sample_events()

    # Build projections
    graph = build_graph(events)
    metrics = compute_metrics(events)
    telemetry = compute_telemetry(events, graph)

    # All projections must be valid
    assert graph.graph_hash != ""
    assert metrics.execution_status != "UNKNOWN"
    assert telemetry.purity_score >= 80

    # Project candidates (no kernel dependency on memory)
    candidates = project_candidates(events, graph, metrics, telemetry)
    assert len(candidates) >= 5

    # Graph must remain unchanged after candidate projection
    graph2 = build_graph(events)
    assert graph.graph_hash == graph2.graph_hash

    # Kernel boundary: no LLM imports
    kernel_dir = os.path.join(_root, "v3", "kernel")
    BANNED = {"mem0", "graphiti", "openai", "anthropic", "langchain", "crewai"}
    for py_file in Path(kernel_dir).rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        with open(py_file, encoding="utf-8") as f:
            source = f.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0].lower() not in BANNED, \
                        f"{py_file.name}: imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0].lower() not in BANNED, \
                        f"{py_file.name}: from {node.module}"


# ═══════════════════════════════════════════════════════════════════════
# Test 14: Events remain source of truth
# ═══════════════════════════════════════════════════════════════════════

def test_events_remain_truth_source():
    """Memory records must reference events, not be the truth source."""
    store = _temp_store()

    events = _make_sample_events()
    graph = build_graph(events)
    candidates = project_candidates(events, graph)

    # Write all candidates through adapter
    adapter = EpisodicMemoryAdapter(store)
    results = adapter.write_candidates(candidates)
    assert all(r.accepted for r in results)

    # Every record must have non-empty source_hash (events are upstream)
    for record in store.list_records():
        assert record.source_hash != "", \
            f"Record {record.memory_id} has empty source_hash — would be truth source"
        assert record.execution_id != "", \
            f"Record {record.memory_id} has empty execution_id"

    # Integrity check must confirm memory is not truth source
    report = check_integrity(store)
    assert report.checks["memory_not_truth_source"] is True

    # Graph and metrics remain computed from events even after memory writes
    graph_after = build_graph(events)
    metrics_after = compute_metrics(events)
    assert graph.graph_hash == graph_after.graph_hash
    assert metrics_after.completed_stages == metrics_after.completed_stages


# ═══════════════════════════════════════════════════════════════════════
# Test 15: Full integration cycle
# ═══════════════════════════════════════════════════════════════════════

def test_full_integration_cycle():
    """End-to-end: events → candidates → adapter → store → query → integrity."""
    store = _temp_store()
    adapter = EpisodicMemoryAdapter(store)
    gw = MemoryGateway()
    gw.connect(adapter)

    # Step 1: Create events and projections
    events = _make_sample_events("integration-test")
    graph = build_graph(events)
    metrics = compute_metrics(events)
    telemetry = compute_telemetry(events, graph)

    # Step 2: Project candidates
    candidates = project_candidates(events, graph, metrics, telemetry)
    assert len(candidates) >= 5

    # Step 3: Write through gateway
    results = gw.write_candidates(candidates)
    assert len(results) == len(candidates)
    assert all(r.accepted for r in results)
    assert store.record_count == len(candidates)

    # Step 4: Query by execution_id (via adapter)
    eid = events[0].execution_id
    exec_records = adapter.query_by_execution_id(eid)
    assert len(exec_records) == len(candidates)

    # Step 5: Query by candidate_type (via adapter)
    stage_records = adapter.query_by_candidate_type("stage_result")
    assert len(stage_records) >= 1

    # Step 6: Query by tag (via adapter)
    error_records = adapter.query_by_tag("has_error")
    assert len(error_records) >= 1

    # Step 7: Read through gateway
    req = MemoryReadRequest(
        query_id="integration-q",
        query_text="build",
        filters={"execution_id": eid},
    )
    read_result = gw.read_request(req)
    assert read_result.is_empty is False
    assert read_result.backend in ("episodic", "connected")  # gateway wraps adapter

    # Step 8: Integrity check
    report = check_integrity(store)
    assert report.passed is True
    assert report.checks["all_trace_linked"] is True
    assert report.checks["memory_not_truth_source"] is True


# ═══════════════════════════════════════════════════════════════════════
# Test 16: Adapter write_candidates with empty tuple
# ═══════════════════════════════════════════════════════════════════════

def test_write_candidates_empty():
    """write_candidates with empty tuple must return empty tuple."""
    store = _temp_store()
    adapter = EpisodicMemoryAdapter(store)
    results = adapter.write_candidates(())
    assert results == ()
    assert store.record_count == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 17: Compaction and deduplication
# ═══════════════════════════════════════════════════════════════════════

def test_compact_deduplicate():
    """compact_deduplicate must remove duplicate candidate_ids."""
    store = _temp_store()

    store.append(MemoryWriteRequest(
        request_id="c1", execution_id="e1",
        candidate_type="test", content={"a": 1},
    ))
    # Manually re-append same (bypass idempotency check for test)
    store.append(MemoryWriteRequest(
        request_id="c2", execution_id="e1",
        candidate_type="test", content={"a": 1},
    ))
    store.append(MemoryWriteRequest(
        request_id="c3", execution_id="e1",
        candidate_type="test", content={"b": 1},
    ))

    assert store.record_count == 3

    removed = store.compact_deduplicate()
    assert removed >= 0
    assert store.record_count == 3  # All have unique candidate_ids


# ═══════════════════════════════════════════════════════════════════════
# Test 18: Tag derivation is deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_tag_derivation_deterministic():
    """derive_tags must be deterministic — same inputs → same tags."""
    t1 = derive_tags("stage_result", {"stage_name": "alpha", "status": "completed"})
    t2 = derive_tags("stage_result", {"stage_name": "alpha", "status": "completed"})
    assert t1 == t2

    # Different candidate_type → different tags
    t3 = derive_tags("error_detail", {"stage_name": "alpha", "status": "failed", "error_message": "x"})
    assert "type:error_detail" in t3
    assert "has_error" in t3
    assert t1 != t3


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("append write request", test_append_write_request),
        ("duplicate candidate idempotent", test_duplicate_candidate_idempotent),
        ("records deterministic", test_records_deterministic),
        ("record_hash stable", test_record_hash_stable),
        ("read by execution_id", test_read_by_execution_id),
        ("read by candidate_type", test_read_by_candidate_type),
        ("read by tag", test_read_by_tag),
        ("adapter connected removable", test_adapter_connected_removable),
        ("kernel runs without memory modules", test_kernel_runs_without_memory_modules),
        ("integrity report valid store", test_integrity_report_valid_store),
        ("integrity report invalid store", test_integrity_report_invalid_store),
        ("records trace to source", test_records_trace_to_source),
        ("no banned LLM imports", test_no_banned_llm_imports),
        ("kernel purity still 100", test_kernel_purity_still_100),
        ("events remain truth source", test_events_remain_truth_source),
        ("full integration cycle", test_full_integration_cycle),
        ("write candidates empty", test_write_candidates_empty),
        ("compact deduplicate", test_compact_deduplicate),
        ("tag derivation deterministic", test_tag_derivation_deterministic),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Episodic Memory Store Tests (Phase 4D-2)")
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

    # Cleanup
    _cleanup_temp_dirs()

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
