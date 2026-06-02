"""
Skill Evolution Plane — Phase 8.

Defines contracts for external skill evolution providers (Anthropic Skills,
SuperClaude, generic) WITHOUT integrating them. Skill evolution providers
may propose skill improvements, SKILL.md alignment, registry updates, or
new skill packages.

All proposals are EVIDENCE, never TRUTH. All real providers are
disabled/blocked by default policy.

Core principle: Skill evolution is proposal-only.
Any change to skills, registry, or packages requires explicit human approval
and tests. Skill evolution outputs are evidence/proposals, never truth.

Stdlib only. No LLM. No skill modification. No registry update.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Provider Types
# ═══════════════════════════════════════════════════════════════════════

PROVIDER_TYPE_ANTHROPIC_SKILLS_LIKE = "anthropic_skills_like"
PROVIDER_TYPE_SUPERCLAUDE_LIKE = "superclaude_like"
PROVIDER_TYPE_DETERMINISTIC_MOCK = "deterministic_mock"
PROVIDER_TYPE_GENERIC = "generic"

ALL_PROVIDER_TYPES = (
    PROVIDER_TYPE_ANTHROPIC_SKILLS_LIKE,
    PROVIDER_TYPE_SUPERCLAUDE_LIKE,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    PROVIDER_TYPE_GENERIC,
)


# ═══════════════════════════════════════════════════════════════════════
# Signal Types
# ═══════════════════════════════════════════════════════════════════════

SIGNAL_TYPE_MISSING_SKILL = "missing_skill"
SIGNAL_TYPE_OUTDATED_SKILL = "outdated_skill"
SIGNAL_TYPE_POOR_DESCRIPTION = "poor_description"
SIGNAL_TYPE_MISSING_TESTS = "missing_tests"
SIGNAL_TYPE_REGISTRY_MISMATCH = "registry_mismatch"
SIGNAL_TYPE_FORMAT_ALIGNMENT = "format_alignment"
SIGNAL_TYPE_DUPLICATE_SKILL = "duplicate_skill"

ALL_SIGNAL_TYPES = (
    SIGNAL_TYPE_MISSING_SKILL,
    SIGNAL_TYPE_OUTDATED_SKILL,
    SIGNAL_TYPE_POOR_DESCRIPTION,
    SIGNAL_TYPE_MISSING_TESTS,
    SIGNAL_TYPE_REGISTRY_MISMATCH,
    SIGNAL_TYPE_FORMAT_ALIGNMENT,
    SIGNAL_TYPE_DUPLICATE_SKILL,
)


# ═══════════════════════════════════════════════════════════════════════
# Proposal Types
# ═══════════════════════════════════════════════════════════════════════

PROPOSAL_TYPE_CREATE_SKILL = "create_skill"
PROPOSAL_TYPE_UPDATE_SKILL = "update_skill"
PROPOSAL_TYPE_DEPRECATE_SKILL = "deprecate_skill"
PROPOSAL_TYPE_REGISTRY_UPDATE = "registry_update"
PROPOSAL_TYPE_FORMAT_ALIGNMENT = "format_alignment"
PROPOSAL_TYPE_TEST_ADDITION = "test_addition"
PROPOSAL_TYPE_DOCS_UPDATE = "docs_update"

ALL_PROPOSAL_TYPES = (
    PROPOSAL_TYPE_CREATE_SKILL,
    PROPOSAL_TYPE_UPDATE_SKILL,
    PROPOSAL_TYPE_DEPRECATE_SKILL,
    PROPOSAL_TYPE_REGISTRY_UPDATE,
    PROPOSAL_TYPE_FORMAT_ALIGNMENT,
    PROPOSAL_TYPE_TEST_ADDITION,
    PROPOSAL_TYPE_DOCS_UPDATE,
)


# ═══════════════════════════════════════════════════════════════════════
# Result Statuses
# ═══════════════════════════════════════════════════════════════════════

STATUS_PROPOSED = "proposed"
STATUS_BLOCKED = "blocked"
STATUS_FAILED = "failed"

ALL_RESULT_STATUSES = (STATUS_PROPOSED, STATUS_BLOCKED, STATUS_FAILED)


# ═══════════════════════════════════════════════════════════════════════
# Severities
# ═══════════════════════════════════════════════════════════════════════

SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"

ALL_SEVERITIES = (SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH)


# ═══════════════════════════════════════════════════════════════════════
# Skill Evolution Provider
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillEvolutionProvider:
    """Description of an external skill evolution provider.

    This is a CONTRACT, not an integration. Providers describe what they
    require and what they can do. They do not execute within the kernel.

    truth_source is ALWAYS False. removable is ALWAYS True.
    """
    provider_id: str = ""
    name: str = ""
    provider_type: str = PROVIDER_TYPE_GENERIC
    capability_type: str = "skill"
    execution_mode: str = "inspect_only"
    requires_llm: bool = False
    can_modify_skills: bool = False
    can_update_registry: bool = False
    can_install_skills: bool = False
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
            "can_modify_skills": self.can_modify_skills,
            "can_update_registry": self.can_update_registry,
            "can_install_skills": self.can_install_skills,
            "external_service_required": self.external_service_required,
            "truth_source": self.truth_source,
            "removable": self.removable,
            "description": self.description,
            "provider_hash": self.provider_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Skill Package Ref
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillPackageRef:
    """A reference to an existing skill package.

    Contains metadata about a skill package — path, hash, frontmatter status.
    Does NOT contain or modify file contents.
    """
    skill_id: str = ""
    name: str = ""
    source_path: str = ""
    has_skill_md: bool = False
    has_frontmatter: bool = False
    metadata_hash: str = ""
    ref_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "source_path": self.source_path,
            "has_skill_md": self.has_skill_md,
            "has_frontmatter": self.has_frontmatter,
            "metadata_hash": self.metadata_hash,
            "ref_hash": self.ref_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Skill Gap Signal
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillGapSignal:
    """A detected gap or issue in the skill ecosystem.

    Signals identify problems — missing skills, outdated descriptions,
    registry mismatches, etc. They are suggestions, never commands.

    truth_source is ALWAYS False.
    """
    signal_id: str = ""
    signal_type: str = SIGNAL_TYPE_MISSING_SKILL
    source_refs: Tuple[str, ...] = ()
    description: str = ""
    severity: str = SEVERITY_LOW
    confidence: float = 0.0
    truth_source: bool = False
    signal_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "source_refs": list(self.source_refs),
            "description": self.description,
            "severity": self.severity,
            "confidence": self.confidence,
            "truth_source": self.truth_source,
            "signal_hash": self.signal_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Skill Evolution Proposal
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillEvolutionProposal:
    """One skill evolution proposal.

    Proposals describe what SHOULD change — create, update, deprecate,
    registry update, etc. They are METADATA only. No files are written.
    No registry is updated. approval_required is ALWAYS True.

    truth_source is ALWAYS False.
    """
    proposal_id: str = ""
    provider_id: str = ""
    proposal_type: str = PROPOSAL_TYPE_CREATE_SKILL
    target_skill_refs: Tuple[str, ...] = ()
    gap_signals: Tuple[str, ...] = ()
    proposed_changes_summary: str = ""
    proposed_files: Tuple[str, ...] = ()
    required_tests: Tuple[str, ...] = ()
    approval_required: bool = True
    truth_source: bool = False
    proposal_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "provider_id": self.provider_id,
            "proposal_type": self.proposal_type,
            "target_skill_refs": list(self.target_skill_refs),
            "gap_signals": list(self.gap_signals),
            "proposed_changes_summary": self.proposed_changes_summary,
            "proposed_files": list(self.proposed_files),
            "required_tests": list(self.required_tests),
            "approval_required": self.approval_required,
            "truth_source": self.truth_source,
            "proposal_hash": self.proposal_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Skill Evolution Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillEvolutionResult:
    """The result of a skill evolution analysis.

    Contains proposals, warnings, and errors. May be blocked if the
    provider violates policy. truth_source is ALWAYS False.
    """
    provider_id: str = ""
    status: str = STATUS_PROPOSED
    proposals: Tuple[SkillEvolutionProposal, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    truth_source: bool = False
    result_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "proposals": [p.to_dict() for p in self.proposals],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "truth_source": self.truth_source,
            "result_hash": self.result_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Skill Evolution Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillEvolutionReport:
    """Full report combining provider, result, evidence, and policy status."""
    provider: Optional[SkillEvolutionProvider] = None
    result: Optional[SkillEvolutionResult] = None
    evidence_bundle_id: str = ""
    policy_status: str = "unknown"
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider.to_dict() if self.provider else None,
            "result": self.result.to_dict() if self.result else None,
            "evidence_bundle_id": self.evidence_bundle_id,
            "policy_status": self.policy_status,
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Validation Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillEvolutionValidationResult:
    """Result of validating a skill evolution object."""
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
        for key in ("provider_hash", "ref_hash", "signal_hash",
                     "proposal_hash", "result_hash", "report_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Skill Package Ref Builder
# ═══════════════════════════════════════════════════════════════════════

def make_skill_package_ref(
    skill_id: str,
    name: str = "",
    source_path: str = "",
    has_skill_md: bool = False,
    has_frontmatter: bool = False,
    metadata_hash_input: str = "",
) -> SkillPackageRef:
    """Build a deterministic SkillPackageRef.

    ref_hash is computed from skill_id + source_path + metadata_hash.
    """
    meta_hash = (metadata_hash_input
                 if metadata_hash_input
                 else hashlib.sha256(f"{skill_id}:{source_path}".encode()).hexdigest()[:16])

    ref = SkillPackageRef(
        skill_id=skill_id,
        name=name,
        source_path=source_path,
        has_skill_md=has_skill_md,
        has_frontmatter=has_frontmatter,
        metadata_hash=meta_hash,
    )
    object.__setattr__(ref, "ref_hash", _compute_hash(ref))
    return ref


# ═══════════════════════════════════════════════════════════════════════
# Gap Signal Builder
# ═══════════════════════════════════════════════════════════════════════

def make_skill_gap_signal(
    signal_type: str,
    source_refs: Tuple[str, ...] = (),
    description: str = "",
    severity: str = SEVERITY_LOW,
    confidence: float = 0.0,
    seed: int = 0,
) -> SkillGapSignal:
    """Build a deterministic SkillGapSignal.

    signal_id = hash(signal_type + sorted source_refs + seed) — deterministic.
    """
    id_input = f"{signal_type}:{':'.join(sorted(source_refs))}:{seed}"
    signal_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    signal = SkillGapSignal(
        signal_id=signal_id,
        signal_type=signal_type,
        source_refs=source_refs,
        description=description,
        severity=severity,
        confidence=confidence,
        truth_source=False,
    )
    object.__setattr__(signal, "signal_hash", _compute_hash(signal))
    return signal


# ═══════════════════════════════════════════════════════════════════════
# Proposal Builder
# ═══════════════════════════════════════════════════════════════════════

def make_skill_evolution_proposal(
    provider_id: str,
    proposal_type: str,
    target_skill_refs: Tuple[str, ...] = (),
    gap_signal_ids: Tuple[str, ...] = (),
    proposed_changes_summary: str = "",
    proposed_files: Tuple[str, ...] = (),
    required_tests: Tuple[str, ...] = (),
    seed: int = 0,
) -> SkillEvolutionProposal:
    """Build a deterministic SkillEvolutionProposal.

    proposal_id = hash(provider_id + proposal_type + sorted refs + seed).
    approval_required is ALWAYS True.
    truth_source is ALWAYS False.
    """
    id_input = f"{provider_id}:{proposal_type}:{':'.join(sorted(target_skill_refs))}:{seed}"
    proposal_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    proposal = SkillEvolutionProposal(
        proposal_id=proposal_id,
        provider_id=provider_id,
        proposal_type=proposal_type,
        target_skill_refs=target_skill_refs,
        gap_signals=gap_signal_ids,
        proposed_changes_summary=proposed_changes_summary,
        proposed_files=proposed_files,
        required_tests=required_tests,
        approval_required=True,
        truth_source=False,
    )
    object.__setattr__(proposal, "proposal_hash", _compute_hash(proposal))
    return proposal


# ═══════════════════════════════════════════════════════════════════════
# Blocked Result Builder
# ═══════════════════════════════════════════════════════════════════════

def make_blocked_skill_result(
    provider_id: str,
    reason: str,
) -> SkillEvolutionResult:
    """Create a blocked skill evolution result."""
    result = SkillEvolutionResult(
        provider_id=provider_id,
        status=STATUS_BLOCKED,
        proposals=(),
        warnings=(reason,),
        truth_source=False,
    )
    object.__setattr__(result, "result_hash", _compute_hash(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
# Mock Skill Evolution Result
# ═══════════════════════════════════════════════════════════════════════

def mock_skill_evolution_result(
    provider_id: str = "deterministic_mock_skill_evolution",
    proposal_count: int = 2,
    signal_count: int = 3,
) -> SkillEvolutionResult:
    """Generate a deterministic mock skill evolution result.

    Produces synthetic proposals and gap signals from fixture input.
    No external provider is executed. Always deterministic — same
    provider_id + counts → same result.

    Proposed files are metadata only. Nothing is written to disk.
    No skills are modified. No registry is updated.
    """
    signal_types_cycle = [
        SIGNAL_TYPE_MISSING_SKILL,
        SIGNAL_TYPE_OUTDATED_SKILL,
        SIGNAL_TYPE_POOR_DESCRIPTION,
        SIGNAL_TYPE_MISSING_TESTS,
        SIGNAL_TYPE_REGISTRY_MISMATCH,
        SIGNAL_TYPE_FORMAT_ALIGNMENT,
        SIGNAL_TYPE_DUPLICATE_SKILL,
    ]

    signals = []
    for i in range(min(signal_count, 10)):
        st = signal_types_cycle[i % len(signal_types_cycle)]
        refs = (f"skill-ref-{i}", f"registry-entry-{i}")
        signal = make_skill_gap_signal(
            signal_type=st,
            source_refs=refs,
            description=f"Mock gap signal {i + 1}: {st}",
            severity=SEVERITY_LOW if i % 2 == 0 else SEVERITY_MEDIUM,
            confidence=0.5 + (i * 0.1),
            seed=i,
        )
        signals.append(signal)

    proposal_types_cycle = [
        PROPOSAL_TYPE_CREATE_SKILL,
        PROPOSAL_TYPE_UPDATE_SKILL,
        PROPOSAL_TYPE_DEPRECATE_SKILL,
        PROPOSAL_TYPE_REGISTRY_UPDATE,
        PROPOSAL_TYPE_FORMAT_ALIGNMENT,
        PROPOSAL_TYPE_TEST_ADDITION,
        PROPOSAL_TYPE_DOCS_UPDATE,
    ]

    proposals = []
    for i in range(min(proposal_count, 7)):
        pt = proposal_types_cycle[i % len(proposal_types_cycle)]
        target_refs = (f"skill-{i}", f"package-{i}")
        gap_ids = tuple(s.signal_id for s in signals[i:i + 1]) if signals else ()
        proposed_files = (
            f"SkillsManagementSystem/packages/skill-{i}/SKILL.md",
            f"v3/tests/test_skill_{i}.py",
        )
        proposal = make_skill_evolution_proposal(
            provider_id=provider_id,
            proposal_type=pt,
            target_skill_refs=target_refs,
            gap_signal_ids=gap_ids,
            proposed_changes_summary=f"Mock proposal {i + 1}: {pt} for skill-{i}",
            proposed_files=proposed_files,
            required_tests=(f"test_skill_{i}_proposal.py",),
            seed=i,
        )
        proposals.append(proposal)

    result = SkillEvolutionResult(
        provider_id=provider_id,
        status=STATUS_PROPOSED,
        proposals=tuple(proposals),
        warnings=(),
        errors=(),
        truth_source=False,
    )
    object.__setattr__(result, "result_hash", _compute_hash(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════

def validate_skill_provider(
    provider: SkillEvolutionProvider,
) -> SkillEvolutionValidationResult:
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
    if provider.can_modify_skills:
        violations.append(f"Provider {provider.provider_id}: can_modify_skills must be False")
    if provider.can_update_registry:
        violations.append(f"Provider {provider.provider_id}: can_update_registry must be False")
    if provider.can_install_skills:
        violations.append(f"Provider {provider.provider_id}: can_install_skills must be False")
    if provider.requires_llm:
        violations.append(f"Provider {provider.provider_id}: requires_llm must be False")
    return SkillEvolutionValidationResult(
        valid=len(violations) == 0,
        target_id=provider.provider_id,
        violations=tuple(violations),
    )


def validate_skill_proposal(
    proposal: SkillEvolutionProposal,
) -> SkillEvolutionValidationResult:
    """Validate a proposal against contract rules."""
    violations = []
    if proposal.truth_source is not False:
        violations.append(f"Proposal {proposal.proposal_id}: truth_source must be False")
    if proposal.approval_required is not True:
        violations.append(f"Proposal {proposal.proposal_id}: approval_required must be True")
    if proposal.proposal_type not in ALL_PROPOSAL_TYPES:
        violations.append(f"Unknown proposal_type: {proposal.proposal_type}")
    if not proposal.proposal_id:
        violations.append("proposal_id is empty")
    if not proposal.provider_id:
        violations.append("provider_id is empty")
    return SkillEvolutionValidationResult(
        valid=len(violations) == 0,
        target_id=proposal.proposal_id,
        violations=tuple(violations),
    )


def validate_skill_result(
    result: SkillEvolutionResult,
) -> SkillEvolutionValidationResult:
    """Validate a result against contract rules."""
    violations = []
    if result.truth_source is not False:
        violations.append(f"Result {result.provider_id}: truth_source must be False")
    if result.status not in ALL_RESULT_STATUSES:
        violations.append(f"Unknown status: {result.status}")
    if result.status == STATUS_BLOCKED and not result.warnings:
        violations.append("Blocked result must have warnings")
    for p in result.proposals:
        if p.truth_source is not False:
            violations.append(f"Proposal {p.proposal_id}: truth_source must be False")
        if p.approval_required is not True:
            violations.append(f"Proposal {p.proposal_id}: approval_required must be True")
    return SkillEvolutionValidationResult(
        valid=len(violations) == 0,
        target_id=result.provider_id,
        violations=tuple(violations),
    )


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping
# ═══════════════════════════════════════════════════════════════════════

def skill_proposals_to_evidence(
    result: SkillEvolutionResult,
    registry_hash: str = "",
    adapter_spec_hash: str = "",
):
    """Convert skill evolution proposals into an EvidenceBundle.

    Each proposal becomes one EvidenceRecord. All records have
    truth_source=False.
    """
    from v3.external.evidence import (
        EVIDENCE_TYPE_SKILL_REFERENCE,
        TRUST_LOW,
        make_evidence_record,
        build_evidence_bundle,
    )

    records = []
    for proposal in result.proposals:
        record = make_evidence_record(
            adapter_id=result.provider_id,
            evidence_type=EVIDENCE_TYPE_SKILL_REFERENCE,
            capability_type="skill",
            input_data={
                "proposal_id": proposal.proposal_id,
                "provider_id": proposal.provider_id,
                "target_skill_refs": list(proposal.target_skill_refs),
                "gap_signals": list(proposal.gap_signals),
            },
            output_data={
                "proposal_type": proposal.proposal_type,
                "proposed_changes_summary": proposal.proposed_changes_summary,
                "proposed_files": list(proposal.proposed_files),
                "required_tests": list(proposal.required_tests),
                "approval_required": proposal.approval_required,
            },
            payload_summary=f"skill evolution proposal: {proposal.proposed_changes_summary[:80]}",
            payload_ref="",
            source_uri=f"provider://{result.provider_id}",
            collected_by="systemkernel",
            collection_mode="inspect_only",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            risk_flags=(),
            confidence=0.5,
            source_trust_level=TRUST_LOW,
        )
        records.append(record)

    if not records:
        empty_record = make_evidence_record(
            adapter_id=result.provider_id,
            evidence_type=EVIDENCE_TYPE_SKILL_REFERENCE,
            capability_type="skill",
            input_data={"provider_id": result.provider_id},
            output_data={"status": result.status, "warnings": list(result.warnings)},
            payload_summary=f"skill evolution result: {result.status} (no proposals)",
            payload_ref="",
            source_uri=f"provider://{result.provider_id}",
            collected_by="systemkernel",
            collection_mode="inspect_only",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            source_trust_level=TRUST_LOW,
        )
        records.append(empty_record)

    return build_evidence_bundle(tuple(records), bundle_type="skill_evolution")


# ═══════════════════════════════════════════════════════════════════════
# Report Builder
# ═══════════════════════════════════════════════════════════════════════

def build_skill_evolution_report(
    provider: SkillEvolutionProvider,
    result: SkillEvolutionResult,
    evidence_bundle,
    policy_status: str = "unknown",
) -> SkillEvolutionReport:
    """Build a full skill evolution report."""
    report = SkillEvolutionReport(
        provider=provider,
        result=result,
        evidence_bundle_id=evidence_bundle.bundle_id if hasattr(evidence_bundle, "bundle_id") else "",
        policy_status=policy_status,
    )
    object.__setattr__(report, "report_hash", _compute_hash(report))
    return report


# ═══════════════════════════════════════════════════════════════════════
# Agent Debugger — Failure Trace Analysis (Phase 16c)
# ═══════════════════════════════════════════════════════════════════════

# Root cause constants
ROOT_CAUSE_TOOL_TIMEOUT = "tool_timeout"
ROOT_CAUSE_BUDGET_EXCEEDED = "budget_exceeded"
ROOT_CAUSE_CHECKPOINT_CORRUPTION = "checkpoint_corruption"
ROOT_CAUSE_RETRY_EXHAUSTED = "retry_exhausted"
ROOT_CAUSE_UNKNOWN = "unknown"

ALL_ROOT_CAUSES = (
    ROOT_CAUSE_TOOL_TIMEOUT,
    ROOT_CAUSE_BUDGET_EXCEEDED,
    ROOT_CAUSE_CHECKPOINT_CORRUPTION,
    ROOT_CAUSE_RETRY_EXHAUSTED,
    ROOT_CAUSE_UNKNOWN,
)

# Root cause → affected component (ETCLOVG single-component mapping)
ROOT_CAUSE_COMPONENT = {
    ROOT_CAUSE_TOOL_TIMEOUT: "timeout",
    ROOT_CAUSE_BUDGET_EXCEEDED: "context_budget",
    ROOT_CAUSE_CHECKPOINT_CORRUPTION: "checkpoint",
    ROOT_CAUSE_RETRY_EXHAUSTED: "retry_policy",
    ROOT_CAUSE_UNKNOWN: "unknown",
}

# Root cause → suggested fix (deterministic mapping)
ROOT_CAUSE_FIX = {
    ROOT_CAUSE_TOOL_TIMEOUT: "increase_timeout",
    ROOT_CAUSE_BUDGET_EXCEEDED: "reduce_context_size",
    ROOT_CAUSE_CHECKPOINT_CORRUPTION: "enable_crash_recovery",
    ROOT_CAUSE_RETRY_EXHAUSTED: "increase_max_retries",
    ROOT_CAUSE_UNKNOWN: "manual_review",
}


@dataclass(frozen=True)
class FailureDiagnosis:
    """Distilled feedback from a failed execution trace.

    Maps each failure to exactly one root cause and one affected component.
    This is the Agent Debugger role from AHE (Fudan/PKU 2026):
    analyzes failure traces → produces distilled, actionable feedback.
    """
    execution_id: str
    failed_stage: str
    root_cause: str           # One of ALL_ROOT_CAUSES
    affected_component: str   # Single ETCLOVG component
    suggested_fix: str        # Concrete action string
    confidence: float         # 0.0-1.0
    trace_summary: str        # Compressed trace (deterministic, not LLM)
    diagnosis_hash: str

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "failed_stage": self.failed_stage,
            "root_cause": self.root_cause,
            "affected_component": self.affected_component,
            "suggested_fix": self.suggested_fix,
            "confidence": self.confidence,
            "trace_summary": self.trace_summary,
            "diagnosis_hash": self.diagnosis_hash,
        }


def _compute_diagnosis_hash(
    execution_id: str, root_cause: str, affected_component: str,
) -> str:
    data = json.dumps({
        "execution_id": execution_id,
        "root_cause": root_cause,
        "affected_component": affected_component,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def diagnose_failure(
    execution_result: dict,
    trace_spans: Tuple[dict, ...] = (),
) -> FailureDiagnosis:
    """Analyze a failed execution and produce a distilled diagnosis.

    Deterministic rules (no LLM):
    - StageError with "timeout" in error → tool_timeout, fix=increase_timeout
    - Budget blocked → budget_exceeded, fix=reduce_context_size
    - Crash marker → checkpoint_corruption, fix=enable_crash_recovery
    - retry_count >= max_retries → retry_exhausted, fix=increase_max_retries
    - Otherwise → unknown, fix=manual_review

    Component observability: each rule maps to exactly one ETCLOVG component.
    """
    execution_id = execution_result.get("execution_id", "")
    failed_stage = execution_result.get("failed_stage", "")
    error = execution_result.get("error", "")
    stage_results = execution_result.get("stage_results", [])

    # Rule 1: Timeout detection
    if "timeout" in error.lower():
        diag = FailureDiagnosis(
            execution_id=execution_id,
            failed_stage=failed_stage or "unknown",
            root_cause=ROOT_CAUSE_TOOL_TIMEOUT,
            affected_component=ROOT_CAUSE_COMPONENT[ROOT_CAUSE_TOOL_TIMEOUT],
            suggested_fix=ROOT_CAUSE_FIX[ROOT_CAUSE_TOOL_TIMEOUT],
            confidence=0.95,
            trace_summary=f"Timeout detected in stage '{failed_stage}': {error[:200]}",
            diagnosis_hash="",
        )
        object.__setattr__(diag, "diagnosis_hash",
                           _compute_diagnosis_hash(diag.execution_id, diag.root_cause, diag.affected_component))
        return diag

    # Rule 1b: Check stage results for timeout errors
    for sr in stage_results:
        sr_error = sr.get("error", "")
        if "timeout" in str(sr_error).lower():
            diag = FailureDiagnosis(
                execution_id=execution_id,
                failed_stage=sr.get("stage_name", failed_stage or "unknown"),
                root_cause=ROOT_CAUSE_TOOL_TIMEOUT,
                affected_component=ROOT_CAUSE_COMPONENT[ROOT_CAUSE_TOOL_TIMEOUT],
                suggested_fix=ROOT_CAUSE_FIX[ROOT_CAUSE_TOOL_TIMEOUT],
                confidence=0.90,
                trace_summary=f"Stage timeout: {sr_error[:200]}",
                diagnosis_hash="",
            )
            object.__setattr__(diag, "diagnosis_hash",
                               _compute_diagnosis_hash(diag.execution_id, diag.root_cause, diag.affected_component))
            return diag

    # Rule 2: Budget exceeded
    invariant_violations = execution_result.get("invariant_violations", [])
    for v in invariant_violations:
        v_str = str(v).lower()
        if "budget" in v_str or "blocked" in v_str:
            diag = FailureDiagnosis(
                execution_id=execution_id,
                failed_stage=failed_stage or "budget_check",
                root_cause=ROOT_CAUSE_BUDGET_EXCEEDED,
                affected_component=ROOT_CAUSE_COMPONENT[ROOT_CAUSE_BUDGET_EXCEEDED],
                suggested_fix=ROOT_CAUSE_FIX[ROOT_CAUSE_BUDGET_EXCEEDED],
                confidence=0.85,
                trace_summary=f"Budget violation: {v_str[:200]}",
                diagnosis_hash="",
            )
            object.__setattr__(diag, "diagnosis_hash",
                               _compute_diagnosis_hash(diag.execution_id, diag.root_cause, diag.affected_component))
            return diag

    # Rule 3: Crash / checkpoint corruption
    if "crash" in str(error).lower():
        diag = FailureDiagnosis(
            execution_id=execution_id,
            failed_stage=failed_stage or "unknown",
            root_cause=ROOT_CAUSE_CHECKPOINT_CORRUPTION,
            affected_component=ROOT_CAUSE_COMPONENT[ROOT_CAUSE_CHECKPOINT_CORRUPTION],
            suggested_fix=ROOT_CAUSE_FIX[ROOT_CAUSE_CHECKPOINT_CORRUPTION],
            confidence=0.80,
            trace_summary=f"Crash detected: {error[:200]}",
            diagnosis_hash="",
        )
        object.__setattr__(diag, "diagnosis_hash",
                           _compute_diagnosis_hash(diag.execution_id, diag.root_cause, diag.affected_component))
        return diag

    # Rule 4: Retry exhaustion
    is_failed = not execution_result.get("success", True)
    has_retries = any(
        not sr.get("passed", True) for sr in stage_results
    )
    if is_failed and has_retries:
        diag = FailureDiagnosis(
            execution_id=execution_id,
            failed_stage=failed_stage or "unknown",
            root_cause=ROOT_CAUSE_RETRY_EXHAUSTED,
            affected_component=ROOT_CAUSE_COMPONENT[ROOT_CAUSE_RETRY_EXHAUSTED],
            suggested_fix=ROOT_CAUSE_FIX[ROOT_CAUSE_RETRY_EXHAUSTED],
            confidence=0.75,
            trace_summary=f"Retry exhausted after stage failures: {failed_stage}",
            diagnosis_hash="",
        )
        object.__setattr__(diag, "diagnosis_hash",
                           _compute_diagnosis_hash(diag.execution_id, diag.root_cause, diag.affected_component))
        return diag

    # Rule 5: Unknown — fallback
    if not execution_result.get("success", True):
        diag = FailureDiagnosis(
            execution_id=execution_id,
            failed_stage=failed_stage or "unknown",
            root_cause=ROOT_CAUSE_UNKNOWN,
            affected_component=ROOT_CAUSE_COMPONENT[ROOT_CAUSE_UNKNOWN],
            suggested_fix=ROOT_CAUSE_FIX[ROOT_CAUSE_UNKNOWN],
            confidence=0.30,
            trace_summary=f"Unknown failure in stage '{failed_stage}': {error[:200]}",
            diagnosis_hash="",
        )
        object.__setattr__(diag, "diagnosis_hash",
                           _compute_diagnosis_hash(diag.execution_id, diag.root_cause, diag.affected_component))
        return diag

    # Success case — should not be called for successful executions
    diag = FailureDiagnosis(
        execution_id=execution_id,
        failed_stage="",
        root_cause=ROOT_CAUSE_UNKNOWN,
        affected_component=ROOT_CAUSE_COMPONENT[ROOT_CAUSE_UNKNOWN],
        suggested_fix="none",
        confidence=0.0,
        trace_summary="No failure detected",
        diagnosis_hash="",
    )
    object.__setattr__(diag, "diagnosis_hash",
                       _compute_diagnosis_hash(diag.execution_id, diag.root_cause, diag.affected_component))
    return diag


# ═══════════════════════════════════════════════════════════════════════
# Evolution Loop — End-to-End Auto-Evolution (Phase 16c)
# ═══════════════════════════════════════════════════════════════════════

def evolution_loop(
    max_iterations: int = 5,
    *,
    auto_apply: bool = False,
) -> Tuple:
    """One pass of the evolution loop.

    Pipeline:
      1. Run benchmark suite (baseline)
      2. For each failure: diagnose_failure() → get diagnosis
      3. For each diagnosis with confidence >= 0.7:
         - Generate SkillEvolutionProposal
         - If auto_apply and can_auto_apply: execute apply_proposal()
         - Verify → if fail, rollback
      4. Re-run benchmark suite
      5. Report delta

    Returns tuple of EvolutionResult (from skill_evolution_executor).
    """
    from v3.external.skill_evolution_policy import can_auto_apply
    from v3.external.skill_evolution_executor import (
        apply_proposal, EvolutionResult,
    )

    results: list = []
    iteration = 0

    for iteration in range(max_iterations):
        # Step 1: Run benchmark
        try:
            from v3.evals.benchmark_suite import run_benchmark
            report = run_benchmark()
        except Exception:
            break

        # Step 2: Diagnose failures
        diagnoses = []
        for result in report.results:
            if not result.passed and result.actual not in ("pass",):
                exec_result = {
                    "execution_id": f"bench-{result.task_name}-{result.config_name}",
                    "success": False,
                    "failed_stage": result.task_name,
                    "error": result.detail,
                    "stage_results": [],
                }
                diag = diagnose_failure(exec_result, ())
                if diag.confidence >= 0.7:
                    diagnoses.append(diag)

        if not diagnoses:
            break  # No failures to fix

        # Step 3: Generate proposals and optionally apply
        for diag in diagnoses:
            proposal = make_skill_evolution_proposal(
                provider_id="evolution_loop",
                proposal_type=PROPOSAL_TYPE_UPDATE_SKILL,
                target_skill_refs=(diag.affected_component,),
                gap_signal_ids=(diag.diagnosis_hash,),
                proposed_changes_summary=(
                    f"Auto-diagnosed: {diag.root_cause} → {diag.suggested_fix} "
                    f"(confidence: {diag.confidence:.0%})"
                ),
                proposed_files=(f"config/{diag.affected_component}.json",),
                required_tests=("benchmark_suite",),
                seed=iteration,
            )

            if auto_apply:
                allowed, reason = can_auto_apply(proposal)
                if allowed:
                    evo_result = apply_proposal(proposal, dry_run=False)
                else:
                    evo_result = EvolutionResult(
                        proposal_id=proposal.proposal_id,
                        applied=False,
                        rollback_available=False,
                        before_state={},
                        after_state={},
                        verification=f"blocked: {reason}",
                        result_hash="",
                    )
            else:
                evo_result = apply_proposal(proposal, dry_run=True)
            results.append(evo_result)

    return tuple(results)
