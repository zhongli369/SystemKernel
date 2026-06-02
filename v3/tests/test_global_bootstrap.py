"""
Tests for global SystemKernel bootstrap script.

Uses temp directories only. Does not touch real F:\Claude\ClaudeCodeProject.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BOOTSTRAP_SCRIPT = ROOT / "tools" / "bootstrap_claude_projects.ps1"
GLOBAL_USAGE_DOC = ROOT / "docs" / "SYSTEMKERNEL_GLOBAL_USAGE.md"
SECTION_MARKER = "## SystemKernel Governance"


def _run_bootstrap(root, mode, systemkernel_path=None):
    """Run the bootstrap script and return (rc, stdout, stderr)."""
    sk_path = systemkernel_path or str(ROOT)
    flag = "-DryRun" if mode == "dry-run" else "-Apply"
    report = os.path.join(root, "report.json")
    cmd = [
        "powershell", "-ExecutionPolicy", "Bypass",
        "-File", str(BOOTSTRAP_SCRIPT),
        "-Root", root,
        "-SystemKernelPath", sk_path,
        flag,
        "-ReportPath", report,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr, report


def _read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


class TestBootstrapExists(unittest.TestCase):
    """Tests for file existence."""

    def test_01_script_exists(self):
        """Bootstrap script exists."""
        self.assertTrue(BOOTSTRAP_SCRIPT.exists(),
                        f"Script not found: {BOOTSTRAP_SCRIPT}")

    def test_02_global_usage_doc_exists(self):
        """Global usage doc exists."""
        self.assertTrue(GLOBAL_USAGE_DOC.exists(),
                        f"Doc not found: {GLOBAL_USAGE_DOC}")


class TestDryRun(unittest.TestCase):
    """Tests for dry-run mode."""

    def test_03_dry_run_creates_no_files(self):
        """Dry-run must not create CLAUDE.md files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = os.path.join(tmpdir, "TestProject")
            os.makedirs(proj_dir)
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "dry-run")
            self.assertEqual(rc, 0, f"Script failed: {stderr}")
            self.assertFalse(os.path.exists(os.path.join(proj_dir, "CLAUDE.md")),
                             "Dry-run should not create CLAUDE.md")

    def test_04_dry_run_reports_correct_counts(self):
        """Dry-run report has correct counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "ProjA"))
            os.makedirs(os.path.join(tmpdir, "ProjB"))
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "dry-run")
            self.assertEqual(rc, 0)
            report = _read_json(report_path)
            self.assertTrue(report["dry_run"])
            self.assertFalse(report["apply"])
            self.assertEqual(report["scanned_count"], 2)
            self.assertEqual(report["create_count"], 2)
            self.assertEqual(report["update_count"], 0)


class TestApply(unittest.TestCase):
    """Tests for apply mode."""

    def test_05_apply_creates_claude_md_when_missing(self):
        """Apply creates CLAUDE.md in projects that lack it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "ProjA"))
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            claude_file = os.path.join(tmpdir, "ProjA", "CLAUDE.md")
            self.assertTrue(os.path.exists(claude_file))
            content = Path(claude_file).read_text(encoding="utf-8")
            self.assertIn(SECTION_MARKER, content)

    def test_06_apply_appends_section_to_existing_claude_md(self):
        """Apply appends section when CLAUDE.md exists without it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = os.path.join(tmpdir, "ProjA")
            os.makedirs(proj_dir)
            existing = "# My Project\n\nSome existing content.\n"
            claude_file = os.path.join(proj_dir, "CLAUDE.md")
            Path(claude_file).write_text(existing, encoding="utf-8")
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            content = Path(claude_file).read_text(encoding="utf-8")
            self.assertIn(SECTION_MARKER, content)
            self.assertIn("My Project", content)

    def test_07_apply_does_not_duplicate_section(self):
        """Apply does not append when section already present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = os.path.join(tmpdir, "ProjA")
            os.makedirs(proj_dir)
            existing = "# My Project\n\n" + SECTION_MARKER + "\n\nSome content.\n"
            claude_file = os.path.join(proj_dir, "CLAUDE.md")
            Path(claude_file).write_text(existing, encoding="utf-8")
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            content = Path(claude_file).read_text(encoding="utf-8")
            self.assertEqual(content.count(SECTION_MARKER), 1)
            report = _read_json(report_path)
            self.assertEqual(report["unchanged_count"], 1)

    def test_08_existing_content_preserved(self):
        """Original CLAUDE.md content is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = os.path.join(tmpdir, "ProjA")
            os.makedirs(proj_dir)
            original = "# My Project\n\n## Build\n\n```bash\nnpm run build\n```\n"
            claude_file = os.path.join(proj_dir, "CLAUDE.md")
            Path(claude_file).write_text(original, encoding="utf-8")
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            content = Path(claude_file).read_text(encoding="utf-8")
            self.assertIn("## Build", content)
            self.assertIn("npm run build", content)
            self.assertIn(SECTION_MARKER, content)
            self.assertTrue(content.index("## Build") < content.index(SECTION_MARKER))


class TestSkipDirectories(unittest.TestCase):
    """Tests for skip-directory logic."""

    def test_09_skipped_dirs_ignored(self):
        """Directories in skip list are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "ProjA"))
            os.makedirs(os.path.join(tmpdir, "node_modules"))
            os.makedirs(os.path.join(tmpdir, ".git"))
            os.makedirs(os.path.join(tmpdir, "dist"))
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            report = _read_json(report_path)
            self.assertEqual(report["scanned_count"], 1)
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "node_modules", "CLAUDE.md")))


class TestReporting(unittest.TestCase):
    """Tests for report generation."""

    def test_10_report_json_written(self):
        """Report JSON is written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "ProjA"))
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(report_path))
            report = _read_json(report_path)
            self.assertIn("actions", report)

    def test_11_report_counts_correct(self):
        """Report counts match actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "NewProj"))
            proj_dir = os.path.join(tmpdir, "ExistingProj")
            os.makedirs(proj_dir)
            Path(os.path.join(proj_dir, "CLAUDE.md")).write_text(
                "# Existing\n\n" + SECTION_MARKER + "\n", encoding="utf-8")
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            report = _read_json(report_path)
            self.assertEqual(report["create_count"], 1)
            self.assertEqual(report["unchanged_count"], 1)
            self.assertEqual(report["update_count"], 0)
            self.assertEqual(len(report["actions"]), report["scanned_count"])

    def test_12_only_claude_md_targeted(self):
        """No other files are created or modified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = os.path.join(tmpdir, "ProjA")
            os.makedirs(proj_dir)
            extra_file = os.path.join(proj_dir, "README.md")
            Path(extra_file).write_text("# README\n", encoding="utf-8")
            extra_mtime = os.path.getmtime(extra_file)
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            self.assertEqual(os.path.getmtime(extra_file), extra_mtime)
            files = os.listdir(proj_dir)
            self.assertIn("CLAUDE.md", files)
            self.assertIn("README.md", files)
            self.assertEqual(len(files), 2)


class TestSectionContent(unittest.TestCase):
    """Tests for governance section content."""

    def test_13_section_contains_systemkernel_path(self):
        """Section references SystemKernel path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "ProjA"))
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            content = Path(os.path.join(tmpdir, "ProjA", "CLAUDE.md")).read_text(encoding="utf-8")
            self.assertIn("SystemKernel path:", content)

    def test_14_section_contains_evidence_rule(self):
        """Section contains evidence-not-truth rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "ProjA"))
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            content = Path(os.path.join(tmpdir, "ProjA", "CLAUDE.md")).read_text(encoding="utf-8")
            self.assertIn("evidence, not truth", content)

    def test_15_section_contains_complexity_rule(self):
        """Section contains ability+10 complexity+300 rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "ProjA"))
            rc, stdout, stderr, report_path = _run_bootstrap(tmpdir, "apply")
            self.assertEqual(rc, 0)
            content = Path(os.path.join(tmpdir, "ProjA", "CLAUDE.md")).read_text(encoding="utf-8")
            self.assertIn("ability +10%", content.lower())
            self.assertIn("complexity +300%", content.lower())


class TestErrorHandling(unittest.TestCase):
    """Tests for error conditions."""

    def test_16_missing_root_exits_nonzero(self):
        """Script exits nonzero when root does not exist."""
        rc, stdout, stderr, _ = _run_bootstrap(
            "F:\\DoesNotExist\\Nope", "dry-run")
        self.assertNotEqual(rc, 0)

    def test_17_both_flags_exits_nonzero(self):
        """Script exits nonzero when both -DryRun and -Apply passed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = os.path.join(tmpdir, "report.json")
            result = subprocess.run([
                "powershell", "-ExecutionPolicy", "Bypass",
                "-File", str(BOOTSTRAP_SCRIPT),
                "-Root", tmpdir,
                "-DryRun", "-Apply",
                "-ReportPath", report,
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_18_no_flag_exits_nonzero(self):
        """Script exits nonzero when neither -DryRun nor -Apply passed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = os.path.join(tmpdir, "report.json")
            result = subprocess.run([
                "powershell", "-ExecutionPolicy", "Bypass",
                "-File", str(BOOTSTRAP_SCRIPT),
                "-Root", tmpdir,
                "-ReportPath", report,
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)


class TestRegression(unittest.TestCase):
    """Regression tests for existing invariants."""

    def test_19_kernel_invariants_importable(self):
        """Kernel invariants are still importable."""
        try:
            from v3.tests import test_kernel_invariants
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"test_kernel_invariants should be importable: {e}")

    def test_20_no_kernel_modifications(self):
        """Bootstrap script does not touch v3/kernel."""
        script = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("v3/kernel", script)
        self.assertNotIn("v3\\kernel", script)

    def test_21_no_memory_modifications(self):
        """Bootstrap script does not touch v3/memory."""
        script = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("v3/memory", script)
        self.assertNotIn("v3\\memory", script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
