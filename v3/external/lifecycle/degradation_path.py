"""
Degradation Path — Graceful degradation when providers fail.

When a provider becomes unavailable (subprocess crash, network timeout,
version mismatch), the system degrades to a lower capability level
instead of failing hard.

Inspired by circuit-breaker patterns: each provider has a degradation
level that determines which fallback behavior to use.

Does NOT modify kernel internals. Degradation events are recorded
as governance evidence, not truth.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Degradation Levels
# ═══════════════════════════════════════════════════════════════════════

DEGRADATION_FULL = "full"          # All providers operational
DEGRADATION_DEGRADED = "degraded"  # One or more providers degraded
DEGRADATION_MINIMAL = "minimal"    # Core-only, most providers offline
DEGRADATION_OFFLINE = "offline"    # All non-kernel providers unavailable

ALL_DEGRADATION_LEVELS = (
    DEGRADATION_FULL,
    DEGRADATION_DEGRADED,
    DEGRADATION_MINIMAL,
    DEGRADATION_OFFLINE,
)

# Severity order (for determining overall level)
LEVEL_SEVERITY = {
    DEGRADATION_FULL: 0,
    DEGRADATION_DEGRADED: 1,
    DEGRADATION_MINIMAL: 2,
    DEGRADATION_OFFLINE: 3,
}


# ═══════════════════════════════════════════════════════════════════════
# Degradation Rule
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DegradationRule:
    """A single degradation rule for a provider.

    When the condition is met (provider unavailable), the system degrades
    to the specified level and uses the fallback behavior.
    """

    rule_id: str = ""
    target: str = ""               # provider_id or capability_type
    condition: str = ""            # human-readable trigger description
    on_degrade: str = DEGRADATION_DEGRADED
    fallback_behavior: str = ""    # "retry_stale", "use_cache", "skip", "error"
    auto_restore: bool = True      # whether to auto-restore when provider recovers

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "target": self.target,
            "condition": self.condition,
            "on_degrade": self.on_degrade,
            "fallback_behavior": self.fallback_behavior,
            "auto_restore": self.auto_restore,
        }


# ═══════════════════════════════════════════════════════════════════════
# Degradation Manager
# ═══════════════════════════════════════════════════════════════════════

class DegradationManager:
    """Manages provider degradation levels with fallback behavior.

    Tracks each provider's current degradation state and computes the
    overall system degradation level (worst of all providers).
    """

    def __init__(self, rules: Tuple[DegradationRule, ...] = ()):
        self._rules = rules
        self._provider_levels: dict[str, str] = {}    # target → level
        self._degradation_history: list[dict] = []     # audit trail
        for rule in rules:
            self._provider_levels[rule.target] = DEGRADATION_FULL

    @property
    def rules(self) -> Tuple[DegradationRule, ...]:
        return self._rules

    @property
    def current_level(self) -> str:
        """Compute overall system degradation level (worst of all providers)."""
        if not self._provider_levels:
            return DEGRADATION_FULL
        worst = DEGRADATION_FULL
        worst_sev = 0
        for target, level in self._provider_levels.items():
            sev = LEVEL_SEVERITY.get(level, 0)
            if sev > worst_sev:
                worst = level
                worst_sev = sev
        return worst

    def degrade(self, rule_id: str, reason: str = "") -> str:
        """Degrade a provider per its rule. Returns the new overall level."""
        rule = self._find_rule(rule_id)
        if rule is None:
            raise ValueError(f"Degradation rule not found: {rule_id}")

        self._provider_levels[rule.target] = rule.on_degrade
        self._degradation_history.append({
            "timestamp": time.time(),
            "event": "degrade",
            "rule_id": rule_id,
            "target": rule.target,
            "to_level": rule.on_degrade,
            "reason": reason,
        })
        return self.current_level

    def restore(self, rule_id: str) -> str:
        """Restore a provider to FULL. Returns the new overall level."""
        rule = self._find_rule(rule_id)
        if rule is None:
            raise ValueError(f"Degradation rule not found: {rule_id}")

        self._provider_levels[rule.target] = DEGRADATION_FULL
        self._degradation_history.append({
            "timestamp": time.time(),
            "event": "restore",
            "rule_id": rule_id,
            "target": rule.target,
            "to_level": DEGRADATION_FULL,
        })
        return self.current_level

    def check(self, target: str) -> str:
        """Get the current degradation level for a specific provider.

        Returns DEGRADATION_FULL if the target has no degradation rule.
        """
        return self._provider_levels.get(target, DEGRADATION_FULL)

    def get_fallback(self, target: str) -> str:
        """Get the fallback behavior for a provider's current level.

        Returns "error" if the target has no degradation rule.
        """
        rule = self._find_rule(target)
        if rule is None:
            return "error"
        return rule.fallback_behavior

    def _find_rule(self, rule_id: str) -> Optional[DegradationRule]:
        for rule in self._rules:
            if rule.rule_id == rule_id or rule.target == rule_id:
                return rule
        return None

    def status_report(self) -> dict:
        """Return a full status report of all provider levels."""
        return {
            "overall_level": self.current_level,
            "providers": dict(self._provider_levels),
            "history_count": len(self._degradation_history),
            "rules_count": len(self._rules),
        }


# ═══════════════════════════════════════════════════════════════════════
# Default Degradation Rules
# ═══════════════════════════════════════════════════════════════════════

def get_default_degradation_rules() -> Tuple[DegradationRule, ...]:
    """Standard degradation rules for Phase 16a providers.

    Each rule defines what happens when a specific external provider
    becomes unavailable. Fallback behaviors are chosen to minimize
    impact on the kernel while being explicit about degradation.
    """
    return (
        DegradationRule(
            rule_id="mem0_unavailable",
            target="mem0",
            condition="mem0 API unreachable or auth failure",
            on_degrade=DEGRADATION_DEGRADED,
            fallback_behavior="skip",
            auto_restore=True,
        ),
        DegradationRule(
            rule_id="graphiti_unavailable",
            target="graphiti",
            condition="Graphiti temporal knowledge graph unreachable",
            on_degrade=DEGRADATION_DEGRADED,
            fallback_behavior="skip",
            auto_restore=True,
        ),
        DegradationRule(
            rule_id="sandbox_timeout",
            target="sandbox",
            condition="Sandbox provider timeout or crash",
            on_degrade=DEGRADATION_DEGRADED,
            fallback_behavior="error",
            auto_restore=True,
        ),
        DegradationRule(
            rule_id="ccusage_unavailable",
            target="ccusage",
            condition="ccusage CLI not found or returns error",
            on_degrade=DEGRADATION_MINIMAL,
            fallback_behavior="use_cache",
            auto_restore=True,
        ),
        DegradationRule(
            rule_id="repomix_unavailable",
            target="repomix",
            condition="Repomix context pack generation failure",
            on_degrade=DEGRADATION_DEGRADED,
            fallback_behavior="error",
            auto_restore=True,
        ),
    )
