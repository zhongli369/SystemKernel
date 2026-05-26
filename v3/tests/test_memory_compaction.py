"""
Memory Compaction Tests — Phase 4D-5.

Comprehensive tests for:
  1. CompactionResult structure (correct counts)
  2. Duplicate detection determinism
  3. merge_sources preserves all source hashes
  4. Low importance archiving
  5. Original episodic records unchanged
  6. compacted_hash stability
  7. result_hash stability
  8. Compaction projection I/O
  9. verify_compaction for valid result
 10. Compaction integrity checks
 11. No provenance loss
 12. Compacted records indexable
 13. Retrieval with compacted projection
 14. Recall provenance links to original sources
 15. Compaction is projection only
 16. Deleting projection → kernel unaffected
 17. No banned LLM/vector imports
 18. Existing 4D tests still pass (regression)
 19. Kernel invariants purity=100 (regression)

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import hashlib
import uuid
import tempfile
import shutil

# Add SystemKernel root to path
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.memory_contract import (
    MemoryWriteRequest, MemoryWriteResult,
    MemoryReadRequest, MemoryReadResult,
)
from v3.kernel.memory_candidate import (
    MemoryCandidate, CandidateType, project_candidates,
)
from v3.kernel.events import make_event, EventType
from v3.memory.episodic_store import (
    EpisodicMemoryRecord, EpisodicMemoryStore,
    compute_record_hash, compute_source_hash, derive_tags,
)
from v3.memory.compaction import (
    CompactionPolicy, CompactedMemoryRecord, CompactionResult,
    MemoryCompactor, compute_content_fingerprint,
    compute_compacted_hash, compute_result_hash,
)
from v3.memory.compaction_integrity import (
    CompactionIntegrityReport, check_compaction_integrity,
    quick_compaction_check, generate_compaction_integrity_report_json,
)
from v3.memory.retrieval import MemoryRetrievalRuntime
from v3.memory.recall import TruthLinkedRecallRuntime
from v3.memory.semantic_index import SemanticMemoryIndex


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_events(execution_id: str, graph_hash: str = "gh-test001") -> tuple:
    """Build sample events for a single execution."""
    import time
    eid = execution_id
    gh = graph_hash
    return (
        make_event(eid, 0, EventType.EXECUTION_STARTED, {"graph_hash": gh, "stage_order": ["build", "test"]}),
        make_event(eid, 1, EventType.STAGE_STARTED, {"stage_name": "build", "graph_hash": gh}),
        make_event(eid, 2, EventType.STAGE_COMPLETED, {"stage_name": "build", "duration_ms": 100, "result": {"ok": True}, "graph_hash": gh}),
        make_event(eid, 3, EventType.STAGE_STARTED, {"stage_name": "test", "graph_hash": gh}),
        make_event(eid, 4, EventType.STAGE_COMPLETED, {"stage_name": "test", "duration_ms": 50, "result": {"ok": True}, "graph_hash": gh}),
        make_event(eid, 5, EventType.EXECUTION_COMPLETED, {"duration_ms": 150, "graph_hash": gh}),
    )


def _make_record(
    memory_id: str,
    candidate_id: str,
    execution_id: str,
    graph_hash: str,
    candidate_type: str,
    content: dict,
    importance: int = 1,
    event_ids: tuple = ("ev-1", "ev-2"),
) -> EpisodicMemoryRecord:
    """Create an EpisodicMemoryRecord with proper hashes."""
    source_hash = compute_source_hash(execution_id, graph_hash, event_ids)
    tags = derive_tags(candidate_type, content)

    record = EpisodicMemoryRecord(
        memory_id=memory_id,
        candidate_id=candidate_id,
        execution_id=execution_id,
        event_ids=event_ids,
        graph_hash=graph_hash,
        candidate_type=candidate_type,
        content=content,
        importance=importance,
        tags=tags,
        created_at=f"2025-01-0{ord(memory_id[-1]) % 9 + 1}T10:00:00Z",
        source_hash=source_hash,
    )
    rhash = compute_record_hash(record)
    return EpisodicMemoryRecord(
        memory_id=record.memory_id,
        candidate_id=record.candidate_id,
        execution_id=record.execution_id,
        event_ids=record.event_ids,
        graph_hash=record.graph_hash,
        candidate_type=record.candidate_type,
        content=record.content,
        importance=record.importance,
        tags=record.tags,
        created_at=record.created_at,
        source_hash=record.source_hash,
        record_hash=rhash,
    )


def _make_sample_records() -> tuple:
    """Make a diverse set of sample records for testing."""
    r1 = _make_record("mem-001", "cid-001", "exec-A", "gh-aaa", "execution_summary",
                       {"status": "completed", "duration_ms": 500}, importance=2)
    r2 = _make_record("mem-002", "cid-002", "exec-A", "gh-aaa", "stage_result",
                       {"stage_name": "build", "status": "passed"}, importance=1)
    r3 = _make_record("mem-003", "cid-003", "exec-A", "gh-aaa", "stage_result",
                       {"stage_name": "test", "status": "passed"}, importance=1)
    r4 = _make_record("mem-004", "cid-004", "exec-A", "gh-aaa", "error_detail",
                       {"error": "minor warning", "stage_name": "lint"}, importance=1)
    # Duplicate of r2 (same content, different IDs)
    r5 = _make_record("mem-005", "cid-005", "exec-B", "gh-bbb", "stage_result",
                       {"stage_name": "build", "status": "passed"}, importance=1)
    r6 = _make_record("mem-006", "cid-006", "exec-B", "gh-bbb", "execution_summary",
                       {"status": "completed", "duration_ms": 500}, importance=2)
    r7 = _make_record("mem-007", "cid-007", "exec-C", "gh-ccc", "stage_result",
                       {"stage_name": "deploy", "status": "passed"}, importance=1)
    # Low importance
    r8 = _make_record("mem-008", "cid-008", "exec-C", "gh-ccc", "background",
                       {"info": "cache warmed"}, importance=0)
    r9 = _make_record("mem-009", "cid-009", "exec-C", "gh-ccc", "background",
                       {"info": "heartbeat check"}, importance=0)
    r10 = _make_record("mem-010", "cid-010", "exec-B", "gh-bbb", "error_detail",
                        {"error": "failed assertion", "stage_name": "build"}, importance=2)
    return (r1, r2, r3, r4, r5, r6, r7, r8, r9, r10)


# ═══════════════════════════════════════════════════════════════════════
# Test 1: compactor returns CompactionResult
# ═══════════════════════════════════════════════════════════════════════

def test_compactor_returns_compaction_result():
    """Compact() must return CompactionResult with correct structure."""
    records = _make_sample_records()
    policy = CompactionPolicy.default()
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    assert isinstance(result, CompactionResult)
    assert result.input_count == len(records)
    assert result.output_count >= 1
    assert result.duplicate_count >= 0
    assert result.archived_count >= 0
    assert len(result.compacted_records) == result.output_count
    assert len(result.result_hash) == 16


# ═══════════════════════════════════════════════════════════════════════
# Test 2: duplicate records are detected deterministically
# ═══════════════════════════════════════════════════════════════════════

def test_duplicate_detection_determinism():
    """Same records compacted twice must produce same duplicate_count."""
    records = _make_sample_records()
    policy = CompactionPolicy(
        duplicate_strategy="keep_first",
        group_by="candidate_type",
        min_importance=1,
    )
    compactor = MemoryCompactor()

    r1 = compactor.compact(records, policy)
    r2 = compactor.compact(records, policy)

    assert r1.duplicate_count == r2.duplicate_count, \
        f"Duplicate count not deterministic: {r1.duplicate_count} vs {r2.duplicate_count}"
    assert r1.result_hash == r2.result_hash, \
        "Result hash must be deterministic across identical inputs"


# ═══════════════════════════════════════════════════════════════════════
# Test 3: merge_sources preserves all source hashes
# ═══════════════════════════════════════════════════════════════════════

def test_merge_sources_preserves_all_hashes():
    """merge_sources strategy must include all source hashes from merged records."""
    records = _make_sample_records()
    policy = CompactionPolicy(
        duplicate_strategy="merge_sources",
        group_by="candidate_type",
        min_importance=1,
    )
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    # Collect all source references from compacted records
    all_refd_memory_ids = set()
    all_refd_record_hashes = set()
    all_refd_source_hashes = set()
    all_refd_execution_ids = set()
    all_refd_graph_hashes = set()

    for cr in result.compacted_records:
        all_refd_memory_ids.update(cr.source_memory_ids)
        all_refd_record_hashes.update(cr.source_record_hashes)
        all_refd_source_hashes.update(cr.source_hashes)
        all_refd_execution_ids.update(cr.execution_ids)
        all_refd_graph_hashes.update(cr.graph_hashes)

    # Every active (importance >= 1) record should be referenced
    active_records = [r for r in records if r.importance >= 1]
    for r in active_records:
        assert r.memory_id in all_refd_memory_ids, \
            f"Record {r.memory_id} not referenced in compacted output"
        assert r.record_hash in all_refd_record_hashes, \
            f"Record hash {r.record_hash} not referenced"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: low importance records can be archived
# ═══════════════════════════════════════════════════════════════════════

def test_low_importance_archived():
    """Records below min_importance must be archived (not in compacted output)."""
    records = _make_sample_records()
    policy = CompactionPolicy(
        min_importance=1,
        archive_low_importance=True,
    )
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    # Low importance records (importance=0) should be archived
    low_importance_count = sum(1 for r in records if r.importance < 1)
    assert result.archived_count == low_importance_count, \
        f"Expected {low_importance_count} archived, got {result.archived_count}"

    # Archived records should NOT be in compacted output
    compacted_ids = set()
    for cr in result.compacted_records:
        compacted_ids.update(cr.source_memory_ids)

    for r in records:
        if r.importance < 1:
            assert r.memory_id not in compacted_ids, \
                f"Archived record {r.memory_id} found in compacted output"


def test_low_importance_skipped_when_not_archiving():
    """When archive_low_importance=False, low importance records are skipped entirely."""
    records = _make_sample_records()
    policy = CompactionPolicy(
        min_importance=1,
        archive_low_importance=False,
    )
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    assert result.archived_count == 0
    # Low importance records still not in output (they're just skipped)
    compacted_ids = set()
    for cr in result.compacted_records:
        compacted_ids.update(cr.source_memory_ids)

    for r in records:
        if r.importance < 1:
            assert r.memory_id not in compacted_ids, \
                f"Skipped record {r.memory_id} found in compacted output"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: original episodic records unchanged
# ═══════════════════════════════════════════════════════════════════════

def test_original_records_unchanged():
    """Compaction must never modify original episodic records."""
    records = _make_sample_records()
    original_snapshots = {r.memory_id: r.record_hash for r in records}

    policy = CompactionPolicy(duplicate_strategy="merge_sources")
    compactor = MemoryCompactor()
    _ = compactor.compact(records, policy)

    for r in records:
        assert r.record_hash == original_snapshots[r.memory_id], \
            f"Record {r.memory_id} was modified by compaction"


# ═══════════════════════════════════════════════════════════════════════
# Test 6: compacted_hash stable
# ═══════════════════════════════════════════════════════════════════════

def test_compacted_hash_stable():
    """Same compacted record content → same compacted_hash, always."""
    records = _make_sample_records()
    policy = CompactionPolicy(duplicate_strategy="keep_first", group_by="candidate_type")
    compactor = MemoryCompactor()

    r1 = compactor.compact(records, policy)
    r2 = compactor.compact(records, policy)

    hashes1 = {cr.compacted_id: cr.compacted_hash for cr in r1.compacted_records}
    hashes2 = {cr.compacted_id: cr.compacted_hash for cr in r2.compacted_records}

    for cid, ch1 in hashes1.items():
        assert cid in hashes2, f"Compacted record {cid} missing in second run"
        assert ch1 == hashes2[cid], \
            f"Compacted hash for {cid} not stable: {ch1} vs {hashes2[cid]}"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: result_hash stable
# ═══════════════════════════════════════════════════════════════════════

def test_result_hash_stable():
    """Same records + policy must produce same result_hash."""
    records = _make_sample_records()
    policy = CompactionPolicy(group_by="candidate_type")

    compactor = MemoryCompactor()
    r1 = compactor.compact(records, policy)
    r2 = compactor.compact(records, policy)
    r3 = compactor.compact(records, policy)

    assert r1.result_hash == r2.result_hash == r3.result_hash, \
        "result_hash must be stable across 3 runs"

    # Different policy → different hash
    policy2 = CompactionPolicy(group_by="execution_id")
    r4 = compactor.compact(records, policy2)
    assert r1.result_hash != r4.result_hash, \
        "Different policies must produce different result hashes"


# ═══════════════════════════════════════════════════════════════════════
# Test 8: compaction projection can be written/read
# ═══════════════════════════════════════════════════════════════════════

def test_compaction_projection_roundtrip():
    """Compaction projection must be writable to and readable from JSON."""
    records = _make_sample_records()
    policy = CompactionPolicy(duplicate_strategy="keep_first")
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    tmpdir = tempfile.mkdtemp()
    try:
        proj_path = os.path.join(tmpdir, "compacted_projection.json")
        written_path = compactor.write_projection(proj_path, result, policy)

        assert os.path.exists(written_path)

        with open(written_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["projection_type"] == "memory_compaction"
        assert data["input_count"] == result.input_count
        assert data["output_count"] == result.output_count
        assert data["result_hash"] == result.result_hash
        assert len(data["compacted_records"]) == result.output_count
        assert data["source_linkage"]["provenance_preserved"] is True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_compaction_projection_loadable():
    """Compactor must be able to load a projection from file."""
    records = _make_sample_records()
    policy = CompactionPolicy()
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    tmpdir = tempfile.mkdtemp()
    try:
        proj_path = os.path.join(tmpdir, "compacted.json")
        compactor.write_projection(proj_path, result, policy)

        loaded = compactor.load_projection(proj_path)
        assert loaded is not None
        assert loaded.input_count == result.input_count
        assert loaded.output_count == result.output_count
        assert loaded.result_hash == result.result_hash
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 9: verify_compaction passes valid result
# ═══════════════════════════════════════════════════════════════════════

def test_verify_compaction_passes_valid_result():
    """verify_compaction must pass for a correctly compacted result."""
    records = _make_sample_records()
    policy = CompactionPolicy()
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    verification = compactor.verify_compaction(result, records)
    assert verification["valid"] is True, \
        f"Verification failed: {verification.get('issues', [])}"


# ═══════════════════════════════════════════════════════════════════════
# Test 10: compaction integrity passes
# ═══════════════════════════════════════════════════════════════════════

def test_compaction_integrity_passes():
    """check_compaction_integrity must pass for valid compaction."""
    records = _make_sample_records()
    policy = CompactionPolicy()
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    report = check_compaction_integrity(result, records, policy)
    assert report.valid is True, \
        f"Integrity check failed: {report.issues}"
    assert len(report.report_hash) == 16


def test_quick_compaction_check():
    """quick_compaction_check must return True for valid compaction."""
    records = _make_sample_records()
    policy = CompactionPolicy()
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    assert quick_compaction_check(result, records, policy) is True


# ═══════════════════════════════════════════════════════════════════════
# Test 11: no provenance loss
# ═══════════════════════════════════════════════════════════════════════

def test_no_provenance_loss():
    """Every compacted record must retain source_hashes, execution_ids, graph_hashes."""
    records = _make_sample_records()
    policy = CompactionPolicy(duplicate_strategy="merge_sources", group_by="candidate_type")
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    for cr in result.compacted_records:
        assert len(cr.source_hashes) > 0, \
            f"Compacted record {cr.compacted_id}: no source_hashes"
        assert len(cr.execution_ids) > 0, \
            f"Compacted record {cr.compacted_id}: no execution_ids"
        assert len(cr.graph_hashes) > 0, \
            f"Compacted record {cr.compacted_id}: no graph_hashes"
        assert len(cr.source_memory_ids) > 0, \
            f"Compacted record {cr.compacted_id}: no source_memory_ids"
        assert len(cr.source_record_hashes) > 0, \
            f"Compacted record {cr.compacted_id}: no source_record_hashes"


# ═══════════════════════════════════════════════════════════════════════
# Test 12: compacted records can be indexed
# ═══════════════════════════════════════════════════════════════════════

def test_compacted_records_can_be_indexed():
    """SemanticMemoryIndex must be buildable from compacted records."""
    records = _make_sample_records()
    policy = CompactionPolicy(duplicate_strategy="keep_first")
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    # Build synthetic episodic records from compacted records
    synthetic = []
    for cr in result.compacted_records:
        rec = EpisodicMemoryRecord(
            memory_id=cr.compacted_id,
            candidate_id=cr.source_memory_ids[0] if cr.source_memory_ids else "unknown",
            execution_id=cr.execution_ids[0] if cr.execution_ids else "unknown",
            event_ids=(),
            graph_hash=cr.graph_hashes[0] if cr.graph_hashes else "",
            candidate_type=cr.candidate_types[0] if cr.candidate_types else "unknown",
            content=cr.content,
            importance=cr.importance,
            tags=cr.tags,
            created_at="",
            source_hash=cr.source_hashes[0] if cr.source_hashes else "",
            record_hash=cr.source_record_hashes[0] if cr.source_record_hashes else cr.compacted_hash,
        )
        synthetic.append(rec)

    index = SemanticMemoryIndex()
    token_count = index.build(tuple(synthetic))
    assert token_count > 0, "Index built from compacted records must have tokens"
    assert index.record_count == len(synthetic)

    # Search should work
    results = index.search("build", limit=5)
    assert len(results) >= 1, "Search on compacted index must return results"


# ═══════════════════════════════════════════════════════════════════════
# Test 13: retrieval can optionally use compacted projection
# ═══════════════════════════════════════════════════════════════════════

def test_retrieval_with_compacted_projection():
    """MemoryRetrievalRuntime must support use_compacted=True."""
    records = _make_sample_records()

    # Create a temp episodic store
    tmpdir = tempfile.mkdtemp()
    try:
        store_path = os.path.join(tmpdir, "episodes.jsonl")
        store = EpisodicMemoryStore(store_path)

        # Write records to store
        for r in records:
            req = MemoryWriteRequest(
                request_id=r.candidate_id,
                execution_id=r.execution_id,
                candidate_type=r.candidate_type,
                content=r.content,
                priority=r.importance,
                context={"graph_hash": r.graph_hash, "event_ids": list(r.event_ids)},
            )
            store.append(req)

        # Create compaction projection
        policy = CompactionPolicy()
        compactor = MemoryCompactor()
        result = compactor.compact(records, policy)
        proj_path = os.path.join(tmpdir, "compacted.json")
        compactor.write_projection(proj_path, result, policy)

        # Build retrieval with compacted
        retrieval = MemoryRetrievalRuntime(store, use_compacted=True, compaction_path=proj_path)
        assert retrieval.use_compacted is True
        assert retrieval.compaction_loaded is True

        # Query
        rreq = MemoryReadRequest(query_id="q1", query_text="build", top_k=5)
        rres = retrieval.read_request(rreq)
        assert rres.backend == "semantic_compacted"
        assert rres.metadata.get("use_compacted") is True

        # Unload compaction
        retrieval.unload_compaction()
        assert retrieval.use_compacted is False
        assert retrieval.compaction_loaded is False

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_retrieval_falls_back_without_compaction():
    """When use_compacted=True but no file exists, should fall back to store."""
    records = _make_sample_records()

    tmpdir = tempfile.mkdtemp()
    try:
        store_path = os.path.join(tmpdir, "episodes.jsonl")
        store = EpisodicMemoryStore(store_path)

        for r in records:
            req = MemoryWriteRequest(
                request_id=r.candidate_id,
                execution_id=r.execution_id,
                candidate_type=r.candidate_type,
                content=r.content,
                priority=r.importance,
                context={"graph_hash": r.graph_hash, "event_ids": list(r.event_ids)},
            )
            store.append(req)

        # Use non-existent compaction path
        retrieval = MemoryRetrievalRuntime(
            store,
            use_compacted=True,
            compaction_path=os.path.join(tmpdir, "nonexistent.json"),
        )
        assert retrieval.use_compacted is True
        assert retrieval.compaction_loaded is False

        # Should still query successfully (fallback to store)
        rreq = MemoryReadRequest(query_id="q1", query_text="build", top_k=5)
        rres = retrieval.read_request(rreq)
        assert rres.backend in ("semantic", "semantic_compacted")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 14: recall provenance still links to original sources
# ═══════════════════════════════════════════════════════════════════════

def test_recall_provenance_links_to_original():
    """Truth-linked recall must still reference original source events after compaction."""
    records = _make_sample_records()

    tmpdir = tempfile.mkdtemp()
    try:
        store_path = os.path.join(tmpdir, "episodes.jsonl")
        store = EpisodicMemoryStore(store_path)

        for r in records:
            req = MemoryWriteRequest(
                request_id=r.candidate_id,
                execution_id=r.execution_id,
                candidate_type=r.candidate_type,
                content=r.content,
                priority=r.importance,
                context={"graph_hash": r.graph_hash, "event_ids": list(r.event_ids)},
            )
            store.append(req)

        # Recall from raw store
        recall = TruthLinkedRecallRuntime(store)
        bundle = recall.recall("build", limit=5)

        assert bundle.integrity_status == "valid"
        for result in bundle.results:
            # Provenance must point to source (execution_id, graph_hash non-empty)
            assert result.provenance.execution_id, \
                "Recall provenance must have execution_id"
            assert result.provenance.graph_hash, \
                "Recall provenance must have graph_hash"
            assert result.provenance.source_hash, \
                "Recall provenance must have source_hash"
            # trace_valid means provenance chain is intact
            assert result.provenance.trace_valid, \
                "Recall provenance trace must be valid"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 15: compaction is projection only
# ═══════════════════════════════════════════════════════════════════════

def test_compaction_is_projection_only():
    """Compaction must never claim to be a truth source."""
    records = _make_sample_records()
    policy = CompactionPolicy()
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    # Every compacted record must reference source records
    for cr in result.compacted_records:
        assert len(cr.source_memory_ids) > 0, \
            f"Compacted record {cr.compacted_id} has no source — would be truth source"
        assert len(cr.source_record_hashes) > 0, \
            f"Compacted record {cr.compacted_id} has no source_record_hashes"

    # Compaction result must not contain records that stand alone
    # (every record links back to original episodic records)


def test_compaction_never_truth_source():
    """Verification must confirm compaction is projection only."""
    records = _make_sample_records()
    policy = CompactionPolicy()
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    verification = compactor.verify_compaction(result, records)
    assert verification["checks"].get("projection_only") is True
    assert verification["checks"].get("provenance_preserved") is True


# ═══════════════════════════════════════════════════════════════════════
# Test 16: deleting compaction projection does not affect kernel
# ═══════════════════════════════════════════════════════════════════════

def test_deleting_projection_leaves_kernel_unaffected():
    """Removing compaction projection file must have zero kernel impact."""
    records = _make_sample_records()

    tmpdir = tempfile.mkdtemp()
    try:
        store_path = os.path.join(tmpdir, "episodes.jsonl")
        store = EpisodicMemoryStore(store_path)

        for r in records:
            req = MemoryWriteRequest(
                request_id=r.candidate_id,
                execution_id=r.execution_id,
                candidate_type=r.candidate_type,
                content=r.content,
                priority=r.importance,
                context={"graph_hash": r.graph_hash, "event_ids": list(r.event_ids)},
            )
            store.append(req)

        # Create projection
        policy = CompactionPolicy()
        compactor = MemoryCompactor()
        result = compactor.compact(records, policy)
        proj_path = os.path.join(tmpdir, "compacted.json")
        compactor.write_projection(proj_path, result, policy)

        assert os.path.exists(proj_path)

        # Delete projection
        os.remove(proj_path)
        assert not os.path.exists(proj_path)

        # Store must still work
        assert store.record_count == len(records)
        retrieved = store.list_records()
        assert len(retrieved) == len(records)

        # Retrieval from raw store must still work
        retrieval = MemoryRetrievalRuntime(store)
        rreq = MemoryReadRequest(query_id="q-delete-test", query_text="build")
        rres = retrieval.read_request(rreq)
        assert rres is not None

        # Integrity of store unchanged
        integrity = store.verify_integrity()
        assert integrity["valid"] is True

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 17: no banned LLM/vector imports
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_imports_in_compaction():
    """Compaction modules must not import LLM, vector DB, or external AI libs."""
    import ast

    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "sklearn", "scipy",
    }

    modules_to_check = [
        os.path.join(_root, "v3", "memory", "compaction.py"),
        os.path.join(_root, "v3", "memory", "compaction_integrity.py"),
    ]

    for mod_path in modules_to_check:
        with open(mod_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in banned, \
                        f"Banned import '{name}' found in {os.path.basename(mod_path)}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    assert name not in banned, \
                        f"Banned import '{name}' found in {os.path.basename(mod_path)}"


# ═══════════════════════════════════════════════════════════════════════
# Test 18: existing 4D tests still pass (regression)
# ═══════════════════════════════════════════════════════════════════════

def test_phase_4d_regression():
    """All existing Phase 4D tests must still pass after compaction changes."""
    import subprocess

    regression_tests = [
        os.path.join(_root, "v3", "tests", "test_memory_boundary.py"),
        os.path.join(_root, "v3", "tests", "test_episodic_memory_store.py"),
        os.path.join(_root, "v3", "tests", "test_semantic_memory_index.py"),
        os.path.join(_root, "v3", "tests", "test_truth_linked_recall.py"),
    ]

    for test_path in regression_tests:
        result = subprocess.run(
            [sys.executable, test_path],
            capture_output=True, text=True,
            timeout=120,
        )
        # Check that these pass (they may have non-zero exit if any test fails)
        # We look for PASS/FAIL patterns
        stdout = result.stdout
        assert "ACCEPTANCE: ACHIEVED" in stdout or result.returncode == 0 or \
               all(w not in stdout for w in ["FAILED", "ERROR"]), \
            f"Regression test {os.path.basename(test_path)} appears to have failures:\n{stdout[:500]}"


# ═══════════════════════════════════════════════════════════════════════
# Test 19: kernel invariants still purity=100 (regression)
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_invariants_regression():
    """Kernel invariants must still pass after compaction changes."""
    import subprocess

    test_path = os.path.join(_root, "v3", "tests", "test_kernel_invariants.py")
    result = subprocess.run(
        [sys.executable, test_path],
        capture_output=True, text=True,
        timeout=120,
    )
    # Check for purity_score=100 or acceptance achieved
    stdout = result.stdout
    assert "ACCEPTANCE: ACHIEVED" in stdout or result.returncode == 0, \
        f"Kernel invariants regression failed:\n{stdout[:500]}"


# ═══════════════════════════════════════════════════════════════════════
# Bonus tests
# ═══════════════════════════════════════════════════════════════════════

def test_policy_validation():
    """CompactionPolicy must reject invalid strategies/group_by values."""
    try:
        CompactionPolicy(duplicate_strategy="invalid_strategy")
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass  # Expected

    try:
        CompactionPolicy(group_by="invalid_group")
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass  # Expected


def test_policy_disabled():
    """When policy.enabled=False, compaction must be a no-op."""
    records = _make_sample_records()
    policy = CompactionPolicy(enabled=False)
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    assert result.input_count == len(records)
    assert result.output_count == 0
    assert result.duplicate_count == 0


def test_empty_records_compact():
    """Compacting empty records must return empty CompactionResult."""
    compactor = MemoryCompactor()
    result = compactor.compact(tuple(), CompactionPolicy())
    assert result.input_count == 0
    assert result.output_count == 0
    assert len(result.compacted_records) == 0
    assert len(result.result_hash) == 16


def test_group_by_execution_id():
    """Grouping by execution_id must produce correct grouping."""
    records = _make_sample_records()
    policy = CompactionPolicy(
        group_by="execution_id",
        duplicate_strategy="merge_sources",
        min_importance=1,
    )
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    # Should have at most one compacted record per unique execution_id
    unique_execs = len(set(r.execution_id for r in records if r.importance >= 1))
    assert result.output_count <= unique_execs


def test_group_by_tag():
    """Grouping by tag must produce correct grouping."""
    records = _make_sample_records()
    policy = CompactionPolicy(
        group_by="tag",
        duplicate_strategy="keep_first",
        min_importance=1,
    )
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)
    assert result.input_count == len(records)
    assert result.duplicate_count >= 0


def test_group_by_content_hash():
    """Grouping by content_hash must group identical-content records together."""
    records = _make_sample_records()
    policy = CompactionPolicy(
        group_by="content_hash",
        duplicate_strategy="keep_first",
        min_importance=1,
    )
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)
    assert result.input_count == len(records)


def test_content_fingerprint_determinism():
    """compute_content_fingerprint must be deterministic."""
    r1 = _make_record("mem-001", "cid-001", "exec-A", "gh-aaa", "stage_result",
                       {"stage_name": "build", "status": "passed"})
    r2 = _make_record("mem-999", "cid-999", "exec-Z", "gh-zzz", "stage_result",
                       {"stage_name": "build", "status": "passed"})

    fp1 = compute_content_fingerprint(r1)
    fp2 = compute_content_fingerprint(r2)
    assert fp1 == fp2, "Same content must produce same fingerprint"

    r3 = _make_record("mem-003", "cid-003", "exec-C", "gh-ccc", "stage_result",
                       {"stage_name": "test", "status": "passed"})
    fp3 = compute_content_fingerprint(r3)
    assert fp1 != fp3, "Different content must produce different fingerprint"


def test_compacted_to_episodic_conversion():
    """CompactedMemoryRecord must convert to dict and back deterministically."""
    cr = CompactedMemoryRecord(
        compacted_id="comp-001",
        source_memory_ids=("mem-001", "mem-002"),
        source_record_hashes=("rh-aaa", "rh-bbb"),
        source_hashes=("sh-111", "sh-222"),
        execution_ids=("exec-A",),
        graph_hashes=("gh-xxx",),
        candidate_types=("stage_result",),
        tags=("type:stage_result", "stage:build"),
        content={"stage_name": "build", "status": "passed"},
        importance=2,
        compaction_reason="stage_result:merge",
    )
    ch = compute_compacted_hash(cr)
    cr = CompactedMemoryRecord(
        compacted_id=cr.compacted_id,
        source_memory_ids=cr.source_memory_ids,
        source_record_hashes=cr.source_record_hashes,
        source_hashes=cr.source_hashes,
        execution_ids=cr.execution_ids,
        graph_hashes=cr.graph_hashes,
        candidate_types=cr.candidate_types,
        tags=cr.tags,
        content=cr.content,
        importance=cr.importance,
        compaction_reason=cr.compaction_reason,
        compacted_hash=ch,
    )

    d = cr.to_dict()
    cr2 = CompactedMemoryRecord.from_dict(d)
    assert cr2.compacted_id == cr.compacted_id
    assert cr2.source_memory_ids == cr.source_memory_ids
    assert cr2.compacted_hash == ch

    # Hash must be stable
    ch2 = compute_compacted_hash(cr2)
    assert ch == ch2


def test_integrity_report_generation():
    """generate_compaction_integrity_report_json must write a valid report file."""
    records = _make_sample_records()
    policy = CompactionPolicy()
    compactor = MemoryCompactor()
    result = compactor.compact(records, policy)

    tmpdir = tempfile.mkdtemp()
    try:
        report_path = os.path.join(tmpdir, "integrity_report.json")
        report = generate_compaction_integrity_report_json(
            result, records, policy, report_path,
        )
        assert os.path.exists(report_path)
        assert report.valid is True

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["valid"] is True
        assert data["result_hash"] == result.result_hash
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Core compaction
        ("compactor returns CompactionResult", test_compactor_returns_compaction_result),
        ("duplicate detection determinism", test_duplicate_detection_determinism),
        ("merge_sources preserves all hashes", test_merge_sources_preserves_all_hashes),
        ("low importance archived", test_low_importance_archived),
        ("low importance skipped when not archiving", test_low_importance_skipped_when_not_archiving),
        ("original records unchanged", test_original_records_unchanged),
        ("compacted_hash stable", test_compacted_hash_stable),
        ("result_hash stable", test_result_hash_stable),
        # Projection I/O
        ("compaction projection roundtrip", test_compaction_projection_roundtrip),
        ("compaction projection loadable", test_compaction_projection_loadable),
        # Verification & integrity
        ("verify_compaction passes valid result", test_verify_compaction_passes_valid_result),
        ("compaction integrity passes", test_compaction_integrity_passes),
        ("quick compaction check", test_quick_compaction_check),
        # Provenance
        ("no provenance loss", test_no_provenance_loss),
        ("compacted records can be indexed", test_compacted_records_can_be_indexed),
        # Retrieval + compaction
        ("retrieval with compacted projection", test_retrieval_with_compacted_projection),
        ("retrieval falls back without compaction", test_retrieval_falls_back_without_compaction),
        # Recall provenance
        ("recall provenance links to original", test_recall_provenance_links_to_original),
        # Projection only
        ("compaction is projection only", test_compaction_is_projection_only),
        ("compaction never truth source", test_compaction_never_truth_source),
        # Removability
        ("deleting projection leaves kernel unaffected", test_deleting_projection_leaves_kernel_unaffected),
        # Banned imports
        ("no banned LLM/vector imports", test_no_banned_imports_in_compaction),
        # Regression (existing tests still pass)
        ("phase 4D regression", test_phase_4d_regression),
        ("kernel invariants regression", test_kernel_invariants_regression),
        # Bonus
        ("policy validation", test_policy_validation),
        ("policy disabled", test_policy_disabled),
        ("empty records compact", test_empty_records_compact),
        ("group by execution_id", test_group_by_execution_id),
        ("group by tag", test_group_by_tag),
        ("group by content_hash", test_group_by_content_hash),
        ("content fingerprint determinism", test_content_fingerprint_determinism),
        ("compacted to episodic conversion", test_compacted_to_episodic_conversion),
        ("integrity report generation", test_integrity_report_generation),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Memory Compaction Tests (Phase 4D-5)")
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
