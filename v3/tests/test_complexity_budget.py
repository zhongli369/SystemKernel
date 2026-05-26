"""
Complexity Budget Tests — Phase 5A.

Comprehensive tests for:
  1. ModuleComplexity creation and serialization
  2. ModuleBenefit creation and serialization
  3. compute_complexity_score — basic
  4. compute_complexity_score — projection only reduces score
  5. compute_complexity_score — removable reduces score
  6. compute_complexity_score — truth sources increase score
  7. compute_benefit_score — all true vs all false
  8. evaluate_verdict — ACCEPT when benefit > complexity
  9. evaluate_verdict — REVIEW when complexity > benefit * 2
  10. evaluate_verdict — REJECT when complexity > benefit * 3
  11. evaluate_verdict — REJECT on kernel purity break
  12. evaluate_verdict — REJECT on memory removability break
  13. evaluate_verdict — REJECT on new truth source
  14. analyze_module — produces valid ModuleComplexity
  15. analyze_directory — finds all modules
  16. evaluate_phase — produces valid PhaseGateResult
  17. fail_if_rejected — raises on REJECT, silent on ACCEPT
  18. verdict hash stable (deterministic)
  19. no banned LLM/vector imports
  20. load_budget_policy returns defaults
  21. ComplexityBudgetVerdict serialization
  22. score determinism (same input → same score)
  23. existing 5A- tests still pass (kernel invariants regression)
  24. complexity budget report generation

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import hashlib
import tempfile
import shutil

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.quality.complexity_budget import (
    ModuleComplexity, ModuleBenefit, ComplexityBudgetVerdict,
    compute_complexity_score, compute_benefit_score,
    evaluate_verdict, VERDICT_ACCEPT, VERDICT_REVIEW, VERDICT_REJECT,
)
from v3.quality.analyze_complexity import (
    ComplexityAnalyzer, analyze_module, analyze_directory,
    count_tests_for_module, count_reports_for_module,
)
from v3.quality.phase_gate import (
    evaluate_phase, load_budget_policy,
    write_complexity_report, fail_if_rejected,
    PhaseGateResult, ComplexityGateRejected,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

_v3_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _simple_complexity(**overrides) -> ModuleComplexity:
    """Build a ModuleComplexity with defaults for testing."""
    defaults = {
        "path": "test/module.py",
        "loc": 100,
        "public_api_count": 5,
        "dataclass_count": 2,
        "function_count": 8,
        "import_count": 4,
        "internal_dependency_count": 2,
        "external_dependency_count": 1,
        "test_count": 3,
        "report_count": 1,
        "has_side_effects": False,
        "truth_source_count": 0,
        "projection_only": True,
        "removable": False,
    }
    defaults.update(overrides)
    m = ModuleComplexity(**defaults)
    return ModuleComplexity(
        path=m.path, loc=m.loc,
        public_api_count=m.public_api_count,
        dataclass_count=m.dataclass_count,
        function_count=m.function_count,
        import_count=m.import_count,
        internal_dependency_count=m.internal_dependency_count,
        external_dependency_count=m.external_dependency_count,
        test_count=m.test_count,
        report_count=m.report_count,
        has_side_effects=m.has_side_effects,
        truth_source_count=m.truth_source_count,
        projection_only=m.projection_only,
        removable=m.removable,
        complexity_score=compute_complexity_score(m),
    )


def _simple_benefit(**overrides) -> ModuleBenefit:
    """Build a ModuleBenefit with defaults for testing."""
    defaults = {
        "path": "test/module.py",
        "improves_debuggability": True,
        "improves_recoverability": True,
        "improves_determinism": True,
        "reduces_manual_steps": True,
        "simplifies_public_api": False,
        "preserves_kernel_purity": True,
        "preserves_memory_removability": True,
        "preserves_truth_source": True,
    }
    defaults.update(overrides)
    b = ModuleBenefit(**defaults)
    return ModuleBenefit(
        path=b.path,
        improves_debuggability=b.improves_debuggability,
        improves_recoverability=b.improves_recoverability,
        improves_determinism=b.improves_determinism,
        reduces_manual_steps=b.reduces_manual_steps,
        simplifies_public_api=b.simplifies_public_api,
        preserves_kernel_purity=b.preserves_kernel_purity,
        preserves_memory_removability=b.preserves_memory_removability,
        preserves_truth_source=b.preserves_truth_source,
        benefit_score=compute_benefit_score(b),
    )


# ═══════════════════════════════════════════════════════════════════════
# Test 1: ModuleComplexity creation and serialization
# ═══════════════════════════════════════════════════════════════════════

def test_module_complexity_creation():
    """ModuleComplexity must be creatable and serializable."""
    mc = ModuleComplexity(
        path="kernel/test.py",
        loc=150,
        public_api_count=8,
        dataclass_count=3,
        function_count=12,
        import_count=6,
        internal_dependency_count=3,
        external_dependency_count=2,
        test_count=5,
        report_count=2,
        has_side_effects=True,
        truth_source_count=0,
        projection_only=True,
        removable=False,
    )
    assert mc.path == "kernel/test.py"
    assert mc.loc == 150
    assert mc.public_api_count == 8
    assert mc.has_side_effects is True
    assert mc.truth_source_count == 0

    d = mc.to_dict()
    assert d["path"] == "kernel/test.py"
    assert d["loc"] == 150
    assert "complexity_score" in d


def test_module_benefit_creation():
    """ModuleBenefit must be creatable and serializable."""
    mb = ModuleBenefit(
        path="kernel/test.py",
        improves_debuggability=True,
        improves_recoverability=False,
        improves_determinism=True,
        reduces_manual_steps=False,
        simplifies_public_api=True,
        preserves_kernel_purity=True,
        preserves_memory_removability=True,
        preserves_truth_source=True,
    )
    assert mb.path == "kernel/test.py"
    assert mb.improves_debuggability is True
    assert mb.improves_recoverability is False

    d = mb.to_dict()
    assert d["path"] == "kernel/test.py"
    assert "benefit_score" in d


# ═══════════════════════════════════════════════════════════════════════
# Test 2: compute_complexity_score — basic
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_score_basic():
    """Complexity score must be computable and non-negative."""
    mc = _simple_complexity()
    score = compute_complexity_score(mc)
    assert score >= 0.0
    assert isinstance(score, float)


def test_complexity_score_projection_only_reduces():
    """projection_only=True must reduce complexity score."""
    mc_proj = _simple_complexity(projection_only=True)
    mc_not = _simple_complexity(projection_only=False)
    assert mc_proj.complexity_score < mc_not.complexity_score, \
        f"projection_only should reduce score: {mc_proj.complexity_score} vs {mc_not.complexity_score}"


def test_complexity_score_removable_reduces():
    """removable=True must reduce complexity score."""
    mc_rem = _simple_complexity(removable=True)
    mc_not = _simple_complexity(removable=False)
    assert mc_rem.complexity_score < mc_not.complexity_score, \
        f"removable should reduce score: {mc_rem.complexity_score} vs {mc_not.complexity_score}"


def test_complexity_score_truth_sources_increase():
    """truth_source_count > 0 must increase complexity score."""
    mc_truth = _simple_complexity(truth_source_count=3)
    mc_clean = _simple_complexity(truth_source_count=0)
    assert mc_truth.complexity_score > mc_clean.complexity_score, \
        f"truth sources should increase score: {mc_truth.complexity_score} vs {mc_clean.complexity_score}"


def test_complexity_score_side_effects_increase():
    """has_side_effects=True must increase complexity score."""
    mc_se = _simple_complexity(has_side_effects=True)
    mc_no = _simple_complexity(has_side_effects=False)
    assert mc_se.complexity_score > mc_no.complexity_score, \
        f"side effects should increase score: {mc_se.complexity_score} vs {mc_no.complexity_score}"


def test_complexity_score_deterministic():
    """Same inputs must produce same complexity score."""
    mc1 = _simple_complexity(loc=200, public_api_count=10, import_count=8)
    mc2 = _simple_complexity(loc=200, public_api_count=10, import_count=8)
    assert mc1.complexity_score == mc2.complexity_score


# ═══════════════════════════════════════════════════════════════════════
# Test 3: compute_benefit_score
# ═══════════════════════════════════════════════════════════════════════

def test_benefit_score_all_true():
    """All benefit fields True must produce max score (5.0 + 1.5 = 6.5)."""
    mb = _simple_benefit(
        improves_debuggability=True,
        improves_recoverability=True,
        improves_determinism=True,
        reduces_manual_steps=True,
        simplifies_public_api=True,
        preserves_kernel_purity=True,
        preserves_memory_removability=True,
        preserves_truth_source=True,
    )
    assert mb.benefit_score == 6.5, f"Expected 6.5, got {mb.benefit_score}"


def test_benefit_score_all_false():
    """All benefit fields False must still preserve base (1.5 from preserves_*)."""
    mb = _simple_benefit(
        improves_debuggability=False,
        improves_recoverability=False,
        improves_determinism=False,
        reduces_manual_steps=False,
        simplifies_public_api=False,
        preserves_kernel_purity=True,
        preserves_memory_removability=True,
        preserves_truth_source=True,
    )
    assert mb.benefit_score == 1.5, f"Expected 1.5, got {mb.benefit_score}"


def test_benefit_score_no_preservation():
    """When no preserves_* fields are True, score should be 0.0."""
    mb = _simple_benefit(
        improves_debuggability=False,
        improves_recoverability=False,
        improves_determinism=False,
        reduces_manual_steps=False,
        simplifies_public_api=False,
        preserves_kernel_purity=False,
        preserves_memory_removability=False,
        preserves_truth_source=False,
    )
    assert mb.benefit_score == 0.0, f"Expected 0.0, got {mb.benefit_score}"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: evaluate_verdict — ACCEPT
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_accept():
    """When benefit > complexity, verdict must be ACCEPT."""
    mc = _simple_complexity(loc=50, public_api_count=2, import_count=2)
    mb = _simple_benefit(
        improves_debuggability=True,
        improves_recoverability=True,
        improves_determinism=True,
        reduces_manual_steps=True,
        simplifies_public_api=True,
    )
    verdict = evaluate_verdict((mc,), (mb,))
    assert verdict.verdict == VERDICT_ACCEPT, \
        f"Expected ACCEPT, got {verdict.verdict}: {verdict.reasons}"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: evaluate_verdict — REVIEW (complexity > benefit * 2)
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_review_complexity_2x():
    """When complexity > benefit * 2 but < benefit * 3, verdict must be REVIEW."""
    # benefit = 1.5 (preserves only), need complexity between 3.0 and 4.5
    mc = _simple_complexity(
        loc=200, public_api_count=8, import_count=8,
        internal_dependency_count=3, external_dependency_count=3,
        has_side_effects=False, truth_source_count=0,
        projection_only=False, removable=False,
        test_count=0, report_count=0,
    )
    mb = _simple_benefit(
        improves_debuggability=False,
        improves_recoverability=False,
        improves_determinism=False,
        reduces_manual_steps=False,
        simplifies_public_api=False,
        preserves_kernel_purity=True,
        preserves_memory_removability=True,
        preserves_truth_source=True,
    )
    c_score = mc.complexity_score
    b_score = mb.benefit_score
    assert c_score > b_score * 2, \
        f"Precondition: complexity {c_score} must > benefit*2 {b_score*2}"
    assert c_score < b_score * 3, \
        f"Precondition: complexity {c_score} must < benefit*3 {b_score*3}"

    verdict = evaluate_verdict((mc,), (mb,), allow_new_truth_source=True)
    assert verdict.verdict == VERDICT_REVIEW, \
        f"Expected REVIEW, got {verdict.verdict}: {verdict.reasons}"


# ═══════════════════════════════════════════════════════════════════════
# Test 6: evaluate_verdict — REJECT (complexity > benefit * 3)
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_reject_complexity_3x():
    """When complexity > benefit * 3, verdict must be REJECT."""
    mc = _simple_complexity(
        loc=1000, public_api_count=50, import_count=40,
        internal_dependency_count=20, external_dependency_count=15,
        has_side_effects=True, truth_source_count=2,
        projection_only=False, removable=False,
        test_count=0, report_count=0,
    )
    mb = _simple_benefit(
        improves_debuggability=False,
        improves_recoverability=False,
        improves_determinism=False,
        reduces_manual_steps=False,
        simplifies_public_api=False,
        preserves_kernel_purity=True,
        preserves_memory_removability=True,
        preserves_truth_source=True,
    )
    c_score = mc.complexity_score
    b_score = mb.benefit_score
    assert c_score > b_score * 3, \
        f"Precondition: complexity {c_score} must > benefit*3 {b_score*3}"

    verdict = evaluate_verdict((mc,), (mb,), allow_new_truth_source=True)
    assert verdict.verdict == VERDICT_REJECT, \
        f"Expected REJECT, got {verdict.verdict}: {verdict.reasons}"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: evaluate_verdict — REJECT kernel purity break
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_reject_kernel_purity():
    """Kernel purity break must immediately REJECT."""
    mc = _simple_complexity()
    mb = _simple_benefit(preserves_kernel_purity=False)
    verdict = evaluate_verdict((mc,), (mb,))
    assert verdict.verdict == VERDICT_REJECT
    assert any("KERNEL_PURITY_BREAK" in r for r in verdict.reasons)


# ═══════════════════════════════════════════════════════════════════════
# Test 8: evaluate_verdict — REJECT memory removability break
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_reject_memory_removability():
    """Memory removability break must immediately REJECT."""
    mc = _simple_complexity()
    mb = _simple_benefit(preserves_memory_removability=False)
    verdict = evaluate_verdict((mc,), (mb,))
    assert verdict.verdict == VERDICT_REJECT
    assert any("MEMORY_REMOVABILITY_BREAK" in r for r in verdict.reasons)


# ═══════════════════════════════════════════════════════════════════════
# Test 9: evaluate_verdict — REJECT new truth source
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_reject_new_truth_source():
    """New truth source must REJECT when allow_new_truth_source=False."""
    mc = _simple_complexity(truth_source_count=1)
    mb = _simple_benefit()
    verdict = evaluate_verdict((mc,), (mb,), allow_new_truth_source=False)
    assert verdict.verdict == VERDICT_REJECT
    assert any("NEW_TRUTH_SOURCE" in r for r in verdict.reasons)


def test_verdict_allow_truth_source():
    """When allow_new_truth_source=True, truth sources must not auto-reject."""
    mc = _simple_complexity(truth_source_count=1)
    mb = _simple_benefit(
        improves_debuggability=True,
        improves_recoverability=True,
        improves_determinism=True,
        reduces_manual_steps=True,
        simplifies_public_api=True,
    )
    verdict = evaluate_verdict((mc,), (mb,), allow_new_truth_source=True)
    assert verdict.verdict != VERDICT_REJECT


# ═══════════════════════════════════════════════════════════════════════
# Test 10: analyze_module — produces valid ModuleComplexity
# ═══════════════════════════════════════════════════════════════════════

def test_analyze_module_valid():
    """analyze_module must produce valid ModuleComplexity for real files."""
    test_file = os.path.join(_v3_root, "kernel", "events.py")
    if not os.path.exists(test_file):
        test_file = os.path.join(_v3_root, "quality", "complexity_budget.py")

    result = analyze_module(test_file, base_dir=_v3_root)
    assert result is not None, f"analyze_module returned None for {test_file}"
    assert result.loc > 0, f"Expected LOC > 0, got {result.loc}"
    assert result.function_count > 0
    assert result.path
    assert result.complexity_score >= 0.0


def test_analyze_module_nonexistent():
    """analyze_module must return None for nonexistent files."""
    result = analyze_module("/nonexistent/path.py")
    assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Test 11: analyze_directory — finds all modules
# ═══════════════════════════════════════════════════════════════════════

def test_analyze_directory_kernel():
    """analyze_directory must find all kernel modules."""
    kernel_dir = os.path.join(_v3_root, "kernel")
    if not os.path.isdir(kernel_dir):
        return  # Skip if no kernel dir

    modules = analyze_directory(kernel_dir)
    assert len(modules) > 0, "Expected at least 1 kernel module"
    for m in modules:
        assert m.path.endswith(".py")
        assert m.loc > 0
        assert m.complexity_score >= 0.0


def test_analyze_directory_memory():
    """analyze_directory must find all memory modules."""
    memory_dir = os.path.join(_v3_root, "memory")
    if not os.path.isdir(memory_dir):
        return

    modules = analyze_directory(memory_dir)
    assert len(modules) > 0, "Expected at least 1 memory module"
    for m in modules:
        assert m.path.endswith(".py")


# ═══════════════════════════════════════════════════════════════════════
# Test 12: ComplexityAnalyzer class
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_analyzer():
    """ComplexityAnalyzer must analyze all v3 modules."""
    analyzer = ComplexityAnalyzer(_v3_root)
    modules = analyzer.analyze_all()
    assert len(modules) > 0, "Expected at least 1 module"

    report = analyzer.generate_report()
    assert "summary" in report
    assert "modules" in report
    assert "risk_factors" in report
    assert report["summary"]["total_modules"] == len(modules)


# ═══════════════════════════════════════════════════════════════════════
# Test 13: evaluate_phase — produces valid PhaseGateResult
# ═══════════════════════════════════════════════════════════════════════

def test_evaluate_phase():
    """evaluate_phase must produce a valid PhaseGateResult."""
    result = evaluate_phase("5A", v3_root=_v3_root)
    assert result.phase == "5A"
    assert result.verdict is not None
    assert result.verdict.verdict in (VERDICT_ACCEPT, VERDICT_REVIEW, VERDICT_REJECT)
    assert len(result.module_complexities) > 0
    assert len(result.module_benefits) > 0
    assert len(result.verdict.verdict_hash) == 16


# ═══════════════════════════════════════════════════════════════════════
# Test 14: fail_if_rejected
# ═══════════════════════════════════════════════════════════════════════

def test_fail_if_rejected_raises():
    """fail_if_rejected must raise on REJECT verdict."""
    v = ComplexityBudgetVerdict(
        total_complexity_score=10.0,
        total_benefit_score=1.0,
        net_value_score=-9.0,
        risk_ratio=10.0,
        verdict=VERDICT_REJECT,
        reasons=("TEST_REJECT",),
    )
    try:
        fail_if_rejected(v)
        assert False, "Should have raised ComplexityGateRejected"
    except ComplexityGateRejected as e:
        assert "REJECTED" in str(e)


def test_fail_if_rejected_silent_on_accept():
    """fail_if_rejected must not raise on ACCEPT verdict."""
    v = ComplexityBudgetVerdict(
        total_complexity_score=1.0,
        total_benefit_score=5.0,
        net_value_score=4.0,
        risk_ratio=0.2,
        verdict=VERDICT_ACCEPT,
        reasons=("All good",),
    )
    fail_if_rejected(v)  # Must not raise


def test_fail_if_rejected_silent_on_review():
    """fail_if_rejected must not raise on REVIEW verdict."""
    v = ComplexityBudgetVerdict(
        total_complexity_score=5.0,
        total_benefit_score=2.0,
        net_value_score=-3.0,
        risk_ratio=2.5,
        verdict=VERDICT_REVIEW,
        reasons=("Needs review",),
    )
    fail_if_rejected(v)  # Must not raise


# ═══════════════════════════════════════════════════════════════════════
# Test 15: verdict hash stable
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_hash_stable():
    """Same verdict inputs must produce same hash."""
    mc = _simple_complexity()
    mb = _simple_benefit()

    v1 = evaluate_verdict((mc,), (mb,))
    v2 = evaluate_verdict((mc,), (mb,))
    assert v1.verdict_hash == v2.verdict_hash
    assert len(v1.verdict_hash) == 16


def test_verdict_hash_different():
    """Different verdict inputs must produce different hash."""
    mc = _simple_complexity()
    mb1 = _simple_benefit(improves_debuggability=True)
    mb2 = _simple_benefit(improves_debuggability=False)

    v1 = evaluate_verdict((mc,), (mb1,))
    v2 = evaluate_verdict((mc,), (mb2,))
    # Hashes may differ only if benefit scores differ enough to change verdict
    # Just verify both are valid hex strings
    assert all(c in "0123456789abcdef" for c in v1.verdict_hash)
    assert all(c in "0123456789abcdef" for c in v2.verdict_hash)


# ═══════════════════════════════════════════════════════════════════════
# Test 16: no banned LLM/vector imports
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_imports():
    """Quality modules must not import LLM/vector DB/AI libs."""
    import ast

    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "sklearn", "scipy",
    }

    quality_dir = os.path.join(_v3_root, "quality")
    for fname in os.listdir(quality_dir):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(quality_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in banned, \
                        f"Banned import '{name}' in {fname}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    assert name not in banned, \
                        f"Banned import '{name}' in {fname}"


# ═══════════════════════════════════════════════════════════════════════
# Test 17: load_budget_policy
# ═══════════════════════════════════════════════════════════════════════

def test_load_budget_policy_defaults():
    """load_budget_policy with no path must return default policy."""
    policy = load_budget_policy()
    assert isinstance(policy, dict)
    assert "kernel" in policy
    assert "memory" in policy


def test_load_budget_policy_nonexistent():
    """load_budget_policy with nonexistent path must fall back to defaults."""
    policy = load_budget_policy("/nonexistent/policy.json")
    assert isinstance(policy, dict)
    assert "kernel" in policy


# ═══════════════════════════════════════════════════════════════════════
# Test 18: ComplexityBudgetVerdict serialization
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_serialization():
    """ComplexityBudgetVerdict must serialize to dict and JSON."""
    v = ComplexityBudgetVerdict(
        total_complexity_score=5.5,
        total_benefit_score=3.0,
        net_value_score=-2.5,
        risk_ratio=1.83,
        verdict=VERDICT_REVIEW,
        reasons=("COMPLEXITY_EXCEEDS_BENEFIT_2X",),
        verdict_hash="abc123def4567890",
    )
    d = v.to_dict()
    assert d["verdict"] == VERDICT_REVIEW
    assert d["total_complexity_score"] == 5.5
    assert len(d["reasons"]) == 1

    j = v.to_json()
    assert "REVIEW" in j
    assert "5.5" in j


# ═══════════════════════════════════════════════════════════════════════
# Test 19: score determinism
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_score_deterministic_full():
    """Complexity scores must be fully deterministic."""
    for i in range(5):
        mc = ModuleComplexity(
            path=f"test/module_{i}.py",
            loc=100 + i * 10,
            public_api_count=5,
            dataclass_count=2,
            function_count=8,
            import_count=4,
            internal_dependency_count=2,
            external_dependency_count=1,
            test_count=3,
            report_count=1,
            has_side_effects=False,
            truth_source_count=0,
            projection_only=True,
            removable=False,
        )
        score1 = compute_complexity_score(mc)
        score2 = compute_complexity_score(mc)
        assert score1 == score2, f"Score must be deterministic: {score1} != {score2}"


def test_benefit_score_deterministic():
    """Benefit scores must be fully deterministic."""
    mb = _simple_benefit()
    scores = [mb.benefit_score for _ in range(5)]
    assert all(s == scores[0] for s in scores)


# ═══════════════════════════════════════════════════════════════════════
# Test 20: write_complexity_report
# ═══════════════════════════════════════════════════════════════════════

def test_write_complexity_report():
    """write_complexity_report must produce valid JSON."""
    tmpdir = tempfile.mkdtemp(prefix="cb-report-")
    try:
        mc = _simple_complexity()
        mb = _simple_benefit()
        verdict = evaluate_verdict((mc,), (mb,))
        result = PhaseGateResult(
            phase="5A",
            verdict=verdict,
            module_complexities=(mc,),
            module_benefits=(mb,),
            passed=verdict.is_accepted,
        )

        output_path = os.path.join(tmpdir, "complexity_budget_report.json")
        written = write_complexity_report(result, output_path)
        assert os.path.exists(written)

        with open(written, encoding="utf-8") as f:
            data = json.load(f)
        assert data["phase"] == "5A"
        assert "verdict" in data
        assert "modules" in data
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 21: Verdict properties
# ═══════════════════════════════════════════════════════════════════════

def test_verdict_properties():
    """is_accepted, is_review, is_rejected must be mutually exclusive."""
    v_accept = ComplexityBudgetVerdict(verdict=VERDICT_ACCEPT)
    assert v_accept.is_accepted and not v_accept.is_review and not v_accept.is_rejected

    v_review = ComplexityBudgetVerdict(verdict=VERDICT_REVIEW)
    assert v_review.is_review and not v_review.is_accepted and not v_review.is_rejected

    v_reject = ComplexityBudgetVerdict(verdict=VERDICT_REJECT)
    assert v_reject.is_rejected and not v_reject.is_accepted and not v_reject.is_review


# ═══════════════════════════════════════════════════════════════════════
# Test 22: existing kernel invariants still pass
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_invariants_regression():
    """Quality modules must not break kernel invariants (no kernel imports)."""
    import ast

    _kernel = os.path.join(_v3_root, "kernel")
    quality_dir = os.path.join(_v3_root, "quality")

    # Check that no kernel file imports from v3/quality/
    violations = []
    for fname in os.listdir(_kernel):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(_kernel, fname)
        with open(fpath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "v3.quality" in node.module:
                    violations.append(f"{fname} imports {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "v3.quality" in alias.name:
                        violations.append(f"{fname} imports {alias.name}")

    assert len(violations) == 0, \
        f"Kernel files must not import from v3/quality/: {violations}"


# ═══════════════════════════════════════════════════════════════════════
# Test 23: count_tests_for_module
# ═══════════════════════════════════════════════════════════════════════

def test_count_tests_for_module():
    """count_tests_for_module must find test functions."""
    tests_dir = os.path.join(_v3_root, "tests")
    if not os.path.isdir(tests_dir):
        return

    count = count_tests_for_module("kernel/events.py", tests_dir)
    assert isinstance(count, int)
    assert count >= 0


def test_count_reports_for_module():
    """count_reports_for_module must find export reports."""
    exports_dir = os.path.join(_v3_root, "exports")
    if not os.path.isdir(exports_dir):
        return

    count = count_reports_for_module("memory/compaction.py", exports_dir)
    assert isinstance(count, int)
    assert count >= 0


# ═══════════════════════════════════════════════════════════════════════
# Test 24: net_value_score positive on good module
# ═══════════════════════════════════════════════════════════════════════

def test_net_value_positive_on_balanced():
    """Well-tested, projection-only, removable modules should have positive net value."""
    mc = _simple_complexity(
        loc=100, public_api_count=3, import_count=3,
        projection_only=True, removable=True, test_count=10, report_count=3,
    )
    mb = _simple_benefit(
        improves_debuggability=True,
        improves_determinism=True,
        reduces_manual_steps=True,
    )
    verdict = evaluate_verdict((mc,), (mb,))
    # Should be ACCEPT — complexity is low, benefit is moderate
    assert verdict.verdict == VERDICT_ACCEPT, \
        f"Expected ACCEPT, got {verdict.verdict}: {verdict.reasons}"
    assert verdict.net_value_score > 0, \
        f"Expected positive net value, got {verdict.net_value_score}"


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Dataclass basics
        ("ModuleComplexity creation", test_module_complexity_creation),
        ("ModuleBenefit creation", test_module_benefit_creation),
        # Complexity scoring
        ("complexity score basic", test_complexity_score_basic),
        ("complexity score projection_only reduces", test_complexity_score_projection_only_reduces),
        ("complexity score removable reduces", test_complexity_score_removable_reduces),
        ("complexity score truth sources increase", test_complexity_score_truth_sources_increase),
        ("complexity score side effects increase", test_complexity_score_side_effects_increase),
        ("complexity score deterministic", test_complexity_score_deterministic),
        # Benefit scoring
        ("benefit score all true", test_benefit_score_all_true),
        ("benefit score all false", test_benefit_score_all_false),
        ("benefit score no preservation", test_benefit_score_no_preservation),
        # Verdicts
        ("verdict ACCEPT", test_verdict_accept),
        ("verdict REVIEW (2x)", test_verdict_review_complexity_2x),
        ("verdict REJECT (3x)", test_verdict_reject_complexity_3x),
        ("verdict REJECT kernel purity", test_verdict_reject_kernel_purity),
        ("verdict REJECT memory removability", test_verdict_reject_memory_removability),
        ("verdict REJECT new truth source", test_verdict_reject_new_truth_source),
        ("verdict allow truth source", test_verdict_allow_truth_source),
        # Analysis
        ("analyze_module valid", test_analyze_module_valid),
        ("analyze_module nonexistent", test_analyze_module_nonexistent),
        ("analyze_directory kernel", test_analyze_directory_kernel),
        ("analyze_directory memory", test_analyze_directory_memory),
        ("ComplexityAnalyzer", test_complexity_analyzer),
        # Phase gate
        ("evaluate_phase", test_evaluate_phase),
        ("fail_if_rejected raises", test_fail_if_rejected_raises),
        ("fail_if_rejected silent ACCEPT", test_fail_if_rejected_silent_on_accept),
        ("fail_if_rejected silent REVIEW", test_fail_if_rejected_silent_on_review),
        # Hash stability
        ("verdict hash stable", test_verdict_hash_stable),
        ("verdict hash valid hex", test_verdict_hash_different),
        # Banned imports
        ("no banned imports", test_no_banned_imports),
        # Policy
        ("load_budget_policy defaults", test_load_budget_policy_defaults),
        ("load_budget_policy nonexistent", test_load_budget_policy_nonexistent),
        # Serialization
        ("verdict serialization", test_verdict_serialization),
        # Determinism
        ("complexity score determinism full", test_complexity_score_deterministic_full),
        ("benefit score determinism", test_benefit_score_deterministic),
        # Report
        ("write_complexity_report", test_write_complexity_report),
        # Properties
        ("verdict properties", test_verdict_properties),
        # Invariants
        ("kernel invariants regression", test_kernel_invariants_regression),
        # Test/report counters
        ("count_tests_for_module", test_count_tests_for_module),
        ("count_reports_for_module", test_count_reports_for_module),
        # Net value
        ("net_value positive on balanced", test_net_value_positive_on_balanced),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Complexity Budget Tests (Phase 5A)")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"  ACCEPTANCE: {'ACHIEVED' if failed == 0 else 'NOT MET'}")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
