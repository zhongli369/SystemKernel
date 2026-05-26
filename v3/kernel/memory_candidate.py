"""
Memory Candidates — Pure functional projection of "memory-worthy" data
from an event stream and its derived projections (graph, metrics, telemetry).

Phase 4D-1: Extracts structured candidates from the event stream. Does NOT
store, index, or retrieve. This is a projection, not a storage operation.

Rules:
  - Pure function: same inputs → same outputs, always
  - No side effects: no file I/O, no network, no database
  - No LLM: no semantic analysis, no classification, no summarization
  - No storage: candidates are returned, not persisted
  - Deterministic: candidate_id is content-addressed
  - Removable: if memory subsystem is absent, candidates are simply not consumed

What makes a "memory candidate":
  - Execution summaries (completed/failed/crashed outcomes)
  - Stage results with timing and status
  - Error details (for future error lookup)
  - Notable events (retries, forks, checkpoints)
  - Pipeline structure (stage order, duration distribution)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

from v3.kernel.events import ExecutionEvent, EventType, json_dumps_stable

if TYPE_CHECKING:
    from v3.kernel.observability_graph import RuntimeGraph
    from v3.kernel.metrics import RuntimeMetrics
    from v3.kernel.telemetry import InvariantTelemetry


# ═══════════════════════════════════════════════════════════════════════
# Candidate Types (closed set)
# ═══════════════════════════════════════════════════════════════════════

class CandidateType:
    EXECUTION_SUMMARY = "execution_summary"
    STAGE_RESULT = "stage_result"
    ERROR_DETAIL = "error_detail"
    NOTABLE_EVENT = "notable_event"
    PIPELINE_STRUCTURE = "pipeline_structure"

    ALL = {
        EXECUTION_SUMMARY,
        STAGE_RESULT,
        ERROR_DETAIL,
        NOTABLE_EVENT,
        PIPELINE_STRUCTURE,
    }


# ═══════════════════════════════════════════════════════════════════════
# MemoryCandidate
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemoryCandidate:
    """A single memory-worthy data point extracted from the event stream.

    Each candidate is self-contained: it carries enough context to be
    stored, indexed, and retrieved independently. The candidate_id is
    content-addressed (deterministic hash of content + type + execution).

    Fields:
        candidate_id: Deterministic, content-addressed ID
        execution_id: Which execution this comes from
        candidate_type: One of CandidateType values
        content: The actual data to potentially store
        context: Additional context (stage_name, sequence range, etc.)
        priority: 0=background, 1=normal, 2=important
        source_sequences: Which event sequences contributed to this candidate
    """

    candidate_id: str
    execution_id: str
    candidate_type: str
    content: dict
    context: dict = field(default_factory=dict)
    priority: int = 1
    source_sequences: Tuple[int, ...] = ()

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "execution_id": self.execution_id,
            "candidate_type": self.candidate_type,
            "content": dict(self.content),
            "context": dict(self.context),
            "priority": self.priority,
            "source_sequences": list(self.source_sequences),
        }

    @staticmethod
    def compute_candidate_id(
        execution_id: str,
        candidate_type: str,
        content: dict,
    ) -> str:
        """Deterministic content-addressed ID."""
        parts = [
            execution_id,
            candidate_type,
            json_dumps_stable(content),
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Projection function
# ═══════════════════════════════════════════════════════════════════════

def project_candidates(
    events: "Tuple[ExecutionEvent, ...]",
    graph: "Optional[RuntimeGraph]" = None,
    metrics: "Optional[RuntimeMetrics]" = None,
    telemetry: "Optional[InvariantTelemetry]" = None,
) -> "Tuple[MemoryCandidate, ...]":
    """Project memory candidates from an event stream and its derived projections.

    Pure function. Deterministic. Same inputs → same candidates, always.

    Args:
        events: Ordered tuple of ExecutionEvents (source of truth)
        graph: Optional pre-built RuntimeGraph (computed if absent)
        metrics: Optional pre-computed RuntimeMetrics (computed if absent)
        telemetry: Optional pre-computed InvariantTelemetry (computed if absent)

    Returns:
        Tuple of MemoryCandidate objects. Empty tuple if no events.
    """
    if not events:
        return ()

    from v3.kernel.observability_graph import build_graph
    from v3.kernel.metrics import compute_metrics
    from v3.kernel.telemetry import compute_telemetry

    if graph is None:
        graph = build_graph(events)
    if metrics is None:
        metrics = compute_metrics(events)
    if telemetry is None:
        telemetry = compute_telemetry(events)

    eid = events[0].execution_id
    candidates: list[MemoryCandidate] = []

    # ── 1. Execution summary ──────────────────────────────────────────
    candidates.append(_make_execution_summary(eid, events, graph, metrics, telemetry))

    # ── 2. Stage results ──────────────────────────────────────────────
    candidates.extend(_make_stage_candidates(eid, events, graph))

    # ── 3. Error details ──────────────────────────────────────────────
    candidates.extend(_make_error_candidates(eid, events, graph))

    # ── 4. Notable events ─────────────────────────────────────────────
    candidates.extend(_make_notable_candidates(eid, events, graph))

    # ── 5. Pipeline structure ─────────────────────────────────────────
    candidates.append(_make_pipeline_candidate(eid, events, graph, metrics))

    return tuple(candidates)


# ═══════════════════════════════════════════════════════════════════════
# Candidate builders (internal)
# ═══════════════════════════════════════════════════════════════════════

def _make_candidate(
    eid: str,
    ctype: str,
    content: dict,
    context: dict | None = None,
    priority: int = 1,
    sequences: Tuple[int, ...] = (),
) -> MemoryCandidate:
    """Factory helper — ensures consistent candidate_id computation."""
    return MemoryCandidate(
        candidate_id=MemoryCandidate.compute_candidate_id(eid, ctype, content),
        execution_id=eid,
        candidate_type=ctype,
        content=content,
        context=context or {},
        priority=priority,
        source_sequences=sequences,
    )


def _make_execution_summary(
    eid: str,
    events: Tuple[ExecutionEvent, ...],
    graph: "RuntimeGraph",
    metrics: "RuntimeMetrics",
    telemetry: "InvariantTelemetry",
) -> MemoryCandidate:
    """Create an execution-level summary candidate."""
    duration_ms = graph.duration_ms
    if duration_ms == 0 and events:
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(events[0].timestamp)
            t1 = datetime.fromisoformat(events[-1].timestamp)
            duration_ms = int((t1 - t0).total_seconds() * 1000)
        except Exception:
            pass

    content = {
        "execution_id": eid,
        "event_count": len(events),
        "stage_order": list(graph.stage_order),
        "stage_count": len(graph.stage_order),
        "duration_ms": duration_ms,
        "failure_count": graph.failure_count,
        "retry_count": graph.retry_count,
        "checkpoint_count": graph.checkpoint_count,
        "fork_count": graph.fork_count,
        "execution_status": metrics.execution_status,
        "purity_score": telemetry.purity_score,
        "is_deterministic": graph.failure_count == 0 and graph.retry_count == 0,
    }

    return _make_candidate(
        eid=eid,
        ctype=CandidateType.EXECUTION_SUMMARY,
        content=content,
        context={"graph_hash": graph.graph_hash},
        priority=2,
        sequences=tuple(range(len(events))),
    )


def _make_stage_candidates(
    eid: str,
    events: Tuple[ExecutionEvent, ...],
    graph: "RuntimeGraph",
) -> "list[MemoryCandidate]":
    """Create per-stage result candidates."""
    candidates: list[MemoryCandidate] = []
    seen: set[str] = set()

    for event in events:
        if event.event_type == EventType.STAGE_COMPLETED:
            sn = event.payload.get("stage_name", "")
            if not sn or sn in seen:
                continue
            seen.add(sn)
            content = {
                "stage_name": sn,
                "status": "completed",
                "duration_ms": event.payload.get("duration_ms", 0),
                "result": event.payload.get("result"),
            }
            candidates.append(_make_candidate(
                eid=eid,
                ctype=CandidateType.STAGE_RESULT,
                content=content,
                context={"stage_name": sn},
                sequences=(event.sequence,),
            ))

        elif event.event_type == EventType.STAGE_FAILED:
            sn = event.payload.get("stage_name", "")
            if not sn or sn in seen:
                continue
            seen.add(sn)
            content = {
                "stage_name": sn,
                "status": "failed",
                "error": event.payload.get("error", ""),
            }
            candidates.append(_make_candidate(
                eid=eid,
                ctype=CandidateType.STAGE_RESULT,
                content=content,
                context={"stage_name": sn},
                priority=2,
                sequences=(event.sequence,),
            ))

    return candidates


def _make_error_candidates(
    eid: str,
    events: Tuple[ExecutionEvent, ...],
    graph: "RuntimeGraph",
) -> "list[MemoryCandidate]":
    """Create error detail candidates for failed stages."""
    candidates: list[MemoryCandidate] = []

    for event in events:
        if event.event_type == EventType.STAGE_FAILED:
            sn = event.payload.get("stage_name", "unknown")
            error_msg = event.payload.get("error", "")
            content = {
                "stage_name": sn,
                "error_message": error_msg,
                "execution_id": eid,
                "sequence": event.sequence,
                "timestamp": event.timestamp,
                "pipeline_position": _find_stage_position(sn, graph.stage_order),
                "total_failures_in_execution": graph.failure_count,
            }
            candidates.append(_make_candidate(
                eid=eid,
                ctype=CandidateType.ERROR_DETAIL,
                content=content,
                context={"stage_name": sn, "error_summary": error_msg[:200] if error_msg else ""},
                priority=2,
                sequences=(event.sequence,),
            ))

        elif event.event_type == EventType.EXECUTION_FAILED:
            sn = event.payload.get("stage_name", "unknown")
            error_msg = event.payload.get("error", "")
            content = {
                "stage_name": sn,
                "error_message": error_msg,
                "execution_id": eid,
                "sequence": event.sequence,
                "timestamp": event.timestamp,
                "is_terminal_error": True,
            }
            candidates.append(_make_candidate(
                eid=eid,
                ctype=CandidateType.ERROR_DETAIL,
                content=content,
                context={"stage_name": sn, "error_summary": error_msg[:200] if error_msg else ""},
                priority=2,
                sequences=(event.sequence,),
            ))

    return candidates


def _make_notable_candidates(
    eid: str,
    events: Tuple[ExecutionEvent, ...],
    graph: "RuntimeGraph",
) -> "list[MemoryCandidate]":
    """Create candidates for notable events: retries, forks, crashes."""
    candidates: list[MemoryCandidate] = []

    for event in events:
        if event.event_type == EventType.RETRY_INCREMENTED:
            retry_num = event.payload.get("retry_number", 0)
            content = {
                "event_type": "retry",
                "retry_number": retry_num,
                "sequence": event.sequence,
                "timestamp": event.timestamp,
                "total_retries_in_execution": graph.retry_count,
            }
            candidates.append(_make_candidate(
                eid=eid,
                ctype=CandidateType.NOTABLE_EVENT,
                content=content,
                context={"event_subtype": "retry"},
                priority=1,
                sequences=(event.sequence,),
            ))

        elif event.event_type == EventType.FORK_CREATED:
            content = {
                "event_type": "fork",
                "original_execution_id": event.payload.get("original_execution_id", ""),
                "forked_at_sequence": event.payload.get("forked_at_sequence", 0),
                "sequence": event.sequence,
                "timestamp": event.timestamp,
            }
            candidates.append(_make_candidate(
                eid=eid,
                ctype=CandidateType.NOTABLE_EVENT,
                content=content,
                context={"event_subtype": "fork"},
                priority=1,
                sequences=(event.sequence,),
            ))

        elif event.event_type == EventType.EXECUTION_CRASHED:
            content = {
                "event_type": "crash",
                "sequence": event.sequence,
                "timestamp": event.timestamp,
                "recovered": event.payload.get("recovered", False),
            }
            candidates.append(_make_candidate(
                eid=eid,
                ctype=CandidateType.NOTABLE_EVENT,
                content=content,
                context={"event_subtype": "crash"},
                priority=2,
                sequences=(event.sequence,),
            ))

    return candidates


def _make_pipeline_candidate(
    eid: str,
    events: Tuple[ExecutionEvent, ...],
    graph: "RuntimeGraph",
    metrics: "RuntimeMetrics",
) -> MemoryCandidate:
    """Create a pipeline structure candidate."""
    stage_durations = metrics.stage_duration_map
    content = {
        "stage_order": list(graph.stage_order),
        "total_stages": len(graph.stage_order),
        "completed_stages": metrics.completed_stages,
        "failed_stages": metrics.failed_stages,
        "failed_stage_names": list(metrics.failed_stage_names),
        "stage_durations": dict(stage_durations),
        "longest_stage": metrics.longest_stage,
        "average_stage_duration_ms": metrics.average_stage_duration_ms,
        "total_duration_ms": graph.duration_ms,
    }
    return _make_candidate(
        eid=eid,
        ctype=CandidateType.PIPELINE_STRUCTURE,
        content=content,
        context={"graph_hash": graph.graph_hash, "pipeline_hash": metrics.execution_id},
        priority=0,
        sequences=tuple(range(len(events))),
    )


def _find_stage_position(
    stage_name: str,
    stage_order: "Tuple[str, ...]",
) -> int:
    """Find the position of a stage in the pipeline order (-1 if not found)."""
    for i, name in enumerate(stage_order):
        if name == stage_name:
            return i
    return -1


# ═══════════════════════════════════════════════════════════════════════
# Candidate query helpers (read-only)
# ═══════════════════════════════════════════════════════════════════════

def get_candidates_by_type(
    candidates: "Tuple[MemoryCandidate, ...]",
    candidate_type: str,
) -> "Tuple[MemoryCandidate, ...]":
    """Filter candidates by type."""
    return tuple(c for c in candidates if c.candidate_type == candidate_type)


def get_error_candidates(
    candidates: "Tuple[MemoryCandidate, ...]",
) -> "Tuple[MemoryCandidate, ...]":
    """Get all error detail candidates."""
    return get_candidates_by_type(candidates, CandidateType.ERROR_DETAIL)


def get_high_priority_candidates(
    candidates: "Tuple[MemoryCandidate, ...]",
) -> "Tuple[MemoryCandidate, ...]":
    """Get candidates with priority > 1 (important)."""
    return tuple(c for c in candidates if c.priority >= 2)


def compute_candidate_fingerprint(
    candidates: "Tuple[MemoryCandidate, ...]",
) -> str:
    """Deterministic fingerprint of all candidates."""
    parts = [c.candidate_id for c in candidates]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
