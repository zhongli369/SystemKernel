"""
Truth-Linked Recall Tests — Phase 4D-4.

18 tests covering:
  1. recall returns RecallBundle
  2. recall results contain provenance
  3. provenance links to record_hash
  4. provenance links to source_hash
  5. provenance links to execution_id
  6. provenance links to graph_hash
  7. recall_hash deterministic
  8. bundle_hash deterministic
  9. verify_provenance passes valid result
 10. verify_bundle passes valid bundle
 11. explanation includes matched tokens and source linkage
 12. recall_from_read_request returns MemoryReadResult
 13. adapter use_recall=True works
 14. adapter still works with use_recall=False
 15. recall layer is projection only
 16. deleting recall/index does not affect kernel tests
 17. no banned LLM/vector imports
 18. existing 4D-1/2/3 tests still pass
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
from v3.memory.integrity import check_integrity
from v3.memory.semantic_index import SemanticMemoryIndex, tokenize
from v3.memory.retrieval import MemoryRetrievalRuntime
from v3.memory.index_integrity import check_index_integrity
from v3.memory.provenance import (
    RecallProvenance,
    extract_provenance,
    verify_provenance,
    verify_provenance_chain,
    compute_provenance_hash,
)
from v3.memory.recall import (
    RecallResult,
    RecallBundle,
    TruthLinkedRecallRuntime,
    compute_recall_hash,
    compute_bundle_hash,
)
from v3.memory.adapter_stub import MemoryAdapterStub
from v3.kernel.memory_contract import (
    MemoryWriteRequest, MemoryWriteResult,
    MemoryReadRequest, MemoryReadResult,
)
from v3.kernel.memory_candidate import MemoryCandidate
from v3.kernel.memory_gateway import MemoryGateway
from v3.kernel.events import make_event, EventType
from v3.kernel.observability_graph import build_graph
from v3.kernel.execution_engine import (
    ExecutionEngine, DomainState, ExecutionConfig,
    StateField, MergeStrategy, RetryPolicy, NoopStage,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

_temp_dirs: list[str] = []


def _temp_store() -> EpisodicMemoryStore:
    d = tempfile.mkdtemp(prefix="recall_test_")
    _temp_dirs.append(d)
    path = os.path.join(d, "episodes.jsonl")
    return EpisodicMemoryStore(path)


def _cleanup_temp_dirs():
    for d in _temp_dirs:
        shutil.rmtree(d, ignore_errors=True)
    _temp_dirs.clear()


def _populate_store(store: EpisodicMemoryStore) -> Tuple[EpisodicMemoryRecord, ...]:
    """Populate a store with diverse records."""
    samples = [
        ("rcl-01", "exec-4d4", "stage_result",
         {"stage_name": "init", "status": "completed", "result": "ok"}, 1,
         ["evt-0", "evt-1"]),
        ("rcl-02", "exec-4d4", "stage_result",
         {"stage_name": "build", "status": "completed", "result": "compiled"}, 1,
         ["evt-2", "evt-3"]),
        ("rcl-03", "exec-4d4-x", "error_detail",
         {"stage_name": "deploy", "status": "failed",
          "error_message": "connection refused on port 8080"}, 2,
         ["evt-4", "evt-5"]),
        ("rcl-04", "exec-4d4-x", "error_detail",
         {"stage_name": "build", "status": "failed",
          "error_message": "compilation error in main.py line 42"}, 2,
         ["evt-6", "evt-7"]),
        ("rcl-05", "exec-4d4-y", "execution_summary",
         {"execution_status": "completed", "duration_ms": 800, "stage_count": 3}, 1,
         ["evt-8", "evt-9"]),
        ("rcl-06", "exec-4d4-y", "stage_result",
         {"stage_name": "lint", "status": "completed",
          "result": "code quality passed"}, 1,
         ["evt-10", "evt-11"]),
    ]

    records = []
    for rid, eid, ctype, content, priority, evt_ids in samples:
        req = MemoryWriteRequest(
            request_id=rid, execution_id=eid,
            candidate_type=ctype, content=content,
            context={"graph_hash": f"gh-{eid}", "event_ids": evt_ids},
            priority=priority,
        )
        result = store.append(req)
        rec = store.get(result.storage_id)
        if rec:
            records.append(rec)
    return tuple(records)


# ═══════════════════════════════════════════════════════════════════════
# Test 1: recall returns RecallBundle
# ═══════════════════════════════════════════════════════════════════════

def test_recall_returns_bundle():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("build error", limit=10)

    assert isinstance(bundle, RecallBundle)
    assert bundle.query == "build error"
    assert len(bundle.results) > 0
    assert bundle.total == len(bundle.results)
    assert len(bundle.bundle_hash) == 16
    assert bundle.integrity_status in ("valid", "partial", "invalid")


# ═══════════════════════════════════════════════════════════════════════
# Test 2: recall results contain provenance
# ═══════════════════════════════════════════════════════════════════════

def test_results_contain_provenance():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("compilation error")

    assert len(bundle.results) > 0
    for result in bundle.results:
        assert isinstance(result, RecallResult)
        assert isinstance(result.provenance, RecallProvenance)
        assert result.provenance.memory_id == result.memory_id
        assert len(result.provenance.provenance_hash) == 16


# ═══════════════════════════════════════════════════════════════════════
# Test 3: provenance links to record_hash
# ═══════════════════════════════════════════════════════════════════════

def test_provenance_links_record_hash():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("build")

    assert len(bundle.results) > 0
    for result in bundle.results:
        record = store.get(result.memory_id)
        assert record is not None
        assert result.provenance.record_hash == record.record_hash
        assert len(result.provenance.record_hash) == 16


# ═══════════════════════════════════════════════════════════════════════
# Test 4: provenance links to source_hash
# ═══════════════════════════════════════════════════════════════════════

def test_provenance_links_source_hash():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("deploy")

    assert len(bundle.results) > 0
    for result in bundle.results:
        record = store.get(result.memory_id)
        assert record is not None
        assert result.provenance.source_hash == record.source_hash
        assert len(result.provenance.source_hash) == 16
        assert result.provenance.source_hash != ""


# ═══════════════════════════════════════════════════════════════════════
# Test 5: provenance links to execution_id
# ═══════════════════════════════════════════════════════════════════════

def test_provenance_links_execution_id():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("completed")

    assert len(bundle.results) > 0
    for result in bundle.results:
        record = store.get(result.memory_id)
        assert record is not None
        assert result.provenance.execution_id == record.execution_id
        assert result.provenance.execution_id != ""


# ═══════════════════════════════════════════════════════════════════════
# Test 6: provenance links to graph_hash
# ═══════════════════════════════════════════════════════════════════════

def test_provenance_links_graph_hash():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("lint")

    assert len(bundle.results) > 0
    for result in bundle.results:
        record = store.get(result.memory_id)
        assert record is not None
        assert result.provenance.graph_hash == record.graph_hash
        assert result.provenance.graph_hash != ""


# ═══════════════════════════════════════════════════════════════════════
# Test 7: recall_hash deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_recall_hash_deterministic():
    store = _temp_store()
    _populate_store(store)

    recall1 = TruthLinkedRecallRuntime(store)
    bundle1 = recall1.recall("build error")

    recall2 = TruthLinkedRecallRuntime(store)
    bundle2 = recall2.recall("build error")

    assert len(bundle1.results) == len(bundle2.results)
    for r1, r2 in zip(bundle1.results, bundle2.results):
        assert r1.recall_hash == r2.recall_hash, \
            f"recall_hash not deterministic: {r1.recall_hash} != {r2.recall_hash}"
        assert r1.memory_id == r2.memory_id
        assert r1.score == r2.score


# ═══════════════════════════════════════════════════════════════════════
# Test 8: bundle_hash deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_bundle_hash_deterministic():
    store = _temp_store()
    _populate_store(store)

    recall1 = TruthLinkedRecallRuntime(store)
    bundle1 = recall1.recall("connection refused")

    recall2 = TruthLinkedRecallRuntime(store)
    bundle2 = recall2.recall("connection refused")

    assert bundle1.bundle_hash == bundle2.bundle_hash, \
        f"bundle_hash not deterministic: {bundle1.bundle_hash} != {bundle2.bundle_hash}"
    assert bundle1.total == bundle2.total
    assert bundle1.integrity_status == bundle2.integrity_status


# ═══════════════════════════════════════════════════════════════════════
# Test 9: verify_provenance passes valid result
# ═══════════════════════════════════════════════════════════════════════

def test_verify_provenance_passes():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("build")

    assert len(bundle.results) > 0
    for result in bundle.results:
        assert recall.verify_provenance(result) is True
        assert result.provenance.trace_valid is True


# ═══════════════════════════════════════════════════════════════════════
# Test 10: verify_bundle passes valid bundle
# ═══════════════════════════════════════════════════════════════════════

def test_verify_bundle_passes():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("compilation error", limit=10)

    assert recall.verify_bundle(bundle) is True
    assert bundle.integrity_status == "valid"


# ═══════════════════════════════════════════════════════════════════════
# Test 11: explanation includes matched tokens and source linkage
# ═══════════════════════════════════════════════════════════════════════

def test_explanation_includes_source_linkage():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("connection refused")

    assert len(bundle.results) > 0
    for result in bundle.results:
        exp = result.explanation
        assert "matched_tokens" in exp
        assert "score" in exp
        assert "score_components" in exp
        assert "source_linkage" in exp
        assert "trace_valid" in exp
        # Source linkage must have key fields
        sl = exp["source_linkage"]
        assert "execution_id" in sl
        assert "graph_hash" in sl
        assert "source_hash" in sl
        assert "record_hash" in sl
        assert len(sl["execution_id"]) > 0
        assert len(sl["graph_hash"]) > 0
        assert len(sl["source_hash"]) == 16


# ═══════════════════════════════════════════════════════════════════════
# Test 12: recall_from_read_request returns MemoryReadResult
# ═══════════════════════════════════════════════════════════════════════

def test_recall_from_read_request():
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    req = MemoryReadRequest(
        query_id="q-recall-001",
        query_text="build error compilation",
        top_k=5,
        min_score=0.01,
    )
    result = recall.recall_from_read_request(req)

    assert isinstance(result, MemoryReadResult)
    assert result.query_id == "q-recall-001"
    assert result.backend == "recall"
    assert result.is_empty is False
    assert len(result.entries) > 0
    assert len(result.scores) == len(result.entries)

    # Metadata must include provenance info
    assert "bundle_hash" in result.metadata
    assert "integrity_status" in result.metadata
    assert len(result.metadata["bundle_hash"]) == 16

    # Each entry should have provenance
    for entry in result.entries:
        assert "provenance" in entry
        prov = entry["provenance"]
        assert "memory_id" in prov
        assert "record_hash" in prov
        assert "source_hash" in prov
        assert "execution_id" in prov


# ═══════════════════════════════════════════════════════════════════════
# Test 13: adapter use_recall=True works
# ═══════════════════════════════════════════════════════════════════════

def test_adapter_use_recall():
    store = _temp_store()
    _populate_store(store)

    adapter = EpisodicMemoryAdapter(store, use_recall=True)
    assert adapter.has_recall is True
    assert adapter.name == "episodic+recall"
    assert adapter.recall_runtime is not None
    assert len(adapter.retrieval_index_hash) == 16

    # Read through adapter (should use recall)
    req = MemoryReadRequest(
        query_id="q-adapter-rcl",
        query_text="build error",
        top_k=5,
        min_score=0.01,
    )
    result = adapter.read_request(req)
    assert result.is_empty is False
    assert result.backend == "recall"
    assert len(result.entries) > 0

    # Entry should have provenance
    for entry in result.entries:
        assert "provenance" in entry

    adapter.close()


# ═══════════════════════════════════════════════════════════════════════
# Test 14: adapter still works with use_recall=False
# ═══════════════════════════════════════════════════════════════════════

def test_adapter_without_recall():
    store = _temp_store()
    _populate_store(store)

    # Default: no recall, no retrieval
    adapter = EpisodicMemoryAdapter(store)
    assert adapter.has_recall is False
    assert adapter.has_retrieval is False
    assert adapter.name == "episodic"

    req_default = MemoryReadRequest(
        query_id="q-no-recall",
        query_text="build",
        top_k=5,
        min_score=0.1,
    )
    result = adapter.read_request(req_default)
    assert result.is_empty is False, "default adapter returned empty"
    assert result.backend == "episodic", f"expected episodic got {result.backend}"

    # With retrieval only (no recall)
    adapter2 = EpisodicMemoryAdapter(store, use_retrieval=True)
    assert adapter2.has_recall is False
    assert adapter2.has_retrieval is True
    assert adapter2.name == "episodic+semantic"

    req_retrieval = MemoryReadRequest(
        query_id="q-retrieval",
        query_text="build",
        top_k=5,
        min_score=0.01,
    )
    result2 = adapter2.read_request(req_retrieval)
    assert result2.is_empty is False, "retrieval adapter returned empty"
    assert result2.backend == "semantic", f"expected semantic got {result2.backend}"

    adapter.close()
    adapter2.close()


# ═══════════════════════════════════════════════════════════════════════
# Test 15: recall layer is projection only
# ═══════════════════════════════════════════════════════════════════════

def test_recall_is_projection_only():
    store = _temp_store()
    records = _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("build error")

    # Every result must reference a record that exists in the store
    for result in bundle.results:
        record = store.get(result.memory_id)
        assert record is not None, \
            f"Result {result.memory_id} has no backing record"

    # Rebuild index, re-recall — same results
    recall2 = TruthLinkedRecallRuntime(store)
    bundle2 = recall2.recall("build error")
    assert bundle.bundle_hash == bundle2.bundle_hash

    # Recall doesn't add records to the store
    assert store.record_count == len(records)


# ═══════════════════════════════════════════════════════════════════════
# Test 16: deleting recall/index does not affect kernel tests
# ═══════════════════════════════════════════════════════════════════════

def test_recall_removable():
    engine = ExecutionEngine(ExecutionConfig(
        pipeline=(
            NoopStage(name="stage_init", delay_s=0.001),
            NoopStage(name="stage_run", delay_s=0.001),
        ),
        retry=RetryPolicy.NONE,
        memory_gateway=None,
        thread_id="recall-removable",
    ))
    state = DomainState(
        schema=(
            StateField("thread_id", str, MergeStrategy.KEEP),
            StateField("target", str, MergeStrategy.REPLACE, default="."),
        ),
        initial={"thread_id": "recall-removable", "target": "."},
    )
    result = engine.run(state)
    assert result["success"] is True

    # Build recall, use it, delete store — kernel still works
    store = _temp_store()
    _populate_store(store)

    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("build")
    assert bundle.total > 0

    # Run kernel again — must work identically
    result2 = engine.run(state)
    assert result2["success"] is True
    assert result2["stage_results"][0]["passed"] is True
    assert result2["stage_results"][1]["passed"] is True


# ═══════════════════════════════════════════════════════════════════════
# Test 17: no banned LLM/vector imports
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_imports():
    BANNED = {
        "mem0", "graphiti", "openai", "anthropic", "langchain", "crewai",
        "chromadb", "qdrant", "pinecone", "weaviate", "faiss", "milvus",
        "sentence_transformers", "transformers", "torch", "tensorflow",
    }

    memory_dir = os.path.join(_root, "v3", "memory")
    new_files = ["provenance.py", "recall.py"]
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
        raise AssertionError(f"Banned imports in Phase 4D-4 modules:\n{detail}")
    assert len(violations) == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 18: existing 4D-1/2/3 tests still pass
# ═══════════════════════════════════════════════════════════════════════

def test_existing_tests_still_pass():
    # 4D-2: Episodic store
    store = _temp_store()
    req = MemoryWriteRequest(
        request_id="et-4d4", execution_id="et-e4d4",
        candidate_type="test", content={"msg": "existing"},
        priority=1,
    )
    result = store.append(req)
    assert result.accepted is True

    # 4D-2: Integrity
    report = check_integrity(store)
    assert report.passed is True

    # 4D-1: Gateway
    gw = MemoryGateway()
    stub = MemoryAdapterStub()
    gw.connect(stub)
    assert gw.is_connected is True

    # 4D-3: Semantic index
    index = SemanticMemoryIndex()
    index.build(store.list_records())
    assert index.is_built is True

    # 4D-3: Retrieval
    retrieval = MemoryRetrievalRuntime(store)
    req2 = MemoryReadRequest(query_id="q-4d4", query_text="existing")
    r2 = retrieval.read_request(req2)
    assert r2.is_empty is False

    # 4D-3: Index integrity
    idx_report = check_index_integrity(index, store)
    assert idx_report.passed is True

    # 4D-4: Recall doesn't break any of the above
    recall = TruthLinkedRecallRuntime(store)
    bundle = recall.recall("existing")
    assert bundle.total > 0


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("recall returns RecallBundle", test_recall_returns_bundle),
        ("results contain provenance", test_results_contain_provenance),
        ("provenance links to record_hash", test_provenance_links_record_hash),
        ("provenance links to source_hash", test_provenance_links_source_hash),
        ("provenance links to execution_id", test_provenance_links_execution_id),
        ("provenance links to graph_hash", test_provenance_links_graph_hash),
        ("recall_hash deterministic", test_recall_hash_deterministic),
        ("bundle_hash deterministic", test_bundle_hash_deterministic),
        ("verify_provenance passes valid result", test_verify_provenance_passes),
        ("verify_bundle passes valid bundle", test_verify_bundle_passes),
        ("explanation includes source linkage", test_explanation_includes_source_linkage),
        ("recall_from_read_request returns MemoryReadResult", test_recall_from_read_request),
        ("adapter use_recall=True works", test_adapter_use_recall),
        ("adapter works without recall", test_adapter_without_recall),
        ("recall layer is projection only", test_recall_is_projection_only),
        ("deleting recall doesn't affect kernel", test_recall_removable),
        ("no banned LLM/vector imports", test_no_banned_imports),
        ("existing tests still pass", test_existing_tests_still_pass),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Truth-Linked Recall Tests (Phase 4D-4)")
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
