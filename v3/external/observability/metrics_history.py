"""
Metrics History — Track and compare stress run trends over time.

Appends each stress run snapshot to a JSONL history file for
regression detection and trend analysis.

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple


@dataclass(frozen=True)
class ComparisonReport:
    baseline_run_id: str
    current_run_id: str
    p50_delta_pct: float
    p99_delta_pct: float
    success_rate_delta: float
    cost_delta_pct: float
    regression: bool
    regression_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "baseline_run_id": self.baseline_run_id,
            "current_run_id": self.current_run_id,
            "p50_delta_pct": round(self.p50_delta_pct, 2),
            "p99_delta_pct": round(self.p99_delta_pct, 2),
            "success_rate_delta": round(self.success_rate_delta, 4),
            "cost_delta_pct": round(self.cost_delta_pct, 2),
            "regression": self.regression,
            "regression_reason": self.regression_reason,
        }


class MetricsHistory:
    """Append-only history of stress run metrics.

    Storage: JSONL file (v3/metrics/history.jsonl).
    Each line is a snapshot of one stress run's key metrics.
    """

    def __init__(self, history_path: Optional[str] = None):
        if history_path is None:
            from pathlib import Path as _Path
            root = _Path(__file__).resolve().parent.parent.parent.parent
            history_path = str(root / "v3" / "metrics" / "history.jsonl")
        self._path = history_path

    def record(self, report) -> str:
        """Record a stress run into the history file.

        Accepts a StressReport (has latency_p50, latency_p99, passes, etc.)
        or any object with matching attributes.

        Returns the run_id assigned.
        """
        run_id = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
        snapshot = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runs": getattr(report, "runs", 0),
            "p50_ms": getattr(report, "latency_p50", 0),
            "p99_ms": getattr(report, "latency_p99", 0),
            "success_rate": getattr(report, "passes", 0) / max(getattr(report, "runs", 1), 1),
            "total_cost_usd": getattr(report, "total_cost_usd", 0),
        }
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
        return run_id

    def compare(self, baseline_run_id: str) -> Optional[ComparisonReport]:
        """Compare the latest run against a baseline run.

        Regression is flagged if p99 degraded >20%.
        """
        records = self._read_all()
        if len(records) < 2:
            return None

        baseline = None
        current = records[-1]  # latest
        for r in records:
            if r.get("run_id") == baseline_run_id:
                baseline = r
                break

        if baseline is None:
            return None

        p50_delta = _pct_change(baseline["p50_ms"], current["p50_ms"])
        p99_delta = _pct_change(baseline["p99_ms"], current["p99_ms"])
        cost_delta = _pct_change(baseline["total_cost_usd"], current["total_cost_usd"])
        sr_delta = current["success_rate"] - baseline["success_rate"]

        regression = False
        reason = ""
        if p99_delta > 20:
            regression = True
            reason = f"p99 degraded {p99_delta:.1f}% (>{20}% threshold)"
        elif sr_delta < -0.05:
            regression = True
            reason = f"Success rate dropped {abs(sr_delta)*100:.1f}%"

        return ComparisonReport(
            baseline_run_id=baseline_run_id,
            current_run_id=current["run_id"],
            p50_delta_pct=p50_delta,
            p99_delta_pct=p99_delta,
            success_rate_delta=sr_delta,
            cost_delta_pct=cost_delta,
            regression=regression,
            regression_reason=reason,
        )

    def trend(self, metric: str, last_n: int = 10) -> list[float]:
        """Return the last N values for a given metric.

        Args:
            metric: "p50_ms" | "p99_ms" | "success_rate" | "total_cost_usd"
        """
        records = self._read_all()
        values = [r.get(metric, 0) for r in records[-last_n:]]
        return values

    def _read_all(self) -> list[dict]:
        if not os.path.isfile(self._path):
            return []
        records = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records


def _pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return ((new - old) / old) * 100.0
