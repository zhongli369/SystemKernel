"""Field ownership registry — single source of truth for module boundaries.

Defines which system owns each AnalysisTask field. Used by
architecture_guard.py to detect cross-module boundary violations.

Ownership domains:
  - repoanalyzer: fields generated and managed by RepoAnalyzer core
  - skillsystem:  fields set by SkillSystem v4 binding layer
  - validation:   no data fields (reports only)
"""

from typing import Dict, Set

# Which system OWNS each AnalysisTask field
FIELD_OWNERSHIP: Dict[str, str] = {
    # RepoAnalyzer core — set during task generation (Phase 4 generators)
    "task_id": "repoanalyzer",
    "title": "repoanalyzer",
    "type": "repoanalyzer",
    "priority": "repoanalyzer",
    "target_nodes": "repoanalyzer",
    "impact_score": "repoanalyzer",
    "risk_level": "repoanalyzer",
    "reason": "repoanalyzer",
    "steps": "repoanalyzer",
    "depends_on": "repoanalyzer",
    "global_task_id": "repoanalyzer",
    # SkillSystem v4 — set by skill_executor.bind_skill()
    "skill_id": "skillsystem",
    "skill_input": "skillsystem",
    "skill_output": "skillsystem",
}

# Fields that MUST NOT be mutated after initial generation
IMMUTABLE_FIELDS: Set[str] = {"task_id", "global_task_id"}

# Pre-computed domain sets
REPOANALYZER_FIELDS: Set[str] = {k for k, v in FIELD_OWNERSHIP.items() if v == "repoanalyzer"}
SKILLSYSTEM_FIELDS: Set[str] = {k for k, v in FIELD_OWNERSHIP.items() if v == "skillsystem"}

# Required fields every task must have (non-empty)
REQUIRED_FIELDS: Set[str] = {"task_id", "title", "type", "priority", "target_nodes"}

# Expected field types
FIELD_TYPES: Dict[str, type] = {
    "task_id": str,
    "title": str,
    "type": str,
    "priority": str,
    "target_nodes": list,
    "impact_score": (float, int),
    "risk_level": str,
    "reason": str,
    "steps": list,
    "depends_on": list,
    "global_task_id": str,
    "skill_id": str,
    "skill_input": dict,
    "skill_output": dict,
}

# All known fields (for drift detection)
ALL_KNOWN_FIELDS: Set[str] = set(FIELD_OWNERSHIP.keys())
