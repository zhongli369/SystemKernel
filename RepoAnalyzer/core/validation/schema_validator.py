"""Enhanced Schema Validation (P1).

Validates task plan structure against expected schema:
  - Required field presence
  - Field type correctness
  - global_task_id format
  - skill_id format
  - Output envelope structure
  - Unknown field detection
"""

import re
from typing import List

from core.model import AnalysisTask
from core.validation.field_ownership import (
    ALL_KNOWN_FIELDS,
    FIELD_TYPES,
    REQUIRED_FIELDS,
    REPOANALYZER_FIELDS,
    SKILLSYSTEM_FIELDS,
)

# RA::<repo>::TASK-XXX format
_GLOBAL_TASK_ID_RE = re.compile(r"^RA::.+::TASK-[A-Z]\d{3}$")

# kebab-case skill names
_SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z][a-z0-9]*)*$")


def validate_task_schema(tasks: List[AnalysisTask]) -> List[dict]:
    """Validate each task's structure against expected schema."""
    violations: List[dict] = []

    for task in tasks:
        tid = task.task_id or "unknown"

        # Required field presence
        for field in REQUIRED_FIELDS:
            value = getattr(task, field, None)
            if value is None or (isinstance(value, (str, list, dict)) and not value):
                violations.append({
                    "type": "SCHEMA_DRIFT",
                    "module": "repoanalyzer",
                    "field": field,
                    "task_id": tid,
                    "issue": f"Required field '{field}' is missing or empty",
                    "severity": "error",
                })

        # Field type validation
        for field, expected_type in FIELD_TYPES.items():
            value = getattr(task, field, None)
            if value is None or (isinstance(value, str) and not value):
                continue  # empty defaults are OK for non-required fields

            if not isinstance(value, expected_type):
                violations.append({
                    "type": "FIELD_TYPE_MISMATCH",
                    "module": "repoanalyzer",
                    "field": field,
                    "task_id": tid,
                    "issue": (
                        f"Field '{field}' has type {type(value).__name__}, "
                        f"expected {getattr(expected_type, '__name__', str(expected_type))}"
                    ),
                    "severity": "error",
                })

        # global_task_id format
        gid = task.global_task_id
        if gid and not _GLOBAL_TASK_ID_RE.match(gid):
            violations.append({
                "type": "SCHEMA_DRIFT",
                "module": "repoanalyzer",
                "field": "global_task_id",
                "task_id": tid,
                "issue": (
                    f"global_task_id '{gid}' does not match "
                    f"RA::<repo>::TASK-XXX format"
                ),
                "severity": "error",
            })

        # skill_id format (when set)
        sid = task.skill_id
        if sid and not _SKILL_ID_RE.match(sid):
            violations.append({
                "type": "SCHEMA_DRIFT",
                "module": "skillsystem",
                "field": "skill_id",
                "task_id": tid,
                "issue": (
                    f"skill_id '{sid}' is not valid kebab-case"
                ),
                "severity": "warning",
            })

        # Unknown field detection — check dataclass fields against known set
        task_dict = _task_to_dict(task)
        unknown_fields = set(task_dict.keys()) - ALL_KNOWN_FIELDS
        for uf in unknown_fields:
            violations.append({
                "type": "SCHEMA_DRIFT",
                "module": "unknown",
                "field": uf,
                "task_id": tid,
                "issue": f"Unknown field '{uf}' found on task — possible schema drift",
                "severity": "warning",
            })

    return violations


def validate_output_envelope(data: dict) -> List[dict]:
    """Validate the output envelope structure."""
    violations: List[dict] = []

    if not isinstance(data, dict):
        return [{
            "type": "SCHEMA_DRIFT",
            "module": "repoanalyzer",
            "field": "envelope",
            "task_id": "*",
            "issue": "Output is not a dict",
            "severity": "error",
        }]

    # schema_version
    sv = data.get("schema_version", "")
    if sv != "repoanalyzer.v1":
        violations.append({
            "type": "SCHEMA_DRIFT",
            "module": "repoanalyzer",
            "field": "schema_version",
            "task_id": "*",
            "issue": f"schema_version '{sv}' is not 'repoanalyzer.v1'",
            "severity": "error",
        })

    # repo_id non-empty
    if not data.get("repo_id", ""):
        violations.append({
            "type": "SCHEMA_DRIFT",
            "module": "repoanalyzer",
            "field": "repo_id",
            "task_id": "*",
            "issue": "repo_id is empty",
            "severity": "error",
        })

    # phase is valid
    valid_phases = {"scan", "enrich", "graph", "analyze", "interpret", "insights", "plan"}
    phase = data.get("phase", "")
    if phase not in valid_phases:
        violations.append({
            "type": "SCHEMA_DRIFT",
            "module": "repoanalyzer",
            "field": "phase",
            "task_id": "*",
            "issue": f"phase '{phase}' is not one of {sorted(valid_phases)}",
            "severity": "error",
        })

    # generated_at present
    if not data.get("generated_at", ""):
        violations.append({
            "type": "SCHEMA_DRIFT",
            "module": "repoanalyzer",
            "field": "generated_at",
            "task_id": "*",
            "issue": "generated_at is empty",
            "severity": "warning",
        })

    return violations


def run_schema_validation(
    tasks: List[AnalysisTask],
    envelope_data: dict | None = None,
) -> dict:
    """Run all schema validation checks."""
    violations: List[dict] = []

    violations.extend(validate_task_schema(tasks))

    if envelope_data is not None:
        violations.extend(validate_output_envelope(envelope_data))

    errors = [v for v in violations if v["severity"] == "error"]
    return {
        "schema_valid": len(errors) == 0,
        "violations": violations,
    }


def _task_to_dict(task: AnalysisTask) -> dict:
    """Convert AnalysisTask to dict using dataclass fields (non-invasive)."""
    from dataclasses import fields
    result = {}
    for f in fields(task):
        result[f.name] = getattr(task, f.name)
    return result
