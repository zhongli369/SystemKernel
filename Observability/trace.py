"""
trace.py — Unified Trace System (v1.0 — Phase 3)

Immutable trace span model with full parent-child chain support.
Append-only JSONL storage. Zero intelligence. Zero side effects.

Trace chain: event → task → routing → execution → validation

Key guarantees:
  - 1 event = 1 trace_id (propagates through all downstream spans)
  - Every span carries parent_span_id for full lineage
  - Append-only — traces are NEVER modified after writing
  - Removable — deleting traces/ has zero impact on kernel behavior
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Trace stages — closed set, deterministic
# ═══════════════════════════════════════════════════════════════════════════════

TRACE_STAGES = frozenset({
    "event",       # EventBus ingestion
    "task",        # TaskSystem task creation
    "routing",     # Adapter skill routing
    "execution",   # ExecutionLoop execution
    "validation",  # ExecutionLoop verification
    "replay",      # Replay system re-execution
})


# ═══════════════════════════════════════════════════════════════════════════════
# Trace span data model (frozen)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TraceSpan:
    """A single immutable point in the execution timeline.

    Every span is linked to its parent via parent_span_id.
    The full chain is reconstructable from span records alone.
    """
    span_id: str
    trace_id: str
    parent_span_id: str          # "" for root span (event)
    stage: str                   # one of TRACE_STAGES
    timestamp: str               # ISO-8601
    data: dict                   # stage-specific payload
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "data": self.data,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Trace collector — pure record sink
# ═══════════════════════════════════════════════════════════════════════════════

class TraceCollector:
    """Append-only trace recorder. Writes JSONL to disk.

    PURE I/O. No intelligence. No aggregation. No decisions.

    Usage:
        collector = TraceCollector()
        span = collector.record(
            stage="event",
            trace_id="evt-123",
            data={"event_type": "cli.task.create"},
        )
        # Continue trace...
        collector.record(
            stage="task",
            trace_id="evt-123",
            parent_span_id=span.span_id,
            data={"task_id": "T-001"},
        )
    """

    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = str(
                Path(__file__).resolve().parent.parent / "traces"
            )
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _trace_file(self) -> Path:
        """Get today's trace file path (partitioned by date)."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir = self._storage_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir / "trace.jsonl"

    def record(
        self,
        stage: str,
        data: dict,
        trace_id: str = "",
        parent_span_id: str = "",
        metadata: dict = None,
    ) -> TraceSpan:
        """Record a single trace span.

        Pure append. No side effects beyond file write.
        Returns the created span (immutable).

        Args:
            stage: One of TRACE_STAGES.
            data: Stage-specific payload dict.
            trace_id: Trace ID (auto-generated if empty — starts new trace).
            parent_span_id: Parent span ID (empty for root span).
            metadata: Optional additional metadata.

        Returns:
            TraceSpan — immutable, created.
        """
        if trace_id:
            tid = trace_id
        else:
            tid = str(uuid.uuid4())

        span = TraceSpan(
            span_id=str(uuid.uuid4()),
            trace_id=tid,
            parent_span_id=parent_span_id,
            stage=stage,
            timestamp=self._now(),
            data=data,
            metadata=metadata or {},
        )

        # Append to JSONL file
        trace_file = self._trace_file()
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(span.to_json() + "\n")

        return span

    def get_chain(self, trace_id: str, date_str: str = None) -> list[TraceSpan]:
        """Retrieve all spans for a trace_id, sorted by timestamp.

        Args:
            trace_id: The trace to retrieve.
            date_str: Optional date partition (YYYY-MM-DD). Searches all dates if None.

        Returns:
            List of TraceSpan objects in temporal order.
        """
        spans = []

        if date_str:
            trace_file = self._storage_dir / date_str / "trace.jsonl"
            if trace_file.exists():
                spans = self._read_spans_from_file(trace_file, trace_id)
        else:
            # Search all date partitions
            for date_dir in sorted(self._storage_dir.iterdir()):
                if not date_dir.is_dir():
                    continue
                trace_file = date_dir / "trace.jsonl"
                if trace_file.exists():
                    spans.extend(self._read_spans_from_file(trace_file, trace_id))

        # Sort by timestamp
        spans.sort(key=lambda s: s.timestamp)
        return spans

    def _read_spans_from_file(self, filepath: Path, trace_id: str) -> list[TraceSpan]:
        """Read spans matching trace_id from a JSONL file."""
        spans = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        if d.get("trace_id") == trace_id:
                            spans.append(TraceSpan(
                                span_id=d["span_id"],
                                trace_id=d["trace_id"],
                                parent_span_id=d["parent_span_id"],
                                stage=d["stage"],
                                timestamp=d["timestamp"],
                                data=d.get("data", {}),
                                metadata=d.get("metadata", {}),
                            ))
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            pass
        return spans

    def list_traces(self, date_str: str = None, limit: int = 100) -> list[str]:
        """List distinct trace_ids in storage.

        Args:
            date_str: Optional date partition filter.
            limit: Maximum number of trace_ids to return.

        Returns:
            List of distinct trace_id strings.
        """
        trace_ids: set[str] = set()

        dirs = [self._storage_dir / date_str] if date_str else sorted(self._storage_dir.iterdir())
        for entry in dirs:
            if not isinstance(entry, Path) or not entry.is_dir():
                continue
            trace_file = entry / "trace.jsonl"
            if not trace_file.exists():
                continue
            try:
                with open(trace_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            trace_ids.add(d.get("trace_id", ""))
                            if len(trace_ids) >= limit:
                                break
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue
            if len(trace_ids) >= limit:
                break

        return sorted(trace_ids)[:limit]


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience: global singleton collector
# ═══════════════════════════════════════════════════════════════════════════════

_collector: Optional[TraceCollector] = None


def _get_collector() -> TraceCollector:
    """Get or create the global TraceCollector singleton.

    Module-level singleton — the ONLY mutable state in trace.py.
    This is a lazy-initialized cache, not a decision engine.
    """
    global _collector
    if _collector is None:
        _collector = TraceCollector()
    return _collector


def record_span(
    stage: str,
    data: dict,
    trace_id: str = "",
    parent_span_id: str = "",
    metadata: dict = None,
) -> TraceSpan:
    """Record a trace span to the global collector.

    Convenience function. Same as TraceCollector.record().
    """
    return _get_collector().record(
        stage=stage,
        data=data,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        metadata=metadata,
    )


def get_trace_chain(trace_id: str, date_str: str = None) -> list[TraceSpan]:
    """Retrieve the full trace chain for a trace_id.

    Convenience function. Same as TraceCollector.get_chain().
    """
    return _get_collector().get_chain(trace_id, date_str)
