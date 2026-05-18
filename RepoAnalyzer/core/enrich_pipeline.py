"""Enrichment pipeline — integrates Phase 1 output with Phase 1.5 semantic layer."""

import json
import os
from typing import List

from core.model import FileEntry, FolderEntry, RepoStats, RepoStructure
from core.role_classifier import classify_file_role
from core.entrypoint_detector import detect_entrypoints, identify_primary_entrypoint, is_entrypoint
from core.importance_scorer import compute_importance
from core.tag_generator import generate_tags
from core.output_contract import wrap_output, unwrap_output


def load_repo_structure(input_path: str) -> RepoStructure:
    """Load a Phase 1 repo_map.json and reconstruct a RepoStructure object."""
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    files = [FileEntry(**f) for f in data.get("files", [])]
    folders = [FolderEntry(**f) for f in data.get("folders", [])]
    stats_data = data.get("stats", {})
    stats = RepoStats(
        total_files=stats_data.get("total_files", 0),
        total_folders=stats_data.get("total_folders", 0),
        language_distribution=stats_data.get("language_distribution", {}),
    )

    return RepoStructure(
        repo_name=data.get("repo_name", ""),
        root_path=data.get("root_path", ""),
        files=files,
        folders=folders,
        stats=stats,
    )


def enrich(structure: RepoStructure) -> RepoStructure:
    """Enrich a RepoStructure with Phase 1.5 semantic annotations."""
    # Detect entry points
    entrypoints = detect_entrypoints(structure.files)
    primary_ep = identify_primary_entrypoint(entrypoints)

    for f in structure.files:
        f.role = classify_file_role(f.path, f.name)
        f.is_entrypoint = is_entrypoint(f.name)
        f.importance_score = compute_importance(f.role, f.is_entrypoint, f.path, f.name)
        f.tags = generate_tags(f.language, f.role, f.is_entrypoint, f.path, f.name)

    return structure


def run_enrich_pipeline(repo_path: str, output_dir: str) -> str:
    """Full Phase 1.5 pipeline: load → enrich → output.

    Reads output/repo_map.json from the scan output directory,
    enriches it, and writes output/repo_map_enriched.json.

    Returns the path to the enriched output file.
    """
    input_path = os.path.join(output_dir, "repo_map.json")

    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Phase 1 output not found: {input_path}. "
            f"Run 'python cli.py scan {repo_path}' first."
        )

    structure = load_repo_structure(input_path)
    structure = enrich(structure)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "repo_map_enriched.json")

    repo_id = os.path.basename(os.path.abspath(repo_path))
    with open(output_path, "w", encoding="utf-8") as f:
        wrapped = wrap_output(repo_id, "enrich", structure.to_dict())
        json.dump(wrapped, f, indent=2, ensure_ascii=False)

    return output_path
