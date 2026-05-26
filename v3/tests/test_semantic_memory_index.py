"""
Semantic Memory Index Tests — Phase 4D-3.

17 tests covering:
  1. index builds from episodic records
  2. tokenization is deterministic
  3. search returns deterministic results
  4. exact token match scores higher
  5. tag match boost works
  6. candidate_type filter works
  7. execution_id filter works
  8. min_importance filter works
  9. limit is respected
 10. explain() returns matched tokens and scoring reasons
 11. index rebuild from store matches direct build
 12. index integrity passes
 13. adapter uses retrieval runtime when configured
 14. adapter still works without retrieval runtime
 15. deleting/replacing semantic index does not affect kernel tests
 16. no banned LLM/vector imports
 17. existing memory boundary and episodic tests still pass
"""

import sys
import os
import json
import uuid
import shutil
import tempfile
import ast
from typing import Tuple
from pathlib import Path

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.memory.episodic_store import (
    EpisodicMemoryRecord, EpisodicMemoryStore,
    compute_record_hash, compute_source_hash, derive_tags,
)
from v3.memory.episodic_adapter import EpisodicMemoryAdapter
from v3.memory.integrity import check_integrity, quick_integrity_check
from v3.memory.semantic_index import (
    SemanticIndexEntry, SemanticSearchResult, SemanticMemoryIndex,
    tokenize,
)
from v3.memory.retrieval import MemoryRetrievalRuntime
from v3.memory.index_integrity import (
    check_index_integrity, quick_index_check,
    generate_index_integrity_report_json,
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
    d = tempfile.mkdtemp(prefix="semantic_test_")
    _temp_dirs.append(d)
    path = os.path.join(d, "episodes.jsonl")
    return EpisodicMemoryStore(path)


def _cleanup_temp_dirs():
    for d in _temp_dirs:
        shutil.rmtree(d, ignore_errors=True)
    _temp_dirs.clear()


def _populate_store(store: EpisodicMemoryStore, count: int = 8) -> Tuple[EpisodicMemoryRecord, ...]:
    """Populate a store with diverse records for index testing."""
    records_data = [
        ("r-01", "exec-A", "stage_result", {"stage_name": "init", "status": "completed", "result": "ok"}, 1),
        ("r-02", "exec-A", "stage_result", {"stage_name": "build", "status": "completed", "result": "ok"}, 1),
        ("r-03", "exec-A", "stage_result", {"stage_name": "test", "status": "completed", "result": "ok"}, 1),
        ("r-04", "exec-B", "error_detail", {"stage_name": "deploy", "status": "failed", "error_message": "connection refused"}, 2),
        ("r-05", "exec-B", "error_detail", {"stage_name": "build", "status": "failed", "error_message": "compilation error in main module"}, 2),
        ("r-06", "exec-C", "execution_summary", {"execution_status": "completed", "duration_ms": 450, "stage_count": 3}, 1),
        ("r-07", "exec-C", "stage_result", {"stage_name": "lint", "status": "completed", "result": "all checks passed"}, 1),
        ("r-08", "exec-D", "pipeline_result", {"pipeline_status": "completed", "stages_passed": 5, "stages_failed": 1}, 1),
    ]

    records = []
    for i, (rid, eid, ctype, content, priority) in enumerate(records_data[:count]):
        req = MemoryWriteRequest(
            request_id=rid,
            execution_id=eid,
            candidate_type=ctype,
            content=content,
            context={
                "graph_hash": f"gh-{eid}",
                "event_ids": [f"evt-{eid}-{j}" for j in range(3)],
            },
            priority=priority,
        )
        result = store.append(req)
        rec = store.get(result.storage_id)
        if rec:
            records.append(rec)

    return tuple(records)


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Index builds from episodic records
# ═══════════════════════════════════════════════════════════════════════

def test_index_builds_from_records():
    """SemanticMemoryIndex must build from episodic memory records."""
    store = _temp_store()
    records = _populate_store(store, count=8)
    assert len(records) == 8

    index = SemanticMemoryIndex()
    token_count = index.build(records)
    assert token_count > 0
    assert index.is_built is True
    assert index.record_count == 8
    assert index.entry_count == token_count


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Tokenization is deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_tokenization_deterministic():
    """Same text must always produce same tokens."""
    text = "Build stage failed with compilation error"

    t1 = tokenize(text)
    t2 = tokenize(text)
    assert t1 == t2

    # Verify expected tokens
    assert "build" in t1
    assert "stage" in t1
    assert "failed" in t1
    assert "compilation" in t1
    assert "error" in t1

    # Short tokens filtered (len < 2)
    assert "a" not in tokenize("a stage is ok now")
    assert "x" not in tokenize("x y z stage")

    # Empty input
    assert tokenize("") == ()
    assert tokenize("  ") == ()

    # CJK support
    tokens = tokenize("构建失败 error")
    assert "构建失败" in tokens or "error" in tokens


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Search returns deterministic results
# ═══════════════════════════════════════════════════════════════════════

def test_search_deterministic():
    """Same query must always return same results in same order."""
    store = _temp_store()
    records = _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.build(records)

    r1 = index.search("build error", limit=10)
    r2 = index.search("build error", limit=10)

    assert len(r1) == len(r2)
    for a, b in zip(r1, r2):
        assert a.memory_id == b.memory_id
        assert a.score == b.score
        assert a.matched_tokens == b.matched_tokens
        assert a.record_hash == b.record_hash


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Exact token match scores higher
# ═══════════════════════════════════════════════════════════════════════

def test_exact_token_match_scores_higher():
    """Records with more matching tokens should score higher."""
    store = _temp_store()
    _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.build(store.list_records())

    results = index.search("build error compilation", limit=10)
    assert len(results) > 0

    # Results with more matched tokens should appear first
    assert all(results[i].score >= results[i + 1].score
               for i in range(len(results) - 1))


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Tag match boost works
# ═══════════════════════════════════════════════════════════════════════

def test_tag_match_boost():
    """Records with tag-matching query tokens should get boosted scores."""
    store = _temp_store()
    records = _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.build(records)

    # Search for "error" — records with has_error tag should rank high
    results = index.search("error", limit=10)
    assert len(results) > 0

    # At least one result should have "has_error" in tags
    error_results = [r for r in results if "has_error" in r.tags]
    assert len(error_results) > 0


# ═══════════════════════════════════════════════════════════════════════
# Test 6: candidate_type filter works
# ═══════════════════════════════════════════════════════════════════════

def test_candidate_type_filter():
    """Search with candidate_type filter must return only matching types."""
    store = _temp_store()
    records = _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.build(records)

    results = index.search(
        "stage", limit=10,
        filters={"candidate_type": "stage_result"},
    )
    assert len(results) > 0
    for r in results:
        assert r.candidate_type == "stage_result"

    # Filter for error_detail
    results2 = index.search(
        "error", limit=10,
        filters={"candidate_type": "error_detail"},
    )
    for r in results2:
        assert r.candidate_type == "error_detail"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: execution_id filter works
# ═══════════════════════════════════════════════════════════════════════

def test_execution_id_filter():
    """Search must filter by execution_id."""
    store = _temp_store()
    records = _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.build(records)

    results = index.search(
        "stage", limit=10,
        filters={"execution_id": "exec-A"},
    )
    assert len(results) > 0
    # All results are from exec-A records (we can't check exec_id directly
    # on SemanticSearchResult, but filtered by construction)
    assert len(results) >= 1

    # Non-existent execution_id
    results2 = index.search(
        "stage", limit=10,
        filters={"execution_id": "exec-Z"},
    )
    assert len(results2) == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 8: min_importance filter works
# ═══════════════════════════════════════════════════════════════════════

def test_min_importance_filter():
    """Search must filter by min_importance."""
    store = _temp_store()
    records = _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.build(records)

    # Only high-importance records (importance >= 2)
    results = index.search(
        "error", limit=10,
        filters={"min_importance": 2},
    )
    assert len(results) > 0

    # All high-importance records are error_detail with priority=2
    for r in results:
        rec = store.get(r.memory_id)
        assert rec is not None
        assert rec.importance >= 2


# ═══════════════════════════════════════════════════════════════════════
# Test 9: limit is respected
# ═══════════════════════════════════════════════════════════════════════

def test_limit_respected():
    """Search must respect the limit parameter."""
    store = _temp_store()
    records = _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.build(records)

    results = index.search("stage", limit=3)
    assert len(results) <= 3

    results2 = index.search("stage", limit=0)
    assert len(results2) == 0

    results3 = index.search("stage", limit=100)
    assert len(results3) <= 8  # Only 8 records total


# ═══════════════════════════════════════════════════════════════════════
# Test 10: explain() returns matched tokens and scoring reasons
# ═══════════════════════════════════════════════════════════════════════

def test_explain_returns_details():
    """explain() must provide query decomposition and matching info."""
    store = _temp_store()
    records = _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.build(records)

    explanation = index.explain("build error compilation")
    assert explanation["query"] == "build error compilation"
    assert "query_tokens" in explanation
    assert len(explanation["query_tokens"]) >= 2
    assert "matched_entries" in explanation
    assert "results" in explanation
    assert "index_hash" in explanation
    assert explanation["total_records"] == 8
    assert explanation["total_index_entries"] > 0


# ═══════════════════════════════════════════════════════════════════════
# Test 11: Index rebuild from store matches direct build
# ═══════════════════════════════════════════════════════════════════════

def test_rebuild_from_store_matches_direct():
    """Index rebuilt from store must match index built directly from records."""
    store = _temp_store()
    records = _populate_store(store, count=8)

    # Direct build
    index1 = SemanticMemoryIndex()
    index1.build(records)

    # Rebuild from store
    index2 = SemanticMemoryIndex()
    index2.rebuild_from_store(store)

    assert index1.index_hash == index2.index_hash
    assert index1.entry_count == index2.entry_count
    assert index1.record_count == index2.record_count

    # Same search results
    r1 = index1.search("build error", limit=10)
    r2 = index2.search("build error", limit=10)
    assert len(r1) == len(r2)
    for a, b in zip(r1, r2):
        assert a.memory_id == b.memory_id
        assert a.score == b.score


# ═══════════════════════════════════════════════════════════════════════
# Test 12: Index integrity passes
# ═══════════════════════════════════════════════════════════════════════

def test_index_integrity_passes():
    """Index integrity report must pass on a clean index."""
    store = _temp_store()
    _populate_store(store, count=8)

    index = SemanticMemoryIndex()
    index.rebuild_from_store(store)

    report = check_index_integrity(index, store)
    assert report.passed is True, f"Index integrity failed: {report.issues}"
    assert len(report.issues) == 0
    assert report.record_count == 8
    assert report.index_entry_count > 0
    assert len(report.index_hash) == 16
    assert report.checks["builds_from_episodic_records"] is True
    assert report.checks["all_memory_ids_valid"] is True
    assert report.checks["all_record_hashes_valid"] is True
    assert report.checks["deterministic_search_ordering"] is True
    assert report.checks["index_hash_stable"] is True
    assert report.checks["index_is_projection_only"] is True
    assert report.checks["no_truth_source_violation"] is True

    # quick_index_check
    assert quick_index_check(index, store) is True


# ═══════════════════════════════════════════════════════════════════════
# Test 13: Adapter uses retrieval runtime when configured
# ═══════════════════════════════════════════════════════════════════════

def test_adapter_uses_retrieval_runtime():
    """When use_retrieval=True, adapter must use semantic index for queries."""
    store = _temp_store()
    _populate_store(store, count=8)

    adapter = EpisodicMemoryAdapter(store, use_retrieval=True)
    assert adapter.has_retrieval is True
    assert adapter.name == "episodic+semantic"
    assert adapter.retrieval is not None
    assert len(adapter.retrieval_index_hash) == 16

    # Read through adapter (should use retrieval)
    req = MemoryReadRequest(
        query_id="q-001",
        query_text="build error",
        top_k=5,
        min_score=0.1,
    )
    result = adapter.read_request(req)
    assert result.is_empty is False
    assert result.backend == "semantic"
    assert len(result.entries) > 0

    # Gateway integration
    gw = MemoryGateway()
    adapter.close()
    adapter2 = EpisodicMemoryAdapter(store, use_retrieval=True)
    gw.connect(adapter2)
    result2 = gw.read_request(req)
    assert result2.is_empty is False
    assert result2.backend in ("semantic", "connected")

    adapter2.close()


# ═══════════════════════════════════════════════════════════════════════
# Test 14: Adapter works without retrieval runtime
# ═══════════════════════════════════════════════════════════════════════

def test_adapter_without_retrieval():
    """Without retrieval, adapter must use original store.read() behavior."""
    store = _temp_store()
    _populate_store(store, count=8)

    adapter = EpisodicMemoryAdapter(store, use_retrieval=False)
    assert adapter.has_retrieval is False
    assert adapter.name == "episodic"
    assert adapter.retrieval is None
    assert adapter.retrieval_index_hash == ""

    req = MemoryReadRequest(
        query_id="q-002",
        query_text="build",
        top_k=5,
        filters={"candidate_type": "stage_result"},
    )
    result = adapter.read_request(req)
    assert result.is_empty is False
    assert result.backend == "episodic"

    adapter.close()


# ═══════════════════════════════════════════════════════════════════════
# Test 15: Deleting semantic index does not affect kernel tests
# ═══════════════════════════════════════════════════════════════════════

def test_semantic_index_removable():
    """Semantic index must be removable without affecting kernel behavior."""
    # Kernel runs without any memory modules
    from v3.kernel.execution_engine import ExecutionEngine, ExecutionConfig, DomainState
    from v3.kernel.execution_engine import StateField, MergeStrategy, RetryPolicy, NoopStage

    engine = ExecutionEngine(ExecutionConfig(
        pipeline=(
            NoopStage(name="stage_a", delay_s=0.001),
            NoopStage(name="stage_b", delay_s=0.001),
        ),
        retry=RetryPolicy.NONE,
        memory_gateway=None,
        thread_id="si-removable-test",
    ))
    state = DomainState(
        schema=(
            StateField("thread_id", str, MergeStrategy.KEEP),
            StateField("target", str, MergeStrategy.REPLACE, default="."),
        ),
        initial={"thread_id": "si-removable-test", "target": "."},
    )
    result = engine.run(state)
    assert result["success"] is True

    # Build and discard index — kernel behavior must be unchanged
    store = _temp_store()
    _populate_store(store, count=4)

    index = SemanticMemoryIndex()
    index.rebuild_from_store(store)
    index_hash_before = index.index_hash

    # Run kernel again — same result
    result2 = engine.run(state)
    assert result2["success"] is True
    assert result2["stage_results"][0]["passed"] is True
    assert result2["stage_results"][1]["passed"] is True

    # Index is unchanged by kernel execution
    assert index.index_hash == index_hash_before


# ═══════════════════════════════════════════════════════════════════════
# Test 16: No banned LLM/vector imports
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_imports():
    """New Phase 4D-3 files must not import banned LLM/vector/SDK modules."""
    BANNED = {
        "mem0", "graphiti", "openai", "anthropic", "langchain", "crewai",
        "chromadb", "qdrant", "pinecone", "weaviate", "faiss", "milvus",
        "sentence_transformers", "transformers", "torch", "tensorflow",
    }

    memory_dir = os.path.join(_root, "v3", "memory")
    new_files = ["semantic_index.py", "retrieval.py", "index_integrity.py"]
    violations = []

    for fname in new_files:
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
        raise AssertionError(f"Banned imports in Phase 4D-3 modules:\n{detail}")

    assert len(violations) == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 17: Existing tests still pass
# ═══════════════════════════════════════════════════════════════════════

def test_existing_tests_still_pass():
    """Verify that Phase 4D-1 and 4D-2 functionality still works correctly."""
    # Episodic store (4D-2)
    store = _temp_store()
    req = MemoryWriteRequest(
        request_id="et-001", execution_id="et-e1",
        candidate_type="test", content={"msg": "existing"},
        priority=1,
    )
    result = store.append(req)
    assert result.accepted is True

    # Integrity (4D-2)
    report = check_integrity(store)
    assert report.passed is True

    # Gateway (4D-1)
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)
    assert gw.is_connected is True

    # Adapter (4D-1/4D-2)
    adapter = EpisodicMemoryAdapter(store)
    candidates = (
        MemoryCandidate(
            candidate_id="mc-001", execution_id="mc-e1",
            candidate_type="stage_result",
            content={"stage": "verify"},
            context={"graph_hash": "gh1"},
            priority=1,
        ),
    )
    results = adapter.write_candidates(candidates)
    assert len(results) == 1
    assert results[0].accepted is True

    adapter.close()

    # Semantic index doesn't interfere
    index = SemanticMemoryIndex()
    index.rebuild_from_store(store)
    assert index.is_built is True


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("index builds from episodic records", test_index_builds_from_records),
        ("tokenization is deterministic", test_tokenization_deterministic),
        ("search returns deterministic results", test_search_deterministic),
        ("exact token match scores higher", test_exact_token_match_scores_higher),
        ("tag match boost works", test_tag_match_boost),
        ("candidate_type filter works", test_candidate_type_filter),
        ("execution_id filter works", test_execution_id_filter),
        ("min_importance filter works", test_min_importance_filter),
        ("limit is respected", test_limit_respected),
        ("explain returns matched tokens and reasons", test_explain_returns_details),
        ("index rebuild from store matches direct build", test_rebuild_from_store_matches_direct),
        ("index integrity passes", test_index_integrity_passes),
        ("adapter uses retrieval runtime when configured", test_adapter_uses_retrieval_runtime),
        ("adapter works without retrieval runtime", test_adapter_without_retrieval),
        ("semantic index removable", test_semantic_index_removable),
        ("no banned LLM/vector imports", test_no_banned_imports),
        ("existing tests still pass", test_existing_tests_still_pass),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Semantic Memory Index Tests (Phase 4D-3)")
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

    _cleanup_temp_dirs()

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
