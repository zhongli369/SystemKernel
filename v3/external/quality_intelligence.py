"""
Quality Intelligence Plane — v4.1.

Defines contracts for external quality evaluation providers (superpowers,
etc.) WITHOUT integrating them. Providers produce advisory quality signals —
defect detection, anti-pattern identification, improvement suggestions,
refinement recommendations.

Quality signals are EVIDENCE, never TRUTH. They evaluate; the kernel decides.

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

SIGNAL_TYPE_DEFECT = "defect"
SIGNAL_TYPE_ANTI_PATTERN = "anti_pattern"
SIGNAL_TYPE_IMPROVEMENT = "improvement"
SIGNAL_TYPE_REFINEMENT = "refinement"
SIGNAL_TYPE_COMPLETENESS_GAP = "completeness_gap"
SIGNAL_TYPE_TESTING_GAP = "testing_gap"

ALL_SIGNAL_TYPES = (
    SIGNAL_TYPE_DEFECT,
    SIGNAL_TYPE_ANTI_PATTERN,
    SIGNAL_TYPE_IMPROVEMENT,
    SIGNAL_TYPE_REFINEMENT,
    SIGNAL_TYPE_COMPLETENESS_GAP,
    SIGNAL_TYPE_TESTING_GAP,
)

# Severity levels
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

ALL_SEVERITIES = (SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW)

# ═══════════════════════════════════════════════════════════════════════
# Request Modes
# ═══════════════════════════════════════════════════════════════════════

MODE_INSPECT_ONLY = "inspect_only"
MODE_DRY_RUN = "dry_run"
MODE_EXTERNAL_SERVICE = "external_service"

ALL_REQUEST_MODES = (MODE_INSPECT_ONLY, MODE_DRY_RUN, MODE_EXTERNAL_SERVICE)


# ═══════════════════════════════════════════════════════════════════════
# Quality Intelligence Provider
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QualityIntelligenceProvider:
    """Description of an external quality intelligence provider.

    Providers evaluate code, plans, and execution traces for quality
    issues. They do NOT enforce changes or override kernel decisions.
    truth_source is ALWAYS False. removable is ALWAYS True.
    """
    provider_id: str = ""
    name: str = ""
    provider_type: str = PROVIDER_TYPE_GENERIC
    capability_type: str = "quality"
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
# Quality Signal
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QualitySignal:
    """One quality intelligence signal — advisory only.

    Signals are EVIDENCE that a provider has evaluated quality.
    They suggest improvements; the kernel decides what to apply.
    """
    signal_id: str = ""
    signal_type: str = ""
    source: str = "superpowers"
    quality_score: float = 0.0
    defects: Tuple[str, ...] = ()
    anti_patterns: Tuple[str, ...] = ()
    improvements: Tuple[str, ...] = ()
    refinement_suggestions: Tuple[str, ...] = ()
    severity: str = SEVERITY_MEDIUM
    confidence: float = 0.0
    risk_flags: Tuple[str, ...] = ()
    provenance: str = ""
    truth_source: bool = False
    signal_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "source": self.source,
            "quality_score": self.quality_score,
            "defects": list(self.defects),
            "anti_patterns": list(self.anti_patterns),
            "improvements": list(self.improvements),
            "refinement_suggestions": list(self.refinement_suggestions),
            "severity": self.severity,
            "confidence": self.confidence,
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
            "signal_type": "quality",
            "confidence": self.confidence,
            "payload": {
                "quality_score": self.quality_score,
                "defects": list(self.defects),
                "anti_patterns": list(self.anti_patterns),
            },
            "recommendations": list(self.refinement_suggestions),
            "risk_flags": list(map(str, self.risk_flags)),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Quality Intelligence Request
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QualityIntelligenceRequest:
    """A request to a quality intelligence provider.

    Describes what to evaluate — plans, code, or execution traces.
    """
    request_id: str = ""
    provider_id: str = ""
    target_type: str = ""
    target_content: str = ""
    target_refs: Tuple[str, ...] = ()
    mode: str = MODE_INSPECT_ONLY
    max_signals: int = 20
    request_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "provider_id": self.provider_id,
            "target_type": self.target_type,
            "target_content": self.target_content,
            "target_refs": list(self.target_refs),
            "mode": self.mode,
            "max_signals": self.max_signals,
            "request_hash": self.request_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Quality Intelligence Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QualityIntelligenceResult:
    """The result of a quality intelligence request.

    Contains quality signals from the provider. May be blocked if the
    provider violates policy. truth_source is ALWAYS False.
    """
    request_id: str = ""
    provider_id: str = ""
    signals: Tuple[QualitySignal, ...] = ()
    quality_score: float = 0.0
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
            "quality_score": self.quality_score,
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
# Quality Intelligence Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QualityIntelligenceReport:
    """Full report combining provider, request, result, and evidence."""
    provider: Optional[QualityIntelligenceProvider] = None
    request: Optional[QualityIntelligenceRequest] = None
    result: Optional[QualityIntelligenceResult] = None
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
    """Deterministic SHA-256 hash for quality intelligence objects."""
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

def make_quality_signal(
    signal_type: str = SIGNAL_TYPE_IMPROVEMENT,
    source: str = "superpowers",
    quality_score: float = 0.0,
    defects: Tuple[str, ...] = (),
    anti_patterns: Tuple[str, ...] = (),
    improvements: Tuple[str, ...] = (),
    refinement_suggestions: Tuple[str, ...] = (),
    severity: str = SEVERITY_MEDIUM,
    confidence: float = 0.0,
    risk_flags: Tuple[str, ...] = (),
    provenance: str = "",
) -> QualitySignal:
    """Create a deterministic QualitySignal.

    signal_id = hash(source + signal_type + content) — deterministic.
    truth_source = ALWAYS False.
    """
    id_input = f"{source}:{signal_type}:{severity}:{quality_score}"
    signal_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    signal = QualitySignal(
        signal_id=signal_id,
        signal_type=signal_type,
        source=source,
        quality_score=quality_score,
        defects=defects,
        anti_patterns=anti_patterns,
        improvements=improvements,
        refinement_suggestions=refinement_suggestions,
        severity=severity,
        confidence=confidence,
        risk_flags=risk_flags,
        provenance=provenance,
        truth_source=False,
    )
    object.__setattr__(signal, "signal_hash", _compute_hash(signal))
    return signal


def build_quality_intelligence_request(
    provider_id: str,
    target_type: str = "",
    target_content: str = "",
    target_refs: Tuple[str, ...] = (),
    mode: str = MODE_INSPECT_ONLY,
    max_signals: int = 20,
) -> QualityIntelligenceRequest:
    """Build a deterministic QualityIntelligenceRequest."""
    refs_input = f"{provider_id}:{target_type}:{target_content[:200]}"
    request_id = hashlib.sha256(refs_input.encode("utf-8")).hexdigest()[:16]

    request = QualityIntelligenceRequest(
        request_id=request_id,
        provider_id=provider_id,
        target_type=target_type,
        target_content=target_content,
        target_refs=target_refs,
        mode=mode,
        max_signals=max_signals,
    )
    object.__setattr__(request, "request_hash", _compute_hash(request))
    return request


def make_blocked_quality_result(
    request_id: str,
    provider_id: str,
    reason: str,
) -> QualityIntelligenceResult:
    """Create a blocked quality intelligence result."""
    result = QualityIntelligenceResult(
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

def quality_signals_to_evidence(
    result: QualityIntelligenceResult,
    registry_hash: str = "",
    adapter_spec_hash: str = "",
):
    """Convert quality intelligence result signals into an EvidenceBundle.

    Each signal becomes one EvidenceRecord. All records have
    truth_source=False.
    """
    from v3.external.evidence import (
        EVIDENCE_TYPE_QUALITY_SIGNAL,
        TRUST_LOW,
        make_evidence_record,
        build_evidence_bundle,
    )

    records = []
    for signal in result.signals:
        record = make_evidence_record(
            adapter_id=result.provider_id,
            evidence_type=EVIDENCE_TYPE_QUALITY_SIGNAL,
            capability_type="quality",
            input_data={
                "request_id": result.request_id,
                "signal_type": signal.signal_type,
            },
            output_data={
                "signal_id": signal.signal_id,
                "signal_type": signal.signal_type,
                "quality_score": signal.quality_score,
                "defects": list(signal.defects),
                "anti_patterns": list(signal.anti_patterns),
                "severity": signal.severity,
                "confidence": signal.confidence,
            },
            payload_summary=f"quality signal: {signal.signal_type} [{signal.severity}] ({signal.signal_id[:8]})",
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

    return build_evidence_bundle(tuple(records), bundle_type="quality_intelligence")


# ═══════════════════════════════════════════════════════════════════════
# Build Report
# ═══════════════════════════════════════════════════════════════════════

def build_quality_intelligence_report(
    provider: QualityIntelligenceProvider,
    request: QualityIntelligenceRequest,
    result: QualityIntelligenceResult,
    evidence_bundle,
    policy_status: str = "unknown",
) -> QualityIntelligenceReport:
    """Build a full quality intelligence report."""
    report = QualityIntelligenceReport(
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
class QualitySignalValidationResult:
    """Result of validating a single QualitySignal."""
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
class QualityIntelligenceValidationResult:
    """Result of validating a QualityIntelligenceResult."""
    valid: bool = True
    result_id: str = ""
    signal_results: Tuple[QualitySignalValidationResult, ...] = ()
    violations: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "result_id": self.result_id,
            "signal_results": [s.to_dict() for s in self.signal_results],
            "violations": list(self.violations),
        }


def validate_quality_signal(signal: QualitySignal) -> QualitySignalValidationResult:
    """Validate a single QualitySignal against contract rules."""
    violations = []

    if signal.truth_source is not False:
        violations.append(f"Signal {signal.signal_id}: truth_source must be False")

    if signal.signal_type not in ALL_SIGNAL_TYPES:
        violations.append(f"Signal {signal.signal_id}: unknown signal_type '{signal.signal_type}'")

    if not signal.signal_id:
        violations.append("signal_id is empty")

    if signal.quality_score < 0.0 or signal.quality_score > 1.0:
        violations.append(f"Signal {signal.signal_id}: quality_score must be 0.0-1.0, got {signal.quality_score}")

    if signal.confidence < 0.0 or signal.confidence > 1.0:
        violations.append(f"Signal {signal.signal_id}: confidence must be 0.0-1.0, got {signal.confidence}")

    if signal.severity not in ALL_SEVERITIES:
        violations.append(f"Signal {signal.signal_id}: unknown severity '{signal.severity}'")

    return QualitySignalValidationResult(
        valid=len(violations) == 0,
        signal_id=signal.signal_id,
        violations=tuple(violations),
    )


def validate_quality_intelligence_result(
    result: QualityIntelligenceResult,
) -> QualityIntelligenceValidationResult:
    """Validate a QualityIntelligenceResult against contract rules."""
    violations = []
    signal_results = []

    if result.truth_source is not False:
        violations.append(f"Result {result.request_id}: truth_source must be False")

    if not result.request_id:
        violations.append("request_id is empty")

    if result.blocked and not result.reason:
        violations.append("Blocked result must have a reason")

    for signal in result.signals:
        sv = validate_quality_signal(signal)
        signal_results.append(sv)
        if not sv.valid:
            violations.append(f"Signal {sv.signal_id}: {', '.join(sv.violations)}")

    return QualityIntelligenceValidationResult(
        valid=len(violations) == 0,
        result_id=result.request_id,
        signal_results=tuple(signal_results),
        violations=tuple(violations),
    )
