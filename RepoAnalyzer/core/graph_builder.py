"""Build structured graph model from dependency edges."""

import json
from typing import Dict, List

from core.model import DependencyEdge, GraphNode
from core.output_contract import unwrap_output


def load_enriched_metadata(repo_map_enriched_path: str) -> dict:
    """Load file metadata from the enriched repo map."""
    with open(repo_map_enriched_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    meta: Dict[str, dict] = {}
    for f in data.get("files", []):
        path = f["path"]
        meta[path] = {
            "role": f.get("role", ""),
            "importance_score": f.get("importance_score", 0.0),
            "is_entrypoint": f.get("is_entrypoint", False),
        }
    return meta


def build_adjacency(edges: List[DependencyEdge]) -> tuple:
    """Build forward and reverse adjacency lists from edges.

    Returns (adjacency_list, reverse_adjacency_list)
    """
    adj: Dict[str, List[str]] = {}
    rev: Dict[str, List[str]] = {}

    for edge in edges:
        src = edge.source
        tgt = edge.target

        if src not in adj:
            adj[src] = []
        adj[src].append(tgt)

        if tgt not in rev:
            rev[tgt] = []
        rev[tgt].append(src)

        # ensure target node exists in adjacency even if it has no outgoing edges
        if tgt not in adj:
            adj[tgt] = []

        # ensure source node exists in reverse even if nothing depends on it
        if src not in rev:
            rev[src] = []

    return adj, rev


def build_graph_nodes(
    file_meta: dict,
    adjacency: Dict[str, List[str]],
) -> List[GraphNode]:
    """Build GraphNode list from file metadata and adjacency keys.

    All nodes from both metadata and adjacency are included.
    """
    all_ids: set = set(adjacency.keys())
    for path in file_meta:
        all_ids.add(path)

    nodes: List[GraphNode] = []
    for node_id in sorted(all_ids):
        meta = file_meta.get(node_id, {})
        nodes.append(GraphNode(
            id=node_id,
            role=meta.get("role", ""),
            importance_score=meta.get("importance_score", 0.0),
            is_entrypoint=meta.get("is_entrypoint", False),
        ))
    return nodes
