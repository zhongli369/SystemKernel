"""
Skill Evolution Provider Profiles — Phase 8.

Defines disabled/blocked profiles for future skill evolution
providers (Anthropic Skills format, SuperClaude patterns) and one
allowed mock provider for deterministic testing.

Profiles are DESCRIPTIONS, not integrations. No provider imports,
executes, or connects to external services.

All profiles: truth_source=False, removable=True.

Default policy blocks all real skill evolution providers.
Only deterministic_mock passes the gate under default policy.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


def _compute_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Profile Status Cache
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SkillEvolutionProfileStatus:
    """Cached status of a skill evolution profile under a given policy."""
    provider_id: str = ""
    allowed: bool = False
    reason: str = ""
    status_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "status_hash": self.status_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Provider Profile Builder
# ═══════════════════════════════════════════════════════════════════════

def _build_provider(
    provider_id: str,
    name: str,
    provider_type: str,
    requires_llm: bool = False,
    can_modify_skills: bool = False,
    can_update_registry: bool = False,
    can_install_skills: bool = False,
    external_service_required: bool = False,
    description: str = "",
) -> "SkillEvolutionProvider":
    """Build a deterministic skill evolution provider with hash."""
    from v3.external.skill_evolution import (
        SkillEvolutionProvider,
        _compute_hash as se_hash,
    )

    provider = SkillEvolutionProvider(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        capability_type="skill",
        execution_mode="inspect_only",
        requires_llm=requires_llm,
        can_modify_skills=can_modify_skills,
        can_update_registry=can_update_registry,
        can_install_skills=can_install_skills,
        external_service_required=external_service_required,
        truth_source=False,
        removable=True,
        description=description,
    )
    object.__setattr__(provider, "provider_hash", se_hash(provider))
    return provider


# ═══════════════════════════════════════════════════════════════════════
# Anthropic Skills Format Provider (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def anthropic_skills_format_provider() -> "SkillEvolutionProvider":
    """Anthropic Skills format provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - can_modify_skills=True  →  blocked (allow_skill_file_modification=False)
    - can_update_registry=True  →  blocked (allow_registry_update=False)
    - can_install_skills=True  →  blocked (allow_skill_installation=False)

    This is a PLACEHOLDER profile. A future Anthropic Skills-based
    evolution provider would analyze existing SKILL.md files against
    Anthropic's SKILL.md conventions and propose format alignment.
    NOT integrated.
    """
    return _build_provider(
        provider_id="anthropic_skills_format",
        name="Anthropic Skills Format Provider",
        provider_type="anthropic_skills_like",
        requires_llm=True,
        can_modify_skills=True,
        can_update_registry=True,
        can_install_skills=True,
        external_service_required=True,
        description=(
            "External skill evolution provider using Anthropic Skills format. "
            "Requires LLM and external service. "
            "Can modify skills, update registry, and install skills. "
            "Would propose SKILL.md alignment with Anthropic conventions. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# SuperClaude Pattern Provider (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def superclaude_pattern_provider() -> "SkillEvolutionProvider":
    """SuperClaude pattern provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - can_modify_skills=True  →  blocked (allow_skill_file_modification=False)
    - can_update_registry=True  →  blocked (allow_registry_update=False)
    - can_install_skills=False
    - external_service_required=True  →  blocked (allow_llm_providers=False)

    This is a PLACEHOLDER profile. A future SuperClaude-based
    evolution provider would analyze existing skill taxonomy against
    SuperClaude patterns and propose taxonomy improvements.
    NOT integrated.
    """
    return _build_provider(
        provider_id="superclaude_pattern",
        name="SuperClaude Pattern Provider",
        provider_type="superclaude_like",
        requires_llm=True,
        can_modify_skills=True,
        can_update_registry=True,
        can_install_skills=False,
        external_service_required=True,
        description=(
            "External skill evolution provider using SuperClaude patterns. "
            "Requires LLM and external service. "
            "Can modify skills and update registry. "
            "Would propose taxonomy and pattern alignment. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Deterministic Mock Provider (ALLOWED by default)
# ═══════════════════════════════════════════════════════════════════════

def deterministic_mock_skill_evolution() -> "SkillEvolutionProvider":
    """Deterministic mock skill evolution provider profile.

    ALLOWED by default policy:
    - requires_llm=False  →  passes
    - can_modify_skills=False  →  passes
    - can_update_registry=False  →  passes
    - can_install_skills=False  →  passes
    - external_service_required=False  →  passes

    Used for testing the skill evolution plane. Always deterministic.
    """
    return _build_provider(
        provider_id="deterministic_mock_skill_evolution",
        name="Deterministic Mock Skill Evolution Provider",
        provider_type="deterministic_mock",
        requires_llm=False,
        can_modify_skills=False,
        can_update_registry=False,
        can_install_skills=False,
        external_service_required=False,
        description=(
            "Deterministic mock skill evolution provider. "
            "Produces synthetic proposals from fixture input. "
            "Used for testing the skill evolution plane. "
            "Always deterministic — same input → same output. "
            "ALLOWED by default policy."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Profile Registry
# ═══════════════════════════════════════════════════════════════════════

def get_all_profiles() -> Tuple["SkillEvolutionProvider", ...]:
    """Return all registered skill evolution provider profiles.

    Sorted by provider_id for determinism.
    """
    profiles = (
        anthropic_skills_format_provider(),
        superclaude_pattern_provider(),
        deterministic_mock_skill_evolution(),
    )
    return tuple(sorted(profiles, key=lambda p: p.provider_id))


def get_profile(provider_id: str) -> Optional["SkillEvolutionProvider"]:
    """Get a single provider profile by ID. Returns None if not found."""
    for p in get_all_profiles():
        if p.provider_id == provider_id:
            return p
    return None


def evaluate_all_profiles(policy) -> Tuple[SkillEvolutionProfileStatus, ...]:
    """Evaluate all skill evolution profiles against a policy.

    Returns tuple of SkillEvolutionProfileStatus, sorted by provider_id.
    """
    from v3.external.skill_evolution_policy import validate_provider_against_policy

    results = []
    for p in get_all_profiles():
        allowed, reason = validate_provider_against_policy(p, policy)
        status = SkillEvolutionProfileStatus(
            provider_id=p.provider_id,
            allowed=allowed,
            reason=reason if not allowed else "OK",
        )
        object.__setattr__(status, "status_hash", _compute_hash(status.to_dict()))
        results.append(status)

    return tuple(sorted(results, key=lambda s: s.provider_id))
