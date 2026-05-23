"""
event_bus.py — EventBus Main Orchestrator (v1.0)

The central event ingestion pipeline. Orchestrates:
  source → normalize → validate → route → task_adapter → TaskSystem

ZERO LLM calls in this entire pipeline.
ALL decisions are deterministic lookups.
NO semantic analysis, classification, or prioritization.

This is a mechanical conveyor belt, not an intelligent system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from EventBus.event_schema import Event, validate, ValidationError
from EventBus.event_router import route, RoutingDecision
from EventBus.adapters.task_adapter import dispatch


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EventResult:
    """Complete trace of an event through the pipeline.

    Immutable. Every step is recorded for audit.
    """
    event: Optional[Event]           # None if validation failed
    validation_errors: tuple[ValidationError, ...]
    decision: Optional[RoutingDecision]
    task_id: Optional[str]           # TaskSystem task ID (if created)
    success: bool
    trace: str                       # Human-readable pipeline trace

    def summary(self) -> str:
        status = "OK" if self.success else "FAIL"
        task = f"task={self.task_id}" if self.task_id else "no-task"
        return f"EventResult({status}, {task}, event={self.event.event_id[:8] if self.event else '?'}...)"


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline — the ONLY way events enter the system
# ═══════════════════════════════════════════════════════════════════════════════

def ingest(raw_event: dict) -> EventResult:
    """Ingest a raw event through the full EventBus pipeline.

    Pipeline stages:
      1. validate()          — structural check (event_schema.py)
      2. route()             — deterministic mapping (event_router.py)
      3. dispatch()          — TaskSystem bridge (adapters/task_adapter.py)

    Each stage is a pure function. The pipeline itself is a pure composition
    of pure functions. The only side effect is TaskSystem task creation in
    dispatch(), which writes to disk.

    Args:
        raw_event: Raw event dict from any source (CLI, GitHub webhook, FileWatch).

    Returns:
        EventResult with full trace — event, decision, task_id, success/failure.
    """
    import uuid as _uuid
    trace_id = str(_uuid.uuid4())
    trace_lines: list[str] = []
    now = lambda: datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    event_span_id: str = ""

    # ── Stage 1: Validate ───────────────────────────────────────────────
    trace_lines.append(f"[{now()}] STAGE-1: validate")
    event, errors = validate(raw_event)

    if event is None:
        trace_lines.append(f"[{now()}] VALIDATION FAILED: {len(errors)} error(s)")
        for e in errors:
            trace_lines.append(f"  - {e}")
        return EventResult(
            event=None,
            validation_errors=tuple(errors),
            decision=None,
            task_id=None,
            success=False,
            trace="\n".join(trace_lines),
        )

    trace_lines.append(f"[{now()}] VALID: {event.summary()}")

    # ── Observability: record event span (non-invasive) ──────────────────
    try:
        from Observability.trace import record_span as _record_span
        _evt_span = _record_span(
            stage="event",
            data={"event_type": event.event_type, "source": event.source},
            trace_id=trace_id,
        )
        event_span_id = _evt_span.span_id
    except Exception:
        pass

    # ── Stage 2: Route ──────────────────────────────────────────────────
    trace_lines.append(f"[{now()}] STAGE-2: route")
    _route_start = datetime.now(timezone.utc)
    decision = route(event)
    _route_ms = (datetime.now(timezone.utc) - _route_start).total_seconds() * 1000
    trace_lines.append(f"[{now()}] ROUTED: action={decision.action} reason={decision.reason}")

    # ── Observability: record routing latency metric (non-invasive)
    try:
        from Observability.metrics import record_metric as _record_metric
        _record_metric("routing_latency_ms", _route_ms, tags={"action": decision.action}, trace_id=trace_id)
    except Exception:
        pass

    if decision.action == "skip":
        trace_lines.append(f"[{now()}] SKIP: {decision.reason}")
        return EventResult(
            event=event,
            validation_errors=(),
            decision=decision,
            task_id=None,
            success=True,  # Skip is not a failure — it's a valid decision
            trace="\n".join(trace_lines),
        )

    # ── Stage 3: Dispatch ───────────────────────────────────────────────
    trace_lines.append(f"[{now()}] STAGE-3: dispatch")
    try:
        task_id = dispatch(decision)
        if task_id:
            trace_lines.append(f"[{now()}] DISPATCHED: task_id={task_id}")
        else:
            trace_lines.append(f"[{now()}] DISPATCH FAILED: task_adapter returned None")
    except Exception as exc:
        trace_lines.append(f"[{now()}] DISPATCH ERROR: {exc}")
        return EventResult(
            event=event,
            validation_errors=(),
            decision=decision,
            task_id=None,
            success=False,
            trace="\n".join(trace_lines),
        )

    # ── Observability: record task span (non-invasive) ───────────────────
    try:
        from Observability.trace import record_span as _record_span
        _record_span(
            stage="task",
            data={"task_id": task_id, "title": decision.title, "priority": decision.priority},
            trace_id=trace_id,
            parent_span_id=event_span_id,
        )
    except Exception:
        pass

    # ── Observability: record event throughput metric (non-invasive)
    try:
        from Observability.metrics import record_metric as _record_metric
        _record_metric("event_throughput", 1, tags={"event_type": event.event_type}, trace_id=trace_id)
    except Exception:
        pass

    trace_lines.append(f"[{now()}] PIPELINE COMPLETE")

    return EventResult(
        event=event,
        validation_errors=(),
        decision=decision,
        task_id=task_id,
        success=task_id is not None,
        trace="\n".join(trace_lines),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience: source-specific ingestion
# ═══════════════════════════════════════════════════════════════════════════════

def ingest_cli(argv: list[str]) -> EventResult:
    """Ingest a CLI event. Convenience wrapper around normalize + ingest."""
    from EventBus.event_schema import normalize_cli
    raw = normalize_cli(argv)
    return ingest(raw)


def ingest_github(headers: dict, body: dict) -> EventResult:
    """Ingest a GitHub webhook event. Convenience wrapper."""
    from EventBus.event_schema import normalize_github_webhook
    raw = normalize_github_webhook(headers, body)
    return ingest(raw)


def ingest_filewatch(path: str, change_type: str) -> EventResult:
    """Ingest a file watch event. Convenience wrapper."""
    from EventBus.event_schema import normalize_filewatch
    raw = normalize_filewatch(path, change_type)
    return ingest(raw)


# ═══════════════════════════════════════════════════════════════════════════════
# Source registration — for extensibility (Phase 2+)
# ═══════════════════════════════════════════════════════════════════════════════

_SOURCES: dict[str, dict] = {}


def register_source(name: str, handler: callable) -> None:
    """Register an event source handler. NOT used for LLM-based sources."""
    if name in _SOURCES:
        raise ValueError(f"Source '{name}' already registered")
    _SOURCES[name] = {"name": name, "handler": handler}


def list_sources() -> list[str]:
    """List registered event sources."""
    return sorted(_SOURCES.keys())


def get_source(name: str) -> Optional[dict]:
    """Get a registered source by name."""
    return _SOURCES.get(name)
