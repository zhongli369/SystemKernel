"""Compute task impact scores from criticality, fan-in, fan-out, and dependency depth."""

from typing import Dict, List


def compute_impact_scores(
    tasks: list,
    fan_stats: dict,
    criticality_map: Dict[str, float],
    adjacency: Dict[str, List[str]],
) -> list:
    """Compute impact_score for each task based on target node metrics.

    Formula per task:
      impact = avg(criticality of targets) * 0.4
             + avg(normalized fan_in of targets) * 0.25
             + avg(normalized fan_out of targets) * 0.15
             + dependency_depth_penalty * 0.20

    Returns the modified task list with impact_score set.
    """
    if not fan_stats:
        return tasks

    max_fan_in = max((f.get("fan_in", 0) for f in fan_stats.values()), default=1)
    max_fan_out = max((f.get("fan_out", 0) for f in fan_stats.values()), default=1)

    for task in tasks:
        targets = task.target_nodes
        if not targets:
            task.impact_score = 0.0
            continue

        total_crit = 0.0
        total_fan_in = 0.0
        total_fan_out = 0.0
        total_depth = 0.0

        for nid in targets:
            total_crit += criticality_map.get(nid, 0.0)
            fan = fan_stats.get(nid, {})
            fi = fan.get("fan_in", 0)
            fo = fan.get("fan_out", 0)
            total_fan_in += fi / max(max_fan_in, 1)
            total_fan_out += fo / max(max_fan_out, 1)
            total_depth += _dependency_depth(nid, adjacency)

        n = len(targets)
        avg_crit = total_crit / n
        avg_fi = total_fan_in / n
        avg_fo = total_fan_out / n
        avg_depth = total_depth / n
        depth_penalty = min(avg_depth / 5.0, 1.0) * 0.20

        impact = avg_crit * 0.40 + avg_fi * 0.25 + avg_fo * 0.15 + depth_penalty
        task.impact_score = round(min(impact, 1.0), 3)

    return tasks


def _dependency_depth(start: str, adjacency: Dict[str, List[str]], max_depth: int = 10) -> int:
    """Compute max dependency depth from a node using BFS."""
    if start not in adjacency or not adjacency[start]:
        return 0

    visited = {start}
    frontier = [(start, 0)]
    max_d = 0

    while frontier:
        current, depth = frontier.pop(0)
        max_d = max(max_d, depth)
        if depth >= max_depth:
            break
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                frontier.append((neighbor, depth + 1))

    return max_d
