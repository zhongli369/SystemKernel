"""
Memory Intelligence Plane — Phase 5.

Defines contracts for external memory intelligence providers (mem0,
Graphiti, Letta) WITHOUT integrating them. Providers are described as
profiles, signals are evidence suggestions only, and no provider may
mutate kernel memory directly.

The existing deterministic Memory Runtime (v3/memory/) is UNCHANGED.
Memory Intelligence is an outer layer that provides evidence about
memory — never truth, never direct mutation.

Stdlib only. No LLM. No vector DB. No graph DB. No external services.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Provider Types
# ═══════════════════════════════════════════════════════════════════════

PROVIDER_TYPE_MEM0_LIKE = "mem0_like"
PROVIDER_TYPE_GRAPHITI_LIKE = "graphiti_like"
PROVIDER_TYPE_LETTA_LIKE = "letta_like"
PROVIDER_TYPE_DETERMINISTIC_MOCK = "deterministic_mock"
PROVIDER_TYPE_GENERIC = "generic"

ALL_PROVIDER_TYPES = (
    PROVIDER_TYPE_MEM0_LIKE,
    PROVIDER_TYPE_GRAPHITI_LIKE,
    PROVIDER_TYPE_LETTA_LIKE,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    PROVIDER_TYPE_GENERIC,
)

# ═══════════════════════════════════════════════════════════════════════
# Signal Types
# ═══════════════════════════════════════════════════════════════════════

SIGNAL_TYPE_ADD = "add"
SIGNAL_TYPE_UPDATE = "update"
SIGNAL_TYPE_DELETE = "delete"
SIGNAL_TYPE_NOOP = "noop"
SIGNAL_TYPE_TEMPORAL_FACT = "temporal_fact"
SIGNAL_TYPE_ENTITY_LINK = "entity_link"
SIGNAL_TYPE_RETRIEVAL_HINT = "retrieval_hint"

ALL_SIGNAL_TYPES = (
    SIGNAL_TYPE_ADD,
    SIGNAL_TYPE_UPDATE,
    SIGNAL_TYPE_DELETE,
    SIGNAL_TYPE_NOOP,
    SIGNAL_TYPE_TEMPORAL_FACT,
    SIGNAL_TYPE_ENTITY_LINK,
    SIGNAL_TYPE_RETRIEVAL_HINT,
)

# Signal types that are suggestions only — never automatic mutations
SUGGESTION_ONLY_SIGNAL_TYPES: Tuple[str, ...] = (
    SIGNAL_TYPE_DELETE,
    SIGNAL_TYPE_UPDATE,
)

# ═══════════════════════════════════════════════════════════════════════
# Request Modes
# ═══════════════════════════════════════════════════════════════════════

MODE_INSPECT_ONLY = "inspect_only"
MODE_DRY_RUN = "dry_run"
MODE_EXTERNAL_SERVICE = "external_service"

ALL_REQUEST_MODES = (MODE_INSPECT_ONLY, MODE_DRY_RUN, MODE_EXTERNAL_SERVICE)


# ═══════════════════════════════════════════════════════════════════════
# Memory Intelligence Provider
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryIntelligenceProvider:
    """Description of an external memory intelligence provider.

    This is a CONTRACT, not an integration. Providers describe what they
    require and what they offer. They do not execute within the kernel.

    truth_source is ALWAYS False. removable is ALWAYS True.
    """
    provider_id: str = ""
    name: str = ""
    provider_type: str = PROVIDER_TYPE_GENERIC
    capability_type: str = "memory"
    execution_mode: str = MODE_INSPECT_ONLY
    requires_llm: bool = False
    requires_vector_db: bool = False
    requires_graph_db: bool = False
    external_service_required: bool = False
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
            "requires_vector_db": self.requires_vector_db,
            "requires_graph_db": self.requires_graph_db,
            "external_service_required": self.external_service_required,
            "truth_source": self.truth_source,
            "removable": self.removable,
            "description": self.description,
            "provider_hash": self.provider_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Memory Signal
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemorySignal:
    """One memory intelligence signal — a suggestion, never a mutation.

    Signals are EVIDENCE that a provider recommends a memory operation.
    They do NOT directly modify kernel memory. Delete and update signals
    are suggestions only.
    """
    signal_id: str = ""
    signal_type: str = SIGNAL_TYPE_NOOP
    source_record_ids: Tuple[str, ...] = ()
    source_hashes: Tuple[str, ...] = ()
    content: str = ""
    confidence: float = 0.0
    risk_flags: Tuple[str, ...] = ()
    provenance: str = ""
    truth_source: bool = False
    signal_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "source_record_ids": list(self.source_record_ids),
            "source_hashes": list(self.source_hashes),
            "content": self.content,
            "confidence": self.confidence,
            "risk_flags": list(self.risk_flags),
            "provenance": self.provenance,
            "truth_source": self.truth_source,
            "signal_hash": self.signal_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Memory Intelligence Request
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryIntelligenceRequest:
    """A request to a memory intelligence provider.

    Describes what records/evidence to analyze and how. The request
    is itself evidence — it records intent, not outcome.
    """
    request_id: str = ""
    provider_id: str = ""
    input_record_refs: Tuple[str, ...] = ()
    input_evidence_refs: Tuple[str, ...] = ()
    mode: str = MODE_INSPECT_ONLY
    max_signals: int = 100
    request_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "provider_id": self.provider_id,
            "input_record_refs": list(self.input_record_refs),
            "input_evidence_refs": list(self.input_evidence_refs),
            "mode": self.mode,
            "max_signals": self.max_signals,
            "request_hash": self.request_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Memory Intelligence Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryIntelligenceResult:
    """The result of a memory intelligence request.

    Contains signals (suggestions) from the provider. May be blocked
    if the provider violates policy. truth_source is ALWAYS False.
    """
    request_id: str = ""
    provider_id: str = ""
    signals: Tuple[MemorySignal, ...] = ()
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


# ═══════════════════════════════════════════════════════════════════════
# Memory Intelligence Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryIntelligenceReport:
    """Full report combining provider, request, result, and evidence.

    truth_source is ALWAYS False.
    """
    provider: Optional[MemoryIntelligenceProvider] = None
    request: Optional[MemoryIntelligenceRequest] = None
    result: Optional[MemoryIntelligenceResult] = None
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
    """Deterministic SHA-256 hash for memory intelligence objects."""
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

def make_memory_signal(
    signal_type: str = SIGNAL_TYPE_NOOP,
    source_record_ids: Tuple[str, ...] = (),
    source_hashes: Tuple[str, ...] = (),
    content: str = "",
    confidence: float = 0.0,
    risk_flags: Tuple[str, ...] = (),
    provenance: str = "",
) -> MemorySignal:
    """Create a deterministic MemorySignal.

    signal_id = hash(signal_type + source_hashes + content) — deterministic.
    truth_source = ALWAYS False.
    """
    id_input = f"{signal_type}:{':'.join(sorted(source_hashes))}:{content}"
    signal_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    signal = MemorySignal(
        signal_id=signal_id,
        signal_type=signal_type,
        source_record_ids=source_record_ids,
        source_hashes=source_hashes,
        content=content,
        confidence=confidence,
        risk_flags=risk_flags,
        provenance=provenance,
        truth_source=False,
    )
    object.__setattr__(signal, "signal_hash", _compute_hash(signal))
    return signal


def build_memory_intelligence_request(
    provider_id: str,
    input_record_refs: Tuple[str, ...] = (),
    input_evidence_refs: Tuple[str, ...] = (),
    mode: str = MODE_INSPECT_ONLY,
    max_signals: int = 100,
) -> MemoryIntelligenceRequest:
    """Build a deterministic MemoryIntelligenceRequest.

    request_id = hash(provider_id + sorted record refs) — deterministic.
    """
    refs_input = f"{provider_id}:{':'.join(sorted(input_record_refs))}:{':'.join(sorted(input_evidence_refs))}"
    request_id = hashlib.sha256(refs_input.encode("utf-8")).hexdigest()[:16]

    request = MemoryIntelligenceRequest(
        request_id=request_id,
        provider_id=provider_id,
        input_record_refs=input_record_refs,
        input_evidence_refs=input_evidence_refs,
        mode=mode,
        max_signals=max_signals,
    )
    object.__setattr__(request, "request_hash", _compute_hash(request))
    return request


def make_blocked_memory_result(
    request_id: str,
    provider_id: str,
    reason: str,
) -> MemoryIntelligenceResult:
    """Create a blocked memory intelligence result.

    Used when a provider is blocked by policy. Always has blocked=True.
    """
    result = MemoryIntelligenceResult(
        request_id=request_id,
        provider_id=provider_id,
        signals=(),
        blocked=True,
        reason=reason,
        truth_source=False,
    )
    object.__setattr__(result, "result_hash", _compute_hash(result))
    return result


def mock_memory_intelligence_result(
    request: MemoryIntelligenceRequest,
    signal_count: int = 3,
) -> MemoryIntelligenceResult:
    """Generate a deterministic mock memory intelligence result.

    Produces synthetic signals from fixture input. No external service.
    Always deterministic — same request → same signals.
    """
    if signal_count > request.max_signals:
        signal_count = request.max_signals

    signals = []
    for i in range(signal_count):
        record_ref = request.input_record_refs[i] if i < len(request.input_record_refs) else f"ref-{i}"
        signal = make_memory_signal(
            signal_type=SIGNAL_TYPE_RETRIEVAL_HINT if i % 2 == 0 else SIGNAL_TYPE_ENTITY_LINK,
            source_record_ids=(record_ref,),
            source_hashes=(hashlib.sha256(record_ref.encode("utf-8")).hexdigest()[:16],),
            content=f"Mock signal {i + 1} for {record_ref}",
            confidence=0.7 + (i * 0.1),
            provenance=f"mock:{request.provider_id}:{request.request_id}",
        )
        signals.append(signal)

    result = MemoryIntelligenceResult(
        request_id=request.request_id,
        provider_id=request.provider_id,
        signals=tuple(signals),
        warnings=(),
        blocked=False,
        reason="",
        truth_source=False,
    )
    object.__setattr__(result, "result_hash", _compute_hash(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping
# ═══════════════════════════════════════════════════════════════════════

def memory_signals_to_evidence(
    result: MemoryIntelligenceResult,
    registry_hash: str = "",
    adapter_spec_hash: str = "",
):
    """Convert memory intelligence result signals into an EvidenceBundle.

    Each signal becomes one EvidenceRecord. All records have
    truth_source=False. The bundle contains only signal-based evidence.

    Returns an EvidenceBundle.
    """
    from v3.external.evidence import (
        EVIDENCE_TYPE_MEMORY_SIGNAL,
        TRUST_LOW,
        make_evidence_record,
        build_evidence_bundle,
    )

    records = []
    for signal in result.signals:
        record = make_evidence_record(
            adapter_id=result.provider_id,
            evidence_type=EVIDENCE_TYPE_MEMORY_SIGNAL,
            capability_type="memory",
            input_data={
                "signal_id": signal.signal_id,
                "signal_type": signal.signal_type,
                "source_record_ids": list(signal.source_record_ids),
            },
            output_data={
                "signal_id": signal.signal_id,
                "signal_type": signal.signal_type,
                "content": signal.content,
                "confidence": signal.confidence,
            },
            payload_summary=f"memory signal: {signal.signal_type} ({signal.signal_id[:8]})",
            payload_ref="",
            source_uri=f"provider://{result.provider_id}",
            collected_by="systemkernel",
            collection_mode=MODE_INSPECT_ONLY,
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            risk_flags=signal.risk_flags,
            confidence=signal.confidence,
            source_trust_level=TRUST_LOW,  # external memory provider
        )
        records.append(record)

    return build_evidence_bundle(tuple(records), bundle_type="memory_intelligence")


# ═══════════════════════════════════════════════════════════════════════
# Build Report
# ═══════════════════════════════════════════════════════════════════════

def build_memory_intelligence_report(
    provider: MemoryIntelligenceProvider,
    request: MemoryIntelligenceRequest,
    result: MemoryIntelligenceResult,
    evidence_bundle,
    policy_status: str = "unknown",
) -> MemoryIntelligenceReport:
    """Build a full memory intelligence report.

    Combines provider, request, result, and evidence into one report.
    """
    report = MemoryIntelligenceReport(
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
class MemorySignalValidationResult:
    """Result of validating a single MemorySignal."""
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
class MemoryIntelligenceValidationResult:
    """Result of validating a MemoryIntelligenceResult."""
    valid: bool = True
    result_id: str = ""
    signal_results: Tuple[MemorySignalValidationResult, ...] = ()
    violations: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "result_id": self.result_id,
            "signal_results": [s.to_dict() for s in self.signal_results],
            "violations": list(self.violations),
        }


def validate_memory_signal(signal: MemorySignal) -> MemorySignalValidationResult:
    """Validate a single MemorySignal against contract rules."""
    violations = []

    if signal.truth_source is not False:
        violations.append(f"Signal {signal.signal_id}: truth_source must be False")

    if signal.signal_type not in ALL_SIGNAL_TYPES:
        violations.append(f"Signal {signal.signal_id}: unknown signal_type '{signal.signal_type}'")

    if not signal.signal_id:
        violations.append("signal_id is empty")

    if signal.signal_type in SUGGESTION_ONLY_SIGNAL_TYPES:
        # Delete/update — must be treated as suggestion only
        # Valid as long as truth_source is False (already checked above)
        pass

    return MemorySignalValidationResult(
        valid=len(violations) == 0,
        signal_id=signal.signal_id,
        violations=tuple(violations),
    )


def validate_memory_intelligence_result(
    result: MemoryIntelligenceResult,
) -> MemoryIntelligenceValidationResult:
    """Validate a MemoryIntelligenceResult against contract rules."""
    violations = []
    signal_results = []

    if result.truth_source is not False:
        violations.append(f"Result {result.request_id}: truth_source must be False")

    if not result.request_id:
        violations.append("request_id is empty")

    if result.blocked and not result.reason:
        violations.append("Blocked result must have a reason")

    for signal in result.signals:
        sv = validate_memory_signal(signal)
        signal_results.append(sv)
        if not sv.valid:
            violations.append(f"Signal {sv.signal_id}: {', '.join(sv.violations)}")

    return MemoryIntelligenceValidationResult(
        valid=len(violations) == 0,
        result_id=result.request_id,
        signal_results=tuple(signal_results),
        violations=tuple(violations),
    )
