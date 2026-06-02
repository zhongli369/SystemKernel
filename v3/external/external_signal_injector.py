"""
External Signal Injector — v4.1.

Central orchestrator for receiving, validating, fusing, and injecting
external intelligence signals into the SystemKernel event pipeline.

Architecture:
  External System (gstack/superpowers methodology)
  → Adapter (gstack_adapter / superpowers_adapter)
  → Schema Validation (direction/quality schemas)
  → EventStore.append() (immutable event log)
  → Decision Fusion (Kernel signal + weighted external signals)
  → Complexity Gate evaluation
  → Observable trace emission

Key invariants:
  - SystemKernel is the SOLE decision authority
  - External signals are MODIFIERS only, never authoritative
  - Complexity Gate blocks if complexity increase > 2x baseline
  - Every signal generates an observable trace
  - truth_source is ALWAYS False for external signals

Stdlib only. No LLM. No external execution.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Trace Actions
# ═══════════════════════════════════════════════════════════════════════

ACTION_ACCEPTED = "accepted"
ACTION_DOWNGRADED = "downgraded"
ACTION_IGNORED = "ignored"

ALL_ACTIONS = (ACTION_ACCEPTED, ACTION_DOWNGRADED, ACTION_IGNORED)

# Rejection reasons
REJECTION_COMPLEXITY = "complexity"
REJECTION_CONFLICT = "conflict"
REJECTION_LOW_CONFIDENCE = "low_confidence"
REJECTION_POLICY_BLOCKED = "policy_blocked"
REJECTION_VALIDATION_FAILED = "validation_failed"

ALL_REJECTION_REASONS = (
    REJECTION_COMPLEXITY,
    REJECTION_CONFLICT,
    REJECTION_LOW_CONFIDENCE,
    REJECTION_POLICY_BLOCKED,
    REJECTION_VALIDATION_FAILED,
)


# ═══════════════════════════════════════════════════════════════════════
# Observable Trace
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SignalTrace:
    """Observable trace for every external signal processed.

    Every signal MUST generate a trace. Required by spec section 7.
    """
    trace_id: str = ""
    source: str = ""
    event_type: str = ""
    kernel_action: str = ACTION_ACCEPTED
    reason: str = ""
    timestamp: str = ""
    confidence: float = 0.0
    complexity_impact: float = 0.0
    trace_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "source": self.source,
            "event_type": self.event_type,
            "kernel_action": self.kernel_action,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "complexity_impact": self.complexity_impact,
            "trace_hash": self.trace_hash,
        }


@dataclass(frozen=True)
class TraceReport:
    """Aggregate report of all signal traces from an injection session."""
    session_id: str = ""
    traces: Tuple[SignalTrace, ...] = ()
    accepted_count: int = 0
    downgraded_count: int = 0
    ignored_count: int = 0
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "traces": [t.to_dict() for t in self.traces],
            "accepted_count": self.accepted_count,
            "downgraded_count": self.downgraded_count,
            "ignored_count": self.ignored_count,
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Decision Fusion
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FusedDecision:
    """Result of the decision fusion process.

    Final_Score = Kernel_Deterministic_Signal
                + Σ (External_Signal × Weight)
                - Complexity_Penalty

    External signals are ONLY modifiers, never authoritative.
    """
    session_id: str = ""
    kernel_score: float = 1.0
    direction_score: float = 0.0
    quality_score: float = 0.0
    complexity_penalty: float = 0.0
    final_score: float = 0.0
    verdict: str = "PROCEED"
    direction_weight: float = 0.4
    quality_weight: float = 0.6
    direction_signals_count: int = 0
    quality_signals_count: int = 0
    blocked: bool = False
    block_reason: str = ""
    decision_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "kernel_score": self.kernel_score,
            "direction_score": self.direction_score,
            "quality_score": self.quality_score,
            "complexity_penalty": self.complexity_penalty,
            "final_score": self.final_score,
            "verdict": self.verdict,
            "direction_weight": self.direction_weight,
            "quality_weight": self.quality_weight,
            "direction_signals_count": self.direction_signals_count,
            "quality_signals_count": self.quality_signals_count,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "decision_hash": self.decision_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Complexity Gate
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ComplexityGateResult:
    """Result of the complexity gate evaluation.

    Rule: if complexity_increase > 2.0 → ignore_external_signal
    """
    passed: bool = True
    baseline_complexity: float = 1.0
    new_complexity: float = 1.0
    increase_ratio: float = 1.0
    reason: str = ""
    gate_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "baseline_complexity": self.baseline_complexity,
            "new_complexity": self.new_complexity,
            "increase_ratio": self.increase_ratio,
            "reason": self.reason,
            "gate_hash": self.gate_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash Helpers
# ═══════════════════════════════════════════════════════════════════════

def _compute_hash(obj) -> str:
    """Deterministic SHA-256 hash."""
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        for key in ("trace_hash", "report_hash", "decision_hash", "gate_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Trace Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_trace(
    source: str,
    event_type: str,
    action: str,
    reason: str = "",
    confidence: float = 0.0,
    complexity_impact: float = 0.0,
) -> SignalTrace:
    """Create an observable trace for a signal."""
    trace_id = str(uuid.uuid4())[:16]
    trace = SignalTrace(
        trace_id=trace_id,
        source=source,
        event_type=event_type,
        kernel_action=action,
        reason=reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
        confidence=confidence,
        complexity_impact=complexity_impact,
    )
    object.__setattr__(trace, "trace_hash", _compute_hash(trace))
    return trace


# ═══════════════════════════════════════════════════════════════════════
# Complexity Gate
# ═══════════════════════════════════════════════════════════════════════

def evaluate_complexity_gate(
    baseline_complexity: float = 1.0,
    new_planes_count: int = 2,
    signals_count: int = 0,
) -> ComplexityGateResult:
    """Evaluate whether the integration passes the complexity gate.

    Each new plane adds ~0.15 to complexity (estimated from code structure).
    Each signal adds ~0.01 to complexity (evidence records).

    Rule from spec section 6:
    if complexity_increase > 2.0:
        ignore_external_signal
    """
    plane_complexity = new_planes_count * 0.15
    signal_complexity = signals_count * 0.01
    additional_complexity = plane_complexity + signal_complexity

    new_complexity = baseline_complexity + additional_complexity
    increase_ratio = new_complexity / max(baseline_complexity, 0.01)

    passed = increase_ratio <= 2.0

    reason = ""
    if not passed:
        reason = (
            f"Complexity gate BLOCKED: increase ratio {increase_ratio:.2f} > 2.0. "
            f"Baseline: {baseline_complexity:.2f}, New: {new_complexity:.2f}. "
            f"External signals IGNORED per spec section 6."
        )
    else:
        reason = (
            f"Complexity gate PASSED: increase ratio {increase_ratio:.2f} ≤ 2.0. "
            f"Baseline: {baseline_complexity:.2f}, New: {new_complexity:.2f}."
        )

    result = ComplexityGateResult(
        passed=passed,
        baseline_complexity=baseline_complexity,
        new_complexity=new_complexity,
        increase_ratio=increase_ratio,
        reason=reason,
    )
    object.__setattr__(result, "gate_hash", _compute_hash(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
# Decision Fusion
# ═══════════════════════════════════════════════════════════════════════

def fuse_decisions(
    kernel_score: float = 1.0,
    direction_result=None,
    quality_result=None,
    direction_weight: float = 0.4,
    quality_weight: float = 0.6,
    baseline_complexity: float = 1.0,
) -> FusedDecision:
    """Fuse external signals with kernel signal using the decision formula.

    Final_Score = Kernel_Deterministic_Signal
                + Σ (External_Signal × Weight)
                - Complexity_Penalty

    External signals are ONLY modifiers. Kernel score is dominant.
    """
    session_id = str(uuid.uuid4())[:16]

    # Extract external signal scores
    direction_score = 0.0
    quality_score = 0.0
    direction_count = 0
    quality_count = 0

    if direction_result is not None and not direction_result.blocked:
        direction_count = len(direction_result.signals)
        # Average confidence across all direction signals
        if direction_result.signals:
            direction_score = sum(
                s.confidence for s in direction_result.signals
            ) / len(direction_result.signals)

    if quality_result is not None and not quality_result.blocked:
        quality_count = len(quality_result.signals)
        if hasattr(quality_result, "quality_score"):
            quality_score = quality_result.quality_score
        elif quality_result.signals:
            quality_score = sum(
                s.confidence for s in quality_result.signals
            ) / len(quality_result.signals)

    # Complexity gate
    total_signals = direction_count + quality_count
    gate = evaluate_complexity_gate(
        baseline_complexity=baseline_complexity,
        new_planes_count=2,
        signals_count=total_signals,
    )

    complexity_penalty = 0.0
    if not gate.passed:
        complexity_penalty = gate.increase_ratio - 2.0  # penalty proportional to overage
        # Cap external scores when gate fails — but still compute for trace
        direction_score = direction_score * 0.1  # 90% reduction
        quality_score = quality_score * 0.1

    # Decision fusion formula
    weighted_direction = direction_score * direction_weight
    weighted_quality = quality_score * quality_weight
    external_contribution = weighted_direction + weighted_quality

    final_score = kernel_score + external_contribution - complexity_penalty
    final_score = max(0.0, min(2.0, final_score))  # Clamp to [0, 2]

    # Verdict
    blocked = False
    block_reason = ""

    if not gate.passed:
        blocked = True
        block_reason = gate.reason
        verdict = "BLOCKED_BY_COMPLEXITY_GATE"
    elif final_score < 0.5:
        verdict = "LOW_CONFIDENCE"
    elif final_score < 0.8:
        verdict = "REVIEW_NEEDED"
    else:
        verdict = "PROCEED"

    decision = FusedDecision(
        session_id=session_id,
        kernel_score=kernel_score,
        direction_score=direction_score,
        quality_score=quality_score,
        complexity_penalty=complexity_penalty,
        final_score=final_score,
        verdict=verdict,
        direction_weight=direction_weight,
        quality_weight=quality_weight,
        direction_signals_count=direction_count,
        quality_signals_count=quality_count,
        blocked=blocked,
        block_reason=block_reason,
    )
    object.__setattr__(decision, "decision_hash", _compute_hash(decision))
    return decision


# ═══════════════════════════════════════════════════════════════════════
# Internal Query Layer
# ═══════════════════════════════════════════════════════════════════════

def query_external_signals(
    task_intent: str = "",
    project_context: str = "",
    target_content: str = "",
    target_type: str = "code",
    system_state_refs: Tuple[str, ...] = (),
    target_refs: Tuple[str, ...] = (),
    registry_hash: str = "",
    adapter_spec_hash: str = "",
) -> dict:
    """Query both external intelligence planes for raw signal data.

    This is the internal query layer called by inject_external_signals.
    Queries direction (gstack) and quality (superpowers) adapters and
    returns raw signal results WITHOUT decision fusion.

    Deterministic. No hidden state. No LLM. No external execution.

    Returns:
      {
        "direction": DirectionIntelligenceResult | None,
        "quality": QualityIntelligenceResult | None,
        "direction_evidence": EvidenceBundle | None,
        "quality_evidence": EvidenceBundle | None,
        "direction_status": "ready" | "blocked" | "validation_failed" | "error" | "skipped",
        "quality_status": "ready" | "blocked" | "validation_failed" | "error" | "skipped",
        "direction_error": str,
        "quality_error": str,
        "query_hash": str,
      }
    """
    direction_result = None
    quality_result = None
    direction_evidence = None
    quality_evidence = None
    direction_status = "skipped"
    quality_status = "skipped"
    direction_error = ""
    quality_error = ""

    # Phase 1: gstack direction analysis
    if task_intent:
        try:
            from v3.external.gstack_adapter import inject_gstack_direction_event

            dir_injection = inject_gstack_direction_event(
                task_intent=task_intent,
                project_context=project_context,
                system_state_refs=system_state_refs,
                registry_hash=registry_hash,
                adapter_spec_hash=adapter_spec_hash,
            )

            direction_result = dir_injection.get("result")
            direction_status = dir_injection["status"]

            if dir_injection["status"] == "ready":
                direction_evidence = dir_injection.get("evidence_bundle")
        except Exception as e:
            direction_status = "error"
            direction_error = str(e)

    # Phase 2: superpowers quality analysis
    if target_content:
        try:
            from v3.external.superpowers_adapter import inject_superpowers_quality_event

            qual_injection = inject_superpowers_quality_event(
                target_content=target_content,
                target_type=target_type,
                target_refs=target_refs,
                registry_hash=registry_hash,
                adapter_spec_hash=adapter_spec_hash,
            )

            quality_result = qual_injection.get("result")
            quality_status = qual_injection["status"]

            if qual_injection["status"] == "ready":
                quality_evidence = qual_injection.get("evidence_bundle")
        except Exception as e:
            quality_status = "error"
            quality_error = str(e)

    query_data = {
        "direction_status": direction_status,
        "quality_status": quality_status,
        "direction_error": direction_error,
        "quality_error": quality_error,
    }

    return {
        "direction": direction_result,
        "quality": quality_result,
        "direction_evidence": direction_evidence,
        "quality_evidence": quality_evidence,
        "direction_status": direction_status,
        "quality_status": quality_status,
        "direction_error": direction_error,
        "quality_error": quality_error,
        "query_hash": _compute_hash(query_data),
    }


# ═══════════════════════════════════════════════════════════════════════
# Unified External Intelligence Gateway
# ═══════════════════════════════════════════════════════════════════════

def inject_external_signals(
    task_intent: str = "",
    project_context: str = "",
    target_content: str = "",
    target_type: str = "code",
    system_state_refs: Tuple[str, ...] = (),
    target_refs: Tuple[str, ...] = (),
    registry_hash: str = "",
    adapter_spec_hash: str = "",
    baseline_complexity: float = 1.0,
) -> dict:
    """Single unified external intelligence gateway.

    Orchestrates direction + quality signals, applies complexity gate,
    performs deterministic decision fusion, and emits a full traceable result.

    Pipeline:
      1. query_external_signals() → raw direction + quality data
      2. Weighted fusion: direction_weight=0.4, quality_weight=0.6
      3. Complexity gate evaluation (threshold: 2.0x baseline)
      4. Decision with reasoning chain

    External signals are MODIFIERS only, never authoritative.
    Kernel is the sole decision authority.
    Deterministic. No hidden state. No LLM. No external execution.

    Returns:
      {
        "decision": {
          "verdict": "PROCEED | REVIEW | BLOCKED",
          "final_score": float,
          "reasoning": [str, ...]
        },
        "signals": {
          "direction": {"source": "gstack", "signals_count": int, "avg_confidence": float, ...},
          "quality": {"source": "superpowers", "signals_count": int, "quality_score": float, ...}
        },
        "trace_id": str,
        "complexity_score": float,
      }
    """
    trace_id = str(uuid.uuid4())[:16]
    reasoning = []

    # Step 1: Query both external intelligence planes
    signals = query_external_signals(
        task_intent=task_intent,
        project_context=project_context,
        target_content=target_content,
        target_type=target_type,
        system_state_refs=system_state_refs,
        target_refs=target_refs,
        registry_hash=registry_hash,
        adapter_spec_hash=adapter_spec_hash,
    )

    direction_result = signals["direction"]
    quality_result = signals["quality"]

    # Step 2: Extract direction signal scores and build summary
    direction_score = 0.0
    direction_count = 0
    direction_summary = {}

    if direction_result is not None and not direction_result.blocked:
        direction_count = len(direction_result.signals)
        if direction_result.signals:
            direction_score = sum(
                s.confidence for s in direction_result.signals
            ) / len(direction_result.signals)
        all_clusters = []
        for s in direction_result.signals:
            all_clusters.extend(s.intent_clusters)
        direction_summary = {
            "source": "gstack",
            "signals_count": direction_count,
            "avg_confidence": round(direction_score, 4),
            "intent_clusters": sorted(set(all_clusters)),
            "status": signals["direction_status"],
        }
    else:
        direction_summary = {
            "source": "gstack",
            "signals_count": 0,
            "avg_confidence": 0.0,
            "intent_clusters": [],
            "status": signals["direction_status"],
        }
        if signals["direction_error"]:
            direction_summary["error"] = signals["direction_error"]

    # Step 3: Extract quality signal scores and build summary
    quality_score = 0.0
    quality_count = 0
    quality_summary = {}

    if quality_result is not None and not quality_result.blocked:
        quality_count = len(quality_result.signals)
        if hasattr(quality_result, "quality_score"):
            quality_score = quality_result.quality_score
        elif quality_result.signals:
            quality_score = sum(
                s.confidence for s in quality_result.signals
            ) / len(quality_result.signals)
        defect_count = sum(
            1 for s in quality_result.signals
            if getattr(s, "signal_type", "") == "defect"
        )
        quality_summary = {
            "source": "superpowers",
            "signals_count": quality_count,
            "quality_score": round(quality_score, 4),
            "defect_count": defect_count,
            "status": signals["quality_status"],
        }
    else:
        quality_summary = {
            "source": "superpowers",
            "signals_count": 0,
            "quality_score": 0.0,
            "defect_count": 0,
            "status": signals["quality_status"],
        }
        if signals["quality_error"]:
            quality_summary["error"] = signals["quality_error"]

    # Step 4: Weighted fusion (direction=0.4, quality=0.6)
    direction_weight = 0.4
    quality_weight = 0.6
    weighted_direction = direction_score * direction_weight
    weighted_quality = quality_score * quality_weight
    external_contribution = weighted_direction + weighted_quality

    reasoning.append(
        f"Direction signals: {direction_count} signal(s), "
        f"avg_confidence={direction_score:.4f}, "
        f"weighted={weighted_direction:.4f} (weight={direction_weight})"
    )
    reasoning.append(
        f"Quality signals: {quality_count} signal(s), "
        f"quality_score={quality_score:.4f}, "
        f"weighted={weighted_quality:.4f} (weight={quality_weight})"
    )
    reasoning.append(
        f"External contribution: {weighted_direction:.4f} + {weighted_quality:.4f} "
        f"= {external_contribution:.4f}"
    )

    # Step 5: Complexity gate
    total_signals = direction_count + quality_count
    gate = evaluate_complexity_gate(
        baseline_complexity=baseline_complexity,
        new_planes_count=2,
        signals_count=total_signals,
    )

    complexity_score = gate.increase_ratio
    complexity_penalty = 0.0

    reasoning.append(
        f"Complexity gate: baseline={gate.baseline_complexity:.2f}, "
        f"new={gate.new_complexity:.2f}, "
        f"ratio={gate.increase_ratio:.2f} (threshold=2.0) "
        f"→ {'PASSED' if gate.passed else 'BLOCKED'}"
    )

    if not gate.passed:
        complexity_penalty = gate.increase_ratio - 2.0
        # Complexity gate failure: external signals reduced to 10%
        weighted_direction = direction_score * direction_weight * 0.1
        weighted_quality = quality_score * quality_weight * 0.1
        external_contribution = weighted_direction + weighted_quality
        reasoning.append(
            f"Complexity gate BLOCKED: external signals reduced to 10%, "
            f"penalty={complexity_penalty:.4f}, "
            f"adjusted external contribution={external_contribution:.4f}"
        )

    # Step 6: Final decision
    kernel_score = 1.0
    final_score = kernel_score + external_contribution - complexity_penalty
    final_score = max(0.0, min(2.0, final_score))

    reasoning.append(
        f"Final score: kernel({kernel_score:.4f}) "
        f"+ external({external_contribution:.4f}) "
        f"- complexity_penalty({complexity_penalty:.4f}) "
        f"= {final_score:.4f}"
    )

    # Step 7: Verdict
    if not gate.passed:
        verdict = "BLOCKED"
        reasoning.append(
            "Verdict BLOCKED: complexity gate threshold (2.0x) exceeded — "
            "external signal influence capped"
        )
    elif final_score < 0.5:
        verdict = "BLOCKED"
        reasoning.append(
            f"Verdict BLOCKED: final_score ({final_score:.4f}) < 0.5 threshold"
        )
    elif final_score < 0.8:
        verdict = "REVIEW"
        reasoning.append(
            f"Verdict REVIEW: final_score ({final_score:.4f}) < 0.8 threshold — "
            "human review recommended before proceeding"
        )
    else:
        verdict = "PROCEED"
        reasoning.append(
            f"Verdict PROCEED: final_score ({final_score:.4f}) >= 0.8 threshold"
        )

    return {
        "decision": {
            "verdict": verdict,
            "final_score": round(final_score, 4),
            "reasoning": reasoning,
        },
        "signals": {
            "direction": direction_summary,
            "quality": quality_summary,
        },
        "trace_id": trace_id,
        "complexity_score": round(complexity_score, 4),
    }


# ═══════════════════════════════════════════════════════════════════════
# Standalone helpers
# ═══════════════════════════════════════════════════════════════════════

def quick_direction_inject(task_intent: str, project_context: str = "") -> dict:
    """Quick directional analysis without full injection pipeline.

    Returns the EEP-normalized output directly.
    """
    from v3.external.gstack_adapter import GstackDirectionAdapter
    return GstackDirectionAdapter.quick_analyze(task_intent, project_context)


def quick_quality_inject(target_content: str, target_type: str = "code") -> dict:
    """Quick quality analysis without full injection pipeline.

    Returns the EEP-normalized output directly.
    """
    from v3.external.superpowers_adapter import SuperpowersQualityAdapter
    return SuperpowersQualityAdapter.quick_analyze(target_content, target_type)
