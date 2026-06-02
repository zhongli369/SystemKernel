"""
L5 Observability Plane — Phase 15b.

Cost tracking, Prometheus-compatible metrics export, Grafana dashboard
templates, and alert policy evaluation. All outputs are evidence-wrapped
(truth_source=False). No external observability dependencies (no
prometheus_client, no Grafana runtime).

Stdlib only. Pull-mode metrics (Prometheus scrape endpoint pattern).
No real-time push. No alert escalation chain — evaluation only.
"""

from v3.external.observability.cost_tracker import (
    CostRecord,
    CostTracker,
    CostSummary,
)

from v3.external.observability.metrics_exporter import (
    MetricsExporter,
    export_metrics,
    export_metrics_json,
    get_dashboard_spec,
)

from v3.external.observability.alert_policy import (
    AlertRule,
    AlertEvent,
    AlertPolicy,
    ALERT_INACTIVE,
    ALERT_PENDING,
    ALERT_FIRING,
    ALERT_RESOLVED,
    evaluate_alerts,
    get_default_rules,
)
