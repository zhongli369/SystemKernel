"""Tool Conflicts Tests — L2 Tool Interface."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.external.tool_conflicts import (
    ConflictReport,
    detect_conflicts,
    KNOWN_CONFLICTS,
    register_conflict,
    unregister_conflict,
    list_conflict_rules,
)


class TestToolConflicts(unittest.TestCase):

    def test_01_known_conflict_detected(self):
        result = detect_conflicts(("mem0_memory_intelligence",
                                   "graphiti_temporal_kg"))
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("mem0_memory_intelligence", result.conflicts[0])
        self.assertIn("graphiti_temporal_kg", result.conflicts[0])

    def test_02_no_conflict_for_safe_pair(self):
        result = detect_conflicts(("context_pack", "skill_evolution"))
        self.assertEqual(len(result.conflicts), 0)

    def test_03_empty_selection_no_conflicts(self):
        result = detect_conflicts(())
        self.assertEqual(len(result.conflicts), 0)

    def test_04_single_tool_no_conflicts(self):
        result = detect_conflicts(("mem0_memory_intelligence",))
        self.assertEqual(len(result.conflicts), 0)

    def test_05_symmetric_detection(self):
        r1 = detect_conflicts(("mem0_memory_intelligence",
                               "graphiti_temporal_kg"))
        r2 = detect_conflicts(("graphiti_temporal_kg",
                               "mem0_memory_intelligence"))
        self.assertEqual(len(r1.conflicts), len(r2.conflicts))
        self.assertEqual(r1.conflict_hash, r2.conflict_hash)

    def test_06_all_known_rules_valid(self):
        for tool_a, tool_b, reason in KNOWN_CONFLICTS:
            self.assertIsInstance(tool_a, str)
            self.assertIsInstance(tool_b, str)
            self.assertIsInstance(reason, str)
            self.assertNotEqual(tool_a, tool_b)
            self.assertGreater(len(reason), 0)

    def test_07_frozen_dataclass(self):
        r = detect_conflicts(("a",))
        with self.assertRaises(Exception):
            r.conflict_hash = "mutated"

    def test_08_register_and_unregister(self):
        register_conflict("test-a", "test-b", "test conflict")
        r = detect_conflicts(("test-a", "test-b"))
        self.assertEqual(len(r.conflicts), 1)
        unregister_conflict("test-a", "test-b")
        r2 = detect_conflicts(("test-a", "test-b"))
        self.assertEqual(len(r2.conflicts), 0)

    def test_09_list_rules_includes_known(self):
        rules = list_conflict_rules()
        self.assertGreaterEqual(len(rules), len(KNOWN_CONFLICTS))

    def test_10_no_self_conflict(self):
        result = detect_conflicts(("mem0_memory_intelligence",
                                   "mem0_memory_intelligence"))
        self.assertEqual(len(result.conflicts), 0)
