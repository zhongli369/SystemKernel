"""
metrics.py — Append-Only Metrics Collector (v1.0 — Phase 3)

Records system metrics. PURELY a write-only log sink.

Core metrics:
  - routing_latency_ms
  - execution_latency_ms
  - validation_success_rate (derived from execution results)
  - retry_rate
  - skill_hit_rate
  - event_throughput

Key guarantees:
  - Append-only: metrics are NEVER modified after writing
  - No aggregation logic: raw data only
  - No inference: no anomaly detection, no optimization
  - Zero AI: no LLM calls
  - Removable: deleting metrics/ has zero impact on kernel behavior
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Metric types — closed set
# ═══════════════════════════════════════════════════════════════════════════════

METRIC_TYPES = frozenset({
    "routing_latency_ms",       # duration of Adapter.resolve()
    "execution_latency_ms",     # duration of ExecutionLoop.run()
    "validation_passed",        # 1 or 0 (per check)
    "retry",                    # 1 if retry occurred, 0 if not
    "skill_hit",                # 1 if skill matched, 0 if empty binding
    "event_throughput",         # count of events per unit time
    "trace_span_count",         # number of spans in a trace
})


# ═══════════════════════════════════════════════════════════════════════════════
# Metric point data model
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MetricPoint:
    """A single immutable metric observation.

    No aggregation. No interpretation. Just a data point.
    """
    timestamp: str
    metric_type: str
    value: float
    tags: dict = field(default_factory=dict)
    trace_id: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "metric_type": self.metric_type,
            "value": self.value,
            "tags": self.tags,
            "trace_id": self.trace_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Metrics collector — append-only record sink
# ═══════════════════════════════════════════════════════════════════════════════

class MetricsCollector:
    """Append-only metrics recorder. Writes JSONL to disk.

    PURE I/O. No intelligence. No aggregation. No decisions.

    Usage:
        collector = MetricsCollector()
        collector.record("routing_latency_ms", 42.5, tags={"skill": "code-review"})
        collector.record("skill_hit", 1, tags={"skill": "debugger"})
    """

    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = str(
                Path(__file__).resolve().parent.parent / "metrics"
            )
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _metric_file(self, metric_type: str) -> Path:
        """Get the metric file path (partitioned by metric type)."""
        metric_dir = self._storage_dir / metric_type
        metric_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return metric_dir / f"{date_str}.jsonl"

    def record(
        self,
        metric_type: str,
        value: float,
        tags: dict = None,
        trace_id: str = "",
    ) -> MetricPoint:
        """Record a single metric observation.

        Pure append. No side effects beyond file write.

        Args:
            metric_type: One of METRIC_TYPES (or custom).
            value: Numeric value.
            tags: Optional tag dict for filtering/grouping.
            trace_id: Optional trace correlation ID.

        Returns:
            MetricPoint — immutable, created.
        """
        point = MetricPoint(
            timestamp=self._now(),
            metric_type=metric_type,
            value=value,
            tags=tags or {},
            trace_id=trace_id,
        )

        metric_file = self._metric_file(metric_type if metric_type in METRIC_TYPES else "custom")
        with open(metric_file, "a", encoding="utf-8") as f:
            f.write(point.to_json() + "\n")

        return point

    def get_points(
        self,
        metric_type: str,
        date_str: str = None,
        limit: int = 1000,
    ) -> list[MetricPoint]:
        """Retrieve metric points for a given type and date.

        Args:
            metric_type: Metric type to query.
            date_str: Date partition (YYYY-MM-DD). Uses today if None.
            limit: Max points to return.

        Returns:
            List of MetricPoint objects in temporal order.
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        metric_file = self._storage_dir / metric_type / f"{date_str}.jsonl"
        if not metric_file.exists():
            # Try custom directory
            metric_file = self._storage_dir / "custom" / f"{date_str}.jsonl"
            if not metric_file.exists():
                return []

        points = []
        try:
            with open(metric_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        if d.get("metric_type") == metric_type or metric_type == "custom":
                            points.append(MetricPoint(
                                timestamp=d["timestamp"],
                                metric_type=d["metric_type"],
                                value=d["value"],
                                tags=d.get("tags", {}),
                                trace_id=d.get("trace_id", ""),
                            ))
                    except (json.JSONDecodeError, KeyError):
                        continue
                    if len(points) >= limit:
                        break
        except OSError:
            pass

        return points

    def get_summary(self, metric_type: str, date_str: str = None) -> dict:
        """Get a simple statistical summary for a metric type.

        PURE COMPUTATION over stored data. No inference. No decisions.
        Returns raw stats: count, sum, min, max, mean.

        Args:
            metric_type: Metric type to summarize.
            date_str: Date partition. Uses today if None.

        Returns:
            Dict with count, sum, min, max, mean keys.
        """
        points = self.get_points(metric_type, date_str)
        if not points:
            return {"count": 0, "sum": 0, "min": 0, "max": 0, "mean": 0}

        values = [p.value for p in points]
        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values) if values else 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience: global singleton collector
# ═══════════════════════════════════════════════════════════════════════════════

_collector: Optional[MetricsCollector] = None


def _get_collector() -> MetricsCollector:
    """Get or create the global MetricsCollector singleton.

    Module-level singleton — the ONLY mutable state in metrics.py.
    This is a lazy-initialized cache, not a decision engine.
    """
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


def record_metric(
    metric_type: str,
    value: float,
    tags: dict = None,
    trace_id: str = "",
) -> MetricPoint:
    """Record a metric point to the global collector.

    Convenience function. Same as MetricsCollector.record().
    """
    return _get_collector().record(
        metric_type=metric_type,
        value=value,
        tags=tags,
        trace_id=trace_id,
    )


def get_metric_summary(metric_type: str, date_str: str = None) -> dict:
    """Get metric summary from the global collector.

    Convenience function. Same as MetricsCollector.get_summary().
    """
    return _get_collector().get_summary(metric_type, date_str)
