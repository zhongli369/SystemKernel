"""
Direction Intelligence Plane — v4.1.

Defines contracts for external direction/intent intelligence providers
(gstack, etc.) WITHOUT integrating them. Providers produce advisory
direction signals — strategic priorities, intent clusters, constraint
detection, risk assessment.

Direction signals are EVIDENCE, never TRUTH. They modify nothing in the
kernel. They suggest; the kernel decides.

Stdlib only. No LLM. No external execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Provider Types
# ═══════════════════════════════════════════════════════════════════════

PROVIDER_TYPE_METHODOLOGY = "methodology"
PROVIDER_TYPE_DETERMINISTIC_MOCK = "deterministic_mock"
PROVIDER_TYPE_GENERIC = "generic"

ALL_PROVIDER_TYPES = (
    PROVIDER_TYPE_METHODOLOGY,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    PROVIDER_TYPE_GENERIC,
)

# ═══════════════════════════════════════════════════════════════════════
# Signal Types
# ═══════════════════════════════════════════════════════════════════════

SIGNAL_TYPE_INTENT_CLUSTER = "intent_cluster"
SIGNAL_TYPE_PRIORITY_RANKING = "priority_ranking"
SIGNAL_TYPE_CONSTRAINT_DETECTED = "constraint_detected"
SIGNAL_TYPE_RISK_ASSESSMENT = "risk_assessment"
SIGNAL_TYPE_STRATEGIC_ALIGNMENT = "strategic_alignment"
SIGNAL_TYPE_SCOPE_RECOMMENDATION = "scope_recommendation"

ALL_SIGNAL_TYPES = (
    SIGNAL_TYPE_INTENT_CLUSTER,
    SIGNAL_TYPE_PRIORITY_RANKING,
    SIGNAL_TYPE_CONSTRAINT_DETECTED,
    SIGNAL_TYPE_RISK_ASSESSMENT,
    SIGNAL_TYPE_STRATEGIC_ALIGNMENT,
    SIGNAL_TYPE_SCOPE_RECOMMENDATION,
)

# ═══════════════════════════════════════════════════════════════════════
# Request Modes
# ═══════════════════════════════════════════════════════════════════════

MODE_INSPECT_ONLY = "inspect_only"
MODE_DRY_RUN = "dry_run"
MODE_EXTERNAL_SERVICE = "external_service"

ALL_REQUEST_MODES = (MODE_INSPECT_ONLY, MODE_DRY_RUN, MODE_EXTERNAL_SERVICE)


# ═══════════════════════════════════════════════════════════════════════
# Direction Intelligence Provider
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DirectionIntelligenceProvider:
    """Description of an external direction intelligence provider.

    Providers offer strategic direction analysis based on their methodology.
    They do NOT make decisions or execute anything.
    truth_source is ALWAYS False. removable is ALWAYS True.
    """
    provider_id: str = ""
    name: str = ""
    provider_type: str = PROVIDER_TYPE_GENERIC
    capability_type: str = "direction"
    execution_mode: str = MODE_INSPECT_ONLY
    requires_llm: bool = False
    requires_external_service: bool = False
    methodology_source: str = ""
    truth_source: bool = False
    removable: bool = True
    description: str = ""
    provider_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "provider_type": self.provider_type,
            "capability_type": self.capability_type,
            "execution_mode": self.execution_mode,
            "requires_llm": self.requires_llm,
            "requires_external_service": self.requires_external_service,
            "methodology_source": self.methodology_source,
            "truth_source": self.truth_source,
            "removable": self.removable,
            "description": self.description,
            "provider_hash": self.provider_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Direction Signal
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DirectionSignal:
    """One direction intelligence signal — advisory only.

    Signals are EVIDENCE that a provider recommends a strategic direction.
    They do NOT make decisions or modify kernel routing.
    All signals are advisory; the kernel is the sole decision authority.
    """
    signal_id: str = ""
    signal_type: str = ""
    source: str = "gstack"
    intent_clusters: Tuple[str, ...] = ()
    priority_ranking: Tuple[str, ...] = ()
    constraints_detected: Tuple[str, ...] = ()
    risk_assessment: Tuple[str, ...] = ()
    confidence: float = 0.0
    recommendations: Tuple[str, ...] = ()
    risk_flags: Tuple[str, ...] = ()
    provenance: str = ""
    truth_source: bool = False
    signal_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "source": self.source,
            "intent_clusters": list(self.intent_clusters),
            "priority_ranking": list(self.priority_ranking),
            "constraints_detected": list(self.constraints_detected),
            "risk_assessment": list(self.risk_assessment),
            "confidence": self.confidence,
            "recommendations": list(self.recommendations),
            "risk_flags": list(self.risk_flags),
            "provenance": self.provenance,
            "truth_source": self.truth_source,
            "signal_hash": self.signal_hash,
        }

    def to_external_output(self) -> dict:
        """Normalize to the External Evidence Provider output contract."""
        import datetime
        return {
            "source": self.source,
            "signal_type": "direction",
            "confidence": self.confidence,
            "payload": {
                "intent_clusters": list(self.intent_clusters),
                "priority_ranking": list(self.priority_ranking),
                "constraints_detected": list(self.constraints_detected),
            },
            "recommendations": list(self.recommendations),
            "risk_flags": list(self.risk_assessment),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Direction Intelligence Request
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DirectionIntelligenceRequest:
    """A request to a direction intelligence provider.

    Describes the task intent, project context, and current system state
    to analyze for strategic direction signals.
    """
    request_id: str = ""
    provider_id: str = ""
    task_intent: str = ""
    project_context: str = ""
    system_state_refs: Tuple[str, ...] = ()
    mode: str = MODE_INSPECT_ONLY
    max_signals: int = 10
    request_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "provider_id": self.provider_id,
            "task_intent": self.task_intent,
            "project_context": self.project_context,
            "system_state_refs": list(self.system_state_refs),
            "mode": self.mode,
            "max_signals": self.max_signals,
            "request_hash": self.request_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Direction Intelligence Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DirectionIntelligenceResult:
    """The result of a direction intelligence request.

    Contains direction signals from the provider. May be blocked if the
    provider violates policy. truth_source is ALWAYS False.
    """
    request_id: str = ""
    provider_id: str = ""
    signals: Tuple[DirectionSignal, ...] = ()
    warnings: Tuple[str, ...] = ()
    blocked: bool = False
    reason: str = ""
    truth_source: bool = False
    result_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "provider_id": self.provider_id,
            "signals": [s.to_dict() for s in self.signals],
            "warnings": list(self.warnings),
            "blocked": self.blocked,
            "reason": self.reason,
            "truth_source": self.truth_source,
            "result_hash": self.result_hash,
        }

    def to_external_outputs(self) -> list:
        """Normalize all signals to the External Evidence Provider output contract."""
        return [s.to_external_output() for s in self.signals]


# ═══════════════════════════════════════════════════════════════════════
# Direction Intelligence Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DirectionIntelligenceReport:
    """Full report combining provider, request, result, and evidence."""
    provider: Optional[DirectionIntelligenceProvider] = None
    request: Optional[DirectionIntelligenceRequest] = None
    result: Optional[DirectionIntelligenceResult] = None
    evidence_bundle_id: str = ""
    policy_status: str = "unknown"
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider.to_dict() if self.provider else None,
            "request": self.request.to_dict() if self.request else None,
            "result": self.result.to_dict() if self.result else None,
            "evidence_bundle_id": self.evidence_bundle_id,
            "policy_status": self.policy_status,
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash Helpers
# ═══════════════════════════════════════════════════════════════════════

def _compute_hash(obj) -> str:
    """Deterministic SHA-256 hash for direction intelligence objects."""
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        for key in ("provider_hash", "signal_hash", "request_hash",
                     "result_hash", "report_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Constructors
# ═══════════════════════════════════════════════════════════════════════

def make_direction_signal(
    signal_type: str = SIGNAL_TYPE_INTENT_CLUSTER,
    source: str = "gstack",
    intent_clusters: Tuple[str, ...] = (),
    priority_ranking: Tuple[str, ...] = (),
    constraints_detected: Tuple[str, ...] = (),
    risk_assessment: Tuple[str, ...] = (),
    confidence: float = 0.0,
    recommendations: Tuple[str, ...] = (),
    risk_flags: Tuple[str, ...] = (),
    provenance: str = "",
) -> DirectionSignal:
    """Create a deterministic DirectionSignal.

    signal_id = hash(source + signal_type + clusters) — deterministic.
    truth_source = ALWAYS False.
    """
    id_input = f"{source}:{signal_type}:{':'.join(sorted(intent_clusters))}"
    signal_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    signal = DirectionSignal(
        signal_id=signal_id,
        signal_type=signal_type,
        source=source,
        intent_clusters=intent_clusters,
        priority_ranking=priority_ranking,
        constraints_detected=constraints_detected,
        risk_assessment=risk_assessment,
        confidence=confidence,
        recommendations=recommendations,
        risk_flags=risk_flags,
        provenance=provenance,
        truth_source=False,
    )
    object.__setattr__(signal, "signal_hash", _compute_hash(signal))
    return signal


def build_direction_intelligence_request(
    provider_id: str,
    task_intent: str = "",
    project_context: str = "",
    system_state_refs: Tuple[str, ...] = (),
    mode: str = MODE_INSPECT_ONLY,
    max_signals: int = 10,
) -> DirectionIntelligenceRequest:
    """Build a deterministic DirectionIntelligenceRequest."""
    refs_input = f"{provider_id}:{task_intent}:{project_context}"
    request_id = hashlib.sha256(refs_input.encode("utf-8")).hexdigest()[:16]

    request = DirectionIntelligenceRequest(
        request_id=request_id,
        provider_id=provider_id,
        task_intent=task_intent,
        project_context=project_context,
        system_state_refs=system_state_refs,
        mode=mode,
        max_signals=max_signals,
    )
    object.__setattr__(request, "request_hash", _compute_hash(request))
    return request


def make_blocked_direction_result(
    request_id: str,
    provider_id: str,
    reason: str,
) -> DirectionIntelligenceResult:
    """Create a blocked direction intelligence result."""
    result = DirectionIntelligenceResult(
        request_id=request_id,
        provider_id=provider_id,
        signals=(),
        blocked=True,
        reason=reason,
        truth_source=False,
    )
    object.__setattr__(result, "result_hash", _compute_hash(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping
# ═══════════════════════════════════════════════════════════════════════

def direction_signals_to_evidence(
    result: DirectionIntelligenceResult,
    registry_hash: str = "",
    adapter_spec_hash: str = "",
):
    """Convert direction intelligence result signals into an EvidenceBundle.

    Each signal becomes one EvidenceRecord. All records have
    truth_source=False.
    """
    from v3.external.evidence import (
        EVIDENCE_TYPE_DIRECTION_SIGNAL,
        TRUST_LOW,
        make_evidence_record,
        build_evidence_bundle,
    )

    records = []
    for signal in result.signals:
        record = make_evidence_record(
            adapter_id=result.provider_id,
            evidence_type=EVIDENCE_TYPE_DIRECTION_SIGNAL,
            capability_type="direction",
            input_data={
                "request_id": result.request_id,
                "signal_type": signal.signal_type,
            },
            output_data={
                "signal_id": signal.signal_id,
                "signal_type": signal.signal_type,
                "intent_clusters": list(signal.intent_clusters),
                "priority_ranking": list(signal.priority_ranking),
                "confidence": signal.confidence,
            },
            payload_summary=f"direction signal: {signal.signal_type} ({signal.signal_id[:8]})",
            payload_ref="",
            source_uri=f"provider://{result.provider_id}",
            collected_by="systemkernel",
            collection_mode=MODE_INSPECT_ONLY,
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            risk_flags=signal.risk_flags,
            confidence=signal.confidence,
            source_trust_level=TRUST_LOW,
        )
        records.append(record)

    return build_evidence_bundle(tuple(records), bundle_type="direction_intelligence")


# ═══════════════════════════════════════════════════════════════════════
# Build Report
# ═══════════════════════════════════════════════════════════════════════

def build_direction_intelligence_report(
    provider: DirectionIntelligenceProvider,
    request: DirectionIntelligenceRequest,
    result: DirectionIntelligenceResult,
    evidence_bundle,
    policy_status: str = "unknown",
) -> DirectionIntelligenceReport:
    """Build a full direction intelligence report."""
    report = DirectionIntelligenceReport(
        provider=provider,
        request=request,
        result=result,
        evidence_bundle_id=evidence_bundle.bundle_id if hasattr(evidence_bundle, "bundle_id") else "",
        policy_status=policy_status,
    )
    object.__setattr__(report, "report_hash", _compute_hash(report))
    return report


# ═══════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DirectionSignalValidationResult:
    """Result of validating a single DirectionSignal."""
    valid: bool = True
    signal_id: str = ""
    violations: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "signal_id": self.signal_id,
            "violations": list(self.violations),
        }


@dataclass(frozen=True)
class DirectionIntelligenceValidationResult:
    """Result of validating a DirectionIntelligenceResult."""
    valid: bool = True
    result_id: str = ""
    signal_results: Tuple[DirectionSignalValidationResult, ...] = ()
    violations: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "result_id": self.result_id,
            "signal_results": [s.to_dict() for s in self.signal_results],
            "violations": list(self.violations),
        }


def validate_direction_signal(signal: DirectionSignal) -> DirectionSignalValidationResult:
    """Validate a single DirectionSignal against contract rules."""
    violations = []

    if signal.truth_source is not False:
        violations.append(f"Signal {signal.signal_id}: truth_source must be False")

    if signal.signal_type not in ALL_SIGNAL_TYPES:
        violations.append(f"Signal {signal.signal_id}: unknown signal_type '{signal.signal_type}'")

    if not signal.signal_id:
        violations.append("signal_id is empty")

    if signal.confidence < 0.0 or signal.confidence > 1.0:
        violations.append(f"Signal {signal.signal_id}: confidence must be 0.0-1.0, got {signal.confidence}")

    return DirectionSignalValidationResult(
        valid=len(violations) == 0,
        signal_id=signal.signal_id,
        violations=tuple(violations),
    )


def validate_direction_intelligence_result(
    result: DirectionIntelligenceResult,
) -> DirectionIntelligenceValidationResult:
    """Validate a DirectionIntelligenceResult against contract rules."""
    violations = []
    signal_results = []

    if result.truth_source is not False:
        violations.append(f"Result {result.request_id}: truth_source must be False")

    if not result.request_id:
        violations.append("request_id is empty")

    if result.blocked and not result.reason:
        violations.append("Blocked result must have a reason")

    for signal in result.signals:
        sv = validate_direction_signal(signal)
        signal_results.append(sv)
        if not sv.valid:
            violations.append(f"Signal {sv.signal_id}: {', '.join(sv.violations)}")

    return DirectionIntelligenceValidationResult(
        valid=len(violations) == 0,
        result_id=result.request_id,
        signal_results=tuple(signal_results),
        violations=tuple(violations),
    )
