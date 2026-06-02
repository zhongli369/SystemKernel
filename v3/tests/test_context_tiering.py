"""
Context Tiering Tests — L3 Context Management.

Tests for tier_policy, tier_store, tier_retrieval.
Stdlib only. Each test is independent and uses tmp_path.
No external dependencies. No disk state pollution.
"""

import json
import math
import os
import sys
import time
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.external.context_tiering.tier_policy import (
    MemoryTier,
    TIER_WORKING,
    TIER_EPISODIC,
    TIER_SEMANTIC,
    TierEntry,
    tier_policy,
    compute_importance,
    compact_episodic_to_semantic,
    compute_ttl_expiry,
    RECENCY_DECAY_RATE,
)
from v3.external.context_tiering.tier_store import (
    FileTierStore,
    create_tier_store,
)
from v3.external.context_tiering.tier_retrieval import (
    RetrievalResult,
    progressive_load,
    rank_by_relevance,
    retrieve_context,
)


# ═══════════════════════════════════════════════════════════════════════
# Test 1: TierEntry creation and freezing
# ═══════════════════════════════════════════════════════════════════════

class TestTierEntryCreation(unittest.TestCase):

    def test_01_entry_frozen(self):
        """TierEntry is frozen — mutation raises exception."""
        entry = tier_policy(TIER_WORKING, execution_id="exec-01")
        with self.assertRaises(Exception):
            entry.entry_id = "mutated"

    def test_02_entry_to_dict_roundtrip(self):
        """to_dict → from_dict preserves all fields."""
        ts = 1717286400.0
        entry = TierEntry(
            entry_id="test-001",
            tier=TIER_EPISODIC,
            execution_id="exec-42",
            content={"stage": "init", "ok": True},
            entity_key="stage_init",
            entity_type="stage",
            importance=0.75,
            timestamp=ts,
            ttl_expires_at=ts + 604800,
        )
        d = entry.to_dict()
        restored = TierEntry.from_dict(d)
        self.assertEqual(restored.entry_id, entry.entry_id)
        self.assertEqual(restored.tier, entry.tier)
        self.assertEqual(restored.execution_id, entry.execution_id)
        self.assertEqual(restored.content, entry.content)
        self.assertEqual(restored.entity_key, entry.entity_key)
        self.assertEqual(restored.entity_type, entry.entity_type)
        self.assertAlmostEqual(restored.importance, entry.importance)
        self.assertAlmostEqual(restored.timestamp, entry.timestamp)
        self.assertAlmostEqual(restored.ttl_expires_at, entry.ttl_expires_at)

    def test_03_tier_ttl_working(self):
        """WORKING tier has ttl_expires_at = 0."""
        entry = tier_policy(TIER_WORKING)
        self.assertEqual(entry.ttl_expires_at, 0.0)
        self.assertEqual(entry.tier, TIER_WORKING)

    def test_04_tier_ttl_episodic(self):
        """EPISODIC tier has ttl_expires_at = timestamp + 604800."""
        ts = 1717286400.0
        entry = tier_policy(TIER_EPISODIC, timestamp=ts)
        self.assertAlmostEqual(entry.ttl_expires_at, ts + 604800)
        self.assertEqual(entry.tier, TIER_EPISODIC)

    def test_05_tier_ttl_semantic(self):
        """SEMANTIC tier has ttl_expires_at = -1 (permanent)."""
        entry = tier_policy(TIER_SEMANTIC)
        self.assertEqual(entry.ttl_expires_at, -1.0)
        self.assertEqual(entry.tier, TIER_SEMANTIC)


# ═══════════════════════════════════════════════════════════════════════
# Test 2: FileTierStore save and load
# ═══════════════════════════════════════════════════════════════════════

class TestFileTierStoreSaveLoad(unittest.TestCase):

    def setUp(self):
        self.tmp = _make_tmp_store()

    def tearDown(self):
        self.tmp = None

    def test_06_save_working_in_memory_only(self):
        """L1 entries stay in memory, never touch disk."""
        entry = tier_policy(TIER_WORKING, execution_id="exec-01",
                            content={"data": "L1"})
        self.tmp.save(entry)
        # L1 loaded via load_by_tier
        l1 = self.tmp.load_by_tier(TIER_WORKING)
        self.assertEqual(len(l1), 1)
        self.assertEqual(l1[0].content["data"], "L1")
        # No file written
        self.assertFalse(self.tmp._episodic_dir.exists())

    def test_07_save_episodic_writes_jsonl(self):
        """L2 entries write to episodic/{execution_id}.jsonl."""
        entry = tier_policy(TIER_EPISODIC, execution_id="exec-02",
                            content={"stage": "build"})
        self.tmp.save(entry)
        l2_path = self.tmp._l2_path("exec-02")
        self.assertTrue(l2_path.exists())
        raw = self.tmp._read_jsonl(l2_path)
        self.assertEqual(len(raw), 1)
        self.assertEqual(raw[0]["execution_id"], "exec-02")

    def test_08_save_semantic_writes_jsonl(self):
        """L3 entries write to semantic/entities.jsonl."""
        entry = tier_policy(TIER_SEMANTIC, execution_id="exec-03",
                            entity_key="pattern_x")
        self.tmp.save(entry)
        l3_path = self.tmp._l3_path()
        self.assertTrue(l3_path.exists())
        raw = self.tmp._read_jsonl(l3_path)
        self.assertEqual(len(raw), 1)
        self.assertEqual(raw[0]["entity_key"], "pattern_x")

    def test_09_load_by_execution(self):
        """load_by_execution returns L1 + L2 entries for an execution."""
        e1 = tier_policy(TIER_WORKING, execution_id="exec-10",
                         content={"order": 1})
        e2 = tier_policy(TIER_EPISODIC, execution_id="exec-10",
                         content={"order": 2})
        e3 = tier_policy(TIER_EPISODIC, execution_id="exec-99",
                         content={"order": 3})
        self.tmp.save(e1)
        self.tmp.save(e2)
        self.tmp.save(e3)
        results = self.tmp.load_by_execution("exec-10")
        ids = {r.entry_id for r in results}
        self.assertIn(e1.entry_id, ids)
        self.assertIn(e2.entry_id, ids)
        self.assertNotIn(e3.entry_id, ids)

    def test_10_load_by_tier(self):
        """load_by_tier returns all entries for a tier."""
        e1 = tier_policy(TIER_WORKING, execution_id="e")
        e2 = tier_policy(TIER_EPISODIC, execution_id="e")
        e3 = tier_policy(TIER_SEMANTIC, execution_id="e",
                         entity_key="key3")
        self.tmp.save(e1)
        self.tmp.save(e2)
        self.tmp.save(e3)
        l1 = self.tmp.load_by_tier(TIER_WORKING)
        l2 = self.tmp.load_by_tier(TIER_EPISODIC)
        l3 = self.tmp.load_by_tier(TIER_SEMANTIC)
        self.assertEqual(len(l1), 1)
        self.assertEqual(len(l2), 1)
        self.assertEqual(len(l3), 1)
        self.assertEqual(l1[0].tier, TIER_WORKING)
        self.assertEqual(l2[0].tier, TIER_EPISODIC)
        self.assertEqual(l3[0].tier, TIER_SEMANTIC)


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Expire
# ═══════════════════════════════════════════════════════════════════════

class TestFileTierStoreExpire(unittest.TestCase):

    def setUp(self):
        self.tmp = _make_tmp_store()

    def tearDown(self):
        self.tmp = None

    def test_11_expire_removes_expired_l2(self):
        """Expired L2 entries are cleaned up."""
        past = time.time() - 86400 * 10  # 10 days ago
        expired = TierEntry(
            entry_id="old-1", tier=TIER_EPISODIC,
            execution_id="exec-old",
            content={}, timestamp=past,
            ttl_expires_at=past + 604800,  # expired ~3 days ago
        )
        self.tmp.save(expired)
        removed = self.tmp.expire()
        self.assertGreaterEqual(removed, 0)
        remaining = self.tmp.load_by_execution("exec-old")
        self.assertEqual(len(remaining), 0)

    def test_12_expire_preserves_valid_l2(self):
        """Valid L2 entries survive expire()."""
        future = time.time() + 86400 * 5  # 5 days from now
        valid = TierEntry(
            entry_id="valid-1", tier=TIER_EPISODIC,
            execution_id="exec-valid",
            content={"key": "val"}, timestamp=time.time(),
            ttl_expires_at=future,
        )
        self.tmp.save(valid)
        self.tmp.expire()
        results = self.tmp.load_by_execution("exec-valid")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].entry_id, "valid-1")

    def test_13_expire_mixed_file_partial_cleanup(self):
        """Mixed file: expired removed, valid kept."""
        now = time.time()
        expired = TierEntry(
            entry_id="old-mix", tier=TIER_EPISODIC,
            execution_id="exec-mix",
            content={}, timestamp=now - 86400 * 10,
            ttl_expires_at=now - 1,  # expired
        )
        valid = TierEntry(
            entry_id="new-mix", tier=TIER_EPISODIC,
            execution_id="exec-mix",
            content={}, timestamp=now,
            ttl_expires_at=now + 604800,  # valid
        )
        self.tmp.save(expired)
        self.tmp.save(valid)
        self.tmp.expire()
        results = self.tmp.load_by_execution("exec-mix")
        ids = {r.entry_id for r in results}
        self.assertIn("new-mix", ids)
        self.assertNotIn("old-mix", ids)


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Compact
# ═══════════════════════════════════════════════════════════════════════

class TestFileTierStoreCompact(unittest.TestCase):

    def setUp(self):
        self.tmp = _make_tmp_store()

    def tearDown(self):
        self.tmp = None

    def test_14_compact_promotes_l2_to_l3(self):
        """3+ L2 entries with same entity_key → promoted to L3."""
        now = time.time()
        for i in range(3):
            entry = TierEntry(
                entry_id=f"compact-{i}",
                tier=TIER_EPISODIC,
                execution_id=f"exec-{i}",
                content={"stage": f"s{i}"},
                entity_key="shared_entity",
                entity_type="stage",
                importance=0.5,
                timestamp=now - (2 - i) * 3600,  # spread over hours
                ttl_expires_at=now + 604800,
            )
            self.tmp.save(entry)

        promoted = self.tmp.compact(window_days=7, threshold=3)
        self.assertEqual(promoted, 1)

        l3 = self.tmp.load_by_tier(TIER_SEMANTIC)
        self.assertEqual(len(l3), 1)
        self.assertEqual(l3[0].entity_key, "shared_entity")
        self.assertEqual(l3[0].tier, TIER_SEMANTIC)
        self.assertEqual(l3[0].ttl_expires_at, -1.0)

    def test_15_compact_below_threshold_no_promotion(self):
        """2 entries below threshold → nothing promoted."""
        now = time.time()
        for i in range(2):
            entry = TierEntry(
                entry_id=f"below-{i}",
                tier=TIER_EPISODIC,
                execution_id=f"exec-{i}",
                content={},
                entity_key="rare_entity",
                timestamp=now,
                ttl_expires_at=now + 604800,
            )
            self.tmp.save(entry)

        promoted = self.tmp.compact(window_days=7, threshold=3)
        self.assertEqual(promoted, 0)

        l3 = self.tmp.load_by_tier(TIER_SEMANTIC)
        self.assertEqual(len(l3), 0)


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Progressive Load with ranking
# ═══════════════════════════════════════════════════════════════════════

class TestProgressiveLoad(unittest.TestCase):

    def setUp(self):
        self.store = _make_tmp_store()

    def tearDown(self):
        self.store = None

    def _make_entry(self, tier, eid, exec_id, content, entity_key="",
                    importance=0.5):
        now = time.time()
        return TierEntry(
            entry_id=eid, tier=tier, execution_id=exec_id,
            content=content, entity_key=entity_key, entity_type="test",
            importance=importance, timestamp=now,
            ttl_expires_at=now + 604800 if tier != TIER_SEMANTIC else -1.0,
        )

    def test_16_l1_hit_short_circuits(self):
        """L1 match returns immediately without checking L2/L3."""
        e = self._make_entry(TIER_WORKING, "l1-1", "e1",
                            {"text": "deploy pipeline error"})
        self.store.save(e)
        result = progressive_load("deploy error", self.store)
        self.assertIn("L1", result.tiers_consulted)
        self.assertNotIn("L2", result.tiers_consulted)
        self.assertNotIn("L3", result.tiers_consulted)
        self.assertEqual(len(result.entries), 1)

    def test_17_progressive_falls_through_to_l2_l3(self):
        """No L1 match → checks L2 and L3."""
        for i in range(3):
            e = self._make_entry(TIER_EPISODIC, f"l2-{i}", f"exec-{i}",
                                {"text": f"error in stage {i}"},
                                entity_key=f"stage_{i}")
            self.store.save(e)
        result = progressive_load("error stage", self.store)
        consulted = set(result.tiers_consulted)
        self.assertIn("L2", consulted)
        self.assertGreaterEqual(len(result.entries), 1)

    def test_18_max_results_truncation(self):
        """max_results limits returned entries."""
        for i in range(10):
            e = self._make_entry(TIER_EPISODIC, f"many-{i}", f"exec-{i}",
                                {"text": f"error stage{i}"},
                                entity_key=f"stage_{i}")
            self.store.save(e)
        result = progressive_load("error stage", self.store, max_results=3)
        self.assertLessEqual(len(result.entries), 3)

    def test_19_min_score_filtering(self):
        """min_score filters low-relevance entries."""
        e1 = self._make_entry(TIER_EPISODIC, "rel-1", "e1",
                             {"text": "deploy error build failed"})
        e2 = self._make_entry(TIER_EPISODIC, "rel-2", "e2",
                             {"text": "completely unrelated topic"})
        self.store.save(e1)
        self.store.save(e2)
        result = progressive_load("deploy error", self.store, min_score=0.1)
        entry_ids = {e.entry_id for e in result.entries}
        self.assertIn("rel-1", entry_ids)
        self.assertNotIn("rel-2", entry_ids)

    def test_20_rank_by_relevance_deterministic(self):
        """Same input → same ranking output."""
        entries = tuple(
            self._make_entry(TIER_EPISODIC, f"det-{i}", f"e{i}",
                           {"text": f"stage {i} result"})
            for i in range(5)
        )
        r1, s1 = rank_by_relevance(entries, "stage result")
        r2, s2 = rank_by_relevance(entries, "stage result")
        self.assertEqual([e.entry_id for e in r1], [e.entry_id for e in r2])
        self.assertEqual(s1, s2)


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Importance Score Determinism
# ═══════════════════════════════════════════════════════════════════════

class TestImportanceScore(unittest.TestCase):

    def test_21_same_inputs_same_output(self):
        """compute_importance is deterministic."""
        s1 = compute_importance(recency_hours=2.0, frequency_count=3,
                                success=True)
        s2 = compute_importance(recency_hours=2.0, frequency_count=3,
                                success=True)
        self.assertEqual(s1, s2)

    def test_22_failure_scores_higher_than_success(self):
        """Failure (success=False) → higher importance than success."""
        score_fail = compute_importance(recency_hours=1.0, frequency_count=1,
                                        success=False)
        score_ok = compute_importance(recency_hours=1.0, frequency_count=1,
                                      success=True)
        self.assertGreater(score_fail, score_ok)

    def test_23_older_entries_score_lower(self):
        """More hours → lower importance (recency decay)."""
        score_recent = compute_importance(recency_hours=1.0, frequency_count=2,
                                          success=True)
        score_old = compute_importance(recency_hours=48.0, frequency_count=2,
                                       success=True)
        self.assertGreater(score_recent, score_old)

    def test_24_higher_frequency_higher_score(self):
        """More occurrences → higher importance."""
        s_low = compute_importance(recency_hours=1.0, frequency_count=1,
                                   success=True)
        s_high = compute_importance(recency_hours=1.0, frequency_count=10,
                                    success=True)
        self.assertGreater(s_high, s_low)

    def test_25_score_range(self):
        """Score is always in [0.0, ~2.0]."""
        for h in [0.0, 1.0, 24.0, 168.0]:
            for f in [1, 3, 10]:
                for ok in [True, False]:
                    s = compute_importance(h, f, ok)
                    self.assertGreaterEqual(s, 0.0)
                    self.assertLess(s, 2.0)


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Token Budget (implemented in Step 2)
# ═══════════════════════════════════════════════════════════════════════

class TestTokenBudget(unittest.TestCase):

    def test_26_token_budget_truncation(self):
        """max_tokens limits total token count in results."""
        store = _make_tmp_store()
        # Create entries with large content
        for i in range(20):
            entry = tier_policy(
                TIER_EPISODIC, execution_id=f"tok-{i}",
                content={"text": "error deploy " * 50 + f"stage_{i} "},
                entity_key=f"stage_{i}",
            )
            store.save(entry)
        # max_tokens=100 should return far fewer entries than max_tokens=8192
        # Use min_score=0 to avoid scoring noise in token budget test
        result_small = progressive_load("error deploy", store, max_tokens=100, min_score=0)
        result_large = progressive_load("error deploy", store, max_tokens=8192, min_score=0)
        self.assertLess(len(result_small.entries), len(result_large.entries))
        self.assertGreater(result_large.total_tokens, 0)

    def test_27_token_estimation_positive(self):
        """_estimate_tokens returns positive integer for any entry."""
        from v3.external.context_tiering.tier_retrieval import _estimate_tokens
        entry = tier_policy(TIER_EPISODIC, content={"key": "value " * 100})
        tokens = _estimate_tokens(entry)
        self.assertGreater(tokens, 0)
        self.assertIsInstance(tokens, int)


# ═══════════════════════════════════════════════════════════════════════
# Test 8: Auto Compact (implemented in Step 5)
# ═══════════════════════════════════════════════════════════════════════

class TestAutoCompact(unittest.TestCase):

    def test_28_auto_compact_on_save(self):
        """Saving 5 L2 entries with same entity_key triggers auto-compact."""
        store = _make_tmp_store()
        store.auto_compact = True
        store.compact_threshold = 5
        now = time.time()
        for i in range(5):
            entry = TierEntry(
                entry_id=f"auto-{i}",
                tier=TIER_EPISODIC,
                execution_id=f"exec-auto-{i}",
                content={"stage": f"s{i}"},
                entity_key="auto_entity",
                entity_type="stage",
                importance=0.5,
                timestamp=now,
                ttl_expires_at=now + 604800,
            )
            store.save(entry)
        # After 5th save, L3 should have the compacted entry
        l3 = store.load_by_tier(TIER_SEMANTIC)
        self.assertEqual(len(l3), 1)
        self.assertEqual(l3[0].entity_key, "auto_entity")


# ═══════════════════════════════════════════════════════════════════════
# Test 9: Execution Hook (Step 3)
# ═══════════════════════════════════════════════════════════════════════

class TestExecutionHook(unittest.TestCase):

    def setUp(self):
        self.store = _make_tmp_store()

    def tearDown(self):
        self.store = None

    def test_29_hook_stage_lifecycle(self):
        """on_stage_start → on_stage_complete → flush produces L2 entry."""
        from v3.external.context_tiering.execution_hook import TierContextHook
        hook = TierContextHook(self.store)
        hook.on_stage_start("exec-01", "init")
        hook.on_stage_complete("exec-01", "init",
                              {"ok": True, "duration_ms": 50})
        promoted = hook.flush("exec-01", min_importance=0.0)
        self.assertEqual(promoted, 1)
        l2 = self.store.load_by_execution("exec-01")
        self.assertEqual(len(l2), 1)
        self.assertEqual(l2[0].tier, TIER_EPISODIC)
        self.assertEqual(l2[0].content["stage_name"], "init")
        self.assertEqual(l2[0].content["status"], "completed")
        self.assertTrue(l2[0].content["success"])

    def test_30_hook_respects_min_importance(self):
        """Entries below min_importance are not promoted to L2."""
        from v3.external.context_tiering.execution_hook import TierContextHook
        hook = TierContextHook(self.store)
        hook.on_stage_start("exec-02", "low_priority")
        hook.on_stage_complete("exec-02", "low_priority",
                              {"ok": True, "duration_ms": 10})
        promoted = hook.flush("exec-02", min_importance=0.99)
        self.assertEqual(promoted, 0)
        l2 = self.store.load_by_execution("exec-02")
        self.assertEqual(len(l2), 0)

    def test_31_hook_multiple_stages(self):
        """Multiple stages in one execution, all promoted."""
        from v3.external.context_tiering.execution_hook import TierContextHook
        hook = TierContextHook(self.store)
        for stage in ["init", "build", "test", "deploy"]:
            hook.on_stage_start("exec-03", stage)
            hook.on_stage_complete("exec-03", stage,
                                  {"ok": True, "duration_ms": 100})
        promoted = hook.flush("exec-03")
        self.assertEqual(promoted, 4)
        l2 = self.store.load_by_execution("exec-03")
        self.assertEqual(len(l2), 4)

    def test_32_metrics_counters(self):
        """Save operations increment metrics counters."""
        from v3.external.context_tiering.execution_hook import TierContextHook
        hook = TierContextHook(self.store)
        hook.on_stage_start("exec-04", "init")
        hook.on_stage_complete("exec-04", "init",
                              {"ok": True, "duration_ms": 30})
        hook.flush("exec-04")
        m = self.store.metrics
        self.assertGreaterEqual(m["writes_working"], 1)
        self.assertGreaterEqual(m["writes_episodic"], 1)


# ═══════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════

_temp_counter = 0

def _make_tmp_store():
    global _temp_counter
    import tempfile
    _temp_counter += 1
    tmpdir = Path(tempfile.mkdtemp(prefix=f"tier_test_{_temp_counter}_"))
    return FileTierStore(storage_root=tmpdir)
