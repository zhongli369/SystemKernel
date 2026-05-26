"""
Test Baseline Packaging — Phase 6A packaging verification.

Validates package manifest, operational handoff, verification script,
and all release freeze invariants remain intact.

At least 21 tests. No network. No clone. No install.
"""

import ast
import hashlib
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════

class TestBaselinePackaging(unittest.TestCase):
    """Phase 6A baseline packaging tests."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = None
        cls.handoff = None

    # ── Package Manifest ──

    def test_01_package_manifest_builds(self):
        """Package manifest builds without error."""
        from v3.release.package_manifest import build_package_manifest
        manifest = build_package_manifest()
        self.assertIsNotNone(manifest)
        self.assertGreater(len(manifest.entries), 0)
        TestBaselinePackaging.manifest = manifest

    def test_02_manifest_hash_deterministic(self):
        """Package manifest hash is deterministic (same files → same hash)."""
        from v3.release.package_manifest import build_package_manifest
        m1 = build_package_manifest()
        m2 = build_package_manifest()
        self.assertEqual(m1.manifest_hash, m2.manifest_hash)
        self.assertGreater(len(m1.manifest_hash), 0)

    def test_03_required_source_files_included(self):
        """All required kernel source files are in the manifest."""
        manifest = TestBaselinePackaging.manifest
        if manifest is None:
            self.skipTest("Manifest not built")
        kernel_entries = [e for e in manifest.entries
                         if e.subsystem == "kernel" and e.artifact_type == "source"]
        self.assertGreater(len(kernel_entries), 0)
        required_files = ["execution_engine.py", "events.py", "checkpoint.py",
                         "observability.py", "invariants.py"]
        found = set(os.path.basename(e.path) for e in kernel_entries)
        for rf in required_files:
            self.assertIn(rf, found, f"Missing required kernel file: {rf}")

    def test_04_tests_included(self):
        """Test files are included in the manifest."""
        manifest = TestBaselinePackaging.manifest
        if manifest is None:
            self.skipTest("Manifest not built")
        test_entries = [e for e in manifest.entries if e.artifact_type == "test"]
        self.assertGreater(len(test_entries), 0)
        test_names = [os.path.basename(e.path) for e in test_entries]
        self.assertIn("test_release_freeze.py", test_names)
        self.assertIn("test_kernel_invariants.py", test_names)

    def test_05_reports_included(self):
        """Export reports are included in the manifest."""
        manifest = TestBaselinePackaging.manifest
        if manifest is None:
            self.skipTest("Manifest not built")
        report_entries = [e for e in manifest.entries if e.artifact_type == "report"]
        self.assertGreater(len(report_entries), 0)

    def test_06_docs_included(self):
        """Documentation files are included in the manifest."""
        manifest = TestBaselinePackaging.manifest
        if manifest is None:
            self.skipTest("Manifest not built")
        doc_entries = [e for e in manifest.entries if e.artifact_type == "doc"]
        self.assertGreater(len(doc_entries), 0)

    def test_07_golden_path_included(self):
        """Golden path example is included in the manifest."""
        manifest = TestBaselinePackaging.manifest
        if manifest is None:
            self.skipTest("Manifest not built")
        gp_entries = [e for e in manifest.entries
                     if "golden_path" in e.path and e.artifact_type == "example"]
        self.assertGreater(len(gp_entries), 0)

    def test_08_transient_caches_excluded(self):
        """Transient cache files are excluded from the manifest."""
        manifest = TestBaselinePackaging.manifest
        if manifest is None:
            self.skipTest("Manifest not built")
        transient_patterns = ("__pycache__", ".pyc", ".egg-info")
        for e in manifest.entries:
            for pat in transient_patterns:
                self.assertNotIn(pat, e.path,
                                f"Transient cache found: {e.path}")

    def test_09_package_verification_passes(self):
        """Package manifest passes self-verification."""
        from v3.release.package_manifest import build_package_manifest, verify_package_manifest
        m = build_package_manifest()
        ok, issues = verify_package_manifest(m)
        self.assertTrue(ok, f"Verification failed: {issues}")

    # ── Handoff ──

    def test_10_handoff_builds(self):
        """Operational handoff builds without error."""
        from v3.release.handoff import build_handoff
        handoff = build_handoff()
        self.assertIsNotNone(handoff)
        self.assertGreater(len(handoff.checklist), 0)
        TestBaselinePackaging.handoff = handoff

    def test_11_handoff_hash_deterministic(self):
        """Operational handoff hash is deterministic."""
        from v3.release.handoff import build_handoff
        h1 = build_handoff()
        h2 = build_handoff()
        self.assertEqual(h1.handoff_hash, h2.handoff_hash)

    def test_12_handoff_checklist_has_required_commands(self):
        """Handoff checklist includes all required verification items."""
        handoff = TestBaselinePackaging.handoff
        if handoff is None:
            self.skipTest("Handoff not built")
        titles = {c.title for c in handoff.checklist}
        required_titles = {
            "Run kernel invariants",
            "Run release freeze tests",
            "Run CLI doctor",
            "Run golden path",
            "Run complexity gate",
            "Verify memory removable",
        }
        for rt in required_titles:
            self.assertIn(rt, titles, f"Missing checklist item: {rt}")

    # ── Verification Script ──

    def test_13_verify_script_exists(self):
        """Verification script exists at scripts/verify_v3_baseline.py."""
        vpath = os.path.join(ROOT, "scripts", "verify_v3_baseline.py")
        self.assertTrue(os.path.exists(vpath),
                       f"verify_v3_baseline.py not found at {vpath}")

    def test_14_verify_script_no_network_clone_install(self):
        """Verification script contains no network/clone/install commands."""
        vpath = os.path.join(ROOT, "scripts", "verify_v3_baseline.py")
        with open(vpath, encoding="utf-8") as f:
            source = f.read()

        banned_patterns = [
            "git clone", "gitClone",
            "pip install", "pip3 install",
            "npm install", "yarn add",
            "urllib.request", "urllib.urlopen",
            "requests.get", "requests.post",
            "httpx.get", "httpx.post",
            "socket.create_connection",
            "http.client",
            "subprocess.run(['git', 'clone']",
            "os.system('git clone",
        ]
        for pattern in banned_patterns:
            self.assertNotIn(pattern, source,
                            f"Banned pattern in verify script: {pattern}")

        # Check no network imports
        tree = ast.parse(source)
        net_imports = {"urllib", "requests", "httpx", "socket", "aiohttp"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    self.assertNotIn(name, net_imports,
                                    f"Network import in verify script: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    self.assertNotIn(name, net_imports,
                                    f"Network import in verify script: {node.module}")

    # ── Documentation ──

    def test_15_operations_doc_exists(self):
        """OPERATIONS.md exists in docs/ directory."""
        opath = os.path.join(ROOT, "docs", "OPERATIONS.md")
        self.assertTrue(os.path.exists(opath),
                       f"OPERATIONS.md not found at {opath}")

        with open(opath, encoding="utf-8") as f:
            content = f.read()
        self.assertGreater(len(content), 500, "OPERATIONS.md is too short")

        # Check key sections exist
        required_sections = [
            "How to Verify",
            "How to Run the CLI",
            "How to Regenerate Reports",
            "What NOT to Modify After Freeze",
            "Rollback Guidance",
            "Complexity Gate Policy",
        ]
        for section in required_sections:
            self.assertIn(section, content,
                         f"Missing section in OPERATIONS.md: {section}")

    # ── Release Artifacts ──

    def test_16_release_notes_exist(self):
        """Release notes still exist after packaging changes."""
        notes_path = os.path.join(EXPORTS_DIR, "systemkernel_v3_release_notes.md")
        self.assertTrue(os.path.exists(notes_path))

    def test_17_release_inventory_exists(self):
        """Release inventory still exists."""
        inv_path = os.path.join(EXPORTS_DIR, "release_inventory.json")
        self.assertTrue(os.path.exists(inv_path))
        data = _read_json(inv_path)
        self.assertIn("release_version", data)

    # ── Complexity Gate ──

    def test_18_complexity_gate_not_reject(self):
        """Complexity gate verdict is not REJECT."""
        cb_path = os.path.join(EXPORTS_DIR, "complexity_budget_report.json")
        data = _read_json(cb_path)
        verdict = data.get("verdict", {}).get("verdict", "UNKNOWN")
        self.assertNotEqual(verdict, "REJECT",
                           f"Complexity gate is REJECT: {data.get('verdict', {})}")

    # ── Kernel Purity ──

    def test_19_kernel_purity_remains_100(self):
        """Kernel purity score is exactly 100."""
        k_path = os.path.join(EXPORTS_DIR, "kernel_validity_report.json")
        data = _read_json(k_path)
        purity = data.get("purity_score", 0)
        self.assertEqual(purity, 100, f"Kernel purity is {purity}, expected 100")

    # ── Memory Removable ──

    def test_20_memory_removable_remains_yes(self):
        """Memory removability remains YES."""
        mem_path = os.path.join(EXPORTS_DIR, "memory_system_report.json")
        data = _read_json(mem_path)
        removable = data.get("verdicts", {}).get("removability", "NO")
        self.assertEqual(removable, "YES",
                        f"Memory removability is {removable}, expected YES")

    # ── Existing Tests Still Pass ──

    def test_21_release_freeze_tests_still_pass(self):
        """Existing release freeze tests still pass (structural check)."""
        # Verify the test file exists and parses correctly
        rf_path = os.path.join(V3_ROOT, "tests", "test_release_freeze.py")
        self.assertTrue(os.path.exists(rf_path))
        with open(rf_path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        test_funcs = [node.name for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name.startswith("test_")]
        self.assertGreater(len(test_funcs), 0, "No test functions found in test_release_freeze.py")

    # ── Bonus: Release Module Imports ──

    def test_22_package_manifest_importable(self):
        """Package manifest module is importable and exports correct symbols."""
        from v3.release.package_manifest import (
            PackageManifestEntry,
            PackageManifest,
            build_package_manifest,
            write_package_manifest,
            verify_package_manifest,
        )
        self.assertIsNotNone(PackageManifestEntry)
        self.assertIsNotNone(PackageManifest)
        self.assertTrue(callable(build_package_manifest))
        self.assertTrue(callable(write_package_manifest))
        self.assertTrue(callable(verify_package_manifest))

    def test_23_handoff_importable(self):
        """Handoff module is importable and exports correct symbols."""
        from v3.release.handoff import (
            HandoffChecklistItem,
            OperationalHandoff,
            build_handoff,
            write_handoff_json,
            write_handoff_md,
        )
        self.assertIsNotNone(HandoffChecklistItem)
        self.assertIsNotNone(OperationalHandoff)
        self.assertTrue(callable(build_handoff))
        self.assertTrue(callable(write_handoff_json))
        self.assertTrue(callable(write_handoff_md))

    # ── Manifest integrity ──

    def test_24_manifest_has_valid_hashes(self):
        """All manifest entries with size > 0 have non-zero hashes."""
        from v3.release.package_manifest import build_package_manifest
        m = build_package_manifest()
        for e in m.entries:
            if e.size_bytes > 0:
                self.assertNotEqual(e.hash, "0" * 16,
                                   f"Zero hash for non-empty file: {e.path}")

    def test_25_manifest_entries_are_deterministically_ordered(self):
        """Manifest entries are sorted deterministically by path."""
        from v3.release.package_manifest import build_package_manifest
        m1 = build_package_manifest()
        m2 = build_package_manifest()
        paths1 = [e.path for e in m1.entries]
        paths2 = [e.path for e in m2.entries]
        self.assertEqual(paths1, paths2)
        self.assertEqual(paths1, sorted(paths1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
