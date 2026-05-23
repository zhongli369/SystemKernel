"""
Observability/ — Pure Observability Layer (v1.0 — Phase 3)

SystemKernel Phase 3: record everything, decide nothing.

ALL observability is:
  - Write-only: records behavior, never influences it
  - Removable: if deleted, kernel behavior is unchanged
  - Append-only: no aggregation logic, no inference
  - Deterministic: same event → same trace record

Architecture:
  Kernel subsystems ──► Observability.trace ──► disk (traces/)
  Kernel subsystems ──► Observability.metrics ──► disk (metrics/)
  Observability.replay ─── reads traces/ from disk

Key guarantees:
  - ZERO AI/LLM calls in observability layer
  - ZERO influence on kernel behavior
  - ZERO modification of Phase 1/2 structures
  - Append-only storage (JSONL files on disk)

Usage:
    from Observability import trace, metrics, replay

    # Record a trace span
    trace.record(stage="event", span_id="...", data={...})

    # Record a metric point
    metrics.record("routing_latency_ms", 42.5, tags={"skill": "code-review"})

    # Replay a trace
    chain = replay.replay_trace("trace-id-here")
"""

from Observability.trace import (
    TraceSpan,
    TraceCollector,
    record_span,
    get_trace_chain,
    TRACE_STAGES,
)
from Observability.metrics import (
    MetricPoint,
    MetricsCollector,
    record_metric,
    get_metric_summary,
    METRIC_TYPES,
)
from Observability.replay import (
    ReplayEngine,
    replay_trace,
    ReplayResult,
)
from Observability.dashboard import (
    view_trace,
    list_recent_traces,
    view_metrics,
    view_all_metrics,
    view_execution_report,
    compare_traces,
)

__all__ = [
    # Trace
    "TraceSpan", "TraceCollector", "record_span", "get_trace_chain", "TRACE_STAGES",
    # Metrics
    "MetricPoint", "MetricsCollector", "record_metric", "get_metric_summary", "METRIC_TYPES",
    # Replay
    "ReplayEngine", "replay_trace", "ReplayResult",
    # Dashboard
    "view_trace", "list_recent_traces", "view_metrics", "view_all_metrics",
    "view_execution_report", "compare_traces",
]
