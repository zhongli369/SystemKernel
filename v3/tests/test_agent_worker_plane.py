"""
Agent Worker Plane Tests — Phase 6.

48+ tests for the Agent Worker Plane: providers, tasks, proposals,
results, reports, policy validation, profiles, evidence mapping, and CLI.
Stdlib only. No external services. No LLM. No agent execution.
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

from v3.external.agent_worker import (
    AgentWorkerProvider,
    AgentWorkerTask,
    AgentWorkerProposal,
    AgentWorkerResult,
    AgentWorkerReport,
    AgentWorkerValidationResult,
    PROVIDER_TYPE_OPENHANDS_LIKE,
    PROVIDER_TYPE_SWE_AGENT_LIKE,
    PROVIDER_TYPE_AUTOGEN_LIKE,
    PROVIDER_TYPE_CONTINUE_LIKE,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    PROVIDER_TYPE_GENERIC,
    ALL_PROVIDER_TYPES,
    STATUS_PLANNED,
    STATUS_BLOCKED,
    STATUS_PROPOSED,
    STATUS_FAILED,
    ALL_RESULT_STATUSES,
    build_agent_worker_task,
    make_blocked_agent_result,
    mock_agent_worker_result,
    agent_proposals_to_evidence,
    build_agent_worker_report,
    validate_agent_worker_provider,
    validate_agent_worker_task,
    validate_agent_worker_result,
    _compute_hash,
)

from v3.external.agent_worker_policy import (
    POLICY_PASS,
    POLICY_BLOCKED,
    POLICY_REVIEW,
    AgentWorkerPolicy,
    default_agent_worker_policy,
    validate_provider_against_policy,
    validate_task_against_policy,
    validate_result_against_policy,
    block_provider_reason,
    evaluate_task_policy,
)

from v3.external.agent_worker_profiles import (
    AgentWorkerProfileStatus,
    openhands_agent_profile,
    swe_agent_profile,
    autogen_agent_profile,
    continue_agent_profile,
    deterministic_mock_agent_profile,
    get_all_profiles,
    get_profile,
    evaluate_all_profiles,
)


# ═══════════════════════════════════════════════════════════════════════
# Provider Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerProvider(unittest.TestCase):

    def test_01_constructor_defaults(self):
        p = AgentWorkerProvider()
        self.assertEqual(p.provider_id, "")
        self.assertEqual(p.name, "")
        self.assertEqual(p.provider_type, PROVIDER_TYPE_GENERIC)
        self.assertEqual(p.capability_type, "agent")
        self.assertEqual(p.execution_mode, "inspect_only")
        self.assertFalse(p.requires_llm)
        self.assertFalse(p.requires_sandbox)
        self.assertFalse(p.requires_network)
        self.assertFalse(p.can_modify_files)
        self.assertFalse(p.can_execute_commands)
        self.assertFalse(p.external_service_required)
        self.assertFalse(p.truth_source)
        self.assertTrue(p.removable)

    def test_02_constructor_full(self):
        p = AgentWorkerProvider(
            provider_id="test_agent",
            name="Test Agent",
            provider_type=PROVIDER_TYPE_OPENHANDS_LIKE,
            requires_llm=True,
            requires_sandbox=True,
            requires_network=True,
            can_modify_files=True,
            can_execute_commands=True,
            external_service_required=True,
            description="Test provider",
        )
        self.assertEqual(p.provider_id, "test_agent")
        self.assertTrue(p.requires_llm)
        self.assertTrue(p.can_modify_files)
        self.assertTrue(p.can_execute_commands)

    def test_03_frozen(self):
        p = AgentWorkerProvider(provider_id="test")
        with self.assertRaises(Exception):
            p.provider_id = "changed"

    def test_04_to_dict(self):
        p = AgentWorkerProvider(provider_id="test", name="Test")
        d = p.to_dict()
        self.assertEqual(d["provider_id"], "test")
        self.assertEqual(d["name"], "Test")
        self.assertFalse(d["truth_source"])
        self.assertTrue(d["removable"])

    def test_05_hash_determinism(self):
        p1 = AgentWorkerProvider(provider_id="test", name="Test")
        p2 = AgentWorkerProvider(provider_id="test", name="Test")
        h1 = _compute_hash(p1)
        h2 = _compute_hash(p2)
        self.assertEqual(h1, h2)

    def test_06_hash_differs_on_change(self):
        p1 = AgentWorkerProvider(provider_id="test_a")
        p2 = AgentWorkerProvider(provider_id="test_b")
        self.assertNotEqual(_compute_hash(p1), _compute_hash(p2))

    def test_07_truth_source_always_false(self):
        p = AgentWorkerProvider(provider_id="test")
        self.assertFalse(p.truth_source)
        d = p.to_dict()
        self.assertFalse(d["truth_source"])

    def test_08_removable_always_true(self):
        p = AgentWorkerProvider(provider_id="test")
        self.assertTrue(p.removable)
        d = p.to_dict()
        self.assertTrue(d["removable"])

    def test_09_all_provider_types(self):
        self.assertIn(PROVIDER_TYPE_OPENHANDS_LIKE, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_SWE_AGENT_LIKE, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_AUTOGEN_LIKE, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_CONTINUE_LIKE, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_DETERMINISTIC_MOCK, ALL_PROVIDER_TYPES)
        self.assertIn(PROVIDER_TYPE_GENERIC, ALL_PROVIDER_TYPES)
        self.assertEqual(len(ALL_PROVIDER_TYPES), 6)


# ═══════════════════════════════════════════════════════════════════════
# Task Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerTask(unittest.TestCase):

    def test_10_constructor_defaults(self):
        t = AgentWorkerTask()
        self.assertEqual(t.task_id, "")
        self.assertEqual(t.provider_id, "")
        self.assertTrue(t.dry_run)
        self.assertEqual(t.max_runtime_seconds, 300)

    def test_11_constructor_full(self):
        t = AgentWorkerTask(
            task_id="task-1",
            provider_id="prov-1",
            task_summary="Test task",
            input_refs=("a.py", "b.py"),
            allowed_paths=("./src",),
            forbidden_paths=("./secrets",),
            max_runtime_seconds=120,
            dry_run=True,
        )
        self.assertEqual(t.task_id, "task-1")
        self.assertEqual(t.task_summary, "Test task")
        self.assertEqual(t.input_refs, ("a.py", "b.py"))
        self.assertEqual(t.allowed_paths, ("./src",))
        self.assertEqual(t.forbidden_paths, ("./secrets",))
        self.assertEqual(t.max_runtime_seconds, 120)
        self.assertTrue(t.dry_run)

    def test_12_frozen(self):
        t = AgentWorkerTask(task_id="test")
        with self.assertRaises(Exception):
            t.task_id = "changed"

    def test_13_to_dict(self):
        t = AgentWorkerTask(task_id="test", provider_id="prov", dry_run=True)
        d = t.to_dict()
        self.assertEqual(d["task_id"], "test")
        self.assertTrue(d["dry_run"])
        self.assertEqual(d["allowed_paths"], [])

    def test_14_hash_determinism(self):
        t1 = AgentWorkerTask(task_id="test", provider_id="prov", dry_run=True)
        t2 = AgentWorkerTask(task_id="test", provider_id="prov", dry_run=True)
        self.assertEqual(_compute_hash(t1), _compute_hash(t2))

    def test_15_hash_differs_on_dry_run(self):
        t1 = AgentWorkerTask(task_id="test", dry_run=True)
        t2 = AgentWorkerTask(task_id="test", dry_run=False)
        self.assertNotEqual(_compute_hash(t1), _compute_hash(t2))


# ═══════════════════════════════════════════════════════════════════════
# Proposal Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerProposal(unittest.TestCase):

    def test_16_constructor_defaults(self):
        p = AgentWorkerProposal()
        self.assertEqual(p.proposal_id, "")
        self.assertFalse(p.truth_source)
        self.assertEqual(p.confidence, 0.0)

    def test_17_frozen(self):
        p = AgentWorkerProposal(proposal_id="test")
        with self.assertRaises(Exception):
            p.proposal_id = "changed"

    def test_18_to_dict(self):
        p = AgentWorkerProposal(proposal_id="p1", confidence=0.8,
                                proposed_plan="Fix bug",
                                proposed_files=("a.py",),
                                risk_flags=("unverified",))
        d = p.to_dict()
        self.assertEqual(d["proposal_id"], "p1")
        self.assertEqual(d["confidence"], 0.8)
        self.assertFalse(d["truth_source"])
        self.assertEqual(d["proposed_files"], ["a.py"])
        self.assertIn("unverified", d["risk_flags"])

    def test_19_hash_determinism(self):
        p1 = AgentWorkerProposal(proposal_id="p1", confidence=0.8)
        p2 = AgentWorkerProposal(proposal_id="p1", confidence=0.8)
        self.assertEqual(_compute_hash(p1), _compute_hash(p2))

    def test_20_truth_source_always_false(self):
        p = AgentWorkerProposal(proposal_id="test")
        self.assertFalse(p.truth_source)

    def test_21_proposed_files_are_strings(self):
        p = AgentWorkerProposal(
            proposal_id="test",
            proposed_files=("file.py", "report.md"),
        )
        self.assertIsInstance(p.proposed_files, tuple)
        self.assertEqual(len(p.proposed_files), 2)

    def test_22_proposed_commands_are_strings(self):
        p = AgentWorkerProposal(
            proposal_id="test",
            proposed_commands=("ls -la", "echo done"),
        )
        self.assertIsInstance(p.proposed_commands, tuple)
        self.assertEqual(len(p.proposed_commands), 2)


# ═══════════════════════════════════════════════════════════════════════
# Result Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerResult(unittest.TestCase):

    def test_23_constructor_defaults(self):
        r = AgentWorkerResult()
        self.assertEqual(r.status, STATUS_PLANNED)
        self.assertFalse(r.truth_source)
        self.assertEqual(len(r.proposals), 0)

    def test_24_frozen(self):
        r = AgentWorkerResult(task_id="test")
        with self.assertRaises(Exception):
            r.task_id = "changed"

    def test_25_to_dict(self):
        r = AgentWorkerResult(task_id="t1", provider_id="p1", status=STATUS_PROPOSED)
        d = r.to_dict()
        self.assertEqual(d["task_id"], "t1")
        self.assertEqual(d["status"], STATUS_PROPOSED)
        self.assertFalse(d["truth_source"])

    def test_26_hash_determinism(self):
        r1 = AgentWorkerResult(task_id="test", status=STATUS_PLANNED)
        r2 = AgentWorkerResult(task_id="test", status=STATUS_PLANNED)
        self.assertEqual(_compute_hash(r1), _compute_hash(r2))

    def test_27_all_result_statuses(self):
        self.assertIn(STATUS_PLANNED, ALL_RESULT_STATUSES)
        self.assertIn(STATUS_BLOCKED, ALL_RESULT_STATUSES)
        self.assertIn(STATUS_PROPOSED, ALL_RESULT_STATUSES)
        self.assertIn(STATUS_FAILED, ALL_RESULT_STATUSES)
        self.assertEqual(len(ALL_RESULT_STATUSES), 4)

    def test_28_truth_source_always_false(self):
        r = AgentWorkerResult(task_id="test")
        self.assertFalse(r.truth_source)


# ═══════════════════════════════════════════════════════════════════════
# Report Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerReport(unittest.TestCase):

    def test_29_constructor_defaults(self):
        r = AgentWorkerReport()
        self.assertIsNone(r.provider)
        self.assertIsNone(r.task)
        self.assertIsNone(r.result)
        self.assertEqual(r.policy_status, "unknown")

    def test_30_frozen(self):
        r = AgentWorkerReport(policy_status="pass")
        with self.assertRaises(Exception):
            r.policy_status = "changed"

    def test_31_to_dict_with_all_none(self):
        r = AgentWorkerReport()
        d = r.to_dict()
        self.assertIsNone(d["provider"])
        self.assertIsNone(d["task"])
        self.assertIsNone(d["result"])

    def test_32_to_dict_with_data(self):
        provider = AgentWorkerProvider(provider_id="p1")
        task = AgentWorkerTask(task_id="t1")
        result = AgentWorkerResult(task_id="t1")
        r = AgentWorkerReport(
            provider=provider, task=task, result=result,
            evidence_bundle_id="bundle-1", policy_status="pass",
        )
        d = r.to_dict()
        self.assertIsNotNone(d["provider"])
        self.assertIsNotNone(d["task"])
        self.assertIsNotNone(d["result"])
        self.assertEqual(d["evidence_bundle_id"], "bundle-1")
        self.assertEqual(d["policy_status"], "pass")

    def test_33_hash_determinism(self):
        r1 = AgentWorkerReport(evidence_bundle_id="b1", policy_status="pass")
        r2 = AgentWorkerReport(evidence_bundle_id="b1", policy_status="pass")
        self.assertEqual(_compute_hash(r1), _compute_hash(r2))


# ═══════════════════════════════════════════════════════════════════════
# Validation Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerValidation(unittest.TestCase):

    def test_34_validate_provider_valid(self):
        p = AgentWorkerProvider(
            provider_id="test", provider_type=PROVIDER_TYPE_DETERMINISTIC_MOCK,
        )
        v = validate_agent_worker_provider(p)
        self.assertTrue(v.valid)
        self.assertEqual(len(v.violations), 0)

    def test_35_validate_provider_truth_source_violation(self):
        p = AgentWorkerProvider(provider_id="test", truth_source=True)
        v = validate_agent_worker_provider(p)
        self.assertFalse(v.valid)
        self.assertTrue(any("truth_source" in x for x in v.violations))

    def test_36_validate_provider_removable_violation(self):
        p = AgentWorkerProvider(provider_id="test", removable=False)
        v = validate_agent_worker_provider(p)
        self.assertFalse(v.valid)
        self.assertTrue(any("removable" in x for x in v.violations))

    def test_37_validate_provider_unknown_type(self):
        p = AgentWorkerProvider(provider_id="test", provider_type="invalid_type")
        v = validate_agent_worker_provider(p)
        self.assertFalse(v.valid)

    def test_38_validate_provider_empty_id(self):
        p = AgentWorkerProvider(provider_id="")
        v = validate_agent_worker_provider(p)
        self.assertFalse(v.valid)

    def test_39_validate_task_valid(self):
        t = AgentWorkerTask(task_id="t1", provider_id="p1", dry_run=True)
        v = validate_agent_worker_task(t)
        self.assertTrue(v.valid)

    def test_40_validate_task_empty_id(self):
        t = AgentWorkerTask(task_id="")
        v = validate_agent_worker_task(t)
        self.assertFalse(v.valid)

    def test_41_validate_task_empty_provider(self):
        t = AgentWorkerTask(task_id="t1", provider_id="")
        v = validate_agent_worker_task(t)
        self.assertFalse(v.valid)

    def test_42_validate_task_dry_run_false_triggers_violation(self):
        t = AgentWorkerTask(task_id="t1", provider_id="p1", dry_run=False)
        v = validate_agent_worker_task(t)
        self.assertFalse(v.valid)
        self.assertTrue(any("dry_run" in x for x in v.violations))

    def test_43_validate_result_valid(self):
        r = AgentWorkerResult(task_id="t1", status=STATUS_PROPOSED)
        v = validate_agent_worker_result(r)
        self.assertTrue(v.valid)

    def test_44_validate_result_truth_source_violation(self):
        r = AgentWorkerResult(task_id="t1", truth_source=True)
        v = validate_agent_worker_result(r)
        self.assertFalse(v.valid)

    def test_45_validate_result_unknown_status(self):
        r = AgentWorkerResult(task_id="t1", status="invalid_status")
        v = validate_agent_worker_result(r)
        self.assertFalse(v.valid)

    def test_46_validate_blocked_result_needs_warnings(self):
        r = AgentWorkerResult(task_id="t1", status=STATUS_BLOCKED, warnings=())
        v = validate_agent_worker_result(r)
        self.assertFalse(v.valid)


# ═══════════════════════════════════════════════════════════════════════
# Builder Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerBuilders(unittest.TestCase):

    def test_47_build_task_deterministic(self):
        t1 = build_agent_worker_task("prov", task_summary="test",
                                     input_refs=("a.py", "b.py"))
        t2 = build_agent_worker_task("prov", task_summary="test",
                                     input_refs=("a.py", "b.py"))
        self.assertEqual(t1.task_id, t2.task_id)
        self.assertEqual(t1.task_hash, t2.task_hash)
        self.assertTrue(t1.dry_run)

    def test_48_build_task_dry_run_default_true(self):
        t = build_agent_worker_task("prov", task_summary="test")
        self.assertTrue(t.dry_run)

    def test_49_build_task_different_summary_different_id(self):
        t1 = build_agent_worker_task("prov", task_summary="task A")
        t2 = build_agent_worker_task("prov", task_summary="task B")
        self.assertNotEqual(t1.task_id, t2.task_id)

    def test_50_make_blocked_agent_result(self):
        r = make_blocked_agent_result("t1", "p1", "Blocked for testing")
        self.assertEqual(r.status, STATUS_BLOCKED)
        self.assertEqual(len(r.proposals), 0)
        self.assertIn("Blocked for testing", r.warnings)
        self.assertFalse(r.truth_source)

    def test_51_make_blocked_result_hash(self):
        r1 = make_blocked_agent_result("t1", "p1", "reason")
        r2 = make_blocked_agent_result("t1", "p1", "reason")
        self.assertEqual(r1.result_hash, r2.result_hash)

    def test_52_mock_result_produces_proposals(self):
        t = build_agent_worker_task("prov", task_summary="mock test",
                                    input_refs=("a.py", "b.py", "c.py"))
        r = mock_agent_worker_result(t, proposal_count=3)
        self.assertEqual(r.status, STATUS_PROPOSED)
        self.assertEqual(len(r.proposals), 3)

    def test_53_mock_result_deterministic(self):
        t = build_agent_worker_task("prov", task_summary="mock test",
                                    input_refs=("a.py", "b.py"))
        r1 = mock_agent_worker_result(t, proposal_count=2)
        r2 = mock_agent_worker_result(t, proposal_count=2)
        self.assertEqual(r1.result_hash, r2.result_hash)

    def test_54_mock_result_max_5_proposals(self):
        t = build_agent_worker_task("prov", task_summary="test",
                                    input_refs=("a.py",))
        r = mock_agent_worker_result(t, proposal_count=10)
        self.assertLessEqual(len(r.proposals), 5)

    def test_55_mock_result_proposals_have_correct_provider(self):
        t = build_agent_worker_task("prov-xyz", task_summary="test",
                                    input_refs=("a.py",))
        r = mock_agent_worker_result(t, proposal_count=1)
        for p in r.proposals:
            self.assertEqual(p.provider_id, "prov-xyz")
            self.assertFalse(p.truth_source)

    def test_56_mock_result_truth_source_false(self):
        t = build_agent_worker_task("prov", task_summary="test")
        r = mock_agent_worker_result(t)
        self.assertFalse(r.truth_source)


# ═══════════════════════════════════════════════════════════════════════
# Policy Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerPolicy(unittest.TestCase):

    def test_57_default_policy_blocks_everything(self):
        p = default_agent_worker_policy()
        self.assertFalse(p.allow_llm_providers)
        self.assertFalse(p.allow_network)
        self.assertFalse(p.allow_file_modification)
        self.assertFalse(p.allow_command_execution)
        self.assertFalse(p.allow_external_services)
        self.assertTrue(p.require_sandbox)
        self.assertTrue(p.require_human_approval)

    def test_58_default_policy_hash_deterministic(self):
        p1 = default_agent_worker_policy()
        p2 = default_agent_worker_policy()
        self.assertEqual(p1.policy_hash, p2.policy_hash)

    def test_59_policy_frozen(self):
        p = default_agent_worker_policy()
        with self.assertRaises(Exception):
            p.allow_llm_providers = True

    def test_60_block_provider_deterministic_mock_passes(self):
        provider = deterministic_mock_agent_profile()
        policy = default_agent_worker_policy()
        reason = block_provider_reason(provider, policy)
        self.assertEqual(reason, "")

    def test_61_block_provider_llm(self):
        provider = openhands_agent_profile()
        policy = default_agent_worker_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("LLM", reason)
        self.assertNotEqual(reason, "")

    def test_62_block_provider_network(self):
        provider = AgentWorkerProvider(
            provider_id="net_agent", provider_type="generic",
            requires_network=True,
        )
        policy = default_agent_worker_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("network", reason)

    def test_63_block_provider_file_modification(self):
        provider = AgentWorkerProvider(
            provider_id="file_agent", provider_type="generic",
            can_modify_files=True,
        )
        policy = default_agent_worker_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("modify files", reason)

    def test_64_block_provider_command_execution(self):
        provider = AgentWorkerProvider(
            provider_id="cmd_agent", provider_type="generic",
            can_execute_commands=True,
        )
        policy = default_agent_worker_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("execute commands", reason)

    def test_65_block_provider_external_service(self):
        provider = AgentWorkerProvider(
            provider_id="ext_agent", provider_type="generic",
            external_service_required=True,
        )
        policy = default_agent_worker_policy()
        reason = block_provider_reason(provider, policy)
        self.assertIn("external service", reason)

    def test_66_validate_provider_against_policy_pass(self):
        provider = deterministic_mock_agent_profile()
        policy = default_agent_worker_policy()
        allowed, reason = validate_provider_against_policy(provider, policy)
        self.assertTrue(allowed)
        self.assertEqual(reason, "OK")

    def test_67_validate_provider_against_policy_block(self):
        provider = openhands_agent_profile()
        policy = default_agent_worker_policy()
        allowed, reason = validate_provider_against_policy(provider, policy)
        self.assertFalse(allowed)

    def test_68_validate_task_against_policy_pass(self):
        task = build_agent_worker_task("prov", task_summary="test",
                                       allowed_paths=("./src",))
        policy = default_agent_worker_policy()
        ok, reason = validate_task_against_policy(task, policy)
        self.assertTrue(ok)

    def test_69_validate_task_dry_run_false_blocked(self):
        task = AgentWorkerTask(task_id="t1", provider_id="p1", dry_run=False)
        policy = default_agent_worker_policy()
        ok, reason = validate_task_against_policy(task, policy)
        self.assertFalse(ok)
        self.assertIn("human approval", reason)

    def test_70_validate_task_max_runtime_exceeded(self):
        task = AgentWorkerTask(task_id="t1", provider_id="p1", dry_run=True,
                               max_runtime_seconds=9999)
        policy = default_agent_worker_policy()
        ok, reason = validate_task_against_policy(task, policy)
        self.assertFalse(ok)
        self.assertIn("max_runtime", reason)

    def test_71_validate_result_against_policy_pass(self):
        result = AgentWorkerResult(task_id="t1", status=STATUS_PROPOSED)
        policy = default_agent_worker_policy()
        ok, reason = validate_result_against_policy(result, policy)
        self.assertTrue(ok)

    def test_72_validate_result_blocked_status_pass(self):
        result = AgentWorkerResult(
            task_id="t1", status=STATUS_BLOCKED,
            warnings=("Blocked for policy",),
        )
        policy = default_agent_worker_policy()
        ok, reason = validate_result_against_policy(result, policy)
        self.assertTrue(ok)

    def test_73_validate_result_max_proposals_exceeded(self):
        proposals = tuple(
            AgentWorkerProposal(proposal_id=f"p{i}") for i in range(20)
        )
        result = AgentWorkerResult(
            task_id="t1", status=STATUS_PROPOSED,
            proposals=proposals,
        )
        policy = default_agent_worker_policy()
        ok, reason = validate_result_against_policy(result, policy)
        self.assertFalse(ok)
        self.assertIn("proposals", reason)

    def test_74_evaluate_task_policy_full_chain(self):
        provider = deterministic_mock_agent_profile()
        task = build_agent_worker_task("deterministic_mock_agent",
                                       task_summary="test",
                                       allowed_paths=("./src",))
        policy = default_agent_worker_policy()
        ok, reason = evaluate_task_policy(task, provider, policy)
        self.assertTrue(ok)


# ═══════════════════════════════════════════════════════════════════════
# Profiles Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerProfiles(unittest.TestCase):

    def test_75_all_profiles_exist(self):
        profiles = get_all_profiles()
        self.assertEqual(len(profiles), 5)

    def test_76_all_profiles_have_truth_source_false(self):
        for p in get_all_profiles():
            self.assertFalse(p.truth_source, f"{p.provider_id}: truth_source must be False")

    def test_77_all_profiles_have_removable_true(self):
        for p in get_all_profiles():
            self.assertTrue(p.removable, f"{p.provider_id}: removable must be True")

    def test_78_mock_profile_allowed_by_default(self):
        policy = default_agent_worker_policy()
        statuses = evaluate_all_profiles(policy)
        mock_status = next(s for s in statuses if s.provider_id == "deterministic_mock_agent")
        self.assertTrue(mock_status.allowed)

    def test_79_real_profiles_blocked_by_default(self):
        policy = default_agent_worker_policy()
        statuses = evaluate_all_profiles(policy)
        for s in statuses:
            if s.provider_id != "deterministic_mock_agent":
                self.assertFalse(s.allowed, f"{s.provider_id} should be blocked")

    def test_80_get_profile_known(self):
        p = get_profile("deterministic_mock_agent")
        self.assertIsNotNone(p)
        self.assertEqual(p.provider_id, "deterministic_mock_agent")

    def test_81_get_profile_unknown(self):
        p = get_profile("nonexistent")
        self.assertIsNone(p)

    def test_82_profiles_sorted(self):
        profiles = get_all_profiles()
        ids = [p.provider_id for p in profiles]
        self.assertEqual(ids, sorted(ids))

    def test_83_evaluate_all_profiles_returns_sorted(self):
        policy = default_agent_worker_policy()
        statuses = evaluate_all_profiles(policy)
        ids = [s.provider_id for s in statuses]
        self.assertEqual(ids, sorted(ids))

    def test_84_openhands_profile_blocked(self):
        p = openhands_agent_profile()
        policy = default_agent_worker_policy()
        allowed, _ = validate_provider_against_policy(p, policy)
        self.assertFalse(allowed)

    def test_85_swe_agent_profile_blocked(self):
        p = swe_agent_profile()
        policy = default_agent_worker_policy()
        allowed, _ = validate_provider_against_policy(p, policy)
        self.assertFalse(allowed)

    def test_86_autogen_profile_blocked(self):
        p = autogen_agent_profile()
        policy = default_agent_worker_policy()
        allowed, _ = validate_provider_against_policy(p, policy)
        self.assertFalse(allowed)

    def test_87_continue_profile_blocked(self):
        p = continue_agent_profile()
        policy = default_agent_worker_policy()
        allowed, _ = validate_provider_against_policy(p, policy)
        self.assertFalse(allowed)


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerEvidenceMapping(unittest.TestCase):

    def test_88_evidence_bundle_from_proposals(self):
        task = build_agent_worker_task("prov", task_summary="test",
                                       input_refs=("a.py", "b.py"))
        result = mock_agent_worker_result(task, proposal_count=2)
        bundle = agent_proposals_to_evidence(result, registry_hash="abc123")
        self.assertEqual(len(bundle.records), 2)
        self.assertFalse(bundle.truth_source)

    def test_89_evidence_bundle_empty_result(self):
        result = AgentWorkerResult(task_id="t1", provider_id="p1",
                                   status=STATUS_PROPOSED, proposals=())
        bundle = agent_proposals_to_evidence(result, registry_hash="abc123")
        self.assertEqual(len(bundle.records), 1)  # fallback empty record

    def test_90_evidence_bundle_blocked_result(self):
        result = make_blocked_agent_result("t1", "p1", "Blocked")
        bundle = agent_proposals_to_evidence(result, registry_hash="abc123")
        self.assertEqual(len(bundle.records), 1)

    def test_91_evidence_bundle_truth_source_false(self):
        task = build_agent_worker_task("prov", task_summary="test",
                                       input_refs=("a.py",))
        result = mock_agent_worker_result(task, proposal_count=1)
        bundle = agent_proposals_to_evidence(result)
        self.assertFalse(bundle.truth_source)

    def test_92_report_from_evidence(self):
        provider = deterministic_mock_agent_profile()
        task = build_agent_worker_task("deterministic_mock_agent",
                                       task_summary="test",
                                       input_refs=("a.py",))
        result = mock_agent_worker_result(task, proposal_count=1)
        bundle = agent_proposals_to_evidence(result)
        report = build_agent_worker_report(provider, task, result, bundle, policy_status="pass")
        self.assertEqual(report.policy_status, "pass")
        self.assertEqual(report.evidence_bundle_id, bundle.bundle_id)
        self.assertIsNotNone(report.provider)
        self.assertIsNotNone(report.task)
        self.assertIsNotNone(report.result)


# ═══════════════════════════════════════════════════════════════════════
# CLI Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerCLI(unittest.TestCase):

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

    def test_93_cli_profiles(self):
        result = self._run("agent-worker", "profiles")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Agent Worker Plane", result.stdout)
        self.assertIn("deterministic_mock_agent", result.stdout)
        self.assertIn("openhands_agent", result.stdout)
        self.assertIn("YES", result.stdout)  # mock allowed

    def test_94_cli_profiles_shows_blocked(self):
        result = self._run("agent-worker", "profiles")
        self.assertIn("NO", result.stdout)  # real providers blocked

    def test_95_cli_mock(self):
        result = self._run("agent-worker", "mock", "--proposals", "3")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Proposals generated", result.stdout)
        self.assertIn("false", result.stdout.lower())

    def test_96_cli_mock_truth_source_false(self):
        result = self._run("agent-worker", "mock")
        self.assertIn("false", result.stdout.lower())

    def test_97_cli_evidence(self):
        result = self._run("agent-worker", "evidence")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Evidence bundle", result.stdout)
        self.assertIn("false", result.stdout.lower())

    def test_98_cli_mock_unknown_provider(self):
        result = self._run("agent-worker", "mock", "--provider", "nonexistent")
        self.assertNotEqual(result.returncode, 0)


# ═══════════════════════════════════════════════════════════════════════
# Invariants Tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgentWorkerInvariants(unittest.TestCase):

    def test_99_no_banned_imports(self):
        """Scan agent_worker.py, _policy.py, _profiles.py for banned imports."""
        banned = {
            "openai", "anthropic", "langchain", "llamaindex",
            "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
            "mem0", "graphiti", "sentence_transformers", "transformers",
            "torch", "tensorflow",
            "openhands", "swe_agent", "autogen",
        }
        for fname in ("agent_worker.py", "agent_worker_policy.py", "agent_worker_profiles.py"):
            fpath = os.path.join(EXTERNAL_DIR, fname)
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name.split(".")[0]
                        self.assertNotIn(name, banned,
                                         f"{fname} imports banned module: {name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        name = node.module.split(".")[0]
                        self.assertNotIn(name, banned,
                                         f"{fname} imports banned module: {name}")

    def test_100_all_truth_source_fields_are_false(self):
        """Verify all AgentWorker* objects have truth_source=False."""
        provider = AgentWorkerProvider(provider_id="test")
        self.assertFalse(provider.truth_source)

        proposal = AgentWorkerProposal(proposal_id="test")
        self.assertFalse(proposal.truth_source)

        result = AgentWorkerResult(task_id="test")
        self.assertFalse(result.truth_source)

        task = AgentWorkerTask(task_id="test")
        t = build_agent_worker_task("prov", task_summary="test")
        r = mock_agent_worker_result(t, proposal_count=1)
        self.assertFalse(r.truth_source)
        for p in r.proposals:
            self.assertFalse(p.truth_source)

    def test_101_fixture_file_exists(self):
        fixture_path = os.path.join(FIXTURE_DIR, "agent_worker_task.json")
        self.assertTrue(os.path.exists(fixture_path))
        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("input_refs", data)
        self.assertIn("fixture_hash", data)


# ═══════════════════════════════════════════════════════════════════════
# Regression Tests
# ═══════════════════════════════════════════════════════════════════════

class TestPhase6Regression(unittest.TestCase):

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

    def test_context_plane_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_context_engineering_plane.py")],
            capture_output=True, text=True, timeout=300, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Context plane tests failed:\n{result.stderr[:1000]}")

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
