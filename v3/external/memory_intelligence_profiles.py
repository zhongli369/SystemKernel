"""
Memory Intelligence Provider Profiles — Phase 5.

Defines disabled/blocked profiles for future memory intelligence
providers (mem0, Graphiti, Letta) and one allowed mock provider
for deterministic testing.

Profiles are DESCRIPTIONS, not integrations. No provider imports,
executes, or connects to external services.

All profiles: truth_source=False, removable=True.

Default policy blocks all real providers. Only deterministic_mock
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
class ProviderProfileStatus:
    """Cached status of a provider profile under a given policy."""
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
    requires_vector_db: bool = False,
    requires_graph_db: bool = False,
    external_service_required: bool = False,
    description: str = "",
) -> "MemoryIntelligenceProvider":
    """Build a deterministic provider with hash."""
    from v3.external.memory_intelligence import (
        MemoryIntelligenceProvider,
        MODE_INSPECT_ONLY,
        MODE_EXTERNAL_SERVICE,
        _compute_hash as mi_hash,
    )

    exec_mode = MODE_EXTERNAL_SERVICE if external_service_required else MODE_INSPECT_ONLY
    provider = MemoryIntelligenceProvider(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        capability_type="memory",
        execution_mode=exec_mode,
        requires_llm=requires_llm,
        requires_vector_db=requires_vector_db,
        requires_graph_db=requires_graph_db,
        external_service_required=external_service_required,
        truth_source=False,
        removable=True,
        description=description,
    )
    object.__setattr__(provider, "provider_hash", mi_hash(provider))
    return provider


# ═══════════════════════════════════════════════════════════════════════
# Mem0 Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def mem0_memory_intelligence_profile() -> "MemoryIntelligenceProvider":
    """mem0 memory intelligence provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - requires_vector_db=True  →  blocked (allow_vector_db_providers=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — mem0 is not integrated.
    """
    return _build_provider(
        provider_id="mem0_memory_intelligence",
        name="Mem0 Memory Intelligence",
        provider_type="mem0_like",
        requires_llm=True,
        requires_vector_db=True,
        requires_graph_db=False,
        external_service_required=True,
        description=(
            "External memory intelligence provider using mem0. "
            "Requires LLM, vector DB, and external service. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Graphiti Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def graphiti_temporal_kg_profile() -> "MemoryIntelligenceProvider":
    """Graphiti temporal knowledge graph provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - requires_graph_db=True  →  blocked (allow_graph_db_providers=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — Graphiti is not integrated.
    """
    return _build_provider(
        provider_id="graphiti_temporal_kg",
        name="Graphiti Temporal Knowledge Graph",
        provider_type="graphiti_like",
        requires_llm=True,
        requires_vector_db=False,
        requires_graph_db=True,
        external_service_required=True,
        description=(
            "External memory intelligence provider using Graphiti. "
            "Requires LLM, graph DB, and external service. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Letta Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def letta_stateful_memory_profile() -> "MemoryIntelligenceProvider":
    """Letta stateful memory provider profile.

    BLOCKED by default policy:
    - requires_llm=True  →  blocked (allow_llm_providers=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — Letta is not integrated.
    """
    return _build_provider(
        provider_id="letta_stateful_memory",
        name="Letta Stateful Memory",
        provider_type="letta_like",
        requires_llm=True,
        requires_vector_db=False,
        requires_graph_db=False,
        external_service_required=True,
        description=(
            "External memory intelligence provider using Letta. "
            "Requires LLM and external service. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Deterministic Mock Profile (ALLOWED by default)
# ═══════════════════════════════════════════════════════════════════════

def deterministic_mock_memory_profile() -> "MemoryIntelligenceProvider":
    """Deterministic mock memory intelligence provider profile.

    ALLOWED by default policy:
    - requires_llm=False  →  passes
    - requires_vector_db=False  →  passes
    - requires_graph_db=False  →  passes
    - external_service_required=False  →  passes

    Used for testing the memory intelligence plane. Always deterministic.
    """
    return _build_provider(
        provider_id="deterministic_mock_memory",
        name="Deterministic Mock Memory Intelligence",
        provider_type="deterministic_mock",
        requires_llm=False,
        requires_vector_db=False,
        requires_graph_db=False,
        external_service_required=False,
        description=(
            "Deterministic mock memory intelligence provider. "
            "Produces synthetic signals from fixture input. "
            "Used for testing the memory intelligence plane. "
            "Always deterministic — same input → same output. "
            "ALLOWED by default policy."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Profile Registry
# ═══════════════════════════════════════════════════════════════════════

def get_all_profiles() -> Tuple["MemoryIntelligenceProvider", ...]:
    """Return all registered memory intelligence provider profiles.

    Sorted by provider_id for determinism.
    """
    profiles = (
        mem0_memory_intelligence_profile(),
        graphiti_temporal_kg_profile(),
        letta_stateful_memory_profile(),
        deterministic_mock_memory_profile(),
    )
    return tuple(sorted(profiles, key=lambda p: p.provider_id))


def get_profile(provider_id: str) -> Optional["MemoryIntelligenceProvider"]:
    """Get a single provider profile by ID. Returns None if not found."""
    for p in get_all_profiles():
        if p.provider_id == provider_id:
            return p
    return None


def evaluate_all_profiles(policy) -> Tuple[ProviderProfileStatus, ...]:
    """Evaluate all provider profiles against a policy.

    Returns tuple of ProviderProfileStatus, sorted by provider_id.
    """
    from v3.external.memory_intelligence_policy import validate_provider_against_policy

    results = []
    for p in get_all_profiles():
        allowed, reason = validate_provider_against_policy(p, policy)
        status = ProviderProfileStatus(
            provider_id=p.provider_id,
            allowed=allowed,
            reason=reason if not allowed else "OK",
        )
        object.__setattr__(status, "status_hash", _compute_hash(status.to_dict()))
        results.append(status)

    return tuple(sorted(results, key=lambda s: s.provider_id))
