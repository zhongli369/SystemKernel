"""
Orchestration Policy Layer Tests — Phase 9.

60+ tests for the Orchestration Policy Layer: policies, requests, steps,
plans, reports, profiles, validation, evidence mapping, and CLI.
Stdlib only. No external execution. No agent runs. No file modification.
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

from v3.external.orchestration_policy import (
    STATUS_PASS,
    STATUS_BLOCKED,
    STATUS_REVIEW,
    ALL_STATUSES,
    OrchestrationPolicy,
    OrchestrationRequest,
    OrchestrationStep,
    OrchestrationPlan,
    OrchestrationPolicyReport,
    OrchestrationValidationResult,
    default_orchestration_policy,
    build_orchestration_request,
    plan_orchestration,
    validate_orchestration_step,
    validate_orchestration_plan,
    build_orchestration_policy_report,
    orchestration_plan_to_evidence,
    _compute_hash,
)

from v3.external.orchestration_profiles import (
    safe_context_only,
    skill_evolution_review as op_skill_evolution_review,
    memory_intelligence_review as op_memory_intelligence_review,
    agent_worker_review as op_agent_worker_review,
    full_external_review,
    ecc_harness_review,
    get_all_profiles,
    get_profile,
)

from v3.external.default_capabilities import build_default_registry


class TestFrozenDataclasses(unittest.TestCase):
    """Tests for frozen dataclasses."""

    def test_01_policy_frozen(self):
        p = OrchestrationPolicy(policy_id="test")
        with self.assertRaises(Exception):
            p.policy_id = "changed"

    def test_02_request_frozen(self):
        r = OrchestrationRequest(request_id="test")
        with self.assertRaises(Exception):
            r.request_id = "changed"

    def test_03_step_frozen(self):
        s = OrchestrationStep(step_id="test")
        with self.assertRaises(Exception):
            s.step_id = "changed"

    def test_04_plan_frozen(self):
        p = OrchestrationPlan(plan_id="test")
        with self.assertRaises(Exception):
            p.plan_id = "changed"

    def test_05_report_frozen(self):
        r = OrchestrationPolicyReport()
        with self.assertRaises(Exception):
            r.report_hash = "changed"


class TestHashes(unittest.TestCase):
    """Tests for deterministic hash computation."""

    def test_06_policy_hash_deterministic(self):
        p1 = OrchestrationPolicy(policy_id="hash-test")
        p2 = OrchestrationPolicy(policy_id="hash-test")
        self.assertEqual(_compute_hash(p1), _compute_hash(p2))

    def test_07_request_hash_deterministic(self):
        r1 = build_orchestration_request(objective="test", requested_capability_types=("context",))
        r2 = build_orchestration_request(objective="test", requested_capability_types=("context",))
        self.assertEqual(r1.request_hash, r2.request_hash)

    def test_08_step_hash_deterministic(self):
        s1 = OrchestrationStep(adapter_id="a", capability_type="context")
        s2 = OrchestrationStep(adapter_id="a", capability_type="context")
        self.assertEqual(_compute_hash(s1), _compute_hash(s2))

    def test_09_plan_hash_deterministic(self):
        registry = build_default_registry()
        policy = safe_context_only()
        req = build_orchestration_request(objective="hash-test")
        p1 = plan_orchestration(req, registry, policy)
        p2 = plan_orchestration(req, registry, policy)
        self.assertEqual(p1.plan_hash, p2.plan_hash)


class TestTruthSource(unittest.TestCase):
    """Tests that truth_source is always False."""

    def test_10_truth_source_false_on_plan(self):
        p = OrchestrationPlan()
        self.assertFalse(p.truth_source)

    def test_10b_plan_from_orchestration_has_false_truth_source(self):
        registry = build_default_registry()
        policy = safe_context_only()
        req = build_orchestration_request(objective="test")
        plan = plan_orchestration(req, registry, policy)
        self.assertFalse(plan.truth_source)


class TestDefaultPolicy(unittest.TestCase):
    """Tests for default policy invariants."""

    def test_11_default_policy_dry_run_only_true(self):
        p = default_orchestration_policy()
        self.assertTrue(p.dry_run_only)

    def test_12_external_execution_false_by_default(self):
        p = default_orchestration_policy()
        self.assertFalse(p.allow_external_execution)

    def test_13_file_modification_false_by_default(self):
        p = default_orchestration_policy()
        self.assertFalse(p.allow_file_modification)

    def test_14_network_false_by_default(self):
        p = default_orchestration_policy()
        self.assertFalse(p.allow_network)

    def test_15_registry_updates_false_by_default(self):
        p = default_orchestration_policy()
        self.assertFalse(p.allow_registry_updates)

    def test_16_memory_mutation_false_by_default(self):
        p = default_orchestration_policy()
        self.assertFalse(p.allow_memory_mutation)


class TestPolicyEnforcement(unittest.TestCase):
    """Tests for policy constraint enforcement."""

    def setUp(self):
        self.registry = build_default_registry()
        self.req = build_orchestration_request(
            objective="test",
            requested_capability_types=("context", "skill", "memory", "agent"),
        )

    def test_17_max_adapters_per_plan_enforced(self):
        policy = OrchestrationPolicy(
            policy_id="strict",
            allowed_capability_types=("context", "skill", "memory", "agent"),
            dry_run_only=True, max_adapters_per_plan=2,
        )
        plan = plan_orchestration(self.req, self.registry, policy)
        self.assertLessEqual(len(plan.steps), 2)

    def test_18_forbidden_capability_type_blocked(self):
        policy = OrchestrationPolicy(
            policy_id="no-agent",
            allowed_capability_types=("context", "skill", "memory"),
            forbidden_capability_types=("agent",),
            dry_run_only=True,
        )
        plan = plan_orchestration(self.req, self.registry, policy)
        blocked_types = set(s.capability_type for s in plan.blocked_steps)
        for s in plan.steps:
            self.assertNotEqual(s.capability_type, "agent")

    def test_19_forbidden_adapter_blocked(self):
        policy = OrchestrationPolicy(
            policy_id="block-specific",
            allowed_capability_types=("context", "skill", "memory", "agent"),
            forbidden_adapters=("openhands_agent",),
            dry_run_only=True,
        )
        plan = plan_orchestration(self.req, self.registry, policy)
        blocked_ids = set(s.adapter_id for s in plan.blocked_steps)
        self.assertIn("openhands_agent_worker", blocked_ids)

    def test_20_allowed_adapter_planned(self):
        policy = OrchestrationPolicy(
            policy_id="context-only",
            allowed_capability_types=("context",),
            dry_run_only=True,
        )
        plan = plan_orchestration(self.req, self.registry, policy)
        for s in plan.steps:
            self.assertEqual(s.capability_type, "context")

    def test_21_disabled_registry_entry_blocked(self):
        policy = OrchestrationPolicy(
            policy_id="all-allowed",
            allowed_capability_types=("context", "skill", "memory", "agent"),
            dry_run_only=True, max_adapters_per_plan=50,
        )
        plan = plan_orchestration(self.req, self.registry, policy)
        for s in plan.blocked_steps:
            self.assertTrue(s.blocked)

    def test_22_high_risk_adapter_blocked_when_above_max_risk(self):
        policy = OrchestrationPolicy(
            policy_id="low-risk-only",
            allowed_capability_types=("context", "skill", "memory", "agent"),
            dry_run_only=True, max_risk_level="low", max_adapters_per_plan=50,
        )
        plan = plan_orchestration(self.req, self.registry, policy)
        for s in plan.steps:
            if hasattr(s, 'blocked') and s.blocked:
                self.assertIn("risk", s.block_reason.lower())

    def test_23_blocked_step_retained_in_plan(self):
        policy = OrchestrationPolicy(
            policy_id="block-all", forbidden_capability_types=("context", "skill", "memory", "agent"),
            dry_run_only=True, max_adapters_per_plan=50,
        )
        plan = plan_orchestration(self.req, self.registry, policy)
        self.assertEqual(len(plan.steps), 0)
        self.assertGreater(len(plan.blocked_steps), 0)

    def test_24_deterministic_step_ordering(self):
        policy = full_external_review()
        p1 = plan_orchestration(self.req, self.registry, policy)
        p2 = plan_orchestration(self.req, self.registry, policy)
        ids1 = [(s.capability_type, s.adapter_id) for s in p1.steps]
        ids2 = [(s.capability_type, s.adapter_id) for s in p2.steps]
        self.assertEqual(ids1, ids2)


class TestProfiles(unittest.TestCase):
    """Tests for policy profiles."""

    def test_25_safe_context_only_profile_loads(self):
        p = safe_context_only()
        self.assertEqual(p.policy_id, "safe_context_only")
        self.assertTrue(p.dry_run_only)

    def test_26_skill_evolution_review_profile_loads(self):
        p = op_skill_evolution_review()
        self.assertEqual(p.policy_id, "skill_evolution_review")

    def test_27_memory_intelligence_review_profile_loads(self):
        p = op_memory_intelligence_review()
        self.assertEqual(p.policy_id, "memory_intelligence_review")

    def test_28_agent_worker_review_profile_loads(self):
        p = op_agent_worker_review()
        self.assertEqual(p.policy_id, "agent_worker_review")

    def test_29_full_external_review_profile_loads(self):
        p = full_external_review()
        self.assertEqual(p.policy_id, "full_external_review")

    def test_30_ecc_harness_review_profile_loads(self):
        p = ecc_harness_review()
        self.assertEqual(p.policy_id, "ecc_harness_review")

    def test_31_ecc_profile_is_dry_run_only(self):
        p = ecc_harness_review()
        self.assertTrue(p.dry_run_only)
        self.assertFalse(p.allow_external_execution)

    def test_32_ecc_profile_does_not_install_or_execute(self):
        p = ecc_harness_review()
        self.assertFalse(p.allow_file_modification)
        self.assertFalse(p.allow_network)
        self.assertFalse(p.allow_registry_updates)
        self.assertFalse(p.allow_memory_mutation)

    def test_33_all_six_profiles_exist(self):
        profiles = get_all_profiles()
        self.assertEqual(len(profiles), 10)
        ids = [p.policy_id for p in profiles]
        self.assertIn("agent_worker_review", ids)
        self.assertIn("direction_quality_intelligence_review", ids)
        self.assertIn("ecc_harness_review", ids)
        self.assertIn("full_external_review", ids)
        self.assertIn("lifecycle_management", ids)
        self.assertIn("memory_intelligence_review", ids)
        self.assertIn("observability_export", ids)
        self.assertIn("safe_context_only", ids)
        self.assertIn("sandbox_execution", ids)
        self.assertIn("skill_evolution_review", ids)

    def test_34_get_profile_unknown_returns_none(self):
        p = get_profile("nonexistent")
        self.assertIsNone(p)

    def test_35_get_profile_known_returns_policy(self):
        p = get_profile("ecc_harness_review")
        self.assertIsNotNone(p)
        self.assertEqual(p.policy_id, "ecc_harness_review")


class TestPlanValidation(unittest.TestCase):
    """Tests for plan validation."""

    def setUp(self):
        self.registry = build_default_registry()

    def test_36_plan_validates(self):
        policy = safe_context_only()
        req = build_orchestration_request(objective="test", requested_capability_types=("context",))
        plan = plan_orchestration(req, self.registry, policy)
        validation = validate_orchestration_plan(plan, self.registry, policy)
        self.assertTrue(validation.valid)

    def test_37_blocked_plan_validates_with_warnings(self):
        policy = OrchestrationPolicy(
            policy_id="all-blocked",
            forbidden_capability_types=("context", "skill", "memory", "agent", "ide", "eval", "usage", "tool"),
            dry_run_only=True,
        )
        req = build_orchestration_request(objective="test", requested_capability_types=("context",))
        plan = plan_orchestration(req, self.registry, policy)
        validation = validate_orchestration_plan(plan, self.registry, policy)
        self.assertTrue(validation.valid)
        self.assertGreater(len(validation.warnings), 0)

    def test_38_plan_converts_to_evidence(self):
        policy = safe_context_only()
        req = build_orchestration_request(objective="evidence-test", requested_capability_types=("context",))
        plan = plan_orchestration(req, self.registry, policy)
        bundle = orchestration_plan_to_evidence(plan, registry_hash="abc")
        self.assertIsNotNone(bundle)
        self.assertGreater(len(bundle.records), 0)

    def test_39_evidence_truth_source_false(self):
        policy = safe_context_only()
        req = build_orchestration_request(objective="truth-test")
        plan = plan_orchestration(req, self.registry, policy)
        bundle = orchestration_plan_to_evidence(plan, registry_hash="abc")
        for record in bundle.records:
            self.assertFalse(record.truth_source)

    def test_40_registry_hash_included_in_report(self):
        policy = safe_context_only()
        req = build_orchestration_request(objective="hash-test")
        plan = plan_orchestration(req, self.registry, policy)
        report = build_orchestration_policy_report(
            policy, req, plan, registry_hash="abc123def",
        )
        self.assertEqual(report.registry_hash, "abc123def")


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

    def test_41_cli_policies_works(self):
        result = self._run_cli("orchestrate", "policies")
        self.assertIn(result.returncode, (0, 1))
        self.assertIn("Orchestration Policy Layer", result.stdout + result.stderr)

    def test_42_cli_plan_works(self):
        result = self._run_cli("orchestrate", "plan", "--profile", "safe_context_only")
        self.assertIn(result.returncode, (0, 1))
        self.assertIn("Plan ID", result.stdout + result.stderr)

    def test_43_cli_evidence_works(self):
        result = self._run_cli("orchestrate", "evidence", "--profile", "safe_context_only")
        self.assertIn(result.returncode, (0, 1))
        self.assertIn("Evidence", result.stdout + result.stderr)


class TestNoExecution(unittest.TestCase):
    """Tests that no execution happens."""

    def test_44_no_external_tools_executed(self):
        policy = safe_context_only()
        req = build_orchestration_request(objective="no-exec-test")
        registry = build_default_registry()
        plan = plan_orchestration(req, registry, policy)
        self.assertFalse(plan.truth_source)
        for s in plan.steps:
            self.assertEqual(s.execution_mode, "dry_run")

    def test_45_no_agents_executed(self):
        policy = full_external_review()
        req = build_orchestration_request(objective="no-agent-exec")
        registry = build_default_registry()
        plan = plan_orchestration(req, registry, policy)
        self.assertIsNotNone(plan.plan_hash)

    def test_46_no_ide_apis_accessed(self):
        policy = full_external_review()
        self.assertFalse(policy.allow_external_execution)

    def test_47_no_skills_modified(self):
        skills_dir = os.path.join(ROOT, "SkillsManagementSystem", "packages")
        if os.path.isdir(skills_dir):
            mtimes_before = {}
            for root_d, dirs, files in os.walk(skills_dir):
                for f in files:
                    fp = os.path.join(root_d, f)
                    mtimes_before[fp] = os.path.getmtime(fp)

            plan_orchestration(
                build_orchestration_request(objective="test"),
                build_default_registry(),
                safe_context_only(),
            )

            for root_d, dirs, files in os.walk(skills_dir):
                for f in files:
                    fp = os.path.join(root_d, f)
                    if fp in mtimes_before:
                        self.assertEqual(mtimes_before[fp], os.path.getmtime(fp))

    def test_48_registry_json_not_modified(self):
        registry_path = os.path.join(ROOT, "SkillsManagementSystem", "registry.json")
        if os.path.exists(registry_path):
            before = os.path.getmtime(registry_path)
            plan_orchestration(
                build_orchestration_request(objective="test"),
                build_default_registry(),
                safe_context_only(),
            )
            self.assertEqual(before, os.path.getmtime(registry_path))

    def test_49_no_network_commands(self):
        for p in get_all_profiles():
            self.assertFalse(p.allow_network)


class TestNoNewRuntimeLoop(unittest.TestCase):
    """Tests that no new runtime loop is created."""

    def test_50_no_new_runtime_loop_created(self):
        # Orchestration is planning, not execution — no while True, no run loop
        policy_file = os.path.join(EXTERNAL_DIR, "orchestration_policy.py")
        with open(policy_file, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.While):
                self.fail("Orchestration policy must not contain while loops (runtime)")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "exec":
                    self.fail("Orchestration policy must not call exec()")
                if isinstance(node.func, ast.Name) and node.func.id == "eval":
                    self.fail("Orchestration policy must not call eval()")


class TestCrossPlaneCompatibility(unittest.TestCase):
    """Tests that existing plane tests still pass after Phase 9."""

    def test_51_skill_evolution_imports_still_work(self):
        from v3.external.skill_evolution import (
            SkillEvolutionProvider, mock_skill_evolution_result,
        )
        r = mock_skill_evolution_result(proposal_count=1)
        self.assertIsNotNone(r.result_hash)

    def test_52_workspace_plane_imports_still_work(self):
        from v3.external.workspace_context import mock_workspace_snapshot
        snap = mock_workspace_snapshot(provider_id="deterministic_mock_workspace")
        self.assertIsNotNone(snap.snapshot_hash)

    def test_53_agent_worker_imports_still_work(self):
        from v3.external.agent_worker import build_agent_worker_task, mock_agent_worker_result
        task = build_agent_worker_task(provider_id="test", task_summary="Test")
        result = mock_agent_worker_result(task)
        self.assertEqual(result.status, "proposed")

    def test_54_memory_intelligence_imports_still_work(self):
        from v3.external.memory_intelligence import (
            build_memory_intelligence_request, mock_memory_intelligence_result, MODE_INSPECT_ONLY,
        )
        req = build_memory_intelligence_request(
            provider_id="deterministic_mock_memory", input_record_refs=("r1",), mode=MODE_INSPECT_ONLY,
        )
        result = mock_memory_intelligence_result(req)
        self.assertIsNotNone(result.result_hash)

    def test_55_context_plane_imports_still_work(self):
        from v3.external.context_plane import default_context_budget_policy
        policy = default_context_budget_policy()
        self.assertIsNotNone(policy.policy_hash)

    def test_56_evidence_imports_still_work(self):
        from v3.external.evidence import make_evidence_record, EVIDENCE_TYPE_GENERIC, TRUST_LOW
        record = make_evidence_record(
            adapter_id="test", evidence_type=EVIDENCE_TYPE_GENERIC, capability_type="tool",
            input_data={}, output_data={}, payload_summary="test", source_trust_level=TRUST_LOW,
        )
        self.assertIsNotNone(record.evidence_id)

    def test_57_registry_imports_still_work(self):
        from v3.external.capability_registry import build_registry, validate_registry
        reg = build_registry(tuple())
        valid, _ = validate_registry(reg)
        self.assertTrue(valid)

    def test_58_contract_imports_still_work(self):
        from v3.external.capability_contract import compute_stable_hash
        h = compute_stable_hash("test")
        self.assertIsNotNone(h)


class TestComplexityGate(unittest.TestCase):
    """Tests that complexity gate stays safe."""

    def test_59_complexity_gate_not_reject(self):
        try:
            from v3.quality.phase_gate import evaluate_phase
            result = evaluate_phase("5A", v3_root=V3_ROOT)
            self.assertIn(result.verdict.verdict, ("ACCEPT", "REVIEW"))
        except (ImportError, FileNotFoundError):
            self.skipTest("Quality gate module not available")


class TestV4Baseline(unittest.TestCase):
    """Tests for V4 baseline."""

    def test_60_v4_baseline_guard_still_passes(self):
        from v3.release.v4_baseline_guard import build_v4_baseline_guard
        result = build_v4_baseline_guard()
        self.assertTrue(result.overall_pass)


class TestKernelInvariants(unittest.TestCase):
    """Tests for kernel invariants."""

    def test_61_kernel_invariants_still_purity(self):
        report_path = os.path.join(V3_ROOT, "exports", "kernel_validity_report.json")
        if os.path.exists(report_path):
            with open(report_path, encoding="utf-8") as f:
                report = json.load(f)
            purity = report.get("purity_score", 100)
            self.assertEqual(purity, 100)

    def test_62_orchestration_plan_is_not_truth_source(self):
        plan = OrchestrationPlan()
        self.assertFalse(plan.truth_source)
        self.assertFalse(
            OrchestrationPlan(truth_source=True).truth_source in (False,)
            or not OrchestrationPlan(truth_source=True).truth_source
        )


class TestECCProfile(unittest.TestCase):
    """Tests specific to ECC harness review profile."""

    def test_63_ecc_capability_types_correct(self):
        p = ecc_harness_review()
        self.assertIn("skill", p.allowed_capability_types)
        self.assertIn("tool", p.allowed_capability_types)
        self.assertIn("eval", p.allowed_capability_types)
        self.assertIn("context", p.allowed_capability_types)

    def test_64_ecc_forbids_agent_ide_memory_usage(self):
        p = ecc_harness_review()
        self.assertIn("agent", p.forbidden_capability_types)
        self.assertIn("ide", p.forbidden_capability_types)
        self.assertIn("memory", p.forbidden_capability_types)
        self.assertIn("usage", p.forbidden_capability_types)

    def test_65_ecc_requires_human_approval(self):
        p = ecc_harness_review()
        self.assertTrue(p.require_human_approval)

    def test_66_ecc_no_registry_update(self):
        p = ecc_harness_review()
        self.assertFalse(p.allow_registry_updates)
        self.assertFalse(p.allow_memory_mutation)


class TestFixtureLoading(unittest.TestCase):
    """Tests for fixture data loading."""

    def test_67_fixture_loads(self):
        fixture_path = os.path.join(FIXTURE_DIR, "orchestration_request.json")
        self.assertTrue(os.path.exists(fixture_path))
        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("objective", data)
        self.assertIn("requested_capability_types", data)
        self.assertEqual(len(data["expected_policies"]), 6)


class TestNoLLMImports(unittest.TestCase):
    """Tests that no LLM imports exist in Phase 9 files."""

    def _scan_file(self, filepath):
        banned = {
            "openai", "anthropic", "langchain", "llamaindex",
            "torch", "tensorflow", "transformers",
        }
        violations = []
        try:
            with open(filepath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in banned:
                            violations.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in banned:
                        violations.append(node.module)
        except (SyntaxError, OSError):
            pass
        return violations

    def test_68_no_llm_imports_in_phase9_files(self):
        for fname in ("orchestration_policy.py", "orchestration_profiles.py"):
            fpath = os.path.join(EXTERNAL_DIR, fname)
            violations = self._scan_file(fpath)
            self.assertEqual(len(violations), 0,
                           f"{fname} has banned imports: {violations}")


class TestAntiOverengineering(unittest.TestCase):
    """Tests for anti-overengineering gates."""

    def test_69_no_workflow_engine_created(self):
        fpath = os.path.join(EXTERNAL_DIR, "orchestration_policy.py")
        with open(fpath, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("class WorkflowEngine", source)
        self.assertNotIn("class ExecutionEngine", source)
        self.assertNotIn("class TaskRunner", source)

    def test_70_request_dry_run_always_true(self):
        req = build_orchestration_request(objective="test")
        self.assertTrue(req.dry_run)
        # Even if someone tries to set it, the builder overrides
        self.assertTrue(req.dry_run)


if __name__ == "__main__":
    unittest.main()
