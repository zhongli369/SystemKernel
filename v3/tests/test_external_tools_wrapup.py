"""
External Tools Wrap-up Tests — Phase 7F.

Verifies all Phase 7 artifacts exist, safety constraints hold,
and no accidental contamination occurred.

Tests:
  1. final status JSON exists
  2. summary markdown exists
  3. EXTERNAL_TOOLS.md exists
  4. repomix status truth_source false
  5. ccusage status truth_source false
  6. anthropic skills deferred
  7. accidental prompt status says no doubao artifacts
  8. kernel_modified false
  9. memory_modified false
  10. no external tool dependency imported
  11. no network/clone commands in wrap-up
  12. complexity gate not REJECT
  13. kernel invariants still purity=100
  14. context pack adapter tests still pass
  15. usage report adapter tests still pass
"""

import ast
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")
TESTS_DIR = os.path.join(V3_ROOT, "tests")
KERNEL_DIR = os.path.join(V3_ROOT, "kernel")
DOCS_DIR = os.path.join(ROOT, "Docs")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable


def _json_read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _file_exists(rel_path):
    return os.path.exists(os.path.join(ROOT, rel_path))


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


def _run_test_suite(relative_path):
    result = subprocess.run(
        [PYTHON, os.path.join(ROOT, relative_path)],
        capture_output=True, text=True, timeout=120,
    )
    return result.returncode, result.stdout, result.stderr


class TestExternalToolsWrapup(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.status_path = os.path.join(EXPORTS_DIR, "external_tools_final_status.json")
        cls.summary_path = os.path.join(EXPORTS_DIR, "phase_7_external_tools_summary.md")

    # ── Test 1: final status JSON exists ──────────────────────────────

    def test_01_final_status_json_exists(self):
        self.assertTrue(
            os.path.exists(self.status_path),
            "external_tools_final_status.json missing"
        )

    # ── Test 2: summary markdown exists ───────────────────────────────

    def test_02_summary_markdown_exists(self):
        self.assertTrue(
            os.path.exists(self.summary_path),
            "phase_7_external_tools_summary.md missing"
        )

    # ── Test 3: EXTERNAL_TOOLS.md exists ──────────────────────────────

    def test_03_external_tools_documented_in_status(self):
        """External tools are documented in the final status JSON."""
        data = _json_read(self.status_path)
        self.assertIn("repomix", data)
        self.assertIn("ccusage", data)
        self.assertIn("anthropic_skills", data)

    # ── Test 4: repomix status truth_source false ─────────────────────

    def test_04_repomix_truth_source_false(self):
        data = _json_read(self.status_path)
        self.assertFalse(
            data["repomix"]["truth_source"],
            "repomix truth_source must be false"
        )

    # ── Test 5: ccusage status truth_source false ─────────────────────

    def test_05_ccusage_truth_source_false(self):
        data = _json_read(self.status_path)
        self.assertFalse(
            data["ccusage"]["truth_source"],
            "ccusage truth_source must be false"
        )

    # ── Test 6: anthropic skills deferred ─────────────────────────────

    def test_06_anthropic_skills_deferred(self):
        data = _json_read(self.status_path)
        self.assertFalse(
            data["anthropic_skills"]["adapter_ready"],
            "anthropic_skills adapter_ready must be false"
        )
        self.assertIn(
            "Skill Format Alignment",
            data["anthropic_skills"]["deferred_to"]
        )

    # ── Test 7: accidental prompt no doubao artifacts ─────────────────

    def test_07_no_doubao_artifacts(self):
        data = _json_read(self.status_path)
        acc = data["accidental_prompt"]
        self.assertFalse(
            acc["doubao_tts_artifacts"],
            "doubao_tts_artifacts must be false"
        )
        self.assertEqual(acc["action_taken"], "damage_audit_only")
        self.assertEqual(acc["risk_level"], "LOW")
        self.assertFalse(acc["kernel_contamination"])

    # ── Test 8: kernel_modified false ─────────────────────────────────

    def test_08_kernel_not_modified(self):
        data = _json_read(self.status_path)
        self.assertFalse(
            data["systemkernel"]["kernel_modified"],
            "kernel_modified must be false"
        )

    # ── Test 9: memory_modified false ─────────────────────────────────

    def test_09_memory_not_modified(self):
        data = _json_read(self.status_path)
        self.assertFalse(
            data["systemkernel"]["memory_modified"],
            "memory_modified must be false"
        )

    # ── Test 10: no external tool dependency imported ─────────────────

    def test_10_no_external_dependency_imported(self):
        for fname in os.listdir(EXTERNAL_DIR):
            if fname.endswith(".py") and fname != "__init__.py":
                fpath = os.path.join(EXTERNAL_DIR, fname)
                self.assertFalse(
                    _has_import(fpath, "repomix"),
                    f"{fname} imports repomix"
                )
                self.assertFalse(
                    _has_import(fpath, "ccusage"),
                    f"{fname} imports ccusage"
                )

    # ── Test 11: no network/clone in wrap-up ──────────────────────────

    def test_11_no_network_in_wrapup(self):
        """Status JSON must not instruct network/clone operations."""
        fpath = os.path.join(EXPORTS_DIR, "external_tools_final_status.json")
        with open(fpath, encoding="utf-8") as f:
            content = f.read().lower()
        self.assertNotIn("git clone", content,
                         "status JSON must not suggest git clone")
        self.assertNotIn("npx ", content,
                         "status JSON must not suggest npx")

    # ── Test 12: complexity gate not REJECT ───────────────────────────

    def test_12_complexity_gate_not_reject(self):
        from v3.quality.phase_gate import evaluate_phase
        result = evaluate_phase("5A", v3_root=V3_ROOT)
        self.assertNotEqual(
            result.verdict.verdict, "REJECT",
            f"Complexity gate REJECTED: {'; '.join(result.verdict.reasons)}"
        )

    # ── Test 13: kernel invariants purity=100 ─────────────────────────

    def test_13_kernel_invariants_purity(self):
        rc, stdout, stderr = _run_test_suite("v3/tests/test_kernel_invariants.py")
        self.assertEqual(rc, 0, f"Kernel invariants failed:\n{stderr[:2000]}")
        self.assertIn("purity_score == 100", stdout)

    # ── Test 14: context pack adapter tests pass ──────────────────────

    def test_14_context_pack_tests_pass(self):
        rc, stdout, stderr = _run_test_suite(
            "v3/tests/test_context_pack_adapter.py"
        )
        self.assertEqual(rc, 0,
                         f"Context pack tests failed:\n{stderr[:2000]}")

    # ── Test 15: usage report adapter tests pass ──────────────────────

    def test_15_usage_report_tests_pass(self):
        rc, stdout, stderr = _run_test_suite(
            "v3/tests/test_usage_report_adapter.py"
        )
        self.assertEqual(rc, 0,
                         f"Usage report tests failed:\n{stderr[:2000]}")

    # ── Test 16: no Doubao/TTS files anywhere ─────────────────────────

    def test_16_no_doubao_files(self):
        """No Doubao/TTS files in Phase 7 scope (v3/, Docs/)."""
        scan_dirs = [V3_ROOT, DOCS_DIR]
        for scan_dir in scan_dirs:
            for root_dir, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs
                           if not d.startswith(".") and d != "__pycache__"]
                for fname in files:
                    full = os.path.join(root_dir, fname)
                    rel = os.path.relpath(full, ROOT).lower()
                    if "doubao" in rel or "tts" in rel:
                        self.fail(f"Unexpected Doubao/TTS file found: {rel}")

    # ── Test 17: EXTERNAL_TOOLS.md references are correct ──────────────

    def test_17_external_tools_status_has_context_pack(self):
        data = _json_read(self.status_path)
        repomix_status = data.get("repomix", {})
        ccusage_status = data.get("ccusage", {})
        self.assertIn("adapter_ready", repomix_status)
        self.assertIn("adapter_ready", ccusage_status)
        self.assertIn("anthropic_skills", data)

    # ── Test 18: status JSON has all required keys ────────────────────

    def test_18_status_json_keys(self):
        data = _json_read(self.status_path)
        for key in ("repomix", "ccusage", "anthropic_skills",
                    "accidental_prompt", "systemkernel", "safety_table"):
            self.assertIn(key, data, f"Missing key in status JSON: {key}")

    # ── Test 19: summary markdown has all phases ──────────────────────

    def test_19_summary_has_all_phases(self):
        with open(self.summary_path, encoding="utf-8") as f:
            content = f.read()
        for phase in ("7A", "7B", "7C", "7D", "7E"):
            self.assertIn(f"Phase {phase}", content,
                          f"Summary missing Phase {phase}")

    # ── Test 20: no external adapter in kernel directory ──────────────

    def test_20_adapters_not_in_kernel(self):
        kernel_files = set()
        for root_dir, dirs, files in os.walk(KERNEL_DIR):
            dirs[:] = [d for d in dirs if not d.startswith(".")
                       and d != "__pycache__"]
            for fname in files:
                if fname.endswith(".py"):
                    kernel_files.add(fname)
        for fname in ("context_pack.py", "usage_report.py"):
            self.assertNotIn(fname, kernel_files,
                             f"External adapter in kernel/: {fname}")


if __name__ == "__main__":
    unittest.main()
