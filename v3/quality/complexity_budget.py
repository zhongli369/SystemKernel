"""
Complexity Budget — Deterministic value-based gating for Phase 5A.

Measures complexity vs benefit for each module and produces an
ACCEPT/REVIEW/REJECT verdict. The gate blocks phases whose complexity
exceeds their proportional benefit.

Rules (machine-enforceable):
  1. If complexity_score > benefit_score * 2 → REVIEW
  2. If complexity_score > benefit_score * 3 → REJECT
  3. If new truth source appears → REJECT
  4. If kernel purity breaks → REJECT
  5. If memory removability breaks → REJECT

Zero LLM. Zero runtime impact. Pure analysis.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Tuple, Optional

# ═══════════════════════════════════════════════════════════════════════
# Verdict constants
# ═══════════════════════════════════════════════════════════════════════

VERDICT_ACCEPT = "ACCEPT"
VERDICT_REVIEW = "REVIEW"
VERDICT_REJECT = "REJECT"


# ═══════════════════════════════════════════════════════════════════════
# ModuleComplexity
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ModuleComplexity:
    """Measured complexity of a single module.

    Fields:
        path: Relative module path (e.g. "kernel/execution_engine.py")
        loc: Non-blank non-comment lines of code
        public_api_count: Number of public functions + dunder methods
        dataclass_count: Number of @dataclass-decorated classes
        function_count: Total function definitions (including private)
        import_count: Total import statements
        internal_dependency_count: Cross-references within same directory
        external_dependency_count: Cross-references outside module directory
        test_count: Matching test functions in tests/
        report_count: Matching export reports in exports/
        has_side_effects: Module performs I/O or modifies global state
        truth_source_count: Number of truth-source claims (new data origins)
        projection_only: True if all outputs derive from upstream sources
        removable: True if deleting the module has zero kernel impact
        complexity_score: Weighted complexity score (0.0 = minimal)
    """

    path: str = ""
    loc: int = 0
    public_api_count: int = 0
    dataclass_count: int = 0
    function_count: int = 0
    import_count: int = 0
    internal_dependency_count: int = 0
    external_dependency_count: int = 0
    test_count: int = 0
    report_count: int = 0
    has_side_effects: bool = False
    truth_source_count: int = 0
    projection_only: bool = True
    removable: bool = False
    complexity_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "loc": self.loc,
            "public_api_count": self.public_api_count,
            "dataclass_count": self.dataclass_count,
            "function_count": self.function_count,
            "import_count": self.import_count,
            "internal_dependency_count": self.internal_dependency_count,
            "external_dependency_count": self.external_dependency_count,
            "test_count": self.test_count,
            "report_count": self.report_count,
            "has_side_effects": self.has_side_effects,
            "truth_source_count": self.truth_source_count,
            "projection_only": self.projection_only,
            "removable": self.removable,
            "complexity_score": round(self.complexity_score, 2),
        }


# ═══════════════════════════════════════════════════════════════════════
# ModuleBenefit
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ModuleBenefit:
    """Estimated benefit of a module.

    Each boolean field contributes 1.0 to the raw benefit score.
    Max raw score = 8.0 (all fields True).

    Fields:
        path: Relative module path
        improves_debuggability: Makes it easier to diagnose issues
        improves_recoverability: Enables recovery from failures
        improves_determinism: Strengthens deterministic guarantees
        reduces_manual_steps: Automates previously manual work
        simplifies_public_api: Reduces the public API surface
        preserves_kernel_purity: Does not break kernel invariants
        preserves_memory_removability: Memory remains removable
        preserves_truth_source: Events remain sole source of truth
        benefit_score: Sum of all true boolean fields (0.0 - 8.0)
    """

    path: str = ""
    improves_debuggability: bool = False
    improves_recoverability: bool = False
    improves_determinism: bool = False
    reduces_manual_steps: bool = False
    simplifies_public_api: bool = False
    preserves_kernel_purity: bool = True
    preserves_memory_removability: bool = True
    preserves_truth_source: bool = True
    benefit_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "improves_debuggability": self.improves_debuggability,
            "improves_recoverability": self.improves_recoverability,
            "improves_determinism": self.improves_determinism,
            "reduces_manual_steps": self.reduces_manual_steps,
            "simplifies_public_api": self.simplifies_public_api,
            "preserves_kernel_purity": self.preserves_kernel_purity,
            "preserves_memory_removability": self.preserves_memory_removability,
            "preserves_truth_source": self.preserves_truth_source,
            "benefit_score": round(self.benefit_score, 2),
        }


# ═══════════════════════════════════════════════════════════════════════
# ComplexityBudgetVerdict
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ComplexityBudgetVerdict:
    """Final gate verdict after evaluating complexity vs benefit.

    Fields:
        total_complexity_score: Sum of all module complexity scores
        total_benefit_score: Sum of all module benefit scores
        net_value_score: benefit - complexity (negative = net cost)
        risk_ratio: complexity / max(benefit, 0.01) — higher = riskier
        verdict: ACCEPT | REVIEW | REJECT
        reasons: Human-readable explanations for the verdict
        verdict_hash: Deterministic hash of this verdict
    """

    total_complexity_score: float = 0.0
    total_benefit_score: float = 0.0
    net_value_score: float = 0.0
    risk_ratio: float = 0.0
    verdict: str = VERDICT_ACCEPT
    reasons: Tuple[str, ...] = ()
    verdict_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "total_complexity_score": round(self.total_complexity_score, 2),
            "total_benefit_score": round(self.total_benefit_score, 2),
            "net_value_score": round(self.net_value_score, 2),
            "risk_ratio": round(self.risk_ratio, 2),
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "verdict_hash": self.verdict_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @property
    def is_accepted(self) -> bool:
        return self.verdict == VERDICT_ACCEPT

    @property
    def is_review(self) -> bool:
        return self.verdict == VERDICT_REVIEW

    @property
    def is_rejected(self) -> bool:
        return self.verdict == VERDICT_REJECT


# ═══════════════════════════════════════════════════════════════════════
# Scoring functions
# ═══════════════════════════════════════════════════════════════════════

def compute_complexity_score(module: ModuleComplexity) -> float:
    """Compute weighted complexity score from module metrics.

    Weights are tuned to penalize:
      - High LOC (maintenance burden)
      - Large public API (coupling surface)
      - Many dependencies (integration risk)
      - Side effects (non-determinism risk)
      - Truth source claims (architectural risk)
    """
    score = 0.0
    score += (module.loc / 100.0) * 0.25
    score += module.public_api_count * 0.15
    score += module.import_count * 0.10
    score += module.internal_dependency_count * 0.15
    score += module.external_dependency_count * 0.20
    score += (1.0 if module.has_side_effects else 0.0) * 0.50
    score += module.truth_source_count * 0.80
    # Negative modifiers (reduce complexity)
    if module.projection_only:
        score -= 0.30
    if module.removable:
        score -= 0.40
    if module.test_count > 0:
        score -= min(module.test_count * 0.05, 0.30)
    if module.report_count > 0:
        score -= min(module.report_count * 0.03, 0.15)
    return max(0.0, round(score, 2))


def compute_benefit_score(module: ModuleBenefit) -> float:
    """Compute benefit score from boolean benefit fields.

    Each True field = 1.0. Negative-modifier fields (preserves_*) = 0.5 each
    since they maintain status quo rather than adding new value.
    """
    score = 0.0
    if module.improves_debuggability:
        score += 1.0
    if module.improves_recoverability:
        score += 1.0
    if module.improves_determinism:
        score += 1.0
    if module.reduces_manual_steps:
        score += 1.0
    if module.simplifies_public_api:
        score += 1.0
    # Preservation benefits (maintaining invariants is good but not additive)
    if module.preserves_kernel_purity:
        score += 0.5
    if module.preserves_memory_removability:
        score += 0.5
    if module.preserves_truth_source:
        score += 0.5
    return round(score, 2)


def evaluate_verdict(
    complexities: Tuple[ModuleComplexity, ...],
    benefits: Tuple[ModuleBenefit, ...],
    *,
    allow_new_truth_source: bool = False,
) -> ComplexityBudgetVerdict:
    """Evaluate the complexity budget gate verdict.

    Args:
        complexities: ModuleComplexity objects for all modules in scope
        benefits: ModuleBenefit objects for all modules in scope
        allow_new_truth_source: If False, any truth_source_count > 0 → REJECT

    Returns:
        ComplexityBudgetVerdict with ACCEPT/REVIEW/REJECT.
    """
    total_complexity = sum(c.complexity_score for c in complexities)
    total_benefit = sum(b.benefit_score for b in benefits)
    net_value = round(total_benefit - total_complexity, 2)
    risk_ratio = round(total_complexity / max(total_benefit, 0.01), 2)

    reasons = []

    # Rule 4: Kernel purity break → REJECT
    for b in benefits:
        if not b.preserves_kernel_purity:
            return ComplexityBudgetVerdict(
                total_complexity_score=total_complexity,
                total_benefit_score=total_benefit,
                net_value_score=net_value,
                risk_ratio=risk_ratio,
                verdict=VERDICT_REJECT,
                reasons=("KERNEL_PURITY_BREAK: module would violate kernel invariants",),
                verdict_hash="",
            )

    # Rule 5: Memory removability break → REJECT
    for b in benefits:
        if not b.preserves_memory_removability:
            return ComplexityBudgetVerdict(
                total_complexity_score=total_complexity,
                total_benefit_score=total_benefit,
                net_value_score=net_value,
                risk_ratio=risk_ratio,
                verdict=VERDICT_REJECT,
                reasons=("MEMORY_REMOVABILITY_BREAK: memory would no longer be removable",),
                verdict_hash="",
            )

    # Rule 3: New truth source → REJECT
    if not allow_new_truth_source:
        for c in complexities:
            if c.truth_source_count > 0:
                return ComplexityBudgetVerdict(
                    total_complexity_score=total_complexity,
                    total_benefit_score=total_benefit,
                    net_value_score=net_value,
                    risk_ratio=risk_ratio,
                    verdict=VERDICT_REJECT,
                    reasons=(f"NEW_TRUTH_SOURCE: {c.path} claims {c.truth_source_count} new truth source(s)",),
                    verdict_hash="",
                )

    # Rule 2: complexity > benefit * 3 → REJECT
    if total_complexity > total_benefit * 3:
        reasons.append(
            f"COMPLEXITY_EXCEEDS_BENEFIT_3X: complexity={total_complexity:.1f} > benefit*3={total_benefit*3:.1f}"
        )

    # Rule 1: complexity > benefit * 2 → REVIEW
    if total_complexity > total_benefit * 2:
        reasons.append(
            f"COMPLEXITY_EXCEEDS_BENEFIT_2X: complexity={total_complexity:.1f} > benefit*2={total_benefit*2:.1f}"
        )

    # Determine verdict
    if any(r.startswith("COMPLEXITY_EXCEEDS_BENEFIT_3X") for r in reasons):
        verdict = VERDICT_REJECT
    elif any(r.startswith("COMPLEXITY_EXCEEDS_BENEFIT_2X") for r in reasons):
        verdict = VERDICT_REVIEW
    elif net_value < 0:
        verdict = VERDICT_REVIEW
        reasons.append(f"NET_VALUE_NEGATIVE: net_value={net_value:.1f}")
    else:
        verdict = VERDICT_ACCEPT

    if not reasons:
        reasons.append(f"All gates passed: complexity={total_complexity:.1f}, benefit={total_benefit:.1f}, net={net_value:.1f}")

    # Deterministic hash
    hash_parts = [
        str(round(total_complexity, 2)),
        str(round(total_benefit, 2)),
        str(round(net_value, 2)),
        str(round(risk_ratio, 2)),
        verdict,
        "|".join(sorted(reasons)),
    ]
    vhash = hashlib.sha256("|".join(hash_parts).encode("utf-8")).hexdigest()[:16]

    return ComplexityBudgetVerdict(
        total_complexity_score=round(total_complexity, 2),
        total_benefit_score=round(total_benefit, 2),
        net_value_score=net_value,
        risk_ratio=risk_ratio,
        verdict=verdict,
        reasons=tuple(reasons),
        verdict_hash=vhash,
    )
