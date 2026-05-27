"""
Memory Intelligence Plane Tests — Phase 5.

47 tests for the Memory Intelligence Plane: providers, signals, requests,
results, reports, policy validation, profiles, evidence mapping, and CLI.
Stdlib only. No external services. No LLM/vector/graph DB.
"""

import ast
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

from v3.external.memory_intelligence import (
    MemoryIntelligenceProvider,
    MemorySignal,
    MemoryIntelligenceRequest,
    MemoryIntelligenceResult,
    MemoryIntelligenceReport,
    MemorySignalValidationResult,
    MemoryIntelligenceValidationResult,
    PROVIDER_TYPE_MEM0_LIKE,
    PROVIDER_TYPE_GRAPHITI_LIKE,
    PROVIDER_TYPE_LETTA_LIKE,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    ALL_PROVIDER_TYPES,
    SIGNAL_TYPE_ADD,
    SIGNAL_TYPE_UPDATE,
    SIGNAL_TYPE_DELETE,
    SIGNAL_TYPE_NOOP,
    SIGNAL_TYPE_TEMPORAL_FACT,
    SIGNAL_TYPE_ENTITY_LINK,
    SIGNAL_TYPE_RETRIEVAL_HINT,
    ALL_SIGNAL_TYPES,
    SUGGESTION_ONLY_SIGNAL_TYPES,
    MODE_INSPECT_ONLY,
    MODE_DRY_RUN,
    MODE_EXTERNAL_SERVICE,
    make_memory_signal,
    build_memory_intelligence_request,
    make_blocked_memory_result,
    mock_memory_intelligence_result,
    memory_signals_to_evidence,
    build_memory_intelligence_report,
    validate_memory_signal,
    validate_memory_intelligence_result,
)
from v3.external.memory_intelligence_policy import (
    MemoryIntelligencePolicy,
    POLICY_PASS,
    POLICY_BLOCKED,
    POLICY_REVIEW,
    default_memory_intelligence_policy,
    validate_provider_against_policy,
    validate_result_against_policy,
    block_provider_reason,
)
from v3.external.memory_intelligence_profiles import (
    get_all_profiles,
    get_profile,
    evaluate_all_profiles,
    mem0_memory_intelligence_profile,
    graphiti_temporal_kg_profile,
    letta_stateful_memory_profile,
    deterministic_mock_memory_profile,
)


def _run_module(module_path, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    result = subprocess.run(
        [PYTHON, module_path] + list(args),
        capture_output=True, text=True, timeout=30,
        cwd=ROOT, env=env,
    )
    return result.returncode, result.stdout, result.stderr


class TestMemoryIntelligencePlane(unittest.TestCase):

    # ═══════════════════════════════════════════════════════════════════
    # Dataclass freezing
    # ═══════════════════════════════════════════════════════════════════

    def test_01_provider_frozen(self):
        """MemoryIntelligenceProvider is frozen."""
        p = deterministic_mock_memory_profile()
        with self.assertRaises(Exception):
            p.provider_id = "changed"

    def test_02_signal_frozen(self):
        """MemorySignal is frozen."""
        s = make_memory_signal(signal_type=SIGNAL_TYPE_NOOP)
        with self.assertRaises(Exception):
            s.signal_type = "changed"

    def test_03_request_frozen(self):
        """MemoryIntelligenceRequest is frozen."""
        req = build_memory_intelligence_request("test")
        with self.assertRaises(Exception):
            req.provider_id = "changed"

    def test_04_result_frozen(self):
        """MemoryIntelligenceResult is frozen."""
        req = build_memory_intelligence_request("test")
        result = mock_memory_intelligence_result(req, 1)
        with self.assertRaises(Exception):
            result.blocked = True

    def test_05_report_frozen(self):
        """MemoryIntelligenceReport is frozen."""
        provider = deterministic_mock_memory_profile()
        req = build_memory_intelligence_request("test")
        result = mock_memory_intelligence_result(req, 1)
        bundle = memory_signals_to_evidence(result)
        report = build_memory_intelligence_report(provider, req, result, bundle)
        with self.assertRaises(Exception):
            report.policy_status = "changed"

    # ═══════════════════════════════════════════════════════════════════
    # Hash determinism
    # ═══════════════════════════════════════════════════════════════════

    def test_06_provider_hash_deterministic(self):
        """Same provider config → same hash."""
        p1 = deterministic_mock_memory_profile()
        p2 = deterministic_mock_memory_profile()
        self.assertEqual(p1.provider_hash, p2.provider_hash)

    def test_07_signal_hash_deterministic(self):
        """Same signal params → same hash."""
        s1 = make_memory_signal(
            signal_type=SIGNAL_TYPE_ENTITY_LINK,
            source_record_ids=("r1",),
            source_hashes=("abc",),
            content="test",
        )
        s2 = make_memory_signal(
            signal_type=SIGNAL_TYPE_ENTITY_LINK,
            source_record_ids=("r1",),
            source_hashes=("abc",),
            content="test",
        )
        self.assertEqual(s1.signal_id, s2.signal_id)
        self.assertEqual(s1.signal_hash, s2.signal_hash)

    def test_08_result_hash_deterministic(self):
        """Same request → same mock result."""
        req1 = build_memory_intelligence_request("test", ("a", "b"), ("c",))
        req2 = build_memory_intelligence_request("test", ("a", "b"), ("c",))
        r1 = mock_memory_intelligence_result(req1, 2)
        r2 = mock_memory_intelligence_result(req2, 2)
        self.assertEqual(r1.result_hash, r2.result_hash)

    # ═══════════════════════════════════════════════════════════════════
    # truth_source invariants
    # ═══════════════════════════════════════════════════════════════════

    def test_09_truth_source_false_provider(self):
        """All providers have truth_source=False."""
        for p in get_all_profiles():
            self.assertFalse(p.truth_source,
                             f"{p.provider_id} truth_source is not False")

    def test_10_truth_source_false_signal(self):
        """Signal truth_source is always False."""
        s = make_memory_signal(signal_type=SIGNAL_TYPE_ADD)
        self.assertFalse(s.truth_source)

    def test_11_truth_source_false_result(self):
        """Result truth_source is always False."""
        req = build_memory_intelligence_request("test")
        result = mock_memory_intelligence_result(req, 1)
        self.assertFalse(result.truth_source)

    def test_12_removable_true(self):
        """All providers have removable=True."""
        for p in get_all_profiles():
            self.assertTrue(p.removable,
                            f"{p.provider_id} removable is not True")

    # ═══════════════════════════════════════════════════════════════════
    # Provider policy blocking
    # ═══════════════════════════════════════════════════════════════════

    def test_13_llm_provider_blocked(self):
        """LLM-requiring provider blocked by default policy."""
        policy = default_memory_intelligence_policy()
        self.assertFalse(policy.allow_llm_providers)
        mem0 = mem0_memory_intelligence_profile()
        allowed, reason = validate_provider_against_policy(mem0, policy)
        self.assertFalse(allowed)
        self.assertIn("LLM", reason)

    def test_14_vector_db_provider_blocked(self):
        """Vector DB provider blocked by default policy."""
        policy = default_memory_intelligence_policy()
        self.assertFalse(policy.allow_vector_db_providers)
        mem0 = mem0_memory_intelligence_profile()
        reason = block_provider_reason(mem0, policy)
        self.assertIn("LLM", reason)  # First match on LLM

    def test_15_graph_db_provider_blocked(self):
        """Graph DB provider blocked by default policy."""
        policy = default_memory_intelligence_policy()
        self.assertFalse(policy.allow_graph_db_providers)
        graphiti = graphiti_temporal_kg_profile()
        allowed, reason = validate_provider_against_policy(graphiti, policy)
        self.assertFalse(allowed)

    def test_16_external_service_provider_blocked(self):
        """External service provider blocked by default policy."""
        policy = default_memory_intelligence_policy()
        self.assertFalse(policy.allow_external_services)
        letta = letta_stateful_memory_profile()
        allowed, reason = validate_provider_against_policy(letta, policy)
        self.assertFalse(allowed)

    def test_17_deterministic_mock_allowed(self):
        """Deterministic mock provider passes default policy."""
        policy = default_memory_intelligence_policy()
        mock = deterministic_mock_memory_profile()
        allowed, reason = validate_provider_against_policy(mock, policy)
        self.assertTrue(allowed, f"Mock should be allowed: {reason}")

    # ═══════════════════════════════════════════════════════════════════
    # Signal type rules
    # ═══════════════════════════════════════════════════════════════════

    def test_18_delete_signal_suggestion_only(self):
        """Delete signal is suggestion only."""
        self.assertIn(SIGNAL_TYPE_DELETE, SUGGESTION_ONLY_SIGNAL_TYPES)

    def test_19_update_signal_suggestion_only(self):
        """Update signal is suggestion only."""
        self.assertIn(SIGNAL_TYPE_UPDATE, SUGGESTION_ONLY_SIGNAL_TYPES)

    def test_20_signals_sorted_deterministically(self):
        """Mock result signals have deterministic order."""
        req = build_memory_intelligence_request("test", ("c", "a", "b"))
        r1 = mock_memory_intelligence_result(req, 3)
        r2 = mock_memory_intelligence_result(req, 3)
        ids1 = [s.signal_id for s in r1.signals]
        ids2 = [s.signal_id for s in r2.signals]
        self.assertEqual(ids1, ids2)

    def test_21_add_signal_not_suggestion_only(self):
        """Add signal is NOT suggestion-only."""
        self.assertNotIn(SIGNAL_TYPE_ADD, SUGGESTION_ONLY_SIGNAL_TYPES)
        self.assertNotIn(SIGNAL_TYPE_NOOP, SUGGESTION_ONLY_SIGNAL_TYPES)

    # ═══════════════════════════════════════════════════════════════════
    # max_signals enforcement
    # ═══════════════════════════════════════════════════════════════════

    def test_22_max_signals_enforced(self):
        """Mock result respects request max_signals."""
        req = build_memory_intelligence_request("test", ("a", "b", "c", "d", "e"),
                                                  max_signals=2)
        result = mock_memory_intelligence_result(req, 5)
        self.assertLessEqual(len(result.signals), 2)

    def test_23_max_signals_policy_enforced(self):
        """Result exceeding policy max_signals is rejected."""
        policy = MemoryIntelligencePolicy(max_signals=1)
        req = build_memory_intelligence_request("test", ("a", "b", "c"), max_signals=5)
        result = mock_memory_intelligence_result(req, 3)
        valid, reason = validate_result_against_policy(result, policy)
        self.assertFalse(valid)
        self.assertIn("max is 1", reason)

    # ═══════════════════════════════════════════════════════════════════
    # Forbidden signal types
    # ═══════════════════════════════════════════════════════════════════

    def test_24_forbidden_signal_type_rejected(self):
        """Signal with forbidden type rejected by policy."""
        policy = MemoryIntelligencePolicy(
            forbidden_signal_types=(SIGNAL_TYPE_DELETE,),
        )
        s = make_memory_signal(signal_type=SIGNAL_TYPE_DELETE,
                               source_hashes=("abc",), provenance="test")
        result = MemoryIntelligenceResult(
            request_id="test",
            provider_id="test",
            signals=(s,),
            truth_source=False,
        )
        valid, reason = validate_result_against_policy(result, policy)
        self.assertFalse(valid)

    def test_25_provenance_required_by_policy(self):
        """Signal without provenance rejected when policy requires it."""
        policy = MemoryIntelligencePolicy(require_provenance=True)
        s = make_memory_signal(signal_type=SIGNAL_TYPE_NOOP, provenance="")
        result = MemoryIntelligenceResult(
            request_id="test", provider_id="test",
            signals=(s,), truth_source=False,
        )
        valid, reason = validate_result_against_policy(result, policy)
        self.assertFalse(valid)
        self.assertIn("provenance", reason)

    # ═══════════════════════════════════════════════════════════════════
    # Blocked results
    # ═══════════════════════════════════════════════════════════════════

    def test_26_blocked_result_has_reason(self):
        """Blocked result must have a reason."""
        blocked = make_blocked_memory_result("r1", "p1", "Policy blocks LLM")
        self.assertTrue(blocked.blocked)
        self.assertGreater(len(blocked.reason), 0)
        self.assertEqual(len(blocked.signals), 0)

    def test_27_blocked_result_validates(self):
        """Blocked result passes validation."""
        blocked = make_blocked_memory_result("r1", "p1", "test reason")
        valid_result = validate_memory_intelligence_result(blocked)
        self.assertTrue(valid_result.valid)

    def test_28_mock_result_validates(self):
        """Mock result passes validation."""
        req = build_memory_intelligence_request("test", ("a", "b"))
        result = mock_memory_intelligence_result(req, 2)
        valid_result = validate_memory_intelligence_result(result)
        self.assertTrue(valid_result.valid)

    def test_29_truth_source_violation_detected(self):
        """Signal with truth_source=True is flagged."""
        s = MemorySignal(
            signal_id="bad", signal_type=SIGNAL_TYPE_NOOP,
            truth_source=True,
        )
        vr = validate_memory_signal(s)
        self.assertFalse(vr.valid)

    # ═══════════════════════════════════════════════════════════════════
    # Evidence mapping
    # ═══════════════════════════════════════════════════════════════════

    def test_30_signals_convert_to_evidence(self):
        """Memory signals are mapped to evidence records."""
        req = build_memory_intelligence_request("test", ("a", "b"))
        result = mock_memory_intelligence_result(req, 2)
        bundle = memory_signals_to_evidence(result, registry_hash="test:hash")
        self.assertEqual(len(bundle.records), 2)
        self.assertTrue(bundle.bundle_id)

    def test_31_evidence_truth_source_false(self):
        """All evidence records from signals have truth_source=False."""
        req = build_memory_intelligence_request("test", ("a",))
        result = mock_memory_intelligence_result(req, 1)
        bundle = memory_signals_to_evidence(result)
        for r in bundle.records:
            self.assertFalse(r.truth_source)

    def test_32_registry_hash_in_provenance(self):
        """Registry hash is included in evidence provenance."""
        req = build_memory_intelligence_request("test", ("a",))
        result = mock_memory_intelligence_result(req, 1)
        bundle = memory_signals_to_evidence(result, registry_hash="reg:abc123")
        for r in bundle.records:
            self.assertIsNotNone(r.provenance)
            self.assertEqual(r.provenance.registry_hash, "reg:abc123")

    # ═══════════════════════════════════════════════════════════════════
    # Profiles
    # ═══════════════════════════════════════════════════════════════════

    def test_33_profiles_load(self):
        """All 4 provider profiles load."""
        profiles = get_all_profiles()
        self.assertEqual(len(profiles), 4)

    def test_34_mem0_profile_blocked(self):
        """mem0 profile is blocked by default policy."""
        policy = default_memory_intelligence_policy()
        mem0 = mem0_memory_intelligence_profile()
        allowed, _ = validate_provider_against_policy(mem0, policy)
        self.assertFalse(allowed)
        self.assertTrue(mem0.requires_llm)

    def test_35_graphiti_profile_blocked(self):
        """Graphiti profile is blocked by default policy."""
        policy = default_memory_intelligence_policy()
        g = graphiti_temporal_kg_profile()
        allowed, _ = validate_provider_against_policy(g, policy)
        self.assertFalse(allowed)
        self.assertTrue(g.requires_graph_db)

    def test_36_letta_profile_blocked(self):
        """Letta profile is blocked by default policy."""
        policy = default_memory_intelligence_policy()
        l = letta_stateful_memory_profile()
        allowed, _ = validate_provider_against_policy(l, policy)
        self.assertFalse(allowed)

    def test_37_mock_profile_allowed(self):
        """Mock profile is allowed by default policy."""
        policy = default_memory_intelligence_policy()
        m = deterministic_mock_memory_profile()
        allowed, _ = validate_provider_against_policy(m, policy)
        self.assertTrue(allowed)
        self.assertFalse(m.requires_llm)

    def test_38_evaluate_all_profiles(self):
        """evaluate_all_profiles returns status for all 4 profiles."""
        policy = default_memory_intelligence_policy()
        statuses = evaluate_all_profiles(policy)
        self.assertEqual(len(statuses), 4)
        allowed = {s.provider_id: s.allowed for s in statuses}
        self.assertTrue(allowed["deterministic_mock_memory"])
        self.assertFalse(allowed["mem0_memory_intelligence"])
        self.assertFalse(allowed["graphiti_temporal_kg"])
        self.assertFalse(allowed["letta_stateful_memory"])

    def test_39_get_profile_unknown(self):
        """get_profile returns None for unknown ID."""
        self.assertIsNone(get_profile("nonexistent"))

    # ═══════════════════════════════════════════════════════════════════
    # CLI
    # ═══════════════════════════════════════════════════════════════════

    def test_40_cli_profiles(self):
        """CLI memory-intel profiles lists profiles."""
        rc, stdout, stderr = _run_module(
            os.path.join(V3_ROOT, "cli", "systemkernel.py"),
            "memory-intel", "profiles",
        )
        self.assertEqual(rc, 0)
        self.assertIn("Memory Intelligence Plane", stdout)
        self.assertIn("deterministic_mock_memory", stdout)
        self.assertIn("mem0_memory_intelligence", stdout)

    def test_41_cli_mock(self):
        """CLI memory-intel mock generates mock result."""
        rc, stdout, stderr = _run_module(
            os.path.join(V3_ROOT, "cli", "systemkernel.py"),
            "memory-intel", "mock",
            "--provider", "deterministic_mock_memory",
            "--signals", "2",
        )
        self.assertEqual(rc, 0)
        self.assertIn("Signals generated", stdout)
        self.assertIn("false", stdout.lower())

    def test_42_cli_mock_blocked_provider(self):
        """CLI mock with blocked provider returns error."""
        rc, stdout, stderr = _run_module(
            os.path.join(V3_ROOT, "cli", "systemkernel.py"),
            "memory-intel", "mock",
            "--provider", "mem0_memory_intelligence",
        )
        self.assertEqual(rc, 1)
        self.assertIn("Policy allowed", stdout)

    def test_43_cli_evidence(self):
        """CLI memory-intel evidence builds evidence bundle."""
        rc, stdout, stderr = _run_module(
            os.path.join(V3_ROOT, "cli", "systemkernel.py"),
            "memory-intel", "evidence",
            "--provider", "deterministic_mock_memory",
            "--output", "/tmp/test_mi_evidence.json",
        )
        self.assertEqual(rc, 0)
        self.assertIn("Evidence bundle", stdout)
        self.assertIn("Report written", stdout)

    # ═══════════════════════════════════════════════════════════════════
    # Purity / no-kernel-modify / no-external-service
    # ═══════════════════════════════════════════════════════════════════

    def test_44_no_banned_imports(self):
        """Phase 5 files must not import LLM/vector/graph DB frameworks."""
        BANNED = {"openai", "anthropic", "langchain", "crewai", "autogen",
                  "mem0", "graphiti", "chromadb", "qdrant", "milvus",
                  "letta", "neo4j", "networkx"}
        phase5_files = [
            "memory_intelligence.py",
            "memory_intelligence_policy.py",
            "memory_intelligence_profiles.py",
        ]
        for fname in phase5_files:
            fpath = os.path.join(EXTERNAL_DIR, fname)
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0].lower()
                        self.assertNotIn(root, BANNED,
                                         f"{fname} imports banned: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root = node.module.split(".")[0].lower()
                        self.assertNotIn(root, BANNED,
                                         f"{fname} imports banned: {node.module}")

    def test_45_no_external_service_calls(self):
        """Phase 5 code does not call external services."""
        phase5_files = [
            "memory_intelligence.py",
            "memory_intelligence_policy.py",
            "memory_intelligence_profiles.py",
        ]
        for fname in phase5_files:
            fpath = os.path.join(EXTERNAL_DIR, fname)
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            self.assertNotIn("subprocess.run", source)
            self.assertNotIn("subprocess.call", source)
            self.assertNotIn("os.system", source)
            self.assertNotIn("urllib.request", source)
            self.assertNotIn("http.client", source)
            self.assertNotIn("socket.connect", source)

    def test_46_signal_types_complete(self):
        """All 7 signal types defined."""
        self.assertEqual(len(ALL_SIGNAL_TYPES), 7)
        self.assertIn(SIGNAL_TYPE_ADD, ALL_SIGNAL_TYPES)
        self.assertIn(SIGNAL_TYPE_NOOP, ALL_SIGNAL_TYPES)
        self.assertIn(SIGNAL_TYPE_TEMPORAL_FACT, ALL_SIGNAL_TYPES)

    def test_47_provider_types_complete(self):
        """All 5 provider types defined."""
        self.assertEqual(len(ALL_PROVIDER_TYPES), 5)
        self.assertIn(PROVIDER_TYPE_DETERMINISTIC_MOCK, ALL_PROVIDER_TYPES)


class TestPhase5Regression(unittest.TestCase):

    def test_v4_baseline_guard_passes(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_v4_baseline_guard.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Baseline guard failed:\n{result.stderr[:1000]}")

    def test_kernel_invariants_passes(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_kernel_invariants.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Kernel invariants failed:\n{result.stderr[:1000]}")
        self.assertIn("purity_score == 100", result.stdout)

    def test_evidence_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_external_evidence.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Evidence tests failed:\n{result.stderr[:1000]}")

    def test_context_plane_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_context_engineering_plane.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Context plane tests failed:\n{result.stderr[:1000]}")

    def test_registry_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_capability_registry.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Registry tests failed:\n{result.stderr[:1000]}")

    def test_contract_tests_still_pass(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_capability_contract.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Contract tests failed:\n{result.stderr[:1000]}")


if __name__ == "__main__":
    unittest.main()
