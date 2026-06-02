"""
Capability Adapter Contract Tests — Phase 1.

31 tests verifying the universal contract for external capabilities.
Stdlib only — zero external test dependencies.
"""

import ast
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
KERNEL_DIR = os.path.join(V3_ROOT, "kernel")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable

# Import Phase 1 modules
from v3.external.capability_contract import (
    CapabilityType,
    CapabilityExecutionMode,
    CapabilityRiskLevel,
    CapabilityInputContract,
    CapabilityOutputContract,
    CapabilityEvidence,
    CapabilityRunResult,
    CapabilityRiskReport,
    ExternalCapabilityAdapterSpec,
    compute_stable_hash,
    validate_adapter_spec,
    validate_run_result,
    make_evidence,
    make_blocked_result,
    make_planned_result,
)
from v3.external.capability_lifecycle import (
    STATE_PROPOSED,
    STATE_REGISTERED,
    STATE_INSPECTED,
    STATE_TRIALED,
    STATE_ADAPTER_READY,
    STATE_APPROVED,
    STATE_DEPRECATED,
    STATE_DISABLED,
    STATE_REJECTED,
    ALL_STATES,
    CapabilityLifecycleRecord,
    CapabilityLifecyclePolicy,
    validate_lifecycle_transition,
    make_lifecycle_record,
    lifecycle_is_active,
    lifecycle_is_terminal,
    ALLOWED_TRANSITIONS,
    FORWARD_TRANSITIONS,
    TERMINAL_STATES,
    ACTIVE_STATES,
)


def _run_test_suite(relative_path):
    result = subprocess.run(
        [PYTHON, os.path.join(ROOT, relative_path)],
        capture_output=True, text=True, timeout=120,
        cwd=ROOT,
    )
    return result.returncode, result.stdout, result.stderr


class TestCapabilityContract(unittest.TestCase):

    # ── Test 1: adapter spec is frozen ──────────────────────────────────

    def test_01_adapter_spec_is_frozen(self):
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="test-adapter",
            name="Test Adapter",
            capability_type=CapabilityType.tool.value,
            forbidden_actions=("no_network",),
        )
        with self.assertRaises(Exception):
            spec.adapter_id = "modified"

    # ── Test 2: evidence is frozen ──────────────────────────────────────

    def test_02_evidence_is_frozen(self):
        ev = CapabilityEvidence(
            evidence_id="ev-test",
            adapter_id="test-adapter",
        )
        with self.assertRaises(Exception):
            ev.truth_source = True

    # ── Test 3: run result is frozen ────────────────────────────────────

    def test_03_run_result_is_frozen(self):
        result = CapabilityRunResult(
            adapter_id="test-adapter",
            status="planned",
        )
        with self.assertRaises(Exception):
            result.status = "completed"

    # ── Test 4: risk report is frozen ───────────────────────────────────

    def test_04_risk_report_is_frozen(self):
        report = CapabilityRiskReport(adapter_id="test-adapter")
        with self.assertRaises(Exception):
            report.risk_level = "low"

    # ── Test 5: hash deterministic ──────────────────────────────────────

    def test_05_hash_deterministic(self):
        spec1 = ExternalCapabilityAdapterSpec(
            adapter_id="hash-test",
            name="Hash Test",
            capability_type=CapabilityType.context.value,
            forbidden_actions=("no_network",),
        )
        spec2 = ExternalCapabilityAdapterSpec(
            adapter_id="hash-test",
            name="Hash Test",
            capability_type=CapabilityType.context.value,
            forbidden_actions=("no_network",),
        )
        h1 = compute_stable_hash(spec1)
        h2 = compute_stable_hash(spec2)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 16)

    # ── Test 6: truth_source false enforced ─────────────────────────────

    def test_06_truth_source_false_enforced(self):
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="ts-test",
            name="Truth Source Test",
            forbidden_actions=("no_network",),
            truth_source=False,
        )
        self.assertFalse(spec.truth_source)
        valid, errors = validate_adapter_spec(spec)
        self.assertTrue(valid, f"Spec should be valid: {errors}")

    # ── Test 7: removable true enforced ─────────────────────────────────

    def test_07_removable_true_enforced(self):
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="rm-test",
            name="Removable Test",
            forbidden_actions=("no_network",),
            removable=True,
        )
        self.assertTrue(spec.removable)
        valid, _ = validate_adapter_spec(spec)
        self.assertTrue(valid)

    # ── Test 8: empty adapter_id invalid ────────────────────────────────

    def test_08_empty_adapter_id_invalid(self):
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="",
            name="No ID",
            forbidden_actions=("no_network",),
        )
        valid, errors = validate_adapter_spec(spec)
        self.assertFalse(valid)
        self.assertTrue(any("adapter_id" in e for e in errors))

    # ── Test 9: forbidden actions required ──────────────────────────────

    def test_09_forbidden_actions_required(self):
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="no-fa",
            name="No Forbidden Actions",
            forbidden_actions=(),  # empty
        )
        valid, errors = validate_adapter_spec(spec)
        self.assertFalse(valid)
        self.assertTrue(any("forbidden_actions" in e for e in errors))

    # ── Test 10: explicit_execute requires approval ─────────────────────

    def test_10_explicit_execute_requires_approval(self):
        input_contract = CapabilityInputContract(
            requires_approval=False,
        )
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="no-approval-exec",
            name="No Approval Execute",
            execution_modes=("explicit_execute",),
            forbidden_actions=("no_network",),
            input_contract=input_contract,
        )
        valid, errors = validate_adapter_spec(spec)
        self.assertFalse(valid)
        self.assertTrue(any("approval" in e.lower() for e in errors))

    # ── Test 11: network requires approval ──────────────────────────────

    def test_11_network_requires_approval(self):
        input_contract = CapabilityInputContract(
            allows_network=True,
            requires_approval=False,
        )
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="net-no-approval",
            name="Network No Approval",
            forbidden_actions=("no_filesystem_write",),
            input_contract=input_contract,
        )
        valid, errors = validate_adapter_spec(spec)
        self.assertFalse(valid)
        self.assertTrue(any("network" in e.lower() for e in errors))

    # ── Test 12: filesystem write requires approval ─────────────────────

    def test_12_filesystem_write_requires_approval(self):
        input_contract = CapabilityInputContract(
            allows_filesystem_write=True,
            requires_approval=False,
        )
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="fsw-no-approval",
            name="FS Write No Approval",
            forbidden_actions=("no_network",),
            input_contract=input_contract,
        )
        valid, errors = validate_adapter_spec(spec)
        self.assertFalse(valid)
        self.assertTrue(any("filesystem" in e.lower() for e in errors))

    # ── Test 13: critical risk blocks by default ────────────────────────

    def test_13_critical_risk_blocks_default(self):
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="critical-adapter",
            name="Critical Adapter",
            risk_level=CapabilityRiskLevel.critical.value,
            execution_modes=("dry_run",),
            forbidden_actions=("no_network",),
        )
        valid, errors = validate_adapter_spec(spec)
        self.assertFalse(valid)
        self.assertTrue(any("disabled" in e for e in errors))

    # ── Test 14: planned result validates ───────────────────────────────

    def test_14_planned_result_validates(self):
        result = make_planned_result("test-adapter")
        valid, errors = validate_run_result(result)
        self.assertTrue(valid, f"Planned result should be valid: {errors}")
        self.assertEqual(result.status, "planned")

    # ── Test 15: blocked result validates ───────────────────────────────

    def test_15_blocked_result_validates(self):
        result = make_blocked_result("test-adapter", "Too risky")
        valid, errors = validate_run_result(result)
        self.assertTrue(valid, f"Blocked result should be valid: {errors}")
        self.assertEqual(result.status, "blocked")
        self.assertIn("BLOCKED", result.warnings[0])

    # ── Test 16: evidence validates ─────────────────────────────────────

    def test_16_evidence_validates(self):
        ev = make_evidence(
            adapter_id="test-adapter",
            capability_type="context",
            input_data={"target": "./src"},
            output_data={"files": 10},
        )
        self.assertFalse(ev.truth_source)
        self.assertNotEqual(ev.evidence_hash, "")
        self.assertNotEqual(ev.evidence_id, "")
        self.assertTrue(ev.evidence_id.startswith("ev-"))

    # ── Test 17: output contract truth_source false ─────────────────────

    def test_17_output_contract_truth_source_false(self):
        oc = CapabilityOutputContract()
        self.assertFalse(oc.truth_source)
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="oc-test",
            name="OC Test",
            forbidden_actions=("no_network",),
            output_contract=oc,
        )
        valid, _ = validate_adapter_spec(spec)
        self.assertTrue(valid)

    # ── Test 18: lifecycle valid proposed → registered ──────────────────

    def test_18_lifecycle_proposed_to_registered(self):
        valid, reason = validate_lifecycle_transition(
            STATE_PROPOSED, STATE_REGISTERED
        )
        self.assertTrue(valid, reason)

    # ── Test 19: lifecycle valid registered → inspected ─────────────────

    def test_19_lifecycle_registered_to_inspected(self):
        valid, reason = validate_lifecycle_transition(
            STATE_REGISTERED, STATE_INSPECTED
        )
        self.assertTrue(valid, reason)

    # ── Test 20: lifecycle valid inspected → trialed ────────────────────

    def test_20_lifecycle_inspected_to_trialed(self):
        valid, reason = validate_lifecycle_transition(
            STATE_INSPECTED, STATE_TRIALED
        )
        self.assertTrue(valid, reason)

    # ── Test 21: lifecycle valid trialed → adapter_ready ────────────────

    def test_21_lifecycle_trialed_to_adapter_ready(self):
        valid, reason = validate_lifecycle_transition(
            STATE_TRIALED, STATE_ADAPTER_READY
        )
        self.assertTrue(valid, reason)

    # ── Test 22: lifecycle invalid proposed → approved ──────────────────

    def test_22_lifecycle_proposed_to_approved_invalid(self):
        valid, reason = validate_lifecycle_transition(
            STATE_PROPOSED, STATE_APPROVED
        )
        self.assertFalse(valid)
        self.assertIn("not allowed", reason.lower())

    # ── Test 23: approved requires adapter_ready first ──────────────────

    def test_23_approved_requires_adapter_ready(self):
        valid, reason = validate_lifecycle_transition(
            STATE_ADAPTER_READY, STATE_APPROVED
        )
        self.assertTrue(valid, reason)
        self.assertIn("approval", reason.lower())

    # ── Test 24: disabled terminal ──────────────────────────────────────

    def test_24_disabled_terminal(self):
        self.assertTrue(lifecycle_is_terminal(STATE_DISABLED))
        self.assertIn(STATE_DISABLED, TERMINAL_STATES)

    # ── Test 25: rejected terminal ──────────────────────────────────────

    def test_25_rejected_terminal(self):
        self.assertTrue(lifecycle_is_terminal(STATE_REJECTED))
        self.assertIn(STATE_REJECTED, TERMINAL_STATES)

    # ── Test 26: lifecycle record hash deterministic ────────────────────

    def test_26_lifecycle_record_hash_deterministic(self):
        r1 = make_lifecycle_record(
            adapter_id="hash-adapter",
            state=STATE_REGISTERED,
            previous_state=STATE_PROPOSED,
            timestamp="2026-05-26T00:00:00+00:00",
        )
        r2 = make_lifecycle_record(
            adapter_id="hash-adapter",
            state=STATE_REGISTERED,
            previous_state=STATE_PROPOSED,
            timestamp="2026-05-26T00:00:00+00:00",
        )
        self.assertEqual(r1.record_hash, r2.record_hash)
        self.assertEqual(len(r1.record_hash), 16)

    # ── Test 27: no LLM/vector/agent framework imports ──────────────────

    def test_27_no_banned_imports(self):
        BANNED = {"openai", "anthropic", "langchain", "crewai", "autogen",
                  "mem0", "graphiti", "chromadb", "qdrant", "milvus"}
        phase1_files = [
            "capability_contract.py",
            "capability_lifecycle.py",
        ]
        for fname in phase1_files:
            fpath = os.path.join(EXTERNAL_DIR, fname)
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0].lower()
                        self.assertNotIn(root, BANNED,
                                         f"{fname} imports banned module: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root = node.module.split(".")[0].lower()
                        self.assertNotIn(root, BANNED,
                                         f"{fname} imports banned module: {node.module}")

    # ── Test 28: v3/kernel untouched ────────────────────────────────────

    def test_28_kernel_untouched(self):
        """Verify no kernel files were modified during Phase 1."""
        from v3.release.v4_baseline_guard import _check_kernel_immutability
        check = _check_kernel_immutability(ROOT)
        self.assertTrue(
            check["pass"],
            f"Kernel files modified: {check['modified_files']}"
        )

    # ── Test 29: lifecycle policy transitions ───────────────────────────

    def test_29_lifecycle_policy(self):
        policy = CapabilityLifecyclePolicy()
        self.assertIn(STATE_PROPOSED, policy.allowed_transitions)
        self.assertEqual(
            policy.allowed_transitions[STATE_PROPOSED],
            (STATE_REGISTERED, STATE_REJECTED, STATE_DISABLED),
        )

    # ── Test 30: all enums have expected values ─────────────────────────

    def test_30_enum_values(self):
        self.assertEqual(len(CapabilityType), 10)  # +direction, +quality in v4.1
        self.assertEqual(len(CapabilityExecutionMode), 5)
        self.assertEqual(len(CapabilityRiskLevel), 4)
        self.assertEqual(len(ALL_STATES), 9)

    # ── Test 31: compute_stable_hash same input same output ─────────────

    def test_31_hash_consistent_across_objects(self):
        h1 = compute_stable_hash({"a": 1, "b": 2})
        h2 = compute_stable_hash({"b": 2, "a": 1})
        self.assertEqual(h1, h2, "Hash must be order-independent (sorted keys)")


class TestPhase1Regression(unittest.TestCase):
    """Regression tests verifying Phase 1 doesn't break existing systems."""

    def test_external_tools_wrapup_passes(self):
        rc, stdout, stderr = _run_test_suite(
            "v3/tests/test_external_tools_wrapup.py"
        )
        self.assertEqual(rc, 0,
                         f"External tools wrapup failed:\n{stderr[:1000]}")

    def test_kernel_invariants_passes(self):
        rc, stdout, stderr = _run_test_suite(
            "v3/tests/test_kernel_invariants.py"
        )
        self.assertEqual(rc, 0,
                         f"Kernel invariants failed:\n{stderr[:1000]}")
        self.assertIn("purity_score == 100", stdout)

    def test_complexity_gate_not_reject(self):
        from v3.quality.phase_gate import evaluate_phase
        result = evaluate_phase("Phase1", v3_root=V3_ROOT)
        self.assertNotEqual(
            result.verdict.verdict, "REJECT",
            f"Complexity gate REJECTED: {'; '.join(result.verdict.reasons)}"
        )


if __name__ == "__main__":
    unittest.main()
