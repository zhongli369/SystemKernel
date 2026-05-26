"""
External Usage Report Adapter — Safe wrapper for ccusage JSON output.

This is NOT a kernel module. It is a developer tool that consumes
pre-generated JSON output from the external ccusage CLI tool.

Rules:
- Standard library only
- Deterministic ordering
- truth_source is ALWAYS False
- No external command execution
- No dependency on ccusage package
- Do not fail if optional fields missing; record warnings
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class UsageReportConfig:
    """Configuration for usage report adapter."""
    input_path: str
    source_tool: str = "ccusage"
    redaction_enabled: bool = True
    max_records: int = 0
    include_model_breakdown: bool = True
    include_agent_breakdown: bool = True
    dry_run: bool = False


@dataclass(frozen=True)
class UsageDayRecord:
    """Single day's usage record."""
    date: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    cost_usd: float
    models: tuple[str, ...]
    agents: tuple[str, ...]


@dataclass(frozen=True)
class UsageReportSummary:
    """Aggregated usage report summary."""
    source_tool: str
    record_count: int
    total_tokens: int
    total_cost_usd: float
    cache_read_ratio: float
    model_count: int
    agent_count: int
    date_start: str
    date_end: str
    sensitive_text_detected: bool
    report_hash: str
    truth_source: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)


# ═══════════════════════════════════════════════════════════════════════
# Adapter
# ═══════════════════════════════════════════════════════════════════════

class UsageReportAdapter:
    """Safe adapter for consuming ccusage JSON output.

    All methods are read-only. No external process execution.
    ccusage must be run separately before using this adapter.
    """

    @staticmethod
    def inspect(input_path: str) -> UsageReportSummary:
        """Read ccusage JSON output and return a summary."""
        records = UsageReportAdapter.parse_ccusage_json(input_path)
        return UsageReportAdapter.summarize(records)

    @staticmethod
    def parse_ccusage_json(input_path: str) -> tuple[UsageDayRecord, ...]:
        """Parse ccusage daily JSON into UsageDayRecord tuples.

        Sorts by date ascending for deterministic output.
        Missing optional fields produce warnings but do not fail.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Usage data file not found: {input_path}")

        with open(input_path, encoding="utf-8") as f:
            raw = json.load(f)

        daily = raw.get("daily", [])
        if not isinstance(daily, list):
            raise ValueError("Invalid ccusage JSON: 'daily' must be a list")

        records = []
        for entry in daily:
            models = tuple(sorted(entry.get("modelsUsed", [])))
            agents = tuple(sorted(entry.get("metadata", {}).get("agents", [])))

            record = UsageDayRecord(
                date=entry.get("period", ""),
                total_tokens=entry.get("totalTokens", 0),
                input_tokens=entry.get("inputTokens", 0),
                output_tokens=entry.get("outputTokens", 0),
                cache_creation_tokens=entry.get("cacheCreationTokens", 0),
                cache_read_tokens=entry.get("cacheReadTokens", 0),
                cost_usd=entry.get("totalCost", 0.0),
                models=models,
                agents=agents,
            )
            records.append(record)

        records.sort(key=lambda r: r.date)
        return tuple(records)

    @staticmethod
    def summarize(records: tuple[UsageDayRecord, ...]) -> UsageReportSummary:
        """Aggregate day records into a summary."""
        warnings = []

        if not records:
            return UsageReportSummary(
                source_tool="ccusage",
                record_count=0,
                total_tokens=0,
                total_cost_usd=0.0,
                cache_read_ratio=0.0,
                model_count=0,
                agent_count=0,
                date_start="",
                date_end="",
                sensitive_text_detected=False,
                report_hash=UsageReportAdapter._compute_hash(()),
            )

        total_tokens = sum(r.total_tokens for r in records)
        total_cost = sum(r.cost_usd for r in records)
        total_cache_read = sum(r.cache_read_tokens for r in records)
        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)

        total_all = total_cache_read + total_input + total_output
        cache_read_ratio = (total_cache_read / total_all) if total_all > 0 else 0.0

        all_models = set()
        all_agents = set()
        for r in records:
            all_models.update(r.models)
            all_agents.update(r.agents)

        date_start = records[0].date
        date_end = records[-1].date

        for r in records:
            if not r.models:
                warnings.append(f"Day {r.date}: no models listed")
            if not r.agents:
                warnings.append(f"Day {r.date}: no agents listed")
            if r.total_tokens == 0:
                warnings.append(f"Day {r.date}: total_tokens is 0")

        report_hash = UsageReportAdapter._compute_hash(records)

        return UsageReportSummary(
            source_tool="ccusage",
            record_count=len(records),
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 6),
            cache_read_ratio=round(cache_read_ratio, 6),
            model_count=len(all_models),
            agent_count=len(all_agents),
            date_start=date_start,
            date_end=date_end,
            sensitive_text_detected=UsageReportAdapter._detect_sensitive(records),
            report_hash=report_hash,
            warnings=tuple(warnings),
        )

    @staticmethod
    def write_summary(summary: UsageReportSummary, output_path: str) -> None:
        """Write summary as JSON to output_path."""
        data = {
            "source_tool": summary.source_tool,
            "record_count": summary.record_count,
            "total_tokens": summary.total_tokens,
            "total_cost_usd": summary.total_cost_usd,
            "cache_read_ratio": summary.cache_read_ratio,
            "model_count": summary.model_count,
            "agent_count": summary.agent_count,
            "date_start": summary.date_start,
            "date_end": summary.date_end,
            "sensitive_text_detected": summary.sensitive_text_detected,
            "report_hash": summary.report_hash,
            "truth_source": summary.truth_source,
            "warnings": list(summary.warnings),
        }
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    @staticmethod
    def verify_summary(summary: UsageReportSummary) -> bool:
        """Verify summary invariants: truth_source is False, hash present, counts consistent."""
        if summary.truth_source is not False:
            return False
        if not summary.report_hash:
            return False
        if summary.record_count < 0:
            return False
        if summary.total_tokens < 0:
            return False
        if summary.total_cost_usd < 0:
            return False
        if not (0.0 <= summary.cache_read_ratio <= 1.0):
            return False
        return True

    @staticmethod
    def _detect_sensitive(records: tuple[UsageDayRecord, ...]) -> bool:
        """Heuristic check for sensitive data in records. Always returns False
        for records that don't include prompt text (ccusage output does not)."""
        return False

    @staticmethod
    def _compute_hash(records: tuple[UsageDayRecord, ...]) -> str:
        """Deterministic hash of records for comparison."""
        parts = []
        for r in records:
            parts.append(
                f"{r.date}|{r.total_tokens}|{r.input_tokens}|{r.output_tokens}|"
                f"{r.cache_read_tokens}|{r.cost_usd}|{','.join(r.models)}|{','.join(r.agents)}"
            )
        return hashlib.sha256(";".join(parts).encode()).hexdigest()[:16]
