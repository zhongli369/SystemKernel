"""Connector to SkillSystem v4 via unified Adapter.

All routing goes through SkillsManagementSystem.core.adapter.resolve().
Single import path — no subprocess, no importlib, no per-call sys.path hacking.
"""

import sys
from pathlib import Path
from typing import Dict, List

# Workspace root: ensures SkillsManagementSystem is importable as a sibling package.
_WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from SkillsManagementSystem.core.adapter import (
    resolve, CapabilityRequest, get_registry_info, get_skill_metadata,
)

_client_instance = None


class SkillClient:
    """Connector to SkillSystem v4 via unified Adapter.

    All routing goes through adapter.resolve() — the single entrypoint.
    """

    def __init__(self):
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                resolve(CapabilityRequest(intent="", context=""))
                self._available = True
            except Exception:
                self._available = False
        return self._available

    def suggest(self, query: str) -> dict:
        """Query SkillSystem v4 for a skill suggestion."""
        if not query or not self.available:
            return {}
        try:
            binding = resolve(CapabilityRequest(intent="", context=query))
            return {
                "skill_id": binding.skill_id,
                "confidence": binding.confidence,
                "alternatives": list(binding.alternatives),
                "reason": binding.reason,
            }
        except Exception:
            return {}

    def suggest_skills(self, query: str) -> List[str]:
        """Return flat list of skill names for a query."""
        result = self.suggest(query)
        if not result or not result.get("skill_id"):
            return []
        skills = [result["skill_id"]]
        for alt in result.get("alternatives", []):
            if alt and alt not in skills:
                skills.append(alt)
        return skills

    def suggest_by_intent(self, intent: str, context: str) -> List[str]:
        """Suggest skills using intent + context via Adapter.

        This is the PREFERRED method. Uses adapter.INTENT_HINTS
        as the single source of truth for intent to query mapping.
        """
        if not self.available:
            return []
        try:
            binding = resolve(CapabilityRequest(
                intent=intent, context=context, source="repoanalyzer",
            ))
            if not binding.skill_id:
                return []
            skills = [binding.skill_id]
            for alt in binding.alternatives:
                if alt and alt not in skills:
                    skills.append(alt)
            return skills
        except Exception:
            return []

    def list_skills(self) -> List[str]:
        """Return list of all known skill names from the registry."""
        try:
            info = get_registry_info()
            return [s["name"] for s in info.get("all_skills", [])]
        except Exception:
            return []

    def get_skill_info(self, skill_name: str) -> dict:
        """Return metadata for a specific skill from the registry."""
        try:
            return get_skill_metadata(skill_name)
        except Exception:
            return {}


def get_skill_client() -> SkillClient:
    """Return the singleton SkillClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = SkillClient()
    return _client_instance
