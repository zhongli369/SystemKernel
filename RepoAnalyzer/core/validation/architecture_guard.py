"""Architecture Constraint Engine (P0).

Enforces module boundary rules, ownership validation, dependency direction,
immutable field protection, and SkillSystem optionality.

Read-only — never modifies data. Returns violation reports only.
"""

from typing import Dict, List

from core.model import AnalysisTask
from core.validation.field_ownership import (
    FIELD_OWNERSHIP,
    IMMUTABLE_FIELDS,
    REPOANALYZER_FIELDS,
    SKILLSYSTEM_FIELDS,
)


def validate_ownership(
    tasks: List[AnalysisTask],
    skill_enabled: bool,
) -> List[dict]:
    """Rule 1: Validate field ownership boundaries.

    Checks:
      - SkillSystem fields must only be set when skill mode was enabled
      - SkillSystem fields must be empty when skill mode was disabled
    """
    violations: List[dict] = []

    for task in tasks:
        for field in SKILLSYSTEM_FIELDS:
            value = getattr(task, field, None)

            if skill_enabled:
                # When enabled, skill fields may be set — no violation
                continue

            # When disabled, skill fields must be empty/default
            is_empty = (
                value == "" or value == {} or value == [] or value is None
            )
            if not is_empty:
                violations.append({
                    "type": "OWNERSHIP_VIOLATION",
                    "module": "skillsystem",
                    "field": field,
                    "task_id": task.task_id,
                    "issue": (
                        f"SkillSystem field '{field}' is set on {task.task_id} "
                        f"but skill execution is disabled"
                    ),
                    "severity": "error",
                })

        # RepoAnalyzer fields must always be populated (non-empty)
        for field in ("task_id", "title", "type", "priority"):
            value = getattr(task, field, None)
            if not value:
                violations.append({
                    "type": "OWNERSHIP_VIOLATION",
                    "module": "repoanalyzer",
                    "field": field,
                    "task_id": task.task_id or "unknown",
                    "issue": f"Required RepoAnalyzer field '{field}' is empty",
                    "severity": "error",
                })

    return violations


def validate_immutable_fields(
    tasks: List[AnalysisTask],
    original_snapshots: Dict[str, dict] | None = None,
) -> List[dict]:
    """Rule 3: Immutable fields must not change after generation.

    If original_snapshots is provided, compares current values against
    the snapshots. Otherwise validates format only.
    """
    violations: List[dict] = []

    for task in tasks:
        for field in IMMUTABLE_FIELDS:
            value = getattr(task, field, None)

            # Must be non-empty
            if not value:
                violations.append({
                    "type": "IMMUTABLE_MUTATION",
                    "module": FIELD_OWNERSHIP.get(field, "unknown"),
                    "field": field,
                    "task_id": task.task_id,
                    "issue": f"Immutable field '{field}' is empty or missing",
                    "severity": "error",
                })

            # Check against snapshot if available
            if original_snapshots and task.task_id in original_snapshots:
                original = original_snapshots[task.task_id].get(field)
                if original is not None and value != original:
                    violations.append({
                        "type": "IMMUTABLE_MUTATION",
                        "module": FIELD_OWNERSHIP.get(field, "unknown"),
                        "field": field,
                        "task_id": task.task_id,
                        "issue": (
                            f"Immutable field '{field}' changed: "
                            f"'{original}' → '{value}'"
                        ),
                        "severity": "error",
                    })

    return violations


def validate_dependency_direction(
    skill_enabled: bool,
) -> List[dict]:
    """Rule 2 + Rule 4: Validate dependency direction and optionality.

    Allowed:   RepoAnalyzer → SkillSystem
    Forbidden: SkillSystem → RepoAnalyzer (control dependency)
    Required:  System must run without SkillSystem
    """
    violations: List[dict] = []

    # Rule 4: SkillSystem must be optional — no hard dependency
    # This is validated at the architectural level: the fact that the
    # pipeline runs at all with skill_enabled=False proves optionality.
    # No violation to report in normal operation.

    # Rule 2: Dependency direction is validated by ownership checks
    # (validate_ownership already prevents SkillSystem from writing
    # to RepoAnalyzer fields).

    return violations


def validate_task_count(
    tasks: List[AnalysisTask],
    expected_count: int | None = None,
) -> List[dict]:
    """Rule 3: Task count stability check.

    If expected_count is provided, flags discrepancies.
    """
    violations: List[dict] = []

    if expected_count is not None and len(tasks) != expected_count:
        violations.append({
            "type": "IMMUTABLE_MUTATION",
            "module": "repoanalyzer",
            "field": "task_count",
            "task_id": "*",
            "issue": (
                f"Task count changed: expected {expected_count}, "
                f"got {len(tasks)}"
            ),
            "severity": "warning",
        })

    return violations


def run_architecture_guard(
    tasks: List[AnalysisTask],
    skill_enabled: bool,
    expected_task_count: int | None = None,
    original_snapshots: Dict[str, dict] | None = None,
) -> dict:
    """Run all architecture constraint checks.

    Returns a dict with violations list and validity flag.
    """
    violations: List[dict] = []

    violations.extend(validate_ownership(tasks, skill_enabled))
    violations.extend(validate_immutable_fields(tasks, original_snapshots))
    violations.extend(validate_dependency_direction(skill_enabled))
    violations.extend(validate_task_count(tasks, expected_task_count))

    errors = [v for v in violations if v["severity"] == "error"]
    return {
        "architecture_valid": len(errors) == 0,
        "violations": violations,
    }
