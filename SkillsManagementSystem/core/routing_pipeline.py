"""
routing_pipeline.py — Top-Level Routing Pipeline (v4.0)

Single entry point for ALL skill routing. Orchestrates:

  capability_registry → routing_engine → external_skill_adapter → output

This module IS the public API for skill routing in v4.0.

Usage:
    from core.routing_pipeline import suggest

    result = suggest("build excel financial dashboard")
    # → RoutingDecision dict

    result = suggest("optimize react rendering performance")
    # → may recommend external (uninstalled) skill with install_hint

Key guarantees:
  - Pure function after initial registry load
  - Deterministic: same input → same output
  - No execution: suggestion only
  - External skills participate equally
  - Installed status is a +0.05 bonus, not a gate
"""

import json
from pathlib import Path
from typing import Optional

from . import RoutingResult
from .capability_registry import (
    load_capability_registry, build_capability_registry,
    get_entry_count, get_installed_count, get_external_count,
)
from .routing_engine import route
from .external_skill_adapter import external_skill_summary

# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline output format
# ═══════════════════════════════════════════════════════════════════════════════

def _format_output(result: RoutingResult) -> dict:
    """Convert RoutingResult to the standard [Routing Decision] output format."""
    output: dict = {
        "query": result.query,
        "top_match": None,
        "alternatives": [],
        "install_required": result.install_required,
        "install_hint": result.install_hint,
        "ambiguity": result.ambiguity,
        "ambiguity_detail": result.ambiguity_detail,
        "fallback_used": result.fallback_used,
        "coverage_warning": result.coverage_warning,
        "matched_keywords": list(result.matched_keywords),
        "score_breakdown": result.score_breakdown,
    }

    if result.top_match:
        tm = result.top_match
        output["top_match"] = {
            "skill": tm.entry.skill,
            "package": tm.entry.package,
            "source": tm.entry.source,
            "installed": tm.entry.installed,
            "confidence": round(tm.final_score, 4),
            "reason": (
                f"Matched via {tm.match_type}: "
                f"{', '.join(tm.matched_tokens[:5])}"
            ),
            "matched_by": (
                [tm.match_type] if not isinstance(tm.match_type, str)
                else [t.strip() for t in tm.match_type.split("+")]
            ),
            "raw_score": round(tm.raw_score, 4),
            "installed_bonus": round(tm.installed_bonus, 4),
        }

    output["alternatives"] = [
        {
            "skill": a.entry.skill,
            "package": a.entry.package,
            "source": a.entry.source,
            "installed": a.entry.installed,
            "confidence": round(a.final_score, 4),
        }
        for a in result.alternatives
    ]

    return output


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

# Module-level singleton registry (loaded once, used many times)
_registry_cache: Optional[list] = None


def _get_registry(force_reload: bool = False) -> list:
    """Get the capability registry, loading from disk if needed."""
    global _registry_cache
    if _registry_cache is None or force_reload:
        _registry_cache = load_capability_registry()
    return _registry_cache


def suggest(query: str, include_external: bool = True) -> dict:
    """Suggest a skill for the given user query.

    This is the PRIMARY public API for skill routing.

    Args:
        query: Raw user input string.
        include_external: Whether to include external skills in results.

    Returns:
        [Routing Decision] dict with top_match, alternatives, install_hint, etc.
    """
    entries = _get_registry()

    if not include_external:
        entries = [e for e in entries if e.source == "local"]

    result = route(query, entries)
    return _format_output(result)


def suggest_pure(query: str, registry_data: dict) -> dict:
    """Suggest a skill using an explicitly provided registry dict.

    Fully pure — no disk access at all. Useful for testing.
    """
    entries = build_capability_registry(registry_data)
    result = route(query, entries)
    return _format_output(result)


def suggest_standalone(query: str, entries: list) -> dict:
    """Suggest a skill from pre-built capability entries.

    Fully pure — no disk access, no registry loading.
    Useful for testing with mock entries.
    """
    result = route(query, entries)
    return _format_output(result)


def get_registry_info() -> dict:
    """Return registry metadata (for health checks / inspection)."""
    entries = _get_registry()
    ext_summary = external_skill_summary(entries)

    return {
        "total_skills": get_entry_count(entries),
        "installed_skills": get_installed_count(entries),
        "external_skills": get_external_count(entries),
        "local_skills": get_entry_count(entries) - get_external_count(entries),
        "external_summary": ext_summary,
        "packages": sorted(set(e.package for e in entries)),
        "domains": sorted(set(
            d for e in entries for d in e.domains
        )),
        "all_skills": [
            {
                "name": e.skill,
                "package": e.package,
                "source": e.source,
                "installed": e.installed,
                "aliases": list(e.aliases[:5]),
                "tags": list(e.tags),
                "domains": list(e.domains),
            }
            for e in sorted(entries, key=lambda x: x.skill)
        ],
    }


def reload_registry():
    """Force reload the capability registry from disk."""
    global _registry_cache
    _registry_cache = None
    return _get_registry(force_reload=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI for testing / inspection
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python routing_pipeline.py <query> [--json] [--info]", file=sys.stderr)
        print("", file=sys.stderr)
        print("  <query>       Route a query and print result", file=sys.stderr)
        print("  --json        Output as JSON", file=sys.stderr)
        print("  --info        Print registry info", file=sys.stderr)
        sys.exit(1)

    if "--info" in sys.argv:
        info = get_registry_info()
        print(json.dumps(info, indent=2, ensure_ascii=False))
        sys.exit(0)

    query = sys.argv[1]
    use_json = "--json" in sys.argv

    result = suggest(query)

    if use_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\nQuery: {result['query']}")
        if result["top_match"]:
            tm = result["top_match"]
            status = "✓ installed" if tm["installed"] else "✗ not installed"
            print(f"Skill:    {tm['skill']}")
            print(f"Package:  {tm['package']}")
            print(f"Source:   {tm['source']} ({status})")
            print(f"Confidence: {tm['confidence']:.2f}")
            print(f"Reason:   {tm['reason']}")
            if result["ambiguity"]:
                print(f"Ambiguity: YES — {result['ambiguity_detail']}")
            if result["install_required"]:
                print(f"Install:  {result['install_hint']}")
        else:
            print("No match found.")
            if result.get("fallback_used"):
                print("Fallback was used but no results.")

        if result["alternatives"]:
            print(f"\nAlternatives ({len(result['alternatives'])}):")
            for i, a in enumerate(result["alternatives"], 1):
                status = "✓" if a["installed"] else "✗"
                print(f"  {i}. {a['skill']} ({a['package']}) "
                      f"[{a['source']}] {status} — {a['confidence']:.2f}")
