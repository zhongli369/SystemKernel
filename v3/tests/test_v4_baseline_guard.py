"""
v4.0 Baseline Guard Tests — Phase 0.

19 tests verifying the v4 baseline guard protects v3.0 kernel integrity.
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
KERNEL_DIR = os.path.join(V3_ROOT, "kernel")
RELEASE_DIR = os.path.join(V3_ROOT, "release")
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")
DOCS_DIR = os.path.join(ROOT, "Docs")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable


def _json_read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _run_module(module_path, *args):
    result = subprocess.run(
        [PYTHON, module_path] + list(args),
        capture_output=True, text=True, timeout=120,
        cwd=ROOT,
    )
    return result.returncode, result.stdout, result.stderr


def _run_test_suite(relative_path):
    return _run_module(os.path.join(ROOT, relative_path))


class TestV4BaselineGuard(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.guard_path = os.path.join(RELEASE_DIR, "v4_baseline_guard.py")
        cls.roadmap_path = os.path.join(DOCS_DIR, "V4_ROADMAP.md")
        cls.invariants_path = os.path.join(DOCS_DIR, "V4_INVARIANTS.md")
        cls.report_path = os.path.join(EXPORTS_DIR, "v4_baseline_guard_report.json")

    # ── Test 1: BaselineGuardResult dataclass ──────────────────────────

    def test_01_dataclass_creation(self):
        """BaselineGuardResult can be created and serialized."""
        from v3.release.v4_baseline_guard import BaselineGuardResult

        result = BaselineGuardResult(
            timestamp="2026-05-26T00:00:00Z",
            invariants_passed=10,
            invariants_failed=0,
            overall_pass=True,
        )
        d = result.to_dict()
        self.assertEqual(d["summary"]["invariants_passed"], 10)
        self.assertEqual(d["summary"]["invariants_failed"], 0)
        self.assertTrue(d["summary"]["overall_pass"])

        json_str = result.to_json()
        self.assertIn('"invariants_passed": 10', json_str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["baseline_commit"][:8], "13f2069c")

    # ── Test 2: build_v4_baseline_guard constructs successfully ────────

    def test_02_build_guard_constructs(self):
        """build_v4_baseline_guard() returns a valid result."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        result = build_v4_baseline_guard(ROOT)
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "overall_pass"))
        self.assertTrue(hasattr(result, "invariants_passed"))
        self.assertTrue(hasattr(result, "invariants_failed"))
        self.assertGreaterEqual(result.invariants_passed, 0)
        self.assertLessEqual(result.invariants_passed, 10)

    # ── Test 3: Kernel immutability check ──────────────────────────────

    def test_03_kernel_immutability(self):
        """All kernel files match baseline hashes."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        result = build_v4_baseline_guard(ROOT)
        self.assertTrue(
            result.kernel_immutability_pass,
            f"Kernel modified files: {result.kernel_modified_files}"
        )
        self.assertEqual(result.kernel_files_modified, 0)
        self.assertGreater(result.kernel_files_checked, 0)

    # ── Test 4: Kernel LLM-free ────────────────────────────────────────

    def test_04_kernel_llm_free(self):
        """No LLM imports in kernel directory."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        result = build_v4_baseline_guard(ROOT)
        self.assertTrue(
            result.kernel_llm_free_pass,
            f"LLM imports in kernel: {result.kernel_llm_imports}"
        )
        self.assertEqual(result.kernel_llm_imports_found, 0)

    # ── Test 5: Protected paths integrity ──────────────────────────────

    def test_05_protected_paths(self):
        """Protected paths match baseline (excluding v4_baseline_guard.py itself)."""
        from v3.release.v4_baseline_guard import check_protected_paths

        check = check_protected_paths(ROOT)
        # Allow v4_baseline_guard.py itself as it's the Phase 0 deliverable
        non_guard_mods = [
            f for f in check["modified_files"]
            if "v4_baseline_guard.py" not in f
        ]
        self.assertEqual(
            len(non_guard_mods), 0,
            f"Protected paths modified (excluding guard): {non_guard_mods}"
        )

    # ── Test 6: Forbidden dependencies clean ───────────────────────────

    def test_06_forbidden_deps_clean(self):
        """No forbidden dependencies in codebase (excluding v4/ if exists)."""
        from v3.release.v4_baseline_guard import check_forbidden_dependencies

        check = check_forbidden_dependencies(ROOT)
        self.assertTrue(
            check["pass"],
            f"Forbidden imports: {check['imports']}"
        )
        self.assertEqual(check["imports_found"], 0)

    # ── Test 7: Adapter contract intact ────────────────────────────────

    def test_07_adapter_contract(self):
        """Adapter resolve() contract preserved."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        result = build_v4_baseline_guard(ROOT)
        self.assertTrue(
            result.adapter_contract_intact,
            result.adapter_contract_detail
        )

    # ── Test 8: Execution pipeline intact ──────────────────────────────

    def test_08_execution_pipeline(self):
        """Pipeline order and retry policy preserved."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        result = build_v4_baseline_guard(ROOT)
        self.assertTrue(
            result.execution_pipeline_intact,
            result.execution_pipeline_detail
        )

    # ── Test 9: EventBus routing table intact ──────────────────────────

    def test_09_eventbus_routing(self):
        """13 routing rules and required actions present."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        result = build_v4_baseline_guard(ROOT)
        self.assertTrue(
            result.eventbus_routing_intact,
            result.eventbus_routing_detail
        )

    # ── Test 10: Observability contract intact ─────────────────────────

    def test_10_observability_contract(self):
        """Write-only, append-only, zero LLM."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        result = build_v4_baseline_guard(ROOT)
        self.assertTrue(
            result.observability_contract_intact,
            result.observability_contract_detail
        )

    # ── Test 11: Baseline tag points to correct commit ─────────────────

    def test_11_baseline_tag(self):
        """Tag systemkernel-v3.0.0-baseline → 13f2069."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        result = build_v4_baseline_guard(ROOT)
        self.assertTrue(
            result.baseline_tag_intact,
            result.baseline_tag_detail
        )

    # ── Test 12: Report JSON written and valid ─────────────────────────

    def test_12_report_writing(self):
        """write_v4_baseline_guard_report produces valid JSON."""
        from v3.release.v4_baseline_guard import (
            build_v4_baseline_guard,
            write_v4_baseline_guard_report,
        )

        result = build_v4_baseline_guard(ROOT)
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            tmp_path = write_v4_baseline_guard_report(result, f.name)

        try:
            self.assertTrue(os.path.isfile(tmp_path))
            data = _json_read(tmp_path)
            required_keys = [
                "inv_01_kernel_immutability",
                "inv_02_memory_removability",
                "inv_03_kernel_llm_free",
                "inv_04_protected_paths",
                "inv_05_forbidden_deps",
                "inv_06_adapter_contract",
                "inv_07_execution_pipeline",
                "inv_08_eventbus_routing",
                "inv_09_observability_contract",
                "inv_10_baseline_tag",
                "summary",
            ]
            for key in required_keys:
                self.assertIn(key, data, f"Missing report key: {key}")
            self.assertIn("overall_pass", data["summary"])
        finally:
            os.unlink(tmp_path)

    # ── Test 13: CLI --dry-run exits 0 ─────────────────────────────────

    def test_13_cli_dry_run(self):
        """--dry-run prints report and exits 0."""
        rc, stdout, stderr = _run_module(self.guard_path, "--dry-run")
        self.assertEqual(rc, 0, f"CLI --dry-run failed:\n{stderr[:1000]}")
        self.assertIn("Baseline Guard Report", stdout)
        self.assertIn("INV-01", stdout)
        self.assertIn("INV-10", stdout)

    # ── Test 14: CLI --verify exits 0 and writes report ────────────────

    def test_14_cli_verify(self):
        """--verify exits 0 and writes report file."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as f:
            tmp_path = f.name

        try:
            rc, stdout, stderr = _run_module(
                self.guard_path, "--verify", "--output", tmp_path
            )
            self.assertEqual(rc, 0, f"CLI --verify failed:\n{stderr[:1000]}")
            self.assertTrue(os.path.isfile(tmp_path))
            data = _json_read(tmp_path)
            self.assertTrue(data["summary"]["overall_pass"])
        finally:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)

    # ── Test 15: V4_INVARIANTS.md has 10 invariants ────────────────────

    def test_15_invariants_doc(self):
        """V4_INVARIANTS.md exists and lists 10 invariants."""
        self.assertTrue(
            os.path.isfile(self.invariants_path),
            "V4_INVARIANTS.md missing"
        )
        with open(self.invariants_path, encoding="utf-8") as f:
            content = f.read()
        for i in range(1, 11):
            label = f"INV-{i:02d}"
            self.assertIn(label, content,
                          f"{label} missing from V4_INVARIANTS.md")

    # ── Test 16: V4_ROADMAP.md has 12 phases ───────────────────────────

    def test_16_roadmap_doc(self):
        """V4_ROADMAP.md exists and lists 12 phases."""
        self.assertTrue(
            os.path.isfile(self.roadmap_path),
            "V4_ROADMAP.md missing"
        )
        with open(self.roadmap_path, encoding="utf-8") as f:
            content = f.read()
        for i in range(0, 13):
            self.assertIn(f"Phase {i}", content,
                          f"Phase {i} missing from V4_ROADMAP.md")
        self.assertIn("Pluggable Intelligence Plane", content)

    # ── Test 17: Guard idempotency ─────────────────────────────────────

    def test_17_idempotency(self):
        """Same root → same overall_pass result."""
        from v3.release.v4_baseline_guard import build_v4_baseline_guard

        r1 = build_v4_baseline_guard(ROOT)
        r2 = build_v4_baseline_guard(ROOT)

        self.assertEqual(r1.overall_pass, r2.overall_pass)
        self.assertEqual(r1.invariants_passed, r2.invariants_passed)
        self.assertEqual(r1.invariants_failed, r2.invariants_failed)
        self.assertEqual(r1.kernel_files_modified, r2.kernel_files_modified)

    # ── Test 18: Forbidden deps catch violation (negative test) ────────

    def test_18_forbidden_deps_catches_violation(self):
        """Scanning a file with 'import openai' should detect it."""
        from v3.release.v4_baseline_guard import FORBIDDEN_DEPENDENCIES
        from v3.release.v4_baseline_guard import _scan_imports

        # Create a temp file with a forbidden import
        with tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write("import os\nimport openai\nfrom anthropic import Client\n")
            tmp_path = f.name

        try:
            violations = _scan_imports(tmp_path, FORBIDDEN_DEPENDENCIES)
            self.assertEqual(len(violations), 2,
                             f"Expected 2 violations, got {len(violations)}")
            import_names = [v["import"] for v in violations]
            self.assertIn("openai", import_names)
            self.assertIn("from anthropic import ...", import_names)
        finally:
            os.unlink(tmp_path)

    # ── Test 19: Report JSON schema complete ───────────────────────────

    def test_19_report_schema_complete(self):
        """Generated report has all required schema fields."""
        from v3.release.v4_baseline_guard import (
            build_v4_baseline_guard,
            write_v4_baseline_guard_report,
        )

        result = build_v4_baseline_guard(ROOT)
        d = result.to_dict()

        # Top-level keys
        for key in ("timestamp", "baseline_commit", "baseline_tag", "summary"):
            self.assertIn(key, d, f"Missing top-level key: {key}")

        # Each invariant section has 'pass' key
        for inv_key in [k for k in d if k.startswith("inv_")]:
            self.assertIn("pass", d[inv_key],
                          f"Missing 'pass' in {inv_key}")

        # Summary has required keys
        for key in ("invariants_passed", "invariants_failed", "overall_pass"):
            self.assertIn(key, d["summary"],
                          f"Missing summary key: {key}")

        # Baseline commit is correct
        self.assertTrue(d["baseline_commit"].startswith("13f2069"))


if __name__ == "__main__":
    unittest.main()
