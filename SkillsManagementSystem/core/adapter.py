"""
adapter.py — Unified Capability Resolution Adapter (v1.0)

The ONLY entrypoint for SkillSystem routing across all systems.

Single responsibility: intent + context → routing_pipeline.suggest() → CapabilityBinding

Architecture contract:
  RepoAnalyzer ─┐
  TaskSystem  ──┼──► adapter.resolve(CapabilityRequest) ──► routing_pipeline.suggest()
  (future)    ──┘

Design constraints:
  - ≤120 lines, single file
  - No state, no cache, no subprocess, no async
  - Pure function from CapabilityRequest to CapabilityBinding
"""

from dataclasses import dataclass
from .routing_pipeline import suggest as _pipeline_suggest
from .routing_pipeline import get_registry_info as _get_registry_info


# ═══════════ Data types (frozen) ═══════════

@dataclass(frozen=True)
class CapabilityRequest:
    """Routing input. Caller compresses domain context into intent + context strings."""
    intent: str           # "refactor"|"decouple"|"stabilize"|"optimize"|"cleanup"|""
    context: str          # free-text describing the specific target / situation
    source: str = ""      # optional audit label: "repoanalyzer"|"tasksystem"


@dataclass(frozen=True)
class CapabilityBinding:
    """Routing output. A resolved skill reference — not an execution result."""
    skill_id: str
    confidence: float
    alternatives: tuple[str, ...]
    reason: str


# ═══════════ Single source of truth: intent → query hint ═══════════

INTENT_HINTS: dict[str, str] = {
    "refactor":   "refactor code improve structure reduce coupling",
    "decouple":   "decouple modules reduce dependencies extract interfaces",
    "stabilize":  "stabilize add error handling logging tests entry point",
    "optimize":   "optimize simplify pipeline reduce dependency count",
    "cleanup":    "cleanup audit deduplicate remove unused code",
}


# ═══════════ Internal: pure query builder ═══════════

def _build_query(request: CapabilityRequest) -> str:
    """Build a routing query from intent hint + context.

    Pure function. No external state. No side effects.
    """
    hint = INTENT_HINTS.get(request.intent, "")
    if hint and request.context:
        return f"{hint} {request.context}"
    if hint:
        return hint
    return request.context


# ═══════════ Public API: metadata ═══════════

def get_registry_info() -> dict:
    """Return registry metadata for inspection / health checks.

    Thin wrapper — all metadata access routes through Adapter.
    """
    return _get_registry_info()


def get_skill_metadata(skill_name: str) -> dict:
    """Return metadata for a specific skill, or empty dict if not found."""
    info = _get_registry_info()
    for s in info.get("all_skills", []):
        if s["name"] == skill_name:
            return s
    return {}


# ═══════════ Public API: routing ═══════════

def resolve(request: CapabilityRequest) -> CapabilityBinding:
    """Resolve a capability request to a skill binding.

    Single entrypoint. Determistic. Stateless.

    Args:
        request: CapabilityRequest with intent, context, and optional source.

    Returns:
        CapabilityBinding with skill_id, confidence, alternatives, and reason.
    """
    import time as _time
    import uuid as _uuid

    _start = _time.monotonic()
    query = _build_query(request)
    result = _pipeline_suggest(query)

    top = result.get("top_match")
    if top is None:
        binding = CapabilityBinding(
            skill_id="",
            confidence=0.0,
            alternatives=(),
            reason=f"No skill matched for query: {query[:100]}",
        )
    else:
        alts: tuple[str, ...] = tuple(
            a["skill"] for a in result.get("alternatives", [])[:5]
        )
        binding = CapabilityBinding(
            skill_id=top["skill"],
            confidence=top.get("confidence", 0.0),
            alternatives=alts,
            reason=top.get("reason", f"Matched: {top['skill']}"),
        )

    _elapsed_ms = (_time.monotonic() - _start) * 1000

    # ── Observability: record routing span + metrics (non-invasive)
    try:
        from Observability.trace import record_span as _record_span
        from Observability.metrics import record_metric as _record_metric

        _trace_id = str(_uuid.uuid4())
        _record_span(
            stage="routing",
            data={
                "skill_id": binding.skill_id,
                "confidence": binding.confidence,
                "alternatives": list(binding.alternatives),
                "intent": request.intent,
                "source": request.source,
            },
            trace_id=_trace_id,
        )
        _record_metric("routing_latency_ms", _elapsed_ms,
                       tags={"intent": request.intent, "source": request.source},
                       trace_id=_trace_id)
        _record_metric("skill_hit", 1 if binding.skill_id else 0,
                       tags={"intent": request.intent},
                       trace_id=_trace_id)
    except Exception:
        pass

    return binding
