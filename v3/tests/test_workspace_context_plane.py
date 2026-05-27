"""
Workspace Context Plane Tests — Phase 7.

56 tests for the Workspace Context Plane: providers, file refs,
diagnostics, git state, snapshots, reports, policy validation,
profiles, evidence mapping, and CLI.
Stdlib only. No IDE APIs. No file watching. No terminal. No LLM.
"""

import ast
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")
FIXTURE_DIR = os.path.join(V3_ROOT, "tests", "fixtures")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable

from v3.external.workspace_context import (
    WorkspaceProvider,
    WorkspaceFileRef,
    WorkspaceDiagnostic,
    WorkspaceGitState,
    WorkspaceSnapshot,
    WorkspaceContextReport,
    WorkspaceValidationResult,
    PROVIDER_TYPE_CONTINUE_LIKE,
    PROVIDER_TYPE_CLINE_LIKE,
    PROVIDER_TYPE_ROO_LIKE,
    PROVIDER_TYPE_VSCODE_LIKE,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    PROVIDER_TYPE_GENERIC,
    ALL_PROVIDER_TYPES,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_ERROR,
    ALL_SEVERITIES,
    make_workspace_file_ref,
    make_workspace_diagnostic,
    make_workspace_git_state,
    make_workspace_snapshot,
    mock_workspace_snapshot,
    validate_workspace_provider,
    validate_workspace_snapshot,
    workspace_snapshot_to_evidence,
    build_workspace_context_report,
    _compute_hash,
)

from v3.external.workspace_context_policy import (
    POLICY_PASS,
    POLICY_BLOCKED,
    POLICY_REVIEW,
    WorkspaceContextPolicy,
    default_workspace_context_policy,
    validate_provider_against_policy,
    validate_snapshot_against_policy,
    block_provider_reason,
)

from v3.external.workspace_context_profiles import (
    WorkspaceProfileStatus,
    continue_workspace_profile,
    cline_workspace_profile,
    roo_workspace_profile,
    vscode_workspace_profile,
    deterministic_mock_workspace_profile,
    get_all_profiles,
    get_profile,
    evaluate_all_profiles,
)


# ═══════════════════════════════════════════════════════════════════════
# Provider Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceProvider(unittest.TestCase):

    def test_01_constructor_defaults(self):
        p = WorkspaceProvider()
        self.assertEqual(p.provider_id, "")
        self.assertEqual(p.capability_type, "ide")
        self.assertEqual(p.execution_mode, "inspect_only")
        self.assertFalse(p.requires_ide_api)
        self.assertFalse(p.requires_file_watch)
        self.assertFalse(p.can_write_files)
        self.assertFalse(p.can_execute_terminal)
        self.assertFalse(p.truth_source)
        self.assertTrue(p.removable)

    def test_02_constructor_full(self):
        p = WorkspaceProvider(
            provider_id="test_ide",
            name="Test IDE",
            provider_type=PROVIDER_TYPE_CONTINUE_LIKE,
            requires_ide_api=True,
            can_read_files=True,
            can_write_files=True,
            description="Test",
        )
        self.assertEqual(p.provider_id, "test_ide")
        self.assertTrue(p.requires_ide_api)
        self.assertTrue(p.can_read_files)

    def test_03_frozen(self):
        p = WorkspaceProvider(provider_id="test")
        with self.assertRaises(Exception):
            p.provider_id = "changed"

    def test_04_to_dict(self):
        p = WorkspaceProvider(provider_id="test", name="Test")
        d = p.to_dict()
        self.assertEqual(d["provider_id"], "test")
        self.assertFalse(d["truth_source"])
        self.assertTrue(d["removable"])

    def test_05_hash_determinism(self):
        p1 = WorkspaceProvider(provider_id="test")
        p2 = WorkspaceProvider(provider_id="test")
        self.assertEqual(_compute_hash(p1), _compute_hash(p2))

    def test_06_truth_source_always_false(self):
        p = WorkspaceProvider(provider_id="test")
        self.assertFalse(p.truth_source)

    def test_07_removable_always_true(self):
        p = WorkspaceProvider(provider_id="test")
        self.assertTrue(p.removable)

    def test_08_all_provider_types(self):
        self.assertEqual(len(ALL_PROVIDER_TYPES), 6)
        self.assertIn(PROVIDER_TYPE_CONTINUE_LIKE, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_DETERMINISTIC_MOCK, ALL_PROVIDER_TYPES)


# ═══════════════════════════════════════════════════════════════════════
# File Ref Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceFileRef(unittest.TestCase):

    def test_09_constructor_defaults(self):
        f = WorkspaceFileRef()
        self.assertEqual(f.path, "")
        self.assertTrue(f.included)
        self.assertFalse(f.redacted)

    def test_10_frozen(self):
        f = WorkspaceFileRef(path="test.py")
        with self.assertRaises(Exception):
            f.path = "changed"

    def test_11_to_dict(self):
        f = WorkspaceFileRef(path="src/main.py", language="python",
                             size_bytes=100, content_hash="abc123")
        d = f.to_dict()
        self.assertEqual(d["path"], "src/main.py")
        self.assertEqual(d["language"], "python")
        self.assertEqual(d["size_bytes"], 100)

    def test_12_hash_determinism(self):
        f1 = make_workspace_file_ref("src/a.py", language="python", size_bytes=100)
        f2 = make_workspace_file_ref("src/a.py", language="python", size_bytes=100)
        self.assertEqual(f1.ref_hash, f2.ref_hash)

    def test_13_hash_differs_on_path(self):
        f1 = make_workspace_file_ref("src/a.py")
        f2 = make_workspace_file_ref("src/b.py")
        self.assertNotEqual(f1.ref_hash, f2.ref_hash)


# ═══════════════════════════════════════════════════════════════════════
# Diagnostic Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceDiagnostic(unittest.TestCase):

    def test_14_constructor_defaults(self):
        d = WorkspaceDiagnostic()
        self.assertEqual(d.severity, SEVERITY_INFO)
        self.assertEqual(d.line, 0)

    def test_15_frozen(self):
        d = WorkspaceDiagnostic(diagnostic_id="d1")
        with self.assertRaises(Exception):
            d.diagnostic_id = "changed"

    def test_16_to_dict(self):
        d = WorkspaceDiagnostic(
            diagnostic_id="d1", path="a.py", severity=SEVERITY_WARNING,
            source="ruff", message_summary="Unused import", line=10,
        )
        self.assertEqual(d.to_dict()["severity"], SEVERITY_WARNING)

    def test_17_hash_determinism(self):
        d1 = make_workspace_diagnostic("a.py", severity=SEVERITY_ERROR,
                                       source="mypy", message_summary="Error", line=1)
        d2 = make_workspace_diagnostic("a.py", severity=SEVERITY_ERROR,
                                       source="mypy", message_summary="Error", line=1)
        self.assertEqual(d1.diagnostic_hash, d2.diagnostic_hash)

    def test_18_diagnostic_id_deterministic(self):
        d1 = make_workspace_diagnostic("a.py", severity=SEVERITY_ERROR,
                                       source="mypy", message_summary="Error")
        d2 = make_workspace_diagnostic("a.py", severity=SEVERITY_ERROR,
                                       source="mypy", message_summary="Error")
        self.assertEqual(d1.diagnostic_id, d2.diagnostic_id)

    def test_19_severities(self):
        self.assertIn(SEVERITY_INFO, ALL_SEVERITIES)
        self.assertIn(SEVERITY_WARNING, ALL_SEVERITIES)
        self.assertIn(SEVERITY_ERROR, ALL_SEVERITIES)


# ═══════════════════════════════════════════════════════════════════════
# Git State Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceGitState(unittest.TestCase):

    def test_20_constructor_defaults(self):
        gs = WorkspaceGitState()
        self.assertEqual(gs.branch, "")
        self.assertEqual(gs.modified_count, 0)

    def test_21_frozen(self):
        gs = WorkspaceGitState(branch="main")
        with self.assertRaises(Exception):
            gs.branch = "changed"

    def test_22_to_dict(self):
        gs = WorkspaceGitState(
            branch="master", head_commit="abc123",
            modified_count=3, untracked_count=1, staged_count=2,
        )
        d = gs.to_dict()
        self.assertEqual(d["branch"], "master")
        self.assertEqual(d["modified_count"], 3)

    def test_23_hash_determinism(self):
        gs1 = make_workspace_git_state(branch="master", modified_count=2)
        gs2 = make_workspace_git_state(branch="master", modified_count=2)
        self.assertEqual(gs1.git_state_hash, gs2.git_state_hash)


# ═══════════════════════════════════════════════════════════════════════
# Snapshot Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceSnapshot(unittest.TestCase):

    def test_24_constructor_defaults(self):
        s = WorkspaceSnapshot()
        self.assertEqual(s.snapshot_id, "")
        self.assertFalse(s.truth_source)

    def test_25_frozen(self):
        s = WorkspaceSnapshot(snapshot_id="s1")
        with self.assertRaises(Exception):
            s.snapshot_id = "changed"

    def test_26_to_dict(self):
        refs = (make_workspace_file_ref("a.py"),)
        s = WorkspaceSnapshot(snapshot_id="s1", provider_id="p1",
                              root_path="/test", file_refs=refs)
        d = s.to_dict()
        self.assertEqual(d["snapshot_id"], "s1")
        self.assertFalse(d["truth_source"])
        self.assertEqual(len(d["file_refs"]), 1)

    def test_27_hash_determinism(self):
        refs = (make_workspace_file_ref("a.py"),)
        s1 = make_workspace_snapshot("p1", file_refs=refs)
        s2 = make_workspace_snapshot("p1", file_refs=refs)
        self.assertEqual(s1.snapshot_hash, s2.snapshot_hash)

    def test_28_file_refs_sorted(self):
        refs = (
            make_workspace_file_ref("c.py"),
            make_workspace_file_ref("a.py"),
            make_workspace_file_ref("b.py"),
        )
        s = make_workspace_snapshot("p1", file_refs=refs)
        paths = [f.path for f in s.file_refs]
        self.assertEqual(paths, sorted(paths))

    def test_29_diagnostics_sorted(self):
        d1 = make_workspace_diagnostic("b.py", severity=SEVERITY_ERROR, line=5)
        d2 = make_workspace_diagnostic("a.py", severity=SEVERITY_WARNING, line=3)
        s = make_workspace_snapshot("p1", diagnostics=(d1, d2))
        keys = [(d.path, d.severity, d.line) for d in s.diagnostics]
        self.assertEqual(keys, sorted(keys))

    def test_30_open_files_sorted(self):
        s = make_workspace_snapshot("p1", open_files=("c.py", "a.py", "b.py"))
        self.assertEqual(list(s.open_files), sorted(s.open_files))

    def test_31_truth_source_always_false(self):
        s = make_workspace_snapshot("p1")
        self.assertFalse(s.truth_source)


# ═══════════════════════════════════════════════════════════════════════
# Report Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceReport(unittest.TestCase):

    def test_32_constructor_defaults(self):
        r = WorkspaceContextReport()
        self.assertIsNone(r.provider)
        self.assertIsNone(r.snapshot)
        self.assertEqual(r.policy_status, "unknown")

    def test_33_frozen(self):
        r = WorkspaceContextReport(policy_status="pass")
        with self.assertRaises(Exception):
            r.policy_status = "changed"

    def test_34_to_dict_with_none(self):
        r = WorkspaceContextReport()
        d = r.to_dict()
        self.assertIsNone(d["provider"])
        self.assertIsNone(d["snapshot"])

    def test_35_hash_determinism(self):
        r1 = WorkspaceContextReport(evidence_bundle_id="b1", policy_status="pass")
        r2 = WorkspaceContextReport(evidence_bundle_id="b1", policy_status="pass")
        self.assertEqual(_compute_hash(r1), _compute_hash(r2))


# ═══════════════════════════════════════════════════════════════════════
# Validation Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceValidation(unittest.TestCase):

    def test_36_validate_provider_valid(self):
        p = WorkspaceProvider(
            provider_id="test", provider_type=PROVIDER_TYPE_DETERMINISTIC_MOCK,
        )
        v = validate_workspace_provider(p)
        self.assertTrue(v.valid)

    def test_37_validate_provider_truth_source_violation(self):
        p = WorkspaceProvider(provider_id="test", truth_source=True)
        v = validate_workspace_provider(p)
        self.assertFalse(v.valid)

    def test_38_validate_provider_removable_violation(self):
        p = WorkspaceProvider(provider_id="test", removable=False)
        v = validate_workspace_provider(p)
        self.assertFalse(v.valid)

    def test_39_validate_provider_unknown_type(self):
        p = WorkspaceProvider(provider_id="test", provider_type="bad_type")
        v = validate_workspace_provider(p)
        self.assertFalse(v.valid)

    def test_40_validate_provider_empty_id(self):
        p = WorkspaceProvider(provider_id="")
        v = validate_workspace_provider(p)
        self.assertFalse(v.valid)

    def test_41_validate_snapshot_valid(self):
        refs = (make_workspace_file_ref("a.py"),)
        s = make_workspace_snapshot("p1", file_refs=refs)
        v = validate_workspace_snapshot(s)
        self.assertTrue(v.valid)

    def test_42_validate_snapshot_truth_source_violation(self):
        s = WorkspaceSnapshot(snapshot_id="s1", provider_id="p1", truth_source=True)
        v = validate_workspace_snapshot(s)
        self.assertFalse(v.valid)

    def test_43_validate_snapshot_unsorted_file_refs(self):
        refs = (
            WorkspaceFileRef(path="c.py", ref_hash="h3"),
            WorkspaceFileRef(path="a.py", ref_hash="h1"),
        )
        s = WorkspaceSnapshot(snapshot_id="s1", provider_id="p1", file_refs=refs)
        v = validate_workspace_snapshot(s)
        self.assertFalse(v.valid)


# ═══════════════════════════════════════════════════════════════════════
# Mock Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceMock(unittest.TestCase):

    def test_44_mock_snapshot_produces_file_refs(self):
        s = mock_workspace_snapshot(file_count=4)
        self.assertEqual(len(s.file_refs), 4)

    def test_45_mock_snapshot_produces_diagnostics(self):
        s = mock_workspace_snapshot(diagnostic_count=3)
        self.assertEqual(len(s.diagnostics), 3)

    def test_46_mock_snapshot_has_git_state(self):
        s = mock_workspace_snapshot()
        self.assertIsNotNone(s.git_state)
        self.assertEqual(s.git_state.branch, "master")

    def test_47_mock_snapshot_deterministic(self):
        s1 = mock_workspace_snapshot("p1", file_count=3, diagnostic_count=2)
        s2 = mock_workspace_snapshot("p1", file_count=3, diagnostic_count=2)
        self.assertEqual(s1.snapshot_hash, s2.snapshot_hash)

    def test_48_mock_snapshot_truth_source_false(self):
        s = mock_workspace_snapshot()
        self.assertFalse(s.truth_source)

    def test_49_mock_snapshot_max_10_files(self):
        s = mock_workspace_snapshot(file_count=20)
        self.assertLessEqual(len(s.file_refs), 10)

    def test_50_mock_snapshot_max_8_diagnostics(self):
        s = mock_workspace_snapshot(diagnostic_count=20)
        self.assertLessEqual(len(s.diagnostics), 8)


# ═══════════════════════════════════════════════════════════════════════
# Policy Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspacePolicy(unittest.TestCase):

    def test_51_default_policy_blocks_everything(self):
        p = default_workspace_context_policy()
        self.assertFalse(p.allow_ide_api)
        self.assertFalse(p.allow_file_watch)
        self.assertFalse(p.allow_file_write)
        self.assertFalse(p.allow_terminal_execution)
        self.assertFalse(p.allow_external_services)
        self.assertTrue(p.require_redaction)
        self.assertTrue(p.require_human_approval)

    def test_52_default_policy_hash_deterministic(self):
        p1 = default_workspace_context_policy()
        p2 = default_workspace_context_policy()
        self.assertEqual(p1.policy_hash, p2.policy_hash)

    def test_53_policy_frozen(self):
        p = default_workspace_context_policy()
        with self.assertRaises(Exception):
            p.allow_ide_api = True

    def test_54_block_mock_provider_passes(self):
        provider = deterministic_mock_workspace_profile()
        policy = default_workspace_context_policy()
        reason = block_provider_reason(provider, policy)
        self.assertEqual(reason, "")

    def test_55_block_provider_ide_api(self):
        provider = continue_workspace_profile()
        policy = default_workspace_context_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("IDE API", reason)

    def test_56_block_provider_file_watch(self):
        provider = WorkspaceProvider(
            provider_id="watch_prov", provider_type="generic",
            requires_file_watch=True,
        )
        policy = default_workspace_context_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("file watch", reason)

    def test_57_block_provider_file_write(self):
        provider = WorkspaceProvider(
            provider_id="write_prov", provider_type="generic",
            can_write_files=True,
        )
        policy = default_workspace_context_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("write files", reason)

    def test_58_block_provider_terminal_execution(self):
        provider = WorkspaceProvider(
            provider_id="term_prov", provider_type="generic",
            can_execute_terminal=True,
        )
        policy = default_workspace_context_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("terminal", reason)

    def test_59_validate_snapshot_max_files(self):
        refs = tuple(make_workspace_file_ref(f"f{i}.py") for i in range(200))
        s = make_workspace_snapshot("p1", file_refs=refs)
        policy = default_workspace_context_policy()
        ok, reason = validate_snapshot_against_policy(s, policy)
        self.assertFalse(ok)
        self.assertIn("file refs", reason)

    def test_60_validate_snapshot_max_diagnostics(self):
        diags = tuple(
            make_workspace_diagnostic(f"f{i}.py", message_summary="msg")
            for i in range(300)
        )
        s = make_workspace_snapshot("p1", diagnostics=diags)
        policy = default_workspace_context_policy()
        ok, reason = validate_snapshot_against_policy(s, policy)
        self.assertFalse(ok)
        self.assertIn("diagnostics", reason)

    def test_61_validate_snapshot_max_open_files(self):
        s = make_workspace_snapshot("p1", open_files=tuple(f"f{i}.py" for i in range(30)))
        policy = default_workspace_context_policy()
        ok, reason = validate_snapshot_against_policy(s, policy)
        self.assertFalse(ok)
        self.assertIn("open files", reason)


# ═══════════════════════════════════════════════════════════════════════
# Profiles Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceProfiles(unittest.TestCase):

    def test_62_all_profiles_exist(self):
        profiles = get_all_profiles()
        self.assertEqual(len(profiles), 5)

    def test_63_all_profiles_truth_source_false(self):
        for p in get_all_profiles():
            self.assertFalse(p.truth_source, f"{p.provider_id}: truth_source must be False")

    def test_64_all_profiles_removable_true(self):
        for p in get_all_profiles():
            self.assertTrue(p.removable, f"{p.provider_id}: removable must be True")

    def test_65_mock_profile_allowed(self):
        policy = default_workspace_context_policy()
        statuses = evaluate_all_profiles(policy)
        mock_status = next(s for s in statuses if s.provider_id == "deterministic_mock_workspace")
        self.assertTrue(mock_status.allowed)

    def test_66_real_profiles_blocked(self):
        policy = default_workspace_context_policy()
        statuses = evaluate_all_profiles(policy)
        for s in statuses:
            if s.provider_id != "deterministic_mock_workspace":
                self.assertFalse(s.allowed, f"{s.provider_id} should be blocked")

    def test_67_get_profile_known(self):
        p = get_profile("deterministic_mock_workspace")
        self.assertIsNotNone(p)

    def test_68_get_profile_unknown(self):
        p = get_profile("nonexistent")
        self.assertIsNone(p)

    def test_69_profiles_sorted(self):
        profiles = get_all_profiles()
        ids = [p.provider_id for p in profiles]
        self.assertEqual(ids, sorted(ids))

    def test_70_continue_profile_blocked(self):
        p = continue_workspace_profile()
        policy = default_workspace_context_policy()
        allowed, _ = validate_provider_against_policy(p, policy)
        self.assertFalse(allowed)

    def test_71_cline_profile_blocked(self):
        p = cline_workspace_profile()
        policy = default_workspace_context_policy()
        allowed, _ = validate_provider_against_policy(p, policy)
        self.assertFalse(allowed)

    def test_72_roo_profile_blocked(self):
        p = roo_workspace_profile()
        policy = default_workspace_context_policy()
        allowed, _ = validate_provider_against_policy(p, policy)
        self.assertFalse(allowed)

    def test_73_vscode_profile_blocked(self):
        p = vscode_workspace_profile()
        policy = default_workspace_context_policy()
        allowed, _ = validate_provider_against_policy(p, policy)
        self.assertFalse(allowed)


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceEvidenceMapping(unittest.TestCase):

    def test_74_evidence_from_snapshot(self):
        s = mock_workspace_snapshot(file_count=3, diagnostic_count=2)
        bundle = workspace_snapshot_to_evidence(s, registry_hash="abc123")
        self.assertEqual(len(bundle.records), 3)  # file refs + diagnostics + git state
        self.assertFalse(bundle.truth_source)

    def test_75_evidence_empty_snapshot(self):
        s = WorkspaceSnapshot(snapshot_id="s1", provider_id="p1")
        bundle = workspace_snapshot_to_evidence(s, registry_hash="abc123")
        self.assertEqual(len(bundle.records), 1)  # fallback record

    def test_76_evidence_truth_source_false(self):
        s = mock_workspace_snapshot()
        bundle = workspace_snapshot_to_evidence(s)
        self.assertFalse(bundle.truth_source)

    def test_77_report_from_evidence(self):
        provider = deterministic_mock_workspace_profile()
        snapshot = mock_workspace_snapshot()
        bundle = workspace_snapshot_to_evidence(snapshot)
        report = build_workspace_context_report(provider, snapshot, bundle, policy_status="pass")
        self.assertEqual(report.policy_status, "pass")
        self.assertEqual(report.evidence_bundle_id, bundle.bundle_id)


# ═══════════════════════════════════════════════════════════════════════
# CLI Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceCLI(unittest.TestCase):

    def setUp(self):
        self.cli_path = os.path.join(V3_ROOT, "cli", "systemkernel.py")
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = ROOT

    def _run(self, *args):
        return subprocess.run(
            [PYTHON, self.cli_path, *args],
            capture_output=True, text=True, timeout=60,
            cwd=ROOT, env=self.env,
        )

    def test_78_cli_profiles(self):
        result = self._run("workspace", "profiles")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Workspace Context Plane", result.stdout)
        self.assertIn("deterministic_mock_workspace", result.stdout)
        self.assertIn("continue_workspace_context", result.stdout)

    def test_79_cli_profiles_shows_blocked(self):
        result = self._run("workspace", "profiles")
        self.assertIn("NO", result.stdout)

    def test_80_cli_mock(self):
        result = self._run("workspace", "mock", "--files", "4", "--diagnostics", "3")
        self.assertEqual(result.returncode, 0)
        self.assertIn("File refs", result.stdout)
        self.assertIn("Diagnostics", result.stdout)

    def test_81_cli_mock_truth_source_false(self):
        result = self._run("workspace", "mock")
        self.assertIn("false", result.stdout.lower())

    def test_82_cli_evidence(self):
        result = self._run("workspace", "evidence")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Evidence bundle", result.stdout)
        self.assertIn("false", result.stdout.lower())

    def test_83_cli_mock_unknown_provider(self):
        result = self._run("workspace", "mock", "--provider", "nonexistent")
        self.assertNotEqual(result.returncode, 0)


# ═══════════════════════════════════════════════════════════════════════
# Invariants Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWorkspaceInvariants(unittest.TestCase):

    def test_84_no_banned_imports(self):
        """Scan workspace files for banned imports."""
        banned = {
            "openai", "anthropic", "langchain", "llamaindex",
            "continue", "cline", "roo",
            "vscode", "ide",
            "watchdog", "pyinotify",
        }
        for fname in ("workspace_context.py", "workspace_context_policy.py",
                      "workspace_context_profiles.py"):
            fpath = os.path.join(EXTERNAL_DIR, fname)
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name.split(".")[0]
                        self.assertNotIn(name, banned,
                                         f"{fname} imports banned: {name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        name = node.module.split(".")[0]
                        self.assertNotIn(name, banned,
                                         f"{fname} imports banned: {name}")

    def test_85_all_truth_source_fields_false(self):
        provider = WorkspaceProvider(provider_id="test")
        self.assertFalse(provider.truth_source)
        snapshot = mock_workspace_snapshot()
        self.assertFalse(snapshot.truth_source)

    def test_86_fixture_file_exists(self):
        fixture_path = os.path.join(FIXTURE_DIR, "workspace_context_input.json")
        self.assertTrue(os.path.exists(fixture_path))
        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("root_path", data)
        self.assertIn("fixture_hash", data)


# ═══════════════════════════════════════════════════════════════════════
# Regression Tests
# ═══════════════════════════════════════════════════════════════════════

class TestPhase7Regression(unittest.TestCase):

    def test_v4_baseline_guard_passes(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_v4_baseline_guard.py")],
            capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Baseline guard failed:\n{result.stderr[:1000]}")

    def test_kernel_invariants_passes(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_kernel_invariants.py")],
            capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Kernel invariants failed:\n{result.stderr[:1000]}")
        self.assertIn("purity_score == 100", result.stdout)

    def test_evidence_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_external_evidence.py")],
            capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Evidence tests failed:\n{result.stderr[:1000]}")

    def test_registry_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_capability_registry.py")],
            capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Registry tests failed:\n{result.stderr[:1000]}")

    def test_contract_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_capability_contract.py")],
            capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Contract tests failed:\n{result.stderr[:1000]}")

    def test_agent_worker_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_agent_worker_plane.py")],
            capture_output=True, text=True, timeout=600, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Agent worker tests failed:\n{result.stderr[:1000]}")

    def test_memory_intelligence_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_memory_intelligence_plane.py")],
            capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Memory intelligence tests failed:\n{result.stderr[:1000]}")

    def test_developer_cli_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_developer_cli.py")],
            capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Developer CLI tests failed:\n{result.stderr[:1000]}")


if __name__ == "__main__":
    unittest.main()
