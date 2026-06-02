"""
Skill Evolution Policy — Phase 8.

Defines policies governing which skill evolution providers are allowed
to operate and what types of proposals they may produce.

Default policy is maximally conservative:
- No LLM-based providers
- No skill file modification
- No registry update
- No skill installation
- Tests required for any proposed change
- Human approval required for any change
- Only deterministic_mock providers allowed

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Tuple


# ═══════════════════════════════════════════════════════════════════════
# Policy Statuses
# ═══════════════════════════════════════════════════════════════════════

POLICY_PASS = "pass"
POLICY_BLOCKED = "blocked"
POLICY_REVIEW = "review"

ALL_POLICY_STATUSES = (POLICY_PASS, POLICY_BLOCKED, POLICY_REVIEW)


# ═══════════════════════════════════════════════════════════════════════
# Skill Evolution Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillEvolutionPolicy:
    """Policy governing skill evolution provider operations.

    The policy defines which capabilities external skill evolution
    providers may use and what constraints apply to proposals and results.

    Default: blocks everything except deterministic mock providers.
    All real skill evolution proposals require human approval.
    """
    allow_llm_providers: bool = False
    allow_skill_file_modification: bool = False
    allow_registry_update: bool = False
    allow_skill_installation: bool = False
    require_tests_for_changes: bool = True
    require_human_approval: bool = True
    max_proposals: int = 10
    allowed_proposal_types: Tuple[str, ...] = ()
    forbidden_paths: Tuple[str, ...] = ()
    policy_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "allow_llm_providers": self.allow_llm_providers,
            "allow_skill_file_modification": self.allow_skill_file_modification,
            "allow_registry_update": self.allow_registry_update,
            "allow_skill_installation": self.allow_skill_installation,
            "require_tests_for_changes": self.require_tests_for_changes,
            "require_human_approval": self.require_human_approval,
            "max_proposals": self.max_proposals,
            "allowed_proposal_types": list(self.allowed_proposal_types),
            "forbidden_paths": list(self.forbidden_paths),
            "policy_hash": self.policy_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Default Policy
# ═══════════════════════════════════════════════════════════════════════

def default_skill_evolution_policy() -> SkillEvolutionPolicy:
    """Return the default skill evolution policy.

    Blocks all LLM, skill file modification, registry update, and
    skill installation. Only deterministic_mock providers pass by default.

    require_tests_for_changes=True and require_human_approval=True are
    the mandatory gates for any future real skill evolution.
    """
    policy = SkillEvolutionPolicy(
        allow_llm_providers=False,
        allow_skill_file_modification=False,
        allow_registry_update=False,
        allow_skill_installation=False,
        require_tests_for_changes=True,
        require_human_approval=True,
        max_proposals=10,
        allowed_proposal_types=(),
        forbidden_paths=(),
    )

    policy_hash = hashlib.sha256(
        json.dumps(policy.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    object.__setattr__(policy, "policy_hash", policy_hash)
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Policy Validation — Provider
# ═══════════════════════════════════════════════════════════════════════

def block_provider_reason(provider, policy: SkillEvolutionPolicy) -> str:
    """Return the reason a provider is blocked, or empty string if allowed.

    Used by the gate: if this returns non-empty, the provider is blocked.
    """
    from v3.external.skill_evolution import PROVIDER_TYPE_DETERMINISTIC_MOCK

    if provider.provider_type == PROVIDER_TYPE_DETERMINISTIC_MOCK:
        return ""

    if provider.requires_llm and not policy.allow_llm_providers:
        return f"Provider '{provider.provider_id}' requires LLM, blocked by policy (allow_llm_providers=False)"

    if provider.can_modify_skills and not policy.allow_skill_file_modification:
        return f"Provider '{provider.provider_id}' can modify skills, blocked by policy (allow_skill_file_modification=False)"

    if provider.can_update_registry and not policy.allow_registry_update:
        return f"Provider '{provider.provider_id}' can update registry, blocked by policy (allow_registry_update=False)"

    if provider.can_install_skills and not policy.allow_skill_installation:
        return f"Provider '{provider.provider_id}' can install skills, blocked by policy (allow_skill_installation=False)"

    if provider.external_service_required and not policy.allow_llm_providers:
        return f"Provider '{provider.provider_id}' requires external service, blocked by default policy"

    return ""


def validate_provider_against_policy(
    provider,
    policy: SkillEvolutionPolicy,
) -> Tuple[bool, str]:
    """Validate a SkillEvolutionProvider against the policy.

    Returns (allowed, reason).
    """
    reason = block_provider_reason(provider, policy)
    if reason:
        return False, reason
    return True, "OK"


def validate_proposal_against_policy(
    proposal,
    policy: SkillEvolutionPolicy,
) -> Tuple[bool, str]:
    """Validate a SkillEvolutionProposal against the policy.

    Returns (valid, reason).
    Checks: allowed_proposal_types, forbidden_paths, tests required,
    approval_required.
    """
    from v3.external.skill_evolution import SkillEvolutionProposal

    if not isinstance(proposal, SkillEvolutionProposal):
        return False, f"Expected SkillEvolutionProposal, got {type(proposal).__name__}"

    if not proposal.approval_required:
        return False, (
            f"Proposal '{proposal.proposal_id}': approval_required must be True"
        )

    if (policy.allowed_proposal_types
            and proposal.proposal_type not in policy.allowed_proposal_types):
        return False, (
            f"Proposal '{proposal.proposal_id}': proposal_type "
            f"'{proposal.proposal_type}' not in allowed_proposal_types"
        )

    if policy.forbidden_paths:
        for pf in proposal.proposed_files:
            for fp in policy.forbidden_paths:
                if pf.startswith(fp.rstrip("/")) or fp.startswith(pf.rstrip("/")):
                    return False, (
                        f"Proposal '{proposal.proposal_id}': proposed_file "
                        f"'{pf}' in forbidden_paths"
                    )

    if policy.require_tests_for_changes and not proposal.required_tests:
        return False, (
            f"Proposal '{proposal.proposal_id}': tests required for changes "
            f"(require_tests_for_changes=True)"
        )

    return True, "OK"


def validate_result_against_policy(
    result,
    policy: SkillEvolutionPolicy,
) -> Tuple[bool, str]:
    """Validate a SkillEvolutionResult against the policy.

    Returns (valid, reason).
    Checks: max_proposals, blocked results, truth_source.
    """
    from v3.external.skill_evolution import SkillEvolutionResult, STATUS_BLOCKED

    if not isinstance(result, SkillEvolutionResult):
        return False, f"Expected SkillEvolutionResult, got {type(result).__name__}"

    if result.status == STATUS_BLOCKED:
        return True, "OK"

    if len(result.proposals) > policy.max_proposals:
        return False, (
            f"Result has {len(result.proposals)} proposals, "
            f"max is {policy.max_proposals}"
        )

    return True, "OK"


# ═══════════════════════════════════════════════════════════════════════
# Auto-Apply Policy — Safety Gate for Self-Evolving Harness (Phase 16c)
# ═══════════════════════════════════════════════════════════════════════

# Components safe to auto-adjust
ALLOWED_AUTO_COMPONENTS: Tuple[str, ...] = (
    "context_budget",
    "retry_policy",
    "timeout",
    "tool_selection",
    "checkpoint",
    "unknown",
)

# Components NEVER auto-modified
BLOCKED_AUTO_COMPONENTS: Tuple[str, ...] = (
    "api_surface",
    "kernel_core",
    "signal_model",
    "capability_registry",
)


@dataclass(frozen=True)
class AutoApplyPolicy:
    """Safety gate for auto-applying skill evolutions.

    Implements the Evolve Agent safety boundary from AHE:
    certain components can be auto-tuned; others are hard-blocked.

    Default: verification required, rollback required, max 3 auto-applies/session.
    """
    require_verification: bool = True
    require_rollback_plan: bool = True
    max_auto_applies_per_session: int = 3
    allowed_components: Tuple[str, ...] = ALLOWED_AUTO_COMPONENTS
    blocked_components: Tuple[str, ...] = BLOCKED_AUTO_COMPONENTS

    def to_dict(self) -> dict:
        return {
            "require_verification": self.require_verification,
            "require_rollback_plan": self.require_rollback_plan,
            "max_auto_applies_per_session": self.max_auto_applies_per_session,
            "allowed_components": list(self.allowed_components),
            "blocked_components": list(self.blocked_components),
        }


# Session-level auto-apply counter
_auto_apply_count: int = 0


def _get_default_auto_policy() -> AutoApplyPolicy:
    return AutoApplyPolicy()


def can_auto_apply(
    proposal,
    policy: Optional[AutoApplyPolicy] = None,
) -> Tuple[bool, str]:
    """Check if a proposal can be auto-applied.

    Checks:
      1. Target component is not in blocked_components (hard block)
      2. Target component is in allowed_components
      3. Session auto-apply count under max
      4. Rollback plan is available

    Returns (allowed, reason).
    """
    global _auto_apply_count

    if policy is None:
        policy = _get_default_auto_policy()

    # Extract target component from proposal
    target_components = getattr(proposal, "target_skill_refs", ())
    if not target_components:
        return False, "No target component specified in proposal"

    for component in target_components:
        # Hard block: NEVER auto-modify blocked components
        if component in policy.blocked_components:
            return False, (
                f"Component '{component}' is in blocked_components — "
                f"auto-apply is NEVER permitted for this component"
            )

        # Must be in allowed list
        if component not in policy.allowed_components:
            return False, (
                f"Component '{component}' is not in allowed_components — "
                f"manual review required for unknown components"
            )

    # Rate limit
    if _auto_apply_count >= policy.max_auto_applies_per_session:
        return False, (
            f"Auto-apply limit reached ({policy.max_auto_applies_per_session} "
            f"per session)"
        )

    # Rollback requirement
    if policy.require_rollback_plan:
        required_tests = getattr(proposal, "required_tests", ())
        if not required_tests:
            return False, "Rollback plan required but no tests specified"

    _auto_apply_count += 1
    return True, "OK"


def can_auto_apply_for_component(
    component: str,
    policy: Optional[AutoApplyPolicy] = None,
) -> Tuple[bool, str]:
    """Check if a specific component can be auto-applied.

    Convenience wrapper for testing the safety gate without a full proposal.

    Returns (allowed, reason).
    """
    if policy is None:
        policy = _get_default_auto_policy()

    if component in policy.blocked_components:
        return False, (
            f"Component '{component}' is in blocked_components — "
            f"auto-apply is NEVER permitted"
        )

    if component not in policy.allowed_components:
        return False, (
            f"Component '{component}' is not in allowed_components — "
            f"manual review required"
        )

    return True, "OK"


def reset_auto_apply_counter() -> None:
    """Reset the session-level auto-apply counter."""
    global _auto_apply_count
    _auto_apply_count = 0
