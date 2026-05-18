"""Convert Phase 3 bottlenecks into actionable tasks.

All skill selection delegates to Adapter via skill_client.
No hardcoded skill names.
"""

from typing import Dict, List

from core.model import AnalysisTask, TaskStep
from core.global_task_id import build_global_task_id
from core.skill_integration.skill_client import get_skill_client


def _bottleneck_type_to_intent(btype: str) -> str:
    """Map bottleneck type to Adapter intent."""
    return {
        "primary": "refactor",
        "orchestration": "decouple",
        "system_critical": "stabilize",
    }.get(btype, "refactor")


def _step_descriptions(btype: str) -> list:
    """Return step descriptions for each bottleneck type (skills resolved at generation time)."""
    return {
        "primary": [
            "Audit all dependents for tight coupling to this node",
            "Design interface/abstraction layer to reduce direct dependency",
            "Incrementally migrate dependents to new interface",
        ],
        "orchestration": [
            "Map orchestration flow and identify redundant dependencies",
            "Consolidate or split orchestrator to reduce fan-out",
            "Simplify pipeline steps where possible",
        ],
        "system_critical": [
            "Add error handling and fallback at entry point",
            "Reduce direct dependency count via facade pattern",
            "Add integration tests for critical path",
        ],
    }.get(btype, [
        "Analyze node dependencies",
        "Evaluate refactoring options",
    ])


def generate_bottleneck_tasks(bottlenecks: list, repo_name: str = "") -> List[AnalysisTask]:
    """Generate tasks from bottleneck list. Skills resolved via Adapter."""
    tasks: List[AnalysisTask] = []
    priority_map = {"critical": "P0", "high": "P1", "medium": "P2"}
    client = get_skill_client()

    for i, b in enumerate(bottlenecks):
        btype = b.bottleneck_type
        intent = _bottleneck_type_to_intent(btype)
        descs = _step_descriptions(btype)

        steps = []
        for j, desc in enumerate(descs):
            context = f"{desc} {b.node_id}"
            suggested = client.suggest_by_intent(intent=intent, context=context)
            steps.append(TaskStep(
                step_id=j + 1,
                description=desc,
                suggested_skills=suggested,
                dependency_nodes=[b.node_id],
            ))

        severity = b.severity
        task_id = f"TASK-B{i + 1:03d}"
        tasks.append(AnalysisTask(
            task_id=task_id,
            global_task_id=build_global_task_id(repo_name, task_id),
            title=f"[{btype.upper()}] Refactor bottleneck: {b.node_id}",
            type=intent,
            priority=priority_map.get(severity, "P2"),
            target_nodes=[b.node_id],
            impact_score=0.0,
            risk_level=severity,
            reason=b.reason,
            steps=steps,
        ))

    return tasks
