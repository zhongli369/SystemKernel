"""
dashboard.py — Minimal CLI Observability Viewer (v1.0 — Phase 3)

Pure display. Zero intelligence. Reads traces/ and metrics/ from disk.
Does NOT interpret, analyze, or decide anything.

Usage:
    python Observability/dashboard.py trace <trace_id> [--date YYYY-MM-DD]
    python Observability/dashboard.py traces [--limit N] [--date YYYY-MM-DD]
    python Observability/dashboard.py metrics <metric_type> [--date YYYY-MM-DD]
    python Observability/dashboard.py report <trace_id> [--date YYYY-MM-DD]
    python Observability/dashboard.py compare <trace_id_1> <trace_id_2>
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from Observability.trace import TraceCollector, TraceSpan
from Observability.metrics import MetricsCollector, METRIC_TYPES
from Observability.replay import ReplayEngine, replay_trace


# ═══════════════════════════════════════════════════════════════════════════════
# Display helpers — pure formatting, no intelligence
# ═══════════════════════════════════════════════════════════════════════════════

def _box(title: str, width: int = 72) -> str:
    """Draw a simple text box around content."""
    bar = "=" * width
    return f"{bar}\n  {title}\n{bar}"


def _kv(label: str, value, indent: int = 2) -> str:
    """Format a key-value line."""
    prefix = " " * indent
    return f"{prefix}{label}: {value}"


def _section(title: str) -> str:
    """Format a section header."""
    return f"\n--- {title} ---"


# ═══════════════════════════════════════════════════════════════════════════════
# View functions — read from disk, format for display
# ═══════════════════════════════════════════════════════════════════════════════

def view_trace(trace_id: str, date_str: str = None) -> str:
    """Display a single trace chain as a human-readable timeline.

    Pure read + format. No interpretation.
    """
    collector = TraceCollector()
    spans = collector.get_chain(trace_id, date_str)

    if not spans:
        return f"No trace found for trace_id: {trace_id}"

    lines = [_box(f"Trace: {trace_id}")]
    lines.append(_kv("Total spans", len(spans)))

    # Summarize stages
    stage_order = [s.stage for s in spans]
    lines.append(_kv("Stage chain", " → ".join(stage_order)))

    # Temporal span
    if len(spans) >= 2:
        start = spans[0].timestamp[:19]
        end = spans[-1].timestamp[:19]
        lines.append(_kv("Time range", f"{start} → {end}"))

    # Detail each span
    for i, span in enumerate(spans):
        lines.append(_section(f"Span {i+1}: {span.stage.upper()}"))
        lines.append(_kv("span_id", span.span_id))
        lines.append(_kv("timestamp", span.timestamp))
        if span.parent_span_id:
            lines.append(_kv("parent", span.parent_span_id))

        # Stage-specific data
        for k, v in span.data.items():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            lines.append(_kv(k, v))

    return "\n".join(lines)


def list_recent_traces(limit: int = 20, date_str: str = None) -> str:
    """List recent trace IDs in storage.

    Pure read. No filtering, no prioritization.
    """
    collector = TraceCollector()
    trace_ids = collector.list_traces(date_str, limit)

    if not trace_ids:
        return "No traces found in storage."

    lines = [_box(f"Recent Traces ({len(trace_ids)} found)")]
    for tid in trace_ids:
        spans = collector.get_chain(tid, date_str)
        if spans:
            stages = [s.stage for s in spans]
            ts = spans[0].timestamp[:19]
            lines.append(f"  [{ts}] {tid} → {' → '.join(stages)} ({len(spans)} spans)")
        else:
            lines.append(f"  {tid} (no spans)")

    return "\n".join(lines)


def view_metrics(metric_type: str, date_str: str = None) -> str:
    """Display metric summary and recent points for a metric type.

    Pure read + format. No inference, no anomaly detection.
    """
    collector = MetricsCollector()

    # Summary stats
    summary = collector.get_summary(metric_type, date_str)

    lines = [_box(f"Metrics: {metric_type}")]
    if date_str:
        lines.append(_kv("Date", date_str))

    lines.append(_section("Summary"))
    lines.append(_kv("Count", summary["count"]))
    lines.append(_kv("Sum", f"{summary['sum']:.2f}"))
    lines.append(_kv("Min", f"{summary['min']:.2f}"))
    lines.append(_kv("Max", f"{summary['max']:.2f}"))
    lines.append(_kv("Mean", f"{summary['mean']:.2f}"))

    # Recent points
    points = collector.get_points(metric_type, date_str, limit=20)
    if points:
        lines.append(_section(f"Recent Points ({len(points)} shown)"))
        for p in points:
            ts = p.timestamp[:19]
            tags_str = ", ".join(f"{k}={v}" for k, v in p.tags.items()) if p.tags else ""
            line = f"  [{ts}] value={p.value}"
            if tags_str:
                line += f" tags=[{tags_str}]"
            if p.trace_id:
                line += f" trace={p.trace_id}"
            lines.append(line)

    return "\n".join(lines)


def view_execution_report(trace_id: str, date_str: str = None) -> str:
    """Display the execution report for a trace.

    Extracts execution + validation spans and formats them as a report.
    Pure display. No analysis.
    """
    collector = TraceCollector()
    spans = collector.get_chain(trace_id, date_str)

    if not spans:
        return f"No trace found for trace_id: {trace_id}"

    exec_spans = [s for s in spans if s.stage in ("execution", "validation")]

    if not exec_spans:
        return f"No execution/validation spans found in trace: {trace_id}"

    lines = [_box(f"Execution Report: {trace_id}")]

    for span in exec_spans:
        lines.append(_section(f"Stage: {span.stage.upper()}"))
        lines.append(_kv("Timestamp", span.timestamp))

        for k, v in span.data.items():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            lines.append(_kv(k, v))

    # Determine outcome
    validation = [s for s in spans if s.stage == "validation"]
    if validation:
        v = validation[0]
        passed = v.data.get("verification_passed", False)
        lines.append(_section("Outcome"))
        lines.append(_kv("Verification", "PASSED" if passed else "FAILED"))

    return "\n".join(lines)


def view_metrics_list(date_str: str = None) -> str:
    """List all available metric types with their latest counts.

    Pure inventory display.
    """
    collector = MetricsCollector()

    lines = [_box("Available Metric Types")]

    for mt in sorted(METRIC_TYPES):
        summary = collector.get_summary(mt, date_str)
        lines.append(f"  {mt}: {summary['count']} points (mean={summary['mean']:.2f})")

    # Also check custom
    custom_summary = collector.get_summary("custom", date_str)
    if custom_summary["count"] > 0:
        lines.append(f"  custom: {custom_summary['count']} points")

    return "\n".join(lines)


def compare_traces(trace_id_1: str, trace_id_2: str) -> str:
    """Compare two trace chains for determinism verification.

    Pure structural comparison. No interpretation.
    """
    engine = ReplayEngine()
    result = engine.compare_traces(trace_id_1, trace_id_2)

    lines = [_box(f"Trace Comparison: {trace_id_1} vs {trace_id_2}")]
    lines.append(_kv("Match", "YES" if result["match"] else "NO"))
    lines.append(_kv("Trace 1 spans", result["trace_1_spans"]))
    lines.append(_kv("Trace 2 spans", result["trace_2_spans"]))
    lines.append(_kv("Common stages", ", ".join(result["common_stages"]) if result["common_stages"] else "(none)"))

    if result["differences"]:
        lines.append(_section(f"Differences ({len(result['differences'])})"))
        for d in result["differences"]:
            lines.append(f"  - {d}")

    return "\n".join(lines)


def view_all_metrics(date_str: str = None) -> str:
    """Display a summary of ALL metric types.

    Single-page overview. No interpretation.
    """
    lines = [_box("All Metrics Overview")]
    if date_str:
        lines.append(_kv("Date", date_str))

    collector = MetricsCollector()
    total_points = 0

    for mt in sorted(METRIC_TYPES):
        summary = collector.get_summary(mt, date_str)
        if summary["count"] > 0:
            total_points += summary["count"]
            lines.append(
                f"  {mt:30s} → count={summary['count']:4d}  "
                f"mean={summary['mean']:8.2f}  min={summary['min']:8.2f}  max={summary['max']:8.2f}"
            )

    lines.append(_section(f"Total: {total_points} metric points across {len(METRIC_TYPES)} types"))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entrypoint
# ═══════════════════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="observability",
        description="SystemKernel Observability Dashboard — read-only trace & metrics viewer",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # trace <trace_id>
    trace_cmd = sub.add_parser("trace", help="View a single trace timeline")
    trace_cmd.add_argument("trace_id", help="Trace ID to view")
    trace_cmd.add_argument("--date", default=None, help="Date partition (YYYY-MM-DD)")

    # traces
    traces_cmd = sub.add_parser("traces", help="List recent traces")
    traces_cmd.add_argument("--limit", type=int, default=20, help="Max traces to show")
    traces_cmd.add_argument("--date", default=None, help="Date partition filter")

    # metrics <metric_type>
    metrics_cmd = sub.add_parser("metrics", help="View metric summary and points")
    metrics_cmd.add_argument("metric_type", nargs="?", help="Metric type (or omit for overview)")
    metrics_cmd.add_argument("--date", default=None, help="Date partition (YYYY-MM-DD)")

    # report <trace_id>
    report_cmd = sub.add_parser("report", help="View execution report for a trace")
    report_cmd.add_argument("trace_id", help="Trace ID")
    report_cmd.add_argument("--date", default=None, help="Date partition")

    # compare <trace_id_1> <trace_id_2>
    compare_cmd = sub.add_parser("compare", help="Compare two traces for determinism")
    compare_cmd.add_argument("trace_id_1", help="First trace ID")
    compare_cmd.add_argument("trace_id_2", help="Second trace ID")

    return parser


def main(argv: list[str] = None) -> str:
    """CLI entry point. Pure dispatch — no intelligence.

    Returns formatted output string. Prints to stdout when run as __main__.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "trace":
        return view_trace(args.trace_id, args.date)
    elif args.command == "traces":
        return list_recent_traces(args.limit, args.date)
    elif args.command == "metrics":
        if args.metric_type:
            return view_metrics(args.metric_type, args.date)
        else:
            return view_all_metrics(args.date)
    elif args.command == "report":
        return view_execution_report(args.trace_id, args.date)
    elif args.command == "compare":
        return compare_traces(args.trace_id_1, args.trace_id_2)
    else:
        parser.print_help()
        return ""


if __name__ == "__main__":
    print(main())
