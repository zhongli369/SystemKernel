"""Architecture Constraint Layer — read-only validation for RepoAnalyzer.

Orchestrates: architecture guard → schema validation → drift detection
→ returns unified ValidationReport.

NEVER modifies data. Only inspects and reports.

Usage:
    from core.validation import run_validation

    report = run_validation(
        tasks=all_tasks,
        repo_name="RepoAnalyzer",
        skill_enabled=False,
        mode="soft",
    )
    # report["architecture_valid"]  → bool
    # report["schema_valid"]        → bool
    # report["violations"]          → list of violation dicts
    # report["system_health_score"] → 0-100
"""

import os
import sys
from typing import List

from core.model import AnalysisTask
from core.validation.architecture_guard import run_architecture_guard
from core.validation.schema_validator import run_schema_validation
from core.validation.drift_detector import run_drift_detection


class ArchitectureViolationError(RuntimeError):
    """Raised in strict mode when architecture violations are found."""
    pass


def _compute_health_score(
    arch_result: dict,
    schema_result: dict,
    drift_result: dict,
) -> int:
    """Compute a system health score from all validation results.

    Starts at 100, deducts for each violation severity.
    """
    score = 100
    all_violations = (
        arch_result.get("violations", []) +
        schema_result.get("violations", []) +
        drift_result.get("violations", [])
    )
    for v in all_violations:
        if v["severity"] == "error":
            score -= 5
        elif v["severity"] == "warning":
            score -= 2

    return max(0, score)


def run_validation(
    tasks: List[AnalysisTask],
    repo_name: str = "",
    skill_enabled: bool = False,
    mode: str = "soft",
    expected_task_count: int | None = None,
    baseline_path: str | None = None,
    envelope_data: dict | None = None,
) -> dict:
    """Run all architecture constraint checks.

    Args:
        tasks: List of AnalysisTask objects to validate.
        repo_name: Repository name for context.
        skill_enabled: Whether SkillSystem binding mode was active.
        mode: 'soft' (log only), 'strict' (raise on violation), 'off' (skip).
        expected_task_count: Expected number of tasks (for stability check).
        baseline_path: Path to drift baseline file.
        envelope_data: Output envelope dict for schema validation.

    Returns:
        ValidationReport dict with schema_valid, architecture_valid,
        drift_detected, violations, warnings, system_health_score.

    Raises:
        ArchitectureViolationError: In strict mode with violations.
    """
    if mode == "off":
        return {
            "schema_valid": True,
            "architecture_valid": True,
            "drift_detected": False,
            "violations": [],
            "warnings": [],
            "system_health_score": 100,
            "mode": "off",
        }

    # Run all three validators
    arch_result = run_architecture_guard(
        tasks, skill_enabled, expected_task_count,
    )
    schema_result = run_schema_validation(tasks, envelope_data)
    drift_result = run_drift_detection(tasks, baseline_path)

    # Merge results
    all_violations = (
        arch_result["violations"] +
        schema_result["violations"] +
        drift_result["violations"]
    )

    # Split into errors and warnings
    errors = [v for v in all_violations if v["severity"] == "error"]
    warnings_list = [v for v in all_violations if v["severity"] == "warning"]

    health_score = _compute_health_score(arch_result, schema_result, drift_result)

    report = {
        "schema_valid": schema_result["schema_valid"],
        "architecture_valid": arch_result["architecture_valid"],
        "drift_detected": drift_result["drift_detected"],
        "violations": errors,
        "warnings": warnings_list,
        "system_health_score": health_score,
        "mode": mode,
    }

    # Emit report
    _emit_validation_report(report)

    # Strict mode — fail on violations
    if mode == "strict" and errors:
        raise ArchitectureViolationError(
            f"Architecture violations found ({len(errors)} errors, "
            f"{len(warnings_list)} warnings). Health score: {health_score}/100"
        )

    return report


def _emit_validation_report(report: dict) -> None:
    """Output validation report to stderr."""
    total_issues = len(report["violations"]) + len(report["warnings"])
    if total_issues == 0:
        return

    lines = [
        f"\n[VALIDATION] Architecture Guard — {report['mode']} mode",
        f"  Schema valid: {report['schema_valid']}",
        f"  Architecture valid: {report['architecture_valid']}",
        f"  Drift detected: {report['drift_detected']}",
        f"  Health score: {report['system_health_score']}/100",
    ]

    if report["violations"]:
        lines.append(f"  Violations ({len(report['violations'])}):")
        for v in report["violations"]:
            lines.append(f"    [{v['type']}] {v['field']}: {v['issue']}")

    if report["warnings"]:
        lines.append(f"  Warnings ({len(report['warnings'])}):")
        for w in report["warnings"]:
            lines.append(f"    [{w['type']}] {w['field']}: {w['issue']}")

    for line in lines:
        print(line, file=sys.stderr)
