"""
Cost Tracker — Token/API cost tracking for LLM usage.

Tracks per-session, per-model token consumption and USD costs.
Integrates with ccusage CLI via subprocess for real usage data.

Cost records are EVIDENCE, never TRUTH. truth_source = False.
Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Cost Record
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CostRecord:
    """A single token usage observation.

    Immutable. One record per API call or ccusage scan.
    truth_source is ALWAYS False — cost data is evidence.
    """

    record_id: str = ""           # sha256(timestamp+session_id)[:16]
    timestamp: float = 0.0
    session_id: str = ""
    model: str = ""               # "claude-opus-4-7", "deepseek-v4", etc.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    source: str = ""              # "ccusage", "api_response", "estimate"

    @staticmethod
    def make_id(timestamp: float, session_id: str) -> str:
        return hashlib.sha256(
            f"{timestamp}:{session_id}".encode()
        ).hexdigest()[:16]

    @staticmethod
    def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int, cache_hit_tokens: int = 0) -> float:
        """Estimate USD cost from token counts. Pricing as of 2026-06.

        Cached prompt tokens cost 10% of regular prompt tokens.
        """
        pricing = {
            "claude-opus-4-7":       (15.0, 75.0),
            "claude-sonnet-4-6":     (3.0,  15.0),
            "claude-haiku-4-5":      (1.0,  5.0),
            "claude-opus-4-5":       (15.0, 75.0),
            "claude-opus-4":         (15.0, 75.0),
            "deepseek-v4-pro":       (2.0,  8.0),
            "deepseek-v4":           (2.0,  8.0),
            "deepseek-v3":           (1.25, 5.0),
            "gpt-5":                 (5.0,  25.0),
            "gpt-4o":                (2.5,  10.0),
        }
        prompt_price, completion_price = pricing.get(model, (1.0, 5.0))

        effective_prompt = prompt_tokens - cache_hit_tokens
        if effective_prompt < 0:
            effective_prompt = 0

        prompt_cost = (effective_prompt / 1_000_000) * prompt_price
        cache_cost = (cache_hit_tokens / 1_000_000) * prompt_price * 0.1
        completion_cost = (completion_tokens / 1_000_000) * completion_price

        return round(prompt_cost + cache_cost + completion_cost, 6)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cache_hit_tokens": self.cache_hit_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "source": self.source,
        }


# ═══════════════════════════════════════════════════════════════════════
# Cost Summary
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CostSummary:
    """Aggregated cost summary across records."""

    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cache_hit_tokens: int = 0
    record_count: int = 0
    by_model: dict = field(default_factory=dict)
    by_session: dict = field(default_factory=dict)
    daily_costs: Tuple[Tuple[str, float], ...] = ()  # (date, cost) pairs

    def to_dict(self) -> dict:
        return {
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cache_hit_tokens": self.total_cache_hit_tokens,
            "record_count": self.record_count,
            "by_model": self.by_model,
            "by_session": self.by_session,
            "daily_costs": [list(d) for d in self.daily_costs],
        }


# ═══════════════════════════════════════════════════════════════════════
# Cost Tracker
# ═══════════════════════════════════════════════════════════════════════

class CostTracker:
    """Tracks token usage and cost across sessions.

    Records are append-only. Aggregation is read-only.
    Integrates with ccusage for real usage data.
    """

    def __init__(self):
        self._records: list[CostRecord] = []

    @property
    def records(self) -> Tuple[CostRecord, ...]:
        return tuple(self._records)

    def record(
        self,
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cache_hit_tokens: int = 0,
        session_id: str = "",
        source: str = "estimate",
    ) -> CostRecord:
        """Record a token usage observation.

        Cost is estimated from pricing table if source is "estimate".
        Otherwise, cost_usd should be provided via the more specific record_raw().
        """
        ts = time.time()
        total = prompt_tokens + completion_tokens
        cost = CostRecord.estimate_cost(model, prompt_tokens, completion_tokens, cache_hit_tokens)
        rec = CostRecord(
            record_id=CostRecord.make_id(ts, session_id or str(ts)),
            timestamp=ts,
            session_id=session_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_hit_tokens=cache_hit_tokens,
            total_tokens=total,
            cost_usd=cost,
            source=source,
        )
        self._records.append(rec)
        return rec

    def total_cost(self) -> float:
        return round(sum(r.cost_usd for r in self._records), 6)

    def cost_by_model(self) -> dict:
        by_model: dict[str, float] = {}
        for r in self._records:
            by_model[r.model] = by_model.get(r.model, 0.0) + r.cost_usd
        return {k: round(v, 6) for k, v in sorted(by_model.items())}

    def cost_by_session(self) -> dict:
        by_session: dict[str, float] = {}
        for r in self._records:
            by_session[r.session_id] = by_session.get(r.session_id, 0.0) + r.cost_usd
        return {k: round(v, 6) for k, v in sorted(by_session.items())}

    def daily_summary(self) -> CostSummary:
        daily: dict[str, float] = {}
        by_model: dict[str, float] = {}
        by_session: dict[str, float] = {}
        total_tokens = 0
        total_prompt = 0
        total_completion = 0
        total_cache = 0

        for r in self._records:
            day = datetime.fromtimestamp(r.timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0.0) + r.cost_usd
            by_model[r.model] = by_model.get(r.model, 0.0) + r.cost_usd
            by_session[r.session_id] = by_session.get(r.session_id, 0.0) + r.cost_usd
            total_tokens += r.total_tokens
            total_prompt += r.prompt_tokens
            total_completion += r.completion_tokens
            total_cache += r.cache_hit_tokens

        return CostSummary(
            total_cost_usd=round(sum(daily.values()), 6),
            total_tokens=total_tokens,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_cache_hit_tokens=total_cache,
            record_count=len(self._records),
            by_model={k: round(v, 6) for k, v in sorted(by_model.items())},
            by_session={k: round(v, 6) for k, v in sorted(by_session.items())},
            daily_costs=tuple(sorted(daily.items())),
        )

    def ingest_from_ccusage(self, path: str = "") -> int:
        """Ingest cost data from ccusage JSON output.

        Calls `ccusage report --json` (or reads from file) and parses
        token usage into CostRecord entries. Returns count of records added.
        """
        data = None
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        else:
            try:
                result = subprocess.run(
                    ["ccusage", "report", "--json"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
            except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
                pass

        if not data:
            return 0

        count = 0
        sessions = data if isinstance(data, list) else [data]
        for session in sessions:
            ts = time.time()
            model = session.get("model", "unknown")
            prompt = int(session.get("prompt_tokens", 0))
            completion = int(session.get("completion_tokens", 0))
            cache = int(session.get("cache_hit_tokens", 0))
            sid = session.get("session_id", str(ts))
            total = prompt + completion
            cost = CostRecord.estimate_cost(model, prompt, completion, cache)
            rec = CostRecord(
                record_id=CostRecord.make_id(ts, sid),
                timestamp=ts,
                session_id=sid,
                model=model,
                prompt_tokens=prompt,
                completion_tokens=completion,
                cache_hit_tokens=cache,
                total_tokens=total,
                cost_usd=cost,
                source="ccusage",
            )
            self._records.append(rec)
            count += 1

        return count
