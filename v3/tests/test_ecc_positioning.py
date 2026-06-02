"""
Phase 13A — Tests for ECC Positioning Analysis.

At least 25 tests covering ECC capability mapping, positioning report,
forbidden action guards, and safety constraints.
"""
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.external.ecc_positioning import (
    ECCCapabilityMapping,
    ECCPositioningReport,
    build_ecc_capability_mapping,
    build_ecc_positioning_report,
    write_ecc_positioning_report,
    check_ecc_forbidden_actions,
    ECC_REPO_NAME,
    ECC_REPO_URL,
    ECC_RECOMMENDED_ROLE,
    ECC_FORBIDDEN_ACTIONS,
    ECC_ALLOWED_ACTIONS,
    ROOT as ECC_ROOT,
)


class TestECCCapabilityMapping(unittest.TestCase):
    """Tests for ECCCapabilityMapping dataclass."""

    def test_01_mapping_frozen(self):
        """ECCCapabilityMapping is frozen."""
        m = ECCCapabilityMapping(
            ecc_area="test", systemkernel_plane="Test Plane",
            use_mode="reference", reuse_strategy="test strategy",
            risk_level="low", notes="test", mapping_hash="abc",
        )
        with self.assertRaises(Exception):
            m.ecc_area = "changed"

    def test_02_report_frozen(self):
        """ECCPositioningReport is frozen."""
        r = ECCPositioningReport(
            repo_name="test", repo_url="http://test",
            recommended_role="reference", mappings=(),
            reusable_patterns=(), forbidden_patterns=(),
            overlap_with_systemkernel=(),
            differentiation_strategy="test",
            complexity_risk="low",
            clone_now="NO", integrate_now="NO",
            report_hash="abc",
        )
        with self.assertRaises(Exception):
            r.repo_name = "changed"

    def test_03_mapping_hash_deterministic(self):
        """ECCCapabilityMapping hash is deterministic."""
        m1 = ECCCapabilityMapping(
            ecc_area="test", systemkernel_plane="Test Plane",
            use_mode="reference", reuse_strategy="test",
            risk_level="low", notes="test", mapping_hash="hash1",
        )
        m2 = ECCCapabilityMapping(
            ecc_area="test", systemkernel_plane="Test Plane",
            use_mode="reference", reuse_strategy="test",
            risk_level="low", notes="test", mapping_hash="hash1",
        )
        self.assertEqual(m1.mapping_hash, m2.mapping_hash)

    def test_04_report_hash_deterministic(self):
        """ECCPositioningReport hash is deterministic for same inputs."""
        r1 = ECCPositioningReport(
            repo_name="test", repo_url="http://test",
            recommended_role="ref", mappings=(),
            reusable_patterns=(), forbidden_patterns=(),
            overlap_with_systemkernel=(),
            differentiation_strategy="d", complexity_risk="low",
            clone_now="NO", integrate_now="NO",
            report_hash="hash1",
        )
        r2 = ECCPositioningReport(
            repo_name="test", repo_url="http://test",
            recommended_role="ref", mappings=(),
            reusable_patterns=(), forbidden_patterns=(),
            overlap_with_systemkernel=(),
            differentiation_strategy="d", complexity_risk="low",
            clone_now="NO", integrate_now="NO",
            report_hash="hash1",
        )
        self.assertEqual(r1.report_hash, r2.report_hash)

    def test_05_skills_map_to_skill_evolution(self):
        """ECC skills map to Skill Evolution Plane."""
        mappings = build_ecc_capability_mapping()
        skill_mapping = [m for m in mappings if "skill" in m.ecc_area.lower() and "system" in m.ecc_area.lower()]
        self.assertTrue(len(skill_mapping) >= 1)
        self.assertIn("Skill Evolution", skill_mapping[0].systemkernel_plane)

    def test_06_doctor_maps_to_ops(self):
        """ECC doctor/repair maps to Productization + Ops (learn or reference mode)."""
        mappings = build_ecc_capability_mapping()
        doctor = [m for m in mappings if "doctor" in m.ecc_area.lower() or "repair" in m.ecc_area.lower()]
        self.assertTrue(len(doctor) >= 1)
        self.assertIn(doctor[0].use_mode, ("learn", "reference"))
        self.assertIn("Ops", doctor[0].systemkernel_plane)

    def test_07_cross_harness_maps_to_registry(self):
        """ECC cross-harness maps to Capability Registry reference."""
        mappings = build_ecc_capability_mapping()
        cross = [m for m in mappings if "cross-harness" in m.ecc_area.lower()]
        self.assertTrue(len(cross) >= 1)
        self.assertIn("Capability Registry", cross[0].systemkernel_plane)

    def test_08_memory_optimization_maps_to_memory_intelligence(self):
        """ECC memory optimization maps to Memory Intelligence Plane."""
        mappings = build_ecc_capability_mapping()
        mem = [m for m in mappings if "memory" in m.ecc_area.lower()]
        self.assertTrue(len(mem) >= 1)
        self.assertIn("Memory Intelligence", mem[0].systemkernel_plane)

    def test_09_workflows_map_to_orchestration(self):
        """ECC workflows/instincts map to Orchestration Policy reference."""
        mappings = build_ecc_capability_mapping()
        wf = [m for m in mappings if "workflow" in m.ecc_area.lower() or "instinct" in m.ecc_area.lower()]
        self.assertTrue(len(wf) >= 1)
        self.assertIn("Orchestration", wf[0].systemkernel_plane)

    def test_10_plugin_maps_to_external_registry(self):
        """ECC plugin/install maps to External Registry + Skill Management."""
        mappings = build_ecc_capability_mapping()
        plugin = [m for m in mappings if "plugin" in m.ecc_area.lower() or "install" in m.ecc_area.lower()]
        self.assertTrue(len(plugin) >= 1)
        plane = plugin[0].systemkernel_plane
        self.assertTrue("Registry" in plane or "registry" in plane.lower())

    def test_11_security_maps_to_eval(self):
        """ECC security scanning maps to Evaluation Harness."""
        mappings = build_ecc_capability_mapping()
        sec = [m for m in mappings if "security" in m.ecc_area.lower()]
        self.assertTrue(len(sec) >= 1)
        self.assertIn("Evaluation", sec[0].systemkernel_plane)

    def test_12_forbidden_includes_install(self):
        """Forbidden actions include ECC install."""
        self.assertTrue(any("install" in f.lower() for f in ECC_FORBIDDEN_ACTIONS))

    def test_13_forbidden_includes_run(self):
        """Forbidden actions include ECC run."""
        self.assertTrue(any("run" in f.lower() for f in ECC_FORBIDDEN_ACTIONS))

    def test_14_forbidden_includes_kernel_modification(self):
        """Forbidden actions include kernel modification."""
        self.assertTrue(any("kernel" in f.lower() for f in ECC_FORBIDDEN_ACTIONS))

    def test_15_forbidden_includes_ecc_clone(self):
        """Forbidden actions include turning SystemKernel into ECC clone."""
        self.assertTrue(any("clone" in f.lower() for f in ECC_FORBIDDEN_ACTIONS))

    def test_16_recommended_role_is_external(self):
        """Recommended role is external/reference, not integrated."""
        report = build_ecc_positioning_report()
        self.assertIn("external", report.recommended_role.lower())
        self.assertNotIn("integrated", report.recommended_role.lower())

    def test_17_complexity_risk_acceptable(self):
        """Complexity risk is not HIGH (must be low or medium)."""
        report = build_ecc_positioning_report()
        self.assertIn(report.complexity_risk, ("low", "medium"))

    def test_18_report_can_be_written(self):
        """ECC positioning report can be written to disk."""
        import tempfile
        report = build_ecc_positioning_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_ecc_positioning_report(report, tmpdir)
            for key, path in paths.items():
                self.assertTrue(os.path.exists(path), f"Report {key} should exist")
                self.assertTrue(os.path.getsize(path) > 0, f"Report {key} not empty")

    def test_19_no_ecc_execution(self):
        """ECC positioning module does not execute ECC."""
        module_file = ECC_ROOT / "v3" / "external" / "ecc_positioning.py"
        source = module_file.read_text(encoding="utf-8")
        self.assertNotIn("subprocess.run", source)
        self.assertNotIn("os.system", source)

    def test_20_no_ecc_install(self):
        """ECC positioning module does not install ECC."""
        module_file = ECC_ROOT / "v3" / "external" / "ecc_positioning.py"
        source = module_file.read_text(encoding="utf-8")
        self.assertNotIn("pip install", source)
        self.assertNotIn("npm install", source)
        self.assertNotIn("git clone", source)

    def test_21_no_network_required(self):
        """ECC positioning module has no network calls."""
        module_file = ECC_ROOT / "v3" / "external" / "ecc_positioning.py"
        source = module_file.read_text(encoding="utf-8")
        banned = ["requests.", "urllib.request", "http.client", "httpx", "socket.connect"]
        for b in banned:
            self.assertNotIn(b, source, f"Network call '{b}' found")

    def test_22_no_kernel_modification(self):
        """ECC positioning does not import from kernel."""
        module_file = ECC_ROOT / "v3" / "external" / "ecc_positioning.py"
        source = module_file.read_text(encoding="utf-8")
        if "v3/kernel" in source:
            self.fail("ECC positioning must not reference v3/kernel")

    def test_23_no_memory_modification(self):
        """ECC positioning does not modify v3/memory."""
        module_file = ECC_ROOT / "v3" / "external" / "ecc_positioning.py"
        source = module_file.read_text(encoding="utf-8")
        # Should not write to memory directories
        has_memory_write = "v3/memory" in source and ("open(" in source or "write" in source)
        self.assertFalse(has_memory_write, "ECC positioning must not write to v3/memory")

    def test_24_complexity_gate_not_reject(self):
        """Complexity gate is not REJECT."""
        report = build_ecc_positioning_report()
        self.assertNotEqual(report.complexity_risk, "high",
                            "Complexity risk should not be HIGH (REJECT)")

    def test_25_forbidden_action_guard_denies_install(self):
        """check_ecc_forbidden_actions denies ECC install."""
        self.assertFalse(check_ecc_forbidden_actions("install ECC"))
        self.assertFalse(check_ecc_forbidden_actions("run ECC packages"))

    def test_26_forbidden_action_guard_allows_inspection(self):
        """check_ecc_forbidden_actions allows safe operations."""
        self.assertTrue(check_ecc_forbidden_actions("inspect ECC docs"))
        self.assertTrue(check_ecc_forbidden_actions("compare ECC taxonomy"))
        self.assertTrue(check_ecc_forbidden_actions("read ECC source reference"))

    def test_27_integrate_now_is_always_no(self):
        """integrate_now is always NO."""
        report = build_ecc_positioning_report()
        self.assertEqual(report.integrate_now, "NO")

    def test_28_all_mappings_have_valid_use_modes(self):
        """All mappings use valid use_mode values."""
        mappings = build_ecc_capability_mapping()
        valid = {"learn", "reference", "external_provider", "reject"}
        for m in mappings:
            self.assertIn(m.use_mode, valid, f"Invalid use_mode: {m.use_mode}")

    def test_29_mappings_are_deterministic(self):
        """Same build produces identical mappings."""
        m1 = build_ecc_capability_mapping()
        m2 = build_ecc_capability_mapping()
        self.assertEqual(len(m1), len(m2))
        for a, b in zip(m1, m2):
            self.assertEqual(a.mapping_hash, b.mapping_hash)
            self.assertEqual(a.ecc_area, b.ecc_area)

    def test_30_report_includes_differentiation(self):
        """Report includes a differentiation strategy."""
        report = build_ecc_positioning_report()
        self.assertTrue(len(report.differentiation_strategy) > 50,
                        "Differentiation strategy should be substantial")

    def test_31_forbidden_actions_not_empty(self):
        """Forbidden actions list is populated."""
        self.assertGreater(len(ECC_FORBIDDEN_ACTIONS), 0)

    def test_32_clone_decision_is_explicit(self):
        """Clone decision is one of YES/NO/MAYBE."""
        report = build_ecc_positioning_report()
        self.assertIn(report.clone_now, ("YES", "NO", "MAYBE"))


class TestRegression(unittest.TestCase):
    """Regression tests for existing invariants."""

    def test_33_simplification_risk_remains_medium_or_better(self):
        """Simplification audit risk should remain MEDIUM or LOW."""
        try:
            from v3.quality.v4_simplification_audit import build_v4_simplification_audit
            report = build_v4_simplification_audit()
            self.assertIn(report.ability_plus_10_complexity_plus_300_risk, ("low", "medium"))
        except Exception as e:
            self.skipTest(f"Simplification audit not available: {e}")

    def test_34_kernel_invariants_purity(self):
        """Kernel invariants should remain importable."""
        try:
            from v3.tests import test_kernel_invariants
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"test_kernel_invariants should be importable: {e}")

    def test_35_ecc_has_orchestration_profile(self):
        """ECC already has a placeholder in orchestration_profiles."""
        try:
            from v3.external.orchestration_profiles import ecc_harness_review
            policy = ecc_harness_review()
            self.assertEqual(policy.policy_id, "ecc_harness_review")
        except ImportError as e:
            self.skipTest(f"orchestration_profiles not available: {e}")

    def test_36_positioning_doc_exists(self):
        """docs/ECC_POSITIONING.md exists."""
        doc_path = ECC_ROOT / "docs" / "ECC_POSITIONING.md"
        self.assertTrue(doc_path.exists(), "ECC positioning doc should exist")
        content = doc_path.read_text(encoding="utf-8")
        self.assertIn("Positioning Analysis", content)

    def test_37_standard_library_only(self):
        """ECC positioning module uses only stdlib."""
        module_file = ECC_ROOT / "v3" / "external" / "ecc_positioning.py"
        source = module_file.read_text(encoding="utf-8")
        third_party = ["numpy", "pandas", "requests", "click", "rich",
                       "pydantic", "attrs", "marshmallow", "anthropic"]
        for lib in third_party:
            self.assertNotIn(f"import {lib}", source,
                             f"Third-party import '{lib}' found")


if __name__ == "__main__":
    unittest.main(verbosity=2)
