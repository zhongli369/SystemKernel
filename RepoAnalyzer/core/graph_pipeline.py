"""Phase 2-B pipeline: Build structured Graph Model from dependency edges.

Orchestrates: load edges + metadata → build nodes + adjacency →
index → analyze (isolated, reachability, fan stats) → output
"""

import json
import os

from core.model import (
    DependencyEdge,
    GraphModel,
    GraphAnalysisStats,
    GraphNode,
)
from core.graph_builder import (
    build_adjacency,
    build_graph_nodes,
    load_enriched_metadata,
)
from core.graph_analyzer import (
    find_isolated_nodes,
    compute_entrypoint_reachability,
    compute_fan_stats,
)
from core.output_contract import wrap_output, unwrap_output


def load_edges(edges_path: str) -> list:
    """Load DependencyEdge list from dependency_edges.json."""
    with open(edges_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    edges = []
    for e in data.get("edges", []):
        edges.append(DependencyEdge(
            source=e["from"],
            target=e["to"],
            type=e.get("type", "import"),
            language=e.get("language", ""),
            confidence=e.get("confidence", 1.0),
        ))
    return edges


def run_graph_pipeline(repo_path: str, output_dir: str) -> str:
    """Full Phase 2-B pipeline.

    Reads output/dependency_edges.json and output/repo_map_enriched.json,
    builds a structured GraphModel, writes output/dependency_graph.json.

    Returns the path to the output file.
    """
    edges_path = os.path.join(output_dir, "dependency_edges.json")
    enriched_path = os.path.join(output_dir, "repo_map_enriched.json")

    if not os.path.exists(edges_path):
        raise FileNotFoundError(
            f"Dependency edges not found: {edges_path}. "
            f"Run 'python cli.py graph {repo_path}' first."
        )
    if not os.path.exists(enriched_path):
        raise FileNotFoundError(
            f"Enriched repo map not found: {enriched_path}. "
            f"Run 'python cli.py enrich {repo_path}' first."
        )

    edges = load_edges(edges_path)

    adjacency, reverse_adj = build_adjacency(edges)

    file_meta = load_enriched_metadata(enriched_path)
    nodes = build_graph_nodes(file_meta, adjacency)

    isolated = find_isolated_nodes(adjacency, reverse_adj)

    entrypoints = [n.id for n in nodes if n.is_entrypoint]
    reachability = compute_entrypoint_reachability(entrypoints, adjacency)

    fan_stats = compute_fan_stats(adjacency, reverse_adj)

    stats = GraphAnalysisStats(
        total_nodes=len(nodes),
        total_edges=len(edges),
        isolated_nodes=isolated,
        entrypoint_reachability=reachability,
        fan_stats=fan_stats,
    )

    graph_model = GraphModel(
        nodes=nodes,
        edges=edges,
        adjacency_list={k: sorted(v) for k, v in adjacency.items()},
        reverse_adjacency_list={k: sorted(v) for k, v in reverse_adj.items()},
        stats=stats,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "dependency_graph.json")

    repo_id = os.path.basename(os.path.abspath(repo_path))
    with open(output_path, "w", encoding="utf-8") as f:
        wrapped = wrap_output(repo_id, "analyze", graph_model.to_dict())
        json.dump(wrapped, f, indent=2, ensure_ascii=False)

    return output_path
