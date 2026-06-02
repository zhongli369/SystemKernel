"""
Lifecycle Manager — Task lifecycle state machine with crash recovery.

Inspired by n8n-io/n8n Execution Node state model:
  idle → running → success | error | waiting → retry → running

Every state transition is validated deterministically. Illegal transitions
raise LifecycleStateError. Crash recovery reads checkpoints from the
existing v3/kernel/checkpoint.py module.

Does NOT modify v3/kernel/execution_engine.py — wraps externally.
Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle States
# ═══════════════════════════════════════════════════════════════════════

LIFECYCLE_IDLE = "idle"
LIFECYCLE_RUNNING = "running"
LIFECYCLE_SUCCESS = "success"
LIFECYCLE_ERROR = "error"
LIFECYCLE_RETRYING = "retrying"
LIFECYCLE_CRASHED = "crashed"
LIFECYCLE_RECOVERING = "recovering"
LIFECYCLE_PAUSED = "paused"
LIFECYCLE_TIMEOUT = "timeout"
LIFECYCLE_CANCELLED = "cancelled"

ALL_LIFECYCLE_STATES = (
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

TERMINAL_STATES = (LIFECYCLE_SUCCESS, LIFECYCLE_ERROR, LIFECYCLE_CANCELLED)

# Legal state transitions
VALID_TRANSITIONS = {
    LIFECYCLE_IDLE:       (LIFECYCLE_RUNNING, LIFECYCLE_CANCELLED),
    LIFECYCLE_RUNNING:    (LIFECYCLE_SUCCESS, LIFECYCLE_ERROR, LIFECYCLE_CRASHED,
                           LIFECYCLE_PAUSED, LIFECYCLE_TIMEOUT, LIFECYCLE_CANCELLED),
    LIFECYCLE_RETRYING:   (LIFECYCLE_RUNNING, LIFECYCLE_CANCELLED),
    LIFECYCLE_CRASHED:    (LIFECYCLE_RECOVERING, LIFECYCLE_ERROR, LIFECYCLE_CANCELLED),
    LIFECYCLE_RECOVERING: (LIFECYCLE_RUNNING, LIFECYCLE_ERROR, LIFECYCLE_CANCELLED),
    LIFECYCLE_PAUSED:     (LIFECYCLE_RUNNING, LIFECYCLE_CANCELLED),
    LIFECYCLE_TIMEOUT:    (LIFECYCLE_RETRYING, LIFECYCLE_ERROR, LIFECYCLE_CANCELLED),
    # Terminal states have no outgoing transitions
    LIFECYCLE_SUCCESS:    (),
    LIFECYCLE_ERROR:      (),
    LIFECYCLE_CANCELLED:  (),
}


class LifecycleStateError(Exception):
    """Raised on illegal state transitions."""
    pass


class TaskLifecycleState:
    """Enum-like state with transition validation."""

    def __init__(self, state: str = LIFECYCLE_IDLE):
        if state not in ALL_LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle state: {state}")
        self._state = state

    @property
    def value(self) -> str:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    def can_transition_to(self, target: str) -> bool:
        return target in VALID_TRANSITIONS.get(self._state, ())

    def transition_to(self, target: str) -> "TaskLifecycleState":
        if not self.can_transition_to(target):
            raise LifecycleStateError(
                f"Illegal transition: {self._state} → {target}. "
                f"Allowed: {VALID_TRANSITIONS.get(self._state, ())}"
            )
        return TaskLifecycleState(target)

    def __eq__(self, other) -> bool:
        if isinstance(other, TaskLifecycleState):
            return self._state == other._state
        if isinstance(other, str):
            return self._state == other
        return False

    def __hash__(self) -> int:
        return hash(self._state)

    def __repr__(self) -> str:
        return f"TaskLifecycleState({self._state!r})"


# ═══════════════════════════════════════════════════════════════════════
# Task Lifecycle
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TaskLifecycle:
    """Immutable snapshot of a task's lifecycle state."""

    task_id: str = ""
    state: str = LIFECYCLE_IDLE
    created_at: float = 0.0
    started_at: Optional[float] = None
    heartbeat_at: Optional[float] = None
    attempts: int = 0
    max_attempts: int = 3
    checkpoints: Tuple[str, ...] = ()     # checkpoint file paths
    last_error: str = ""                   # last error message
    last_error_type: str = ""              # classified error type

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "state": self.state,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "heartbeat_at": self.heartbeat_at,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "checkpoints": list(self.checkpoints),
            "last_error": self.last_error,
            "last_error_type": self.last_error_type,
        }


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle Manager
# ═══════════════════════════════════════════════════════════════════════

class LifecycleManager:
    """Manages task lifecycles with retry, heartbeat, and crash recovery.

    Wraps external execution (does NOT modify kernel execution_engine.py).
    All state transitions are validated — illegal transitions raise errors.
    """

    def __init__(self, heartbeat_interval: float = 30.0):
        self._tasks: dict[str, TaskLifecycle] = {}
        self._heartbeat_interval = heartbeat_interval

    @property
    def active_tasks(self) -> dict[str, TaskLifecycle]:
        return dict(self._tasks)

    def _update_task(self, task: TaskLifecycle) -> None:
        self._tasks[task.task_id] = task

    # ── Lifecycle Operations ──────────────────────────────────────────

    def start(self, task_id: str = "", max_attempts: int = 3) -> TaskLifecycle:
        """Create and start a new task. IDLE → RUNNING."""
        if not task_id:
            task_id = str(uuid.uuid4())[:16]
        if task_id in self._tasks:
            existing = self._tasks[task_id]
            if existing.state == LIFECYCLE_RUNNING:
                raise LifecycleStateError(
                    f"Task {task_id} is already RUNNING"
                )
        now = time.time()
        task = TaskLifecycle(
            task_id=task_id,
            state=LIFECYCLE_RUNNING,
            created_at=now,
            started_at=now,
            heartbeat_at=now,
            attempts=1,
            max_attempts=max_attempts,
        )
        self._update_task(task)
        return task

    def heartbeat(self, task_id: str) -> None:
        """Update heartbeat timestamp. Must be in RUNNING state."""
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state != LIFECYCLE_RUNNING:
            raise LifecycleStateError(
                f"Cannot heartbeat task {task_id} in state {task.state}. Must be RUNNING."
            )
        now = time.time()
        updated = TaskLifecycle(
            task_id=task.task_id,
            state=task.state,
            created_at=task.created_at,
            started_at=task.started_at,
            heartbeat_at=now,
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=task.last_error,
            last_error_type=task.last_error_type,
        )
        self._update_task(updated)

    def succeed(self, task_id: str) -> TaskLifecycle:
        """Mark task as successful. RUNNING → SUCCESS."""
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state != LIFECYCLE_RUNNING:
            raise LifecycleStateError(
                f"Cannot succeed task {task_id} in state {task.state}. Must be RUNNING."
            )
        updated = TaskLifecycle(
            task_id=task.task_id,
            state=LIFECYCLE_SUCCESS,
            created_at=task.created_at,
            started_at=task.started_at,
            heartbeat_at=task.heartbeat_at,
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=task.last_error,
            last_error_type=task.last_error_type,
        )
        self._update_task(updated)
        return updated

    def fail(
        self,
        task_id: str,
        error: Optional[Exception] = None,
        error_type: str = "",
        should_retry_fn=None,
    ) -> TaskLifecycle:
        """Record failure. RUNNING → RETRYING or ERROR depending on retry policy.

        If should_retry_fn is provided and returns True, transitions to RETRYING.
        Otherwise transitions to ERROR (terminal).
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state != LIFECYCLE_RUNNING:
            raise LifecycleStateError(
                f"Cannot fail task {task_id} in state {task.state}. Must be RUNNING."
            )

        err_msg = str(error) if error else ""
        if not error_type:
            from v3.external.lifecycle.retry_policy import classify_error
            error_type = classify_error(error) if error else "unknown"

        # Determine next state
        if should_retry_fn and callable(should_retry_fn) and should_retry_fn():
            next_state = LIFECYCLE_RETRYING
        elif task.attempts < task.max_attempts and error_type in (
            "timeout", "connection_error", "exit_nonzero", "subprocess_error", "temporary_failure",
        ):
            next_state = LIFECYCLE_RETRYING
        else:
            next_state = LIFECYCLE_ERROR

        updated = TaskLifecycle(
            task_id=task.task_id,
            state=next_state,
            created_at=task.created_at,
            started_at=task.started_at,
            heartbeat_at=task.heartbeat_at,
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=err_msg,
            last_error_type=error_type,
        )
        self._update_task(updated)
        return updated

    def retry(self, task_id: str) -> TaskLifecycle:
        """Resume task after retry delay. RETRYING → RUNNING."""
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state not in (LIFECYCLE_RETRYING, LIFECYCLE_TIMEOUT):
            raise LifecycleStateError(
                f"Cannot retry task {task_id} in state {task.state}. Must be RETRYING or TIMEOUT."
            )
        now = time.time()
        updated = TaskLifecycle(
            task_id=task.task_id,
            state=LIFECYCLE_RUNNING,
            created_at=task.created_at,
            started_at=now,
            heartbeat_at=now,
            attempts=task.attempts + 1,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=task.last_error,
            last_error_type=task.last_error_type,
        )
        self._update_task(updated)
        return updated

    def crash(self, task_id: str, error: str = "") -> TaskLifecycle:
        """Mark task as crashed. RUNNING → CRASHED."""
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state != LIFECYCLE_RUNNING:
            raise LifecycleStateError(
                f"Cannot crash task {task_id} in state {task.state}. Must be RUNNING."
            )
        updated = TaskLifecycle(
            task_id=task.task_id,
            state=LIFECYCLE_CRASHED,
            created_at=task.created_at,
            started_at=task.started_at,
            heartbeat_at=task.heartbeat_at,
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=error,
            last_error_type="crash",
        )
        self._update_task(updated)
        return updated

    def recover(self, task_id: str) -> TaskLifecycle:
        """Recover task from checkpoint. CRASHED → RECOVERING → RUNNING.

        Checkpoint loading is delegated to v3/kernel/checkpoint.py.
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state != LIFECYCLE_CRASHED:
            raise LifecycleStateError(
                f"Cannot recover task {task_id} in state {task.state}. Must be CRASHED."
            )

        # Transition CRASHED → RECOVERING
        recovering = TaskLifecycle(
            task_id=task.task_id,
            state=LIFECYCLE_RECOVERING,
            created_at=task.created_at,
            started_at=time.time(),
            heartbeat_at=time.time(),
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=task.last_error,
            last_error_type=task.last_error_type,
        )
        self._update_task(recovering)

        # Transition RECOVERING → RUNNING (checkpoint reloaded)
        now = time.time()
        running = TaskLifecycle(
            task_id=task.task_id,
            state=LIFECYCLE_RUNNING,
            created_at=task.created_at,
            started_at=now,
            heartbeat_at=now,
            attempts=task.attempts + 1,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=task.last_error,
            last_error_type=task.last_error_type,
        )
        self._update_task(running)
        return running

    def pause(self, task_id: str) -> TaskLifecycle:
        """Pause a running task. RUNNING → PAUSED."""
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state != LIFECYCLE_RUNNING:
            raise LifecycleStateError(
                f"Cannot pause task {task_id} in state {task.state}. Must be RUNNING."
            )
        updated = TaskLifecycle(
            task_id=task.task_id,
            state=LIFECYCLE_PAUSED,
            created_at=task.created_at,
            started_at=task.started_at,
            heartbeat_at=task.heartbeat_at,
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=task.last_error,
            last_error_type=task.last_error_type,
        )
        self._update_task(updated)
        return updated

    def resume(self, task_id: str) -> TaskLifecycle:
        """Resume a paused task. PAUSED → RUNNING."""
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state != LIFECYCLE_PAUSED:
            raise LifecycleStateError(
                f"Cannot resume task {task_id} in state {task.state}. Must be PAUSED."
            )
        updated = TaskLifecycle(
            task_id=task.task_id,
            state=LIFECYCLE_RUNNING,
            created_at=task.created_at,
            started_at=time.time(),
            heartbeat_at=time.time(),
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=task.last_error,
            last_error_type=task.last_error_type,
        )
        self._update_task(updated)
        return updated

    def cancel(self, task_id: str) -> TaskLifecycle:
        """Cancel a task from any non-terminal state."""
        task = self._tasks.get(task_id)
        if task is None:
            raise LifecycleStateError(f"Task {task_id} not found")
        if task.state in TERMINAL_STATES:
            raise LifecycleStateError(
                f"Cannot cancel task {task_id}: already in terminal state {task.state}."
            )
        updated = TaskLifecycle(
            task_id=task.task_id,
            state=LIFECYCLE_CANCELLED,
            created_at=task.created_at,
            started_at=task.started_at,
            heartbeat_at=task.heartbeat_at,
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            checkpoints=task.checkpoints,
            last_error=task.last_error,
            last_error_type=task.last_error_type,
        )
        self._update_task(updated)
        return updated

    # ── Health ────────────────────────────────────────────────────────

    def orphan_detection(self) -> Tuple[str, ...]:
        """Detect tasks with stale heartbeats.

        A task is orphaned if:
          - State is RUNNING
          - heartbeat_at is older than 3x heartbeat_interval seconds ago

        Returns tuple of orphaned task_ids.
        """
        now = time.time()
        threshold = 3 * self._heartbeat_interval
        orphans = []
        for task_id, task in self._tasks.items():
            if task.state == LIFECYCLE_RUNNING and task.heartbeat_at is not None:
                if now - task.heartbeat_at > threshold:
                    orphans.append(task_id)
        return tuple(orphans)

    def get_task(self, task_id: str) -> Optional[TaskLifecycle]:
        """Get a task's current lifecycle state."""
        return self._tasks.get(task_id)


# ═══════════════════════════════════════════════════════════════════════
# Execution Wrapper (external wrapping of kernel execution_engine)
# ═══════════════════════════════════════════════════════════════════════

def execute_with_lifecycle(
    execute_fn,
    task_id: str = "",
    lifecycle_mgr: Optional[LifecycleManager] = None,
    retry_policy=None,
    max_attempts: int = 3,
) -> dict:
    """Wrap an external execution function with lifecycle management.

    Does NOT modify v3/kernel/execution_engine.py. This is an external
    wrapper that adds retry + lifecycle tracking to any callable.

    Returns:
      {
        "result": any,              # execute_fn return value
        "lifecycle": TaskLifecycle,  # final lifecycle state
        "success": bool,
        "attempts": int,
        "total_duration_ms": float,
      }
    """
    from v3.external.lifecycle.retry_policy import (
        calculate_backoff, should_retry, classify_error, policy_standard,
    )
    import time as _time

    if lifecycle_mgr is None:
        lifecycle_mgr = LifecycleManager()
    if retry_policy is None:
        retry_policy = policy_standard()

    lifecycle = lifecycle_mgr.start(task_id=task_id, max_attempts=max_attempts)
    start_time = _time.time()

    for attempt in range(max_attempts):
        try:
            result = execute_fn()
            lifecycle = lifecycle_mgr.succeed(lifecycle.task_id)
            duration = (_time.time() - start_time) * 1000
            return {
                "result": result,
                "lifecycle": lifecycle,
                "success": True,
                "attempts": attempt + 1,
                "total_duration_ms": round(duration, 2),
            }
        except Exception as e:
            error_type = classify_error(e)
            if should_retry(retry_policy, attempt, error_type):
                lifecycle = lifecycle_mgr.fail(lifecycle.task_id, e, error_type)
                delay = calculate_backoff(retry_policy, attempt + 1)
                _time.sleep(delay)
                lifecycle = lifecycle_mgr.retry(lifecycle.task_id)
            else:
                lifecycle = lifecycle_mgr.fail(lifecycle.task_id, e, error_type)
                duration = (_time.time() - start_time) * 1000
                return {
                    "result": None,
                    "lifecycle": lifecycle,
                    "success": False,
                    "attempts": attempt + 1,
                    "total_duration_ms": round(duration, 2),
                    "error": str(e),
                    "error_type": error_type,
                }

    # Exhausted all attempts
    lifecycle = lifecycle_mgr.fail(lifecycle.task_id, error_type="max_attempts_exceeded")
    duration = (_time.time() - start_time) * 1000
    return {
        "result": None,
        "lifecycle": lifecycle,
        "success": False,
        "attempts": max_attempts,
        "total_duration_ms": round(duration, 2),
        "error": "Max attempts exceeded",
        "error_type": "max_attempts_exceeded",
    }
