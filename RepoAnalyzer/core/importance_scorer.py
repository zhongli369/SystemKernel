"""Importance scorer — computes a 0~1 importance score for each file."""

from typing import Optional

# Base score by role
ROLE_BASE_SCORE = {
    "entrypoint": 1.0,
    "service": 0.8,
    "interface": 0.8,
    "data": 0.7,
    "component": 0.6,
    "utility": 0.5,
    "config": 0.4,
    "script": 0.3,
    "test": 0.2,
    "asset": 0.15,
    "docs": 0.1,
    "unknown": 0.3,
}

# Bonus keywords in path that indicate higher importance
IMPORTANCE_BONUS_KEYWORDS = [
    "core",
    "engine",
    "kernel",
    "orchestrator",
    "pipeline",
    "dispatcher",
    "runtime",
]


def compute_importance(
    role: str,
    is_entrypoint: bool,
    path: str,
    name: str,
) -> float:
    """Compute importance score for a file (0.0 ~ 1.0).

    Formula: base_role_score + entrypoint_bonus + naming_bonus, clamped to 1.0
    """
    base = ROLE_BASE_SCORE.get(role, 0.3)
    score = base

    if is_entrypoint and role != "entrypoint":
        score += 0.1

    normalized = path.replace("\\", "/").lower()
    for kw in IMPORTANCE_BONUS_KEYWORDS:
        if kw in normalized:
            score += 0.1
            break

    name_lower = name.lower()
    if any(kw in name_lower for kw in ("cli", "main", "app", "index", "server")):
        if not is_entrypoint and role != "entrypoint":
            score += 0.05

    return min(score, 1.0)
