"""
Agent Worker Plane — Phase 6.

Defines contracts for external agent workers (OpenHands, SWE-agent,
AutoGen, Continue) WITHOUT integrating them. Agent workers are
external proposal generators — they may propose plans, patches, or
artifacts but cannot mutate kernel truth or execute automatically.

All proposals are EVIDENCE, never TRUTH. All real workers are
disabled/blocked by default policy.

Stdlib only. No LLM. No agent frameworks. No external execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Provider Types
# ═══════════════════════════════════════════════════════════════════════

PROVIDER_TYPE_OPENHANDS_LIKE = "openhands_like"
PROVIDER_TYPE_SWE_AGENT_LIKE = "swe_agent_like"
PROVIDER_TYPE_AUTOGEN_LIKE = "autogen_like"
PROVIDER_TYPE_CONTINUE_LIKE = "continue_like"
PROVIDER_TYPE_DETERMINISTIC_MOCK = "deterministic_mock"
PROVIDER_TYPE_GENERIC = "generic"

ALL_PROVIDER_TYPES = (
    PROVIDER_TYPE_OPENHANDS_LIKE,
    PROVIDER_TYPE_SWE_AGENT_LIKE,
    PROVIDER_TYPE_AUTOGEN_LIKE,
    PROVIDER_TYPE_CONTINUE_LIKE,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    PROVIDER_TYPE_GENERIC,
)

# ═══════════════════════════════════════════════════════════════════════
# Result Statuses
# ═══════════════════════════════════════════════════════════════════════

STATUS_PLANNED = "planned"
STATUS_BLOCKED = "blocked"
STATUS_PROPOSED = "proposed"
STATUS_FAILED = "failed"

ALL_RESULT_STATUSES = (STATUS_PLANNED, STATUS_BLOCKED, STATUS_PROPOSED, STATUS_FAILED)


# ═══════════════════════════════════════════════════════════════════════
# Agent Worker Provider
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentWorkerProvider:
    """Description of an external agent worker provider.

    This is a CONTRACT, not an integration. Providers describe what they
    require and what they can do. They do not execute within the kernel.

    truth_source is ALWAYS False. removable is ALWAYS True.
    """
    provider_id: str = ""
    name: str = ""
    provider_type: str = PROVIDER_TYPE_GENERIC
    capability_type: str = "agent"
    execution_mode: str = "inspect_only"
    requires_llm: bool = False
    requires_sandbox: bool = False
    requires_network: bool = False
    can_modify_files: bool = False
    can_execute_commands: bool = False
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
            "requires_sandbox": self.requires_sandbox,
            "requires_network": self.requires_network,
            "can_modify_files": self.can_modify_files,
            "can_execute_commands": self.can_execute_commands,
            "external_service_required": self.external_service_required,
            "truth_source": self.truth_source,
            "removable": self.removable,
            "description": self.description,
            "provider_hash": self.provider_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Agent Worker Task
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentWorkerTask:
    """A task submitted to an external agent worker.

    Describes what the worker should analyze/propose. Tasks are
    always dry_run=True by default — no execution without explicit
    human approval.
    """
    task_id: str = ""
    provider_id: str = ""
    task_summary: str = ""
    input_refs: Tuple[str, ...] = ()
    allowed_paths: Tuple[str, ...] = ()
    forbidden_paths: Tuple[str, ...] = ()
    max_runtime_seconds: int = 300
    dry_run: bool = True
    task_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "provider_id": self.provider_id,
            "task_summary": self.task_summary,
            "input_refs": list(self.input_refs),
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "max_runtime_seconds": self.max_runtime_seconds,
            "dry_run": self.dry_run,
            "task_hash": self.task_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Agent Worker Proposal
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentWorkerProposal:
    """One proposal from an agent worker.

    Proposals contain plans, suggested files (metadata only), and
    suggested commands (strings only). Nothing is executed. Nothing is
    written to disk. truth_source is ALWAYS False.
    """
    proposal_id: str = ""
    provider_id: str = ""
    task_id: str = ""
    proposed_plan: str = ""
    proposed_files: Tuple[str, ...] = ()
    proposed_commands: Tuple[str, ...] = ()
    risk_flags: Tuple[str, ...] = ()
    confidence: float = 0.0
    provenance: str = ""
    truth_source: bool = False
    proposal_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "provider_id": self.provider_id,
            "task_id": self.task_id,
            "proposed_plan": self.proposed_plan,
            "proposed_files": list(self.proposed_files),
            "proposed_commands": list(self.proposed_commands),
            "risk_flags": list(self.risk_flags),
            "confidence": self.confidence,
            "provenance": self.provenance,
            "truth_source": self.truth_source,
            "proposal_hash": self.proposal_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Agent Worker Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentWorkerResult:
    """The result of an agent worker task.

    Contains proposals, artifacts (metadata), warnings, and errors.
    May be blocked if the provider violates policy.
    truth_source is ALWAYS False.
    """
    task_id: str = ""
    provider_id: str = ""
    status: str = STATUS_PLANNED
    proposals: Tuple[AgentWorkerProposal, ...] = ()
    artifacts: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    truth_source: bool = False
    result_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "provider_id": self.provider_id,
            "status": self.status,
            "proposals": [p.to_dict() for p in self.proposals],
            "artifacts": list(self.artifacts),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "truth_source": self.truth_source,
            "result_hash": self.result_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Agent Worker Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentWorkerReport:
    """Full report combining provider, task, result, and evidence."""
    provider: Optional[AgentWorkerProvider] = None
    task: Optional[AgentWorkerTask] = None
    result: Optional[AgentWorkerResult] = None
    evidence_bundle_id: str = ""
    policy_status: str = "unknown"
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider.to_dict() if self.provider else None,
            "task": self.task.to_dict() if self.task else None,
            "result": self.result.to_dict() if self.result else None,
            "evidence_bundle_id": self.evidence_bundle_id,
            "policy_status": self.policy_status,
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Validation Results
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentWorkerValidationResult:
    """Result of validating an agent worker object."""
    valid: bool = True
    target_id: str = ""
    violations: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "target_id": self.target_id,
            "violations": list(self.violations),
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash Helpers
# ═══════════════════════════════════════════════════════════════════════

def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        for key in ("provider_hash", "task_hash", "proposal_hash",
                     "result_hash", "report_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Task Builder
# ═══════════════════════════════════════════════════════════════════════

def build_agent_worker_task(
    provider_id: str,
    task_summary: str = "",
    input_refs: Tuple[str, ...] = (),
    allowed_paths: Tuple[str, ...] = (),
    forbidden_paths: Tuple[str, ...] = (),
    max_runtime_seconds: int = 300,
    dry_run: bool = True,
) -> AgentWorkerTask:
    """Build a deterministic AgentWorkerTask.

    task_id = hash(provider_id + summary + sorted refs) — deterministic.
    dry_run is True by default — no execution without explicit approval.
    """
    id_input = f"{provider_id}:{task_summary}:{':'.join(sorted(input_refs))}"
    task_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    task = AgentWorkerTask(
        task_id=task_id,
        provider_id=provider_id,
        task_summary=task_summary,
        input_refs=input_refs,
        allowed_paths=allowed_paths,
        forbidden_paths=forbidden_paths,
        max_runtime_seconds=max_runtime_seconds,
        dry_run=dry_run,
    )
    object.__setattr__(task, "task_hash", _compute_hash(task))
    return task


# ═══════════════════════════════════════════════════════════════════════
# Blocked Result Builder
# ═══════════════════════════════════════════════════════════════════════

def make_blocked_agent_result(
    task_id: str,
    provider_id: str,
    reason: str,
) -> AgentWorkerResult:
    """Create a blocked agent worker result."""
    result = AgentWorkerResult(
        task_id=task_id,
        provider_id=provider_id,
        status=STATUS_BLOCKED,
        proposals=(),
        warnings=(reason,),
        truth_source=False,
    )
    object.__setattr__(result, "result_hash", _compute_hash(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
# Mock Agent Worker Result
# ═══════════════════════════════════════════════════════════════════════

def mock_agent_worker_result(
    task: AgentWorkerTask,
    proposal_count: int = 2,
) -> AgentWorkerResult:
    """Generate a deterministic mock agent worker result.

    Produces synthetic proposals from fixture input. No external agent
    is executed. Always deterministic — same task → same proposals.

    Proposed plans and commands are strings only; proposed files are
    metadata only. Nothing is written to disk or executed.
    """
    proposals = []
    for i in range(min(proposal_count, 5)):
        ref = task.input_refs[i] if i < len(task.input_refs) else f"ref-{i}"
        id_input = f"{task.task_id}:{ref}:proposal:{i}"
        proposal_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

        proposal = AgentWorkerProposal(
            proposal_id=proposal_id,
            provider_id=task.provider_id,
            task_id=task.task_id,
            proposed_plan=f"Mock proposal {i + 1}: analyze {ref} and suggest improvements",
            proposed_files=tuple(
                f for f in (f"{ref}.patch", f"{ref}.review.md") if task.allowed_paths == ()
                or any(f.startswith(ap.rstrip("/")) for ap in task.allowed_paths)
            ) if i == 0 else (f"{ref}.report.md",),
            proposed_commands=(
                f"git diff {ref}",
                f"ruff check {ref}" if i == 0 else "",
            ) if i == 0 else (),
            risk_flags=("mock",),
            confidence=0.6 + (i * 0.15),
            provenance=f"mock:{task.provider_id}:{task.task_id}",
            truth_source=False,
        )
        object.__setattr__(proposal, "proposal_hash", _compute_hash(proposal))
        proposals.append(proposal)

    result = AgentWorkerResult(
        task_id=task.task_id,
        provider_id=task.provider_id,
        status=STATUS_PROPOSED,
        proposals=tuple(proposals),
        artifacts=("mock_artifact_1.txt",),
        warnings=(),
        errors=(),
        truth_source=False,
    )
    object.__setattr__(result, "result_hash", _compute_hash(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════

def validate_agent_worker_provider(
    provider: AgentWorkerProvider,
) -> AgentWorkerValidationResult:
    """Validate a provider against contract rules."""
    violations = []
    if provider.truth_source is not False:
        violations.append(f"Provider {provider.provider_id}: truth_source must be False")
    if provider.removable is not True:
        violations.append(f"Provider {provider.provider_id}: removable must be True")
    if provider.provider_type not in ALL_PROVIDER_TYPES:
        violations.append(f"Unknown provider_type: {provider.provider_type}")
    if not provider.provider_id:
        violations.append("provider_id is empty")
    return AgentWorkerValidationResult(
        valid=len(violations) == 0,
        target_id=provider.provider_id,
        violations=tuple(violations),
    )


def validate_agent_worker_task(
    task: AgentWorkerTask,
) -> AgentWorkerValidationResult:
    """Validate a task against contract rules."""
    violations = []
    if not task.task_id:
        violations.append("task_id is empty")
    if not task.provider_id:
        violations.append("provider_id is empty")
    if not task.dry_run:
        violations.append("dry_run must be True by default")
    return AgentWorkerValidationResult(
        valid=len(violations) == 0,
        target_id=task.task_id,
        violations=tuple(violations),
    )


def validate_agent_worker_result(
    result: AgentWorkerResult,
) -> AgentWorkerValidationResult:
    """Validate a result against contract rules."""
    violations = []
    if result.truth_source is not False:
        violations.append(f"Result {result.task_id}: truth_source must be False")
    if result.status not in ALL_RESULT_STATUSES:
        violations.append(f"Unknown status: {result.status}")
    if result.status == STATUS_BLOCKED and not result.warnings:
        violations.append("Blocked result must have warnings")
    for p in result.proposals:
        if p.truth_source is not False:
            violations.append(f"Proposal {p.proposal_id}: truth_source must be False")
    return AgentWorkerValidationResult(
        valid=len(violations) == 0,
        target_id=result.task_id,
        violations=tuple(violations),
    )


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping
# ═══════════════════════════════════════════════════════════════════════

def agent_proposals_to_evidence(
    result: AgentWorkerResult,
    registry_hash: str = "",
    adapter_spec_hash: str = "",
):
    """Convert agent worker proposals into an EvidenceBundle.

    Each proposal becomes one EvidenceRecord. All records have
    truth_source=False.
    """
    from v3.external.evidence import (
        EVIDENCE_TYPE_AGENT_RESULT,
        TRUST_LOW,
        make_evidence_record,
        build_evidence_bundle,
    )

    records = []
    for proposal in result.proposals:
        record = make_evidence_record(
            adapter_id=result.provider_id,
            evidence_type=EVIDENCE_TYPE_AGENT_RESULT,
            capability_type="agent",
            input_data={
                "task_id": proposal.task_id,
                "proposal_id": proposal.proposal_id,
            },
            output_data={
                "proposed_plan": proposal.proposed_plan,
                "proposed_files": list(proposal.proposed_files),
                "proposed_commands": list(proposal.proposed_commands),
                "confidence": proposal.confidence,
            },
            payload_summary=f"agent proposal: {proposal.proposed_plan[:80]}",
            payload_ref="",
            source_uri=f"provider://{result.provider_id}",
            collected_by="systemkernel",
            collection_mode="inspect_only",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            risk_flags=proposal.risk_flags,
            confidence=proposal.confidence,
            source_trust_level=TRUST_LOW,
        )
        records.append(record)

    if not records:
        empty_record = make_evidence_record(
            adapter_id=result.provider_id,
            evidence_type=EVIDENCE_TYPE_AGENT_RESULT,
            capability_type="agent",
            input_data={"task_id": result.task_id},
            output_data={"status": result.status, "warnings": list(result.warnings)},
            payload_summary=f"agent result: {result.status} (no proposals)",
            payload_ref="",
            source_uri=f"provider://{result.provider_id}",
            collected_by="systemkernel",
            collection_mode="inspect_only",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            source_trust_level=TRUST_LOW,
        )
        records.append(empty_record)

    return build_evidence_bundle(tuple(records), bundle_type="agent_worker")


# ═══════════════════════════════════════════════════════════════════════
# Report Builder
# ═══════════════════════════════════════════════════════════════════════

def build_agent_worker_report(
    provider: AgentWorkerProvider,
    task: AgentWorkerTask,
    result: AgentWorkerResult,
    evidence_bundle,
    policy_status: str = "unknown",
) -> AgentWorkerReport:
    """Build a full agent worker report."""
    report = AgentWorkerReport(
        provider=provider,
        task=task,
        result=result,
        evidence_bundle_id=evidence_bundle.bundle_id if hasattr(evidence_bundle, "bundle_id") else "",
        policy_status=policy_status,
    )
    object.__setattr__(report, "report_hash", _compute_hash(report))
    return report
