#!/usr/bin/env python3
"""
classify.py — Auto-classification engine for Skill Package Manager.

Given a skill path or skill data, reads SKILL.md frontmatter and description,
then matches against package auto_match_keywords to determine the best-fit package.

Two entry points:
  classify_skill_pure(skill_data, manifests)  — PURE: no disk access
  classify_skill(skill_path, manifests=None)  — convenience: reads SKILL.md from disk

Returns:
    {
        "package": "dev",
        "confidence": 0.82,
        "matched_keywords": ["react", "frontend"]
    }

Usage:
    python classify.py <skill_path>
    python classify.py <skill_path> --json
"""

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGES_DIR = SCRIPT_DIR / "packages"
SKILL_MD_FILENAME = "SKILL.md"
CONFIDENCE_THRESHOLD = 0.15  # minimum confidence to auto-assign


# ---------------------------------------------------------------------------
# SKILL.md frontmatter parser
# ---------------------------------------------------------------------------

def parse_skill_md(skill_path: Path) -> dict:
    """Parse SKILL.md from a skill directory. Returns dict with keys:
    name, description, tags, body_text (for keyword extraction).
    """
    md_path = skill_path / SKILL_MD_FILENAME
    if not md_path.exists():
        return {}

    text = md_path.read_text(encoding="utf-8", errors="replace")
    result = {"body_text": text}

    # Parse YAML frontmatter (between --- delimiters)
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        for line in frontmatter.split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip("\"'")
                result[key] = value if value else []
            elif line and line.startswith("-"):
                if "tags" not in result or not isinstance(result.get("tags"), list):
                    result["tags"] = []
                result["tags"].append(line.lstrip("- ").strip())

    return result


# ---------------------------------------------------------------------------
# Keyword extraction from skill description + body
# ---------------------------------------------------------------------------

def extract_keywords(skill_data: dict, name: str = None) -> set:
    """Extract keyword set from skill frontmatter and body text."""
    keywords = set()

    # From skill name — often the most specific signal
    if name:
        keywords.update(_tokenize(name.replace("-", " ")))

    # From description
    desc = skill_data.get("description", "")
    keywords.update(_tokenize(desc))

    # From tags
    if isinstance(skill_data.get("tags"), list):
        for tag in skill_data["tags"]:
            keywords.update(_tokenize(str(tag)))
    elif isinstance(skill_data.get("tags"), str):
        keywords.update(_tokenize(skill_data["tags"]))

    # From body text (first 2000 chars for efficiency)
    body = skill_data.get("body_text", "")[:2000]
    # Extract meaningful heading text (lines starting with #)
    for line in body.split("\n"):
        line = line.strip().lstrip("#").strip()
        if line and len(line) > 3:
            keywords.update(_tokenize(line.lower()))

    return keywords


def _tokenize(text: str) -> set:
    """Tokenize text into lowercase keyword tokens (1-3 word phrases)."""
    text = str(text).lower()
    # Strip punctuation
    text = re.sub(r"[^a-z0-9\s/#\-]", " ", text)
    tokens = set()
    words = text.split()
    for w in words:
        w = w.strip("/#- ")
        if len(w) >= 2:
            tokens.add(w)
    # Also add bigrams
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}".strip("/#- ")
        if len(bigram) >= 4:
            tokens.add(bigram)
    # And trigrams
    for i in range(len(words) - 2):
        trigram = f"{words[i]} {words[i+1]} {words[i+2]}".strip("/#- ")
        if len(trigram) >= 5:
            tokens.add(trigram)
    return tokens


# ---------------------------------------------------------------------------
# Package manifest loader
# ---------------------------------------------------------------------------

def load_all_manifests() -> dict:
    """Load all package manifest.json files from disk."""
    manifests = {}
    if not PACKAGES_DIR.exists():
        return manifests

    for pkg_dir in PACKAGES_DIR.iterdir():
        if not pkg_dir.is_dir():
            continue
        manifest_path = pkg_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifests[manifest["name"]] = manifest
            except (json.JSONDecodeError, KeyError):
                continue
    return manifests


# ---------------------------------------------------------------------------
# Pure classification function (v3.5 — no disk access)
# ---------------------------------------------------------------------------

def classify_skill_pure(skill_data: dict, manifests: dict,
                         skill_name: str = None) -> dict:
    """Classify a skill into the best-matching package.

    PURE FUNCTION — no filesystem access, no side effects.
    All data is passed in as parameters.

    Args:
        skill_data: Parsed SKILL.md data (from parse_skill_md)
        manifests: Dict of {package_name: manifest_dict}
        skill_name: Optional skill name override

    Returns:
        {
            "package": "dev",           # best package name, or None
            "confidence": 0.82,         # 0.0–1.0
            "matched_keywords": [...],  # matched keywords
            "scores": {...},           # per-package scores (for debugging)
            "severity": "high" | "medium" | "low" | "none"
        }
    """
    if not manifests:
        return _no_match("No packages available for classification")

    if not skill_data:
        return _no_match("No skill data provided")

    name = skill_name or skill_data.get("name") or "unknown"
    skill_keywords = extract_keywords(skill_data, name=name)
    if not skill_keywords:
        return _no_match("No keywords extractable from skill")

    # Score each package — keyword matching against skill content
    scores = {}
    for pkg_name, manifest in manifests.items():
        match_keywords = [kw.lower() for kw in manifest.get("auto_match_keywords", [])]
        if not match_keywords:
            continue

        matched = []
        for pkg_kw in match_keywords:
            parts = pkg_kw.split()

            if len(parts) == 1:
                # Single-word keyword: tokenize and check for any overlap
                pkg_tokens = _tokenize(pkg_kw)
                if any(pt in skill_keywords for pt in pkg_tokens):
                    matched.append(pkg_kw)
            else:
                # Multi-word keyword (e.g. "code review", "claude api"):
                # Match if the full multi-word phrase appears as a bigram/trigram
                # in skill keywords, OR if a majority of component words match.
                if pkg_kw in skill_keywords:
                    matched.append(pkg_kw)
                    continue
                parts3 = [p for p in parts if len(p) >= 3]
                if len(parts3) >= 2:
                    hits = sum(1 for p in parts3 if p in skill_keywords)
                    # 2 words → both must match; 3+ → majority
                    required = len(parts3) if len(parts3) == 2 else (len(parts3) + 1) // 2
                    if hits >= required:
                        matched.append(pkg_kw)

        if matched:
            matched_unique = list(set(matched))
            # Jaccard-inspired: matched / (pkg_keywords + unmatched)
            raw_score = len(matched_unique) / len(match_keywords)
            scores[pkg_name] = {
                "score": round(raw_score, 4),
                "matched": matched_unique,
            }

    if not scores:
        return _no_match("No keyword matches across any package")

    # Require at least 2 matches or 1 very strong match for confidence
    best_pkg = max(scores, key=lambda p: scores[p]["score"])
    best = scores[best_pkg]

    # Confidence: penalize single-match results heavily
    match_count = len(best["matched"])
    raw = best["score"]
    if match_count == 1:
        confidence = min(raw * 0.4, 0.35)  # single match → low confidence
    elif match_count == 2:
        confidence = min(raw * 1.5, 0.75)
    else:
        confidence = min(raw * 2.0, 1.0)

    severity = "high"
    if confidence < 0.35:
        severity = "low"
    elif confidence < 0.65:
        severity = "medium"

    return {
        "package": best_pkg,
        "confidence": round(confidence, 4),
        "matched_keywords": best["matched"],
        "scores": {p: s["score"] for p, s in scores.items()},
        "severity": severity,
        "match_count": match_count,
    }


# ---------------------------------------------------------------------------
# Convenience wrapper (reads from disk — for CLI / registration use)
# ---------------------------------------------------------------------------

def classify_skill(skill_path, manifests=None) -> dict:
    """Classify a skill into the best-matching package.

    Convenience wrapper that reads SKILL.md from disk.
    For pure operation, use classify_skill_pure() directly.

    Args:
        skill_path: Path to skill directory (str or Path)
        manifests: Optional pre-loaded manifests dict (loaded from disk if None)

    Returns:
        Same format as classify_skill_pure()
    """
    skill_path = Path(skill_path)
    if manifests is None:
        manifests = load_all_manifests()

    if not manifests:
        return _no_match("No packages available for classification")

    # Parse skill from disk
    skill_data = parse_skill_md(skill_path)
    if not skill_data:
        return _no_match(f"No SKILL.md found at {skill_path}")

    skill_name = skill_data.get("name") or skill_path.name
    return classify_skill_pure(skill_data, manifests, skill_name=skill_name)


def _no_match(reason: str) -> dict:
    return {
        "package": None,
        "confidence": 0.0,
        "matched_keywords": [],
        "scores": {},
        "severity": "none",
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python classify.py <skill_path> [--json]", file=sys.stderr)
        sys.exit(1)

    skill_path = sys.argv[1]
    use_json = "--json" in sys.argv

    result = classify_skill(skill_path)

    if use_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["package"] is None:
            print(f"  No match: {result.get('reason', 'unknown')}")
        else:
            print(f"  Package:      {result['package']}")
            print(f"  Confidence:   {result['confidence']:.2%}")
            print(f"  Severity:     {result['severity']}")
            print(f"  Keywords:     {', '.join(result['matched_keywords'])}")
            if result["scores"]:
                print(f"  All scores:   {json.dumps(result['scores'], indent=2)}")

    sys.exit(0 if result["package"] else 1)


if __name__ == "__main__":
    main()
