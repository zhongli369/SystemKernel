"""Non-executing skill suggestion mapper for task steps.

Delegates to unified Adapter (SkillsManagementSystem.core.adapter).
No local keyword matching — all routing logic lives in SkillSystem.
Single source of truth: adapter.INTENT_HINTS.
"""

from typing import Dict, List

from core.skill_integration.skill_client import get_skill_client


def suggest_skills(
    task_type: str,
    target_nodes: List[str],
    node_roles: Dict[str, str],
    node_system_roles: Dict[str, str],
) -> List[str]:
    """Suggest skills for a task step based on type and target node context.

    Delegates to unified Adapter via skill_client.
    All intents resolve through adapter.INTENT_HINTS (single source of truth).
    """
    client = get_skill_client()
    if not client.available:
        return []

    # Build context from node roles
    context_parts: List[str] = []
    for nid in target_nodes[:3]:
        role = node_roles.get(nid, "")
        sys_role = node_system_roles.get(nid, "")
        if role:
            context_parts.append(role)
        if sys_role:
            context_parts.append(sys_role)

    context = " ".join(context_parts) if context_parts else " ".join(target_nodes[:3])
    return client.suggest_by_intent(intent=task_type, context=context)
