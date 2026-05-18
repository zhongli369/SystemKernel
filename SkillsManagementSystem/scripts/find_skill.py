#!/usr/bin/env python3
"""
find_skill.py — Search for skills in local registry.

Pure registry lookup only. No external subprocess calls.
No side effects beyond reading registry.json.

Usage:
    python scripts/find_skill.py <query>
    python scripts/find_skill.py <query> --json
"""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = SCRIPT_DIR / "registry.json"


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def tokenize(text: str) -> set:
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    tokens = set()
    words = text.split()
    for w in words:
        if len(w) >= 2:
            tokens.add(w)
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if len(bigram) >= 4:
            tokens.add(bigram)
    return tokens


def _score_candidate(query_tokens: set, name: str, description: str = "") -> float:
    name_lower = name.lower().replace("-", " ").replace("_", " ")
    desc_lower = (description or "").lower()

    name_tokens = tokenize(name_lower)
    desc_tokens = tokenize(desc_lower)

    # Exact query match in name
    if all(qt in name_tokens for qt in query_tokens):
        return 0.95

    # Jaccard on name tokens
    intersection = query_tokens & name_tokens
    union = query_tokens | name_tokens
    name_score = len(intersection) / max(len(union), 1)

    # Jaccard on description tokens (weighted lower)
    desc_intersection = query_tokens & desc_tokens
    desc_union = query_tokens | desc_tokens
    desc_score = len(desc_intersection) / max(len(desc_union), 1) * 0.4 if desc_union else 0

    return round(max(name_score * 0.7 + desc_score, 0.05), 4)


# ---------------------------------------------------------------------------
# Pure search function — accepts registry data as parameter
# ---------------------------------------------------------------------------

def find_skill_pure(query: str, registry: dict) -> dict:
    """Search skills in registry by keyword overlap.

    PURE FUNCTION — no disk access, no subprocess calls, no side effects.

    Args:
        query: Search query string
        registry: Full registry.json data as dict

    Returns:
        {"query": str, "results": [...], "count": int}
    """
    query_tokens = tokenize(query)
    results = []

    # Search skills
    for skill_name, skill in registry.get("skills", {}).items():
        score = _score_candidate(query_tokens, skill_name, skill.get("description", ""))
        if score > 0.1:
            results.append({
                "name": skill_name,
                "source": "[local]",
                "score": score,
                "description": skill.get("description", ""),
                "package": skill.get("package", "?"),
            })

    # Search packages
    seen = {r["name"] for r in results}
    for pkg_name, pkg in registry.get("packages", {}).items():
        if pkg_name in seen:
            continue
        score = _score_candidate(query_tokens, pkg_name, pkg.get("description", ""))
        if score > 0.1:
            results.append({
                "name": pkg_name,
                "source": "[package]",
                "score": score,
                "description": pkg.get("description", ""),
                "package": pkg_name,
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return {"query": query, "results": results[:20], "count": len(results)}


# ---------------------------------------------------------------------------
# Convenience wrapper — loads registry from disk
# ---------------------------------------------------------------------------

def find_skill(query: str) -> dict:
    """Search skills across local registry.

    Convenience wrapper that loads registry.json from disk.
    For pure operation, use find_skill_pure() directly.
    """
    registry = load_registry()
    print(f"  [local] searching registry...")
    result = find_skill_pure(query, registry)
    print(f"  [local] found {result['count']} result(s)")
    return result


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_results(result: dict) -> str:
    if not result["results"]:
        return f'No skills found for "{result["query"]}".'

    lines = [f'Searching for: "{result["query"]}"', ""]
    for i, r in enumerate(result["results"], 1):
        confidence = r["score"]
        tag = r["source"]
        lines.append(f"{i}. {r['name']} (confidence {confidence:.2f}) {tag}")
        if r.get("description"):
            lines.append(f"   {r['description'][:100]}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/find_skill.py <query> [--json]", file=sys.stderr)
        sys.exit(1)

    query = sys.argv[1]
    use_json = "--json" in sys.argv

    result = find_skill(query)

    if use_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_results(result))


if __name__ == "__main__":
    main()
