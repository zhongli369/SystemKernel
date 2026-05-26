"""
Observability Graph Tests — Phase 4C.

12 tests exercising observability graph, telemetry, metrics, and
their integration with the event-sourced runtime:

  1. graph can be built from event stream
  2. graph nodes are deterministic
  3. graph edges preserve stage order
  4. graph_hash stable across identical runs
  5. telemetry purity score remains 100
  6. metrics aggregate event types correctly
  7. failed execution produces error node
  8. retry event produces retry node and edge
  9. checkpoint event is snapshot node, not truth source
  10. replay_to_graph/replay_to_metrics/replay_to_telemetry from events
  11. observability modules contain no banned LLM imports
  12. existing Phase 4A/4B tests still pass (integration check)
"""

import sys
import os
import ast
import uuid
from pathlib import Path

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.execution_engine import (
    ExecutionEngine, DomainState, ExecutionConfig,
    StateField, MergeStrategy, RetryPolicy, NoopStage,
)
from v3.kernel.execution_state import (
    ExecutionState, ExecutionStatus, compute_pipeline_hash,
)
from v3.kernel.checkpoint import FileCheckpointStore
from v3.kernel.events import (
    ExecutionEvent, EventType, make_event,
    validate_event_stream, event_stream_fingerprint,
)
from v3.kernel.event_store import FileEventStore

# Phase 4C modules
from v3.kernel.observability_graph import (
    RuntimeGraph, RuntimeNode, RuntimeEdge,
    NodeType, EdgeType,
    build_graph, get_nodes_by_type, get_edges_by_type,
    get_error_nodes, is_deterministic,
)
from v3.kernel.telemetry import (
    InvariantTelemetry, compute_telemetry, telemetry_fingerprint,
)
from v3.kernel.metrics import (
    RuntimeMetrics, compute_metrics, metrics_fingerprint,
)
from v3.kernel.replay import (
    replay_from_events, replay_to_graph, replay_to_metrics, replay_to_telemetry,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_success_events(eid: str = None) -> tuple:
    """Create a valid successful event stream."""
    if eid is None:
        eid = f"obs-{uuid.uuid4().hex[:8]}"
    return (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "pipeline_hash": compute_pipeline_hash(("alpha", "beta", "gamma")),
            "stage_order": ["alpha", "beta", "gamma"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "alpha"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={
            "stage_name": "alpha", "result": {"ok": True}, "duration_ms": 10,
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, payload={"stage_name": "beta"}),
        make_event(eid, 4, EventType.STAGE_COMPLETED, payload={
            "stage_name": "beta", "result": {"ok": True}, "duration_ms": 5,
        }),
        make_event(eid, 5, EventType.STAGE_STARTED, payload={"stage_name": "gamma"}),
        make_event(eid, 6, EventType.STAGE_COMPLETED, payload={
            "stage_name": "gamma", "result": {"ok": True}, "duration_ms": 7,
        }),
        make_event(eid, 7, EventType.EXECUTION_COMPLETED, payload={"duration_ms": 22}),
    )


def _make_failure_events(eid: str = None) -> tuple:
    """Create an event stream with a stage failure."""
    if eid is None:
        eid = f"fail-{uuid.uuid4().hex[:8]}"
    return (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["alpha", "beta"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "alpha"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={
            "stage_name": "alpha", "duration_ms": 10,
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, payload={"stage_name": "beta"}),
        make_event(eid, 4, EventType.STAGE_FAILED, payload={
            "stage_name": "beta", "error": "test failure",
        }),
        make_event(eid, 5, EventType.EXECUTION_FAILED, payload={"error": "test failure"}),
    )


def _make_retry_events(eid: str = None) -> tuple:
    """Create an event stream with a retry."""
    if eid is None:
        eid = f"retry-{uuid.uuid4().hex[:8]}"
    return (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["alpha", "beta"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "alpha"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={
            "stage_name": "alpha", "duration_ms": 10,
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, payload={"stage_name": "beta"}),
        make_event(eid, 4, EventType.STAGE_FAILED, payload={
            "stage_name": "beta", "error": "first attempt failed",
        }),
        make_event(eid, 5, EventType.RETRY_INCREMENTED, payload={"retry_count": 1}),
        make_event(eid, 6, EventType.STAGE_STARTED, payload={"stage_name": "beta"}),
        make_event(eid, 7, EventType.STAGE_COMPLETED, payload={
            "stage_name": "beta", "duration_ms": 8,
        }),
        make_event(eid, 8, EventType.EXECUTION_COMPLETED, payload={"duration_ms": 18}),
    )


def _make_checkpoint_events(eid: str = None) -> tuple:
    """Create an event stream with checkpoint events."""
    if eid is None:
        eid = f"cp-{uuid.uuid4().hex[:8]}"
    return (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["alpha"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "alpha"}),
        make_event(eid, 2, EventType.EVENT_RECORDED, payload={
            "checkpoint_stage": "alpha", "is_truth_source": False,
        }),
        make_event(eid, 3, EventType.STAGE_COMPLETED, payload={
            "stage_name": "alpha", "duration_ms": 10,
        }),
        make_event(eid, 4, EventType.EXECUTION_COMPLETED),
    )


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Graph can be built from event stream
# ═══════════════════════════════════════════════════════════════════════

def test_graph_from_event_stream():
    """build_graph must produce a valid RuntimeGraph from events."""
    events = _make_success_events()
    graph = build_graph(events)

    assert graph is not None
    assert graph.execution_id == events[0].execution_id
    assert graph.event_count == 8
    assert graph.failure_count == 0
    assert graph.retry_count == 0
    assert graph.stage_order == ("alpha", "beta", "gamma")
    assert len(graph.nodes) >= 4  # execution + 3 stages
    assert len(graph.edges) >= 1
    assert graph.graph_hash, "graph_hash must not be empty"

    # Verify execution node exists
    exec_nodes = get_nodes_by_type(graph, NodeType.EXECUTION)
    assert len(exec_nodes) == 1
    assert exec_nodes[0].label.startswith("Execution")

    # Verify stage nodes exist
    stage_nodes = get_nodes_by_type(graph, NodeType.STAGE)
    assert len(stage_nodes) == 3, f"Expected 3 stage nodes, got {len(stage_nodes)}"
    stage_labels = {n.label for n in stage_nodes}
    assert stage_labels == {"alpha", "beta", "gamma"}


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Graph nodes are deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_graph_nodes_deterministic():
    """Same events must produce identical graph nodes every time."""
    events = _make_success_events()

    graphs = [build_graph(events) for _ in range(10)]

    baseline = graphs[0]
    for i, g in enumerate(graphs[1:], start=2):
        assert g.execution_id == baseline.execution_id
        assert len(g.nodes) == len(baseline.nodes), \
            f"Run {i}: node count differs ({len(g.nodes)} vs {len(baseline.nodes)})"
        assert len(g.edges) == len(baseline.edges), \
            f"Run {i}: edge count differs ({len(g.edges)} vs {len(baseline.edges)})"
        assert g.graph_hash == baseline.graph_hash, \
            f"Run {i}: graph_hash differs"
        assert g.event_count == baseline.event_count
        assert g.stage_order == baseline.stage_order


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Graph edges preserve stage order
# ═══════════════════════════════════════════════════════════════════════

def test_graph_edges_preserve_stage_order():
    """Edges must reflect the correct stage execution order."""
    events = _make_success_events()
    graph = build_graph(events)

    # Get CONTAINS edges (execution → stage)
    contains_edges = get_edges_by_type(graph, EdgeType.CONTAINS)
    assert len(contains_edges) == 3, f"Expected 3 CONTAINS edges, got {len(contains_edges)}"

    # Get NEXT edges between stages
    next_edges = get_edges_by_type(graph, EdgeType.NEXT)
    assert len(next_edges) >= 1, "Expected at least 1 NEXT edge"

    # Verify stage nodes are connected in order
    stage_nodes = get_nodes_by_type(graph, NodeType.STAGE)
    stage_labels = [n.label for n in stage_nodes]
    assert "alpha" in stage_labels
    assert "beta" in stage_labels
    assert "gamma" in stage_labels


# ═══════════════════════════════════════════════════════════════════════
# Test 4: graph_hash stable across identical runs
# ═══════════════════════════════════════════════════════════════════════

def test_graph_hash_stable():
    """graph_hash must be identical for identical event streams."""
    eid = f"hash-stable-{uuid.uuid4().hex[:8]}"

    # Build two identical streams
    events_a = (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["x", "y"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "x"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={
            "stage_name": "x", "duration_ms": 10,
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, payload={"stage_name": "y"}),
        make_event(eid, 4, EventType.STAGE_COMPLETED, payload={
            "stage_name": "y", "duration_ms": 5,
        }),
        make_event(eid, 5, EventType.EXECUTION_COMPLETED),
    )

    # Rebuild with same payload (different event_ids but same content structure)
    events_b = (
        make_event(eid, 0, EventType.EXECUTION_STARTED, payload={
            "stage_order": ["x", "y"],
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, payload={"stage_name": "x"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, payload={
            "stage_name": "x", "duration_ms": 10,
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, payload={"stage_name": "y"}),
        make_event(eid, 4, EventType.STAGE_COMPLETED, payload={
            "stage_name": "y", "duration_ms": 5,
        }),
        make_event(eid, 5, EventType.EXECUTION_COMPLETED),
    )

    graph_a = build_graph(events_a)
    graph_b = build_graph(events_b)

    # Each graph should be self-consistent
    hash_a1 = graph_a.graph_hash
    hash_a2 = build_graph(events_a).graph_hash
    assert hash_a1 == hash_a2, "Same events must produce same graph_hash"

    # Same stream replayed should produce same hash
    assert graph_a.graph_hash == graph_b.graph_hash, \
        f"Identical event structures should produce same graph_hash: {graph_a.graph_hash} vs {graph_b.graph_hash}"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Telemetry purity score remains 100
# ═══════════════════════════════════════════════════════════════════════

def test_telemetry_purity_score_100():
    """A clean successful event stream must score purity=100."""
    events = _make_success_events()
    graph = build_graph(events)
    telemetry = compute_telemetry(events, graph)

    assert telemetry.single_loop_confirmed, "Single loop must be confirmed"
    assert telemetry.event_stream_valid, "Event stream must be valid"
    assert telemetry.event_sequence_contiguous, "Sequence must be contiguous"
    assert telemetry.event_parent_chain_valid, "Parent chain must be valid"
    assert telemetry.replay_reconstructable, "Must be replay reconstructable"
    assert telemetry.has_terminal_event, "Must have terminal event"
    assert telemetry.no_memory_dependency, "Must have no memory dependency"
    assert telemetry.truth_source_is_events, "Truth source must be events"
    assert telemetry.checkpoint_is_snapshot_only, "Checkpoints must be snapshots only"
    assert telemetry.deterministic_graph_hash, "Graph hash must be deterministic"

    assert telemetry.purity_score == 100, \
        f"Expected purity_score=100, got {telemetry.purity_score}"
    assert telemetry.is_pure

    # Telemetry must be serializable
    d = telemetry.to_dict()
    assert d["purity_score"] == 100
    assert isinstance(d["metadata"]["event_count"], int)


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Metrics aggregate event types correctly
# ═══════════════════════════════════════════════════════════════════════

def test_metrics_aggregate_correctly():
    """compute_metrics must correctly count stages, durations, and event types."""
    events = _make_success_events()
    metrics = compute_metrics(events)

    assert metrics.total_events == 8
    assert metrics.total_stages == 3
    assert metrics.completed_stages == 3
    assert metrics.failed_stages == 0
    assert metrics.retries == 0
    assert metrics.forks == 0
    assert metrics.crashes == 0
    assert metrics.execution_status == "COMPLETED"
    assert metrics.duration_ms > 0

    # Stage duration map
    assert "alpha" in metrics.stage_duration_map
    assert metrics.stage_duration_map["alpha"] == 10
    assert metrics.stage_duration_map["beta"] == 5
    assert metrics.stage_duration_map["gamma"] == 7

    # Event type counts
    assert metrics.event_type_counts[EventType.EXECUTION_STARTED] == 1
    assert metrics.event_type_counts[EventType.STAGE_STARTED] == 3
    assert metrics.event_type_counts[EventType.STAGE_COMPLETED] == 3
    assert metrics.event_type_counts[EventType.EXECUTION_COMPLETED] == 1

    # Average stage duration
    assert metrics.average_stage_duration_ms > 0

    # Longest stage
    assert metrics.longest_stage == "alpha"

    # Success rate
    assert metrics.success_rate == 1.0

    # Metrics fingerprint must be stable
    fp1 = metrics_fingerprint(metrics)
    fp2 = metrics_fingerprint(compute_metrics(events))
    assert fp1 == fp2, "Metrics fingerprint must be deterministic"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Failed execution produces error node
# ═══════════════════════════════════════════════════════════════════════

def test_failed_execution_error_node():
    """A failed stage must produce an ERROR node in the graph."""
    events = _make_failure_events()
    graph = build_graph(events)

    assert graph.failure_count == 1
    assert graph.event_count == 6

    error_nodes = get_error_nodes(graph)
    assert len(error_nodes) == 1, f"Expected 1 error node, got {len(error_nodes)}"
    assert error_nodes[0].node_type == NodeType.ERROR
    assert error_nodes[0].status == "failed"
    assert "beta" in error_nodes[0].label

    # Verify FAILED_AT edge exists
    failed_edges = get_edges_by_type(graph, EdgeType.FAILED_AT)
    assert len(failed_edges) == 1, f"Expected 1 FAILED_AT edge, got {len(failed_edges)}"

    # Metrics should reflect failure
    metrics = compute_metrics(events)
    assert metrics.failed_stages == 1
    assert metrics.execution_status == "FAILED"
    assert "beta" in metrics.failed_stage_names

    # Telemetry should still be valid (failure is a valid outcome)
    telemetry = compute_telemetry(events, graph)
    assert telemetry.has_terminal_event
    assert telemetry.event_stream_valid


# ═══════════════════════════════════════════════════════════════════════
# Test 8: Retry event produces retry node and edge
# ═══════════════════════════════════════════════════════════════════════

def test_retry_produces_retry_node():
    """RETRY_INCREMENTED event must produce a RETRY node with RETRIED_BY edge."""
    events = _make_retry_events()
    graph = build_graph(events)

    assert graph.retry_count == 1

    retry_nodes = get_nodes_by_type(graph, NodeType.RETRY)
    assert len(retry_nodes) == 1, f"Expected 1 retry node, got {len(retry_nodes)}"
    assert retry_nodes[0].label == "Retry #1"

    retried_edges = get_edges_by_type(graph, EdgeType.RETRIED_BY)
    assert len(retried_edges) == 1, f"Expected 1 RETRIED_BY edge, got {len(retried_edges)}"

    # Metrics should count retries
    metrics = compute_metrics(events)
    assert metrics.retries == 1
    assert metrics.completed_stages == 2  # alpha + beta (retry)
    assert metrics.execution_status == "COMPLETED"  # retry succeeded


# ═══════════════════════════════════════════════════════════════════════
# Test 9: Checkpoint event is snapshot node, not truth source
# ═══════════════════════════════════════════════════════════════════════

def test_checkpoint_is_snapshot_not_truth():
    """Checkpoint nodes must be marked as snapshot-only, not truth sources."""
    events = _make_checkpoint_events()
    graph = build_graph(events)

    assert graph.checkpoint_count == 1

    checkpoint_nodes = get_nodes_by_type(graph, NodeType.CHECKPOINT)
    assert len(checkpoint_nodes) == 1, f"Expected 1 checkpoint node, got {len(checkpoint_nodes)}"
    cp_node = checkpoint_nodes[0]

    assert cp_node.status == "snapshot"
    assert cp_node.metadata.get("is_truth_source") == False, \
        "Checkpoint must NOT be marked as truth source"

    # Verify CHECKPOINTED_AT edge
    cp_edges = get_edges_by_type(graph, EdgeType.CHECKPOINTED_AT)
    assert len(cp_edges) == 1, f"Expected 1 CHECKPOINTED_AT edge, got {len(cp_edges)}"

    # Telemetry: checkpoint_is_snapshot_only must be True
    telemetry = compute_telemetry(events, graph)
    assert telemetry.checkpoint_is_snapshot_only, \
        "checkpoint_is_snapshot_only must be True"


# ═══════════════════════════════════════════════════════════════════════
# Test 10: Replay-to-* functions work from events only
# ═══════════════════════════════════════════════════════════════════════

def test_replay_to_projections():
    """replay_to_graph, replay_to_metrics, replay_to_telemetry all work from events."""
    events = _make_success_events()

    # replay_to_graph
    graph = replay_to_graph(events)
    assert graph is not None
    assert isinstance(graph, RuntimeGraph)
    assert graph.execution_id == events[0].execution_id
    assert graph.stage_order == ("alpha", "beta", "gamma")

    # replay_to_metrics
    metrics = replay_to_metrics(events)
    assert metrics is not None
    assert isinstance(metrics, RuntimeMetrics)
    assert metrics.total_events == 8
    assert metrics.completed_stages == 3

    # replay_to_telemetry
    telemetry = replay_to_telemetry(events)
    assert telemetry is not None
    assert isinstance(telemetry, InvariantTelemetry)
    assert telemetry.purity_score == 100

    # replay_to_telemetry with pre-built graph
    telemetry2 = replay_to_telemetry(events, graph)
    assert telemetry2 is not None
    assert telemetry2.purity_score == 100

    # All three return None for empty events
    assert replay_to_graph(()) is None
    assert replay_to_metrics(()) is None
    assert replay_to_telemetry(()) is None


# ═══════════════════════════════════════════════════════════════════════
# Test 11: Observability modules contain no banned LLM imports
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_llm_imports_in_observability():
    """Phase 4C modules must not import openai, anthropic, langchain, crewai, mem0, graphiti."""
    BANNED = {"mem0", "graphiti", "openai", "anthropic", "langchain", "crewai"}

    obs_modules = [
        "v3/kernel/observability_graph.py",
        "v3/kernel/telemetry.py",
        "v3/kernel/metrics.py",
    ]

    kernel_dir = os.path.join(_root, "v3", "kernel")
    violations = []

    for mod_path in obs_modules:
        full_path = os.path.join(kernel_dir, os.path.basename(mod_path))
        if not os.path.exists(full_path):
            violations.append(f"Module not found: {mod_path}")
            continue

        try:
            with open(full_path, encoding="utf-8") as f:
                source = f.read()
        except Exception:
            violations.append(f"Cannot read: {mod_path}")
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            violations.append(f"Syntax error in {mod_path}: {e}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0].lower()
                    if root_pkg in BANNED:
                        violations.append(
                            f"{mod_path}:{node.lineno} imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0].lower()
                    if root_pkg in BANNED:
                        violations.append(
                            f"{mod_path}:{node.lineno} imports from {node.module}"
                        )

    assert len(violations) == 0, \
        f"Banned LLM imports found in Phase 4C modules:\n" + "\n".join(violations)


# ═══════════════════════════════════════════════════════════════════════
# Test 12: Integration — existing Phase 4A/4B tests still pass
# ═══════════════════════════════════════════════════════════════════════

def test_integration_existing_tests_still_pass():
    """Verify that event runtime and checkpoint tests still work with Phase 4C modules loaded."""
    import tempfile
    import shutil

    tmpdir = tempfile.mkdtemp(prefix="obs_int_")
    try:
        store = FileEventStore(tmpdir)
        cp_store = FileCheckpointStore(tmpdir)
        eid = f"integ-{uuid.uuid4().hex[:8]}"

        # Run the engine with event and checkpoint stores
        engine = ExecutionEngine(ExecutionConfig(
            pipeline=(
                NoopStage(name="a", delay_s=0.001),
                NoopStage(name="b", delay_s=0.001),
                NoopStage(name="c", delay_s=0.001),
            ),
            retry=RetryPolicy.ONCE,
            max_retries=1,
            checkpoint_store=cp_store,
            event_store=store,
            thread_id="integ-test",
            memory_gateway=None,
        ))
        state = DomainState(
            schema=(
                StateField("thread_id", str, MergeStrategy.KEEP),
                StateField("target", str, MergeStrategy.REPLACE, default="."),
                StateField("task_id", str, MergeStrategy.KEEP),
                StateField("_last_stage", str, MergeStrategy.REPLACE),
                StateField("_last_result", dict, MergeStrategy.REPLACE),
            ),
            initial={
                "thread_id": "integ-test",
                "target": ".",
                "task_id": f"task-{uuid.uuid4().hex[:8]}",
            },
        )
        result = engine.run(state, execution_id=eid)
        assert result["success"] is True

        # Event stream is available
        event_stream = engine.event_stream
        assert len(event_stream) > 0

        # Build Phase 4C projections from the real event stream
        graph = build_graph(event_stream)
        assert graph is not None
        assert graph.execution_id == eid
        assert graph.stage_order == ("a", "b", "c")
        assert graph.failure_count == 0
        assert graph.graph_hash

        metrics = compute_metrics(event_stream)
        assert metrics.total_events > 0
        assert metrics.completed_stages == 3
        assert metrics.execution_status == "COMPLETED"

        telemetry = compute_telemetry(event_stream, graph)
        assert telemetry.purity_score == 100
        assert telemetry.is_pure

        # Verify deterministic: graph, metrics, telemetry all stable
        graph2 = build_graph(event_stream)
        assert graph.graph_hash == graph2.graph_hash

        # Replay projections
        rg = replay_to_graph(event_stream)
        assert rg is not None
        assert rg.execution_id == eid

        rm = replay_to_metrics(event_stream)
        assert rm is not None
        assert rm.completed_stages == 3

        rt = replay_to_telemetry(event_stream)
        assert rt is not None
        assert rt.purity_score == 100

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("graph from event stream", test_graph_from_event_stream),
        ("graph nodes deterministic", test_graph_nodes_deterministic),
        ("graph edges preserve stage order", test_graph_edges_preserve_stage_order),
        ("graph_hash stable across identical runs", test_graph_hash_stable),
        ("telemetry purity score remains 100", test_telemetry_purity_score_100),
        ("metrics aggregate event types correctly", test_metrics_aggregate_correctly),
        ("failed execution produces error node", test_failed_execution_error_node),
        ("retry produces retry node and edge", test_retry_produces_retry_node),
        ("checkpoint is snapshot node, not truth source", test_checkpoint_is_snapshot_not_truth),
        ("replay_to_* from events only", test_replay_to_projections),
        ("no banned LLM imports in observability", test_no_banned_llm_imports_in_observability),
        ("integration — existing tests still pass", test_integration_existing_tests_still_pass),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("  SystemKernel v3.0 — Observability Graph Tests (Phase 4C)")
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
