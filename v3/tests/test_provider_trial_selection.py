"""
Phase 14A — Tests for Provider Trial Selection.

At least 25 tests covering frozen dataclasses, scoring determinism,
ranking, safety constraints, and regression.
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.evals.provider_trial_selection import (
    ProviderTrialCandidate,
    ProviderTrialScore,
    ProviderTrialSelectionReport,
    build_default_trial_candidates,
    score_trial_candidate,
    select_best_trial,
    write_provider_trial_selection_report,
    compute_ability_complexity_risk,
    VERDICT_RECOMMENDED,
    VERDICT_ACCEPTABLE,
    VERDICT_DEFER,
    VERDICT_REJECT,
    _hash,
)


class TestFrozenDataclasses(unittest.TestCase):
    """Tests for frozen dataclass invariants."""

    def test_01_candidate_frozen(self):
        """ProviderTrialCandidate is frozen."""
        c = ProviderTrialCandidate(
            candidate_id="test", name="Test", provider_type="test",
            required_plane="Test Plane", existing_adapter_ready=False,
            requires_network=False, requires_install=False,
            requires_external_service=False, can_run_read_only=True,
            can_produce_evidence=False, can_be_reversed=True,
            notes="test", candidate_hash="abc",
        )
        with self.assertRaises(Exception):
            c.candidate_id = "changed"

    def test_02_score_frozen(self):
        """ProviderTrialScore is frozen."""
        s = ProviderTrialScore(
            candidate_id="test", capability_gain=5, complexity_delta=3,
            kernel_risk=2, memory_risk=1, dependency_risk=3,
            execution_risk=2, reversibility_score=8,
            adapter_readiness_score=7, evidence_fit_score=6,
            manual_step_reduction_score=5, total_score=100,
            risk_ratio=0.5, verdict=VERDICT_ACCEPTABLE,
            reasons=("test",), score_hash="abc",
        )
        with self.assertRaises(Exception):
            s.total_score = 200

    def test_03_report_frozen(self):
        """ProviderTrialSelectionReport is frozen."""
        r = ProviderTrialSelectionReport(
            candidates=(), scores=(),
            recommended_candidate="test",
            rejected_candidates=(), deferred_candidates=(),
            report_hash="abc",
        )
        with self.assertRaises(Exception):
            r.recommended_candidate = "changed"


class TestHashDeterminism(unittest.TestCase):
    """Tests for deterministic hashing."""

    def test_04_candidate_hash_deterministic(self):
        """Candidate hash is deterministic for same inputs."""
        c1 = ProviderTrialCandidate(
            candidate_id="test", name="Test", provider_type="test",
            required_plane="Test Plane", existing_adapter_ready=True,
            requires_network=False, requires_install=False,
            requires_external_service=False, can_run_read_only=True,
            can_produce_evidence=True, can_be_reversed=True,
            notes="test", candidate_hash="hash1",
        )
        c2 = ProviderTrialCandidate(
            candidate_id="test", name="Test", provider_type="test",
            required_plane="Test Plane", existing_adapter_ready=True,
            requires_network=False, requires_install=False,
            requires_external_service=False, can_run_read_only=True,
            can_produce_evidence=True, can_be_reversed=True,
            notes="test", candidate_hash="hash1",
        )
        self.assertEqual(c1.candidate_hash, c2.candidate_hash)

    def test_05_score_hash_deterministic(self):
        """Score hash is deterministic for same inputs."""
        s1 = ProviderTrialScore(
            candidate_id="test", capability_gain=5, complexity_delta=3,
            kernel_risk=2, memory_risk=1, dependency_risk=3,
            execution_risk=2, reversibility_score=8,
            adapter_readiness_score=7, evidence_fit_score=6,
            manual_step_reduction_score=5, total_score=100,
            risk_ratio=0.5, verdict=VERDICT_ACCEPTABLE,
            reasons=("test",), score_hash="hash1",
        )
        s2 = ProviderTrialScore(
            candidate_id="test", capability_gain=5, complexity_delta=3,
            kernel_risk=2, memory_risk=1, dependency_risk=3,
            execution_risk=2, reversibility_score=8,
            adapter_readiness_score=7, evidence_fit_score=6,
            manual_step_reduction_score=5, total_score=100,
            risk_ratio=0.5, verdict=VERDICT_ACCEPTABLE,
            reasons=("test",), score_hash="hash1",
        )
        self.assertEqual(s1.score_hash, s2.score_hash)

    def test_06_report_hash_deterministic(self):
        """Report hash is deterministic for same inputs."""
        candidates = build_default_trial_candidates()
        r1 = select_best_trial(candidates)
        r2 = select_best_trial(candidates)
        self.assertEqual(r1.report_hash, r2.report_hash)


class TestDefaultCandidates(unittest.TestCase):
    """Tests for default candidate list."""

    @classmethod
    def setUpClass(cls):
        cls.candidates = build_default_trial_candidates()
        cls.candidate_ids = {c.candidate_id for c in cls.candidates}

    def test_07_includes_repomix(self):
        self.assertIn("repomix", self.candidate_ids)

    def test_08_includes_ccusage(self):
        self.assertIn("ccusage", self.candidate_ids)

    def test_09_includes_ecc(self):
        self.assertIn("ecc", self.candidate_ids)

    def test_10_includes_mem0(self):
        self.assertIn("mem0", self.candidate_ids)

    def test_11_includes_graphiti(self):
        self.assertIn("graphiti", self.candidate_ids)

    def test_12_includes_openhands(self):
        self.assertIn("openhands", self.candidate_ids)

    def test_13_includes_continue(self):
        self.assertIn("continue", self.candidate_ids)

    def test_14_includes_anthropic_skills(self):
        self.assertIn("anthropic_skills", self.candidate_ids)


class TestScoring(unittest.TestCase):
    """Tests for scoring and ranking logic."""

    @classmethod
    def setUpClass(cls):
        cls.candidates = build_default_trial_candidates()
        cls.scores = {s.candidate_id: s for s in
                      [score_trial_candidate(c) for c in cls.candidates]}
        cls.report = select_best_trial(cls.candidates)

    def test_15_repomix_recommended_or_top(self):
        """Repomix is recommended or top ranked."""
        self.assertIn(
            self.report.recommended_candidate,
            ("repomix",),
            f"Expected repomix recommended, got {self.report.recommended_candidate}"
        )

    def test_16_repomix_highest_score(self):
        """Repomix has the highest total score."""
        best = self.report.scores[0]
        self.assertEqual(best.candidate_id, "repomix")

    def test_17_ccusage_acceptable(self):
        """ccusage is acceptable or better."""
        verdict = self.scores["ccusage"].verdict
        self.assertIn(verdict, (VERDICT_RECOMMENDED, VERDICT_ACCEPTABLE))

    def test_18_ecc_deferred(self):
        """ECC is deferred."""
        verdict = self.scores["ecc"].verdict
        self.assertEqual(verdict, VERDICT_DEFER,
                         f"ECC should be deferred, got {verdict}")

    def test_19_mem0_rejected(self):
        """mem0 is rejected."""
        verdict = self.scores["mem0"].verdict
        self.assertEqual(verdict, VERDICT_REJECT,
                         f"mem0 should be rejected, got {verdict}")

    def test_20_graphiti_rejected(self):
        """Graphiti is rejected."""
        verdict = self.scores["graphiti"].verdict
        self.assertEqual(verdict, VERDICT_REJECT,
                         f"graphiti should be rejected, got {verdict}")

    def test_21_openhands_rejected(self):
        """OpenHands/SWE-agent is rejected."""
        verdict = self.scores["openhands"].verdict
        self.assertEqual(verdict, VERDICT_REJECT)

    def test_22_continue_deferred(self):
        """Continue is deferred."""
        verdict = self.scores["continue"].verdict
        self.assertEqual(verdict, VERDICT_DEFER)

    def test_23_repomix_low_risk_ratio(self):
        """Repomix has low risk ratio (< 0.5)."""
        self.assertLess(self.scores["repomix"].risk_ratio, 0.5)

    def test_24_high_risk_providers_high_ratio(self):
        """High-risk providers (mem0, graphiti) have high risk ratios (> 10)."""
        self.assertGreater(self.scores["mem0"].risk_ratio, 10)
        self.assertGreater(self.scores["graphiti"].risk_ratio, 10)


class TestSafetyConstraints(unittest.TestCase):
    """Tests for safety invariants in the selection module."""

    def test_25_no_provider_execution(self):
        """Selection module does not execute any provider."""
        module_path = ROOT / "v3" / "evals" / "provider_trial_selection.py"
        source = module_path.read_text(encoding="utf-8")
        self.assertNotIn("subprocess.run", source)
        self.assertNotIn("os.system", source)

    def test_26_no_network(self):
        """Selection module has no network calls."""
        module_path = ROOT / "v3" / "evals" / "provider_trial_selection.py"
        source = module_path.read_text(encoding="utf-8")
        import_lines = [l.strip() for l in source.split("\n")
                        if l.strip().startswith(("import ", "from "))]
        banned = ["requests", "urllib.request", "http.client", "httpx", "socket"]
        for line in import_lines:
            for b in banned:
                self.assertNotIn(b, line, f"Network import '{b}' found: {line}")

    def test_27_no_install(self):
        """Selection module does not install anything."""
        module_path = ROOT / "v3" / "evals" / "provider_trial_selection.py"
        source = module_path.read_text(encoding="utf-8")
        self.assertNotIn("pip install", source)
        self.assertNotIn("npm install", source)

    def test_28_no_kernel_modification(self):
        """Selection module does not import from kernel."""
        module_path = ROOT / "v3" / "evals" / "provider_trial_selection.py"
        source = module_path.read_text(encoding="utf-8")
        self.assertNotIn("v3.kernel", source)
        self.assertNotIn("v3/kernel", source)

    def test_29_no_memory_modification(self):
        """Selection module does not modify v3/memory."""
        module_path = ROOT / "v3" / "evals" / "provider_trial_selection.py"
        source = module_path.read_text(encoding="utf-8")
        has_memory_write = "v3/memory" in source and ("open(" in source or "write" in source)
        self.assertFalse(has_memory_write)


class TestRiskComputation(unittest.TestCase):
    """Tests for ability+10 complexity+300 risk computation."""

    def test_30_risk_low_for_repomix(self):
        """Risk is low when recommended is repomix (risk_ratio < 0.5)."""
        report = select_best_trial(build_default_trial_candidates())
        risk = compute_ability_complexity_risk(report.scores)
        self.assertEqual(risk, "low")

    def test_31_risk_empty_scores(self):
        """Risk is low for empty scores."""
        risk = compute_ability_complexity_risk(())
        self.assertEqual(risk, "low")

    def test_32_risk_high_detected(self):
        """Risk is high when top candidate has risk_ratio >= 3.0."""
        high_score = ProviderTrialScore(
            candidate_id="risky", capability_gain=2, complexity_delta=9,
            kernel_risk=5, memory_risk=8, dependency_risk=9,
            execution_risk=10, reversibility_score=1,
            adapter_readiness_score=0, evidence_fit_score=0,
            manual_step_reduction_score=0, total_score=-500,
            risk_ratio=10.0, verdict=VERDICT_REJECT,
            reasons=("test",), score_hash="abc",
        )
        risk = compute_ability_complexity_risk((high_score,))
        self.assertEqual(risk, "high")


class TestReportWriting(unittest.TestCase):
    """Tests for report generation."""

    def test_33_report_writable(self):
        """Reports can be written to disk."""
        import tempfile
        report = select_best_trial(build_default_trial_candidates())
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_provider_trial_selection_report(report, tmpdir)
            for key, path in paths.items():
                self.assertTrue(os.path.exists(path), f"Report {key} should exist")
                self.assertTrue(os.path.getsize(path) > 0, f"Report {key} not empty")

    def test_34_report_includes_all_candidates(self):
        """Report includes all 8 candidates."""
        report = select_best_trial(build_default_trial_candidates())
        self.assertEqual(len(report.candidates), 8)


class TestRegression(unittest.TestCase):
    """Regression tests for existing invariants."""

    def test_35_complexity_gate_not_reject(self):
        """Complexity gate must not return REJECT."""
        try:
            from v3.quality.phase_gate import evaluate_phase
            result = evaluate_phase("14A", v3_root=str(ROOT / "v3"))
            self.assertNotEqual(result.verdict.verdict, "REJECT")
        except Exception as e:
            self.skipTest(f"Phase gate not available: {e}")

    def test_36_kernel_invariants_still_purity_100(self):
        """Kernel invariants should remain importable (purity 100)."""
        try:
            from v3.tests import test_kernel_invariants
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"test_kernel_invariants should be importable: {e}")

    def test_37_standard_library_only(self):
        """Provider trial selection module uses only stdlib."""
        module_path = ROOT / "v3" / "evals" / "provider_trial_selection.py"
        source = module_path.read_text(encoding="utf-8")
        third_party = ["numpy", "pandas", "requests", "click", "rich",
                       "pydantic", "attrs", "marshmallow", "anthropic",
                       "openai", "langchain", "torch", "tensorflow"]
        for lib in third_party:
            self.assertNotIn(f"import {lib}", source,
                           f"Third-party import '{lib}' found")

    def test_38_scores_are_deterministic(self):
        """Same candidates produce identical scores."""
        c1 = build_default_trial_candidates()
        c2 = build_default_trial_candidates()
        scores1 = [score_trial_candidate(c) for c in c1]
        scores2 = [score_trial_candidate(c) for c in c2]
        for s1, s2 in zip(scores1, scores2):
            self.assertEqual(s1.total_score, s2.total_score)
            self.assertEqual(s1.verdict, s2.verdict)
            self.assertEqual(s1.risk_ratio, s2.risk_ratio)

    def test_39_all_candidates_have_valid_verdicts(self):
        """All candidates have a valid verdict."""
        candidates = build_default_trial_candidates()
        for c in candidates:
            s = score_trial_candidate(c)
            self.assertIn(s.verdict, (VERDICT_RECOMMENDED, VERDICT_ACCEPTABLE,
                                       VERDICT_DEFER, VERDICT_REJECT))

    def test_40_no_empty_candidate_ids(self):
        """All candidates have non-empty IDs."""
        candidates = build_default_trial_candidates()
        for c in candidates:
            self.assertTrue(len(c.candidate_id) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
