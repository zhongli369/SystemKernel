"""Compute node criticality_score (0~1) from fan-in, fan-out, role, and entrypoint status."""

from typing import Dict

from core.model import FanInOut


def compute_criticality(
    node_id: str,
    role: str,
    importance_score: float,
    is_entrypoint: bool,
    fan_stats: Dict[str, FanInOut],
    isolated_nodes: list,
) -> float:
    """Compute system criticality score for a node.

    Formula:
      base = importance_score * 0.25
      + fan_in / max_fan_in * 0.30   (reverse dependencies — who depends on this)
      + fan_out / max_fan_out * 0.15  (forward dependencies — what this depends on)
      + entrypoint_bonus               +0.30
      + role_bonus                     -0.20 ~ +0.20
      + isolated_penalty               -0.30

    Result clamped to [0.0, 1.0].
    """
    if not fan_stats:
        return 0.0

    fan = fan_stats.get(node_id)
    if fan is None:
        return 0.0

    max_fan_in = max((f.fan_in for f in fan_stats.values()), default=1)
    max_fan_out = max((f.fan_out for f in fan_stats.values()), default=1)

    score = 0.0

    # Base from Phase 1.5 importance
    score += importance_score * 0.25

    # Fan-in contribution (how many depend on me)
    if max_fan_in > 0:
        score += (fan.fan_in / max_fan_in) * 0.30

    # Fan-out contribution (how many I depend on)
    if max_fan_out > 0:
        score += (fan.fan_out / max_fan_out) * 0.15

    # Entrypoint boost
    if is_entrypoint:
        score += 0.30

    # Role-based adjustment
    role_bonus = {
        "entrypoint": 0.20,
        "service": 0.20,
        "interface": 0.15,
        "data": 0.10,
        "component": 0.05,
        "utility": -0.10,
        "config": -0.05,
        "script": -0.10,
        "test": -0.20,
        "docs": -0.25,
        "asset": -0.25,
    }
    score += role_bonus.get(role, 0.0)

    # Isolated node penalty
    if node_id in (isolated_nodes or []):
        score -= 0.30

    return max(0.0, min(score, 1.0))
