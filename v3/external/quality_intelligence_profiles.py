"""
Quality Intelligence Provider Profiles — v4.1.

Defines provider profiles for quality intelligence (superpowers methodology).
Profiles are DESCRIPTIONS, not integrations. No provider imports, executes,
or connects to external services.

All profiles: truth_source=False, removable=True.

Default policy allows methodology providers (analysis-only, no execution).
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
    requires_external_service: bool = False,
    methodology_source: str = "",
    description: str = "",
) -> "QualityIntelligenceProvider":
    """Build a deterministic provider with hash."""
    from v3.external.quality_intelligence import (
        QualityIntelligenceProvider,
        MODE_INSPECT_ONLY,
        _compute_hash as qi_hash,
    )

    provider = QualityIntelligenceProvider(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        capability_type="quality",
        execution_mode=MODE_INSPECT_ONLY,
        requires_llm=requires_llm,
        requires_external_service=requires_external_service,
        methodology_source=methodology_source,
        truth_source=False,
        removable=True,
        description=description,
    )
    object.__setattr__(provider, "provider_hash", qi_hash(provider))
    return provider


# ═══════════════════════════════════════════════════════════════════════
# superpowers Profile (ALLOWED by default — methodology-based analysis)
# ═══════════════════════════════════════════════════════════════════════

def superpowers_quality_profile() -> "QualityIntelligenceProvider":
    """superpowers quality intelligence provider profile.

    ALLOWED by default policy:
    - provider_type=methodology → allowed (analysis-only)
    - requires_llm=False → passes
    - requires_external_service=False → passes

    superpowers provides a methodology for quality evaluation:
    - test-driven-development: RED-GREEN-REFACTOR, testing anti-patterns
    - systematic-debugging: 4-phase root cause process
    - writing-plans: Bite-sized tasks, exact file paths, verification steps
    - requesting-code-review: Pre-review checklist, severity levels
    - verification-before-completion: Evidence over claims
    - brainstorming: Socratic design refinement

    This is a METHODOLOGY profile — superpowers is not executed.
    Its principles are used as an evaluation rubric for quality signals.
    """
    return _build_provider(
        provider_id="superpowers_quality_intelligence",
        name="superpowers Quality Intelligence",
        provider_type="methodology",
        requires_llm=False,
        requires_external_service=False,
        methodology_source="https://github.com/obra/superpowers",
        description=(
            "Quality evaluation intelligence using superpowers methodology. "
            "Provides defect detection, anti-pattern identification, improvement "
            "suggestions, and refinement recommendations based on superpowers' "
            "TDD discipline, systematic debugging, plan structure review, "
            "and verification standards. "
            "Analysis-only — never rewrites code, never overrides decisions. "
            "ALLOWED by default policy."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Deterministic Mock Profile (ALLOWED by default)
# ═══════════════════════════════════════════════════════════════════════

def deterministic_mock_quality_profile() -> "QualityIntelligenceProvider":
    """Deterministic mock quality intelligence provider profile.

    ALLOWED by default policy. Used for testing the quality plane.
    """
    return _build_provider(
        provider_id="deterministic_mock_quality",
        name="Deterministic Mock Quality Intelligence",
        provider_type="deterministic_mock",
        requires_llm=False,
        requires_external_service=False,
        methodology_source="",
        description=(
            "Deterministic mock quality intelligence provider. "
            "Produces synthetic quality signals from fixture input. "
            "Always deterministic — same input → same output. "
            "ALLOWED by default policy."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Profile Registry
# ═══════════════════════════════════════════════════════════════════════

def get_all_profiles() -> Tuple["QualityIntelligenceProvider", ...]:
    """Return all registered quality intelligence provider profiles."""
    profiles = (
        superpowers_quality_profile(),
        deterministic_mock_quality_profile(),
    )
    return tuple(sorted(profiles, key=lambda p: p.provider_id))


def get_profile(provider_id: str) -> Optional["QualityIntelligenceProvider"]:
    """Get a single provider profile by ID. Returns None if not found."""
    for p in get_all_profiles():
        if p.provider_id == provider_id:
            return p
    return None


def evaluate_all_profiles(policy) -> Tuple[ProviderProfileStatus, ...]:
    """Evaluate all provider profiles against a policy."""
    from v3.external.quality_intelligence_policy import validate_provider_against_policy

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
