"""
Metrics Exporter — Prometheus-compatible metrics in text and JSON format.

Extends the kernel-level metrics (Observability/metrics.py) with L5
production metrics: cost, latency, evidence, complexity, stability.

Outputs Prometheus text format (no prometheus_client dependency) and
JSON format for Grafana/API consumption.

Pull-mode only. No push. No real-time streaming.
Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Metric Types (Prometheus-compatible)
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CounterMetric:
    """Monotonically increasing counter."""
    name: str = ""
    help: str = ""
    value: float = 0.0
    labels: Tuple[Tuple[str, str], ...] = ()  # (key, value) pairs

    def to_prometheus(self) -> str:
        label_str = ""
        if self.labels:
            label_str = "{" + ",".join(f'{k}="{v}"' for k, v in self.labels) + "}"
        lines = [
            f"# HELP {self.name} {self.help}",
            f"# TYPE {self.name} counter",
            f"{self.name}{label_str} {self.value}",
        ]
        return "\n".join(lines)


@dataclass(frozen=True)
class GaugeMetric:
    """Value that can go up and down."""
    name: str = ""
    help: str = ""
    value: float = 0.0
    labels: Tuple[Tuple[str, str], ...] = ()

    def to_prometheus(self) -> str:
        label_str = ""
        if self.labels:
            label_str = "{" + ",".join(f'{k}="{v}"' for k, v in self.labels) + "}"
        lines = [
            f"# HELP {self.name} {self.help}",
            f"# TYPE {self.name} gauge",
            f"{self.name}{label_str} {self.value}",
        ]
        return "\n".join(lines)


@dataclass(frozen=True)
class HistogramMetric:
    """Distribution with configurable buckets."""
    name: str = ""
    help: str = ""
    sum: float = 0.0
    count: int = 0
    buckets: Tuple[Tuple[float, int], ...] = ()  # (upper_bound, count)
    labels: Tuple[Tuple[str, str], ...] = ()

    def to_prometheus(self) -> str:
        label_str = ""
        if self.labels:
            label_str = "{" + ",".join(f'{k}="{v}"' for k, v in self.labels) + "}"
        lines = [
            f"# HELP {self.name} {self.help}",
            f"# TYPE {self.name} histogram",
        ]
        for upper, cnt in self.buckets:
            lines.append(f"{self.name}_bucket{label_str},le=\"{upper}\" {cnt}")
        lines.append(f"{self.name}_bucket{label_str},le=\"+Inf\" {self.count}")
        lines.append(f"{self.name}_sum{label_str} {self.sum}")
        lines.append(f"{self.name}_count{label_str} {self.count}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Metrics Exporter
# ═══════════════════════════════════════════════════════════════════════

# Standard latency buckets (seconds)
LATENCY_BUCKETS = (0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0)


class MetricsExporter:
    """Collects and exports SystemKernel production metrics.

    Extends kernel/observability.py metrics with L5 dimensions:
    cost, latency, evidence, complexity, stability.
    """

    def __init__(self):
        self._executions_total: float = 0.0
        self._routes_total: dict[str, float] = {}
        self._errors_total: dict[str, float] = {}
        self._cost_tokens_total: dict[str, float] = {}
        self._cost_usd_total: float = 0.0
        self._execution_latency_buckets: list[float] = []
        self._sandbox_lifetime_buckets: list[float] = []
        self._evidence_records_total: dict[str, float] = {}
        self._complexity_score: float = 1.0
        self._stability_freeze_score: float = 100.0

    # ── Record helpers ─────────────────────────────────────────────────

    def inc_executions(self, delta: float = 1.0) -> None:
        self._executions_total += delta

    def inc_routes(self, skill_id: str, delta: float = 1.0) -> None:
        self._routes_total[skill_id] = self._routes_total.get(skill_id, 0.0) + delta

    def inc_errors(self, error_type: str, delta: float = 1.0) -> None:
        self._errors_total[error_type] = self._errors_total.get(error_type, 0.0) + delta

    def add_cost(self, model: str, tokens: int, cost_usd: float) -> None:
        self._cost_tokens_total[model] = self._cost_tokens_total.get(model, 0.0) + tokens
        self._cost_usd_total += cost_usd

    def record_latency(self, seconds: float) -> None:
        self._execution_latency_buckets.append(seconds)

    def record_sandbox_lifetime(self, seconds: float) -> None:
        self._sandbox_lifetime_buckets.append(seconds)

    def inc_evidence(self, evidence_type: str, delta: float = 1.0) -> None:
        self._evidence_records_total[evidence_type] = (
            self._evidence_records_total.get(evidence_type, 0.0) + delta
        )

    def set_complexity(self, score: float) -> None:
        self._complexity_score = score

    def set_stability(self, score: float) -> None:
        self._stability_freeze_score = score

    # ── Persistence ─────────────────────────────────────────────────

    def dump_to_disk(self, path: str) -> str:
        """Serialize current metrics to a JSON file.

        Returns the absolute path written.
        """
        data = {
            "executions_total": self._executions_total,
            "routes_total": dict(self._routes_total),
            "errors_total": dict(self._errors_total),
            "cost_tokens_total": dict(self._cost_tokens_total),
            "cost_usd_total": self._cost_usd_total,
            "execution_latency_buckets": self._execution_latency_buckets,
            "sandbox_lifetime_buckets": self._sandbox_lifetime_buckets,
            "evidence_records_total": dict(self._evidence_records_total),
            "complexity_score": self._complexity_score,
            "stability_freeze_score": self._stability_freeze_score,
            "dumped_at": datetime.now(timezone.utc).isoformat(),
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return os.path.abspath(path)

    def load_from_disk(self, path: str) -> bool:
        """Restore metrics from a JSON file previously written by dump_to_disk.

        Returns True if load succeeded, False if file missing or corrupt.
        """
        if not os.path.isfile(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False
        self._executions_total = data.get("executions_total", 0.0)
        self._routes_total = data.get("routes_total", {})
        self._errors_total = data.get("errors_total", {})
        self._cost_tokens_total = data.get("cost_tokens_total", {})
        self._cost_usd_total = data.get("cost_usd_total", 0.0)
        self._execution_latency_buckets = data.get("execution_latency_buckets", [])
        self._sandbox_lifetime_buckets = data.get("sandbox_lifetime_buckets", [])
        self._evidence_records_total = data.get("evidence_records_total", {})
        self._complexity_score = data.get("complexity_score", 1.0)
        self._stability_freeze_score = data.get("stability_freeze_score", 100.0)
        return True

    def reset(self) -> None:
        """Reset all metrics to zero. For testing only."""
        self._executions_total = 0.0
        self._routes_total.clear()
        self._errors_total.clear()
        self._cost_tokens_total.clear()
        self._cost_usd_total = 0.0
        self._execution_latency_buckets.clear()
        self._sandbox_lifetime_buckets.clear()
        self._evidence_records_total.clear()
        self._complexity_score = 1.0
        self._stability_freeze_score = 100.0

    # ── Bucket helpers ─────────────────────────────────────────────────

    @staticmethod
    def _build_histogram_buckets(values: list[float], bucket_defs: Tuple[float, ...]) -> Tuple[Tuple[float, int], ...]:
        buckets: list[Tuple[float, int]] = []
        for upper in sorted(bucket_defs):
            count = sum(1 for v in values if v <= upper)
            buckets.append((upper, count))
        return tuple(buckets)

    # ── Export methods ─────────────────────────────────────────────────

    def export_metrics(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines: list[str] = []

        # Counter: executions
        lines.append(CounterMetric(
            name="systemkernel_executions_total",
            help="Total number of kernel executions.",
            value=self._executions_total,
        ).to_prometheus())

        # Counter: routes (per skill)
        for skill_id, count in sorted(self._routes_total.items()):
            lines.append(CounterMetric(
                name="systemkernel_routes_total",
                help="Total route resolutions per skill.",
                value=count,
                labels=(("skill_id", skill_id),),
            ).to_prometheus())

        # Counter: errors (per error_type)
        for error_type, count in sorted(self._errors_total.items()):
            lines.append(CounterMetric(
                name="systemkernel_errors_total",
                help="Total errors by type.",
                value=count,
                labels=(("error_type", error_type),),
            ).to_prometheus())

        # Counter: cost tokens (per model)
        for model, tokens in sorted(self._cost_tokens_total.items()):
            lines.append(CounterMetric(
                name="systemkernel_cost_tokens_total",
                help="Total tokens consumed per model.",
                value=tokens,
                labels=(("model", model),),
            ).to_prometheus())

        # Counter: cost USD
        lines.append(CounterMetric(
            name="systemkernel_cost_usd_total",
            help="Total estimated USD cost.",
            value=self._cost_usd_total,
        ).to_prometheus())

        # Histogram: execution latency
        latency_buckets = self._build_histogram_buckets(
            self._execution_latency_buckets, LATENCY_BUCKETS
        )
        lines.append(HistogramMetric(
            name="systemkernel_execution_latency_seconds",
            help="Execution latency in seconds.",
            sum=sum(self._execution_latency_buckets),
            count=len(self._execution_latency_buckets),
            buckets=latency_buckets,
        ).to_prometheus())

        # Histogram: sandbox lifetime
        sandbox_buckets = self._build_histogram_buckets(
            self._sandbox_lifetime_buckets, LATENCY_BUCKETS
        )
        lines.append(HistogramMetric(
            name="systemkernel_sandbox_lifetime_seconds",
            help="Sandbox lifetime in seconds.",
            sum=sum(self._sandbox_lifetime_buckets),
            count=len(self._sandbox_lifetime_buckets),
            buckets=sandbox_buckets,
        ).to_prometheus())

        # Counter: evidence records (per type)
        for evidence_type, count in sorted(self._evidence_records_total.items()):
            lines.append(CounterMetric(
                name="systemkernel_evidence_records_total",
                help="Total evidence records by type.",
                value=count,
                labels=(("evidence_type", evidence_type),),
            ).to_prometheus())

        # Gauge: complexity
        lines.append(GaugeMetric(
            name="systemkernel_complexity_score",
            help="Current complexity budget score.",
            value=self._complexity_score,
        ).to_prometheus())

        # Gauge: stability freeze
        lines.append(GaugeMetric(
            name="systemkernel_stability_freeze_score",
            help="Stability freeze score (0-100).",
            value=self._stability_freeze_score,
        ).to_prometheus())

        return "\n".join(lines) + "\n"

    def export_json(self) -> dict:
        """Export all metrics as JSON dict (for Grafana/API)."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "systemkernel_executions_total": self._executions_total,
                "systemkernel_routes_total": dict(sorted(self._routes_total.items())),
                "systemkernel_errors_total": dict(sorted(self._errors_total.items())),
                "systemkernel_cost_tokens_total": dict(sorted(self._cost_tokens_total.items())),
                "systemkernel_cost_usd_total": round(self._cost_usd_total, 6),
                "systemkernel_execution_latency_seconds": {
                    "sum": sum(self._execution_latency_buckets),
                    "count": len(self._execution_latency_buckets),
                    "buckets": [
                        {"le": str(u), "count": c}
                        for u, c in self._build_histogram_buckets(
                            self._execution_latency_buckets, LATENCY_BUCKETS
                        )
                    ],
                },
                "systemkernel_sandbox_lifetime_seconds": {
                    "sum": sum(self._sandbox_lifetime_buckets),
                    "count": len(self._sandbox_lifetime_buckets),
                },
                "systemkernel_evidence_records_total": dict(sorted(self._evidence_records_total.items())),
                "systemkernel_complexity_score": self._complexity_score,
                "systemkernel_stability_freeze_score": self._stability_freeze_score,
            },
        }


# ═══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════

# Singleton exporter instance for module-level access
_exporter = MetricsExporter()


def export_metrics() -> str:
    """Return Prometheus text format metrics from the singleton exporter."""
    return _exporter.export_metrics()


def export_metrics_json() -> dict:
    """Return JSON metrics from the singleton exporter."""
    return _exporter.export_json()


def get_exporter() -> MetricsExporter:
    """Get the module-level MetricsExporter instance."""
    return _exporter


def get_dashboard_spec() -> dict:
    """Return the Grafana dashboard specification."""
    spec_path = os.path.join(os.path.dirname(__file__), "ops_dashboard_spec.json")
    try:
        with open(spec_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
