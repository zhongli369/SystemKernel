"""
L4 Lifecycle Management — Phase 15c.

Retry policies, task lifecycle state machine, and graceful degradation.
Wraps external execution with crash recovery, heartbeat monitoring,
and provider health-based degradation.

Does NOT modify v3/kernel/execution_engine.py (frozen zone).
All lifecycle logic is external wrapping, not kernel internals.

Inspired by:
  - temporal.io: Activity Heartbeat + Retry Policy concepts
  - n8n-io/n8n: Execution Node state model
  - dagger/dagger: Pipeline cache invalidation strategy

Stdlib only. No external dependencies.
"""

from v3.external.lifecycle.retry_policy import (
    RetryPolicy,
    RetryResult,
    calculate_backoff,
    should_retry,
    classify_error,
    policy_quick,
    policy_standard,
    policy_resilient,
)

from v3.external.lifecycle.lifecycle_manager import (
    TaskLifecycleState,
    TaskLifecycle,
    LifecycleManager,
    execute_with_lifecycle,
    LIFECYCLE_IDLE,
    LIFECYCLE_RUNNING,
    LIFECYCLE_SUCCESS,
    LIFECYCLE_ERROR,
    LIFECYCLE_RETRYING,
    LIFECYCLE_CRASHED,
    LIFECYCLE_RECOVERING,
    LIFECYCLE_PAUSED,
    LIFECYCLE_TIMEOUT,
    LIFECYCLE_CANCELLED,
)

from v3.external.lifecycle.degradation_path import (
    DegradationRule,
    DegradationManager,
    DEGRADATION_FULL,
    DEGRADATION_DEGRADED,
    DEGRADATION_MINIMAL,
    DEGRADATION_OFFLINE,
    get_default_degradation_rules,
)
