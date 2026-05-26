"""
SystemKernel v3.0 — Quality Gate Subsystem.

Phase 5A: Complexity Budget Gate.
Ensures every phase delivers positive net value. Blocks phases that add
complexity without proportional benefit.

Zero LLM. Zero runtime impact. Deterministic analysis only.
"""

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
    PhaseGateResult,
)

__all__ = [
    "ModuleComplexity",
    "ModuleBenefit",
    "ComplexityBudgetVerdict",
    "compute_complexity_score",
    "compute_benefit_score",
    "evaluate_verdict",
    "VERDICT_ACCEPT",
    "VERDICT_REVIEW",
    "VERDICT_REJECT",
    "ComplexityAnalyzer",
    "analyze_module",
    "analyze_directory",
    "count_tests_for_module",
    "count_reports_for_module",
    "evaluate_phase",
    "load_budget_policy",
    "write_complexity_report",
    "fail_if_rejected",
    "PhaseGateResult",
]
