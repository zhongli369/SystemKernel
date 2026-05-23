#!/usr/bin/env python3
"""
suggestion_engine.py — DEPRECATED compatibility wrapper (v4.0 → to be removed)

STATUS: DEPRECATED. All routing MUST go through Adapter.resolve().
This module exists ONLY for backward compatibility with v3.5 callers.
New code should use:

    from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest
    binding = resolve(CapabilityRequest(intent="...", context="..."))

Delegates to the capability-based routing pipeline (core/routing_pipeline.py).
Maintains backward compatibility with v3.5 input/output format.

Standard Input (v3.5 compat):
  {
    "task_id": str,
    "step_id": str,
    "step_content": str,
    "context_log": str | None   (optional)
  }

Standard Output — [Skill Suggestion Only]:
  {
    "skill": str | None,
    "package": str | None,
    "confidence": float,       # 0.0 ~ 1.0
    "reason": str,
    "applicable_step": str,
    "alternatives": [{skill, package, confidence}, ...],
    "install_required": bool,
    "install_hint": str | None
  }

This module is PURELY passive:
  - No execution authority
  - No workflow control
  - No filesystem writes
  - No CLI / subprocess calls
  - No TaskSystem interaction

Phase 2 governance:
  - DEPRECATED. Use Adapter.resolve() instead.
  - This file is a compatibility shim, NOT a routing entry point.
  - It delegates to routing_pipeline.suggest() — which itself is an internal
    implementation detail behind Adapter.resolve().
  - Callers should migrate to the canonical path: Adapter.resolve(CapabilityRequest(...))
"""

import sys
from pathlib import Path

# Ensure sibling modules are importable
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from core.routing_pipeline import suggest as _pipeline_suggest


def suggest_skill(task_context: dict) -> dict:
    """Suggest a skill based on task context.

    Pure function. No side effects. Only returns suggestions.

    Uses the v4.0 capability-based routing pipeline under the hood.

    Args:
        task_context: Dict with task_id, step_id, step_content, and
                      optional context_log.

    Returns:
        [Skill Suggestion Only] dict with skill, package, confidence,
        reason, applicable_step, alternatives, install_required, install_hint.
    """
    step_content = task_context.get("step_content", "")
    context_log = task_context.get("context_log", "")
    query = f"{step_content} {context_log or ''}".strip()

    if not query:
        return {
            "skill": None,
            "package": None,
            "confidence": 0.0,
            "reason": "No step content or context provided",
            "applicable_step": task_context.get("step_id", ""),
            "alternatives": [],
            "install_required": False,
            "install_hint": None,
        }

    result = _pipeline_suggest(query)

    # Map v4.0 output back to v3.5-compatible format
    tm = result.get("top_match")
    output = {
        "skill": tm["skill"] if tm else None,
        "package": tm["package"] if tm else None,
        "confidence": tm["confidence"] if tm else 0.0,
        "reason": tm["reason"] if tm else result.get("score_breakdown", {}).get("reason", "No match found"),
        "applicable_step": task_context.get("step_id", ""),
        "alternatives": result.get("alternatives", []),
        "install_required": result.get("install_required", False),
        "install_hint": result.get("install_hint"),
    }

    if result.get("ambiguity"):
        output["reason"] += f" | {result.get('ambiguity_detail', '')}"

    return output


# ═══════════════════════════════════════════════════════════════════════════════
# Direct query interface (new in v4.0)
# ═══════════════════════════════════════════════════════════════════════════════

def suggest(query: str) -> dict:
    """Suggest a skill directly from a query string.

    Simpler interface — no task_context dict needed.
    Uses the v4.0 routing pipeline.
    """
    return _pipeline_suggest(query)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI — for testing / inspection only
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    if len(sys.argv) < 2:
        print("Usage: python suggestion_engine.py <query> [--json]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Prints [Skill Suggestion Only] as JSON.", file=sys.stderr)
        sys.exit(1)

    query = sys.argv[1]
    use_json = "--json" in sys.argv

    result = suggest(query) if use_json else suggest(query)
    print(json.dumps(result, indent=2, ensure_ascii=False))
