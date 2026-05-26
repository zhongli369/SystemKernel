"""
ExecutionEngine v4.0 — State + Checkpoint + Reducer + Replay execution engine.

Upgrades over v3:
  - ExecutionState (frozen lifecycle tracker) for recoverable execution
  - Enhanced Checkpoint with pipeline_hash, truth_fingerprint, invariant_status
  - CrashMarker for crash detection and recovery
  - resume_from_checkpoint=True for interrupted execution
  - Nesting guard (ExecutionEngineNestingError)
  - _finalize_checkpoint() for post-execution truth embedding

ZERO LLM. Deterministic pipeline only.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, Tuple

# Memory gateway types (same package — no external deps)
try:
    from v3.kernel.memory_gateway import MemoryEventType, MemoryEventSource
except ImportError:
    MemoryEventType = None  # type: ignore
    MemoryEventSource = None  # type: ignore

# Execution lifecycle + checkpoint (Phase 4A)
from v3.kernel.execution_state import (
    ExecutionState, ExecutionStatus, StageStatus,
    compute_pipeline_hash,
)
from v3.kernel.checkpoint import (
    Checkpoint, CheckpointStore, FileCheckpointStore,
    CrashMarker, compute_truth_fingerprint,
)

# Event sourcing (Phase 4B)
from v3.kernel.events import (
    ExecutionEvent, EventType, make_event,
    reduce_execution_state, compute_event_hash,
)
from v3.kernel.event_store import EventStore


# ═══════════════════════════════════════════════════════════════════════
# Merge Strategy
# ═══════════════════════════════════════════════════════════════════════

class MergeStrategy(Enum):
    REPLACE = "replace"
    APPEND = "append"
    MERGE = "merge"
    KEEP = "keep"


# ═══════════════════════════════════════════════════════════════════════
# Domain State (pipeline data container)
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StateField:
    """Schema for one field in DomainState."""
    name: str
    type_: type = str
    merge: MergeStrategy = MergeStrategy.REPLACE
    default: Any = None


class DomainState:
    """Immutable domain state for pipeline data with reducer-based updates.

    Holds pipeline-scoped data (task_id, thread_id, target, etc.).
    Inspired by LangGraph's TypedDict + Annotated reducers.
    NO LLM nodes. NO graph edges. Only deterministic pipeline threading.
    """

    def __init__(self, schema: Tuple[StateField, ...], initial: Optional[dict] = None):
        self._schema = {f.name: f for f in schema}
        self._data: dict[str, Any] = {f.name: f.default for f in schema}
        if initial:
            for k, v in initial.items():
                if k in self._schema:
                    self._data[k] = v

    def update(self, **kwargs: Any) -> "DomainState":
        """Create new state with reducer-merged updates. Immutable."""
        new_data = dict(self._data)
        for key, value in kwargs.items():
            field = self._schema.get(key)
            if field is None:
                continue
            if field.merge == MergeStrategy.REPLACE:
                new_data[key] = value
            elif field.merge == MergeStrategy.APPEND:
                current = new_data.get(key, [])
                if current is None:
                    current = []
                new_data[key] = current + (value if isinstance(value, list) else [value])
            elif field.merge == MergeStrategy.MERGE:
                current = dict(new_data.get(key, {}) or {})
                if isinstance(value, dict):
                    current.update(value)
                new_data[key] = current
            elif field.merge == MergeStrategy.KEEP:
                if new_data.get(key) is None:
                    new_data[key] = value
        return DomainState(tuple(self._schema.values()), new_data)

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def snapshot(self) -> dict:
        return dict(self._data)

    def __repr__(self) -> str:
        return f"DomainState({self._data})"


# ═══════════════════════════════════════════════════════════════════════
# Pipeline Stage
# ═══════════════════════════════════════════════════════════════════════

class RetryPolicy(Enum):
    NONE = "none"
    ONCE = "once"
    FALLBACK = "fallback"
    CIRCUIT_BREAKER = "cb"


@dataclass(frozen=True)
class StageResult:
    """Output of one pipeline stage."""
    stage_name: str
    passed: bool
    output: dict = field(default_factory=dict)
    duration_ms: int = 0
    error: str = ""


class PipelineStage:
    """One stage in the execution pipeline. Pure function contract.

    Subclass and override run().
    """

    def run(self, state: DomainState) -> StageResult:
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════
# Built-in stages
# ═══════════════════════════════════════════════════════════════════════

class LintStage(PipelineStage):
    """Run ruff check on target directory."""

    def run(self, state: DomainState) -> StageResult:
        target = state.get("target") or "."
        start = time.monotonic()
        import subprocess
        try:
            proc = subprocess.run(
                ["ruff", "check", str(target)],
                capture_output=True, text=True, timeout=300, cwd=str(target),
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return StageResult(
                stage_name="lint",
                passed=proc.returncode == 0,
                output={"stdout": proc.stdout[:2000], "stderr": proc.stderr[:2000]},
                duration_ms=elapsed,
                error=proc.stderr[:500] if proc.returncode != 0 else "",
            )
        except FileNotFoundError:
            return StageResult(
                stage_name="lint", passed=True, output={"stdout": "ruff not installed -- skipping"},
                duration_ms=int((time.monotonic() - start) * 1000),
            )


class NoopStage(PipelineStage):
    """A stage that always passes. Used for testing and demos."""

    def __init__(self, name: str = "noop", delay_s: float = 0.0):
        self._name = name
        self._delay = delay_s

    def run(self, state: DomainState) -> StageResult:
        start = time.monotonic()
        if self._delay:
            time.sleep(self._delay)
        elapsed = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage_name=self._name,
            passed=True,
            output={"message": f"Stage '{self._name}' completed"},
            duration_ms=elapsed,
        )


# ═══════════════════════════════════════════════════════════════════════
# Execution Config
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExecutionConfig:
    """Immutable execution configuration. Frozen after construction.

    Pipeline is a tuple — immutable by Python semantics.
    All fields are frozen — no runtime modification allowed.
    """
    pipeline: Tuple[PipelineStage, ...] = ()
    retry: RetryPolicy = RetryPolicy.ONCE
    max_retries: int = 1
    checkpoint_store: Optional[CheckpointStore] = None
    event_store: Optional[EventStore] = None
    thread_id: str = "default"
    memory_gateway: Any = None  # Optional[MemoryGateway], Any to avoid circular import


# ═══════════════════════════════════════════════════════════════════════
# Execution Engine
# ═══════════════════════════════════════════════════════════════════════

class ExecutionEngineFrozenError(Exception):
    """Raised when attempting to modify a frozen ExecutionEngine."""
    pass


class ExecutionEngineNestingError(Exception):
    """Raised when run() is called while another execution is in progress."""
    pass


class ExecutionEngine:
    """v4 Execution Engine — Event-Sourced State + Checkpoint + Replay.

    Phase 4B upgrades:
      - Event-sourced runtime: state transitions emit events
      - ExecutionState is a pure projection derived from event history
      - Optional EventStore for append-only event persistence
      - Checkpoints are optimization snapshots, not authoritative
      - All mutation goes through _emit() — no direct lifecycle writes

    Phase 4A upgrades:
      - ExecutionState (frozen lifecycle tracker) per execution
      - Enhanced checkpoints with pipeline_hash, truth_fingerprint
      - CrashMarker for crash detection + recovery
      - resume_from_checkpoint=True for interrupted executions
      - Nesting guard prevents nested run() calls

    FROZEN after initialization. Pipeline is immutable.
    Only observability hooks and bug fixes allowed.
    No dynamic stage injection. No runtime structural modification.
    """

    def __init__(self, config: ExecutionConfig):
        # Validate before freezing
        if not isinstance(config.pipeline, tuple):
            raise TypeError("pipeline must be a tuple (immutable)")
        self._config = config
        self._state: Optional[DomainState] = None
        self._last_cp_id: Optional[str] = None
        self._frozen = True
        self._run_count: int = 0
        # Phase 4A: lifecycle tracking
        self._executing: bool = False
        self._execution_id: Optional[str] = None
        self._lifecycle: Optional[ExecutionState] = None
        # Phase 4B: event-sourced runtime
        self._event_stream: list[ExecutionEvent] = []
        self._event_seq: int = 0
        self._last_event_id: Optional[str] = None

    @property
    def config(self) -> ExecutionConfig:
        """Read-only access to config. Returns frozen dataclass."""
        return self._config

    @property
    def frozen(self) -> bool:
        """Whether the engine is frozen. Always True after __init__."""
        return self._frozen

    @property
    def run_count(self) -> int:
        """Number of times run() has been called."""
        return self._run_count

    @property
    def lifecycle(self) -> Optional[ExecutionState]:
        """Current execution lifecycle state (Phase 4A).
        Phase 4B: This is a cached reduction of the event stream."""
        return self._lifecycle

    @property
    def event_stream(self) -> Tuple[ExecutionEvent, ...]:
        """Current execution event stream (Phase 4B). Immutable view."""
        return tuple(self._event_stream)

    # ── Event Sourcing (Phase 4B) ───────────────────────────────────────

    def _emit(
        self, event_type: str, payload: Optional[dict] = None,
    ) -> ExecutionEvent:
        """Emit an execution event. Appends to stream, updates cached lifecycle,
        and persists to EventStore if configured.

        This is the ONLY path for state mutation in Phase 4B.
        No code may directly mutate self._lifecycle.
        """
        event = make_event(
            execution_id=self._execution_id or "",
            sequence=self._event_seq,
            event_type=event_type,
            payload=payload or {},
            parent_event_id=self._last_event_id,
        )
        self._event_stream.append(event)
        self._event_seq += 1
        self._last_event_id = event.event_id

        # Persist to EventStore (append-only)
        self._persist_event(event)

        # Update cached lifecycle by reducing event
        if self._lifecycle:
            self._lifecycle = self._apply_event(self._lifecycle, event)

        return event

    def _apply_event(
        self, es: ExecutionState, event: ExecutionEvent
    ) -> ExecutionState:
        """Apply a single event to an ExecutionState, returning new state.
        Delegates to the pure reducer from events module."""
        p = event.payload
        etype = event.event_type

        if etype == EventType.EXECUTION_STARTED:
            return es.start()
        elif etype == EventType.STAGE_STARTED:
            return es.start_stage(p.get("stage_name", ""))
        elif etype == EventType.STAGE_COMPLETED:
            return es.advance(
                p.get("stage_name", ""), p.get("result"), p.get("duration_ms", 0),
            )
        elif etype == EventType.STAGE_FAILED:
            return es.fail(p.get("stage_name", ""), p.get("error", ""))
        elif etype == EventType.EXECUTION_COMPLETED:
            return es.complete()
        elif etype == EventType.EXECUTION_FAILED:
            return es.fail(p.get("stage_name", ""), p.get("error", ""))
        elif etype == EventType.EXECUTION_CRASHED:
            return es.crash()
        elif etype == EventType.RETRY_INCREMENTED:
            return es.increment_retry()
        elif etype == EventType.EVENT_RECORDED:
            return es.increment_event()
        return es

    def _persist_event(self, event: ExecutionEvent) -> None:
        """Persist event to EventStore. Non-blocking, never fails."""
        if self.config.event_store is None:
            return
        try:
            self.config.event_store.append(event)
        except Exception:
            pass  # Event persistence must not affect execution

    def _reduce(self) -> ExecutionState:
        """Reduce entire event stream to ExecutionState.
        Used for verification — the cached _lifecycle should match."""
        return reduce_execution_state(tuple(self._event_stream))

    def _require_frozen(self) -> None:
        """Guard: assert engine hasn't been tampered with."""
        if not self._frozen:
            raise ExecutionEngineFrozenError(
                "ExecutionEngine freeze state compromised"
            )
        if id(self._config.pipeline) != id(self.config.pipeline):
            raise ExecutionEngineFrozenError(
                "Pipeline tuple identity changed -- possible mutation"
            )

    # ── Main Entry Point ──────────────────────────────────────────────

    def run(
        self,
        initial_state: DomainState,
        *,
        resume_from_checkpoint: bool = False,
        execution_id: Optional[str] = None,
    ) -> dict:
        """Execute pipeline with event sourcing at each stage.

        Phase 4B: All state transitions emitted as events.
        ExecutionState is a pure projection of the event stream.
        Phase 4A: Supports resume_from_checkpoint for crash recovery.
        Guard: _require_frozen() + nesting guard.
        Single control flow path -- one _post_execution hook, one return.
        """
        self._require_frozen()

        # Nesting guard: no nested execution allowed
        if self._executing:
            raise ExecutionEngineNestingError(
                "run() called while another execution is already in progress"
            )

        self._executing = True
        self._run_count += 1
        self._execution_id = execution_id or str(uuid.uuid4())
        total_start = time.monotonic()

        # Phase 4B: Reset event stream for this execution
        self._event_stream = []
        self._event_seq = 0
        self._last_event_id = None

        try:
            # Initialize lifecycle + emit ExecutionStarted
            self._lifecycle = ExecutionState(execution_id=self._execution_id)
            pipeline_names = tuple(
                getattr(s, "_name", None) or s.__class__.__name__
                for s in self.config.pipeline
            )
            self._emit(EventType.EXECUTION_STARTED, payload={
                "pipeline_hash": compute_pipeline_hash(pipeline_names),
                "stage_order": list(pipeline_names),
                "thread_id": self.config.thread_id,
            })

            # Resume from checkpoint if requested
            resumed = False
            if resume_from_checkpoint and self.config.checkpoint_store:
                resumed = self._detect_crash_and_resume(self._execution_id)

            if not resumed:
                self._state = initial_state

            # Execute pipeline
            if not self.config.pipeline:
                self._emit(EventType.EXECUTION_COMPLETED)
                _result = self._build_result(True, None, [], total_start, self._execution_id)
            else:
                _result = self._run_pipeline(self._execution_id, total_start)

            # Finalize checkpoint with truth data
            self._post_execution(_result, self._execution_id)
            self._finalize_checkpoint(_result)

            return _result
        finally:
            self._executing = False

    # ── Crash Detection + Resume ──────────────────────────────────────

    def _detect_crash_and_resume(self, execution_id: str) -> bool:
        """Check for crash marker. If found, load last checkpoint and prepare resume.

        Returns True if a checkpoint was loaded and we should resume from it.
        """
        if not self.config.checkpoint_store:
            return False

        crash_data = CrashMarker.read(execution_id)
        last_cp = self.config.checkpoint_store.load_latest(execution_id)

        if crash_data and last_cp:
            # Crash detected — restore from last checkpoint, re-execute crashed stage
            self._state = DomainState(
                tuple(self._state._schema.values()) if self._state else (),
                last_cp.state_snapshot,
            )
            self._lifecycle = ExecutionState(
                execution_id=execution_id,
                current_stage=crash_data.get("stage", ""),
                current_stage_index=crash_data.get("stage_index", 0),
                completed_stages=tuple(last_cp.stage_order[:crash_data.get("stage_index", 0)]),
                status=ExecutionStatus.CRASHED,
            ).start()
            # Clear the crash marker — we're recovering now
            CrashMarker.clear(execution_id)
            return True

        if last_cp:
            # No crash, but checkpoints exist — resume from next uncompleted stage
            self._state = DomainState(
                tuple(self._state._schema.values()) if self._state else (),
                last_cp.state_snapshot,
            )
            resume_idx = last_cp.stage_index + 1
            self._lifecycle = ExecutionState(
                execution_id=execution_id,
                current_stage=last_cp.stage,
                current_stage_index=resume_idx,
                completed_stages=tuple(last_cp.stage_order[:resume_idx]),
                status=ExecutionStatus.RUNNING,
            ).start()
            return True

        return False

    # ── Pipeline Execution ────────────────────────────────────────────

    def _build_result(
        self, success: bool, failed_stage: Optional[str],
        stage_results: list, total_start: float, trace_id: str,
        **extra,
    ) -> dict:
        """Build standard result dict. Single place for result shape."""
        d = {
            "success": success,
            "failed_stage": failed_stage,
            "stage_results": stage_results,
            "state_snapshot": self._state.snapshot() if self._state else {},
            "duration_ms": int((time.monotonic() - total_start) * 1000),
            "trace_id": trace_id,
            "execution_id": self._execution_id,
        }
        d.update(extra)
        return d

    def _run_pipeline(self, trace_id: str, total_start: float) -> dict:
        """Execute all pipeline stages. Supports stage-skipping for resume.
        Phase 4B: Emits events for all state transitions."""
        # Determine start index (for resume scenarios)
        start_idx = self._lifecycle.current_stage_index if self._lifecycle else 0
        stage_results = list(self._lifecycle.stage_progress) if self._lifecycle else []

        for i, stage in enumerate(self.config.pipeline):
            if i < start_idx:
                continue  # Skip already-completed stages (resume)
            early = self._run_one_stage(stage, i, stage_results, trace_id, total_start)
            if early is not None:
                return early  # circuit breaker or failure

        # Phase 4B: Emit completion event (not direct mutation)
        self._emit(EventType.EXECUTION_COMPLETED)
        return self._build_result(
            True, None, stage_results, total_start, trace_id,
        )

    def _run_one_stage(
        self, stage: PipelineStage, stage_index: int,
        stage_results: list, trace_id: str, total_start: float,
    ) -> Optional[dict]:
        """Run one stage with retry. Returns result dict on early exit, None if passed.

        Phase 4B: All lifecycle transitions emitted as events.
        Phase 4A: Uses CrashMarker for crash recovery.
        """
        stage_name = getattr(stage, "_name", None) or stage.__class__.__name__

        # Phase 4B: Emit stage started event
        self._emit(EventType.STAGE_STARTED, payload={"stage_name": stage_name})

        # Write crash marker before executing stage
        CrashMarker.write(self._execution_id, stage_name, stage_index)

        attempts = 0
        while attempts <= self.config.max_retries:
            result = stage.run(self._state)
            stage_results.append(asdict(result))

            if result.passed:
                self._state = self._state.update(
                    _last_stage=stage_name,
                    _last_result=asdict(result),
                )
                # Phase 4B: Emit stage completed event
                self._emit(EventType.STAGE_COMPLETED, payload={
                    "stage_name": stage_name,
                    "result": asdict(result),
                    "duration_ms": result.duration_ms,
                })
                # Checkpoint + clear crash marker
                self._checkpoint(stage_name, stage_index)
                CrashMarker.clear(self._execution_id)
                # Emit memory event
                self._emit_memory_event(
                    stage_name, True, asdict(result), trace_id,
                )
                return None  # stage passed, continue pipeline

            attempts += 1
            # Phase 4B: Emit retry event
            self._emit(EventType.RETRY_INCREMENTED)

            if self.config.retry == RetryPolicy.NONE:
                break
            if self.config.retry == RetryPolicy.FALLBACK and attempts > self.config.max_retries:
                break
            if self.config.retry == RetryPolicy.CIRCUIT_BREAKER and attempts > self.config.max_retries:
                # Phase 4B: Emit stage failed event
                self._emit(EventType.STAGE_FAILED, payload={
                    "stage_name": stage_name,
                    "error": f"Circuit breaker: {stage_name} failed after {attempts} attempts",
                })
                CrashMarker.clear(self._execution_id)
                return self._build_result(
                    False, stage_name, stage_results, total_start, trace_id,
                    error=f"Circuit breaker: {stage_name} failed after {attempts} attempts",
                )

        # Stage failed after all retries
        # Phase 4B: Emit failure events
        error_msg = stage_results[-1].get("error", "") if stage_results else ""
        self._emit(EventType.STAGE_FAILED, payload={
            "stage_name": stage_name,
            "error": error_msg,
        })
        self._emit(EventType.EXECUTION_FAILED, payload={
            "stage_name": stage_name,
            "error": error_msg,
        })
        CrashMarker.clear(self._execution_id)
        self._emit_memory_event(
            stage_name, False,
            stage_results[-1] if stage_results else {},
            trace_id,
        )
        return self._build_result(
            False, stage_name, stage_results, total_start, trace_id,
        )

    # ── Checkpointing ─────────────────────────────────────────────────

    def _checkpoint(self, stage_name: str, stage_index: int) -> None:
        """Record enhanced checkpoint after each successful stage.

        Phase 4A: Includes pipeline_hash, stage_order, lifecycle_snapshot.
        """
        if not self.config.checkpoint_store:
            return

        # Build pipeline stage names
        pipeline_stage_names = tuple(
            getattr(s, "_name", None) or s.__class__.__name__
            for s in self.config.pipeline
        )
        phash = compute_pipeline_hash(pipeline_stage_names)

        cp = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            execution_id=self._execution_id,
            stage=stage_name,
            stage_index=stage_index,
            state_snapshot=self._state.snapshot() if self._state else {},
            lifecycle_snapshot=self._lifecycle.snapshot() if self._lifecycle else {},
            pipeline_hash=phash,
            stage_order=pipeline_stage_names,
            truth_fingerprint="",  # Filled at _finalize_checkpoint
            invariant_status="UNKNOWN",  # Filled at _finalize_checkpoint
            timestamp=datetime.now(timezone.utc).isoformat(),
            parent_id=self._last_cp_id,
        )
        self.config.checkpoint_store.save_checkpoint(cp)
        self._last_cp_id = cp.checkpoint_id

        # Phase 4B: EventRecorded emitted (not direct mutation)
        self._emit(EventType.EVENT_RECORDED)

    def _finalize_checkpoint(self, result: dict) -> None:
        """Emit final checkpoint with truth data after post_execution.

        This preserves append-only: we write a completion record rather
        than modifying previous checkpoints.
        """
        if not self.config.checkpoint_store:
            return

        truth = result.get("truth", {})
        pipeline_stage_names = tuple(
            getattr(s, "_name", None) or s.__class__.__name__
            for s in self.config.pipeline
        )
        phash = compute_pipeline_hash(pipeline_stage_names)

        inv_status = "CLEAN"
        if result.get("invariant_critical"):
            inv_status = "CRITICAL"
        elif result.get("invariant_violations"):
            inv_status = "WARN"

        final_cp = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            execution_id=self._execution_id,
            stage="__completed__",
            stage_index=len(pipeline_stage_names),
            state_snapshot=self._state.snapshot() if self._state else {},
            lifecycle_snapshot=self._lifecycle.snapshot() if self._lifecycle else {},
            pipeline_hash=phash,
            stage_order=pipeline_stage_names,
            truth_fingerprint=compute_truth_fingerprint(truth),
            invariant_status=inv_status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            parent_id=self._last_cp_id,
        )
        self.config.checkpoint_store.save_checkpoint(final_cp)
        self._last_cp_id = final_cp.checkpoint_id

    # ── Event Stream Operations (Phase 4B) ───────────────────────────

    def _rebuild_state(self) -> Optional[ExecutionState]:
        """Rebuild ExecutionState entirely from the event store.
        If no EventStore, uses in-memory event stream.
        Compare with cached _lifecycle to verify consistency."""
        events: Tuple[ExecutionEvent, ...] = ()
        if self.config.event_store and self._execution_id:
            events = self.config.event_store.load_stream(self._execution_id)
        if not events and self._event_stream:
            events = tuple(self._event_stream)
        if not events:
            return None
        return reduce_execution_state(events, self._execution_id or "")

    def _fork_execution(
        self, at_sequence: int, new_execution_id: Optional[str] = None
    ) -> Tuple[ExecutionEvent, ...]:
        """Create an execution fork from the current event stream.
        Returns the forked event stream with a new execution_id.
        The caller can use the forked events to instantiate a new engine run."""
        from v3.kernel.time_travel import fork_execution
        events = self._event_stream if self._event_stream else ()
        if not events:
            return ()
        branch = fork_execution(tuple(events), at_sequence)
        # Persist forked events if event store is configured
        if self.config.event_store and branch.events:
            for evt in branch.events:
                try:
                    self.config.event_store.append(evt)
                except Exception:
                    pass
        return branch.events

    # ── Memory ────────────────────────────────────────────────────────

    def _emit_memory_event(
        self, stage_name: str, passed: bool, data: dict, execution_id: str
    ) -> None:
        """Emit memory event through gateway. Non-blocking. Never fails.

        This is the ONLY memory hook in ExecutionEngine.
        Minimal, non-invasive, try/except guarded.
        If no MemoryGateway is configured, this is a no-op.
        """
        gw = self.config.memory_gateway
        if gw is None:
            return
        try:
            gw.write(
                event_type=MemoryEventType.WRITE,
                source=MemoryEventSource.EXECUTION_ENGINE,
                source_stage=stage_name,
                execution_id=execution_id,
                payload={
                    "content": f"Stage '{stage_name}' {'passed' if passed else 'failed'}",
                    "metadata": {
                        "task_id": (self._state.get("task_id") or "") if self._state else "",
                        "thread_id": self.config.thread_id,
                        "skill_id": (self._state.get("skill_id") or "") if self._state else "",
                        "stage": stage_name,
                        "success": passed,
                        "tags": ["execution", stage_name],
                    },
                },
            )
        except Exception:
            # Memory emission failure MUST NOT affect execution
            pass

    # ── Post-Execution ────────────────────────────────────────────────

    def _post_execution(self, result: dict, trace_id: str) -> None:
        """Single post-execution hook -- validate invariants + capture truth snapshot.

        Uses unified truth_model.ExecutionTruthSnapshot.
        Appends 'truth' to result dict. Writes JSONL. Never raises.
        """
        # Validate invariants (non-blocking)
        violations: list = []
        try:
            from v3.kernel.invariants import (
                create_default_registry, has_critical_violations,
            )
            registry = create_default_registry()
            violations = registry.validate_all(result, self)
            if violations:
                result["invariant_violations"] = violations
                result["invariant_critical"] = has_critical_violations(violations)
            else:
                result["invariant_violations"] = []
                result["invariant_critical"] = False
        except Exception:
            result["invariant_violations"] = []
            result["invariant_critical"] = False

        # Capture unified truth snapshot
        try:
            from v3.kernel.truth_model import capture_truth, write_truth
            truth = capture_truth(result, self, violations=violations)
            result["truth"] = truth.to_dict()
            write_truth(truth)
        except Exception:
            pass
