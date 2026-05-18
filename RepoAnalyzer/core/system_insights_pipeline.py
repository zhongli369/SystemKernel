"""Phase 3 pipeline: System Intelligence Layer.

Orchestrates: load interpreted graph → detect bottlenecks →
classify architecture layers → compute coupling metrics →
generate health report → export system_insights.json
"""

import json
import os
from typing import Dict

from core.model import SystemInsights, FanInOut
from core.bottleneck_detector import detect_bottlenecks
from core.architecture_layering import classify_layers
from core.coupling_analyzer import compute_coupling
from core.system_health_reporter import generate_health_report
from core.output_contract import wrap_output, unwrap_output


def _build_fan_stats(fan_data: dict) -> Dict[str, FanInOut]:
    result: Dict[str, FanInOut] = {}
    for nid, fd in fan_data.items():
        result[nid] = FanInOut(
            fan_in=fd.get("fan_in", 0),
            fan_out=fd.get("fan_out", 0),
        )
    return result


def run_system_insights_pipeline(repo_path: str, output_dir: str) -> str:
    """Full Phase 3 pipeline.

    Reads output/interpreted_graph.json, produces output/system_insights.json.
    """
    input_path = os.path.join(output_dir, "interpreted_graph.json")

    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Interpreted graph not found: {input_path}. "
            f"Run 'python cli.py interpret {repo_path}' first."
        )

    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    nodes = data.get("nodes", [])
    adjacency = data.get("adjacency_list", {})
    fan_data = data.get("stats", {}).get("fan_stats", {})
    fan_stats = _build_fan_stats(fan_data)

    # 1. Detect bottlenecks
    bottlenecks = detect_bottlenecks(nodes, fan_stats, adjacency)

    # 2. Classify architecture layers
    arch_layers = classify_layers(nodes)

    # 3. Compute coupling metrics
    coupling = compute_coupling(nodes, fan_stats, adjacency)

    # 4. Generate health report
    health = generate_health_report(nodes, bottlenecks, coupling)

    insights = SystemInsights(
        bottlenecks=bottlenecks,
        architecture_layers=arch_layers,
        coupling_metrics=coupling,
        system_health=health,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "system_insights.json")

    repo_id = os.path.basename(os.path.abspath(repo_path))
    with open(output_path, "w", encoding="utf-8") as f:
        wrapped = wrap_output(repo_id, "insights", insights.to_dict())
        json.dump(wrapped, f, indent=2, ensure_ascii=False)

    return output_path
