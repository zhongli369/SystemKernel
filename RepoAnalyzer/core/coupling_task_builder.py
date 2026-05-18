"""Generate optimization tasks from coupling metrics.

All skill selection delegates to Adapter via skill_client.
No hardcoded skill names.
"""

from typing import Dict, List, Set

from core.model import AnalysisTask, TaskStep
from core.global_task_id import build_global_task_id
from core.skill_integration.skill_client import get_skill_client


def generate_coupling_tasks(
    coupling_metrics: dict,
    fan_stats: dict,
    criticality_map: Dict[str, float],
    skip_nodes: Set[str],
    repo_name: str = "",
) -> List[AnalysisTask]:
    """Generate tasks for high-coupling and low-cohesion nodes. Skills resolved via Adapter."""
    tasks: List[AnalysisTask] = []
    idx = 0
    client = get_skill_client()

    high_coupling = coupling_metrics.get("high_coupling_nodes", [])
    low_cohesion = coupling_metrics.get("low_cohesion_nodes", [])

    for nid in high_coupling:
        if nid in skip_nodes:
            continue

        fan = fan_stats.get(nid, {})
        fan_out = fan.get("fan_out", 0)
        intent = "decouple"

        idx += 1
        task_id = f"TASK-C{idx:03d}"
        tasks.append(AnalysisTask(
            task_id=task_id,
            global_task_id=build_global_task_id(repo_name, task_id),
            title=f"[DECOUPLE] Reduce coupling in: {nid}",
            type=intent,
            priority="P1",
            target_nodes=[nid],
            impact_score=0.0,
            risk_level="medium",
            reason=f"High coupling node with fan-out={fan_out}; depends on too many modules",
            steps=[
                TaskStep(
                    step_id=1,
                    description=f"Analyze {fan_out} direct dependencies for necessity",
                    suggested_skills=client.suggest_by_intent(
                        intent=intent,
                        context=f"Analyze {fan_out} direct dependencies for necessity {nid}",
                    ),
                    dependency_nodes=[nid],
                ),
                TaskStep(
                    step_id=2,
                    description="Extract intermediate abstraction to reduce direct fan-out",
                    suggested_skills=client.suggest_by_intent(
                        intent=intent,
                        context=f"Extract intermediate abstraction to reduce direct fan-out {nid}",
                    ),
                    dependency_nodes=[nid],
                ),
                TaskStep(
                    step_id=3,
                    description="Refactor dependents to use new abstraction",
                    suggested_skills=client.suggest_by_intent(
                        intent=intent,
                        context=f"Refactor dependents to use new abstraction {nid}",
                    ),
                    dependency_nodes=[nid],
                ),
            ],
        ))

    for nid in low_cohesion:
        if nid in skip_nodes:
            continue

        intent = "refactor"

        idx += 1
        task_id = f"TASK-C{idx:03d}"
        tasks.append(AnalysisTask(
            task_id=task_id,
            global_task_id=build_global_task_id(repo_name, task_id),
            title=f"[RESTRUCTURE] Improve cohesion in: {nid}",
            type=intent,
            priority="P2",
            target_nodes=[nid],
            impact_score=0.0,
            risk_level="low",
            reason="Low cohesion: dependencies span too many unrelated modules",
            steps=[
                TaskStep(
                    step_id=1,
                    description="Group related dependencies into cohesive modules",
                    suggested_skills=client.suggest_by_intent(
                        intent=intent,
                        context=f"Group related dependencies into cohesive modules {nid}",
                    ),
                    dependency_nodes=[nid],
                ),
                TaskStep(
                    step_id=2,
                    description="Move unrelated functionality to appropriate modules",
                    suggested_skills=client.suggest_by_intent(
                        intent=intent,
                        context=f"Move unrelated functionality to appropriate modules {nid}",
                    ),
                    dependency_nodes=[nid],
                ),
            ],
        ))

    return tasks
