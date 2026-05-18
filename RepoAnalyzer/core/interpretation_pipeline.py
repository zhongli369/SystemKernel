"""Phase 2.5 pipeline: Graph Interpretation Layer.

Orchestrates: load dependency graph → compute criticality →
classify system roles → infer edge dependency types →
compute impact levels → export interpreted_graph.json
"""

import json
import os
from typing import Dict

from core.model import (
    InterpretedNode,
    InterpretedEdge,
    InterpretedGraph,
    FanInOut,
)
from core.criticality_scorer import compute_criticality
from core.system_role_classifier import classify_system_role
from core.dependency_meaning_inferer import infer_dependency_type
from core.impact_analyzer import compute_impact_level
from core.output_contract import wrap_output, unwrap_output


def _load_graph(graph_path: str) -> dict:
    with open(graph_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return unwrap_output(raw)


def _build_fan_stats(stats_data: dict) -> Dict[str, FanInOut]:
    result: Dict[str, FanInOut] = {}
    for node_id, fan_data in stats_data.get("fan_stats", {}).items():
        result[node_id] = FanInOut(
            fan_in=fan_data.get("fan_in", 0),
            fan_out=fan_data.get("fan_out", 0),
        )
    return result


def run_interpretation_pipeline(repo_path: str, output_dir: str) -> str:
    """Full Phase 2.5 pipeline.

    Reads output/dependency_graph.json, produces output/interpreted_graph.json.
    """
    graph_path = os.path.join(output_dir, "dependency_graph.json")

    if not os.path.exists(graph_path):
        raise FileNotFoundError(
            f"Dependency graph not found: {graph_path}. "
            f"Run 'python cli.py analyze {repo_path}' first."
        )

    data = _load_graph(graph_path)

    fan_stats = _build_fan_stats(data.get("stats", {}))
    isolated_nodes = data.get("stats", {}).get("isolated_nodes", [])

    # Build lookup tables
    node_roles: Dict[str, str] = {}
    node_importance: Dict[str, float] = {}
    node_entrypoint: Dict[str, bool] = {}
    for n in data.get("nodes", []):
        node_roles[n["id"]] = n.get("role", "")
        node_importance[n["id"]] = n.get("importance_score", 0.0)
        node_entrypoint[n["id"]] = n.get("is_entrypoint", False)

    # Interpret nodes
    system_roles: Dict[str, str] = {}
    interpreted_nodes = []
    for n in data.get("nodes", []):
        nid = n["id"]
        role = node_roles.get(nid, "")
        importance = node_importance.get(nid, 0.0)
        is_ep = node_entrypoint.get(nid, False)

        criticality = compute_criticality(
            nid, role, importance, is_ep, fan_stats, isolated_nodes
        )
        system_role = classify_system_role(
            nid, role, is_ep, fan_stats, isolated_nodes
        )
        impact = compute_impact_level(
            criticality, is_ep, nid in (isolated_nodes or [])
        )

        system_roles[nid] = system_role
        interpreted_nodes.append(InterpretedNode(
            id=nid,
            role=role,
            importance_score=importance,
            is_entrypoint=is_ep,
            criticality_score=round(criticality, 3),
            system_role=system_role,
            impact_level=impact,
        ))

    # Interpret edges
    interpreted_edges = []
    edge_types_seen: Dict[str, int] = {}
    for e in data.get("edges", []):
        src = e["from"]
        tgt = e["to"]
        dep_type = infer_dependency_type(
            node_roles.get(src, ""),
            node_roles.get(tgt, ""),
            system_roles.get(src, ""),
            system_roles.get(tgt, ""),
        )
        edge_types_seen[dep_type] = edge_types_seen.get(dep_type, 0) + 1

        interpreted_edges.append(InterpretedEdge(
            source=src,
            target=tgt,
            type=e.get("type", "import"),
            language=e.get("language", ""),
            confidence=e.get("confidence", 1.0),
            dependency_type=dep_type,
        ))

    # Aggregate stats
    criticality_levels = {"high": 0, "medium": 0, "low": 0}
    for n in interpreted_nodes:
        criticality_levels[n.impact_level] += 1

    system_role_counts: Dict[str, int] = {}
    for n in interpreted_nodes:
        sr = n.system_role
        system_role_counts[sr] = system_role_counts.get(sr, 0) + 1

    stats = {
        "total_nodes": len(interpreted_nodes),
        "total_edges": len(interpreted_edges),
        "criticality_distribution": criticality_levels,
        "system_role_distribution": system_role_counts,
        "dependency_type_distribution": edge_types_seen,
        "isolated_nodes": isolated_nodes,
        "entrypoint_reachability": data.get("stats", {}).get("entrypoint_reachability", {}),
        "fan_stats": data.get("stats", {}).get("fan_stats", {}),
    }

    graph = InterpretedGraph(
        nodes=interpreted_nodes,
        edges=interpreted_edges,
        adjacency_list=data.get("adjacency_list", {}),
        reverse_adjacency_list=data.get("reverse_adjacency_list", {}),
        stats=stats,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "interpreted_graph.json")

    repo_id = os.path.basename(os.path.abspath(repo_path))
    with open(output_path, "w", encoding="utf-8") as f:
        wrapped = wrap_output(repo_id, "interpret", graph.to_dict())
        json.dump(wrapped, f, indent=2, ensure_ascii=False)

    return output_path
