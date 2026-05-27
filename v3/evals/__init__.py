"""
Evaluation & Regression Harness — Phase 10.

Deterministic, local-only evaluation framework measuring whether
the v4 Pluggable Intelligence Plane provides real engineering value.

Three sub-modules:
- evaluation_harness: EvalCase, EvalResult, EvalSuite, EvalSuiteResult
- benefit_complexity: BenefitSignal, BenefitComplexityScore
- regression_matrix: RegressionCheck, RegressionMatrix, RegressionMatrixResult

Core principle:
Future capabilities must prove value before integration.
Evaluation is the guardrail against "ability +10%, complexity +300%".
"""

# ── Evaluation Harness ──────────────────────────────────────────────────
from v3.evals.evaluation_harness import (
    CATEGORY_CONTEXT,
    CATEGORY_MEMORY,
    CATEGORY_AGENT,
    CATEGORY_WORKSPACE,
    CATEGORY_SKILL,
    CATEGORY_ORCHESTRATION,
    CATEGORY_REGISTRY,
    CATEGORY_EVIDENCE,
    ALL_CATEGORIES,
    EvalCase,
    EvalResult,
    EvalSuite,
    EvalSuiteResult,
    build_default_eval_suite,
    run_eval_case,
    run_eval_suite,
    validate_eval_result,
    write_eval_result,
)

# ── Benefit-Complexity Scoring ─────────────────────────────────────────
from v3.evals.benefit_complexity import (
    VERDICT_ACCEPT as BC_VERDICT_ACCEPT,
    VERDICT_REVIEW as BC_VERDICT_REVIEW,
    VERDICT_REJECT as BC_VERDICT_REJECT,
    ALL_VERDICTS as BC_ALL_VERDICTS,
    BenefitSignal,
    BenefitComplexityScore,
    score_benefit_complexity,
    compare_against_thresholds,
    write_benefit_complexity_report,
)

# ── Regression Matrix ──────────────────────────────────────────────────
from v3.evals.regression_matrix import (
    CHECK_PASS,
    CHECK_FAIL,
    CHECK_SKIP,
    ALL_CHECK_STATUSES,
    RegressionCheck,
    RegressionMatrix,
    RegressionMatrixResult,
    build_v4_regression_matrix,
    run_static_regression_matrix,
    write_regression_matrix_result,
)

__all__ = [
    # Categories
    "CATEGORY_CONTEXT",
    "CATEGORY_MEMORY",
    "CATEGORY_AGENT",
    "CATEGORY_WORKSPACE",
    "CATEGORY_SKILL",
    "CATEGORY_ORCHESTRATION",
    "CATEGORY_REGISTRY",
    "CATEGORY_EVIDENCE",
    "ALL_CATEGORIES",
    # Eval harness
    "EvalCase",
    "EvalResult",
    "EvalSuite",
    "EvalSuiteResult",
    "build_default_eval_suite",
    "run_eval_case",
    "run_eval_suite",
    "validate_eval_result",
    "write_eval_result",
    # Benefit-complexity
    "BC_VERDICT_ACCEPT",
    "BC_VERDICT_REVIEW",
    "BC_VERDICT_REJECT",
    "BC_ALL_VERDICTS",
    "BenefitSignal",
    "BenefitComplexityScore",
    "score_benefit_complexity",
    "compare_against_thresholds",
    "write_benefit_complexity_report",
    # Regression matrix
    "CHECK_PASS",
    "CHECK_FAIL",
    "CHECK_SKIP",
    "ALL_CHECK_STATUSES",
    "RegressionCheck",
    "RegressionMatrix",
    "RegressionMatrixResult",
    "build_v4_regression_matrix",
    "run_static_regression_matrix",
    "write_regression_matrix_result",
]
