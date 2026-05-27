"""
Orchestration Policy Profiles — Phase 9.

Defines common deterministic policy profiles for different orchestration
scenarios. Each profile is a pre-configured OrchestrationPolicy that can
be used to plan which external capability adapters may be used together.

Profiles are PLANS, not executions. No adapter is run. No tool is called.
All profiles default to dry_run_only=True.

Includes an ECC harness review placeholder for future everything-claude-code
evaluation — disabled, dry-run only, no execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Tuple


def _compute_policy_hash(policy) -> str:
    data = policy.to_dict()
    data.pop("policy_hash", None)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Profile Status
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OrchestrationProfileStatus:
    """Status of an orchestration policy profile."""
    policy_id: str = ""
    description: str = ""
    active: bool = True
    status_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "description": self.description,
            "active": self.active,
            "status_hash": self.status_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Profile Builder
# ═══════════════════════════════════════════════════════════════════════

def _build(
    policy_id: str,
    allowed_capability_types: Tuple[str, ...] = (),
    forbidden_capability_types: Tuple[str, ...] = (),
    allowed_adapters: Tuple[str, ...] = (),
    forbidden_adapters: Tuple[str, ...] = (),
    require_human_approval: bool = True,
    dry_run_only: bool = True,
    max_adapters_per_plan: int = 10,
    max_risk_level: str = "low",
    allow_external_execution: bool = False,
    allow_file_modification: bool = False,
    allow_network: bool = False,
    allow_registry_updates: bool = False,
    allow_memory_mutation: bool = False,
) -> "OrchestrationPolicy":
    """Build a deterministic orchestration policy profile."""
    from v3.external.orchestration_policy import OrchestrationPolicy

    policy = OrchestrationPolicy(
        policy_id=policy_id,
        allowed_capability_types=allowed_capability_types,
        forbidden_capability_types=forbidden_capability_types,
        allowed_adapters=allowed_adapters,
        forbidden_adapters=forbidden_adapters,
        require_human_approval=require_human_approval,
        dry_run_only=dry_run_only,
        max_adapters_per_plan=max_adapters_per_plan,
        max_risk_level=max_risk_level,
        allow_external_execution=allow_external_execution,
        allow_file_modification=allow_file_modification,
        allow_network=allow_network,
        allow_registry_updates=allow_registry_updates,
        allow_memory_mutation=allow_memory_mutation,
    )
    object.__setattr__(policy, "policy_hash", _compute_policy_hash(policy))
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Safe Context Only Profile
# ═══════════════════════════════════════════════════════════════════════

def safe_context_only() -> "OrchestrationPolicy":
    """Allows context + usage inspect-only adapters.

    Good for planning Repomix/ccusage evidence gathering.
    No file modification. No network. No execution.
    """
    return _build(
        policy_id="safe_context_only",
        allowed_capability_types=("context", "usage"),
        forbidden_capability_types=("agent", "ide", "eval", "skill", "tool"),
        require_human_approval=True,
        dry_run_only=True,
        max_adapters_per_plan=5,
        max_risk_level="medium",
        allow_external_execution=False,
        allow_file_modification=False,
        allow_network=False,
        allow_registry_updates=False,
        allow_memory_mutation=False,
    )


# ═══════════════════════════════════════════════════════════════════════
# Skill Evolution Review Profile
# ═══════════════════════════════════════════════════════════════════════

def skill_evolution_review() -> "OrchestrationPolicy":
    """Allows skill proposal providers only, no registry writes.

    Good for planning skill evolution review pipelines.
    No skill modification. No registry update. No installation.
    """
    return _build(
        policy_id="skill_evolution_review",
        allowed_capability_types=("skill",),
        forbidden_capability_types=("agent", "ide", "eval", "memory", "context", "usage", "tool"),
        require_human_approval=True,
        dry_run_only=True,
        max_adapters_per_plan=5,
        max_risk_level="medium",
        allow_external_execution=False,
        allow_file_modification=False,
        allow_network=False,
        allow_registry_updates=False,
        allow_memory_mutation=False,
    )


# ═══════════════════════════════════════════════════════════════════════
# Memory Intelligence Review Profile
# ═══════════════════════════════════════════════════════════════════════

def memory_intelligence_review() -> "OrchestrationPolicy":
    """Allows deterministic mock memory intelligence only.

    Good for planning memory signal generation reviews.
    No external memory service. No write operations.
    """
    return _build(
        policy_id="memory_intelligence_review",
        allowed_capability_types=("memory",),
        forbidden_capability_types=("agent", "ide", "eval", "skill", "context", "usage", "tool"),
        require_human_approval=True,
        dry_run_only=True,
        max_adapters_per_plan=3,
        max_risk_level="low",
        allow_external_execution=False,
        allow_file_modification=False,
        allow_network=False,
        allow_registry_updates=False,
        allow_memory_mutation=False,
    )


# ═══════════════════════════════════════════════════════════════════════
# Agent Worker Review Profile
# ═══════════════════════════════════════════════════════════════════════

def agent_worker_review() -> "OrchestrationPolicy":
    """Allows deterministic mock agent worker only.

    Good for planning agent proposal review pipelines.
    No agent execution. No file modification. No network.
    """
    return _build(
        policy_id="agent_worker_review",
        allowed_capability_types=("agent",),
        forbidden_capability_types=("context", "memory", "ide", "eval", "skill", "usage", "tool"),
        require_human_approval=True,
        dry_run_only=True,
        max_adapters_per_plan=3,
        max_risk_level="low",
        allow_external_execution=False,
        allow_file_modification=False,
        allow_network=False,
        allow_registry_updates=False,
        allow_memory_mutation=False,
    )


# ═══════════════════════════════════════════════════════════════════════
# Full External Review Profile
# ═══════════════════════════════════════════════════════════════════════

def full_external_review() -> "OrchestrationPolicy":
    """Allows all capability types but dry_run_only, no execution.

    Good for comprehensive planning and audit of all external
    capability adapters. No execution permitted.
    """
    return _build(
        policy_id="full_external_review",
        allowed_capability_types=(
            "context", "memory", "agent", "ide", "eval", "skill", "usage", "tool",
        ),
        forbidden_capability_types=(),
        require_human_approval=True,
        dry_run_only=True,
        max_adapters_per_plan=20,
        max_risk_level="high",
        allow_external_execution=False,
        allow_file_modification=False,
        allow_network=False,
        allow_registry_updates=False,
        allow_memory_mutation=False,
    )


# ═══════════════════════════════════════════════════════════════════════
# ECC Harness Review Profile (FUTURE — DISABLED)
# ═══════════════════════════════════════════════════════════════════════

def ecc_harness_review() -> "OrchestrationPolicy":
    """Placeholder profile for future ECC / everything-claude-code evaluation.

    ECC should be usable by SystemKernel as an external capability source,
    but SystemKernel must not become an ECC clone.

    Capability types: skill + tool + eval + context
    Disabled / dry-run only. No execution. No install. No kernel modification.

    This is a FUTURE placeholder. ECC is NOT integrated in this phase.
    """
    return _build(
        policy_id="ecc_harness_review",
        allowed_capability_types=("skill", "tool", "eval", "context"),
        forbidden_capability_types=("agent", "ide", "memory", "usage"),
        require_human_approval=True,
        dry_run_only=True,
        max_adapters_per_plan=8,
        max_risk_level="medium",
        allow_external_execution=False,
        allow_file_modification=False,
        allow_network=False,
        allow_registry_updates=False,
        allow_memory_mutation=False,
    )


# ═══════════════════════════════════════════════════════════════════════
# Profile Registry
# ═══════════════════════════════════════════════════════════════════════

def get_all_profiles() -> Tuple["OrchestrationPolicy", ...]:
    """Return all orchestration policy profiles.

    Sorted by policy_id for determinism.
    """
    profiles = (
        safe_context_only(),
        skill_evolution_review(),
        memory_intelligence_review(),
        agent_worker_review(),
        full_external_review(),
        ecc_harness_review(),
    )
    return tuple(sorted(profiles, key=lambda p: p.policy_id))


def get_profile(policy_id: str):
    """Get a single policy profile by ID. Returns None if not found."""
    for p in get_all_profiles():
        if p.policy_id == policy_id:
            return p
    return None


def get_all_profile_statuses() -> Tuple[OrchestrationProfileStatus, ...]:
    """Get status summaries for all profiles."""
    results = []
    descriptions = {
        "safe_context_only": "Context + usage inspect-only",
        "skill_evolution_review": "Skill proposals only, no registry writes",
        "memory_intelligence_review": "Mock memory intelligence only",
        "agent_worker_review": "Mock agent worker only",
        "full_external_review": "All capability types, dry-run only",
        "ecc_harness_review": "ECC future harness — disabled placeholder",
    }
    for p in get_all_profiles():
        desc = descriptions.get(p.policy_id, "")
        status = OrchestrationProfileStatus(
            policy_id=p.policy_id,
            description=desc,
            active=True,
        )
        object.__setattr__(status, "status_hash",
                          hashlib.sha256(
                              json.dumps(status.to_dict(), sort_keys=True).encode()
                          ).hexdigest()[:16])
        results.append(status)
    return tuple(results)
