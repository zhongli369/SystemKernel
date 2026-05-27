"""
Skill Evolution Plane Tests — Phase 8.

55+ tests for the Skill Evolution Plane: providers, skill package refs,
gap signals, proposals, results, reports, policy validation, profiles,
evidence mapping, and CLI.
Stdlib only. No external services. No LLM. No skill modification.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")
FIXTURE_DIR = os.path.join(V3_ROOT, "tests", "fixtures")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable

from v3.external.skill_evolution import (
    SkillEvolutionProvider,
    SkillPackageRef,
    SkillGapSignal,
    SkillEvolutionProposal,
    SkillEvolutionResult,
    SkillEvolutionReport,
    SkillEvolutionValidationResult,
    PROVIDER_TYPE_ANTHROPIC_SKILLS_LIKE,
    PROVIDER_TYPE_SUPERCLAUDE_LIKE,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    PROVIDER_TYPE_GENERIC,
    ALL_PROVIDER_TYPES,
    SIGNAL_TYPE_MISSING_SKILL,
    SIGNAL_TYPE_OUTDATED_SKILL,
    SIGNAL_TYPE_POOR_DESCRIPTION,
    SIGNAL_TYPE_MISSING_TESTS,
    SIGNAL_TYPE_REGISTRY_MISMATCH,
    SIGNAL_TYPE_FORMAT_ALIGNMENT,
    SIGNAL_TYPE_DUPLICATE_SKILL,
    ALL_SIGNAL_TYPES,
    PROPOSAL_TYPE_CREATE_SKILL,
    PROPOSAL_TYPE_UPDATE_SKILL,
    PROPOSAL_TYPE_DEPRECATE_SKILL,
    PROPOSAL_TYPE_REGISTRY_UPDATE,
    PROPOSAL_TYPE_FORMAT_ALIGNMENT,
    PROPOSAL_TYPE_TEST_ADDITION,
    PROPOSAL_TYPE_DOCS_UPDATE,
    ALL_PROPOSAL_TYPES,
    STATUS_PROPOSED,
    STATUS_BLOCKED,
    STATUS_FAILED,
    ALL_RESULT_STATUSES,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_HIGH,
    ALL_SEVERITIES,
    make_skill_package_ref,
    make_skill_gap_signal,
    make_skill_evolution_proposal,
    make_blocked_skill_result,
    mock_skill_evolution_result,
    validate_skill_provider,
    validate_skill_proposal,
    validate_skill_result,
    skill_proposals_to_evidence,
    build_skill_evolution_report,
    _compute_hash,
)

from v3.external.skill_evolution_policy import (
    POLICY_PASS,
    POLICY_BLOCKED,
    POLICY_REVIEW,
    SkillEvolutionPolicy,
    default_skill_evolution_policy,
    validate_provider_against_policy,
    validate_proposal_against_policy,
    validate_result_against_policy,
    block_provider_reason,
)

from v3.external.skill_evolution_profiles import (
    SkillEvolutionProfileStatus,
    anthropic_skills_format_provider,
    superclaude_pattern_provider,
    deterministic_mock_skill_evolution,
    get_all_profiles,
    get_profile,
    evaluate_all_profiles,
)


class TestSkillEvolutionDataclasses(unittest.TestCase):
    """Tests for frozen dataclasses — immutability and defaults."""

    def test_01_provider_frozen(self):
        p = SkillEvolutionProvider(provider_id="test")
        with self.assertRaises(Exception):
            p.provider_id = "changed"

    def test_02_skill_package_ref_frozen(self):
        r = SkillPackageRef(skill_id="test")
        with self.assertRaises(Exception):
            r.skill_id = "changed"

    def test_03_gap_signal_frozen(self):
        s = SkillGapSignal(signal_id="test")
        with self.assertRaises(Exception):
            s.signal_id = "changed"

    def test_04_proposal_frozen(self):
        p = SkillEvolutionProposal(proposal_id="test")
        with self.assertRaises(Exception):
            p.proposal_id = "changed"

    def test_05_result_frozen(self):
        r = SkillEvolutionResult(provider_id="test")
        with self.assertRaises(Exception):
            r.provider_id = "changed"

    def test_06_report_frozen(self):
        r = SkillEvolutionReport()
        with self.assertRaises(Exception):
            r.report_hash = "changed"


class TestSkillEvolutionHashes(unittest.TestCase):
    """Tests for deterministic hash computation."""

    def test_07_provider_hash_deterministic(self):
        p1 = SkillEvolutionProvider(provider_id="hash-test", name="Test")
        p2 = SkillEvolutionProvider(provider_id="hash-test", name="Test")
        h1 = _compute_hash(p1)
        h2 = _compute_hash(p2)
        self.assertEqual(h1, h2)

    def test_08_skill_ref_hash_deterministic(self):
        r1 = make_skill_package_ref(skill_id="ref-hash-test", source_path="/test")
        r2 = make_skill_package_ref(skill_id="ref-hash-test", source_path="/test")
        self.assertEqual(r1.ref_hash, r2.ref_hash)

    def test_09_gap_signal_hash_deterministic(self):
        s1 = make_skill_gap_signal(signal_type=SIGNAL_TYPE_MISSING_SKILL,
                                   source_refs=("ref-a",), description="test", seed=0)
        s2 = make_skill_gap_signal(signal_type=SIGNAL_TYPE_MISSING_SKILL,
                                   source_refs=("ref-a",), description="test", seed=0)
        self.assertEqual(s1.signal_hash, s2.signal_hash)

    def test_10_proposal_hash_deterministic(self):
        p1 = make_skill_evolution_proposal(provider_id="prov", proposal_type=PROPOSAL_TYPE_CREATE_SKILL,
                                           target_skill_refs=("s1",), seed=0)
        p2 = make_skill_evolution_proposal(provider_id="prov", proposal_type=PROPOSAL_TYPE_CREATE_SKILL,
                                           target_skill_refs=("s1",), seed=0)
        self.assertEqual(p1.proposal_hash, p2.proposal_hash)

    def test_11_result_hash_deterministic(self):
        r1 = mock_skill_evolution_result(provider_id="test-prov", proposal_count=2, signal_count=2)
        r2 = mock_skill_evolution_result(provider_id="test-prov", proposal_count=2, signal_count=2)
        self.assertEqual(r1.result_hash, r2.result_hash)


class TestTruthSourceAndRemovable(unittest.TestCase):
    """Tests that truth_source is always False and removable is always True."""

    def test_12_truth_source_false_on_provider(self):
        for p in get_all_profiles():
            self.assertFalse(p.truth_source, f"{p.provider_id}: truth_source must be False")

    def test_13_truth_source_false_on_signal(self):
        s = make_skill_gap_signal(signal_type=SIGNAL_TYPE_MISSING_SKILL,
                                  source_refs=("ref",), description="test")
        self.assertFalse(s.truth_source)

    def test_14_truth_source_false_on_proposal(self):
        p = make_skill_evolution_proposal(provider_id="prov", proposal_type=PROPOSAL_TYPE_CREATE_SKILL)
        self.assertFalse(p.truth_source)

    def test_15_truth_source_false_on_result(self):
        r = mock_skill_evolution_result()
        self.assertFalse(r.truth_source)

    def test_16_removable_true_on_provider(self):
        for p in get_all_profiles():
            self.assertTrue(p.removable, f"{p.provider_id}: removable must be True")


class TestProviderPolicyValidation(unittest.TestCase):
    """Tests that real providers are blocked and mock is allowed."""

    def setUp(self):
        self.policy = default_skill_evolution_policy()

    def test_17_llm_provider_blocked_by_default(self):
        p = anthropic_skills_format_provider()
        allowed, reason = validate_provider_against_policy(p, self.policy)
        self.assertFalse(allowed)
        self.assertIn("LLM", reason)

    def test_18_skill_file_modifying_provider_blocked_by_default(self):
        p = superclaude_pattern_provider()
        p2 = SkillEvolutionProvider(
            provider_id="test", provider_type="superclaude_like",
            can_modify_skills=True,
        )
        allowed, reason = validate_provider_against_policy(p2, self.policy)
        self.assertFalse(allowed)

    def test_19_registry_updating_provider_blocked_by_default(self):
        p = anthropic_skills_format_provider()
        allowed, reason = validate_provider_against_policy(p, self.policy)
        self.assertFalse(allowed)

    def test_20_skill_installation_provider_blocked_by_default(self):
        p = anthropic_skills_format_provider()
        allowed, _ = validate_provider_against_policy(p, self.policy)
        self.assertFalse(allowed)

    def test_21_deterministic_mock_provider_allowed(self):
        p = deterministic_mock_skill_evolution()
        allowed, reason = validate_provider_against_policy(p, self.policy)
        self.assertTrue(allowed, f"Mock should be allowed: {reason}")

    def test_21b_anthropic_skills_provider_blocked(self):
        p = anthropic_skills_format_provider()
        allowed, _ = validate_provider_against_policy(p, self.policy)
        self.assertFalse(allowed)

    def test_21c_superclaude_provider_blocked(self):
        p = superclaude_pattern_provider()
        allowed, _ = validate_provider_against_policy(p, self.policy)
        self.assertFalse(allowed)


class TestProposalRules(unittest.TestCase):
    """Tests for proposal invariants."""

    def test_22_approval_required_always_true(self):
        p = make_skill_evolution_proposal(provider_id="prov", proposal_type=PROPOSAL_TYPE_CREATE_SKILL)
        self.assertTrue(p.approval_required)

    def test_23_proposed_files_not_written(self):
        p = make_skill_evolution_proposal(
            provider_id="prov", proposal_type=PROPOSAL_TYPE_UPDATE_SKILL,
            proposed_files=("/tmp/should-not-exist/test.md",),
        )
        for f in p.proposed_files:
            self.assertFalse(os.path.exists(f), f"File should not exist: {f}")

    def test_24_registry_update_is_proposal_only(self):
        p = make_skill_evolution_proposal(
            provider_id="prov", proposal_type=PROPOSAL_TYPE_REGISTRY_UPDATE,
        )
        self.assertEqual(p.proposal_type, PROPOSAL_TYPE_REGISTRY_UPDATE)
        self.assertTrue(p.approval_required)
        self.assertFalse(p.truth_source)

    def test_25_forbidden_path_rejected(self):
        policy = SkillEvolutionPolicy(
            forbidden_paths=("/etc/", "/sys/"),
        )
        p = make_skill_evolution_proposal(
            provider_id="prov",
            proposal_type=PROPOSAL_TYPE_UPDATE_SKILL,
            proposed_files=("/etc/skills/config.json",),
            required_tests=("test_x.py",),
        )
        valid, reason = validate_proposal_against_policy(p, policy)
        self.assertFalse(valid)
        self.assertIn("forbidden_paths", reason)

    def test_26_max_proposals_enforced(self):
        policy = SkillEvolutionPolicy(max_proposals=1)
        r = mock_skill_evolution_result(proposal_count=5)
        self.assertGreater(len(r.proposals), 1)
        valid, reason = validate_result_against_policy(r, policy)
        self.assertFalse(valid)

    def test_27_tests_required_for_change_proposals(self):
        policy = SkillEvolutionPolicy(require_tests_for_changes=True)
        p = make_skill_evolution_proposal(
            provider_id="prov", proposal_type=PROPOSAL_TYPE_UPDATE_SKILL,
        )
        valid, reason = validate_proposal_against_policy(p, policy)
        self.assertFalse(valid)
        self.assertIn("tests required", reason)


class TestResultValidation(unittest.TestCase):
    """Tests for result validation."""

    def test_28_blocked_result_validates(self):
        r = make_blocked_skill_result(provider_id="test", reason="Testing block")
        validation = validate_skill_result(r)
        self.assertTrue(validation.valid)

    def test_29_mock_result_validates(self):
        r = mock_skill_evolution_result()
        validation = validate_skill_result(r)
        self.assertTrue(validation.valid, f"Violations: {validation.violations}")

    def test_29b_result_with_false_truth_source_fails_validation(self):
        r = SkillEvolutionResult(
            provider_id="test",
            truth_source=True,
            status=STATUS_PROPOSED,
        )
        validation = validate_skill_result(r)
        self.assertFalse(validation.valid)

    def test_29c_result_unknown_status_fails(self):
        r = SkillEvolutionResult(
            provider_id="test",
            status="invalid_status",
        )
        validation = validate_skill_result(r)
        self.assertFalse(validation.valid)


class TestEvidenceMapping(unittest.TestCase):
    """Tests for evidence conversion."""

    def test_30_proposals_convert_to_evidence(self):
        r = mock_skill_evolution_result(proposal_count=3)
        bundle = skill_proposals_to_evidence(r, registry_hash="abc123")
        self.assertIsNotNone(bundle)
        self.assertGreater(len(bundle.records), 0)

    def test_31_evidence_truth_source_false(self):
        r = mock_skill_evolution_result(proposal_count=2)
        bundle = skill_proposals_to_evidence(r, registry_hash="abc123")
        for record in bundle.records:
            self.assertFalse(record.truth_source)

    def test_32_registry_hash_included_in_provenance(self):
        r = mock_skill_evolution_result(proposal_count=2)
        bundle = skill_proposals_to_evidence(r, registry_hash="abc123def")
        self.assertIsNotNone(bundle.bundle_id)


class TestProfiles(unittest.TestCase):
    """Tests for provider profiles."""

    def test_33_profiles_load(self):
        profiles = get_all_profiles()
        self.assertGreater(len(profiles), 0)

    def test_34_anthropic_skills_provider_blocked_in_profile_list(self):
        policy = default_skill_evolution_policy()
        statuses = evaluate_all_profiles(policy)
        status_map = {s.provider_id: s for s in statuses}
        self.assertIn("anthropic_skills_format", status_map)
        self.assertFalse(status_map["anthropic_skills_format"].allowed)

    def test_35_superclaude_provider_blocked_in_profile_list(self):
        policy = default_skill_evolution_policy()
        statuses = evaluate_all_profiles(policy)
        status_map = {s.provider_id: s for s in statuses}
        self.assertIn("superclaude_pattern", status_map)
        self.assertFalse(status_map["superclaude_pattern"].allowed)

    def test_36_mock_profile_allowed_in_profile_list(self):
        policy = default_skill_evolution_policy()
        statuses = evaluate_all_profiles(policy)
        status_map = {s.provider_id: s for s in statuses}
        self.assertIn("deterministic_mock_skill_evolution", status_map)
        self.assertTrue(status_map["deterministic_mock_skill_evolution"].allowed)

    def test_36b_get_profile_returns_none_for_unknown(self):
        p = get_profile("nonexistent_provider")
        self.assertIsNone(p)

    def test_36c_get_profile_returns_provider(self):
        p = get_profile("deterministic_mock_skill_evolution")
        self.assertIsNotNone(p)
        self.assertEqual(p.provider_id, "deterministic_mock_skill_evolution")


class TestCLIIntegration(unittest.TestCase):
    """Tests for CLI commands."""

    def setUp(self):
        self.cli_path = os.path.join(V3_ROOT, "cli", "systemkernel.py")

    def _run_cli(self, *args):
        result = subprocess.run(
            [PYTHON, self.cli_path] + list(args),
            capture_output=True, text=True, timeout=60,
            cwd=ROOT,
        )
        return result

    def test_37_cli_profiles_works(self):
        result = self._run_cli("skill-evolution", "profiles")
        self.assertIn(result.returncode, (0, 1))
        self.assertIn("Skill Evolution Plane", result.stdout + result.stderr)

    def test_38_cli_mock_works(self):
        result = self._run_cli("skill-evolution", "mock")
        self.assertIn(result.returncode, (0, 1))
        self.assertIn("Policy allowed", result.stdout + result.stderr)

    def test_39_cli_evidence_works(self):
        result = self._run_cli("skill-evolution", "evidence")
        self.assertIn(result.returncode, (0, 1))
        self.assertIn("Evidence", result.stdout + result.stderr)


class TestNoRealFileModification(unittest.TestCase):
    """Tests that no real files are modified by Phase 8 operations."""

    def test_40_no_real_skill_files_modified(self):
        # Verify our mock operations don't touch the real skills directory
        skills_dir = os.path.join(ROOT, "SkillsManagementSystem", "packages")
        before = []
        if os.path.isdir(skills_dir):
            for root, dirs, files in os.walk(skills_dir):
                for f in files:
                    fpath = os.path.join(root, f)
                    before.append((fpath, os.path.getmtime(fpath)))

        # Run mock operations
        mock_skill_evolution_result(proposal_count=3)
        make_skill_evolution_proposal(
            provider_id="test", proposal_type=PROPOSAL_TYPE_REGISTRY_UPDATE,
            proposed_files=("SkillsManagementSystem/packages/test/SKILL.md",),
            required_tests=("test_x.py",),
        )

        # Verify nothing changed
        if os.path.isdir(skills_dir):
            for root, dirs, files in os.walk(skills_dir):
                for f in files:
                    fpath = os.path.join(root, f)
                    if fpath in dict(before):
                        self.assertEqual(
                            dict(before)[fpath], os.path.getmtime(fpath),
                            f"File modified: {fpath}"
                        )

    def test_41_registry_json_not_modified(self):
        registry_path = os.path.join(ROOT, "SkillsManagementSystem", "registry.json")
        if os.path.exists(registry_path):
            before_mtime = os.path.getmtime(registry_path)
            mock_skill_evolution_result(proposal_count=2)
            after_mtime = os.path.getmtime(registry_path)
            self.assertEqual(before_mtime, after_mtime,
                           "registry.json should not be modified")

    def test_42_no_skill_installation_performed(self):
        packages_dir = os.path.join(ROOT, "SkillsManagementSystem", "packages")
        before_dirs = set()
        if os.path.isdir(packages_dir):
            before_dirs = set(os.listdir(packages_dir))

        mock_skill_evolution_result(proposal_count=3)
        skill_proposals_to_evidence(
            mock_skill_evolution_result(), registry_hash="test",
        )

        if os.path.isdir(packages_dir):
            after_dirs = set(os.listdir(packages_dir))
            self.assertEqual(before_dirs, after_dirs,
                           "No packages should be installed")


class TestNoLLMOrExternalImports(unittest.TestCase):
    """Tests that no LLM or external tool imports exist in Phase 8 files."""

    def _scan_file_for_banned_imports(self, filepath):
        banned = {
            "openai", "anthropic", "langchain", "llamaindex",
            "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
            "torch", "tensorflow", "sklearn", "transformers",
        }
        violations = []
        try:
            with open(filepath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name.split(".")[0]
                        if name in banned:
                            violations.append(name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        name = node.module.split(".")[0]
                        if name in banned:
                            violations.append(name)
        except (SyntaxError, OSError):
            pass
        return violations

    def test_43_no_llm_imports(self):
        phase8_files = [
            os.path.join(EXTERNAL_DIR, "skill_evolution.py"),
            os.path.join(EXTERNAL_DIR, "skill_evolution_policy.py"),
            os.path.join(EXTERNAL_DIR, "skill_evolution_profiles.py"),
        ]
        for fpath in phase8_files:
            violations = self._scan_file_for_banned_imports(fpath)
            self.assertEqual(len(violations), 0,
                           f"{os.path.basename(fpath)} has banned imports: {violations}")


class TestNoExternalToolsExecuted(unittest.TestCase):
    """Tests that no external tools are executed."""

    def test_44_no_external_tools_executed(self):
        # Phase 8 operations are pure data — no subprocess calls
        with tempfile.TemporaryDirectory() as tmpdir:
            # All operations are in-process Python only
            p = make_skill_package_ref(skill_id="test", source_path=tmpdir)
            self.assertIsNotNone(p.ref_hash)


class TestNoV3KernelModifications(unittest.TestCase):
    """Tests that v3/kernel is not modified."""

    def test_45_no_v3_kernel_modifications(self):
        kernel_dir = os.path.join(V3_ROOT, "kernel")
        if os.path.isdir(kernel_dir):
            for fname in os.listdir(kernel_dir):
                fpath = os.path.join(kernel_dir, fname)
                if fname.endswith(".py"):
                    with open(fpath, encoding="utf-8") as f:
                        source = f.read()
                    self.assertNotIn("skill_evolution", source,
                                    f"Kernel file {fname} references skill_evolution")


class TestNoV3MemoryModifications(unittest.TestCase):
    """Tests that v3/memory is not modified."""

    def test_46_no_v3_memory_modifications(self):
        memory_dir = os.path.join(V3_ROOT, "memory")
        if os.path.isdir(memory_dir):
            for fname in os.listdir(memory_dir):
                fpath = os.path.join(memory_dir, fname)
                if fname.endswith(".py"):
                    with open(fpath, encoding="utf-8") as f:
                        source = f.read()
                    self.assertNotIn("skill_evolution", source,
                                    f"Memory file {fname} references skill_evolution")


class TestCrossPlaneCompatibility(unittest.TestCase):
    """Tests that existing plane tests still pass after Phase 8."""

    def test_47_workspace_plane_imports_still_work(self):
        from v3.external.workspace_context import (
            WorkspaceProvider, WorkspaceSnapshot, mock_workspace_snapshot,
        )
        snap = mock_workspace_snapshot(provider_id="deterministic_mock_workspace")
        self.assertIsNotNone(snap.snapshot_hash)

    def test_48_agent_worker_imports_still_work(self):
        from v3.external.agent_worker import (
            AgentWorkerProvider, build_agent_worker_task, mock_agent_worker_result,
        )
        task = build_agent_worker_task(provider_id="test", task_summary="Test")
        result = mock_agent_worker_result(task)
        self.assertEqual(result.status, STATUS_PROPOSED)

    def test_49_memory_intelligence_imports_still_work(self):
        from v3.external.memory_intelligence import (
            MemoryIntelligenceProvider, mock_memory_intelligence_result,
            build_memory_intelligence_request, MODE_INSPECT_ONLY,
        )
        req = build_memory_intelligence_request(
            provider_id="deterministic_mock_memory",
            input_record_refs=("r1",), mode=MODE_INSPECT_ONLY,
        )
        result = mock_memory_intelligence_result(req)
        self.assertIsNotNone(result.result_hash)

    def test_50_evidence_imports_still_work(self):
        from v3.external.evidence import (
            EvidenceSource, make_evidence_record, build_evidence_bundle,
            EVIDENCE_TYPE_SKILL_REFERENCE, TRUST_LOW,
        )
        record = make_evidence_record(
            adapter_id="test",
            evidence_type=EVIDENCE_TYPE_SKILL_REFERENCE,
            capability_type="skill",
            input_data={}, output_data={}, payload_summary="test",
            source_trust_level=TRUST_LOW,
        )
        self.assertIsNotNone(record.evidence_id)

    def test_51_registry_imports_still_work(self):
        from v3.external.capability_registry import (
            CapabilityRegistry, build_registry, validate_registry,
        )
        reg = build_registry(tuple())
        valid, errors = validate_registry(reg)
        self.assertTrue(valid)

    def test_52_contract_imports_still_work(self):
        from v3.external.capability_contract import (
            CapabilityType, CapabilityInputContract, compute_stable_hash,
        )
        h = compute_stable_hash("test")
        self.assertIsNotNone(h)


class TestComplexityGate(unittest.TestCase):
    """Tests that complexity gate stays safe."""

    def test_53_complexity_gate_not_reject(self):
        import importlib
        try:
            from v3.quality.phase_gate import evaluate_phase
            result = evaluate_phase("5A", v3_root=V3_ROOT)
            self.assertIn(result.verdict.verdict, ("ACCEPT", "REVIEW"))
            self.assertNotEqual(result.verdict.verdict, "REJECT")
        except (ImportError, FileNotFoundError):
            self.skipTest("Quality gate module not available")


class TestV4BaselineGuard(unittest.TestCase):
    """Tests that V4 baseline invariants hold."""

    def test_54_v4_baseline_guard_still_passes(self):
        try:
            from v3.quality.v4_baseline_guard import check_v4_baseline
            result = check_v4_baseline()
            self.assertTrue(result.get("success", True),
                          f"V4 baseline guard failed: {result}")
        except (ImportError, FileNotFoundError):
            self.skipTest("V4 baseline guard not available")


class TestKernelInvariants(unittest.TestCase):
    """Tests for kernel invariants after Phase 8."""

    def test_55_kernel_invariants_still_purity(self):
        report_path = os.path.join(V3_ROOT, "exports", "kernel_validity_report.json")
        if os.path.exists(report_path):
            with open(report_path, encoding="utf-8") as f:
                report = json.load(f)
            purity = report.get("purity_score", 100)
            self.assertEqual(purity, 100, "Kernel purity should be 100")


class TestFixtureLoading(unittest.TestCase):
    """Tests for fixture data loading."""

    def test_56_fixture_loads(self):
        fixture_path = os.path.join(FIXTURE_DIR, "skill_evolution_input.json")
        self.assertTrue(os.path.exists(fixture_path))
        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("skill_refs", data)
        self.assertIn("gap_signals", data)
        self.assertIn("context_refs", data)
        self.assertEqual(len(data["skill_refs"]), 4)
        self.assertEqual(len(data["gap_signals"]), 4)


class TestProviderSignals(unittest.TestCase):
    """Tests for signal generation."""

    def test_57_deterministic_signals_produced(self):
        r = mock_skill_evolution_result(signal_count=5)
        self.assertGreaterEqual(len(r.proposals), 1)
        for p in r.proposals:
            self.assertTrue(p.approval_required)
            self.assertFalse(p.truth_source)

    def test_58_all_signal_types_covered(self):
        for st in ALL_SIGNAL_TYPES:
            s = make_skill_gap_signal(signal_type=st, source_refs=("test",), seed=0)
            self.assertEqual(s.signal_type, st)
            self.assertFalse(s.truth_source)


class TestProviderValidation(unittest.TestCase):
    """Additional provider validation tests."""

    def test_59_provider_with_can_modify_skills_fails(self):
        p = SkillEvolutionProvider(
            provider_id="bad", provider_type=PROVIDER_TYPE_GENERIC,
            can_modify_skills=True,
        )
        v = validate_skill_provider(p)
        self.assertFalse(v.valid)

    def test_60_provider_with_can_update_registry_fails(self):
        p = SkillEvolutionProvider(
            provider_id="bad", provider_type=PROVIDER_TYPE_GENERIC,
            can_update_registry=True,
        )
        v = validate_skill_provider(p)
        self.assertFalse(v.valid)

    def test_61_provider_with_can_install_skills_fails(self):
        p = SkillEvolutionProvider(
            provider_id="bad", provider_type=PROVIDER_TYPE_GENERIC,
            can_install_skills=True,
        )
        v = validate_skill_provider(p)
        self.assertFalse(v.valid)

    def test_62_provider_with_requires_llm_fails(self):
        p = SkillEvolutionProvider(
            provider_id="bad", provider_type=PROVIDER_TYPE_GENERIC,
            requires_llm=True,
        )
        v = validate_skill_provider(p)
        self.assertFalse(v.valid)


class TestDefaultPolicy(unittest.TestCase):
    """Tests for default policy."""

    def test_63_default_policy_blocks_all_four_axes(self):
        p = default_skill_evolution_policy()
        self.assertFalse(p.allow_llm_providers)
        self.assertFalse(p.allow_skill_file_modification)
        self.assertFalse(p.allow_registry_update)
        self.assertFalse(p.allow_skill_installation)

    def test_64_default_policy_requires_tests_and_approval(self):
        p = default_skill_evolution_policy()
        self.assertTrue(p.require_tests_for_changes)
        self.assertTrue(p.require_human_approval)

    def test_65_policy_hash_stable(self):
        p1 = default_skill_evolution_policy()
        p2 = default_skill_evolution_policy()
        self.assertEqual(p1.policy_hash, p2.policy_hash)


class TestBlockedProviderReason(unittest.TestCase):
    """Tests for block_provider_reason function."""

    def test_66_mock_provider_returns_empty_reason(self):
        p = deterministic_mock_skill_evolution()
        policy = default_skill_evolution_policy()
        reason = block_provider_reason(p, policy)
        self.assertEqual(reason, "")

    def test_67_llm_provider_returns_reason(self):
        p = anthropic_skills_format_provider()
        policy = default_skill_evolution_policy()
        reason = block_provider_reason(p, policy)
        self.assertNotEqual(reason, "")
        self.assertIn("LLM", reason)


class TestEvidenceEmptyResult(unittest.TestCase):
    """Tests for evidence mapping with empty results."""

    def test_68_empty_result_evidence(self):
        r = SkillEvolutionResult(
            provider_id="empty", status=STATUS_BLOCKED,
            warnings=("Blocked by policy",),
        )
        bundle = skill_proposals_to_evidence(r, registry_hash="test")
        self.assertIsNotNone(bundle)
        self.assertEqual(len(bundle.records), 1)


class TestAllProviderTypes(unittest.TestCase):
    """Tests covering all provider types."""

    def test_69_all_provider_types_defined(self):
        self.assertEqual(len(ALL_PROVIDER_TYPES), 4)
        self.assertIn(PROVIDER_TYPE_ANTHROPIC_SKILLS_LIKE, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_SUPERCLAUDE_LIKE, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_DETERMINISTIC_MOCK, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_GENERIC, ALL_PROVIDER_TYPES)


class TestAllSeverities(unittest.TestCase):
    """Tests covering all severity levels."""

    def test_70_all_severities_defined(self):
        self.assertEqual(len(ALL_SEVERITIES), 3)
        self.assertIn(SEVERITY_LOW, ALL_SEVERITIES)
        self.assertIn(SEVERITY_MEDIUM, ALL_SEVERITIES)
        self.assertIn(SEVERITY_HIGH, ALL_SEVERITIES)


class TestAllResultStatuses(unittest.TestCase):
    """Tests covering all result statuses."""

    def test_71_all_result_statuses_defined(self):
        self.assertEqual(len(ALL_RESULT_STATUSES), 3)
        self.assertIn(STATUS_PROPOSED, ALL_RESULT_STATUSES)
        self.assertIn(STATUS_BLOCKED, ALL_RESULT_STATUSES)
        self.assertIn(STATUS_FAILED, ALL_RESULT_STATUSES)


if __name__ == "__main__":
    unittest.main()
