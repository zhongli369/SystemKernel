r"""
SystemKernel public API — single entry point for all projects under F:\Claude\.
Pure forwarding layer. No logic, no caching, no decoration, no error handling.
"""
from SkillsManagementSystem.core.adapter import resolve as _resolve, CapabilityRequest
from ExecutionLoop.loop import run as _run, ExecutionRequest, ResolvedCapability
from TaskSystem.core.task_manager import create_task as _create_task


def resolve_skill(intent: str, context: str):
    """Forward to Adapter.resolve(). No added logic."""
    return _resolve(CapabilityRequest(intent=intent, context=context))


def run_skill(skill_id: str, target: str):
    """Forward to ExecutionLoop.run(). No added logic."""
    capability = ResolvedCapability(skill_id=skill_id)
    request = ExecutionRequest(capability=capability, target=target, verification=())
    return _run(request)


def create_task_safe(*args, **kwargs):
    """Forward to TaskSystem.create_task(). No added logic."""
    return _create_task(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════
# v4.1: External Intelligence Plane (gstack direction + superpowers quality)
# ═══════════════════════════════════════════════════════════════════════

def query_external_signals(plane: str, **kwargs):
    """Unified query layer for external intelligence signals.

    Routes to the appropriate deterministic adapter based on plane.
    No LLM calls. No external runtime dependencies. No state mutation.

    Args:
        plane: "direction" | "quality"
        **kwargs: plane-specific parameters

    direction kwargs:
        task_intent: str
        project_context: str = ""

    quality kwargs:
        target_content: str
        target_type: str = "code"

    Returns:
        {
            "plane": "direction" | "quality",
            "source": "gstack" | "superpowers",
            "signal_type": "direction" | "quality",
            "outputs": [...],
            "confidence": 0.0-1.0
        }
    """
    if plane == "direction":
        from v3.external.gstack_adapter import GstackDirectionAdapter
        task_intent = kwargs.get("task_intent", "")
        project_context = kwargs.get("project_context", "")
        raw = GstackDirectionAdapter.quick_analyze(task_intent, project_context)
    elif plane == "quality":
        from v3.external.superpowers_adapter import SuperpowersQualityAdapter
        target_content = kwargs.get("target_content", "")
        target_type = kwargs.get("target_type", "code")
        raw = SuperpowersQualityAdapter.quick_analyze(target_content, target_type)
    else:
        raise ValueError(f"Unknown plane: {plane!r}. Valid planes: direction, quality")

    outputs = raw.get("outputs", [])
    if outputs:
        confidences = [s.get("confidence", 0.0) for s in outputs]
        aggregate_confidence = round(sum(confidences) / len(confidences), 2)
    else:
        aggregate_confidence = 0.0

    return {
        "plane": plane,
        "source": raw["source"],
        "signal_type": raw["signal_type"],
        "outputs": outputs,
        "confidence": aggregate_confidence,
    }


def analyze_direction(task_intent: str, project_context: str = ""):
    """Backward-compatible wrapper. Delegates to query_external_signals(plane="direction")."""
    return query_external_signals(
        plane="direction",
        task_intent=task_intent,
        project_context=project_context,
    )


def analyze_quality(target_content: str, target_type: str = "code"):
    """Backward-compatible wrapper. Delegates to query_external_signals(plane="quality")."""
    return query_external_signals(
        plane="quality",
        target_content=target_content,
        target_type=target_type,
    )


def inject_external_signals(
    task_intent: str = "",
    project_context: str = "",
    target_content: str = "",
    target_type: str = "code",
):
    """Forward to external_signal_injector.inject_external_signals(). Single unified gateway.

    Orchestrates direction (gstack) + quality (superpowers) signals with
    weighted fusion (direction=0.4, quality=0.6), complexity gate, and
    decision fusion. External signals are MODIFIERS only, never authoritative.

    Returns:
      {"decision": {"verdict": "PROCEED|REVIEW|BLOCKED", "final_score": float, "reasoning": [...]},
       "signals": {"direction": {...}, "quality": {...}},
       "trace_id": str, "complexity_score": float}
    """
    from v3.external.external_signal_injector import inject_external_signals as _inject
    return _inject(
        task_intent=task_intent,
        project_context=project_context,
        target_content=target_content,
        target_type=target_type,
    )


# ═══════════════════════════════════════════════════════════════════════
# v4.1: Capability Facade Layer
# ═══════════════════════════════════════════════════════════════════════

def list_capabilities():
    """Read-only discovery of all enabled capabilities.

    Reads from the capability registry. Returns only enabled=True entries.
    Does NOT expose disabled/dormant adapters.
    Does NOT modify registry or trigger any side effects.

    Returns:
      {
        "capabilities": [
          {"name": "...", "type": "...", "description": "...", "status": "enabled"},
          ...
        ],
        "source": "capability_registry",
        "timestamp": "ISO-8601"
      }
    """
    from datetime import datetime, timezone
    from v3.external.default_capabilities import build_default_registry

    registry = build_default_registry()
    capabilities = []

    for entry in registry.entries:
        if not entry.enabled:
            continue

        capabilities.append({
            "name": entry.adapter_id,
            "type": entry.spec.capability_type if entry.spec else "unknown",
            "description": entry.notes or (entry.spec.name if entry.spec else ""),
            "status": "enabled",
        })

    return {
        "capabilities": capabilities,
        "source": "capability_registry",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
