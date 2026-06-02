"""
Alert Policy — Threshold-based alert evaluation.

Defines alert rules against metrics, evaluates them deterministically,
and emits AlertEvent records. No escalation chain — evaluation only.
Notifications are handled by external webhooks (not implemented here).

Inspired by getsentry/sentry error fingerprinting:
  fingerprint = sha256(error_type + file_path + line_number + message_pattern)[:12]

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Alert States
# ═══════════════════════════════════════════════════════════════════════

ALERT_INACTIVE = "inactive"
ALERT_PENDING = "pending"
ALERT_FIRING = "firing"
ALERT_RESOLVED = "resolved"

ALL_ALERT_STATES = (ALERT_INACTIVE, ALERT_PENDING, ALERT_FIRING, ALERT_RESOLVED)

# Severity
SEV_INFO = "info"
SEV_WARNING = "warning"
SEV_CRITICAL = "critical"

ALL_SEVERITIES = (SEV_INFO, SEV_WARNING, SEV_CRITICAL)


# ═══════════════════════════════════════════════════════════════════════
# Alert Rule
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AlertRule:
    """A single alert rule definition.

    Evaluated against current metric values. The for_duration field
    prevents flapping — the condition must hold for at least N seconds
    before transitioning to FIRING.
    """

    rule_id: str = ""
    metric: str = ""               # metric name to monitor
    condition: str = ">"           # ">", "<", "==", ">=", "<="
    threshold: float = 0.0
    for_duration: int = 0          # seconds the condition must persist
    severity: str = SEV_INFO
    description: str = ""

    def evaluate(self, value: float) -> bool:
        """Check if the condition triggers for a given metric value."""
        if self.condition == ">":
            return value > self.threshold
        elif self.condition == "<":
            return value < self.threshold
        elif self.condition == ">=":
            return value >= self.threshold
        elif self.condition == "<=":
            return value <= self.threshold
        elif self.condition == "==":
            return value == self.threshold
        return False

    def fingerprint(self, context: str = "") -> str:
        """Deterministic alert fingerprint for grouping.

        Same pattern as Sentry: sha256(type + metric + condition + threshold)[:12]
        """
        payload = f"{self.metric}:{self.condition}:{self.threshold}:{context}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "metric": self.metric,
            "condition": self.condition,
            "threshold": self.threshold,
            "for_duration": self.for_duration,
            "severity": self.severity,
            "description": self.description,
        }


# ═══════════════════════════════════════════════════════════════════════
# Alert Event
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AlertEvent:
    """Emitted when an AlertRule evaluates to true (or recovers)."""

    event_id: str = ""
    rule_id: str = ""
    state: str = ALERT_INACTIVE    # pending, firing, resolved
    severity: str = SEV_INFO
    metric: str = ""
    current_value: float = 0.0
    threshold: float = 0.0
    condition: str = ">"
    fired_at: float = 0.0
    resolved_at: float = 0.0       # 0 if not resolved
    fingerprint: str = ""
    event_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "rule_id": self.rule_id,
            "state": self.state,
            "severity": self.severity,
            "metric": self.metric,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "condition": self.condition,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
            "fingerprint": self.fingerprint,
            "event_hash": self.event_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Alert Policy
# ═══════════════════════════════════════════════════════════════════════

class AlertPolicy:
    """Evaluates a set of alert rules against current metrics.

    Tracks pending/firing state to implement for_duration logic.
    No escalation chain — fires events, consumer decides next action.
    """

    def __init__(self, rules: Tuple[AlertRule, ...] = ()):
        self._rules = rules
        self._state: dict[str, dict] = {}  # rule_id → {state, first_triggered_at, value}

    @property
    def rules(self) -> Tuple[AlertRule, ...]:
        return self._rules

    def evaluate(self, metrics: dict) -> Tuple[AlertEvent, ...]:
        """Evaluate all rules against the given metrics snapshot.

        metrics: dict[str, float] — e.g. {"cost_usd": 5.0, "error_rate": 0.02, ...}

        Returns a tuple of AlertEvents for rules that changed state.
        Stable rules (no state change) are omitted from output.
        """
        events: list[AlertEvent] = []
        now = time.time()

        for rule in self._rules:
            current_value = metrics.get(rule.metric, 0.0)
            triggered = rule.evaluate(current_value)
            fingerprint = rule.fingerprint()
            prev = self._state.get(rule.rule_id, {
                "state": ALERT_INACTIVE,
                "first_triggered_at": 0.0,
            })

            if triggered:
                if prev["state"] == ALERT_INACTIVE:
                    if rule.for_duration == 0:
                        # No duration — fire immediately, skip PENDING
                        prev = {
                            "state": ALERT_FIRING,
                            "first_triggered_at": now,
                            "value": current_value,
                        }
                        self._state[rule.rule_id] = prev
                        events.append(AlertEvent(
                            event_id=hashlib.sha256(
                                f"{rule.rule_id}:{now}:firing".encode()
                            ).hexdigest()[:16],
                            rule_id=rule.rule_id,
                            state=ALERT_FIRING,
                            severity=rule.severity,
                            metric=rule.metric,
                            current_value=current_value,
                            threshold=rule.threshold,
                            condition=rule.condition,
                            fired_at=now,
                            fingerprint=fingerprint,
                            event_hash="",
                        ))
                    else:
                        # First trigger — enter PENDING, wait for duration
                        prev = {
                            "state": ALERT_PENDING,
                            "first_triggered_at": now,
                            "value": current_value,
                        }
                        self._state[rule.rule_id] = prev
                elif prev["state"] == ALERT_PENDING:
                    # Check if duration threshold is met
                    elapsed = now - prev["first_triggered_at"]
                    if rule.for_duration > 0 and elapsed >= rule.for_duration:
                        # Transition PENDING → FIRING
                        prev = {
                            "state": ALERT_FIRING,
                            "first_triggered_at": prev["first_triggered_at"],
                            "value": current_value,
                        }
                        self._state[rule.rule_id] = prev
                        events.append(AlertEvent(
                            event_id=hashlib.sha256(
                                f"{rule.rule_id}:{now}:firing".encode()
                            ).hexdigest()[:16],
                            rule_id=rule.rule_id,
                            state=ALERT_FIRING,
                            severity=rule.severity,
                            metric=rule.metric,
                            current_value=current_value,
                            threshold=rule.threshold,
                            condition=rule.condition,
                            fired_at=now,
                            fingerprint=fingerprint,
                            event_hash="",
                        ))
                    elif rule.for_duration == 0:
                        # No duration — fire immediately
                        prev["state"] = ALERT_FIRING
                        self._state[rule.rule_id] = prev
                        events.append(AlertEvent(
                            event_id=hashlib.sha256(
                                f"{rule.rule_id}:{now}:firing".encode()
                            ).hexdigest()[:16],
                            rule_id=rule.rule_id,
                            state=ALERT_FIRING,
                            severity=rule.severity,
                            metric=rule.metric,
                            current_value=current_value,
                            threshold=rule.threshold,
                            condition=rule.condition,
                            fired_at=now,
                            fingerprint=fingerprint,
                            event_hash="",
                        ))
                # FIRING stays FIRING (no duplicate events)
            else:
                if prev["state"] in (ALERT_PENDING, ALERT_FIRING):
                    # Rule recovered — emit RESOLVED
                    events.append(AlertEvent(
                        event_id=hashlib.sha256(
                            f"{rule.rule_id}:{now}:resolved".encode()
                        ).hexdigest()[:16],
                        rule_id=rule.rule_id,
                        state=ALERT_RESOLVED,
                        severity=rule.severity,
                        metric=rule.metric,
                        current_value=current_value,
                        threshold=rule.threshold,
                        condition=rule.condition,
                        fired_at=prev.get("first_triggered_at", 0.0),
                        resolved_at=now,
                        fingerprint=fingerprint,
                        event_hash="",
                    ))
                    self._state[rule.rule_id] = {
                        "state": ALERT_INACTIVE,
                        "first_triggered_at": 0.0,
                    }

        # Set event hashes after construction
        result = []
        for e in events:
            event_data = {
                "event_id": e.event_id,
                "rule_id": e.rule_id,
                "state": e.state,
                "current_value": e.current_value,
                "threshold": e.threshold,
                "fired_at": e.fired_at,
            }
            eh = hashlib.sha256(
                json.dumps(event_data, sort_keys=True).encode()
            ).hexdigest()[:16]
            result.append(AlertEvent(
                event_id=e.event_id,
                rule_id=e.rule_id,
                state=e.state,
                severity=e.severity,
                metric=e.metric,
                current_value=e.current_value,
                threshold=e.threshold,
                condition=e.condition,
                fired_at=e.fired_at,
                resolved_at=e.resolved_at,
                fingerprint=e.fingerprint,
                event_hash=eh,
            ))

        return tuple(result)

    def reset(self) -> None:
        """Reset all alert states to INACTIVE."""
        self._state.clear()


# ═══════════════════════════════════════════════════════════════════════
# Default Alert Rules
# ═══════════════════════════════════════════════════════════════════════

def get_default_rules() -> Tuple[AlertRule, ...]:
    """Return the standard set of alert rules.

    These cover the five key risk dimensions:
      - Cost spike
      - Error rate
      - Latency p99
      - Complexity approaching threshold
      - Stability freeze violation
    """
    return (
        AlertRule(
            rule_id="cost_spike",
            metric="cost_usd_daily_ratio",
            condition=">",
            threshold=2.0,           # > 2x daily average
            for_duration=300,         # 5 minutes sustained
            severity=SEV_WARNING,
            description="Daily cost exceeds 2x the moving average — possible runaway loop or model switch.",
        ),
        AlertRule(
            rule_id="error_rate_high",
            metric="error_rate",
            condition=">",
            threshold=0.1,            # > 10% error rate
            for_duration=60,           # 1 minute sustained
            severity=SEV_CRITICAL,
            description="Execution error rate exceeds 10% — possible systemic failure or bad deployment.",
        ),
        AlertRule(
            rule_id="latency_p99_high",
            metric="execution_latency_p99_seconds",
            condition=">",
            threshold=30.0,            # > 30s p99
            for_duration=120,          # 2 minutes sustained
            severity=SEV_WARNING,
            description="p99 execution latency exceeds 30 seconds — possible resource contention.",
        ),
        AlertRule(
            rule_id="complexity_approaching_review",
            metric="complexity_score",
            condition=">",
            threshold=6.5,             # > 6.5 complexity
            for_duration=0,            # immediate
            severity=SEV_INFO,
            description="Complexity score exceeds 6.5 — architecture review recommended.",
        ),
        AlertRule(
            rule_id="freeze_violation",
            metric="stability_freeze_score",
            condition="<",
            threshold=96.0,            # < 96 freeze score
            for_duration=0,            # immediate
            severity=SEV_CRITICAL,
            description="Stability freeze score below 96 — one or more SF invariants may be violated.",
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════

def evaluate_alerts(metrics: dict) -> Tuple[AlertEvent, ...]:
    """Evaluate default rules against the given metrics snapshot.

    Convenience function. For stateful evaluation across multiple
    calls, create and retain an AlertPolicy instance.
    """
    policy = AlertPolicy(rules=get_default_rules())
    return policy.evaluate(metrics)
