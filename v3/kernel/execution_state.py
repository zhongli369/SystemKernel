"""
ExecutionState — Frozen lifecycle tracker for deterministic execution runs.

Tracks the lifecycle of one execution: which stage is active, which stages
have completed, the overall status, retry counts, and event counts.

Fully immutable: every mutation returns a new frozen dataclass instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Tuple
import hashlib


# ═══════════════════════════════════════════════════════════════════════
# Status Enums
# ═══════════════════════════════════════════════════════════════════════

class ExecutionStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CRASHED = "CRASHED"

    ALL = {PENDING, RUNNING, COMPLETED, FAILED, CRASHED}


class StageStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    ALL = {PENDING, RUNNING, COMPLETED, FAILED}


# ═══════════════════════════════════════════════════════════════════════
# StageProgress — per-stage tracking
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StageProgress:
    """Immutable record of one pipeline stage's execution progress."""

    stage_name: str
    status: str = StageStatus.PENDING
    result: Optional[dict] = None
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "stage_name": self.stage_name,
            "status": self.status,
            "result": self.result,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════════════
# ExecutionState — lifecycle tracker
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExecutionState:
    """Frozen execution lifecycle tracker.

    Tracks the lifecycle of ONE execution run. Every mutation returns a
    new instance — the original is never modified.

    Fields:
        execution_id: Unique identifier for this execution run
        current_stage: Name of the currently active stage
        current_stage_index: Index of current stage in the pipeline
        completed_stages: Tuple of stage names that have passed
        stage_progress: Per-stage tracking records (Tuple of dicts for JSON compat)
        event_count: Total checkpoint/memory events emitted
        started_at: ISO-8601 timestamp when execution began
        updated_at: ISO-8601 timestamp of last mutation
        status: One of ExecutionStatus values
        retry_count: Total retries across all stages
        metadata: Extensible key-value store
    """

    execution_id: str
    current_stage: str = ""
    current_stage_index: int = 0
    completed_stages: Tuple[str, ...] = ()
    stage_progress: Tuple[dict, ...] = ()
    event_count: int = 0
    started_at: str = ""
    updated_at: str = ""
    status: str = ExecutionStatus.PENDING
    retry_count: int = 0
    metadata: dict = field(default_factory=dict)

    # ── Lifecycle transitions ─────────────────────────────────────────

    def start(self) -> "ExecutionState":
        """Mark execution as RUNNING. Sets started_at timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        return ExecutionState(
            execution_id=self.execution_id,
            current_stage=self.current_stage,
            current_stage_index=self.current_stage_index,
            completed_stages=self.completed_stages,
            stage_progress=self.stage_progress,
            event_count=self.event_count,
            started_at=now,
            updated_at=now,
            status=ExecutionStatus.RUNNING,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    def start_stage(self, stage_name: str) -> "ExecutionState":
        """Begin executing a stage. Marks stage as RUNNING in progress."""
        now = datetime.now(timezone.utc).isoformat()
        new_progress = list(self.stage_progress)
        new_progress.append(StageProgress(
            stage_name=stage_name,
            status=StageStatus.RUNNING,
            started_at=now,
        ).to_dict())
        return ExecutionState(
            execution_id=self.execution_id,
            current_stage=stage_name,
            current_stage_index=len(new_progress) - 1,
            completed_stages=self.completed_stages,
            stage_progress=tuple(new_progress),
            event_count=self.event_count,
            started_at=self.started_at,
            updated_at=now,
            status=ExecutionStatus.RUNNING,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    def advance(
        self, stage_name: str, result: Optional[dict] = None, duration_ms: int = 0
    ) -> "ExecutionState":
        """Mark a stage as COMPLETED. Appends to completed_stages."""
        now = datetime.now(timezone.utc).isoformat()
        new_progress = list(self.stage_progress)

        # Update the matching StageProgress entry
        found = False
        for i, sp in enumerate(new_progress):
            if sp["stage_name"] == stage_name and sp["status"] == StageStatus.RUNNING:
                new_progress[i] = {
                    **sp,
                    "status": StageStatus.COMPLETED,
                    "result": result,
                    "completed_at": now,
                    "duration_ms": duration_ms,
                }
                found = True
                break
        if not found:
            new_progress.append(StageProgress(
                stage_name=stage_name,
                status=StageStatus.COMPLETED,
                result=result,
                started_at=now,
                completed_at=now,
                duration_ms=duration_ms,
            ).to_dict())

        new_completed = self.completed_stages + (stage_name,)
        return ExecutionState(
            execution_id=self.execution_id,
            current_stage=stage_name,
            current_stage_index=len(new_completed),
            completed_stages=new_completed,
            stage_progress=tuple(new_progress),
            event_count=self.event_count,
            started_at=self.started_at,
            updated_at=now,
            status=ExecutionStatus.RUNNING if len(new_progress) < 100 else self.status,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    def fail(self, stage_name: str, error: str = "") -> "ExecutionState":
        """Mark execution as FAILED after a stage fails."""
        now = datetime.now(timezone.utc).isoformat()
        new_progress = list(self.stage_progress)
        found = False
        for i, sp in enumerate(new_progress):
            if sp["stage_name"] == stage_name:
                new_progress[i] = {
                    **sp,
                    "status": StageStatus.FAILED,
                    "error": error,
                    "completed_at": now,
                }
                found = True
                break
        if not found:
            new_progress.append(StageProgress(
                stage_name=stage_name,
                status=StageStatus.FAILED,
                error=error,
                completed_at=now,
            ).to_dict())
        return ExecutionState(
            execution_id=self.execution_id,
            current_stage=stage_name,
            current_stage_index=self.current_stage_index,
            completed_stages=self.completed_stages,
            stage_progress=tuple(new_progress),
            event_count=self.event_count,
            started_at=self.started_at,
            updated_at=now,
            status=ExecutionStatus.FAILED,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    def complete(self) -> "ExecutionState":
        """Mark execution as COMPLETED after all stages pass."""
        now = datetime.now(timezone.utc).isoformat()
        return ExecutionState(
            execution_id=self.execution_id,
            current_stage=self.current_stage,
            current_stage_index=self.current_stage_index,
            completed_stages=self.completed_stages,
            stage_progress=self.stage_progress,
            event_count=self.event_count,
            started_at=self.started_at,
            updated_at=now,
            status=ExecutionStatus.COMPLETED,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    def crash(self) -> "ExecutionState":
        """Mark execution as CRASHED (unexpected termination)."""
        now = datetime.now(timezone.utc).isoformat()
        return ExecutionState(
            execution_id=self.execution_id,
            current_stage=self.current_stage,
            current_stage_index=self.current_stage_index,
            completed_stages=self.completed_stages,
            stage_progress=self.stage_progress,
            event_count=self.event_count,
            started_at=self.started_at,
            updated_at=now,
            status=ExecutionStatus.CRASHED,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    # ── Counters ───────────────────────────────────────────────────────

    def increment_retry(self) -> "ExecutionState":
        """Increment retry count. Returns new instance."""
        now = datetime.now(timezone.utc).isoformat()
        return ExecutionState(
            execution_id=self.execution_id,
            current_stage=self.current_stage,
            current_stage_index=self.current_stage_index,
            completed_stages=self.completed_stages,
            stage_progress=self.stage_progress,
            event_count=self.event_count,
            started_at=self.started_at,
            updated_at=now,
            status=self.status,
            retry_count=self.retry_count + 1,
            metadata=self.metadata,
        )

    def increment_event(self) -> "ExecutionState":
        """Increment emitted event count. Returns new instance."""
        now = datetime.now(timezone.utc).isoformat()
        return ExecutionState(
            execution_id=self.execution_id,
            current_stage=self.current_stage,
            current_stage_index=self.current_stage_index,
            completed_stages=self.completed_stages,
            stage_progress=self.stage_progress,
            event_count=self.event_count + 1,
            started_at=self.started_at,
            updated_at=now,
            status=self.status,
            retry_count=self.retry_count,
            metadata=self.metadata,
        )

    # ── Serialization ──────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Full serializable dict representation."""
        return {
            "execution_id": self.execution_id,
            "current_stage": self.current_stage,
            "current_stage_index": self.current_stage_index,
            "completed_stages": list(self.completed_stages),
            "stage_progress": list(self.stage_progress),
            "event_count": self.event_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "retry_count": self.retry_count,
            "metadata": dict(self.metadata),
        }

    def fingerprint(self) -> str:
        """Deterministic structural fingerprint for cross-run comparison."""
        parts = [
            self.execution_id,
            "|".join(self.completed_stages),
            self.status,
            str(self.retry_count),
        ]
        return hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════

def compute_pipeline_hash(stages: Tuple[str, ...]) -> str:
    """Deterministic SHA-256 hash of an ordered tuple of stage names."""
    return hashlib.sha256("|".join(stages).encode()).hexdigest()[:16]
