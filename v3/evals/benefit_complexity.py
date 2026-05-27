"""
Benefit-Complexity Scoring — Phase 10.

Measures whether v4 planes deliver real engineering value without
excessive complexity. Designed to catch the "ability +10%, complexity +300%"
anti-pattern before it reaches production.

No external execution. No LLM scoring. Deterministic.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Tuple


# ═══════════════════════════════════════════════════════════════════════
# Verdict constants
# ═══════════════════════════════════════════════════════════════════════

VERDICT_ACCEPT = "ACCEPT"
VERDICT_REVIEW = "REVIEW"
VERDICT_REJECT = "REJECT"

ALL_VERDICTS = (VERDICT_ACCEPT, VERDICT_REVIEW, VERDICT_REJECT)


# ═══════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BenefitSignal:
    """Signals that a plane/module delivers genuine engineering value.

    Each field is a boolean: True means the benefit is present.
    """
    reduces_manual_steps: bool = False
    improves_verifiability: bool = False
    improves_replaceability: bool = False
    improves_safety_boundary: bool = False
    improves_debuggability: bool = False
    avoids_new_truth_source: bool = True
    avoids_runtime_dependency: bool = True
    signal_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "reduces_manual_steps": self.reduces_manual_steps,
            "improves_verifiability": self.improves_verifiability,
            "improves_replaceability": self.improves_replaceability,
            "improves_safety_boundary": self.improves_safety_boundary,
            "improves_debuggability": self.improves_debuggability,
            "avoids_new_truth_source": self.avoids_new_truth_source,
            "avoids_runtime_dependency": self.avoids_runtime_dependency,
            "signal_hash": self.signal_hash,
        }

    def benefit_score(self) -> float:
        """Compute raw benefit score.

        Each True benefit = +1.0 (max 5.0 from improvements).
        avoid_new_truth_source = +1.5 (required gate).
        avoids_runtime_dependency = +1.0.
        Max = 7.5.
        """
        score = 0.0
        if self.reduces_manual_steps:
            score += 1.0
        if self.improves_verifiability:
            score += 1.0
        if self.improves_replaceability:
            score += 1.0
        if self.improves_safety_boundary:
            score += 1.0
        if self.improves_debuggability:
            score += 1.0
        if self.avoids_new_truth_source:
            score += 1.5
        if self.avoids_runtime_dependency:
            score += 1.0
        return score


@dataclass(frozen=True)
class BenefitComplexityScore:
    """Combined benefit-vs-complexity score for one target."""
    target_id: str = ""
    benefit_score: float = 0.0
    complexity_score: float = 0.0
    net_value: float = 0.0
    risk_ratio: float = 0.0
    verdict: str = VERDICT_REVIEW
    reasons: Tuple[str, ...] = ()
    score_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "benefit_score": self.benefit_score,
            "complexity_score": self.complexity_score,
            "net_value": self.net_value,
            "risk_ratio": self.risk_ratio,
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "score_hash": self.score_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash helpers
# ═══════════════════════════════════════════════════════════════════════

def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        for key in ("signal_hash", "score_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════

def score_benefit_complexity(
    target_id: str,
    benefit_signal: BenefitSignal,
    complexity_score: float,
) -> BenefitComplexityScore:
    """Compute a benefit-complexity score for one target.

    risk_ratio = complexity_score / max(benefit_score, 0.01)
    net_value = benefit_score - complexity_score
    """
    b_score = benefit_signal.benefit_score()
    c_score = max(complexity_score, 0.01)
    risk = round(c_score / max(b_score, 0.01), 4)
    net = round(b_score - c_score, 4)

    reasons = []
    if not benefit_signal.avoids_new_truth_source:
        reasons.append("NEW_TRUTH_SOURCE: target introduces a new truth source")
    if not benefit_signal.avoids_runtime_dependency:
        reasons.append("RUNTIME_DEPENDENCY: target introduces a runtime dependency")
    if risk > 3.0:
        reasons.append(f"RISK_RATIO_EXCEEDS_3: risk_ratio={risk}")
    if risk > 2.0:
        reasons.append(f"RISK_RATIO_EXCEEDS_2: risk_ratio={risk}")
    if net < 0:
        reasons.append(f"NEGATIVE_NET_VALUE: net_value={net}")

    verdict = compare_against_thresholds(risk, benefit_signal)

    score = BenefitComplexityScore(
        target_id=target_id,
        benefit_score=b_score,
        complexity_score=c_score,
        net_value=net,
        risk_ratio=risk,
        verdict=verdict,
        reasons=tuple(reasons),
    )
    object.__setattr__(score, "score_hash", _compute_hash(score))
    return score


def compare_against_thresholds(
    risk_ratio: float,
    benefit_signal: BenefitSignal,
) -> str:
    """Determine verdict from risk_ratio and benefit signals.

    Rules:
    - No new truth source → required (REJECT if violated)
    - Runtime dependency → REJECT
    - risk_ratio > 3 → REJECT
    - risk_ratio > 2 → REVIEW
    - Otherwise → ACCEPT
    """
    if not benefit_signal.avoids_new_truth_source:
        return VERDICT_REJECT
    if not benefit_signal.avoids_runtime_dependency:
        return VERDICT_REJECT
    if risk_ratio > 3.0:
        return VERDICT_REJECT
    if risk_ratio > 2.0:
        return VERDICT_REVIEW
    return VERDICT_ACCEPT


# ═══════════════════════════════════════════════════════════════════════
# Report generation
# ═══════════════════════════════════════════════════════════════════════

def write_benefit_complexity_report(
    scores: Tuple[BenefitComplexityScore, ...],
    path: str,
) -> str:
    """Write a benefit-complexity report to JSON."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    accepted = sum(1 for s in scores if s.verdict == VERDICT_ACCEPT)
    review = sum(1 for s in scores if s.verdict == VERDICT_REVIEW)
    rejected = sum(1 for s in scores if s.verdict == VERDICT_REJECT)

    report = {
        "report_type": "benefit_complexity_report",
        "targets": [s.to_dict() for s in scores],
        "summary": {
            "total": len(scores),
            "accepted": accepted,
            "review": review,
            "rejected": rejected,
            "average_benefit": round(sum(s.benefit_score for s in scores) / max(len(scores), 1), 4),
            "average_complexity": round(sum(s.complexity_score for s in scores) / max(len(scores), 1), 4),
            "average_net_value": round(sum(s.net_value for s in scores) / max(len(scores), 1), 4),
            "overall_verdict": VERDICT_REJECT if rejected > 0 else (
                VERDICT_REVIEW if review > 0 else VERDICT_ACCEPT
            ),
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return os.path.abspath(path)
