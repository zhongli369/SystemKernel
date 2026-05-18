"""Lightweight graph analysis: isolated nodes, reachability, fan-in/out."""

from collections import deque
from typing import Dict, List, Set

from core.model import FanInOut, GraphModel, GraphAnalysisStats
from core.graph_builder import build_adjacency, build_graph_nodes, load_enriched_metadata
from core.graph_indexer import NodeIndex


def find_isolated_nodes(
    adjacency: Dict[str, List[str]],
    reverse_adj: Dict[str, List[str]],
) -> List[str]:
    """Find nodes with no incoming and no outgoing edges."""
    isolated: List[str] = []
    for node_id in sorted(adjacency.keys()):
        out = len(adjacency.get(node_id, []))
        inn = len(reverse_adj.get(node_id, []))
        if out == 0 and inn == 0:
            isolated.append(node_id)
    return isolated


def bfs_reachable(start: str, adjacency: Dict[str, List[str]]) -> List[str]:
    """BFS from a start node; returns all reachable nodes in sorted order."""
    if start not in adjacency:
        return []

    visited: Set[str] = set()
    queue = deque([start])
    visited.add(start)

    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    visited.discard(start)
    return sorted(visited)


def compute_entrypoint_reachability(
    entrypoints: List[str],
    adjacency: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """For each entrypoint, compute the set of nodes reachable via BFS."""
    result: Dict[str, List[str]] = {}
    for ep in entrypoints:
        reachable = bfs_reachable(ep, adjacency)
        result[ep] = reachable
    return result


def compute_fan_stats(
    adjacency: Dict[str, List[str]],
    reverse_adj: Dict[str, List[str]],
) -> Dict[str, FanInOut]:
    """Compute fan-in and fan-out for every node."""
    all_nodes: Set[str] = set(adjacency.keys()) | set(reverse_adj.keys())
    result: Dict[str, FanInOut] = {}
    for node_id in sorted(all_nodes):
        result[node_id] = FanInOut(
            fan_in=len(reverse_adj.get(node_id, [])),
            fan_out=len(adjacency.get(node_id, [])),
        )
    return result


def compute_reverse_dependency_map(
    adjacency: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """Build reverse dependency map (who depends on me?). Same as reverse adjacency."""
    # reverse_adjacency already built by build_adjacency — this is a semantic alias
    return dict(adjacency)
