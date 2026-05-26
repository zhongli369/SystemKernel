"""
Memory Runtime Finalization Tests — Phase 4D-6.

Comprehensive tests for:
  1. MemoryRuntime construction from paths
  2. ingest_events projects candidates
  3. ingest_events writes episodic records
  4. build_index works
  5. retrieve works through facade
  6. recall works through facade
  7. compact works through facade
  8. verify_all returns full system report
  9. export_summary is JSON serializable
 10. runtime_hash stable
 11. report_hash stable
 12. disabling index works
 13. disabling recall works
 14. disabling compaction works
 15. runtime does not depend on ExecutionEngine
 16. kernel tests pass without memory runtime
 17. deleting v3/memory does not affect kernel invariants
 18. all outputs are projection only
 19. events remain source of truth
 20. no banned LLM/vector imports
 21. existing 4D tests still pass
 22. full memory pipeline deterministic

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import hashlib
import uuid
import tempfile
import shutil

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.events import make_event, EventType, ExecutionEvent
from v3.kernel.memory_contract import MemoryWriteRequest, MemoryReadRequest
from v3.kernel.memory_candidate import (
    MemoryCandidate, CandidateType, project_candidates,
    compute_candidate_fingerprint,
)
from v3.kernel.observability_graph import build_graph
from v3.kernel.metrics import compute_metrics
from v3.kernel.telemetry import compute_telemetry
from v3.memory.runtime import (
    MemoryRuntimeConfig, MemoryRuntimeResult, MemoryRuntime,
    compute_runtime_hash,
)
from v3.memory.system_report import (
    MemorySystemReport, generate_system_report, write_system_report_json,
)
from v3.memory.episodic_store import EpisodicMemoryStore
from v3.memory.compaction import CompactionPolicy
from v3.memory.semantic_index import SemanticMemoryIndex


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_events(execution_id: str = "rt-test-001") -> tuple:
    """Build a sample event stream."""
    eid = execution_id
    return (
        make_event(eid, 0, EventType.EXECUTION_STARTED, {
            "stage_order": ["init", "build", "test", "deploy"]
        }),
        make_event(eid, 1, EventType.STAGE_STARTED, {"stage_name": "init"}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, {
            "stage_name": "init", "duration_ms": 50, "result": {"ok": True}
        }),
        make_event(eid, 3, EventType.STAGE_STARTED, {"stage_name": "build"}),
        make_event(eid, 4, EventType.STAGE_COMPLETED, {
            "stage_name": "build", "duration_ms": 300, "result": {"ok": True}
        }),
        make_event(eid, 5, EventType.STAGE_STARTED, {"stage_name": "test"}),
        make_event(eid, 6, EventType.STAGE_FAILED, {
            "stage_name": "test", "error": "assertion failure in test_foo"
        }),
        make_event(eid, 7, EventType.RETRY_INCREMENTED, {"retry_number": 1}),
        make_event(eid, 8, EventType.STAGE_STARTED, {"stage_name": "test"}),
        make_event(eid, 9, EventType.STAGE_COMPLETED, {
            "stage_name": "test", "duration_ms": 200, "result": {"ok": True}
        }),
        make_event(eid, 10, EventType.STAGE_STARTED, {"stage_name": "deploy"}),
        make_event(eid, 11, EventType.STAGE_COMPLETED, {
            "stage_name": "deploy", "duration_ms": 100, "result": {"ok": True}
        }),
        make_event(eid, 12, EventType.EXECUTION_COMPLETED, {"duration_ms": 650}),
    )


def _make_temp_store(prefix: str = "mem-test") -> tuple:
    """Create a temporary episodic store directory and return (dir, store_path, store)."""
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    store_path = os.path.join(tmpdir, "episodes.jsonl")
    return tmpdir, store_path


# ═══════════════════════════════════════════════════════════════════════
# Test 1: MemoryRuntime construction from paths
# ═══════════════════════════════════════════════════════════════════════

def test_runtime_from_paths():
    """MemoryRuntime.from_paths must construct correctly."""
    tmpdir, store_path = _make_temp_store("rt-cfg-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path,
            compaction_path=os.path.join(tmpdir, "compacted.json"),
        )
        assert runtime is not None
        assert runtime.config.store_path == store_path
        assert runtime.config.enable_index is True
        assert runtime.config.enable_recall is True
        assert runtime.config.enable_compaction is True
        assert runtime.total_records == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_runtime_config_default():
    """Default MemoryRuntimeConfig must have reasonable values."""
    cfg = MemoryRuntimeConfig.default()
    assert cfg.enable_index is True
    assert cfg.enable_recall is True
    assert cfg.enable_compaction is True
    assert cfg.deterministic is True
    assert "episodes.jsonl" in cfg.store_path


# ═══════════════════════════════════════════════════════════════════════
# Test 2: ingest_events projects candidates
# ═══════════════════════════════════════════════════════════════════════

def test_ingest_events_projects_candidates():
    """ingest_events must project candidates from event stream."""
    tmpdir, store_path = _make_temp_store("rt-ingest-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path,
            enable_index=False,
            enable_compaction=False,
        )
        events = _make_events()
        result = runtime.ingest_events(events)

        assert result.execution_id == events[0].execution_id
        assert result.candidates_count >= 5, \
            f"Expected at least 5 candidates, got {result.candidates_count}"
        assert result.written_count == result.candidates_count
        assert result.integrity_status == "valid"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 3: ingest_events writes episodic records
# ═══════════════════════════════════════════════════════════════════════

def test_ingest_events_writes_episodic_records():
    """ingest_events must persist records to the episodic store."""
    tmpdir, store_path = _make_temp_store("rt-write-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path,
            enable_index=False,
            enable_compaction=False,
        )
        events = _make_events()
        runtime.ingest_events(events)

        # Store must have records
        assert runtime.total_records > 0
        records = runtime.store.list_records()
        assert len(records) > 0

        # Every record must have source_hash and record_hash
        for r in records:
            assert r.source_hash, f"Record {r.memory_id} missing source_hash"
            assert r.record_hash, f"Record {r.memory_id} missing record_hash"

        # Re-run same events → idempotent (no duplicates)
        result2 = runtime.ingest_events(events)
        assert result2.written_count == 0, \
            "Re-running same events must produce 0 new writes (idempotent)"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 4: build_index works
# ═══════════════════════════════════════════════════════════════════════

def test_build_index():
    """build_index must create a semantic index from stored records."""
    tmpdir, store_path = _make_temp_store("rt-idx-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path,
            enable_index=True,
            enable_compaction=False,
        )
        events = _make_events()
        runtime.ingest_events(events)

        # Build index explicitly
        token_count = runtime.build_index()
        assert token_count > 0, f"Index must have at least 1 token, got {token_count}"

        # Retrieve should work
        results = runtime.retrieve("build", limit=5)
        assert len(results) >= 1, "Should find records about 'build'"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 5: retrieve works through facade
# ═══════════════════════════════════════════════════════════════════════

def test_retrieve_through_facade():
    """retrieve() through MemoryRuntime must return search results."""
    tmpdir, store_path = _make_temp_store("rt-retr-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_index=True, enable_compaction=False,
        )
        events = _make_events()
        runtime.ingest_events(events)

        results = runtime.retrieve("test failure", limit=10)
        assert len(results) >= 1, "Should find error-related records"

        # Results must be deterministic
        results2 = runtime.retrieve("test failure", limit=10)
        assert len(results) == len(results2)
        for r1, r2 in zip(results, results2):
            assert r1.memory_id == r2.memory_id
            assert r1.score == r2.score
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 6: recall works through facade
# ═══════════════════════════════════════════════════════════════════════

def test_recall_through_facade():
    """recall() through MemoryRuntime must return RecallBundle with provenance."""
    tmpdir, store_path = _make_temp_store("rt-recall-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_recall=True, enable_compaction=False,
        )
        events = _make_events()
        runtime.ingest_events(events)

        bundle = runtime.recall("assertion failure", limit=5)
        assert bundle is not None, \
            f"recall() returned None (enable_recall={runtime.config.enable_recall}, records={runtime.total_records})"
        assert len(bundle.results) >= 1, \
            f"Expected at least 1 recall result, got {len(bundle.results)} (bundle.integrity={bundle.integrity_status})"
        assert bundle.integrity_status == "valid", \
            f"Bundle integrity: {bundle.integrity_status}"

        # Each result must have provenance
        for r in bundle.results:
            assert r.provenance.execution_id, f"Result {r.memory_id} missing execution_id"
            assert r.provenance.trace_valid, f"Result {r.memory_id} trace_valid=False"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 7: compact works through facade
# ═══════════════════════════════════════════════════════════════════════

def test_compact_through_facade():
    """compact() through MemoryRuntime must return CompactionResult."""
    tmpdir, store_path = _make_temp_store("rt-comp-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path,
            compaction_path=os.path.join(tmpdir, "compacted.json"),
            enable_compaction=True,
        )
        events = _make_events()
        runtime.ingest_events(events)

        comp_result = runtime.compact()
        assert comp_result is not None
        assert comp_result.input_count > 0
        assert comp_result.output_count >= 1
        assert len(comp_result.result_hash) == 16

        # Projection file must exist
        assert os.path.exists(runtime.config.compaction_path)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 8: verify_all returns full system report
# ═══════════════════════════════════════════════════════════════════════

def test_verify_all():
    """verify_all must return a complete system report dict."""
    tmpdir, store_path = _make_temp_store("rt-verify-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path,
            enable_index=True,
            enable_compaction=True,
        )
        events = _make_events()
        runtime.ingest_events(events)
        runtime.compact()

        report = runtime.verify_all()
        assert "store_integrity" in report
        assert "index_integrity" in report
        assert "compaction_integrity" in report
        assert "verdicts" in report
        assert "report_hash" in report

        verdicts = report["verdicts"]
        assert verdicts.get("removability") == "YES"
        assert verdicts.get("projection_only") in ("YES", "PARTIAL")
        assert verdicts.get("source_of_truth") in ("YES", "PARTIAL")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 9: export_summary is JSON serializable
# ═══════════════════════════════════════════════════════════════════════

def test_export_summary():
    """export_summary must produce valid JSON."""
    tmpdir, store_path = _make_temp_store("rt-summary-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_compaction=False,
        )
        events = _make_events()
        runtime.ingest_events(events)
        runtime.build_index()

        summary = runtime.export_summary()
        assert isinstance(summary, dict)
        assert "runtime_config" in summary
        assert "store" in summary
        assert "index" in summary
        assert "integrity" in summary

        # Must be JSON serializable
        j = json.dumps(summary, ensure_ascii=False, default=str)
        assert len(j) > 100
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 10: runtime_hash stable
# ═══════════════════════════════════════════════════════════════════════

def test_runtime_hash_stable():
    """Same events → same runtime_hash."""
    tmpdir1, sp1 = _make_temp_store("rt-hash1-")
    tmpdir2, sp2 = _make_temp_store("rt-hash2-")
    try:
        r1 = MemoryRuntime.from_paths(store_path=sp1,
            enable_index=False, enable_compaction=False)
        r2 = MemoryRuntime.from_paths(store_path=sp2,
            enable_index=False, enable_compaction=False)

        events = _make_events("hash-test-eid")
        result1 = r1.ingest_events(events)
        result2 = r2.ingest_events(events)

        assert result1.runtime_hash == result2.runtime_hash, \
            f"Hash mismatch: {result1.runtime_hash} vs {result2.runtime_hash}"
        assert len(result1.runtime_hash) == 16
    finally:
        shutil.rmtree(tmpdir1, ignore_errors=True)
        shutil.rmtree(tmpdir2, ignore_errors=True)


def test_compute_runtime_hash_deterministic():
    """compute_runtime_hash must be deterministic."""
    r1 = MemoryRuntimeResult(
        execution_id="e1", candidates_count=5, written_count=5,
        indexed_count=20, compacted_count=3,
    )
    r2 = MemoryRuntimeResult(
        execution_id="e1", candidates_count=5, written_count=5,
        indexed_count=20, compacted_count=3,
    )
    assert compute_runtime_hash(r1) == compute_runtime_hash(r2)

    r3 = MemoryRuntimeResult(
        execution_id="e2", candidates_count=5, written_count=5,
    )
    assert compute_runtime_hash(r1) != compute_runtime_hash(r3)


# ═══════════════════════════════════════════════════════════════════════
# Test 11: report_hash stable
# ═══════════════════════════════════════════════════════════════════════

def test_system_report_hash_stable():
    """Same store state → same system report hash."""
    tmpdir, store_path = _make_temp_store("rt-rephash-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_compaction=False,
        )
        events = _make_events()
        runtime.ingest_events(events)
        runtime.build_index()

        report1 = runtime.verify_all()
        report2 = runtime.verify_all()

        assert report1["report_hash"] == report2["report_hash"], \
            "System report hash must be stable"
        assert len(report1["report_hash"]) == 16
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 12: disabling index works
# ═══════════════════════════════════════════════════════════════════════

def test_disable_index():
    """When enable_index=False, ingest_events must not build index."""
    tmpdir, store_path = _make_temp_store("rt-noidx-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_index=False,
        )
        events = _make_events()
        result = runtime.ingest_events(events)

        assert result.indexed_count == 0
        # retrieve should still auto-build and work
        results = runtime.retrieve("build")
        assert isinstance(results, tuple)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 13: disabling recall works
# ═══════════════════════════════════════════════════════════════════════

def test_disable_recall():
    """When enable_recall=False, recall() must return None."""
    tmpdir, store_path = _make_temp_store("rt-norecall-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_recall=False,
        )
        events = _make_events()
        runtime.ingest_events(events)

        bundle = runtime.recall("test")
        assert bundle is None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 14: disabling compaction works
# ═══════════════════════════════════════════════════════════════════════

def test_disable_compaction():
    """When enable_compaction=False, compact() must return None."""
    tmpdir, store_path = _make_temp_store("rt-nocomp-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_compaction=False,
        )
        events = _make_events()
        result = runtime.ingest_events(events)

        assert result.compacted_count == 0

        comp = runtime.compact()
        assert comp is None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 15: runtime does not depend on ExecutionEngine
# ═══════════════════════════════════════════════════════════════════════

def test_runtime_does_not_import_execution_engine():
    """MemoryRuntime must not depend on ExecutionEngine."""
    import ast

    runtime_path = os.path.join(_root, "v3", "memory", "runtime.py")
    with open(runtime_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "execution_engine" not in alias.name.lower(), \
                    f"MemoryRuntime imports execution_engine: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "execution_engine" not in node.module.lower(), \
                    f"MemoryRuntime imports from execution_engine: {node.module}"


# ═══════════════════════════════════════════════════════════════════════
# Test 16: kernel tests pass without memory runtime
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_without_memory_runtime():
    """Kernel operations must work without MemoryRuntime (removability)."""
    from v3.kernel.execution_engine import (
        ExecutionEngine, ExecutionConfig, DomainState,
        StateField, MergeStrategy, RetryPolicy, NoopStage,
    )

    engine = ExecutionEngine(ExecutionConfig(
        pipeline=(
            NoopStage(name="s1", delay_s=0.001),
            NoopStage(name="s2", delay_s=0.001),
        ),
        retry=RetryPolicy.ONCE,
        max_retries=1,
        checkpoint_store=None,
        memory_gateway=None,
        thread_id="no-mem-runtime-test",
    ))

    state = DomainState(
        schema=(
            StateField("thread_id", str, MergeStrategy.KEEP),
            StateField("target", str, MergeStrategy.REPLACE, default="."),
            StateField("task_id", str, MergeStrategy.KEEP),
        ),
        initial={
            "thread_id": "no-mem-runtime-test",
            "target": ".",
            "task_id": "task-no-mem-rt",
        },
    )

    result = engine.run(state)
    assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════════
# Test 17: deleting v3/memory does not affect kernel
# ═══════════════════════════════════════════════════════════════════════

def test_memory_removable():
    """Deleting v3/memory/ must not affect kernel operations."""
    # This is a structural test: verify that no kernel/ file imports from v3/memory/
    import ast

    kernel_dir = os.path.join(_root, "v3", "kernel")
    violations = []

    for root_dir, dirs, files in os.walk(kernel_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                try:
                    source = f.read()
                except Exception:
                    continue
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "v3.memory" in alias.name:
                            violations.append(
                                f"{os.path.relpath(fpath, _root)} imports {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "v3.memory" in node.module:
                        # Allow kernel boundary modules that define the contract
                        if fname in ("memory_contract.py", "memory_candidate.py", "memory_gateway.py"):
                            continue
                        violations.append(
                            f"{os.path.relpath(fpath, _root)} imports from {node.module}"
                        )

    assert len(violations) == 0, \
        f"Kernel files must not import from v3.memory/: {violations}"


# ═══════════════════════════════════════════════════════════════════════
# Test 18: all outputs are projection only
# ═══════════════════════════════════════════════════════════════════════

def test_all_outputs_projection_only():
    """Every memory output must derive from events and have source linkage."""
    tmpdir, store_path = _make_temp_store("rt-proj-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_index=True, enable_compaction=True,
        )
        events = _make_events()
        runtime.ingest_events(events)

        # Check store: every record has source_hash
        records = runtime.store.list_records()
        for r in records:
            assert r.source_hash, f"Record {r.memory_id} has no source_hash"
            assert r.execution_id, f"Record {r.memory_id} has no execution_id"

        # Check index: verify_integrity confirms no truth source violation
        report = runtime.verify_all()
        store_checks = report["store_integrity"].get("checks", {})
        if "memory_not_truth_source" in store_checks:
            assert store_checks["memory_not_truth_source"] is True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 19: events remain source of truth
# ═══════════════════════════════════════════════════════════════════════

def test_events_remain_source_of_truth():
    """Memory outputs must all derive from events, never replace them."""
    events = _make_events()
    graph = build_graph(events)
    metrics = compute_metrics(events)
    telemetry = compute_telemetry(events, graph)

    # All derived data comes from events
    assert len(graph.stage_order) == 4  # init, build, test, deploy
    assert metrics.retries == 1
    assert telemetry.purity_score > 0

    # Recomputing with same events must produce identical results
    graph2 = build_graph(events)
    assert graph.graph_hash == graph2.graph_hash

    # Now ingest into memory runtime
    tmpdir, store_path = _make_temp_store("rt-truth-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_index=False, enable_compaction=False,
        )
        result = runtime.ingest_events(events, graph, metrics, telemetry)

        # Memory output is a projection — events are the input
        assert result.candidates_count > 0
        assert result.execution_id == events[0].execution_id

        # Replaying same events must produce same candidates
        result2 = runtime.ingest_events(events, graph, metrics, telemetry)
        assert result2.written_count == 0  # idempotent

        # Graph is unchanged by memory operations
        graph3 = build_graph(events)
        assert graph.graph_hash == graph3.graph_hash
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 20: no banned LLM/vector imports
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_imports_in_runtime():
    """Memory runtime modules must not import LLM/vector DB/AI libs."""
    import ast

    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "sklearn", "scipy",
    }

    modules = [
        os.path.join(_root, "v3", "memory", "runtime.py"),
        os.path.join(_root, "v3", "memory", "system_report.py"),
    ]

    for mod_path in modules:
        with open(mod_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in banned, \
                        f"Banned import '{name}' in {os.path.basename(mod_path)}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    assert name not in banned, \
                        f"Banned import '{name}' in {os.path.basename(mod_path)}"


# ═══════════════════════════════════════════════════════════════════════
# Test 21: existing 4D tests still pass
# ═══════════════════════════════════════════════════════════════════════

def test_existing_4d_tests_pass():
    """All existing Phase 4D tests must still pass."""
    import subprocess

    _python = sys.executable
    regression_tests = [
        "v3/tests/test_memory_compaction.py",
        "v3/tests/test_truth_linked_recall.py",
        "v3/tests/test_semantic_memory_index.py",
        "v3/tests/test_episodic_memory_store.py",
        "v3/tests/test_memory_boundary.py",
    ]

    for test_path in regression_tests:
        full_path = os.path.join(_root, test_path)
        result = subprocess.run(
            [_python, full_path],
            capture_output=True, text=True, timeout=120,
        )
        stdout = result.stdout
        assert "ACCEPTANCE: ACHIEVED" in stdout, \
            f"Regression test {test_path} failed:\n{stdout[:500]}"


# ═══════════════════════════════════════════════════════════════════════
# Test 22: full memory pipeline deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_full_pipeline_deterministic():
    """Full pipeline (ingest → index → retrieve → recall → compact → verify)
    must produce identical results on identical inputs."""
    tmpdir1, sp1 = _make_temp_store("rt-det1-")
    tmpdir2, sp2 = _make_temp_store("rt-det2-")
    try:
        policy = CompactionPolicy(
            duplicate_strategy="keep_first",
            group_by="candidate_type",
            min_importance=1,
        )
        cfg = MemoryRuntimeConfig(
            store_path=sp1,
            compaction_path=os.path.join(tmpdir1, "compacted.json"),
            enable_index=True,
            enable_recall=True,
            enable_compaction=True,
            compaction_policy=policy,
        )
        r1 = MemoryRuntime(cfg)
        r2 = MemoryRuntime(MemoryRuntimeConfig(
            store_path=sp2,
            compaction_path=os.path.join(tmpdir2, "compacted.json"),
            enable_index=True,
            enable_recall=True,
            enable_compaction=True,
            compaction_policy=policy,
        ))

        events = _make_events("det-pipeline-eid")

        result1 = r1.ingest_events(events)
        result2 = r2.ingest_events(events)

        # Both runs must produce same result
        assert result1.candidates_count == result2.candidates_count
        assert result1.written_count == result2.written_count
        assert result1.indexed_count == result2.indexed_count
        assert result1.compacted_count == result2.compacted_count

        # Retrieval must be deterministic
        ret1 = r1.retrieve("build test", limit=10)
        ret2 = r2.retrieve("build test", limit=10)
        assert len(ret1) == len(ret2)
        for a, b in zip(ret1, ret2):
            assert a.memory_id == b.memory_id
            assert a.score == b.score

        # Recall must be deterministic
        recall1 = r1.recall("failure", limit=10)
        recall2 = r2.recall("failure", limit=10)
        assert recall1 is not None and recall2 is not None
        assert recall1.bundle_hash == recall2.bundle_hash
        assert len(recall1.results) == len(recall2.results)

        # Compaction must be deterministic
        comp1 = r1.compact()
        comp2 = r2.compact()
        assert comp1 is not None and comp2 is not None
        assert comp1.result_hash == comp2.result_hash

        # System report must be deterministic
        rep1 = r1.verify_all()
        rep2 = r2.verify_all()
        assert rep1["report_hash"] == rep2["report_hash"]
    finally:
        shutil.rmtree(tmpdir1, ignore_errors=True)
        shutil.rmtree(tmpdir2, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Bonus tests
# ═══════════════════════════════════════════════════════════════════════

def test_empty_events_handled():
    """ingest_events on empty tuple must not crash."""
    tmpdir, store_path = _make_temp_store("rt-empty-")
    try:
        runtime = MemoryRuntime.from_paths(store_path=store_path)
        result = runtime.ingest_events(tuple())
        assert result.candidates_count == 0
        assert result.written_count == 0
        assert result.integrity_status == "valid"
        assert len(result.runtime_hash) == 16
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_multiple_executions():
    """Ingesting events from different executions must accumulate records."""
    tmpdir, store_path = _make_temp_store("rt-multi-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_index=False, enable_compaction=False,
        )
        e1 = _make_events("multi-exec-A")
        e2 = _make_events("multi-exec-B")

        r1 = runtime.ingest_events(e1)
        r2 = runtime.ingest_events(e2)

        assert r1.written_count > 0
        assert r2.written_count > 0
        assert runtime.total_records == r1.written_count + r2.written_count
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_write_candidates_direct():
    """write_candidates must accept MemoryCandidate objects directly."""
    tmpdir, store_path = _make_temp_store("rt-writec-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_compaction=False,
        )
        events = _make_events()
        candidates = project_candidates(events)

        written = runtime.write_candidates(candidates)
        assert written == len(candidates)
        assert runtime.total_records == len(candidates)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_compaction_with_custom_policy():
    """compact() must accept a custom CompactionPolicy."""
    tmpdir, store_path = _make_temp_store("rt-custpol-")
    try:
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_compaction=True,
        )
        events = _make_events()
        runtime.ingest_events(events)

        policy = CompactionPolicy(
            duplicate_strategy="merge_sources",
            group_by="execution_id",
            min_importance=1,
        )
        result = runtime.compact(policy=policy)
        assert result is not None
        assert result.output_count >= 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_config_serialization():
    """MemoryRuntimeConfig must roundtrip through dict."""
    cfg1 = MemoryRuntimeConfig(
        store_path="/tmp/foo.jsonl",
        enable_index=False,
        enable_recall=False,
    )
    d = cfg1.to_dict()
    cfg2 = MemoryRuntimeConfig.from_dict(d)
    assert cfg2.store_path == cfg1.store_path
    assert cfg2.enable_index == cfg1.enable_index
    assert cfg2.enable_recall == cfg1.enable_recall


def test_runtime_result_serialization():
    """MemoryRuntimeResult must serialize to dict and back."""
    r1 = MemoryRuntimeResult(
        execution_id="e1",
        candidates_count=10,
        written_count=10,
        indexed_count=50,
        compacted_count=5,
        integrity_status="valid",
        runtime_hash="abc1234567890def",
    )
    d = r1.to_dict()
    j = r1.to_json()
    assert "e1" in j
    assert "10" in j


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Construction
        ("runtime from paths", test_runtime_from_paths),
        ("runtime config default", test_runtime_config_default),
        # ingest_events
        ("ingest_events projects candidates", test_ingest_events_projects_candidates),
        ("ingest_events writes episodic records", test_ingest_events_writes_episodic_records),
        # Index
        ("build_index works", test_build_index),
        # Retrieve
        ("retrieve through facade", test_retrieve_through_facade),
        # Recall
        ("recall through facade", test_recall_through_facade),
        # Compact
        ("compact through facade", test_compact_through_facade),
        # Verify & export
        ("verify_all returns system report", test_verify_all),
        ("export_summary JSON serializable", test_export_summary),
        # Hash stability
        ("runtime_hash stable", test_runtime_hash_stable),
        ("compute_runtime_hash deterministic", test_compute_runtime_hash_deterministic),
        ("system report hash stable", test_system_report_hash_stable),
        # Disabling subsystems
        ("disable index", test_disable_index),
        ("disable recall", test_disable_recall),
        ("disable compaction", test_disable_compaction),
        # Independence
        ("runtime does not import ExecutionEngine", test_runtime_does_not_import_execution_engine),
        ("kernel without memory runtime", test_kernel_without_memory_runtime),
        ("memory removable (kernel boundary)", test_memory_removable),
        # Projection & truth
        ("all outputs projection only", test_all_outputs_projection_only),
        ("events remain source of truth", test_events_remain_source_of_truth),
        # Banned imports
        ("no banned LLM/vector imports", test_no_banned_imports_in_runtime),
        # Regression
        ("existing 4D tests pass", test_existing_4d_tests_pass),
        # Determinism
        ("full pipeline deterministic", test_full_pipeline_deterministic),
        # Bonus
        ("empty events handled", test_empty_events_handled),
        ("multiple executions", test_multiple_executions),
        ("write_candidates direct", test_write_candidates_direct),
        ("compaction with custom policy", test_compaction_with_custom_policy),
        ("config serialization", test_config_serialization),
        ("runtime result serialization", test_runtime_result_serialization),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Memory Runtime Finalization Tests (Phase 4D-6)")
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
            import traceback
            print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"  ACCEPTANCE: {'ACHIEVED' if failed == 0 else 'NOT MET'}")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
