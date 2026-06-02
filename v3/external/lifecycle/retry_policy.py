"""
Retry Policy — Exponential backoff and retry decision logic.

Inspired by temporal.io Activity RetryPolicy:
  initial_interval → backoff_coefficient → max_attempts → max_interval

Deterministic. Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Error Classification
# ═══════════════════════════════════════════════════════════════════════

RETRYABLE_ERRORS = frozenset({
    "timeout",
    "connection_error",
    "exit_nonzero",
    "subprocess_error",
    "temporary_failure",
})

NON_RETRYABLE_ERRORS = frozenset({
    "validation_error",
    "permission_denied",
    "not_found",
    "config_error",
    "fatal",
})


def classify_error(error: Exception) -> str:
    """Classify an exception into a retry-relevant error type.

    Deterministic mapping from exception class hierarchy to error type string.
    """
    import subprocess
    import builtins

    name = type(error).__name__

    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, builtins.TimeoutError):
        return "timeout"
    if isinstance(error, subprocess.TimeoutExpired):
        return "timeout"
    if isinstance(error, ConnectionError):
        return "connection_error"
    if isinstance(error, subprocess.CalledProcessError):
        return "exit_nonzero"
    if isinstance(error, (ValueError, TypeError)):
        return "validation_error"
    if isinstance(error, PermissionError):
        return "permission_denied"
    if isinstance(error, FileNotFoundError):
        return "not_found"
    if name.lower().startswith("config"):
        return "config_error"

    # Default: treat unknown errors as subprocess_error (retryable once)
    return "subprocess_error"


# ═══════════════════════════════════════════════════════════════════════
# Retry Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RetryPolicy:
    """Immutable retry strategy definition.

    Controls how many times and how fast a failed operation is retried.
    The backoff formula is:
      delay = min(initial_interval * (backoff_coefficient ^ (attempt-1)), max_interval)
    """

    policy_id: str = ""
    initial_interval: float = 1.0        # seconds before first retry
    backoff_coefficient: float = 2.0     # multiplier per attempt
    max_interval: float = 60.0           # cap on backoff delay
    max_attempts: int = 3                # total attempts including first
    retry_on: Tuple[str, ...] = ("timeout", "connection_error", "exit_nonzero")

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "initial_interval": self.initial_interval,
            "backoff_coefficient": self.backoff_coefficient,
            "max_interval": self.max_interval,
            "max_attempts": self.max_attempts,
            "retry_on": list(self.retry_on),
        }


@dataclass(frozen=True)
class RetryResult:
    """Outcome of a retry sequence."""

    attempt: int = 0
    error_type: Optional[str] = None
    duration_ms: float = 0.0
    final_success: bool = False
    total_attempts: int = 0

    def to_dict(self) -> dict:
        return {
            "attempt": self.attempt,
            "error_type": self.error_type,
            "duration_ms": self.duration_ms,
            "final_success": self.final_success,
            "total_attempts": self.total_attempts,
        }


# ═══════════════════════════════════════════════════════════════════════
# Backoff Calculation
# ═══════════════════════════════════════════════════════════════════════

def calculate_backoff(policy: RetryPolicy, attempt: int) -> float:
    """Calculate the backoff delay for a given retry attempt.

    Formula: min(initial_interval * (backoff_coefficient ^ (attempt-1)), max_interval)

    attempt=0 → 0 (first try, no delay)
    attempt=1 → 1 * 2^0 = 1s (first retry after initial failure)
    attempt=2 → 1 * 2^1 = 2s
    attempt=3 → 1 * 2^2 = 4s (capped at max_interval)
    """
    if attempt < 0:
        raise ValueError(f"Attempt must be >= 0, got {attempt}")
    if attempt == 0:
        return 0.0
    delay = policy.initial_interval * (policy.backoff_coefficient ** (attempt - 1))
    return min(delay, policy.max_interval)


def should_retry(policy: RetryPolicy, attempt: int, error_type: str) -> bool:
    """Determine whether to retry based on policy and error type.

    Returns True if:
      - The current attempt count (0-indexed) is less than max_attempts - 1
      - The error_type is in the policy's retry_on set
    """
    if attempt + 1 >= policy.max_attempts:
        return False
    if error_type not in policy.retry_on:
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════
# Predefined Policies
# ═══════════════════════════════════════════════════════════════════════

def policy_quick() -> RetryPolicy:
    """Quick retry: 2 attempts, 0.5s initial. For fast CLI commands."""
    return RetryPolicy(
        policy_id="quick",
        initial_interval=0.5,
        backoff_coefficient=2.0,
        max_interval=10.0,
        max_attempts=2,
        retry_on=("timeout", "exit_nonzero"),
    )


def policy_standard() -> RetryPolicy:
    """Standard retry: 3 attempts, 1s initial. For subprocess calls."""
    return RetryPolicy(
        policy_id="standard",
        initial_interval=1.0,
        backoff_coefficient=2.0,
        max_interval=30.0,
        max_attempts=3,
        retry_on=("timeout", "connection_error", "exit_nonzero", "subprocess_error"),
    )


def policy_resilient() -> RetryPolicy:
    """Resilient retry: 5 attempts, 2s initial, 3x backoff. For network-dependent ops."""
    return RetryPolicy(
        policy_id="resilient",
        initial_interval=2.0,
        backoff_coefficient=3.0,
        max_interval=60.0,
        max_attempts=5,
        retry_on=("timeout", "connection_error", "exit_nonzero", "subprocess_error", "temporary_failure"),
    )


# ═══════════════════════════════════════════════════════════════════════
# Backoff Table (for verification)
# ═══════════════════════════════════════════════════════════════════════

def backoff_table(policy: RetryPolicy) -> Tuple[Tuple[int, float], ...]:
    """Generate a backoff table for verification. (attempt_number, delay_seconds)."""
    return tuple(
        (i, calculate_backoff(policy, i))
        for i in range(policy.max_attempts + 1)
    )
