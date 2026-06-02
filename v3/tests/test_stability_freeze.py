"""
Stability Freeze Tests — v4.1.

Verifies that the SystemKernel API surface, signal contracts, and injection
pipeline remain frozen. Detects architectural drift before it enters the
codebase.

Stdlib only — zero external test dependencies.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
RELEASE_DIR = os.path.join(V3_ROOT, "release")
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable


def _json_read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _run_module(module_path, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [PYTHON, "-X", "utf8", module_path] + list(args),
        capture_output=True, text=True, timeout=120,
        cwd=ROOT, env=env, encoding="utf-8",
    )
    return result.returncode, result.stdout, result.stderr


class TestStabilityFreeze(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.freeze_path = os.path.join(RELEASE_DIR, "stability_freeze.py")
        cls.api_path = os.path.join(ROOT, "api.py")
        cls.injector_path = os.path.join(EXTERNAL_DIR, "external_signal_injector.py")
        cls.registry_path = os.path.join(EXTERNAL_DIR, "default_capabilities.py")
        cls.report_path = os.path.join(EXPORTS_DIR, "stability_freeze_report.json")

    # ── Test 1: StabilityFreezeResult dataclass ─────────────────────────

    def test_01_dataclass_creation(self):
        """StabilityFreezeResult can be created and serialized."""
        from v3.release.stability_freeze import StabilityFreezeResult

        result = StabilityFreezeResult(
            timestamp="2026-05-28T00:00:00Z",
            version="4.1",
            invariants_passed=7,
            invariants_failed=0,
            overall_pass=True,
        )
        d = result.to_dict()
        self.assertEqual(d["summary"]["invariants_passed"], 7)
        self.assertEqual(d["summary"]["invariants_failed"], 0)
        self.assertTrue(d["summary"]["overall_pass"])

        json_str = result.to_json()
        self.assertIn('"invariants_passed": 7', json_str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["version"], "4.1")

    # ── Test 2: build_stability_freeze constructs successfully ──────────

    def test_02_build_constructs(self):
        """build_stability_freeze() returns a valid result."""
        from v3.release.stability_freeze import build_stability_freeze

        result = build_stability_freeze(ROOT)
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "overall_pass"))
        self.assertTrue(hasattr(result, "invariants_passed"))
        self.assertTrue(hasattr(result, "invariants_failed"))
        self.assertGreaterEqual(result.invariants_passed, 0)
        self.assertLessEqual(result.invariants_passed, 7)

    # ── Test 3: SF-01 API surface intact ────────────────────────────────

    def test_03_api_surface_intact(self):
        """All 8 frozen API functions present with correct parameters."""
        from v3.release.stability_freeze import build_stability_freeze

        result = build_stability_freeze(ROOT)
        self.assertTrue(
            result.api_surface_pass,
            f"API surface violations: missing={list(result.api_missing_functions)}, "
            f"extra={list(result.api_extra_functions)}, "
            f"signature={list(result.api_signature_violations)}"
        )
        self.assertEqual(result.api_missing_functions, ())
        self.assertEqual(result.api_extra_functions, ())
        self.assertEqual(result.api_signature_violations, ())
        self.assertEqual(result.api_functions_found, result.api_functions_expected)

    # ── Test 4: SF-02 Capability freeze ─────────────────────────────────

    def test_04_capability_freeze(self):
        """list_capabilities() is read-only, enabled-only, no internal leak."""
        from v3.release.stability_freeze import build_stability_freeze

        result = build_stability_freeze(ROOT)
        self.assertTrue(result.capability_freeze_pass, result.capability_detail)
        self.assertTrue(result.capability_read_only)
        self.assertTrue(result.capability_enabled_only)
        self.assertTrue(result.capability_no_internal_leak)

    # ── Test 5: SF-03 Signal contract frozen ────────────────────────────

    def test_05_signal_contract(self):
        """Direction (gstack, 0.4) + Quality (superpowers, 0.6) intact."""
        from v3.release.stability_freeze import build_stability_freeze

        result = build_stability_freeze(ROOT)
        self.assertTrue(
            result.signal_contract_pass,
            f"Weight violations: {list(result.signal_weight_violations)}"
        )
        self.assertEqual(result.signal_weight_violations, ())

    # ── Test 6: SF-04 Injection pipeline frozen ─────────────────────────

    def test_06_injection_pipeline(self):
        """5-step pipeline with complexity gate preserved."""
        from v3.release.stability_freeze import build_stability_freeze

        result = build_stability_freeze(ROOT)
        self.assertTrue(result.pipeline_freeze_pass)
        self.assertTrue(result.pipeline_complexity_gate_intact)
        self.assertGreaterEqual(len(result.pipeline_stages_found), 5)

    # ── Test 7: SF-05 Internal systems protected ────────────────────────

    def test_07_internal_protection(self):
        """No direct access to v3/kernel, v3/memory, EventBus, etc. from api.py."""
        from v3.release.stability_freeze import build_stability_freeze

        result = build_stability_freeze(ROOT)
        self.assertTrue(
            result.internal_protection_pass,
            f"Internal imports: {list(result.internal_imports_in_api)}, "
            f"exposures: {list(result.internal_subsystems_exposed)}"
        )
        self.assertEqual(result.internal_imports_in_api, ())
        self.assertEqual(result.internal_subsystems_exposed, ())

    # ── Test 8: SF-06 ECC rule enforced ─────────────────────────────────

    def test_08_ecc_rule(self):
        """ECC is execution-only, not exposed via API or registry."""
        from v3.release.stability_freeze import build_stability_freeze

        result = build_stability_freeze(ROOT)
        self.assertTrue(result.ecc_rule_pass, result.ecc_detail)
        self.assertFalse(result.ecc_in_api)
        self.assertFalse(result.ecc_in_registry)

    # ── Test 9: SF-07 Complexity guard ──────────────────────────────────

    def test_09_complexity_guard(self):
        """No new entry points, no circular deps between signal planes."""
        from v3.release.stability_freeze import build_stability_freeze

        result = build_stability_freeze(ROOT)
        self.assertTrue(
            result.complexity_guard_pass,
            f"Violations: {list(result.new_entry_points)}"
        )
        self.assertFalse(result.circular_deps_detected)
        self.assertEqual(result.new_entry_points, ())

    # ── Test 10: Report writing ─────────────────────────────────────────

    def test_10_report_writing(self):
        """write_stability_freeze_report produces valid JSON."""
        from v3.release.stability_freeze import (
            build_stability_freeze,
            write_stability_freeze_report,
        )

        result = build_stability_freeze(ROOT)
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            tmp_path = write_stability_freeze_report(result, f.name)

        try:
            self.assertTrue(os.path.isfile(tmp_path))
            data = _json_read(tmp_path)
            required_keys = [
                "sf_01_api_surface",
                "sf_02_capability_freeze",
                "sf_03_signal_contract",
                "sf_04_injection_pipeline",
                "sf_05_internal_protection",
                "sf_06_ecc_rule",
                "sf_07_complexity_guard",
                "summary",
            ]
            for key in required_keys:
                self.assertIn(key, data, f"Missing report key: {key}")
            self.assertIn("overall_pass", data["summary"])
            self.assertTrue(data["summary"]["overall_pass"])
        finally:
            os.unlink(tmp_path)

    # ── Test 11: CLI --dry-run exits 0 ──────────────────────────────────

    def test_11_cli_dry_run(self):
        """--dry-run prints report and exits 0."""
        rc, stdout, stderr = _run_module(self.freeze_path, "--dry-run")
        self.assertEqual(rc, 0, f"CLI --dry-run failed:\n{stderr[:1000]}")
        self.assertIn("Stability Freeze Report", stdout)
        self.assertIn("SF-01", stdout)
        self.assertIn("SF-07", stdout)
        self.assertIn("FROZEN", stdout)

    # ── Test 12: CLI --verify writes report ─────────────────────────────

    def test_12_cli_verify(self):
        """--verify exits 0 and writes report file."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as f:
            tmp_path = f.name

        try:
            rc, stdout, stderr = _run_module(
                self.freeze_path, "--verify", "--output", tmp_path
            )
            self.assertEqual(rc, 0, f"CLI --verify failed:\n{stderr[:1000]}")
            self.assertTrue(os.path.isfile(tmp_path))
            data = _json_read(tmp_path)
            self.assertTrue(data["summary"]["overall_pass"])
        finally:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)

    # ── Test 13: Idempotency ────────────────────────────────────────────

    def test_13_idempotency(self):
        """Same root → same overall_pass result."""
        from v3.release.stability_freeze import build_stability_freeze

        r1 = build_stability_freeze(ROOT)
        r2 = build_stability_freeze(ROOT)

        self.assertEqual(r1.overall_pass, r2.overall_pass)
        self.assertEqual(r1.invariants_passed, r2.invariants_passed)
        self.assertEqual(r1.invariants_failed, r2.invariants_failed)

    # ── Test 14: API surface detects extra functions ────────────────────

    def test_14_detects_extra_function(self):
        """An extra public function in api.py should fail SF-01."""
        from v3.release.stability_freeze import (
            _check_api_surface,
            StabilityFreezeResult,
        )

        # Create a temp api.py with an extra function
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_api = os.path.join(tmpdir, "api.py")
            with open(tmp_api, "w", encoding="utf-8") as f:
                f.write("""
def resolve_skill(intent, context):
    pass

def run_skill(skill_id, target):
    pass

def create_task_safe(*args, **kwargs):
    pass

def list_capabilities():
    pass

def query_external_signals(plane, **kwargs):
    pass

def analyze_direction(task_intent, project_context=""):
    pass

def analyze_quality(target_content, target_type="code"):
    pass

def inject_external_signals(task_intent="", project_context="", target_content="", target_type="code"):
    pass

def NEW_UNFROZEN_FUNCTION():    # This should be detected
    pass
""")
            result = _check_api_surface(tmpdir)
            self.assertFalse(result["pass"])
            self.assertIn("NEW_UNFROZEN_FUNCTION", result["extra"])

    # ── Test 15: Detects missing API function ───────────────────────────

    def test_15_detects_missing_function(self):
        """A missing API function should fail SF-01."""
        from v3.release.stability_freeze import _check_api_surface

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_api = os.path.join(tmpdir, "api.py")
            with open(tmp_api, "w", encoding="utf-8") as f:
                f.write("""
def resolve_skill(intent, context):
    pass

# Missing: run_skill, create_task_safe, etc.
""")
            result = _check_api_surface(tmpdir)
            self.assertFalse(result["pass"])
            self.assertGreater(len(result["missing"]), 0)

    # ── Test 16: Detects signature change ───────────────────────────────

    def test_16_detects_signature_change(self):
        """A renamed parameter should fail SF-01."""
        from v3.release.stability_freeze import _check_api_surface

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_api = os.path.join(tmpdir, "api.py")
            with open(tmp_api, "w", encoding="utf-8") as f:
                f.write("""
def resolve_skill(wrong_name, context):   # 'intent' renamed to 'wrong_name'
    pass

def run_skill(skill_id, target):
    pass

def create_task_safe(*args, **kwargs):
    pass

def list_capabilities():
    pass

def query_external_signals(plane, **kwargs):
    pass

def analyze_direction(task_intent, project_context=""):
    pass

def analyze_quality(target_content, target_type="code"):
    pass

def inject_external_signals(task_intent="", project_context="", target_content="", target_type="code"):
    pass
""")
            result = _check_api_surface(tmpdir)
            self.assertFalse(result["pass"])
            self.assertTrue(
                any("resolve_skill" in v for v in result["signature_violations"]),
                f"Expected signature violation for resolve_skill, got: {result['signature_violations']}"
            )

    # ── Test 17: ECC detection in API ───────────────────────────────────

    def test_17_detects_ecc_in_api(self):
        """ECC appearing in api.py as a functional export should fail SF-06."""
        from v3.release.stability_freeze import _check_ecc_rule

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_api = os.path.join(tmpdir, "api.py")
            with open(tmp_api, "w", encoding="utf-8") as f:
                f.write('''
def ecc_get_status():
    """ECC status — should NOT be here."""
    return {"status": "active"}

def resolve_skill(intent, context):
    pass
''')
            # Also need a default_capabilities.py to prevent false positive
            os.makedirs(os.path.join(tmpdir, "v3", "external"), exist_ok=True)
            cap_path = os.path.join(tmpdir, "v3", "external", "default_capabilities.py")
            with open(cap_path, "w", encoding="utf-8") as f:
                f.write("# no ECC references\n")

            result = _check_ecc_rule(tmpdir)
            self.assertFalse(result["pass"],
                           "ECC exposed as API function should fail SF-06")
            self.assertTrue(result["ecc_in_api"])

    # ── Test 18: Signal plane isolation verified ────────────────────────

    def test_18_signal_plane_isolation(self):
        """gstack adapter must not import superpowers, and vice versa."""
        gstack_path = os.path.join(EXTERNAL_DIR, "gstack_adapter.py")
        superpowers_path = os.path.join(EXTERNAL_DIR, "superpowers_adapter.py")

        if os.path.isfile(gstack_path):
            with open(gstack_path, encoding="utf-8") as f:
                gstack_source = f.read()
            self.assertNotIn(
                "superpowers", gstack_source.lower(),
                "gstack_adapter must not reference superpowers (circular dependency)"
            )

        if os.path.isfile(superpowers_path):
            with open(superpowers_path, encoding="utf-8") as f:
                superpowers_source = f.read()
            self.assertNotIn(
                "gstack", superpowers_source.lower(),
                "superpowers_adapter must not reference gstack (circular dependency)"
            )

    # ── Test 19: API only exposes allowed imports ───────────────────────

    def test_19_api_imports_whitelist(self):
        """api.py must not import from v3/kernel, v3/memory, v3/evals, v3/intake."""
        if not os.path.isfile(self.api_path):
            self.skipTest("api.py not found")

        with open(self.api_path, encoding="utf-8") as f:
            source = f.read()

        forbidden = ("v3.kernel", "v3.memory", "v3.evals", "v3.intake")
        for fb in forbidden:
            self.assertNotIn(
                f"from {fb}", source,
                f"api.py must not import from {fb}"
            )
            self.assertNotIn(
                f"import {fb}", source,
                f"api.py must not import from {fb}"
            )


class TestStabilityFreezeNoRegression(unittest.TestCase):
    """Verify stability freeze doesn't break existing test suites."""

    def test_baseline_guard_still_passes(self):
        """v4_baseline_guard must still pass."""
        guard_path = os.path.join(RELEASE_DIR, "v4_baseline_guard.py")
        rc, stdout, stderr = _run_module(guard_path, "--dry-run")
        self.assertEqual(rc, 0,
                       f"Baseline guard failed after stability freeze:\n{stderr[:1000]}")

    def test_capability_contract_tests_pass(self):
        """Phase 1 capability contract tests still pass."""
        test_path = os.path.join(V3_ROOT, "tests", "test_capability_contract.py")
        rc, stdout, stderr = _run_module(test_path)
        self.assertEqual(rc, 0,
                       f"Capability contract tests failed:\n{stderr[:1000]}")

    def test_capability_registry_tests_pass(self):
        """Phase 2 capability registry tests still pass."""
        test_path = os.path.join(V3_ROOT, "tests", "test_capability_registry.py")
        rc, stdout, stderr = _run_module(test_path)
        self.assertEqual(rc, 0,
                       f"Capability registry tests failed:\n{stderr[:1000]}")

    def test_external_evidence_tests_pass(self):
        """External evidence tests still pass."""
        test_path = os.path.join(V3_ROOT, "tests", "test_external_evidence.py")
        rc, stdout, stderr = _run_module(test_path)
        self.assertEqual(rc, 0,
                       f"External evidence tests failed:\n{stderr[:1000]}")

    def test_orchestration_policy_tests_pass(self):
        """Orchestration policy tests still pass."""
        test_path = os.path.join(V3_ROOT, "tests", "test_orchestration_policy.py")
        rc, stdout, stderr = _run_module(test_path)
        self.assertEqual(rc, 0,
                       f"Orchestration policy tests failed:\n{stderr[:1000]}")


if __name__ == "__main__":
    unittest.main()
