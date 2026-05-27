"""
Orchestration Policy Layer — Phase 9.

Defines a deterministic policy layer for planning which external capability
adapters may be used together. This is NOT an execution engine. This is NOT
an AI planner. It only builds policy, dry-run orchestration plans, validation,
and evidence bundle planning.

Core principle:
Orchestration decides what is allowed to be planned.
It does not execute tools, agents, or mutate kernel truth.

Stdlib only. No LLM. No external execution. No file modification.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Validation Statuses
# ═══════════════════════════════════════════════════════════════════════

STATUS_PASS = "pass"
STATUS_BLOCKED = "blocked"
STATUS_REVIEW = "review"

ALL_STATUSES = (STATUS_PASS, STATUS_BLOCKED, STATUS_REVIEW)


# ═══════════════════════════════════════════════════════════════════════
# Orchestration Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OrchestrationPolicy:
    """Policy governing which capability adapters may be planned together.

    This is a PLANNING BOUNDARY, not an execution gate. It controls what
    appears in a dry-run orchestration plan. It does not execute anything.
    """
    policy_id: str = ""
    allowed_capability_types: Tuple[str, ...] = ()
    forbidden_capability_types: Tuple[str, ...] = ()
    allowed_adapters: Tuple[str, ...] = ()
    forbidden_adapters: Tuple[str, ...] = ()
    require_human_approval: bool = True
    dry_run_only: bool = True
    max_adapters_per_plan: int = 10
    max_risk_level: str = "low"
    allow_external_execution: bool = False
    allow_file_modification: bool = False
    allow_network: bool = False
    allow_registry_updates: bool = False
    allow_memory_mutation: bool = False
    policy_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "allowed_capability_types": list(self.allowed_capability_types),
            "forbidden_capability_types": list(self.forbidden_capability_types),
            "allowed_adapters": list(self.allowed_adapters),
            "forbidden_adapters": list(self.forbidden_adapters),
            "require_human_approval": self.require_human_approval,
            "dry_run_only": self.dry_run_only,
            "max_adapters_per_plan": self.max_adapters_per_plan,
            "max_risk_level": self.max_risk_level,
            "allow_external_execution": self.allow_external_execution,
            "allow_file_modification": self.allow_file_modification,
            "allow_network": self.allow_network,
            "allow_registry_updates": self.allow_registry_updates,
            "allow_memory_mutation": self.allow_memory_mutation,
            "policy_hash": self.policy_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Orchestration Request
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OrchestrationRequest:
    """A dry-run request to plan capability adapter orchestration.

    Describes what capabilities are needed and what constraints apply.
    dry_run is ALWAYS True — no execution happens.
    """
    request_id: str = ""
    objective: str = ""
    requested_capability_types: Tuple[str, ...] = ()
    input_refs: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()
    dry_run: bool = True
    request_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "objective": self.objective,
            "requested_capability_types": list(self.requested_capability_types),
            "input_refs": list(self.input_refs),
            "constraints": list(self.constraints),
            "dry_run": self.dry_run,
            "request_hash": self.request_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Orchestration Step
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OrchestrationStep:
    """One planned step in an orchestration plan.

    Maps one adapter to one capability type. Steps are METADATA only —
    they describe what COULD be done, not what IS done.

    Blocked steps are retained in the plan, not silently removed.
    """
    step_id: str = ""
    adapter_id: str = ""
    capability_type: str = ""
    execution_mode: str = "dry_run"
    reason: str = ""
    expected_evidence_type: str = ""
    approval_required: bool = True
    blocked: bool = False
    block_reason: str = ""
    step_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "adapter_id": self.adapter_id,
            "capability_type": self.capability_type,
            "execution_mode": self.execution_mode,
            "reason": self.reason,
            "expected_evidence_type": self.expected_evidence_type,
            "approval_required": self.approval_required,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "step_hash": self.step_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Orchestration Plan
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OrchestrationPlan:
    """A deterministic dry-run orchestration plan.

    Contains ordered steps and blocked steps. Steps are sorted
    deterministically by (capability_type, adapter_id).

    truth_source is ALWAYS False. This is a PLAN, not a record of
    what happened.
    """
    plan_id: str = ""
    request: Optional[OrchestrationRequest] = None
    steps: Tuple[OrchestrationStep, ...] = ()
    blocked_steps: Tuple[OrchestrationStep, ...] = ()
    warnings: Tuple[str, ...] = ()
    truth_source: bool = False
    plan_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "request": self.request.to_dict() if self.request else None,
            "steps": [s.to_dict() for s in self.steps],
            "blocked_steps": [s.to_dict() for s in self.blocked_steps],
            "warnings": list(self.warnings),
            "truth_source": self.truth_source,
            "plan_hash": self.plan_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Orchestration Policy Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OrchestrationPolicyReport:
    """Full report combining policy, request, plan, and validation."""
    policy: Optional[OrchestrationPolicy] = None
    request: Optional[OrchestrationRequest] = None
    plan: Optional[OrchestrationPlan] = None
    registry_hash: str = ""
    validation_status: str = STATUS_REVIEW
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "policy": self.policy.to_dict() if self.policy else None,
            "request": self.request.to_dict() if self.request else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "registry_hash": self.registry_hash,
            "validation_status": self.validation_status,
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Validation Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OrchestrationValidationResult:
    """Result of validating an orchestration object."""
    valid: bool = True
    target_id: str = ""
    violations: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "target_id": self.target_id,
            "violations": list(self.violations),
            "warnings": list(self.warnings),
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash Helpers
# ═══════════════════════════════════════════════════════════════════════

def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        for key in ("policy_hash", "request_hash", "step_hash",
                     "plan_hash", "report_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Default Policy
# ═══════════════════════════════════════════════════════════════════════

def default_orchestration_policy() -> OrchestrationPolicy:
    """Return the default orchestration policy.

    Max conservative: dry_run_only=True, no execution, no file mod,
    no network, no registry updates, no memory mutation.
    Only low risk adapters allowed by default.
    """
    policy = OrchestrationPolicy(
        policy_id="default_orchestration",
        allowed_capability_types=(),
        forbidden_capability_types=(),
        allowed_adapters=(),
        forbidden_adapters=(),
        require_human_approval=True,
        dry_run_only=True,
        max_adapters_per_plan=10,
        max_risk_level="low",
        allow_external_execution=False,
        allow_file_modification=False,
        allow_network=False,
        allow_registry_updates=False,
        allow_memory_mutation=False,
    )

    policy_hash = hashlib.sha256(
        json.dumps(policy.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    object.__setattr__(policy, "policy_hash", policy_hash)
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Request Builder
# ═══════════════════════════════════════════════════════════════════════

def build_orchestration_request(
    objective: str = "",
    requested_capability_types: Tuple[str, ...] = (),
    input_refs: Tuple[str, ...] = (),
    constraints: Tuple[str, ...] = (),
) -> OrchestrationRequest:
    """Build a deterministic OrchestrationRequest.

    request_id = hash(objective + sorted types + sorted refs) — deterministic.
    dry_run is ALWAYS True.
    """
    id_input = f"{objective}:{':'.join(sorted(requested_capability_types))}:{':'.join(sorted(input_refs))}"
    request_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    request = OrchestrationRequest(
        request_id=request_id,
        objective=objective,
        requested_capability_types=requested_capability_types,
        input_refs=input_refs,
        constraints=constraints,
        dry_run=True,
    )
    object.__setattr__(request, "request_hash", _compute_hash(request))
    return request


# ═══════════════════════════════════════════════════════════════════════
# Step Planning
# ═══════════════════════════════════════════════════════════════════════

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_EVIDENCE_TYPE_MAP = {
    "context": "context_pack",
    "memory": "memory_signal",
    "agent": "agent_result",
    "ide": "ide_context",
    "skill": "skill_reference",
    "eval": "eval_result",
    "usage": "usage_report",
    "tool": "generic",
}


def _make_step(
    adapter_id: str,
    capability_type: str,
    execution_mode: str = "dry_run",
    reason: str = "",
    approval_required: bool = True,
    blocked: bool = False,
    block_reason: str = "",
) -> OrchestrationStep:
    """Build a deterministic OrchestrationStep."""
    id_input = f"{adapter_id}:{capability_type}:{execution_mode}"
    step_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    expected_evidence_type = _EVIDENCE_TYPE_MAP.get(capability_type, "generic")

    step = OrchestrationStep(
        step_id=step_id,
        adapter_id=adapter_id,
        capability_type=capability_type,
        execution_mode=execution_mode,
        reason=reason,
        expected_evidence_type=expected_evidence_type,
        approval_required=approval_required,
        blocked=blocked,
        block_reason=block_reason,
    )
    object.__setattr__(step, "step_hash", _compute_hash(step))
    return step


# ═══════════════════════════════════════════════════════════════════════
# Orchestration Planner
# ═══════════════════════════════════════════════════════════════════════

def plan_orchestration(
    request: OrchestrationRequest,
    registry,
    policy: OrchestrationPolicy,
) -> OrchestrationPlan:
    """Build a deterministic dry-run orchestration plan.

    This is the core planning function. It:
    1. Finds all matching capability adapters in the registry
    2. Checks each against the policy
    3. Sorts steps deterministically by (capability_type, adapter_id)
    4. Retains blocked steps (never silently removed)
    5. Returns a plan with hash — NO EXECUTION

    The registry parameter must have an `entries` attribute that is an
    iterable of CapabilityRegistryEntry-like objects with `.adapter_id`,
    `.enabled`, and `.spec` (with `.capability_type`, `.risk_level`).
    """
    plan_id = hashlib.sha256(
        f"{request.request_id}:{policy.policy_id}".encode("utf-8")
    ).hexdigest()[:16]

    steps = []
    blocked_steps = []
    warnings = []

    requested_types = set(request.requested_capability_types)
    allowed_types = set(policy.allowed_capability_types) if policy.allowed_capability_types else requested_types
    forbidden_types = set(policy.forbidden_capability_types)
    allowed_adapters = set(policy.allowed_adapters)
    forbidden_adapters = set(policy.forbidden_adapters)
    max_risk = _RISK_ORDER.get(policy.max_risk_level, 0)

    candidate_adapters = []
    for entry in registry.entries:
        if not entry.spec:
            continue
        ct = entry.spec.capability_type
        if requested_types and ct not in requested_types:
            continue
        candidate_adapters.append(entry)

    # Sort deterministically
    candidate_adapters.sort(key=lambda e: (e.spec.capability_type, e.adapter_id))

    for entry in candidate_adapters:
        ct = entry.spec.capability_type
        adapter_id = entry.adapter_id
        risk = entry.spec.risk_level
        risk_order = _RISK_ORDER.get(risk, 0)

        block_reasons = []

        # Policy checks
        if allowed_types and ct not in allowed_types:
            block_reasons.append(f"Capability type '{ct}' not in allowed_capability_types")
        if ct in forbidden_types:
            block_reasons.append(f"Capability type '{ct}' is in forbidden_capability_types")
        if allowed_adapters and adapter_id not in allowed_adapters:
            block_reasons.append(f"Adapter '{adapter_id}' not in allowed_adapters")
        if adapter_id in forbidden_adapters:
            block_reasons.append(f"Adapter '{adapter_id}' is in forbidden_adapters")
        if risk_order > max_risk:
            block_reasons.append(
                f"Risk level '{risk}' exceeds max_risk_level '{policy.max_risk_level}'"
            )
        if not entry.enabled:
            block_reasons.append(f"Adapter '{adapter_id}' is disabled in registry")

        execution_mode = "dry_run"
        if policy.dry_run_only:
            execution_mode = "dry_run"

        if block_reasons:
            step = _make_step(
                adapter_id=adapter_id,
                capability_type=ct,
                execution_mode=execution_mode,
                reason=f"Blocked: {'; '.join(block_reasons)}",
                approval_required=policy.require_human_approval,
                blocked=True,
                block_reason="; ".join(block_reasons),
            )
            blocked_steps.append(step)
            warnings.append(f"Blocked: {adapter_id} — {'; '.join(block_reasons)}")
        else:
            step = _make_step(
                adapter_id=adapter_id,
                capability_type=ct,
                execution_mode=execution_mode,
                reason=f"Planned: {ct} via {adapter_id}",
                approval_required=policy.require_human_approval,
                blocked=False,
            )
            steps.append(step)

    # Enforce max_adapters_per_plan
    if len(steps) > policy.max_adapters_per_plan:
        overflow = steps[policy.max_adapters_per_plan:]
        steps = steps[:policy.max_adapters_per_plan]
        for s in overflow:
            blocked_s = _make_step(
                adapter_id=s.adapter_id,
                capability_type=s.capability_type,
                execution_mode="dry_run",
                reason=f"Exceeds max_adapters_per_plan ({policy.max_adapters_per_plan})",
                approval_required=True,
                blocked=True,
                block_reason=f"Exceeds max_adapters_per_plan ({policy.max_adapters_per_plan})",
            )
            blocked_steps.append(blocked_s)
            warnings.append(f"Overflow: {s.adapter_id} exceeds max_adapters_per_plan")

    plan = OrchestrationPlan(
        plan_id=plan_id,
        request=request,
        steps=tuple(steps),
        blocked_steps=tuple(blocked_steps),
        warnings=tuple(warnings),
        truth_source=False,
    )
    object.__setattr__(plan, "plan_hash", _compute_hash(plan))
    return plan


# ═══════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════

def validate_orchestration_step(
    step: OrchestrationStep,
    registry,
    policy: OrchestrationPolicy,
) -> OrchestrationValidationResult:
    """Validate a single orchestration step."""
    violations = []
    warn = []
    if not step.step_id:
        violations.append("step_id is empty")
    if not step.adapter_id:
        violations.append("adapter_id is empty")
    if step.blocked and not step.block_reason:
        violations.append("Blocked step must have block_reason")
    if step.blocked:
        warn.append(f"Step {step.step_id} is blocked: {step.block_reason}")
    return OrchestrationValidationResult(
        valid=len(violations) == 0,
        target_id=step.step_id,
        violations=tuple(violations),
        warnings=tuple(warn),
    )


def validate_orchestration_plan(
    plan: OrchestrationPlan,
    registry,
    policy: OrchestrationPolicy,
) -> OrchestrationValidationResult:
    """Validate a full orchestration plan."""
    violations = []
    warn = list(plan.warnings)
    if plan.truth_source is not False:
        violations.append("truth_source must be False")
    if not plan.plan_id:
        violations.append("plan_id is empty")
    if not plan.request:
        violations.append("request is missing")
    if not plan.steps and not plan.blocked_steps:
        warn.append("Plan has no steps (empty plan)")
    return OrchestrationValidationResult(
        valid=len(violations) == 0,
        target_id=plan.plan_id,
        violations=tuple(violations),
        warnings=tuple(warn),
    )


# ═══════════════════════════════════════════════════════════════════════
# Report Builder
# ═══════════════════════════════════════════════════════════════════════

def build_orchestration_policy_report(
    policy: OrchestrationPolicy,
    request: OrchestrationRequest,
    plan: OrchestrationPlan,
    registry_hash: str = "",
) -> OrchestrationPolicyReport:
    """Build a full orchestration policy report."""
    validation = validate_orchestration_plan(plan, None, policy)
    status = STATUS_PASS if validation.valid else STATUS_BLOCKED
    if validation.warnings:
        status = STATUS_REVIEW

    report = OrchestrationPolicyReport(
        policy=policy,
        request=request,
        plan=plan,
        registry_hash=registry_hash,
        validation_status=status,
    )
    object.__setattr__(report, "report_hash", _compute_hash(report))
    return report


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping
# ═══════════════════════════════════════════════════════════════════════

def orchestration_plan_to_evidence(
    plan: OrchestrationPlan,
    registry_hash: str = "",
    adapter_spec_hash: str = "",
):
    """Convert an orchestration plan into an EvidenceBundle.

    Each step becomes one EvidenceRecord. All records have
    truth_source=False.
    """
    from v3.external.evidence import (
        EVIDENCE_TYPE_GENERIC,
        TRUST_LOW,
        make_evidence_record,
        build_evidence_bundle,
    )

    records = []
    all_steps = list(plan.steps) + list(plan.blocked_steps)

    for step in all_steps:
        record = make_evidence_record(
            adapter_id=step.adapter_id,
            evidence_type=EVIDENCE_TYPE_GENERIC,
            capability_type=step.capability_type,
            input_data={
                "step_id": step.step_id,
                "adapter_id": step.adapter_id,
                "capability_type": step.capability_type,
                "execution_mode": step.execution_mode,
                "blocked": step.blocked,
            },
            output_data={
                "reason": step.reason,
                "block_reason": step.block_reason,
                "approval_required": step.approval_required,
                "expected_evidence_type": step.expected_evidence_type,
            },
            payload_summary=f"orchestration step: {step.adapter_id} {'BLOCKED' if step.blocked else 'PLANNED'}",
            payload_ref="",
            source_uri=f"plan://{plan.plan_id}",
            collected_by="systemkernel",
            collection_mode="dry_run",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            risk_flags=(),
            confidence=0.5,
            source_trust_level=TRUST_LOW,
        )
        records.append(record)

    if not records:
        empty_record = make_evidence_record(
            adapter_id="orchestration",
            evidence_type=EVIDENCE_TYPE_GENERIC,
            capability_type="tool",
            input_data={"plan_id": plan.plan_id},
            output_data={"status": "empty plan"},
            payload_summary="orchestration plan: empty (no steps)",
            payload_ref="",
            source_uri=f"plan://{plan.plan_id}",
            collected_by="systemkernel",
            collection_mode="dry_run",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            source_trust_level=TRUST_LOW,
        )
        records.append(empty_record)

    return build_evidence_bundle(tuple(records), bundle_type="orchestration_plan")
