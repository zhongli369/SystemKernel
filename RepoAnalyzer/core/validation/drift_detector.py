"""Drift Detection System (P1).

Detects structural changes between pipeline runs:
  - Unexpected field additions/removals
  - Cross-module field usage changes
  - Silent coupling increase (SkillSystem dependency growth)
  - Task count stability

Uses baseline fingerprinting: saves a snapshot of expected field set
and compares subsequent runs against it.
"""

import json
import os
from dataclasses import fields
from typing import Dict, List

from core.model import AnalysisTask
from core.validation.field_ownership import (
    ALL_KNOWN_FIELDS,
    SKILLSYSTEM_FIELDS,
)


def save_baseline(tasks: List[AnalysisTask], baseline_path: str) -> dict:
    """Save field fingerprint to a baseline file for future drift detection.

    Captures: field names, types, task count, skill field distribution.
    """
    task_count = len(tasks)
    field_set: Dict[str, str] = {}

    for task in tasks:
        for f in fields(task):
            value = getattr(task, f.name)
            type_name = type(value).__name__
            if f.name not in field_set:
                field_set[f.name] = type_name

    # Count tasks with skill bindings
    skill_bound = sum(1 for t in tasks if t.skill_id)

    baseline = {
        "baseline_version": "repoanalyzer.drift.v1",
        "task_count": task_count,
        "field_set": field_set,
        "skill_bound_tasks": skill_bound,
        "skill_bound_ratio": round(skill_bound / task_count, 3) if task_count else 0.0,
        "known_fields": sorted(ALL_KNOWN_FIELDS),
    }

    os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)

    return baseline


def load_baseline(baseline_path: str) -> dict:
    """Load a previously saved baseline, or return empty dict."""
    if not os.path.exists(baseline_path):
        return {}
    try:
        with open(baseline_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def detect_drift(
    tasks: List[AnalysisTask],
    baseline: dict | None = None,
) -> List[dict]:
    """Compare current tasks against baseline to detect structural drift.

    Detects:
      - New fields added since baseline
      - Fields removed since baseline
      - Field type changes
    """
    violations: List[dict] = []

    if not baseline:
        return violations

    baseline_fields: Dict[str, str] = baseline.get("field_set", {})
    baseline_count = baseline.get("task_count", 0)

    # Build current field set
    current_fields: Dict[str, str] = {}
    for task in tasks:
        for f in fields(task):
            value = getattr(task, f.name)
            current_fields[f.name] = type(value).__name__

    # New fields added
    new_fields = set(current_fields) - set(baseline_fields)
    for nf in new_fields:
        violations.append({
            "type": "SCHEMA_DRIFT",
            "module": "unknown",
            "field": nf,
            "task_id": "*",
            "issue": (
                f"New field '{nf}' (type: {current_fields[nf]}) "
                f"appeared since baseline — possible schema drift"
            ),
            "severity": "warning",
        })

    # Fields removed
    removed_fields = set(baseline_fields) - set(current_fields)
    for rf in removed_fields:
        violations.append({
            "type": "SCHEMA_DRIFT",
            "module": "unknown",
            "field": rf,
            "task_id": "*",
            "issue": (
                f"Field '{rf}' present in baseline is missing "
                f"in current output — possible schema regression"
            ),
            "severity": "warning",
        })

    # Field type changes
    for field in set(baseline_fields) & set(current_fields):
        if baseline_fields[field] != current_fields[field]:
            violations.append({
                "type": "FIELD_TYPE_MISMATCH",
                "module": "unknown",
                "field": field,
                "task_id": "*",
                "issue": (
                    f"Field '{field}' type changed: "
                    f"{baseline_fields[field]} → {current_fields[field]}"
                ),
                "severity": "error",
            })

    # Task count change
    current_count = len(tasks)
    if baseline_count and current_count != baseline_count:
        violations.append({
            "type": "IMMUTABLE_MUTATION",
            "module": "repoanalyzer",
            "field": "task_count",
            "task_id": "*",
            "issue": (
                f"Task count changed: {baseline_count} → {current_count}"
            ),
            "severity": "warning",
        })

    return violations


def detect_coupling_increase(
    tasks: List[AnalysisTask],
    previous_skill_ratio: float | None = None,
) -> List[dict]:
    """Detect increased coupling to SkillSystem.

    Flags when the proportion of skill-bound tasks increases
    beyond a threshold relative to a previous baseline.
    """
    violations: List[dict] = []

    if previous_skill_ratio is None:
        return violations

    task_count = len(tasks)
    if not task_count:
        return violations

    skill_bound = sum(1 for t in tasks if t.skill_id)
    current_ratio = skill_bound / task_count

    # Flag if skill dependency grew by more than 20%
    if previous_skill_ratio > 0 and current_ratio > previous_skill_ratio * 1.2:
        violations.append({
            "type": "COUPLING_INCREASE",
            "module": "skillsystem",
            "field": "skill_id",
            "task_id": "*",
            "issue": (
                f"SkillSystem coupling increased: "
                f"{previous_skill_ratio:.1%} → {current_ratio:.1%} "
                f"of tasks have skill bindings"
            ),
            "severity": "warning",
        })

    return violations


def run_drift_detection(
    tasks: List[AnalysisTask],
    baseline_path: str | None = None,
    previous_skill_ratio: float | None = None,
) -> dict:
    """Run all drift detection checks.

    If baseline_path is provided, loads baseline and compares.
    If baseline doesn't exist yet, saves one for future comparison.
    """
    violations: List[dict] = []

    if baseline_path:
        baseline = load_baseline(baseline_path)
        if baseline:
            violations.extend(detect_drift(tasks, baseline))
            prev_ratio = baseline.get("skill_bound_ratio")
            if prev_ratio is not None:
                violations.extend(detect_coupling_increase(tasks, prev_ratio))
        else:
            # First run — save baseline, no violations
            save_baseline(tasks, baseline_path)

    if previous_skill_ratio is not None:
        violations.extend(detect_coupling_increase(tasks, previous_skill_ratio))

    errors = [v for v in violations if v["severity"] == "error"]
    return {
        "drift_detected": len(violations) > 0,
        "violations": violations,
    }
