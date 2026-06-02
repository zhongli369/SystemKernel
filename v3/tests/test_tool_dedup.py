"""Tool Dedup Tests — L2 Tool Interface."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.external.tool_dedup import (
    DedupReport,
    detect_duplicates,
    _jaccard,
    _tokenize,
    DUPLICATE_THRESHOLD,
)
from v3.external.capability_registry import (
    CapabilityRegistry,
    CapabilityRegistryEntry,
)
from v3.external.capability_contract import ExternalCapabilityAdapterSpec


class TestToolDedup(unittest.TestCase):

    def test_01_identical_descriptions_are_duplicates(self):
        a = {"hello", "world"}
        b = {"hello", "world"}
        self.assertAlmostEqual(_jaccard(a, b), 1.0)

    def test_02_completely_different_no_duplicate(self):
        a = {"foo", "bar"}
        b = {"baz", "qux"}
        self.assertAlmostEqual(_jaccard(a, b), 0.0)

    def test_03_partial_overlap_below_threshold(self):
        t1 = _tokenize("deploy build test")
        t2 = _tokenize("deploy unrelated different")
        score = _jaccard(t1, t2)
        self.assertLess(score, DUPLICATE_THRESHOLD)

    def test_04_empty_registry_no_duplicates(self):
        registry = CapabilityRegistry(entries=())
        result = detect_duplicates(registry)
        self.assertEqual(len(result.duplicates), 0)
        self.assertEqual(len(result.unique_tools), 0)

    def test_05_single_tool_no_duplicates(self):
        entry = _make_entry("tool-1", "skill", "test tool")
        registry = CapabilityRegistry(entries=(entry,))
        result = detect_duplicates(registry)
        self.assertEqual(len(result.duplicates), 0)
        self.assertEqual(result.unique_tools, ("tool-1",))

    def test_06_deterministic_report_hash(self):
        entry = _make_entry("a", "skill", "deploy build test")
        r1 = detect_duplicates(CapabilityRegistry(entries=(entry,)))
        r2 = detect_duplicates(CapabilityRegistry(entries=(entry,)))
        self.assertEqual(r1.report_hash, r2.report_hash)

    def test_07_unique_tools_excludes_duplicates(self):
        e1 = _make_entry("dup-a", "skill",
                        "deploy build test run execute")
        e2 = _make_entry("dup-b", "skill",
                        "deploy build test run execute")
        e3 = _make_entry("unique-c", "tool",
                        "browse web scrape data")
        registry = CapabilityRegistry(entries=(e1, e2, e3))
        result = detect_duplicates(registry, threshold=0.85)
        dup_ids = set()
        for a, b in result.duplicates:
            dup_ids.add(a)
            dup_ids.add(b)
        for uid in result.unique_tools:
            self.assertNotIn(uid, dup_ids)

    def test_08_frozen_dataclass(self):
        entry = _make_entry("a", "skill", "test")
        registry = CapabilityRegistry(entries=(entry,))
        r = detect_duplicates(registry)
        with self.assertRaises(Exception):
            r.report_hash = "mutated"


def _make_entry(adapter_id: str, capability_type: str, notes: str = ""):
    spec = ExternalCapabilityAdapterSpec(
        adapter_id=adapter_id,
        name=adapter_id,
        capability_type=capability_type,
    )
    return CapabilityRegistryEntry(
        adapter_id=adapter_id,
        spec=spec,
        enabled=True,
        notes=notes,
    )
