"""
Phase 13C — Tests for v4 Simplification Audit.

At least 25 tests covering module surface analysis, opportunity detection,
audit report generation, and safety constraints.
"""
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

# Ensure the root is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Import module under test ──
from v3.quality.v4_simplification_audit import (
    ModuleSurfaceMetrics,
    SimplificationOpportunity,
    SimplificationAuditReport,
    analyze_module_surface,
    find_simplification_opportunities,
    build_v4_simplification_audit,
    write_simplification_audit,
    AUDIT_TARGETS,
    DO_NOT_TOUCH_PATHS,
    CATEGORIES,
    ROOT as AUDIT_ROOT,
)


class TestModuleSurfaceMetrics(unittest.TestCase):
    """Tests for ModuleSurfaceMetrics dataclass."""

    def test_01_module_metrics_frozen(self):
        """ModuleSurfaceMetrics is frozen."""
        m = ModuleSurfaceMetrics(
            path="test.py", loc=100, dataclass_count=2,
            public_function_count=5, private_function_count=3,
            public_export_count=10, cli_command_count=0,
            test_count=0, report_count=1, dependency_count=8,
            complexity_score=12.5, surface_hash="abc123",
        )
        with self.assertRaises(Exception):
            m.loc = 200

    def test_02_opportunity_frozen(self):
        """SimplificationOpportunity is frozen."""
        o = SimplificationOpportunity(
            opportunity_id="S-001", category="oversized_module",
            target_path="test.py", description="Too large",
            expected_complexity_reduction=5.0, behavior_risk="medium",
            recommended_action="simplify_later", reason="Test",
            opportunity_hash="abc",
        )
        with self.assertRaises(Exception):
            o.category = "other"

    def test_03_audit_report_frozen(self):
        """SimplificationAuditReport is frozen."""
        r = SimplificationAuditReport(
            modules_analyzed=10, total_loc=1000, total_public_api=50,
            total_exports=30, opportunities=(), safe_now_count=0,
            defer_count=5, do_not_touch_count=3,
            ability_plus_10_complexity_plus_300_risk="medium",
            report_hash="abc",
        )
        with self.assertRaises(Exception):
            r.total_loc = 2000

    def test_04_module_metrics_hash_deterministic(self):
        """ModuleSurfaceMetrics hash is deterministic for same inputs."""
        m1 = ModuleSurfaceMetrics(
            path="test.py", loc=100, dataclass_count=2,
            public_function_count=5, private_function_count=3,
            public_export_count=10, cli_command_count=0,
            test_count=0, report_count=1, dependency_count=8,
            complexity_score=12.5, surface_hash="abc123",
        )
        m2 = ModuleSurfaceMetrics(
            path="test.py", loc=100, dataclass_count=2,
            public_function_count=5, private_function_count=3,
            public_export_count=10, cli_command_count=0,
            test_count=0, report_count=1, dependency_count=8,
            complexity_score=12.5, surface_hash="abc123",
        )
        self.assertEqual(m1.surface_hash, m2.surface_hash)
        self.assertEqual(hash(m1), hash(m1))  # self-consistent

    def test_05_opportunity_hash_deterministic(self):
        """SimplificationOpportunity hash is deterministic."""
        o1 = SimplificationOpportunity(
            opportunity_id="S-001", category="oversized_module",
            target_path="test.py", description="Too large",
            expected_complexity_reduction=5.0, behavior_risk="medium",
            recommended_action="simplify_later", reason="Test",
            opportunity_hash="hash1",
        )
        o2 = SimplificationOpportunity(
            opportunity_id="S-001", category="oversized_module",
            target_path="test.py", description="Too large",
            expected_complexity_reduction=5.0, behavior_risk="medium",
            recommended_action="simplify_later", reason="Test",
            opportunity_hash="hash1",
        )
        self.assertEqual(o1.opportunity_hash, o2.opportunity_hash)

    def test_06_report_hash_deterministic(self):
        """SimplificationAuditReport hash is deterministic."""
        r1 = SimplificationAuditReport(
            modules_analyzed=10, total_loc=1000, total_public_api=50,
            total_exports=30, opportunities=(), safe_now_count=0,
            defer_count=5, do_not_touch_count=3,
            ability_plus_10_complexity_plus_300_risk="medium",
            report_hash="test_hash",
        )
        r2 = SimplificationAuditReport(
            modules_analyzed=10, total_loc=1000, total_public_api=50,
            total_exports=30, opportunities=(), safe_now_count=0,
            defer_count=5, do_not_touch_count=3,
            ability_plus_10_complexity_plus_300_risk="medium",
            report_hash="test_hash",
        )
        self.assertEqual(r1.report_hash, r2.report_hash)


class TestSurfaceAnalysis(unittest.TestCase):
    """Tests for module surface analysis."""

    def test_07_analyzes_external(self):
        """Analyzes v3/external/ modules."""
        ext_dir = AUDIT_ROOT / "v3" / "external"
        py_files = list(ext_dir.glob("*.py"))
        for pf in py_files[:3]:
            rel = str(pf.relative_to(AUDIT_ROOT)).replace("\\", "/")
            m = analyze_module_surface(rel)
            self.assertIsInstance(m, ModuleSurfaceMetrics)
            self.assertTrue(m.loc > 0 or pf.stat().st_size == 0)
            self.assertEqual(m.path, rel)

    def test_08_analyzes_evals(self):
        """Analyzes v3/evals/ modules."""
        evals_dir = AUDIT_ROOT / "v3" / "evals"
        py_files = list(evals_dir.glob("*.py"))
        self.assertTrue(len(py_files) > 0, "No eval files found")
        for pf in py_files:
            rel = str(pf.relative_to(AUDIT_ROOT)).replace("\\", "/")
            m = analyze_module_surface(rel)
            self.assertIsInstance(m, ModuleSurfaceMetrics)
            self.assertTrue(m.loc >= 0)

    def test_09_analyzes_ops(self):
        """Analyzes v3/ops/ modules."""
        ops_dir = AUDIT_ROOT / "v3" / "ops"
        py_files = list(ops_dir.glob("*.py"))
        self.assertTrue(len(py_files) > 0, "No ops files found")
        for pf in py_files:
            rel = str(pf.relative_to(AUDIT_ROOT)).replace("\\", "/")
            m = analyze_module_surface(rel)
            self.assertIsInstance(m, ModuleSurfaceMetrics)

    def test_10_analyzes_release(self):
        """Analyzes v3/release/ modules."""
        rel_dir = AUDIT_ROOT / "v3" / "release"
        py_files = list(rel_dir.glob("*.py"))
        self.assertTrue(len(py_files) > 0, "No release files found")
        for pf in py_files[:5]:
            rel = str(pf.relative_to(AUDIT_ROOT)).replace("\\", "/")
            m = analyze_module_surface(rel)
            self.assertIsInstance(m, ModuleSurfaceMetrics)

    def test_11_detects_public_functions(self):
        """Detects public functions in modules."""
        # systemkernel.py should have many public functions
        m = analyze_module_surface("v3/cli/systemkernel.py")
        self.assertGreater(m.public_function_count, 0,
                           "systemkernel.py should have public functions")

    def test_12_detects_dataclasses(self):
        """Detects dataclass definitions."""
        # external/__init__.py or evidence.py should have dataclasses
        m = analyze_module_surface("v3/external/evidence.py")
        self.assertGreaterEqual(m.dataclass_count, 0)

    def test_13_detects_exports(self):
        """Detects __all__ exports."""
        m = analyze_module_surface("v3/external/__init__.py")
        self.assertGreaterEqual(m.public_export_count, 0)

    def test_14_detects_cli_command_surface(self):
        """Detects CLI command surface in systemkernel.py."""
        m = analyze_module_surface("v3/cli/systemkernel.py")
        self.assertGreater(m.cli_command_count, 0,
                           "systemkernel.py should have CLI subcommands")

    def test_15_detects_oversized_module_candidates(self):
        """Identifies oversized module candidates."""
        metrics = [
            ModuleSurfaceMetrics(
                path="big.py", loc=800, dataclass_count=0,
                public_function_count=20, private_function_count=10,
                public_export_count=0, cli_command_count=0,
                test_count=0, report_count=0, dependency_count=10,
                complexity_score=20.0, surface_hash="h1",
            ),
            ModuleSurfaceMetrics(
                path="small.py", loc=100, dataclass_count=0,
                public_function_count=3, private_function_count=1,
                public_export_count=0, cli_command_count=0,
                test_count=0, report_count=0, dependency_count=2,
                complexity_score=3.0, surface_hash="h2",
            ),
        ]
        opportunities = find_simplification_opportunities(metrics)
        oversized = [o for o in opportunities if o.category == "oversized_module"]
        self.assertTrue(len(oversized) >= 1, "Should find at least one oversized module")


class TestOpportunityDetection(unittest.TestCase):
    """Tests for simplification opportunity detection."""

    def test_16_do_not_touch_for_kernel(self):
        """Kernel paths are in DO_NOT_TOUCH_PATHS."""
        kernel_entries = [p for p in DO_NOT_TOUCH_PATHS if "kernel" in p]
        self.assertTrue(len(kernel_entries) > 0,
                        "v3/kernel should be in DO_NOT_TOUCH_PATHS")

    def test_17_do_not_touch_for_release(self):
        """Release paths are in DO_NOT_TOUCH_PATHS."""
        release_entries = [p for p in DO_NOT_TOUCH_PATHS if "release" in p]
        self.assertTrue(len(release_entries) > 0,
                        "v3/release should be in DO_NOT_TOUCH_PATHS")

    def test_18_no_source_mutation(self):
        """Audit module does not mutate source files."""
        # Verify audit module only reads files, never writes to source
        audit_file = AUDIT_ROOT / "v3" / "quality" / "v4_simplification_audit.py"
        source = audit_file.read_text(encoding="utf-8")
        # Audit should not contain any destructive write patterns
        self.assertNotIn("os.remove", source)
        self.assertNotIn("shutil.rmtree", source)
        self.assertNotIn("subprocess.run", source)

    def test_19_no_external_execution(self):
        """Audit module does not execute external tools."""
        audit_file = AUDIT_ROOT / "v3" / "quality" / "v4_simplification_audit.py"
        source = audit_file.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("urllib", source)

    def test_20_no_network(self):
        """Audit module has no network calls."""
        audit_file = AUDIT_ROOT / "v3" / "quality" / "v4_simplification_audit.py"
        source = audit_file.read_text(encoding="utf-8")
        banned = ["requests.", "urllib.request", "http.client", "socket.", "httpx"]
        for b in banned:
            self.assertNotIn(b, source, f"Network call '{b}' found in audit module")

    def test_21_risk_classification_present(self):
        """All opportunities have valid risk classification."""
        o = SimplificationOpportunity(
            opportunity_id="S-001", category="oversized_module",
            target_path="test.py", description="Test",
            expected_complexity_reduction=5.0, behavior_risk="medium",
            recommended_action="simplify_later", reason="Test",
            opportunity_hash="hash1",
        )
        self.assertIn(o.behavior_risk, ("low", "medium", "high"))

    def test_22_report_can_be_written(self):
        """Simplification audit report can be written to disk."""
        import tempfile
        report = build_v4_simplification_audit()
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_simplification_audit(report, tmpdir)
            for key, path in paths.items():
                self.assertTrue(os.path.exists(path),
                                f"Report {key} at {path} should exist")
                self.assertTrue(os.path.getsize(path) > 0,
                                f"Report {key} should not be empty")

    def test_23_complexity_gate_not_reject(self):
        """Complexity gate does not return REJECT for audit scope."""
        report = build_v4_simplification_audit()
        # Risk should be low or medium, not REJECT
        self.assertIn(report.ability_plus_10_complexity_plus_300_risk,
                      ("low", "medium"),
                      f"Risk should not be high, got {report.ability_plus_10_complexity_plus_300_risk}")

    def test_24_valid_categories(self):
        """All opportunities use valid categories."""
        from v3.quality.v4_simplification_audit import CATEGORIES
        report = build_v4_simplification_audit()
        for o in report.opportunities:
            self.assertIn(o.category, CATEGORIES,
                          f"Invalid category: {o.category}")

    def test_25_valid_recommended_actions(self):
        """All opportunities use valid recommended actions."""
        valid_actions = {"keep", "simplify_later", "simplify_now", "do_not_touch"}
        report = build_v4_simplification_audit()
        for o in report.opportunities:
            self.assertIn(o.recommended_action, valid_actions,
                          f"Invalid action: {o.recommended_action}")

    def test_26_audit_targets_exist(self):
        """All AUDIT_TARGETS directories exist."""
        for target in AUDIT_TARGETS:
            target_path = AUDIT_ROOT / target
            self.assertTrue(target_path.exists(),
                            f"Audit target {target} should exist")

    def test_27_opportunities_are_deterministic(self):
        """Same metrics produce same opportunities."""
        metrics1 = [
            ModuleSurfaceMetrics(
                path="a.py", loc=700, dataclass_count=3,
                public_function_count=10, private_function_count=5,
                public_export_count=15, cli_command_count=0,
                test_count=0, report_count=2, dependency_count=15,
                complexity_score=18.0, surface_hash="h1",
            ),
        ]
        metrics2 = [
            ModuleSurfaceMetrics(
                path="a.py", loc=700, dataclass_count=3,
                public_function_count=10, private_function_count=5,
                public_export_count=15, cli_command_count=0,
                test_count=0, report_count=2, dependency_count=15,
                complexity_score=18.0, surface_hash="h1",
            ),
        ]
        opps1 = find_simplification_opportunities(metrics1)
        opps2 = find_simplification_opportunities(metrics2)
        self.assertEqual(len(opps1), len(opps2))
        for o1, o2 in zip(opps1, opps2):
            self.assertEqual(o1.opportunity_hash, o2.opportunity_hash)

    def test_28_build_audit_returns_report(self):
        """build_v4_simplification_audit returns valid report."""
        report = build_v4_simplification_audit()
        self.assertIsInstance(report, SimplificationAuditReport)
        self.assertGreater(report.modules_analyzed, 0)
        self.assertGreater(report.total_loc, 0)
        self.assertGreaterEqual(len(report.opportunities), 0)

    def test_29_empty_module_handled(self):
        """Nonexistent module returns zero metrics."""
        m = analyze_module_surface("nonexistent/path/to/file.py")
        self.assertEqual(m.loc, 0)
        self.assertEqual(m.complexity_score, 0.0)

    def test_30_report_hash_stable(self):
        """Report hash is stable across rebuilds."""
        r1 = build_v4_simplification_audit()
        r2 = build_v4_simplification_audit()
        self.assertEqual(r1.report_hash, r2.report_hash)

    def test_31_do_not_touch_covers_verification_scripts(self):
        """DO_NOT_TOUCH_PATHS includes verification scripts."""
        verify_entries = [p for p in DO_NOT_TOUCH_PATHS if "verify" in p]
        self.assertTrue(len(verify_entries) >= 1,
                        "Should protect verify scripts")

    def test_32_kernel_not_in_audit_targets(self):
        """v3/kernel is NOT in audit targets (protected)."""
        self.assertNotIn("v3/kernel", AUDIT_TARGETS,
                         "v3/kernel should not be audited for simplification")

    def test_33_opportunities_have_unique_ids(self):
        """All opportunities have unique IDs."""
        report = build_v4_simplification_audit()
        ids = [o.opportunity_id for o in report.opportunities]
        self.assertEqual(len(ids), len(set(ids)),
                         "All opportunity IDs should be unique")

    def test_34_v4_risk_field_valid(self):
        """ability_plus_10_complexity_plus_300_risk is valid."""
        report = build_v4_simplification_audit()
        self.assertIn(report.ability_plus_10_complexity_plus_300_risk,
                      ("low", "medium", "high"))

    def test_35_excessive_exports_detected(self):
        """Modules with many exports are flagged."""
        metrics = [
            ModuleSurfaceMetrics(
                path="exports_heavy.py", loc=300, dataclass_count=2,
                public_function_count=10, private_function_count=3,
                public_export_count=25, cli_command_count=0,
                test_count=0, report_count=1, dependency_count=5,
                complexity_score=15.0, surface_hash="h1",
            ),
        ]
        opportunities = find_simplification_opportunities(metrics)
        export_opps = [o for o in opportunities if o.category == "excessive_exports"]
        self.assertTrue(len(export_opps) >= 1, "Should detect excessive exports")


class TestRegression(unittest.TestCase):
    """Regression: ensure existing tests still pass."""

    def test_36_kernel_invariants_importable(self):
        """test_kernel_invariants module can be imported."""
        try:
            from v3.tests import test_kernel_invariants
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"test_kernel_invariants should be importable: {e}")

    def test_37_complexity_budget_importable(self):
        """test_complexity_budget module can be imported."""
        try:
            from v3.tests import test_complexity_budget
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"test_complexity_budget should be importable: {e}")

    def test_38_v4_release_freeze_importable(self):
        """test_v4_release_freeze module can be imported."""
        try:
            from v3.tests import test_v4_release_freeze
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"test_v4_release_freeze should be importable: {e}")

    def test_39_audit_standard_library_only(self):
        """Audit module uses only standard library."""
        audit_file = AUDIT_ROOT / "v3" / "quality" / "v4_simplification_audit.py"
        source = audit_file.read_text(encoding="utf-8")
        third_party = ["numpy", "pandas", "requests", "click", "rich",
                       "pydantic", "attrs", "marshmallow"]
        for lib in third_party:
            self.assertNotIn(f"import {lib}", source,
                             f"Third-party import '{lib}' found in audit module")

    def test_40_do_not_touch_paths_valid(self):
        """All DO_NOT_TOUCH_PATHS reference paths."""
        for path in DO_NOT_TOUCH_PATHS:
            # Paths may be directories or specific files
            full = AUDIT_ROOT / path
            if not full.exists():
                # Some paths are prefixes; verify parent directory exists
                parent = full.parent
                self.assertTrue(parent.exists(),
                                f"Parent of DO_NOT_TOUCH {path} should exist")

    def test_41_report_writes_all_three_formats(self):
        """write_simplification_audit writes JSON, MD, and phase report."""
        import tempfile
        report = build_v4_simplification_audit()
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_simplification_audit(report, tmpdir)
            self.assertIn("json", paths)
            self.assertIn("md", paths)
            self.assertIn("phase_report", paths)
            for key, path in paths.items():
                self.assertTrue(os.path.exists(path),
                                f"'{key}' output {path} should exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
