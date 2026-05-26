"""
Phase Gate — Deterministic gating for Phase 5A.

Provides evaluate_phase() which runs the full complexity budget analysis
and returns an ACCEPT/REVIEW/REJECT verdict. Blocks phases that fail
the complexity budget gate.

Usage:
    gate_result = evaluate_phase(v3_root="/path/to/v3")
    if gate_result.verdict.is_rejected:
        fail_if_rejected(gate_result.verdict)  # raises ComplexityGateRejected

Zero LLM. Zero runtime impact. Pure analysis.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

from v3.quality.complexity_budget import (
    ModuleComplexity, ModuleBenefit, ComplexityBudgetVerdict,
    compute_benefit_score, evaluate_verdict, compute_complexity_score,
    VERDICT_ACCEPT, VERDICT_REVIEW, VERDICT_REJECT,
)


# ═══════════════════════════════════════════════════════════════════════
# PhaseGateResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PhaseGateResult:
    """Complete result of a phase gate evaluation.

    Fields:
        phase: Phase identifier (e.g. "5A")
        verdict: The complexity budget verdict
        module_complexities: All analyzed module complexities
        module_benefits: All module benefit assessments
        report_path: Path to the written complexity report
        passed: True if verdict is ACCEPT
    """

    phase: str = ""
    verdict: ComplexityBudgetVerdict = field(default_factory=lambda: ComplexityBudgetVerdict())
    module_complexities: Tuple[ModuleComplexity, ...] = ()
    module_benefits: Tuple[ModuleBenefit, ...] = ()
    report_path: str = ""
    passed: bool = False


# ═══════════════════════════════════════════════════════════════════════
# Default budget policy
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_BENEFIT_POLICY: dict = {
    "kernel": {
        "execution_engine.py": {
            "improves_debuggability": False,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": False,
        },
        "events.py": {
            "improves_debuggability": False,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": False,
        },
        "event_store.py": {
            "improves_debuggability": False,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": True,
        },
        "checkpoint.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": True,
        },
        "replay.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": False,
        },
        "time_travel.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": False,
        },
        "observability.py": {
            "improves_debuggability": True,
            "improves_recoverability": False,
            "improves_determinism": False,
            "reduces_manual_steps": True,
            "simplifies_public_api": False,
        },
        "observability_graph.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": False,
        },
        "execution_state.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": False,
        },
        "telemetry.py": {
            "improves_debuggability": True,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": False,
        },
        "metrics.py": {
            "improves_debuggability": True,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": False,
        },
        "memory_contract.py": {
            "improves_debuggability": False,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": True,
        },
        "memory_candidate.py": {
            "improves_debuggability": False,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": True,
        },
        "memory_gateway.py": {
            "improves_debuggability": False,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": True,
        },
    },
    "memory": {
        "episodic_store.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": True,
        },
        "semantic_index.py": {
            "improves_debuggability": True,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": True,
        },
        "recall.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": False,
        },
        "retrieval.py": {
            "improves_debuggability": True,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": True,
        },
        "compaction.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": False,
        },
        "compaction_integrity.py": {
            "improves_debuggability": True,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": True,
        },
        "runtime.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": True,
        },
        "system_report.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": True,
        },
        "provenance.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": False,
            "simplifies_public_api": True,
        },
        "integrity.py": {
            "improves_debuggability": True,
            "improves_recoverability": True,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": True,
        },
        "index_integrity.py": {
            "improves_debuggability": True,
            "improves_recoverability": False,
            "improves_determinism": True,
            "reduces_manual_steps": True,
            "simplifies_public_api": True,
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def load_budget_policy(policy_path: Optional[str] = None) -> dict:
    """Load a budget benefit policy from JSON.

    If no path given, returns the default built-in policy.

    Policy format:
        {
            "<dir>": {
                "<file.py>": {
                    "improves_debuggability": bool,
                    "improves_recoverability": bool,
                    "improves_determinism": bool,
                    "reduces_manual_steps": bool,
                    "simplifies_public_api": bool,
                }
            }
        }
    """
    if policy_path is None:
        return dict(DEFAULT_BENEFIT_POLICY)

    if not os.path.exists(policy_path):
        return dict(DEFAULT_BENEFIT_POLICY)

    with open(policy_path, encoding="utf-8") as f:
        loaded = json.load(f)

    # Merge with defaults (loaded overrides defaults)
    merged = dict(DEFAULT_BENEFIT_POLICY)
    for dir_key, files in loaded.items():
        if dir_key not in merged:
            merged[dir_key] = {}
        for fname, benefits in files.items():
            merged[dir_key][fname] = benefits
    return merged


def _build_benefits(
    complexities: Tuple[ModuleComplexity, ...],
    policy: dict,
) -> Tuple[ModuleBenefit, ...]:
    """Build ModuleBenefit objects by matching policy to complexity paths."""
    benefits = []
    for c in complexities:
        # Determine directory key
        path = c.path.replace("\\", "/")
        dir_key = path.split("/")[0] if "/" in path else ""

        # Look up in policy
        basename = os.path.basename(path)
        file_policy = policy.get(dir_key, {}).get(basename, {})

        b = ModuleBenefit(
            path=path,
            improves_debuggability=file_policy.get("improves_debuggability", False),
            improves_recoverability=file_policy.get("improves_recoverability", False),
            improves_determinism=file_policy.get("improves_determinism", False),
            reduces_manual_steps=file_policy.get("reduces_manual_steps", False),
            simplifies_public_api=file_policy.get("simplifies_public_api", False),
            preserves_kernel_purity=True,  # Default true — set false if kernel purity broken
            preserves_memory_removability=True,
            preserves_truth_source=True,
            benefit_score=0.0,
        )
        benefits.append(ModuleBenefit(
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
        ))

    return tuple(benefits)


def evaluate_phase(
    phase: str,
    v3_root: Optional[str] = None,
    *,
    policy_path: Optional[str] = None,
    allow_new_truth_source: bool = False,
) -> PhaseGateResult:
    """Evaluate a phase against the complexity budget gate.

    Args:
        phase: Phase identifier (e.g. "5A")
        v3_root: Path to v3/ directory. Auto-detected if None.
        policy_path: Path to a custom benefit policy JSON file.
        allow_new_truth_source: If True, new truth sources don't auto-reject.

    Returns:
        PhaseGateResult with verdict and full analysis data.
    """
    if v3_root is None:
        v3_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    from v3.quality.analyze_complexity import ComplexityAnalyzer

    analyzer = ComplexityAnalyzer(v3_root)
    complexities = analyzer.analyze_all()

    policy = load_budget_policy(policy_path)
    benefits = _build_benefits(complexities, policy)

    verdict = evaluate_verdict(
        complexities,
        benefits,
        allow_new_truth_source=allow_new_truth_source,
    )
    # Recompute verdict with hash
    verdict = ComplexityBudgetVerdict(
        total_complexity_score=verdict.total_complexity_score,
        total_benefit_score=verdict.total_benefit_score,
        net_value_score=verdict.net_value_score,
        risk_ratio=verdict.risk_ratio,
        verdict=verdict.verdict,
        reasons=verdict.reasons,
        verdict_hash=verdict.verdict_hash,
    )

    passed = verdict.verdict == VERDICT_ACCEPT

    return PhaseGateResult(
        phase=phase,
        verdict=verdict,
        module_complexities=complexities,
        module_benefits=benefits,
        report_path="",
        passed=passed,
    )


def write_complexity_report(
    gate_result: PhaseGateResult,
    output_path: str,
) -> str:
    """Write a comprehensive complexity budget report to a JSON file.

    Returns the absolute path written.
    """
    report = {
        "phase": gate_result.phase,
        "verdict": gate_result.verdict.to_dict(),
        "modules": [
            {
                "path": c.path,
                "complexity": c.to_dict(),
                "benefit": next(
                    (b.to_dict() for b in gate_result.module_benefits if b.path == c.path),
                    {},
                ),
            }
            for c in gate_result.module_complexities
        ],
        "summary": {
            "total_modules": len(gate_result.module_complexities),
            "passed": gate_result.passed,
        },
    }

    dirname = os.path.dirname(output_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)

    return os.path.abspath(output_path)


def fail_if_rejected(verdict: ComplexityBudgetVerdict) -> None:
    """Raise ComplexityGateRejected if the verdict is REJECT.

    Does nothing if verdict is ACCEPT or REVIEW.
    """
    if verdict.is_rejected:
        raise ComplexityGateRejected(
            f"Phase gate REJECTED: {'; '.join(verdict.reasons)}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════

class ComplexityGateRejected(Exception):
    """Raised when a phase fails the complexity budget gate with REJECT."""
    pass
