"""Phase 2-A pipeline: Import Dependency Extraction.

Orchestrates: load enriched repo map → extract imports → resolve paths →
build dependency graph → output dependency_edges.json
"""

import json
import os
from typing import Dict, List

from core.dependency_builder import build_dependency_graph
from core.output_contract import wrap_output, unwrap_output


def load_file_list(repo_map_path: str):
    """Load the enriched repo_map JSON and extract file metadata."""
    with open(repo_map_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    file_paths: List[str] = []
    file_languages: Dict[str, str] = {}

    for f in data.get("files", []):
        path = f["path"]
        file_paths.append(path)
        file_languages[path] = f.get("language", "")

    root_path = data.get("root_path", "")
    return root_path, file_paths, file_languages


def run_dependency_pipeline(repo_path: str, output_dir: str) -> str:
    """Full Phase 2-A pipeline.

    Reads output/repo_map_enriched.json, builds dependency graph,
    writes output/dependency_edges.json.

    Returns the path to the output file.
    """
    input_path = os.path.join(output_dir, "repo_map_enriched.json")

    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Enriched repo map not found: {input_path}. "
            f"Run 'python cli.py enrich {repo_path}' first."
        )

    root_path, file_paths, file_languages = load_file_list(input_path)

    graph = build_dependency_graph(root_path, file_paths, file_languages)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "dependency_edges.json")

    repo_id = os.path.basename(os.path.abspath(repo_path))
    with open(output_path, "w", encoding="utf-8") as f:
        wrapped = wrap_output(repo_id, "graph", graph.to_dict())
        json.dump(wrapped, f, indent=2, ensure_ascii=False)

    return output_path
