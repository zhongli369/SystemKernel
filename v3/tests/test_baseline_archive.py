"""
Test Baseline Archive — Phase 6B archive + tag prep verification.

Validates tag metadata, archive manifest, changelog, and pre-tag
readiness. Does NOT execute git commands. No network. No clone.
"""

import ast
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestBaselineArchive(unittest.TestCase):
    """Phase 6B baseline archive tests."""

    @classmethod
    def setUpClass(cls):
        cls.tag_metadata = None
        cls.archive_manifest = None

    # ═══════════════════════════════════════════════════════════════════
    # Tag Metadata
    # ═══════════════════════════════════════════════════════════════════

    def test_01_tag_metadata_builds(self):
        """Tag metadata builds without error."""
        from v3.release.tag_metadata import build_tag_metadata
        metadata = build_tag_metadata()
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.version, "3.0.0")
        TestBaselineArchive.tag_metadata = metadata

    def test_02_tag_name_is_correct(self):
        """Tag name is systemkernel-v3.0.0-baseline."""
        metadata = TestBaselineArchive.tag_metadata
        if metadata is None:
            self.skipTest("Tag metadata not built")
        self.assertEqual(metadata.tag_name, "systemkernel-v3.0.0-baseline")

    def test_03_tag_metadata_hash_deterministic(self):
        """Tag metadata baseline_hash is deterministic."""
        from v3.release.tag_metadata import build_tag_metadata
        m1 = build_tag_metadata()
        m2 = build_tag_metadata()
        self.assertEqual(m1.baseline_hash, m2.baseline_hash)
        self.assertGreater(len(m1.baseline_hash), 0)

    def test_04_tag_metadata_references_manifest_hash(self):
        """Tag metadata includes manifest_hash from package manifest."""
        metadata = TestBaselineArchive.tag_metadata
        if metadata is None:
            self.skipTest("Tag metadata not built")
        self.assertGreater(len(metadata.manifest_hash), 0)

    def test_05_tag_metadata_references_validation_matrix_hash(self):
        """Tag metadata includes validation_matrix_hash."""
        metadata = TestBaselineArchive.tag_metadata
        if metadata is None:
            self.skipTest("Tag metadata not built")
        self.assertGreater(len(metadata.validation_matrix_hash), 0)

    def test_06_tag_metadata_references_handoff_hash(self):
        """Tag metadata includes handoff_hash."""
        metadata = TestBaselineArchive.tag_metadata
        if metadata is None:
            self.skipTest("Tag metadata not built")
        self.assertGreater(len(metadata.handoff_hash), 0)

    def test_07_tag_metadata_verification_passes(self):
        """Tag metadata passes self-verification."""
        from v3.release.tag_metadata import build_tag_metadata, verify_tag_metadata
        m = build_tag_metadata()
        ok, issues = verify_tag_metadata(m)
        self.assertTrue(ok, f"Tag metadata verification failed: {issues}")

    # ═══════════════════════════════════════════════════════════════════
    # Archive Manifest
    # ═══════════════════════════════════════════════════════════════════

    def test_08_archive_manifest_builds(self):
        """Archive manifest builds without error."""
        from v3.release.archive_manifest import build_archive_manifest
        manifest = build_archive_manifest()
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.version, "3.0.0")
        TestBaselineArchive.archive_manifest = manifest

    def test_09_archive_manifest_hash_deterministic(self):
        """Archive manifest hash is deterministic."""
        from v3.release.archive_manifest import build_archive_manifest
        m1 = build_archive_manifest()
        m2 = build_archive_manifest()
        self.assertEqual(m1.archive_hash, m2.archive_hash)

    def test_10_archive_manifest_includes_reports(self):
        """Archive manifest includes required reports."""
        manifest = TestBaselineArchive.archive_manifest
        if manifest is None:
            self.skipTest("Archive manifest not built")
        self.assertGreater(len(manifest.included_reports), 0)
        self.assertIn("kernel_validity_report.json", manifest.included_reports)

    def test_11_archive_manifest_includes_docs(self):
        """Archive manifest includes documentation files."""
        manifest = TestBaselineArchive.archive_manifest
        if manifest is None:
            self.skipTest("Archive manifest not built")
        self.assertGreater(len(manifest.included_docs), 0)

    def test_12_archive_manifest_includes_golden_path(self):
        """Archive manifest includes golden path examples."""
        manifest = TestBaselineArchive.archive_manifest
        if manifest is None:
            self.skipTest("Archive manifest not built")
        gp = [e for e in manifest.included_examples if "golden_path" in e]
        self.assertGreater(len(gp), 0)

    def test_13_archive_manifest_excludes_caches(self):
        """Archive manifest explicitly excludes cache patterns."""
        manifest = TestBaselineArchive.archive_manifest
        if manifest is None:
            self.skipTest("Archive manifest not built")
        self.assertIn("__pycache__/", manifest.excluded_patterns)
        self.assertIn(".git/", manifest.excluded_patterns)

    def test_14_archive_manifest_ready(self):
        """Archive manifest reports archive_ready is True."""
        manifest = TestBaselineArchive.archive_manifest
        if manifest is None:
            self.skipTest("Archive manifest not built")
        self.assertTrue(manifest.archive_ready)

    def test_15_archive_manifest_verification_passes(self):
        """Archive manifest passes self-verification."""
        from v3.release.archive_manifest import build_archive_manifest, verify_archive_manifest
        m = build_archive_manifest()
        ok, issues = verify_archive_manifest(m)
        self.assertTrue(ok, f"Archive manifest verification failed: {issues}")

    # ═══════════════════════════════════════════════════════════════════
    # Changelog
    # ═══════════════════════════════════════════════════════════════════

    def test_16_changelog_exists(self):
        """CHANGELOG.md exists in docs/ directory."""
        cpath = os.path.join(ROOT, "docs", "CHANGELOG.md")
        self.assertTrue(os.path.exists(cpath),
                       f"CHANGELOG.md not found at {cpath}")
        with open(cpath, encoding="utf-8") as f:
            content = f.read()
        self.assertGreater(len(content), 500)
        self.assertIn("3.0.0", content)
        self.assertIn("Deterministic Kernel", content)

    # ═══════════════════════════════════════════════════════════════════
    # No Git Execution
    # ═══════════════════════════════════════════════════════════════════

    def test_17_no_git_tag_command_in_release(self):
        """No git tag command is executed in release modules."""
        import ast
        release_dir = os.path.join(V3_ROOT, "release")
        git_patterns = ["git tag", "git push", "subprocess.run(['git'"]
        for fname in os.listdir(release_dir):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(release_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    source = f.read()
                for pat in git_patterns:
                    self.assertNotIn(pat, source,
                                    f"Git command in {fname}: {pat}")
            except UnicodeDecodeError:
                pass

    def test_18_no_git_push_command_in_release(self):
        """No git push command exists in any release module."""
        release_dir = os.path.join(V3_ROOT, "release")
        for fname in os.listdir(release_dir):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(release_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    source = f.read()
                self.assertNotIn("git push", source,
                                f"'git push' found in {fname}")
            except UnicodeDecodeError:
                pass

    # ═══════════════════════════════════════════════════════════════════
    # Invariants Preserved
    # ═══════════════════════════════════════════════════════════════════

    def test_19_kernel_purity_remains_100(self):
        """Kernel purity score is exactly 100."""
        k_path = os.path.join(EXPORTS_DIR, "kernel_validity_report.json")
        data = _read_json(k_path)
        purity = data.get("purity_score", 0)
        self.assertEqual(purity, 100,
                       f"Kernel purity is {purity}, expected 100")

    def test_20_memory_removable_remains_yes(self):
        """Memory removability remains YES."""
        mem_path = os.path.join(EXPORTS_DIR, "memory_system_report.json")
        data = _read_json(mem_path)
        removable = data.get("verdicts", {}).get("removability", "NO")
        self.assertEqual(removable, "YES",
                       f"Memory removable is {removable}, expected YES")

    def test_21_complexity_gate_not_reject(self):
        """Complexity gate verdict is not REJECT."""
        cb_path = os.path.join(EXPORTS_DIR, "complexity_budget_report.json")
        data = _read_json(cb_path)
        verdict = data.get("verdict", {}).get("verdict", "UNKNOWN")
        self.assertNotEqual(verdict, "REJECT",
                          f"Complexity gate is REJECT")

    # ═══════════════════════════════════════════════════════════════════
    # Pre-tag Readiness
    # ═══════════════════════════════════════════════════════════════════

    def test_22_verification_script_still_referenced(self):
        """Verification script exists and is valid Python."""
        vpath = os.path.join(ROOT, "scripts", "verify_v3_baseline.py")
        self.assertTrue(os.path.exists(vpath))
        with open(vpath, encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)  # must be valid Python

    def test_23_all_release_modules_importable(self):
        """All release modules are importable with correct symbols."""
        from v3.release.tag_metadata import (
            TagMetadata, build_tag_metadata,
            write_tag_metadata, verify_tag_metadata,
        )
        from v3.release.archive_manifest import (
            ArchiveManifest, build_archive_manifest,
            write_archive_manifest, verify_archive_manifest,
        )
        self.assertIsNotNone(TagMetadata)
        self.assertIsNotNone(ArchiveManifest)
        self.assertTrue(callable(build_tag_metadata))
        self.assertTrue(callable(build_archive_manifest))
        self.assertTrue(callable(verify_tag_metadata))
        self.assertTrue(callable(verify_archive_manifest))

    def test_24_tag_metadata_writes_to_file(self):
        """Tag metadata can be written to a JSON file."""
        from v3.release.tag_metadata import build_tag_metadata, write_tag_metadata
        import tempfile
        m = build_tag_metadata()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = write_tag_metadata(m, f.name)
        self.assertTrue(os.path.exists(path))
        data = _read_json(path)
        self.assertEqual(data["tag_name"], "systemkernel-v3.0.0-baseline")
        os.unlink(path)

    def test_25_archive_manifest_writes_to_file(self):
        """Archive manifest can be written to a JSON file."""
        from v3.release.archive_manifest import build_archive_manifest, write_archive_manifest
        import tempfile
        m = build_archive_manifest()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = write_archive_manifest(m, f.name)
        self.assertTrue(os.path.exists(path))
        data = _read_json(path)
        self.assertEqual(data["archive_name"], "systemkernel-v3.0.0-baseline")
        os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
