"""
package_router.py — Package-Level Intent Detection (v4.0)

Detects which package(s) a user query targets, using:
  1. lazyload_rules.json keyword → package mapping
  2. Package manifest auto_match_keywords

Used for:
  - Package-level routing (when no specific skill matches)
  - Lazy-load hints (suggest installing a package)
  - Domain context for skill disambiguation

IMPORTANT: Package routing does NOT gate skill discovery.
It provides context hints only. A skill CAN be recommended even
if its package scores low on package-level matching.
"""

import json
import re
from pathlib import Path

from . import CapabilityEntry

# ═══════════════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════════════

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
_LAZYLOAD_PATH = _SCRIPT_DIR / "data" / "lazyload_rules.json"
_PACKAGES_DIR = _SCRIPT_DIR / "packages"


# ═══════════════════════════════════════════════════════════════════════════════
# Tokenization
# ═══════════════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> set[str]:
    text = re.sub(r"[^a-z0-9\s]", " ", str(text).lower())
    words = text.split()
    tokens = set()
    for w in words:
        w = w.strip()
        if len(w) >= 2:
            tokens.add(w)
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if len(bigram) >= 4:
            tokens.add(bigram)
    return tokens


# ═══════════════════════════════════════════════════════════════════════════════
# Rule loading
# ═══════════════════════════════════════════════════════════════════════════════

def _load_lazyload_rules() -> list[dict]:
    """Load lazyload_rules.json rules. Returns empty list on failure."""
    try:
        data = json.loads(_LAZYLOAD_PATH.read_text(encoding="utf-8"))
        return data.get("rules", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_manifest_keywords(pkg_name: str) -> list[str]:
    """Load auto_match_keywords from a package manifest."""
    manifest_path = _PACKAGES_DIR / pkg_name / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return manifest.get("auto_match_keywords", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _get_all_package_keywords() -> dict[str, tuple[str, ...]]:
    """Build {package_name: (keywords, ...)} from manifests + lazyload rules."""
    pkg_keywords: dict[str, set[str]] = {}

    # From lazyload rules
    for rule in _load_lazyload_rules():
        pkg = rule.get("package", "")
        kws = rule.get("keywords", [])
        if pkg and kws:
            pkg_keywords.setdefault(pkg, set()).update(kw.lower() for kw in kws)

    # From package manifests
    for pkg_dir in _PACKAGES_DIR.iterdir():
        if not pkg_dir.is_dir() or not (pkg_dir / "manifest.json").exists():
            continue
        pkg_name = pkg_dir.name
        manifest_kws = _load_manifest_keywords(pkg_name)
        if manifest_kws:
            pkg_keywords.setdefault(pkg_name, set()).update(
                kw.lower() for kw in manifest_kws
            )

    return {pkg: tuple(kws) for pkg, kws in pkg_keywords.items()}


# Cache — built once
_PKG_KEYWORDS_CACHE: dict[str, tuple[str, ...]] | None = None


def _get_pkg_keywords() -> dict[str, tuple[str, ...]]:
    global _PKG_KEYWORDS_CACHE
    if _PKG_KEYWORDS_CACHE is None:
        _PKG_KEYWORDS_CACHE = _get_all_package_keywords()
    return _PKG_KEYWORDS_CACHE


# ═══════════════════════════════════════════════════════════════════════════════
# Package matching
# ═══════════════════════════════════════════════════════════════════════════════

PACKAGE_CONTEXT_SCORE = 0.15


def detect_package(query: str) -> list[dict]:
    """Detect which package(s) the query targets.

    Returns list of {package, score, matched_keywords} sorted by score desc.
    """
    query_tokens = _tokenize(query.lower())
    if not query_tokens:
        return []

    pkg_keywords = _get_pkg_keywords()
    results = []

    for pkg_name, keywords in pkg_keywords.items():
        matched = []
        for kw in keywords:
            kw_tokens = _tokenize(kw)
            if not kw_tokens:
                continue
            # Check for phrase match
            if len(kw_tokens) >= 2 and kw in query.lower():
                matched.append(kw)
                continue
            # Token overlap
            overlap = query_tokens & kw_tokens
            if overlap:
                matched.append(kw)

        if matched:
            score = min(
                PACKAGE_CONTEXT_SCORE * len(matched),
                0.60,  # cap package context score
            )
            results.append({
                "package": pkg_name,
                "score": round(score, 4),
                "matched_keywords": matched,
            })

    results.sort(key=lambda r: (-r["score"], r["package"]))
    return results


def get_package_context_boost(entries: list[CapabilityEntry],
                              package_scores: list[dict]) -> dict[str, float]:
    """Compute a package-level context boost for each skill entry.

    Returns {skill_name: boost_amount} where boost is in [0, 0.10].
    This is a WEAK signal — it nudges skills from context-relevant packages
    but does not override strong alias/capability signals.
    """
    if not package_scores:
        return {}

    pkg_score_map = {ps["package"]: ps["score"] for ps in package_scores}
    max_pkg_score = max(ps["score"] for ps in package_scores) if package_scores else 0.0

    boosts = {}
    for entry in entries:
        pkg_score = pkg_score_map.get(entry.package, 0.0)
        if pkg_score > 0 and max_pkg_score > 0:
            # Scale: package with highest match gets 0.10, others proportional
            boost = (pkg_score / max_pkg_score) * 0.10
        else:
            boost = 0.0
        boosts[entry.skill] = round(boost, 4)

    return boosts
