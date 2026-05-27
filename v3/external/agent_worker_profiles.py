"""
Agent Worker Provider Profiles — Phase 6.

Defines disabled/blocked profiles for future agent worker
providers (OpenHands, SWE-agent, AutoGen, Continue) and one
allowed mock provider for deterministic testing.

Profiles are DESCRIPTIONS, not integrations. No provider imports,
executes, or connects to external services.

All profiles: truth_source=False, removable=True.

Default policy blocks all real agent workers. Only deterministic_mock
passes the gate under default policy.
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
class AgentWorkerProfileStatus:
    """Cached status of an agent worker profile under a given policy."""
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
# Provider Profile Builders
# ═══════════════════════════════════════════════════════════════════════

def _build_provider(
    provider_id: str,
    name: str,
    provider_type: str,
    requires_llm: bool = False,
    requires_sandbox: bool = False,
    requires_network: bool = False,
    can_modify_files: bool = False,
    can_execute_commands: bool = False,
    external_service_required: bool = False,
    description: str = "",
) -> "AgentWorkerProvider":
    """Build a deterministic agent worker provider with hash."""
    from v3.external.agent_worker import (
        AgentWorkerProvider,
        _compute_hash as aw_hash,
    )

    provider = AgentWorkerProvider(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        capability_type="agent",
        execution_mode="inspect_only",
        requires_llm=requires_llm,
        requires_sandbox=requires_sandbox,
        requires_network=requires_network,
        can_modify_files=can_modify_files,
        can_execute_commands=can_execute_commands,
        external_service_required=external_service_required,
        truth_source=False,
        removable=True,
        description=description,
    )
    object.__setattr__(provider, "provider_hash", aw_hash(provider))
    return provider


# ═══════════════════════════════════════════════════════════════════════
# OpenHands Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def openhands_agent_profile() -> "AgentWorkerProvider":
    """OpenHands agent worker provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - requires_sandbox=True  →  blocked (default policy requires sandbox,
      but LLM requirement blocks first)
    - can_modify_files=True  →  blocked (allow_file_modification=False)
    - can_execute_commands=True  →  blocked (allow_command_execution=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — OpenHands is not integrated.
    """
    return _build_provider(
        provider_id="openhands_agent",
        name="OpenHands Agent Worker",
        provider_type="openhands_like",
        requires_llm=True,
        requires_sandbox=True,
        requires_network=True,
        can_modify_files=True,
        can_execute_commands=True,
        external_service_required=True,
        description=(
            "External agent worker provider using OpenHands. "
            "Requires LLM, sandbox, network, and external service. "
            "Can modify files and execute commands. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# SWE-agent Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def swe_agent_profile() -> "AgentWorkerProvider":
    """SWE-agent worker provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - can_modify_files=True  →  blocked (allow_file_modification=False)
    - can_execute_commands=True  →  blocked (allow_command_execution=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — SWE-agent is not integrated.
    """
    return _build_provider(
        provider_id="swe_agent_worker",
        name="SWE-agent Worker",
        provider_type="swe_agent_like",
        requires_llm=True,
        requires_sandbox=False,
        requires_network=False,
        can_modify_files=True,
        can_execute_commands=True,
        external_service_required=True,
        description=(
            "External agent worker provider using SWE-agent. "
            "Requires LLM and external service. "
            "Can modify files and execute commands. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# AutoGen Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def autogen_agent_profile() -> "AgentWorkerProvider":
    """AutoGen agent worker provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - can_modify_files=True  →  blocked (allow_file_modification=False)
    - can_execute_commands=True  →  blocked (allow_command_execution=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — AutoGen is not integrated.
    """
    return _build_provider(
        provider_id="autogen_agent",
        name="AutoGen Agent Worker",
        provider_type="autogen_like",
        requires_llm=True,
        requires_sandbox=False,
        requires_network=False,
        can_modify_files=True,
        can_execute_commands=True,
        external_service_required=True,
        description=(
            "External agent worker provider using AutoGen. "
            "Requires LLM and external service. "
            "Can modify files and execute commands. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Continue Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def continue_agent_profile() -> "AgentWorkerProvider":
    """Continue agent worker provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - can_modify_files=True  →  blocked (allow_file_modification=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    Continue is primarily an IDE agent — it can modify files but
    typically does not execute arbitrary commands.

    This is a PLACEHOLDER profile — Continue is not integrated.
    """
    return _build_provider(
        provider_id="continue_agent",
        name="Continue IDE Agent",
        provider_type="continue_like",
        requires_llm=True,
        requires_sandbox=False,
        requires_network=False,
        can_modify_files=True,
        can_execute_commands=False,
        external_service_required=True,
        description=(
            "External agent worker provider using Continue. "
            "Requires LLM and external service. "
            "Can modify files. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Deterministic Mock Profile (ALLOWED by default)
# ═══════════════════════════════════════════════════════════════════════

def deterministic_mock_agent_profile() -> "AgentWorkerProvider":
    """Deterministic mock agent worker provider profile.

    ALLOWED by default policy:
    - requires_llm=False  →  passes
    - requires_sandbox=False  →  passes
    - requires_network=False  →  passes
    - can_modify_files=False  →  passes
    - can_execute_commands=False  →  passes
    - external_service_required=False  →  passes

    Used for testing the agent worker plane. Always deterministic.
    """
    return _build_provider(
        provider_id="deterministic_mock_agent",
        name="Deterministic Mock Agent Worker",
        provider_type="deterministic_mock",
        requires_llm=False,
        requires_sandbox=False,
        requires_network=False,
        can_modify_files=False,
        can_execute_commands=False,
        external_service_required=False,
        description=(
            "Deterministic mock agent worker provider. "
            "Produces synthetic proposals from fixture input. "
            "Used for testing the agent worker plane. "
            "Always deterministic — same input → same output. "
            "ALLOWED by default policy."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Profile Registry
# ═══════════════════════════════════════════════════════════════════════

def get_all_profiles() -> Tuple["AgentWorkerProvider", ...]:
    """Return all registered agent worker provider profiles.

    Sorted by provider_id for determinism.
    """
    profiles = (
        openhands_agent_profile(),
        swe_agent_profile(),
        autogen_agent_profile(),
        continue_agent_profile(),
        deterministic_mock_agent_profile(),
    )
    return tuple(sorted(profiles, key=lambda p: p.provider_id))


def get_profile(provider_id: str) -> Optional["AgentWorkerProvider"]:
    """Get a single provider profile by ID. Returns None if not found."""
    for p in get_all_profiles():
        if p.provider_id == provider_id:
            return p
    return None


def evaluate_all_profiles(policy) -> Tuple[AgentWorkerProfileStatus, ...]:
    """Evaluate all agent worker profiles against a policy.

    Returns tuple of AgentWorkerProfileStatus, sorted by provider_id.
    """
    from v3.external.agent_worker_policy import validate_provider_against_policy

    results = []
    for p in get_all_profiles():
        allowed, reason = validate_provider_against_policy(p, policy)
        status = AgentWorkerProfileStatus(
            provider_id=p.provider_id,
            allowed=allowed,
            reason=reason if not allowed else "OK",
        )
        object.__setattr__(status, "status_hash", _compute_hash(status.to_dict()))
        results.append(status)

    return tuple(sorted(results, key=lambda s: s.provider_id))
