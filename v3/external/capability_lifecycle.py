"""
Capability Adapter Lifecycle — Phase 1.

Defines the state machine for capability adapter lifecycle management.
Every external capability adapter follows this lifecycle from proposal
through to deprecation or rejection.

States:
  proposed → registered → inspected → trialed → adapter_ready → approved
  Any state → disabled | rejected | deprecated

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle States
# ═══════════════════════════════════════════════════════════════════════

STATE_PROPOSED = "proposed"
STATE_REGISTERED = "registered"
STATE_INSPECTED = "inspected"
STATE_TRIALED = "trialed"
STATE_ADAPTER_READY = "adapter_ready"
STATE_APPROVED = "approved"
STATE_DEPRECATED = "deprecated"
STATE_DISABLED = "disabled"
STATE_REJECTED = "rejected"

ALL_STATES = (
    STATE_PROPOSED,
    STATE_REGISTERED,
    STATE_INSPECTED,
    STATE_TRIALED,
    STATE_ADAPTER_READY,
    STATE_APPROVED,
    STATE_DEPRECATED,
    STATE_DISABLED,
    STATE_REJECTED,
)

# Forward progression (must go through each gate)
FORWARD_TRANSITIONS = {
    STATE_PROPOSED: STATE_REGISTERED,
    STATE_REGISTERED: STATE_INSPECTED,
    STATE_INSPECTED: STATE_TRIALED,
    STATE_TRIALED: STATE_ADAPTER_READY,
    STATE_ADAPTER_READY: STATE_APPROVED,
}

# Terminal states (require manual intervention to reopen)
TERMINAL_STATES = (STATE_REJECTED, STATE_DISABLED, STATE_DEPRECATED)

# States where the adapter is considered active/usable
ACTIVE_STATES = (STATE_APPROVED, STATE_ADAPTER_READY)


# ═══════════════════════════════════════════════════════════════════════
# Allowed Transitions
# ═══════════════════════════════════════════════════════════════════════

ALLOWED_TRANSITIONS: dict[str, Tuple[str, ...]] = {
    # Forward path
    STATE_PROPOSED: (STATE_REGISTERED, STATE_REJECTED, STATE_DISABLED),
    STATE_REGISTERED: (STATE_INSPECTED, STATE_REJECTED, STATE_DISABLED),
    STATE_INSPECTED: (STATE_TRIALED, STATE_REJECTED, STATE_DISABLED),
    STATE_TRIALED: (STATE_ADAPTER_READY, STATE_REJECTED, STATE_DISABLED),
    STATE_ADAPTER_READY: (STATE_APPROVED, STATE_REJECTED, STATE_DISABLED),
    # Terminal / maintenance
    STATE_APPROVED: (STATE_DEPRECATED, STATE_DISABLED),
    STATE_DEPRECATED: (STATE_DISABLED,),
    STATE_DISABLED: (STATE_PROPOSED,),   # Manual reopen to proposed only
    STATE_REJECTED: (STATE_PROPOSED,),   # Manual reopen to proposed only
}

# Transitions that require human approval
APPROVAL_REQUIRED_TRANSITIONS = {
    (STATE_ADAPTER_READY, STATE_APPROVED),
}


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle Record
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityLifecycleRecord:
    """A single state transition in the adapter lifecycle."""
    adapter_id: str = ""
    state: str = STATE_PROPOSED
    previous_state: str = ""
    reason: str = ""
    approved_by: str = ""
    timestamp: str = ""
    record_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "state": self.state,
            "previous_state": self.previous_state,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "timestamp": self.timestamp,
            "record_hash": self.record_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityLifecyclePolicy:
    """Policy governing adapter lifecycle transitions.

    This is the machine-readable policy that lifecycle validation
    checks against.
    """
    allowed_transitions: dict = field(default_factory=lambda: dict(ALLOWED_TRANSITIONS))
    requires_human_approval: Tuple[Tuple[str, str], ...] = (
        (STATE_ADAPTER_READY, STATE_APPROVED),
    )
    terminal_states: Tuple[str, ...] = TERMINAL_STATES

    def to_dict(self) -> dict:
        return {
            "allowed_transitions": {
                k: list(v) for k, v in sorted(self.allowed_transitions.items())
            },
            "requires_human_approval": [
                list(t) for t in self.requires_human_approval
            ],
            "terminal_states": list(self.terminal_states),
        }


# ═══════════════════════════════════════════════════════════════════════
# Functions
# ═══════════════════════════════════════════════════════════════════════

def validate_lifecycle_transition(
    previous: str,
    next_state: str,
) -> Tuple[bool, str]:
    """Validate a lifecycle state transition.

    Returns (valid, reason).
    """
    if previous not in ALL_STATES:
        return False, f"Unknown previous state: {previous}"
    if next_state not in ALL_STATES:
        return False, f"Unknown next state: {next_state}"

    allowed = ALLOWED_TRANSITIONS.get(previous, ())
    if next_state not in allowed:
        return False, f"Transition '{previous} → {next_state}' not allowed. Allowed: {allowed}"

    # Check for bypass: cannot skip forward stages
    forward_next = FORWARD_TRANSITIONS.get(previous)
    if forward_next:
        # If moving forward (not to terminal), must go to the exact next state
        if next_state not in TERMINAL_STATES and next_state != forward_next:
            return False, (
                f"Cannot skip from '{previous}' to '{next_state}'. "
                f"Must go through '{forward_next}'"
            )

    if (previous, next_state) in APPROVAL_REQUIRED_TRANSITIONS:
        reason_text = f"Transition '{previous} → {next_state}' requires human approval"
        return True, reason_text  # valid, but approval needed

    return True, "OK"


def make_lifecycle_record(
    adapter_id: str,
    state: str,
    previous_state: str = "",
    reason: str = "",
    approved_by: str = "",
    timestamp: Optional[str] = None,
) -> CapabilityLifecycleRecord:
    """Create a lifecycle record with deterministic hash.

    If timestamp is None, uses current UTC time.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    record = CapabilityLifecycleRecord(
        adapter_id=adapter_id,
        state=state,
        previous_state=previous_state,
        reason=reason,
        approved_by=approved_by,
        timestamp=timestamp,
    )

    # Deterministic hash
    hash_input = json.dumps({
        "adapter_id": adapter_id,
        "state": state,
        "previous_state": previous_state,
        "timestamp": timestamp,
    }, sort_keys=True, ensure_ascii=False)
    record_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]
    object.__setattr__(record, "record_hash", record_hash)

    return record


def lifecycle_is_active(state: str) -> bool:
    """Check if a lifecycle state means the adapter is active/usable."""
    return state in ACTIVE_STATES


def lifecycle_is_terminal(state: str) -> bool:
    """Check if a lifecycle state is terminal (requires manual reopen)."""
    return state in TERMINAL_STATES
