"""
ObservabilityService v3.0 — Trace + Metrics + ccusage Bridge.

Upgrades over v2:
  - Token + cost tracking (ccusage-compatible JSONL)
  - Cost budget enforcement
  - ccusage export bridge

ZERO LLM. Write-only for kernel behavior. Removable without kernel impact.

Storage:
  traces/  → YYYY-MM-DD/trace.jsonl
  metrics/ → {metric_type}/YYYY-MM-DD.jsonl
  cost/    → YYYY-MM-DD/usage.jsonl (ccusage-compatible)
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# Trace
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TraceSpan:
    span_id: str
    trace_id: str
    parent_span_id: str
    stage: str          # event|task|routing|execution|validation|replay
    timestamp: str       # ISO-8601
    data: dict
    metadata: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MetricPoint:
    timestamp: str
    metric_type: str
    value: float
    tags: dict = field(default_factory=dict)
    trace_id: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Cost
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CostSnapshot:
    timestamp: str
    input_tokens: int
    output_tokens: int
    cache_create_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    model: str = "unknown"


# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ObservabilityConfig:
    traces_path: str = "./v3/traces/"
    metrics_path: str = "./v3/metrics/"
    cost_tracking: bool = True
    cost_budget_usd: float = 0.0  # 0 = unlimited


# ═══════════════════════════════════════════════════════════════════════
# ObservabilityService
# ═══════════════════════════════════════════════════════════════════════

class ObservabilityService:
    """v3 Observability — write-only, zero LLM, removable.

    Key guarantees:
      - Write-only: records behavior, never drives it
      - Append-only: JSONL, never modified after write
      - Removable: delete traces/ + metrics/ → zero kernel impact
      - No intelligence: zero LLM calls, zero decisions
    """

    def __init__(self, config: Optional[ObservabilityConfig] = None):
        self.config = config or ObservabilityConfig()
        os.makedirs(self.config.traces_path, exist_ok=True)
        os.makedirs(self.config.metrics_path, exist_ok=True)
        self._budget_warned = False

    # ── Trace ──────────────────────────────────────────────────────

    def log_event(
        self,
        stage: str,
        data: dict,
        trace_id: str = "",
        parent_span_id: str = "",
        metadata: Optional[dict] = None,
    ) -> TraceSpan:
        """Record a trace span. Non-blocking. Exceptions swallowed."""
        span = TraceSpan(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id or str(uuid.uuid4()),
            parent_span_id=parent_span_id,
            stage=stage,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
            metadata=metadata or {},
        )
        try:
            self._write_trace(span)
        except Exception:
            pass
        return span

    def _write_trace(self, span: TraceSpan) -> None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        trace_dir = os.path.join(self.config.traces_path, date_str)
        os.makedirs(trace_dir, exist_ok=True)
        fpath = os.path.join(trace_dir, "trace.jsonl")
        with open(fpath, "a") as f:
            f.write(json.dumps(asdict(span), ensure_ascii=False) + "\n")

    def get_trace_chain(self, trace_id: str, date_str: Optional[str] = None) -> list[dict]:
        """Read a trace chain from disk. Deterministic replay."""
        date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        trace_dir = os.path.join(self.config.traces_path, date_str)
        fpath = os.path.join(trace_dir, "trace.jsonl")
        if not os.path.exists(fpath):
            return []
        spans = []
        with open(fpath) as f:
            for line in f:
                record = json.loads(line.strip())
                if record.get("trace_id") == trace_id:
                    spans.append(record)
        return spans

    # ── Metrics ────────────────────────────────────────────────────

    def emit_metrics(
        self,
        metric_type: str,
        value: float,
        tags: Optional[dict] = None,
        trace_id: str = "",
    ) -> MetricPoint:
        """Record a metric point. Non-blocking. Exceptions swallowed."""
        point = MetricPoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_type=metric_type,
            value=value,
            tags=tags or {},
            trace_id=trace_id,
        )
        try:
            self._write_metric(point)
        except Exception:
            pass
        return point

    def _write_metric(self, point: MetricPoint) -> None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        metric_dir = os.path.join(self.config.metrics_path, point.metric_type)
        os.makedirs(metric_dir, exist_ok=True)
        fpath = os.path.join(metric_dir, f"{date_str}.jsonl")
        with open(fpath, "a") as f:
            f.write(json.dumps(asdict(point), ensure_ascii=False) + "\n")

    def get_metric_summary(self, metric_type: str, date_str: Optional[str] = None) -> dict:
        """Read metric summary. Deterministic."""
        date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        metric_dir = os.path.join(self.config.metrics_path, metric_type)
        fpath = os.path.join(metric_dir, f"{date_str}.jsonl")
        if not os.path.exists(fpath):
            return {"count": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0}
        values = []
        with open(fpath) as f:
            for line in f:
                record = json.loads(line.strip())
                values.append(record.get("value", 0.0))
        if not values:
            return {"count": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0}
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    # ── Cost Tracking ───────────────────────────────────────────────

    def log_cost(self, snapshot: CostSnapshot) -> None:
        """Record a cost snapshot. ccusage-compatible JSONL format."""
        if not self.config.cost_tracking:
            return
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cost_dir = os.path.join(self.config.traces_path, "cost")
            os.makedirs(cost_dir, exist_ok=True)
            fpath = os.path.join(cost_dir, f"{date_str}.jsonl")
            with open(fpath, "a") as f:
                f.write(json.dumps(asdict(snapshot), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def check_budget(self) -> Optional[str]:
        """Check cost budget. Returns warning string if approaching limit."""
        if not self.config.cost_tracking or self.config.cost_budget_usd <= 0:
            return None
        total = self._get_total_cost()
        if total >= self.config.cost_budget_usd:
            return f"BUDGET EXCEEDED: ${total:.2f} / ${self.config.cost_budget_usd:.2f}"
        pct = total / self.config.cost_budget_usd
        if pct >= 0.95 and not self._budget_warned:
            self._budget_warned = True
        if pct >= 0.80:
            return f"BUDGET WARNING: ${total:.2f} / ${self.config.cost_budget_usd:.2f} ({pct:.0%})"
        return None

    def _get_total_cost(self) -> float:
        total = 0.0
        cost_dir = os.path.join(self.config.traces_path, "cost")
        if not os.path.exists(cost_dir):
            return 0.0
        for fname in os.listdir(cost_dir):
            if fname.endswith(".jsonl"):
                with open(os.path.join(cost_dir, fname)) as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            total += record.get("cost_usd", 0.0)
                        except json.JSONDecodeError:
                            pass
        return total

    # ── ccusage Bridge ──────────────────────────────────────────────

    def ccusage_bridge_stub(self, output_path: str) -> str:
        """Export traces to ccusage-compatible JSONL format.

        This is a STUB — Phase 4 will implement full conversion.
        Current: writes sample ccusage-compatible JSON for external tooling.
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        sample = {
            "session_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "model": "unknown",
            "cost_usd": 0.0,
        }
        with open(output_path, "w") as f:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        return output_path

    # ── Dashboard (simple CLI) ─────────────────────────────────────

    def status(self) -> str:
        """Return a human-readable status summary."""
        lines = [
            "════════════════════════════════",
            "  SystemKernel v3 Observability  ",
            "════════════════════════════════",
            f"  Traces:  {self.config.traces_path}",
            f"  Metrics: {self.config.metrics_path}",
            f"  Cost tracking: {'ON' if self.config.cost_tracking else 'OFF'}",
        ]
        if self.config.cost_tracking:
            total = self._get_total_cost()
            budget = self.config.cost_budget_usd
            lines.append(f"  Total cost: ${total:.4f}")
            if budget > 0:
                lines.append(f"  Budget: ${budget:.2f} ({total/budget:.1%} used)")
        lines.append("════════════════════════════════")
        return "\n".join(lines)
