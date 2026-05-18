"""Compute coupling scores and approximate cohesion for nodes."""

from typing import Dict, List, Set

from core.model import CouplingMetrics, FanInOut


def compute_coupling(
    nodes: list,
    fan_stats: Dict[str, FanInOut],
    adjacency: Dict[str, List[str]],
) -> CouplingMetrics:
    """Calculate coupling and cohesion metrics.

    Coupling: normalized fan-out. High fan-out = high coupling (depends on too many).
    Cohesion approximation: inverse of dependency dispersion.
      - A node with tightly grouped dependencies (same layer/module) has higher cohesion.
      - A node with scattered dependencies across the system has lower cohesion.
    """
    if not fan_stats:
        return CouplingMetrics()

    # Normalization base: max fan_out in the system
    max_fan_out = max((f.fan_out for f in fan_stats.values()), default=1)

    coupling_scores: Dict[str, float] = {}
    for nid, fan in fan_stats.items():
        if max_fan_out > 0:
            coupling_scores[nid] = fan.fan_out / max_fan_out
        else:
            coupling_scores[nid] = 0.0

    # High coupling: coupling_score > 0.6
    high_coupling = sorted([
        nid for nid, score in coupling_scores.items() if score > 0.6
    ])

    # Cohesion approximation: check dependency dispersion
    # For each node, look at its outgoing edges' targets — are they in similar paths?
    low_cohesion = []
    for n in nodes:
        nid = n["id"]
        targets = adjacency.get(nid, [])
        if len(targets) <= 1:
            continue  # can't measure cohesion with 0-1 deps

        # Count how many different top-level directories the targets span
        top_dirs: Set[str] = set()
        for t in targets:
            top = t.split("/")[0] if "/" in t else "."
            top_dirs.add(top)

        # If dependencies span > 2 top-level directories, cohesion is low
        if len(targets) >= 3 and len(top_dirs) > 2:
            low_cohesion.append(nid)

    low_cohesion.sort()

    avg_coupling = (
        sum(coupling_scores.values()) / len(coupling_scores)
        if coupling_scores else 0.0
    )

    return CouplingMetrics(
        high_coupling_nodes=high_coupling,
        low_cohesion_nodes=low_cohesion,
        avg_coupling_score=round(avg_coupling, 3),
    )
