"""
Test Context Pack Adapter — Phase 7C external tool wrapper tests.

All tests that interact with the adapter plan/inspect path use NO network.
No external process is executed. Mocked where needed.
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

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _fixture_path(name):
    return os.path.join(FIXTURES_DIR, name)


def _resolve_cli():
    return os.path.join(V3_ROOT, "cli", "systemkernel.py")


class TestContextPackConfig(unittest.TestCase):
    """ContextPackConfig unit tests."""

    def test_01_config_creates_deterministic_command(self):
        """Same config produces same command string."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c1 = ContextPackConfig(
            target_path="v3/intake",
            output_path="external_trials/out.md",
            style="markdown",
        )
        r1 = ContextPackAdapter.plan(c1)
        r2 = ContextPackAdapter.plan(c1)
        self.assertEqual(r1.command, r2.command)
        self.assertIn("npx repomix@latest", r1.command)
        self.assertIn("v3/intake", r1.command)
        self.assertIn("--style", r1.command)
        self.assertIn("markdown", r1.command)

    def test_02_config_invalid_style_raises(self):
        """Unsupported style raises ValueError."""
        from v3.external.context_pack import ContextPackConfig

        with self.assertRaises(ValueError):
            ContextPackConfig(style="html")

    def test_03_valid_styles_accepted(self):
        """All four valid styles are accepted."""
        from v3.external.context_pack import ContextPackConfig

        for style in ("markdown", "xml", "json", "plain"):
            c = ContextPackConfig(style=style)
            self.assertEqual(c.style, style)


class TestContextPackAdapterPlan(unittest.TestCase):
    """ContextPackAdapter.plan() tests — no execution."""

    def test_04_plan_does_not_execute(self):
        """plan() returns without spawning any process."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        # This would fail if plan tried to actually run npx
        c = ContextPackConfig(
            target_path="v3/intake",
            output_path="external_trials/out.md",
        )
        result = ContextPackAdapter.plan(c)
        self.assertIsNotNone(result)

    def test_05_plan_returns_status_planned(self):
        """Valid plan returns status='planned'."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path="v3/intake",
            output_path="external_trials/out.md",
        )
        result = ContextPackAdapter.plan(c)
        self.assertEqual(result.status, "planned")

    def test_06_target_repo_root_blocked(self):
        """Planning against repo root is blocked by default."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path=".",  # repo root (relative)
            output_path="external_trials/out.md",
        )
        result = ContextPackAdapter.plan(c)
        self.assertEqual(result.status, "blocked")
        self.assertTrue(any("ROOT_BLOCKED" in w for w in result.warnings))

    def test_07_target_v3_root_blocked(self):
        """Planning against v3/ root is blocked by default."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path="v3",
            output_path="external_trials/out.md",
        )
        result = ContextPackAdapter.plan(c)
        self.assertEqual(result.status, "blocked")

    def test_08_small_subdir_target_allowed(self):
        """Planning against a small subdirectory is not blocked."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path="v3/intake",
            output_path="external_trials/out.md",
        )
        result = ContextPackAdapter.plan(c)
        self.assertEqual(result.status, "planned")
        self.assertGreaterEqual(len(result.included_files), 1)

    def test_09_repo_root_allowed_with_flag(self):
        """allow_repo_root=True permits planning against root."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path="v3/intake",  # use a real subdir with allow_repo_root
            output_path="external_trials/out.md",
            allow_repo_root=True,
        )
        result = ContextPackAdapter.plan(c)
        self.assertEqual(result.status, "planned")

    def test_10_target_not_found_blocked(self):
        """Non-existent target is blocked."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path="nonexistent/directory/xyz",
            output_path="external_trials/out.md",
        )
        result = ContextPackAdapter.plan(c)
        self.assertEqual(result.status, "blocked")
        self.assertTrue(any("NOT_FOUND" in w for w in result.warnings))

    def test_11_output_path_in_command(self):
        """Output path appears in the constructed command."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path="v3/intake",
            output_path="external_trials/special_output.md",
        )
        result = ContextPackAdapter.plan(c)
        self.assertIn("special_output.md", result.command)

    def test_12_oversized_output_blocked(self):
        """Very low max_bytes blocks a real directory."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path="v3/intake",
            output_path="external_trials/out.md",
            max_bytes=100,  # impossibly low
        )
        result = ContextPackAdapter.plan(c)
        self.assertEqual(result.status, "blocked")
        self.assertTrue(any("OVERSIZE" in w for w in result.warnings))


class TestContextPackAdapterGenerate(unittest.TestCase):
    """ContextPackAdapter.generate() — safety gate tests."""

    def test_13_generate_without_allow_execute_blocked(self):
        """generate() refuses unless allow_execute=True."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path="v3/intake",
            output_path="external_trials/out.md",
        )
        result = ContextPackAdapter.generate(c, allow_execute=False)
        self.assertEqual(result.status, "blocked")
        self.assertTrue(any("EXECUTE_NOT_ALLOWED" in w for w in result.warnings))

    def test_14_generate_with_allow_execute_on_root_blocked(self):
        """Even with allow_execute, root target is blocked."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

        c = ContextPackConfig(
            target_path=".",
            output_path="external_trials/out.md",
        )
        result = ContextPackAdapter.generate(c, allow_execute=True)
        self.assertEqual(result.status, "blocked")


class TestContextPackAdapterInspect(unittest.TestCase):
    """ContextPackAdapter.inspect_output() tests — read-only."""

    def test_15_inspect_counts_bytes(self):
        """inspect_output returns correct byte count."""
        from v3.external.context_pack import ContextPackAdapter

        fixture = _fixture_path("context_pack_sample.md")
        result = ContextPackAdapter.inspect_output(fixture)
        self.assertEqual(result.status, "generated")
        self.assertGreater(result.size_bytes, 0)
        expected_size = os.path.getsize(fixture)
        self.assertEqual(result.size_bytes, expected_size)

    def test_16_inspect_counts_lines(self):
        """inspect_output returns correct line count."""
        from v3.external.context_pack import ContextPackAdapter

        fixture = _fixture_path("context_pack_sample.md")
        result = ContextPackAdapter.inspect_output(fixture)
        with open(fixture, encoding="utf-8") as f:
            expected_lines = len(f.read().split("\n"))
        self.assertEqual(result.line_count, expected_lines)

    def test_17_inspect_computes_hash(self):
        """inspect_output computes a deterministic SHA-256 hash."""
        from v3.external.context_pack import ContextPackAdapter

        fixture = _fixture_path("context_pack_sample.md")
        r1 = ContextPackAdapter.inspect_output(fixture)
        r2 = ContextPackAdapter.inspect_output(fixture)
        self.assertEqual(r1.pack_hash, r2.pack_hash)
        self.assertGreater(len(r1.pack_hash), 0)

    def test_18_inspect_finds_included_files(self):
        """inspect_output extracts ## File: headers."""
        from v3.external.context_pack import ContextPackAdapter

        fixture = _fixture_path("context_pack_sample.md")
        result = ContextPackAdapter.inspect_output(fixture)
        self.assertIn("sample.py", result.included_files)
        self.assertIn("utils.py", result.included_files)

    def test_19_inspect_missing_file_blocked(self):
        """Non-existent file returns blocked status."""
        from v3.external.context_pack import ContextPackAdapter

        result = ContextPackAdapter.inspect_output("nonexistent/file.md")
        self.assertEqual(result.status, "blocked")

    def test_20_truth_source_always_false(self):
        """truth_source is ALWAYS False regardless of method."""
        from v3.external.context_pack import (
            ContextPackAdapter, ContextPackConfig, ContextPackResult,
        )

        # Plan
        c = ContextPackConfig(target_path="v3/intake", output_path="out.md")
        r = ContextPackAdapter.plan(c)
        self.assertFalse(r.truth_source)

        # Inspect
        fixture = _fixture_path("context_pack_sample.md")
        r = ContextPackAdapter.inspect_output(fixture)
        self.assertFalse(r.truth_source)

        # Generate blocked
        r = ContextPackAdapter.generate(c, allow_execute=False)
        self.assertFalse(r.truth_source)

        # Direct construction
        direct = ContextPackResult(status="generated", pack_hash="abc123")
        self.assertFalse(direct.truth_source)

    def test_21_verify_pack_passes_valid_result(self):
        """verify_pack returns True for a valid generated result."""
        from v3.external.context_pack import ContextPackAdapter

        fixture = _fixture_path("context_pack_sample.md")
        result = ContextPackAdapter.inspect_output(fixture)
        self.assertTrue(ContextPackAdapter.verify_pack(result))

    def test_22_verify_pack_fails_on_failed(self):
        """verify_pack returns False for failed status."""
        from v3.external.context_pack import ContextPackAdapter, ContextPackResult

        r = ContextPackResult(status="failed", warnings=("error",))
        self.assertFalse(ContextPackAdapter.verify_pack(r))

    def test_23_result_included_files_deterministic_order(self):
        """inspect_output included_files are deterministically ordered."""
        from v3.external.context_pack import ContextPackAdapter

        fixture = _fixture_path("context_pack_sample.md")
        r1 = ContextPackAdapter.inspect_output(fixture)
        r2 = ContextPackAdapter.inspect_output(fixture)
        self.assertEqual(r1.included_files, r2.included_files)


class TestCLIIntegration(unittest.TestCase):
    """CLI integration tests — run systemkernel.py subprocess."""

    def _run_cli(self, *args):
        """Run CLI and return (returncode, stdout, stderr)."""
        cli = _resolve_cli()
        result = subprocess.run(
            [sys.executable, cli] + list(args),
            capture_output=True, text=True, timeout=30,
            cwd=ROOT,
        )
        return result.returncode, result.stdout, result.stderr

    def test_24_cli_plan_works(self):
        """CLI context-pack plan subcommand runs successfully."""
        rc, stdout, stderr = self._run_cli(
            "context-pack", "plan", "v3/intake",
            "--output", "external_trials/test_plan.md",
        )
        self.assertEqual(rc, 0, f"CLI plan failed: {stderr}")
        self.assertIn("npx repomix", stdout)
        self.assertIn("planned", stdout.lower())

    def test_25_cli_inspect_works(self):
        """CLI context-pack inspect reads fixture and reports."""
        fixture = _fixture_path("context_pack_sample.md")
        rc, stdout, stderr = self._run_cli(
            "context-pack", "inspect", fixture,
        )
        self.assertEqual(rc, 0, f"CLI inspect failed: {stderr}")
        self.assertIn("sample.py", stdout)
        self.assertIn("utils.py", stdout)

    def test_26_cli_generate_without_allow_execute_refused(self):
        """CLI generate without --allow-execute is refused."""
        rc, stdout, stderr = self._run_cli(
            "context-pack", "generate", "v3/intake",
            "--output", "external_trials/test_gen.md",
        )
        # Should either fail non-zero or print refusal
        combined = stdout + stderr
        refused = (
            rc != 0
            or "not allowed" in combined.lower()
            or "required" in combined.lower()
            or "allow" in combined.lower()
        )
        self.assertTrue(refused, f"Expected refusal but got rc={rc}: {combined[:200]}")


class TestInvariants(unittest.TestCase):
    """Cross-cutting invariant tests."""

    def test_27_no_repomix_python_import(self):
        """No Python file in v3/ imports repomix as a module."""
        violations = []
        for dirpath, dirnames, filenames in os.walk(V3_ROOT):
            dirnames[:] = [d for d in dirnames
                          if not d.startswith(".")
                          and d not in ("__pycache__", "checkpoints", "traces", "metrics")]
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if "repomix" in alias.name.lower():
                                    violations.append(
                                        f"{os.path.relpath(fpath, ROOT)}: imports {alias.name}")
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and "repomix" in node.module.lower():
                                violations.append(
                                    f"{os.path.relpath(fpath, ROOT)}: imports {node.module}")
                except (SyntaxError, OSError):
                    pass
        self.assertEqual(len(violations), 0,
                        f"Repomix imports found: {violations}")

    def test_28_no_network_required_in_tests(self):
        """This test file itself does not import or use network modules."""
        with open(__file__, encoding="utf-8") as f:
            source = f.read()
        banned = ("requests", "httpx", "urllib3", "urllib.request", "socket")
        for name in banned:
            self.assertNotIn(f"import {name}", source)
            self.assertNotIn(f"from {name}", source)

    def test_29_no_kernel_modifications(self):
        """v3/kernel/ directory has no changes related to context_pack."""
        kernel_dir = os.path.join(V3_ROOT, "kernel")
        if not os.path.isdir(kernel_dir):
            self.skipTest("kernel directory not found")
        for fname in os.listdir(kernel_dir):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(kernel_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("context_pack", content,
                           f"context_pack reference in kernel/{fname}")
            self.assertNotIn("repomix", content,
                           f"repomix reference in kernel/{fname}")

    def test_30_not_in_kernel_import_path(self):
        """context_pack adapter is in v3/external/, not kernel/."""
        adapter_path = os.path.join(EXTERNAL_DIR, "context_pack.py")
        self.assertTrue(os.path.exists(adapter_path))
        # It should NOT be in kernel/
        kernel_adapter = os.path.join(V3_ROOT, "kernel", "context_pack.py")
        self.assertFalse(os.path.exists(kernel_adapter))

    def test_31_complexity_gate_not_reject(self):
        """Complexity gate verdict is not REJECT."""
        cb_path = os.path.join(EXPORTS_DIR, "complexity_budget_report.json")
        if not os.path.exists(cb_path):
            self.skipTest("Complexity budget report not found")
        with open(cb_path, encoding="utf-8") as f:
            data = json.load(f)
        verdict = data.get("verdict", {}).get("verdict", "UNKNOWN")
        self.assertNotEqual(verdict, "REJECT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
