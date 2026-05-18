"""Build dependency edges from extracted imports and resolved paths."""

import os
from typing import Dict, List, Optional, Set

from core.model import DependencyEdge, DependencyGraph, DependencyGraphStats
from core.import_extractor import extract_imports
from core.path_resolver import build_file_index, resolve_import


def build_dependency_graph(
    root_path: str,
    file_paths: List[str],
    file_languages: Dict[str, str],
) -> DependencyGraph:
    """Build a full dependency graph from source files.

    Args:
        root_path: Absolute root of the repository
        file_paths: List of relative file paths
        file_languages: Mapping from relative path → language string

    Returns:
        DependencyGraph with nodes and edges populated
    """
    root_path = os.path.abspath(root_path)
    file_index = build_file_index(file_paths)

    edges: List[DependencyEdge] = []
    seen_edges: Set[tuple] = set()  # deduplicate
    nodes_set: Set[str] = set()

    for rel_path in file_paths:
        lang = file_languages.get(rel_path, "")
        if lang not in ("python", "javascript", "typescript"):
            continue

        full_path = os.path.join(root_path, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        raw_imports = extract_imports(lang, content)
        if not raw_imports:
            continue

        nodes_set.add(rel_path.replace("\\", "/"))

        for imp in raw_imports:
            result = resolve_import(imp, rel_path, file_index, lang)
            if result is None:
                continue

            resolved_path, confidence = result

            edge_key = (rel_path.replace("\\", "/"), resolved_path)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            nodes_set.add(resolved_path)
            edges.append(DependencyEdge(
                source=rel_path.replace("\\", "/"),
                target=resolved_path,
                type="import",
                language=lang,
                confidence=confidence,
            ))

    nodes = sorted(nodes_set)
    stats = DependencyGraphStats(
        total_edges=len(edges),
        unique_nodes=len(nodes),
    )

    return DependencyGraph(nodes=nodes, edges=edges, stats=stats)
