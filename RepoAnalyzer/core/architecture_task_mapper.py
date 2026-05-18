"""Map architecture layers to task types and priorities.

All skill selection delegates to Adapter via skill_client.
No hardcoded skill names — LAYER_TASK_CONFIG only holds step descriptions.
"""

from typing import Dict, List, Set

from core.model import AnalysisTask, TaskStep
from core.global_task_id import build_global_task_id
from core.skill_integration.skill_client import get_skill_client

LAYER_TASK_CONFIG = {
    "entry_layer": {
        "type": "stabilize",
        "priority": "P0",
        "reason_tpl": "Entry point '{nid}': stabilize with error handling, logging, and tests",
        "steps": [
            "Add comprehensive error handling at entry point",
            "Add structured logging for observability",
            "Add smoke/integration tests for critical paths",
        ],
    },
    "orchestration_layer": {
        "type": "optimize",
        "priority": "P1",
        "reason_tpl": "Orchestrator '{nid}': simplify pipeline, reduce dependency count",
        "steps": [
            "Audit orchestration flow for redundant steps",
            "Consolidate pipeline stages where possible",
            "Add pipeline monitoring and failure recovery",
        ],
    },
    "core_layer": {
        "type": "refactor",
        "priority": "P1",
        "reason_tpl": "Core module '{nid}': ensure clear interfaces, reduce coupling",
        "steps": [
            "Define explicit public interface for this module",
            "Add type annotations and docstrings",
            "Review and reduce cross-module imports",
        ],
    },
    "utility_layer": {
        "type": "cleanup",
        "priority": "P2",
        "reason_tpl": "Utility module '{nid}': review necessity, deduplicate, document",
        "steps": [
            "Audit utility usage across codebase",
            "Deduplicate redundant utility functions",
        ],
    },
    "leaf_layer": {
        "type": "cleanup",
        "priority": "P2",
        "reason_tpl": "Leaf module '{nid}': verify it belongs, consider consolidation",
        "steps": [
            "Verify module is still needed",
            "Consider consolidating with related modules",
        ],
    },
}


def generate_architecture_tasks(
    architecture_layers: dict,
    criticality_map: Dict[str, float],
    fan_stats: dict,
    skip_nodes: Set[str],
    repo_name: str = "",
) -> List[AnalysisTask]:
    """Generate tasks for each architecture layer. Skills resolved via Adapter."""
    tasks: List[AnalysisTask] = []
    task_counter = 0
    client = get_skill_client()

    layer_order = ["entry_layer", "orchestration_layer", "core_layer", "utility_layer", "leaf_layer"]

    for layer_name in layer_order:
        nodes = architecture_layers.get(layer_name, [])
        if not nodes:
            continue

        config = LAYER_TASK_CONFIG.get(layer_name)
        if config is None:
            continue

        intent = config["type"]

        if layer_name in ("entry_layer", "orchestration_layer"):
            batch_size = 1
        else:
            batch_size = 3

        for i in range(0, len(nodes), batch_size):
            batch = [n for n in nodes[i:i + batch_size] if n not in skip_nodes]
            if not batch:
                continue

            task_counter += 1
            primary = batch[0]

            steps = []
            for j, desc in enumerate(config["steps"]):
                context = f"{desc} {primary}"
                suggested = client.suggest_by_intent(intent=intent, context=context)
                steps.append(TaskStep(
                    step_id=j + 1,
                    description=desc,
                    suggested_skills=suggested,
                    dependency_nodes=batch,
                ))

            title_target = primary if len(batch) == 1 else f"{primary} +{len(batch) - 1}"
            task_id = f"TASK-A{task_counter:03d}"
            tasks.append(AnalysisTask(
                task_id=task_id,
                global_task_id=build_global_task_id(repo_name, task_id),
                title=f"[{intent.upper()}] {layer_name}: {title_target}",
                type=intent,
                priority=config["priority"],
                target_nodes=list(batch),
                impact_score=0.0,
                risk_level="medium" if layer_name in ("entry_layer", "orchestration_layer") else "low",
                reason=config["reason_tpl"].format(nid=primary),
                steps=steps,
            ))

    return tasks
