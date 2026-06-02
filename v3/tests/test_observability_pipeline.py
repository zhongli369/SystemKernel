"""Observability Pipeline Tests — L5 smoke, stress, metrics, cost, alerts."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestSmokeTest(unittest.TestCase):

    def test_01_smoke_test_runs_and_passes(self):
        from v3.external.observability.smoke_test import run_smoke_test
        passed, msg = run_smoke_test()
        self.assertTrue(passed, f"Smoke test failed: {msg}")
        self.assertIn("PASS", msg)


class TestStressRunner(unittest.TestCase):

    def test_02_stress_runner_mini(self):
        from v3.external.observability.stress_runner import run_stress
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "stress_report.json")
            report = run_stress(runs=10, output=output, verbose=False)
            self.assertEqual(report.runs, 10)
            self.assertGreaterEqual(report.passes, 9)
            self.assertGreater(report.latency_p50, 0)
            self.assertGreater(report.trace_spans, 0)


class TestMetricsExporter(unittest.TestCase):

    def test_03_metrics_exporter_increment(self):
        from v3.external.observability.metrics_exporter import MetricsExporter
        e = MetricsExporter()
        e.inc_executions(5)
        data = e.export_json()
        self.assertGreaterEqual(data["metrics"]["systemkernel_executions_total"], 5)

    def test_04_metrics_persistence_roundtrip(self):
        from v3.external.observability.metrics_exporter import MetricsExporter
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "snapshot.json")
            e = MetricsExporter()
            e.inc_executions(10)
            e.add_cost("test-model", 100, 0.05)
            e.dump_to_disk(path)

            e2 = MetricsExporter()
            self.assertTrue(e2.load_from_disk(path))
            data = e2.export_json()
            self.assertEqual(data["metrics"]["systemkernel_executions_total"], 10)
            self.assertGreater(data["metrics"]["systemkernel_cost_usd_total"], 0)

    def test_05_metrics_reset(self):
        from v3.external.observability.metrics_exporter import MetricsExporter
        e = MetricsExporter()
        e.inc_executions(50)
        e.reset()
        data = e.export_json()
        self.assertEqual(data["metrics"]["systemkernel_executions_total"], 0)


class TestCostTracker(unittest.TestCase):

    def test_06_cost_tracker_summary(self):
        from v3.external.observability.cost_tracker import CostTracker
        t = CostTracker()
        t.record(model="test-model", prompt_tokens=1000,
                 completion_tokens=500)
        summary = t.daily_summary()
        self.assertGreater(summary.total_cost_usd, 0)
        self.assertGreater(summary.total_tokens, 0)


class TestAlertPolicy(unittest.TestCase):

    def test_07_alert_policy_firing(self):
        from v3.external.observability.alert_policy import (
            evaluate_alerts, ALERT_FIRING,
        )
        metrics = {
            "systemkernel_executions_total": 0,
            "systemkernel_cost_usd_total": 999.0,  # Over budget
            "systemkernel_execution_latency_seconds": {
                "count": 100, "sum": 500,  # avg 5s
            },
            "systemkernel_complexity_score": 9.0,
        }
        results = evaluate_alerts(metrics)
        firing = [a for a in results if getattr(a, "state", None) == ALERT_FIRING]
        self.assertGreaterEqual(len(firing), 1)


class TestMetricsHistory(unittest.TestCase):

    def test_08_history_record_and_trend(self):
        from v3.external.observability.metrics_history import MetricsHistory
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.jsonl")
            h = MetricsHistory(history_path=path)

            class FakeReport:
                runs = 10
                latency_p50 = 32.0
                latency_p99 = 47.0
                passes = 10
                total_cost_usd = 0.004

            for _ in range(3):
                h.record(FakeReport())

            trend = h.trend("p50_ms", last_n=10)
            self.assertEqual(len(trend), 3)
            self.assertTrue(all(v == 32.0 for v in trend))

    def test_09_history_no_regression(self):
        from v3.external.observability.metrics_history import MetricsHistory
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.jsonl")
            h = MetricsHistory(history_path=path)

            class FakeReport:
                runs = 10
                latency_p50 = 32.0
                latency_p99 = 47.0
                passes = 10
                total_cost_usd = 0.004

            baseline = h.record(FakeReport())
            # Second run with same metrics
            FakeReport.latency_p99 = 47.0  # no change
            h.record(FakeReport())
            report = h.compare(baseline)
            self.assertIsNotNone(report)
            self.assertFalse(report.regression)
