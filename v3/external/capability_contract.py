"""
Capability Adapter Contract — Phase 1.

Universal contract for all external capabilities: context tools, memory
intelligence, agent workers, IDE/workspace providers, eval tools, skill
evolution tools, and usage/cost tools.

External systems provide EVIDENCE, never TRUTH.
Adapters are BOUNDARY CONTRACTS, not runtime dependencies.
Kernel remains DETERMINISTIC and ZERO LLM.

Stdlib only. No external dependencies. No external tool execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import auto, Enum
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════

class CapabilityType(Enum):
    """Closed set of capability types. Extend by addition only."""
    context = "context"        # Context pack generators (repomix, etc.)
    memory = "memory"          # Memory/vector stores (mem0, graphiti, etc.)
    agent = "agent"            # Agent/worker executors (OpenHands, AutoGen, etc.)
    ide = "ide"                # IDE/workspace providers (Continue, etc.)
    eval = "eval"              # Evaluation/test tools
    skill = "skill"            # Skill evolution/management tools
    usage = "usage"            # Usage/cost tracking tools (ccusage, etc.)
    tool = "tool"              # Generic external tool
    direction = "direction"    # Strategic direction/intent signals (gstack, etc.)
    quality = "quality"        # Quality evaluation/critique signals (superpowers, etc.)


class CapabilityExecutionMode(Enum):
    """How a capability may be executed. Escalation path from safest."""
    dry_run = "dry_run"                # Plan only, zero side effects
    inspect_only = "inspect_only"      # Read existing output, no execution
    explicit_execute = "explicit_execute"  # Execute with explicit --allow flag
    external_service = "external_service"  # Talk to external running service
    disabled = "disabled"              # Explicitly disabled


class CapabilityRiskLevel(Enum):
    """Risk classification for a capability adapter."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ═══════════════════════════════════════════════════════════════════════
# Frozen Dataclasses — Input/Output Contracts
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityInputContract:
    """What a capability adapter accepts as input.

    Defines the boundary between external tool input and kernel data.
    All permission fields must be explicitly granted.
    """
    schema_name: str = ""
    required_fields: Tuple[str, ...] = ()
    optional_fields: Tuple[str, ...] = ()
    max_input_bytes: int = 0
    allows_filesystem_read: bool = False
    allows_filesystem_write: bool = False
    allows_network: bool = False
    requires_approval: bool = False

    def to_dict(self) -> dict:
        return {
            "schema_name": self.schema_name,
            "required_fields": list(self.required_fields),
            "optional_fields": list(self.optional_fields),
            "max_input_bytes": self.max_input_bytes,
            "allows_filesystem_read": self.allows_filesystem_read,
            "allows_filesystem_write": self.allows_filesystem_write,
            "allows_network": self.allows_network,
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class CapabilityOutputContract:
    """What a capability adapter produces as output.

    CRITICAL: truth_source is ALWAYS False. External tools produce
    evidence, never authoritative truth.
    """
    schema_name: str = ""
    output_fields: Tuple[str, ...] = ()
    max_output_bytes: int = 0
    contains_evidence: bool = True
    contains_artifacts: bool = False
    truth_source: bool = False      # MUST always be False — enforced
    provenance_required: bool = True

    def to_dict(self) -> dict:
        return {
            "schema_name": self.schema_name,
            "output_fields": list(self.output_fields),
            "max_output_bytes": self.max_output_bytes,
            "contains_evidence": self.contains_evidence,
            "contains_artifacts": self.contains_artifacts,
            "truth_source": self.truth_source,
            "provenance_required": self.provenance_required,
        }


# ═══════════════════════════════════════════════════════════════════════
# Evidence
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityEvidence:
    """Evidence produced by a capability execution.

    Evidence is NOT truth. It is a structured record of what an external
    tool produced at a specific point in time, with provenance tracking.
    """
    evidence_id: str = ""
    adapter_id: str = ""
    capability_type: str = ""
    input_hash: str = ""
    output_hash: str = ""
    provenance: str = ""            # tool, version, invocation, timestamp
    risk_flags: Tuple[str, ...] = ()
    confidence: float = 0.0
    truth_source: bool = False      # MUST always be False
    evidence_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "adapter_id": self.adapter_id,
            "capability_type": self.capability_type,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "provenance": self.provenance,
            "risk_flags": list(self.risk_flags),
            "confidence": self.confidence,
            "truth_source": self.truth_source,
            "evidence_hash": self.evidence_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Run Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityRunResult:
    """Result of a single capability execution.

    Status:
      - planned: execution planned but not yet run
      - skipped: execution skipped (safety gate, approval required)
      - blocked: execution blocked (forbidden, risk too high)
      - completed: execution completed, evidence available
      - failed: execution failed, errors available
    """
    adapter_id: str = ""
    execution_mode: str = ""
    status: str = "planned"
    evidence: Optional[CapabilityEvidence] = None
    artifacts: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    result_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "execution_mode": self.execution_mode,
            "status": self.status,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "artifacts": list(self.artifacts),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "result_hash": self.result_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Risk Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityRiskReport:
    """Risk assessment for a capability adapter.

    Used to determine whether an adapter is safe to register, trial,
    or approve. Critical-risk adapters default to disabled.
    """
    adapter_id: str = ""
    risk_level: str = CapabilityRiskLevel.medium.value
    forbidden_actions: Tuple[str, ...] = ()
    approval_required: bool = True
    dependency_risks: Tuple[str, ...] = ()
    truth_source_risk: bool = False       # True if adapter might be treated as truth
    kernel_boundary_risk: bool = False    # True if adapter touches kernel internals
    risk_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "risk_level": self.risk_level,
            "forbidden_actions": list(self.forbidden_actions),
            "approval_required": self.approval_required,
            "dependency_risks": list(self.dependency_risks),
            "truth_source_risk": self.truth_source_risk,
            "kernel_boundary_risk": self.kernel_boundary_risk,
            "risk_hash": self.risk_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Adapter Spec
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExternalCapabilityAdapterSpec:
    """Complete specification for a capability adapter.

    This is the master contract. Every external capability adapter
    MUST be described by one of these specs before it can be registered.

    Hard guarantees:
      - removable: ALWAYS True (enforced — adapters are not kernel)
      - truth_source: ALWAYS False (enforced — external is evidence only)
      - adapter_id: non-empty, deterministic
      - forbidden_actions: non-empty
    """
    adapter_id: str = ""
    name: str = ""
    capability_type: str = CapabilityType.tool.value
    execution_modes: Tuple[str, ...] = ()
    input_contract: Optional[CapabilityInputContract] = None
    output_contract: Optional[CapabilityOutputContract] = None
    allowed_actions: Tuple[str, ...] = ()
    forbidden_actions: Tuple[str, ...] = ()
    removable: bool = True
    truth_source: bool = False
    risk_level: str = CapabilityRiskLevel.medium.value
    version: str = "1.0.0"
    spec_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "name": self.name,
            "capability_type": self.capability_type,
            "execution_modes": list(self.execution_modes),
            "input_contract": self.input_contract.to_dict() if self.input_contract else None,
            "output_contract": self.output_contract.to_dict() if self.output_contract else None,
            "allowed_actions": list(self.allowed_actions),
            "forbidden_actions": list(self.forbidden_actions),
            "removable": self.removable,
            "truth_source": self.truth_source,
            "risk_level": self.risk_level,
            "version": self.version,
            "spec_hash": self.spec_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash Computation
# ═══════════════════════════════════════════════════════════════════════

def compute_stable_hash(obj, prefix: str = "") -> str:
    """Deterministic SHA-256 hash for any contract object.

    Same input → same hash. Always. Used for evidence_hash, result_hash,
    spec_hash, and risk_hash fields.

    Serializes via JSON with sorted keys to ensure determinism.
    """
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)

    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    full_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if prefix:
        return f"{prefix}:{full_hash[:16]}"
    return full_hash[:16]


# ═══════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════

def validate_adapter_spec(spec: ExternalCapabilityAdapterSpec) -> Tuple[bool, Tuple[str, ...]]:
    """Validate an adapter spec against all contract rules.

    Returns (valid, errors).
    """
    errors = []

    # adapter_id must be non-empty
    if not spec.adapter_id or not spec.adapter_id.strip():
        errors.append("adapter_id must be non-empty")

    # truth_source must always be False
    if spec.truth_source is not False:
        errors.append("truth_source must be False")

    # removable must always be True
    if spec.removable is not True:
        errors.append("removable must be True")

    # forbidden_actions must not be empty
    if not spec.forbidden_actions:
        errors.append("forbidden_actions must not be empty")

    # explicit_execute requires approval
    if "explicit_execute" in spec.execution_modes:
        if spec.input_contract and not spec.input_contract.requires_approval:
            errors.append("explicit_execute mode requires approval in input_contract")

    # Network permission requires approval
    if spec.input_contract and spec.input_contract.allows_network:
        if not spec.input_contract.requires_approval:
            errors.append("network access requires approval")

    # Filesystem write requires approval
    if spec.input_contract and spec.input_contract.allows_filesystem_write:
        if not spec.input_contract.requires_approval:
            errors.append("filesystem write requires approval")

    # Critical risk defaults to disabled
    if spec.risk_level == CapabilityRiskLevel.critical.value:
        if "disabled" not in spec.execution_modes:
            errors.append("critical risk adapter must default to disabled execution mode")

    # Output contract truth_source must be False
    if spec.output_contract and spec.output_contract.truth_source is not False:
        errors.append("output_contract.truth_source must be False")

    # Capability type must be a valid enum value
    valid_types = {t.value for t in CapabilityType}
    if spec.capability_type not in valid_types:
        errors.append(f"capability_type '{spec.capability_type}' not in {valid_types}")

    # Execution modes must be valid
    valid_modes = {m.value for m in CapabilityExecutionMode}
    for mode in spec.execution_modes:
        if mode not in valid_modes:
            errors.append(f"execution_mode '{mode}' not in {valid_modes}")

    # Risk level must be valid
    valid_risks = {r.value for r in CapabilityRiskLevel}
    if spec.risk_level not in valid_risks:
        errors.append(f"risk_level '{spec.risk_level}' not in {valid_risks}")

    return len(errors) == 0, tuple(errors)


def validate_run_result(result: CapabilityRunResult) -> Tuple[bool, Tuple[str, ...]]:
    """Validate a run result against contract rules.

    Returns (valid, errors).
    """
    errors = []

    valid_statuses = {"planned", "skipped", "blocked", "completed", "failed"}
    if result.status not in valid_statuses:
        errors.append(f"status '{result.status}' not in {valid_statuses}")

    if not result.adapter_id or not result.adapter_id.strip():
        errors.append("adapter_id must be non-empty")

    if result.evidence:
        if result.evidence.truth_source is not False:
            errors.append("evidence.truth_source must be False")

    if result.execution_mode == "explicit_execute" and result.status == "completed":
        if not result.evidence:
            errors.append("completed explicit_execute must have evidence")

    valid_modes = {m.value for m in CapabilityExecutionMode}
    if result.execution_mode not in valid_modes:
        errors.append(f"execution_mode '{result.execution_mode}' not in {valid_modes}")

    return len(errors) == 0, tuple(errors)


# ═══════════════════════════════════════════════════════════════════════
# Constructors
# ═══════════════════════════════════════════════════════════════════════

def make_evidence(
    adapter_id: str,
    capability_type: str,
    input_data: dict,
    output_data: dict,
    provenance: str = "",
    risk_flags: Tuple[str, ...] = (),
    confidence: float = 0.0,
) -> CapabilityEvidence:
    """Create a CapabilityEvidence with deterministic hashes.

    truth_source is ALWAYS False — enforced here.
    """
    input_hash = compute_stable_hash(input_data, "input")
    output_hash = compute_stable_hash(output_data, "output")

    evidence = CapabilityEvidence(
        evidence_id=f"ev-{input_hash[:8]}-{output_hash[:8]}",
        adapter_id=adapter_id,
        capability_type=capability_type,
        input_hash=input_hash,
        output_hash=output_hash,
        provenance=provenance,
        risk_flags=risk_flags,
        confidence=confidence,
        truth_source=False,  # HARD — always False
    )
    # Set evidence_hash after construction
    object.__setattr__(evidence, "evidence_hash",
                       compute_stable_hash(evidence, "evidence"))
    return evidence


def make_blocked_result(
    adapter_id: str,
    reason: str = "",
    risk_level: str = CapabilityRiskLevel.high.value,
) -> CapabilityRunResult:
    """Create a CapabilityRunResult with status='blocked'.

    Used when safety gates prevent execution.
    """
    result = CapabilityRunResult(
        adapter_id=adapter_id,
        execution_mode="disabled",
        status="blocked",
        warnings=(f"BLOCKED: {reason}" if reason else "BLOCKED: risk threshold exceeded",),
        errors=(f"Risk level {risk_level} — execution not permitted",),
    )
    object.__setattr__(result, "result_hash",
                       compute_stable_hash(result, "result"))
    return result


def make_planned_result(
    adapter_id: str,
    execution_mode: str = CapabilityExecutionMode.dry_run.value,
) -> CapabilityRunResult:
    """Create a CapabilityRunResult with status='planned'.

    Used when an execution is planned but not yet performed.
    """
    result = CapabilityRunResult(
        adapter_id=adapter_id,
        execution_mode=execution_mode,
        status="planned",
    )
    object.__setattr__(result, "result_hash",
                       compute_stable_hash(result, "result"))
    return result
