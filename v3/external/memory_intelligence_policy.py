"""
Memory Intelligence Policy — Phase 5.

Defines policies governing which memory intelligence providers are
allowed to operate and what types of signals they may produce.

Default policy is maximally conservative:
- No LLM-based providers
- No vector DB providers
- No graph DB providers
- No external service providers
- Only deterministic_mock providers allowed
- Delete/update signals are suggestions only, never automatic

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
# Memory Intelligence Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryIntelligencePolicy:
    """Policy governing memory intelligence provider operations.

    The policy defines which capabilities external memory intelligence
    providers may use and what signal types they may produce.

    Default: blocks everything except deterministic mock providers.
    """
    allow_llm_providers: bool = False
    allow_vector_db_providers: bool = False
    allow_graph_db_providers: bool = False
    allow_external_services: bool = False
    max_signals: int = 100
    allowed_signal_types: Tuple[str, ...] = ()
    forbidden_signal_types: Tuple[str, ...] = ()
    require_provenance: bool = True
    policy_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "allow_llm_providers": self.allow_llm_providers,
            "allow_vector_db_providers": self.allow_vector_db_providers,
            "allow_graph_db_providers": self.allow_graph_db_providers,
            "allow_external_services": self.allow_external_services,
            "max_signals": self.max_signals,
            "allowed_signal_types": list(self.allowed_signal_types),
            "forbidden_signal_types": list(self.forbidden_signal_types),
            "require_provenance": self.require_provenance,
            "policy_hash": self.policy_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Default Policy
# ═══════════════════════════════════════════════════════════════════════

def default_memory_intelligence_policy() -> MemoryIntelligencePolicy:
    """Return the default memory intelligence policy.

    Blocks all LLM, vector DB, graph DB, and external service providers.
    Only deterministic_mock providers pass by default.
    All signal types allowed — but only through mock provider.
    """
    from v3.external.memory_intelligence import (
        SIGNAL_TYPE_DELETE,
        SIGNAL_TYPE_UPDATE,
        ALL_SIGNAL_TYPES,
        PROVIDER_TYPE_DETERMINISTIC_MOCK,
    )

    # By default, all signal types are allowed but delete/update
    # are suggestion-only (enforced at the signal level, not policy level).
    # The policy allows all types — the provider gate is the primary enforcement.
    policy = MemoryIntelligencePolicy(
        allow_llm_providers=False,
        allow_vector_db_providers=False,
        allow_graph_db_providers=False,
        allow_external_services=False,
        max_signals=100,
        allowed_signal_types=ALL_SIGNAL_TYPES,
        forbidden_signal_types=(),
        require_provenance=True,
    )

    policy_hash = hashlib.sha256(
        json.dumps(policy.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    object.__setattr__(policy, "policy_hash", policy_hash)
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Policy Validation
# ═══════════════════════════════════════════════════════════════════════

def block_provider_reason(provider, policy: MemoryIntelligencePolicy) -> str:
    """Return the reason a provider is blocked, or empty string if allowed.

    Used by the gate: if this returns non-empty, the provider is blocked.
    """
    from v3.external.memory_intelligence import (
        PROVIDER_TYPE_DETERMINISTIC_MOCK,
    )

    # Deterministic mock always allowed
    if provider.provider_type == PROVIDER_TYPE_DETERMINISTIC_MOCK:
        return ""

    if provider.requires_llm and not policy.allow_llm_providers:
        return f"Provider '{provider.provider_id}' requires LLM, blocked by policy (allow_llm_providers=False)"

    if provider.requires_vector_db and not policy.allow_vector_db_providers:
        return f"Provider '{provider.provider_id}' requires vector DB, blocked by policy (allow_vector_db_providers=False)"

    if provider.requires_graph_db and not policy.allow_graph_db_providers:
        return f"Provider '{provider.provider_id}' requires graph DB, blocked by policy (allow_graph_db_providers=False)"

    if provider.external_service_required and not policy.allow_external_services:
        return f"Provider '{provider.provider_id}' requires external service, blocked by policy (allow_external_services=False)"

    return ""


def validate_provider_against_policy(
    provider,
    policy: MemoryIntelligencePolicy,
) -> Tuple[bool, str]:
    """Validate a MemoryIntelligenceProvider against the policy.

    Returns (allowed, reason).
    """
    reason = block_provider_reason(provider, policy)
    if reason:
        return False, reason
    return True, "OK"


def validate_result_against_policy(
    result,
    policy: MemoryIntelligencePolicy,
) -> Tuple[bool, str]:
    """Validate a MemoryIntelligenceResult against the policy.

    Returns (valid, reason).
    Checks: max_signals, forbidden signal types, blocked results.
    """
    from v3.external.memory_intelligence import MemoryIntelligenceResult

    if not isinstance(result, MemoryIntelligenceResult):
        return False, f"Expected MemoryIntelligenceResult, got {type(result).__name__}"

    if result.blocked:
        return True, "OK"  # Blocked results are valid — just empty

    # Check max signals
    if len(result.signals) > policy.max_signals:
        return False, (
            f"Result has {len(result.signals)} signals, "
            f"max is {policy.max_signals}"
        )

    # Check for forbidden signal types
    for signal in result.signals:
        if signal.signal_type in policy.forbidden_signal_types:
            return False, (
                f"Signal '{signal.signal_id}' has forbidden type "
                f"'{signal.signal_type}'"
            )

    # Check provenance if required
    if policy.require_provenance:
        for signal in result.signals:
            if not signal.provenance:
                return False, (
                    f"Signal '{signal.signal_id}' is missing provenance "
                    f"(require_provenance=True)"
                )

    return True, "OK"
