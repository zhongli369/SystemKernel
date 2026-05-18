"""
routing_engine.py — Capability-Based Routing Engine (v4.0)

The CORE routing module. Orchestrates all matching dimensions:

  1. Alias resolution (exact > phrase > token_overlap)
  2. Capability + tag + domain matching
  3. Package-level context detection
  4. External skill integration
  5. Ambiguity detection
  6. Fallback resolution
  7. Deterministic tie-breaking

Scoring model:
  EXACT_ALIAS_MATCH       +1.00
  ALIAS_PHRASE_MATCH      +0.85
  ALIAS_TOKEN_OVERLAP     0.45–0.80
  CAPABILITY_MATCH        +0.75 per match
  TAG_MATCH               +0.45 per match
  DOMAIN_MATCH            +0.25 per match
  PACKAGE_CONTEXT_MATCH   +0.15 per match
  INSTALLED_BONUS         +0.05 (only for installed skills)

Tie-breaking (deterministic, in order):
  1. capability score
  2. exact alias score
  3. installed bonus
  4. tag overlap count
  5. alphabetical (skill name)

NO hardcoded 14-rule keyword list.
NO rule-order priority dependence.
NO ML / embeddings / vector DB.
"""

from typing import Optional

from . import CapabilityEntry, RoutingResult, MatchResult
from .alias_resolver import resolve_aliases
from .tag_matcher import match_all_tags
from .package_router import detect_package, get_package_context_boost
from .external_skill_adapter import (
    needs_install, get_install_hint, enrich_external_match,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Scoring constants
# ═══════════════════════════════════════════════════════════════════════════════

INSTALLED_BONUS = 0.05          # weak — does not gate routing
AMBIGUITY_THRESHOLD = 0.12      # score gap below this → ambiguity
FALLBACK_SCORE_THRESHOLD = 0.15  # below this → fallback used


# ═══════════════════════════════════════════════════════════════════════════════
# Keyword normalization (abbreviation expansion for office skills)
# ═══════════════════════════════════════════════════════════════════════════════

_ABBREV_MAP = {
    "ppt": "powerpoint",
    "pptx": "powerpoint",
    "xls": "excel",
    "xlsx": "excel",
    "doc": "word",
    "docx": "word",
    "spreadsheet": "excel",
    "presentation": "powerpoint",
    "slides": "powerpoint",
    "sheet": "excel",
    "word": "word",
}


def _normalize_query(query: str) -> str:
    """Expand abbreviations in query for better matching.

    e.g. 'create ppt' → 'create powerpoint'
         'build xlsx' → 'build excel'
    """
    words = query.lower().split()
    expanded = [_ABBREV_MAP.get(w, w) for w in words]
    return " ".join(expanded)


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_match_result(match: dict, pkg_boost: float = 0.0) -> MatchResult:
    """Convert a raw match dict into a MatchResult with final score.

    Applies installed bonus (+0.05 if installed) and package context boost.
    """
    entry = match["entry"]
    raw_score = match["score"]
    installed_bonus = INSTALLED_BONUS if entry.installed else 0.0
    final_score = min(raw_score + installed_bonus + pkg_boost, 1.0)

    return MatchResult(
        entry=entry,
        match_type=match["match_type"],
        matched_tokens=match.get("matched_tokens", ()),
        raw_score=round(raw_score, 4),
        installed_bonus=round(installed_bonus, 4),
        final_score=round(final_score, 4),
    )


def _merge_and_score(
    alias_matches: list[dict],
    tag_matches: list[dict],
    pkg_boosts: dict[str, float],
) -> list[MatchResult]:
    """Merge alias and tag matches, deduplicate by skill, keep best match type.

    For each skill, we prefer the match with the highest raw_score.
    Alias matches take priority over tag matches at equal score (more specific).
    """
    best: dict[str, MatchResult] = {}

    # Process alias matches first (higher priority)
    for match in alias_matches:
        skill = match["entry"].skill
        pkg_boost = pkg_boosts.get(skill, 0.0)
        mr = _compute_match_result(match, pkg_boost)
        if skill not in best or mr.raw_score > best[skill].raw_score:
            best[skill] = mr

    # Process tag matches
    for match in tag_matches:
        skill = match["entry"].skill
        pkg_boost = pkg_boosts.get(skill, 0.0)
        mr = _compute_match_result(match, pkg_boost)

        if skill not in best:
            # Tag match on a skill not already matched by alias
            best[skill] = mr
        else:
            existing = best[skill]
            # If tag match has higher raw score AND existing is not alias-based, replace
            if mr.raw_score > existing.raw_score and existing.match_type != "alias":
                best[skill] = mr
            # If existing is alias-based, keep it (alias > tag)
            # If tag match brings new capability insight, add match_type
            elif mr.match_type == "tag" and existing.match_type == "alias":
                # Keep alias as primary but note capability match
                if mr.raw_score > 0.5:
                    best[skill] = MatchResult(
                        entry=existing.entry,
                        match_type="alias+tag",
                        matched_tokens=existing.matched_tokens + mr.matched_tokens,
                        raw_score=max(existing.raw_score, mr.raw_score),
                        installed_bonus=existing.installed_bonus,
                        final_score=max(existing.final_score, mr.final_score),
                    )

    return list(best.values())


# ═══════════════════════════════════════════════════════════════════════════════
# Ambiguity detection
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_ambiguity(candidates: list[MatchResult]) -> tuple[bool, str | None]:
    """Detect if top candidates are ambiguous (close in score).

    Returns (is_ambiguous, detail_string_or_none).
    """
    if len(candidates) < 2:
        return False, None

    top = candidates[0]
    second = candidates[1]
    gap = round(top.final_score - second.final_score, 4)

    if gap < AMBIGUITY_THRESHOLD:
        detail = (
            f"Ambiguity: '{top.entry.skill}' ({top.final_score:.2f}) vs "
            f"'{second.entry.skill}' ({second.final_score:.2f}), gap={gap:.4f}. "
            f"Selected '{top.entry.skill}' by tie-breaking rules."
        )
        # List up to 4 competing candidates within threshold
        competing = [c for c in candidates[1:6]
                     if (top.final_score - c.final_score) < AMBIGUITY_THRESHOLD + 0.05]
        if competing:
            names = [f"'{c.entry.skill}' ({c.final_score:.2f})" for c in competing]
            detail += f" Competing: {', '.join(names)}."
        return True, detail

    return False, None


# ═══════════════════════════════════════════════════════════════════════════════
# Deterministic tie-breaking sort
# ═══════════════════════════════════════════════════════════════════════════════

def _sort_candidates(candidates: list[MatchResult]) -> list[MatchResult]:
    """Sort candidates deterministically.

    Primary: final_score descending
    Tie-break 1: match_type preference (alias > alias+tag > tag)
    Tie-break 2: installed (installed before not)
    Tie-break 3: alphabetical by skill name
    """
    match_type_priority = {"alias": 0, "alias+tag": 1, "tag": 2}

    def sort_key(mr: MatchResult):
        return (
            -mr.final_score,
            match_type_priority.get(mr.match_type, 9),
            not mr.entry.installed,  # False (installed) sorts before True
            mr.entry.skill,
        )

    return sorted(candidates, key=sort_key)


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback resolution
# ═══════════════════════════════════════════════════════════════════════════════

def _fallback_search(query: str, entries: list[CapabilityEntry],
                     pkg_boosts: dict[str, float]) -> list[MatchResult]:
    """Fallback: use tag matching + domain matching with lower threshold.

    When no strong match found, this provides "closest guesses" rather than
    returning None. Returns empty list if truly nothing matches.
    """
    tag_results = match_all_tags(query, entries)
    if not tag_results:
        return []

    results = []
    for match in tag_results:
        if match["score"] > 0.15:  # very low threshold for fallback
            pkg_boost = pkg_boosts.get(match["entry"].skill, 0.0)
            mr = _compute_match_result(match, pkg_boost)
            results.append(mr)

    return _sort_candidates(results)


# ═══════════════════════════════════════════════════════════════════════════════
# Main routing function
# ═══════════════════════════════════════════════════════════════════════════════

def route(query: str, entries: list[CapabilityEntry]) -> RoutingResult:
    """Route a user query to the best-matching skill.

    Pure function. Deterministic. No side effects.

    Args:
        query: Raw user input string.
        entries: Capability registry entries (from capability_registry).

    Returns:
        RoutingResult with top_match, alternatives, install info, ambiguity flag.
    """
    query = query.strip()
    if not query:
        return RoutingResult(
            query=query,
            top_match=None,
            alternatives=(),
            install_required=False,
            install_hint=None,
            ambiguity=False,
            ambiguity_detail=None,
            fallback_used=False,
            coverage_warning=False,
            score_breakdown={},
            matched_keywords=(),
        )

    # Normalize query (abbreviation expansion)
    normalized = _normalize_query(query)

    # Step 1: Package-level context
    package_scores = detect_package(normalized)
    pkg_boosts = get_package_context_boost(entries, package_scores)

    # Step 2: Alias matching
    alias_matches = resolve_aliases(normalized, entries)

    # Step 3: Tag + capability + domain matching
    tag_matches = match_all_tags(normalized, entries)

    # Step 4: Merge and score
    candidates = _merge_and_score(alias_matches, tag_matches, pkg_boosts)

    # Step 5: If no candidates, use fallback
    fallback_used = False
    coverage_warning = False

    if not candidates:
        candidates = _fallback_search(normalized, entries, pkg_boosts)
        if candidates:
            fallback_used = True
            coverage_warning = True
        else:
            return RoutingResult(
                query=query,
                top_match=None,
                alternatives=(),
                install_required=False,
                install_hint=None,
                ambiguity=False,
                ambiguity_detail=None,
                fallback_used=True,
                coverage_warning=True,
                score_breakdown={"reason": "No matching skills found for query"},
                matched_keywords=(),
            )

    # Step 6: Sort deterministically
    candidates = _sort_candidates(candidates)

    # Step 7: Detect ambiguity
    is_ambiguous, ambiguity_detail = _detect_ambiguity(candidates)

    # Step 8: Build result
    top = candidates[0] if candidates else None
    alternatives = tuple(candidates[1:9]) if len(candidates) > 1 else ()

    install_required = False
    install_hint = None
    if top and needs_install(top.entry):
        install_required = True
        install_hint = get_install_hint(top.entry)

    # Collect all matched keywords
    all_keywords: list[str] = []
    if top:
        all_keywords.extend(top.matched_tokens)
    for alt in alternatives[:4]:
        for kw in alt.matched_tokens:
            if kw not in all_keywords:
                all_keywords.append(kw)

    return RoutingResult(
        query=query,
        top_match=top,
        alternatives=alternatives,
        install_required=install_required,
        install_hint=install_hint,
        ambiguity=is_ambiguous,
        ambiguity_detail=ambiguity_detail,
        fallback_used=fallback_used,
        coverage_warning=coverage_warning,
        score_breakdown={
            "top_score": round(top.final_score, 4) if top else 0.0,
            "raw_score": round(top.raw_score, 4) if top else 0.0,
            "installed_bonus": round(top.installed_bonus, 4) if top else 0.0,
            "match_type": top.match_type if top else None,
            "candidate_count": len(candidates),
            "alias_candidates": len(alias_matches),
            "tag_candidates": len(tag_matches),
            "package_context": [
                {"package": p["package"], "score": p["score"]}
                for p in package_scores[:5]
            ],
        },
        matched_keywords=tuple(all_keywords[:20]),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience: load registry and route in one call
# ═══════════════════════════════════════════════════════════════════════════════

def route_from_disk(query: str) -> RoutingResult:
    """Load capability registry from disk and route query.

    Convenience function — the only disk I/O happens at load time.
    After loading, the route() call is pure.
    """
    from core.capability_registry import load_capability_registry
    entries = load_capability_registry()
    return route(query, entries)
