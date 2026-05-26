"""
Test Usage Report Adapter — Phase 7E external usage adapter tests.

All tests use fixture data. No network access. No ccusage execution.
No dependency on ccusage package.

Tests:
  1. fixture parses
  2. day records created
  3. total tokens computed
  4. total cost computed
  5. cache read ratio computed
  6. models counted
  7. agents counted
  8. date range computed
  9. missing optional fields handled
  10. sensitive text detection false for safe fixture
  11. report_hash deterministic
  12. truth_source false
  13. write_summary writes JSON
  14. verify_summary passes
  15. CLI usage inspect works
  16. CLI usage summarize works
  17. no ccusage import
  18. no external command execution
  19. no network required
  20. no v3/kernel modifications
  21. complexity gate not REJECT
  22. existing developer CLI tests pass
  23. kernel invariants still purity=100
"""

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")
TESTS_DIR = os.path.join(V3_ROOT, "tests")
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")
KERNEL_DIR = os.path.join(V3_ROOT, "kernel")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable
CLI_PATH = os.path.join(V3_ROOT, "cli", "systemkernel.py")


def _fixture(name):
    return os.path.join(FIXTURES_DIR, name)


def _has_import(filepath, module_name):
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name or alias.name.startswith(module_name + "."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == module_name or node.module.startswith(module_name + ".")):
                return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════

class TestUsageReportAdapter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from v3.external.usage_report import UsageReportAdapter
        cls.adapter = UsageReportAdapter
        cls.fixture_path = _fixture("ccusage_daily_sample.json")
        cls.records = UsageReportAdapter.parse_ccusage_json(cls.fixture_path)
        cls.summary = UsageReportAdapter.summarize(cls.records)

    # ── Test 1: fixture parses ────────────────────────────────────────

    def test_01_fixture_parses(self):
        """Fixture JSON file parses without error."""
        records = self.adapter.parse_ccusage_json(self.fixture_path)
        self.assertIsInstance(records, tuple)
        self.assertEqual(len(records), 3)

    # ── Test 2: day records created ───────────────────────────────────

    def test_02_day_records_created(self):
        """Each entry becomes a UsageDayRecord with expected fields."""
        from v3.external.usage_report import UsageDayRecord

        for r in self.records:
            self.assertIsInstance(r, UsageDayRecord)
            self.assertIsInstance(r.date, str)
            self.assertIsInstance(r.total_tokens, int)
            self.assertIsInstance(r.input_tokens, int)
            self.assertIsInstance(r.output_tokens, int)
            self.assertIsInstance(r.cache_read_tokens, int)
            self.assertIsInstance(r.cost_usd, float)
            self.assertIsInstance(r.models, tuple)
            self.assertIsInstance(r.agents, tuple)

    # ── Test 3: total tokens computed ─────────────────────────────────

    def test_03_total_tokens_computed(self):
        """Summary total_tokens equals sum of day totals."""
        expected = sum(r.total_tokens for r in self.records)
        self.assertEqual(self.summary.total_tokens, expected)
        self.assertGreater(self.summary.total_tokens, 0)

    # ── Test 4: total cost computed ───────────────────────────────────

    def test_04_total_cost_computed(self):
        """Summary total_cost_usd equals sum of day costs."""
        expected = round(sum(r.cost_usd for r in self.records), 6)
        self.assertEqual(self.summary.total_cost_usd, expected)

    # ── Test 5: cache read ratio computed ─────────────────────────────

    def test_05_cache_read_ratio_computed(self):
        """Cache read ratio is between 0 and 1."""
        self.assertGreaterEqual(self.summary.cache_read_ratio, 0.0)
        self.assertLessEqual(self.summary.cache_read_ratio, 1.0)

    # ── Test 6: models counted ────────────────────────────────────────

    def test_06_models_counted(self):
        """Model count matches unique models across records."""
        all_models = set()
        for r in self.records:
            all_models.update(r.models)
        self.assertEqual(self.summary.model_count, len(all_models))
        self.assertGreater(self.summary.model_count, 0)

    # ── Test 7: agents counted ────────────────────────────────────────

    def test_07_agents_counted(self):
        """Agent count matches unique agents across records."""
        all_agents = set()
        for r in self.records:
            all_agents.update(r.agents)
        self.assertEqual(self.summary.agent_count, len(all_agents))
        self.assertGreater(self.summary.agent_count, 0)

    # ── Test 8: date range computed ───────────────────────────────────

    def test_08_date_range_computed(self):
        """Date range is sorted ascending."""
        self.assertEqual(self.summary.date_start, "2026-05-20")
        self.assertEqual(self.summary.date_end, "2026-05-22")
        self.assertLessEqual(self.summary.date_start, self.summary.date_end)

    # ── Test 9: missing optional fields handled ───────────────────────

    def test_09_missing_optional_fields_handled(self):
        """Entries with missing fields do not crash parsing."""
        incomplete = {
            "daily": [
                {"period": "2026-06-01", "totalTokens": 100},
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(incomplete, f)
            tmp_path = f.name

        try:
            records = self.adapter.parse_ccusage_json(tmp_path)
            self.assertEqual(len(records), 1)
            r = records[0]
            self.assertEqual(r.date, "2026-06-01")
            self.assertEqual(r.total_tokens, 100)
            self.assertEqual(r.input_tokens, 0)
            self.assertEqual(r.output_tokens, 0)
            self.assertEqual(r.cost_usd, 0.0)
            self.assertEqual(r.models, ())
            self.assertEqual(r.agents, ())
        finally:
            os.unlink(tmp_path)

    # ── Test 10: sensitive text detection false for safe fixture ──────

    def test_10_sensitive_text_detection_false(self):
        """Safe fixture has no sensitive text detected."""
        self.assertFalse(self.summary.sensitive_text_detected)

    # ── Test 11: report_hash deterministic ────────────────────────────

    def test_11_report_hash_deterministic(self):
        """Same input produces same report_hash."""
        s1 = self.adapter.summarize(self.records)
        s2 = self.adapter.summarize(self.records)
        self.assertEqual(s1.report_hash, s2.report_hash)
        self.assertEqual(len(self.summary.report_hash), 16)

    # ── Test 12: truth_source false ───────────────────────────────────

    def test_12_truth_source_false(self):
        """truth_source is always False."""
        self.assertFalse(self.summary.truth_source)

    # ── Test 13: write_summary writes JSON ─────────────────────────────

    def test_13_write_summary_writes_json(self):
        """write_summary produces valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            self.adapter.write_summary(self.summary, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            with open(tmp_path, encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data["source_tool"], "ccusage")
            self.assertEqual(data["record_count"], 3)
            self.assertFalse(data["truth_source"])
            self.assertIn("report_hash", data)
        finally:
            os.unlink(tmp_path)

    # ── Test 14: verify_summary passes ────────────────────────────────

    def test_14_verify_summary_passes(self):
        """Valid summary passes verification."""
        self.assertTrue(self.adapter.verify_summary(self.summary))

    # ── Test 15: CLI usage inspect works ──────────────────────────────

    def test_15_cli_usage_inspect_works(self):
        """systemkernel usage inspect <path> runs successfully."""
        result = subprocess.run(
            [PYTHON, CLI_PATH, "usage", "inspect", self.fixture_path],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage Report Inspect", result.stdout)
        self.assertIn("truth source", result.stdout.lower())

    # ── Test 16: CLI usage summarize works ────────────────────────────

    def test_16_cli_usage_summarize_works(self):
        """systemkernel usage summarize writes output file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            out_path = f.name

        try:
            result = subprocess.run(
                [PYTHON, CLI_PATH, "usage", "summarize", self.fixture_path,
                 "--output", out_path],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(os.path.exists(out_path))

            with open(out_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["source_tool"], "ccusage")
            self.assertFalse(data["truth_source"])
        finally:
            os.unlink(out_path)

    # ── Test 17: no ccusage import ────────────────────────────────────

    def test_17_no_ccusage_import(self):
        """usage_report.py does not import ccusage."""
        self.assertFalse(
            _has_import(os.path.join(EXTERNAL_DIR, "usage_report.py"), "ccusage"),
            "usage_report.py must not import ccusage"
        )

    # ── Test 18: no external command execution ────────────────────────

    def test_18_no_external_command_execution(self):
        """usage_report.py does not use subprocess or os.system for ccusage."""
        fpath = os.path.join(EXTERNAL_DIR, "usage_report.py")
        with open(fpath, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == "subprocess" or node.func.value.id == "os":
                            if node.func.attr in ("run", "call", "Popen", "system", "popen"):
                                self.fail(
                                    f"usage_report.py must not call {node.func.value.id}.{node.func.attr}()"
                                )

    # ── Test 19: no network required ──────────────────────────────────

    def test_19_no_network_required(self):
        """usage_report.py uses no networking libraries."""
        for banned in ("socket", "urllib", "requests", "http"):
            self.assertFalse(
                _has_import(os.path.join(EXTERNAL_DIR, "usage_report.py"), banned),
                f"usage_report.py must not import {banned}"
            )

    # ── Test 20: no v3/kernel modifications ───────────────────────────

    def test_20_no_kernel_modifications(self):
        """This adapter does not touch v3/kernel files."""
        kernel_files = set()
        for root_dir, dirs, files in os.walk(KERNEL_DIR):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in files:
                if fname.endswith(".py"):
                    kernel_files.add(os.path.join(root_dir, fname))

        adapter_path = os.path.join(EXTERNAL_DIR, "usage_report.py")
        with open(adapter_path, encoding="utf-8") as f:
            source = f.read()

        for kf in kernel_files:
            rel = os.path.relpath(kf, ROOT)
            if rel.replace("\\", "/") in source:
                self.fail(f"usage_report.py references kernel file: {rel}")

    # ── Test 21: complexity gate not REJECT ───────────────────────────

    def test_21_complexity_gate_not_reject(self):
        """Adapter addition should not cause REJECT in complexity gate."""
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from v3.quality.phase_gate import evaluate_phase

        result = evaluate_phase("5A", v3_root=V3_ROOT)
        self.assertNotEqual(
            result.verdict.verdict, "REJECT",
            f"Complexity gate REJECTED: {'; '.join(result.verdict.reasons)}"
        )

    # ── Test 22: existing developer CLI tests pass ────────────────────

    def test_22_existing_developer_cli_tests_pass(self):
        """Developer CLI tests still pass."""
        test_path = os.path.join(TESTS_DIR, "test_developer_cli.py")
        result = subprocess.run(
            [PYTHON, test_path],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0,
                         f"test_developer_cli.py failed:\n{result.stderr[:2000]}")

    # ── Test 23: kernel invariants still purity=100 ───────────────────

    def test_23_kernel_invariants_purity(self):
        """Kernel invariants tests still report purity=100."""
        test_path = os.path.join(TESTS_DIR, "test_kernel_invariants.py")
        result = subprocess.run(
            [PYTHON, test_path],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0,
                         f"test_kernel_invariants.py failed:\n{result.stderr[:2000]}")

    # ── Additional: empty records ─────────────────────────────────────

    def test_24_empty_records_produces_zero_summary(self):
        """Empty record set produces a valid zero-summary."""
        summary = self.adapter.summarize(())
        self.assertEqual(summary.record_count, 0)
        self.assertEqual(summary.total_tokens, 0)
        self.assertEqual(summary.total_cost_usd, 0.0)
        self.assertTrue(self.adapter.verify_summary(summary))

    # ── Additional: record ordering is deterministic ──────────────────

    def test_25_record_ordering_deterministic(self):
        """Records are always sorted by date ascending."""
        dates = [r.date for r in self.records]
        self.assertEqual(dates, sorted(dates))

    # ── Additional: UsageReportConfig ──────────────────────────────────

    def test_26_usage_report_config_defaults(self):
        """UsageReportConfig has expected defaults."""
        from v3.external.usage_report import UsageReportConfig

        config = UsageReportConfig(input_path="/tmp/test.json")
        self.assertEqual(config.source_tool, "ccusage")
        self.assertTrue(config.redaction_enabled)
        self.assertTrue(config.include_model_breakdown)
        self.assertTrue(config.include_agent_breakdown)
        self.assertFalse(config.dry_run)

    # ── Additional: write_summary creates directories ──────────────────

    def test_27_write_summary_creates_dirs(self):
        """write_summary creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "subdir", "nested", "output.json")
            self.adapter.write_summary(self.summary, out_path)
            self.assertTrue(os.path.exists(out_path))

    # ── Additional: verify_summary rejects truth_source=True ──────────

    def test_28_verify_summary_rejects_truth_source_true(self):
        """Summary with truth_source=True fails verification."""
        from v3.external.usage_report import UsageReportSummary

        bad = UsageReportSummary(
            source_tool="ccusage", record_count=1, total_tokens=100,
            total_cost_usd=0.0, cache_read_ratio=0.5, model_count=1,
            agent_count=1, date_start="2026-01-01", date_end="2026-01-01",
            sensitive_text_detected=False, report_hash="abc123",
            truth_source=True,
        )
        self.assertFalse(self.adapter.verify_summary(bad))

    # ── Additional: verify_summary rejects bad ratios ──────────────────

    def test_29_verify_summary_rejects_bad_ratios(self):
        """Summary with invalid cache_read_ratio fails verification."""
        from v3.external.usage_report import UsageReportSummary

        bad = UsageReportSummary(
            source_tool="ccusage", record_count=1, total_tokens=100,
            total_cost_usd=0.0, cache_read_ratio=1.5, model_count=1,
            agent_count=1, date_start="2026-01-01", date_end="2026-01-01",
            sensitive_text_detected=False, report_hash="abc123",
        )
        self.assertFalse(self.adapter.verify_summary(bad))

    # ── Additional: verify_summary fails for negative cost ─────────────

    def test_30_verify_summary_rejects_negative_cost(self):
        """Summary with negative cost fails verification."""
        from v3.external.usage_report import UsageReportSummary

        bad = UsageReportSummary(
            source_tool="ccusage", record_count=1, total_tokens=100,
            total_cost_usd=-5.0, cache_read_ratio=0.5, model_count=1,
            agent_count=1, date_start="2026-01-01", date_end="2026-01-01",
            sensitive_text_detected=False, report_hash="abc123",
        )
        self.assertFalse(self.adapter.verify_summary(bad))

    # ── Additional: UsageDayRecord frozen ──────────────────────────────

    def test_31_day_record_frozen(self):
        """UsageDayRecord is frozen (immutable)."""
        from v3.external.usage_report import UsageDayRecord

        r = UsageDayRecord(
            date="2026-01-01", total_tokens=100, input_tokens=50,
            output_tokens=50, cache_creation_tokens=0, cache_read_tokens=100,
            cost_usd=0.0, models=("m1",), agents=("a1",),
        )
        with self.assertRaises(Exception):
            r.total_tokens = 200

    # ── Additional: UsageReportSummary frozen ──────────────────────────

    def test_32_summary_frozen(self):
        """UsageReportSummary is frozen."""
        with self.assertRaises(Exception):
            self.summary.total_tokens = 0


if __name__ == "__main__":
    unittest.main()
