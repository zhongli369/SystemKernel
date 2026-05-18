"""Skill binding layer for AnalysisTask.

"Execution" here means binding — resolving the best skill and attaching
skill_id, skill_input, and skill_output metadata to the task.

SkillSystem v4 has no execution runtime; actual skill execution is
Claude's responsibility. This layer provides the structured binding
that downstream systems (TaskSystem, Claude) can act on.
"""

import os

from core.model import AnalysisTask
from core.skill_integration.skill_resolver import (
    resolve_skill,
    resolve_input,
    validate_skill_compatibility,
)


def _execution_enabled() -> bool:
    """Check whether skill binding mode is enabled."""
    return os.environ.get("REPOANALYZER_SKILL_EXECUTION_ENABLED", "").lower() in (
        "1", "true", "yes",
    )


def bind_skill(task: AnalysisTask) -> dict:
    """Resolve skill for a task and attach skill_id + skill_input.

    Does nothing if skill execution is disabled or no skill resolved.
    Returns binding result dict for audit/logging.
    """
    if not _execution_enabled():
        return {"status": "disabled", "task_id": task.task_id}

    skill_id = resolve_skill(task)
    if not skill_id:
        return {"status": "unresolved", "task_id": task.task_id}

    skill_input = resolve_input(task)

    task.skill_id = skill_id
    task.skill_input = skill_input
    task.skill_output = {
        "binding_status": "resolved",
        "skill_id": skill_id,
        "method": "skill_resolver_fallback_chain",
    }

    return {
        "status": "bound",
        "task_id": task.task_id,
        "skill_id": skill_id,
        "skill_input": skill_input,
    }


def execute_skill_binding(task: AnalysisTask) -> dict:
    """Full binding with validation step.

    Same as bind_skill() but additionally validates compatibility
    before attaching.
    """
    if not _execution_enabled():
        return {"status": "disabled", "task_id": task.task_id}

    skill_id = resolve_skill(task)
    if not skill_id:
        return {"status": "unresolved", "task_id": task.task_id}

    if not validate_skill_compatibility(task, skill_id):
        return {"status": "incompatible", "task_id": task.task_id, "skill_id": skill_id}

    skill_input = resolve_input(task)

    task.skill_id = skill_id
    task.skill_input = skill_input
    task.skill_output = {
        "binding_status": "validated",
        "skill_id": skill_id,
        "method": "skill_resolver_fallback_chain",
    }

    return {
        "status": "bound",
        "task_id": task.task_id,
        "skill_id": skill_id,
        "skill_input": skill_input,
    }
