"""
Direction Intelligence Policy — v4.1.

Defines policies governing which direction intelligence providers are
allowed to operate and what types of signals they may produce.

Default policy is conservative:
- Methodology-based providers OK (analysis-only, no execution)
- No external service providers
- No LLM providers (methodology is pre-defined, not runtime LLM)
- All signal types allowed but advisory-only

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
# Direction Intelligence Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DirectionIntelligencePolicy:
    """Policy governing direction intelligence provider operations.

    Controls which providers and signal types are allowed.
    Default: methodology providers OK, no external service, no LLM.
    All signals are advisory — never authoritative.
    """
    allow_llm_providers: bool = False
    allow_external_services: bool = False
    allow_methodology_providers: bool = True
    max_signals: int = 10
    allowed_signal_types: Tuple[str, ...] = ()
    forbidden_signal_types: Tuple[str, ...] = ()
    require_provenance: bool = True
    weight: float = 0.4
    policy_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "allow_llm_providers": self.allow_llm_providers,
            "allow_external_services": self.allow_external_services,
            "allow_methodology_providers": self.allow_methodology_providers,
            "max_signals": self.max_signals,
            "allowed_signal_types": list(self.allowed_signal_types),
            "forbidden_signal_types": list(self.forbidden_signal_types),
            "require_provenance": self.require_provenance,
            "weight": self.weight,
            "policy_hash": self.policy_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Default Policy
# ═══════════════════════════════════════════════════════════════════════

def default_direction_intelligence_policy() -> DirectionIntelligencePolicy:
    """Return the default direction intelligence policy.

    Methodology-based providers are allowed (analysis-only).
    No LLM, no external services.
    Suggested weight for decision fusion: 0.4.
    """
    from v3.external.direction_intelligence import ALL_SIGNAL_TYPES

    policy = DirectionIntelligencePolicy(
        allow_llm_providers=False,
        allow_external_services=False,
        allow_methodology_providers=True,
        max_signals=10,
        allowed_signal_types=ALL_SIGNAL_TYPES,
        forbidden_signal_types=(),
        require_provenance=True,
        weight=0.4,
    )

    policy_hash = hashlib.sha256(
        json.dumps(policy.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    object.__setattr__(policy, "policy_hash", policy_hash)
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Policy Validation
# ═══════════════════════════════════════════════════════════════════════

def block_provider_reason(provider, policy: DirectionIntelligencePolicy) -> str:
    """Return the reason a provider is blocked, or empty string if allowed."""
    from v3.external.direction_intelligence import (
        PROVIDER_TYPE_DETERMINISTIC_MOCK,
        PROVIDER_TYPE_METHODOLOGY,
    )

    if provider.provider_type in (PROVIDER_TYPE_DETERMINISTIC_MOCK, PROVIDER_TYPE_METHODOLOGY):
        if provider.provider_type == PROVIDER_TYPE_METHODOLOGY and not policy.allow_methodology_providers:
            return f"Provider '{provider.provider_id}': methodology providers blocked by policy"
        return ""

    if provider.requires_llm and not policy.allow_llm_providers:
        return f"Provider '{provider.provider_id}' requires LLM, blocked by policy"

    if provider.requires_external_service and not policy.allow_external_services:
        return f"Provider '{provider.provider_id}' requires external service, blocked by policy"

    return ""


def validate_provider_against_policy(
    provider,
    policy: DirectionIntelligencePolicy,
) -> Tuple[bool, str]:
    """Validate a DirectionIntelligenceProvider against the policy.

    Returns (allowed, reason).
    """
    reason = block_provider_reason(provider, policy)
    if reason:
        return False, reason
    return True, "OK"


def validate_result_against_policy(
    result,
    policy: DirectionIntelligencePolicy,
) -> Tuple[bool, str]:
    """Validate a DirectionIntelligenceResult against the policy.

    Returns (valid, reason).
    """
    from v3.external.direction_intelligence import DirectionIntelligenceResult

    if not isinstance(result, DirectionIntelligenceResult):
        return False, f"Expected DirectionIntelligenceResult, got {type(result).__name__}"

    if result.blocked:
        return True, "OK"

    if len(result.signals) > policy.max_signals:
        return False, (
            f"Result has {len(result.signals)} signals, max is {policy.max_signals}"
        )

    for signal in result.signals:
        if signal.signal_type in policy.forbidden_signal_types:
            return False, (
                f"Signal '{signal.signal_id}' has forbidden type '{signal.signal_type}'"
            )

    if policy.require_provenance:
        for signal in result.signals:
            if not signal.provenance:
                return False, (
                    f"Signal '{signal.signal_id}' is missing provenance"
                )

    return True, "OK"
