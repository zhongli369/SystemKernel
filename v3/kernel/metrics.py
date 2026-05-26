"""
Metrics — Deterministic runtime metrics aggregation from event streams.

Phase 4C: Aggregates an event stream into RuntimeMetrics. Pure function —
no side effects, no wall clock, no file I/O, no LLM. All durations and
counts are derived from event payload data only.

Deterministic: same events → same metrics every time.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.kernel.events import ExecutionEvent


# ═══════════════════════════════════════════════════════════════════════
# RuntimeMetrics
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuntimeMetrics:
    """Aggregated metrics from an event stream.

    All data derived from event payloads — no wall clock dependence.
    """

    execution_id: str
    total_events: int
    total_stages: int
    completed_stages: int
    failed_stages: int
    retries: int
    crashes: int
    forks: int
    checkpoints: int
    duration_ms: int
    average_stage_duration_ms: float
    longest_stage: str
    failed_stage_names: Tuple[str, ...]
    stage_duration_map: dict = field(default_factory=dict)
    event_type_counts: dict = field(default_factory=dict)
    execution_status: str = "UNKNOWN"

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "total_events": self.total_events,
            "total_stages": self.total_stages,
            "completed_stages": self.completed_stages,
            "failed_stages": self.failed_stages,
            "retries": self.retries,
            "crashes": self.crashes,
            "forks": self.forks,
            "checkpoints": self.checkpoints,
            "duration_ms": self.duration_ms,
            "average_stage_duration_ms": self.average_stage_duration_ms,
            "longest_stage": self.longest_stage,
            "failed_stage_names": list(self.failed_stage_names),
            "stage_duration_map": dict(self.stage_duration_map),
            "event_type_counts": dict(self.event_type_counts),
            "execution_status": self.execution_status,
        }

    @property
    def success_rate(self) -> float:
        if self.total_stages == 0:
            return 0.0
        return self.completed_stages / self.total_stages


# ═══════════════════════════════════════════════════════════════════════
# Metrics Computation
# ═══════════════════════════════════════════════════════════════════════

def compute_metrics(
    events: "Tuple[ExecutionEvent, ...]",
) -> "RuntimeMetrics":
    """Compute runtime metrics from an event stream.

    Pure function. Deterministic. All values from event payloads.

    Args:
        events: Ordered tuple of ExecutionEvents

    Returns:
        RuntimeMetrics aggregated from the event stream.
    """
    from v3.kernel.events import EventType

    if not events:
        return RuntimeMetrics(
            execution_id="",
            total_events=0,
            total_stages=0,
            completed_stages=0,
            failed_stages=0,
            retries=0,
            crashes=0,
            forks=0,
            checkpoints=0,
            duration_ms=0,
            average_stage_duration_ms=0.0,
            longest_stage="",
            failed_stage_names=(),
        )

    eid = events[0].execution_id

    # Event type counts
    event_type_counts: dict[str, int] = {}
    for e in events:
        event_type_counts[e.event_type] = event_type_counts.get(e.event_type, 0) + 1

    # Stage tracking
    completed_stages = 0
    failed_stages = 0
    failed_stage_names: list[str] = []
    stage_durations: dict[str, int] = {}
    retries = 0
    crashes = 0
    forks = 0
    checkpoints = 0
    total_stages_seen: set[str] = set()
    execution_status = "UNKNOWN"

    for event in events:
        etype = event.event_type
        payload = event.payload

        if etype == EventType.STAGE_STARTED:
            sn = payload.get("stage_name", "")
            if sn:
                total_stages_seen.add(sn)

        elif etype == EventType.STAGE_COMPLETED:
            sn = payload.get("stage_name", "")
            dur = payload.get("duration_ms", 0)
            completed_stages += 1
            if sn:
                total_stages_seen.add(sn)
                stage_durations[sn] = stage_durations.get(sn, 0) + dur

        elif etype == EventType.STAGE_FAILED:
            sn = payload.get("stage_name", "unknown")
            failed_stages += 1
            failed_stage_names.append(sn)

        elif etype == EventType.RETRY_INCREMENTED:
            retries += 1

        elif etype == EventType.EXECUTION_CRASHED:
            crashes += 1
            execution_status = "CRASHED"

        elif etype == EventType.FORK_CREATED:
            forks += 1

        elif etype in (EventType.EVENT_RECORDED, EventType.REPLAY_STARTED, EventType.REPLAY_COMPLETED):
            checkpoints += 1

        elif etype == EventType.EXECUTION_COMPLETED:
            execution_status = "COMPLETED"

        elif etype == EventType.EXECUTION_FAILED:
            execution_status = "FAILED"

    # Duration from payload data
    duration_ms = 0
    if events:
        # Sum stage durations from payloads
        duration_ms = sum(stage_durations.values())
        # Also check EXECUTION_COMPLETED for total duration
        for event in events:
            if event.event_type == EventType.EXECUTION_COMPLETED:
                dur = event.payload.get("duration_ms", 0)
                if dur > 0:
                    duration_ms = dur
                    break

    # Also check execution_started payload for declared stage_order
    total_stages = len(total_stages_seen)
    if events and events[0].event_type == EventType.EXECUTION_STARTED:
        declared = events[0].payload.get("stage_order", [])
        if declared:
            total_stages = len(declared)

    # Average stage duration
    if completed_stages > 0:
        avg_dur = duration_ms / completed_stages
    else:
        avg_dur = 0.0

    # Longest stage
    longest_stage = ""
    if stage_durations:
        longest_stage = max(stage_durations, key=lambda k: stage_durations[k])

    return RuntimeMetrics(
        execution_id=eid,
        total_events=len(events),
        total_stages=total_stages,
        completed_stages=completed_stages,
        failed_stages=failed_stages,
        retries=retries,
        crashes=crashes,
        forks=forks,
        checkpoints=checkpoints,
        duration_ms=duration_ms,
        average_stage_duration_ms=round(avg_dur, 2),
        longest_stage=longest_stage,
        failed_stage_names=tuple(failed_stage_names),
        stage_duration_map=dict(stage_durations),
        event_type_counts=dict(event_type_counts),
        execution_status=execution_status,
    )


# ═══════════════════════════════════════════════════════════════════════
# Metrics fingerprint
# ═══════════════════════════════════════════════════════════════════════

def metrics_fingerprint(metrics: RuntimeMetrics) -> str:
    """Deterministic fingerprint of metrics snapshot."""
    parts = [
        metrics.execution_id,
        str(metrics.total_events),
        str(metrics.total_stages),
        str(metrics.completed_stages),
        str(metrics.failed_stages),
        str(metrics.retries),
        str(metrics.crashes),
        str(metrics.forks),
        str(metrics.checkpoints),
        str(metrics.duration_ms),
        str(metrics.average_stage_duration_ms),
        metrics.longest_stage,
        "|".join(metrics.failed_stage_names),
        metrics.execution_status,
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
