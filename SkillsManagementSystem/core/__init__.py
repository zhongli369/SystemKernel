"""
core/ — Skill System Routing Pipeline (v4.0)

Capability-based routing. Suggestion-only. Deterministic. No side effects.

Architecture:
  capability_registry    — unified local + external skill metadata
  alias_resolver         — exact / fuzzy alias matching
  tag_matcher            — tag-based matching
  package_router         — package-level intent detection
  external_skill_adapter — external skill integration
  routing_engine         — main scoring + tie-breaking
  routing_pipeline       — top-level orchestration entry point
"""

from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityEntry:
    """Unified skill capability record — local + external are treated equally."""
    skill: str                     # skill name
    package: str                   # parent package
    source: str                    # "local" | "external"
    installed: bool                # True if skill files exist on disk
    description: str               # from registry.json / frontmatter
    aliases: tuple[str, ...]       # search aliases (e.g. "react optimization")
    tags: tuple[str, ...]          # topic tags (e.g. "react", "frontend")
    domains: tuple[str, ...]       # domain categories (e.g. "frontend", "backend")
    capabilities: tuple[str, ...]  # capability descriptions (e.g. "render optimization")
    install_hint: str = ""         # npx / pip install command for external skills
    version: str = "1.0.0"


@dataclass(frozen=True)
class MatchResult:
    """Result of a single matching dimension."""
    entry: CapabilityEntry
    match_type: str                # "alias" | "capability" | "tag" | "domain" | "package_context"
    matched_tokens: tuple[str, ...]
    raw_score: float               # pre-bonus score
    installed_bonus: float = 0.0   # +0.05 max
    final_score: float = 0.0       # raw_score + installed_bonus

    def with_final_score(self, final: float) -> "MatchResult":
        return MatchResult(
            entry=self.entry,
            match_type=self.match_type,
            matched_tokens=self.matched_tokens,
            raw_score=self.raw_score,
            installed_bonus=self.installed_bonus,
            final_score=final,
        )


@dataclass(frozen=True)
class RoutingResult:
    """Final routing output."""
    query: str
    top_match: Optional[MatchResult]
    alternatives: tuple[MatchResult, ...]
    install_required: bool           # True if top match is external + not installed
    install_hint: Optional[str]
    ambiguity: bool                  # True if #1 and #2 are close in score
    ambiguity_detail: Optional[str]
    fallback_used: bool
    coverage_warning: bool           # True if result came from weak fallback
    score_breakdown: dict
    matched_keywords: tuple[str, ...]

    def as_dict(self) -> dict:
        d = {
            "query": self.query,
            "top_match": None,
            "alternatives": [],
            "install_required": self.install_required,
            "install_hint": self.install_hint,
            "ambiguity": self.ambiguity,
            "ambiguity_detail": self.ambiguity_detail,
            "fallback_used": self.fallback_used,
            "coverage_warning": self.coverage_warning,
            "score_breakdown": self.score_breakdown,
            "matched_keywords": list(self.matched_keywords),
        }
        if self.top_match:
            d["top_match"] = {
                "skill": self.top_match.entry.skill,
                "package": self.top_match.entry.package,
                "source": self.top_match.entry.source,
                "installed": self.top_match.entry.installed,
                "confidence": round(self.top_match.final_score, 4),
                "reason": f"Matched via {self.top_match.match_type}: {', '.join(self.top_match.matched_tokens[:5])}",
                "matched_by": [self.top_match.match_type],
            }
        d["alternatives"] = [
            {
                "skill": a.entry.skill,
                "package": a.entry.package,
                "source": a.entry.source,
                "installed": a.entry.installed,
                "confidence": round(a.final_score, 4),
            }
            for a in self.alternatives[:5]
        ]
        return d


@dataclass(frozen=True)
class AmbiguityDetail:
    """Details when multiple candidates are close in score."""
    is_ambiguous: bool
    candidates: tuple[tuple[str, str, float], ...]  # (skill, package, score)
    score_gap: float
    reason: str
