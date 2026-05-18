"""Map AnalysisTask → skill_id via unified Adapter.

Delegates to SkillsManagementSystem.core.adapter.resolve().
Single source of truth: adapter.INTENT_HINTS.
"""

from core.model import AnalysisTask
from core.skill_integration.skill_client import get_skill_client


def resolve_skill(task: AnalysisTask) -> str:
    """Resolve the best skill_id for an AnalysisTask.

    Returns a skill name string, or empty string if no match.
    """
    if task.skill_id:
        return task.skill_id

    client = get_skill_client()
    if not client.available:
        return ""

    # Build context from task metadata
    context = f"{task.title} {task.reason} {' '.join(task.target_nodes[:3])}"

    skills = client.suggest_by_intent(intent=task.type, context=context)
    return skills[0] if skills else ""


def resolve_input(task: AnalysisTask) -> dict:
    """Build a skill_input schema from the task's steps and metadata."""
    return {
        "task_id": task.task_id,
        "global_task_id": task.global_task_id,
        "title": task.title,
        "type": task.type,
        "priority": task.priority,
        "target_nodes": task.target_nodes,
        "reason": task.reason,
        "steps": [
            {
                "step_id": s.step_id,
                "description": s.description,
                "dependency_nodes": s.dependency_nodes,
            }
            for s in task.steps
        ],
    }


def validate_skill_compatibility(task: AnalysisTask, skill_id: str) -> bool:
    """Check whether a skill is compatible with the task type and context."""
    if not skill_id:
        return False

    client = get_skill_client()
    if not client.available:
        return False

    # Verify skill exists in registry
    info = client.get_skill_info(skill_id)
    if not info:
        return False

    # Verify skill appears in suggestions for this task type + context
    context = f"{task.title} {task.reason}"
    skills = client.suggest_by_intent(intent=task.type, context=context)
    return skill_id in skills
