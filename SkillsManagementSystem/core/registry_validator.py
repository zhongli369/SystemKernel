"""
registry_validator.py — Registry Purity Validator (v1.0)

Validates that the skill registry is the SINGLE SOURCE OF TRUTH for skill metadata.

Checks:
  1. Schema conformity — every skill has required fields
  2. Duplicate detection — no skill defined in multiple packages
  3. Version consistency — semver format on all version fields
  4. Cross-reference integrity — packages reference skills that exist

Pure function. No side effects. No semantic analysis. No LLM.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Unified skill record schema (normative)
# ═══════════════════════════════════════════════════════════════════════════════

# Required fields for every skill in registry.json
REQUIRED_REGISTRY_SKILL_FIELDS = frozenset({
    "skill_id",
    "version",
    "category",
    "inputs",
    "outputs",
    "constraints",
    "deterministic",
    "source",
    "validator",
})

# Allowed values for closed-set fields
ALLOWED_SOURCES = frozenset({"core", "package", "external"})
ALLOWED_CATEGORIES = frozenset({
    "development", "analysis", "design", "office",
    "meta", "research", "algorithms", "art",
    "communication", "testing", "mobile", "ai",
    "game", "voice", "memory", "finance",
})


# ═══════════════════════════════════════════════════════════════════════════════
# Report types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RegistryIssue:
    """A single validation issue."""
    issue_type: str        # "missing_field" | "duplicate" | "version" | "cross_ref" | "schema"
    severity: str          # "CRITICAL" | "MEDIUM" | "LOW"
    location: str          # skill name or path
    detail: str            # human-readable description


@dataclass
class PurityReport:
    """Full registry purity validation report."""
    total_skills: int = 0
    total_packages: int = 0
    issues: list = field(default_factory=list)
    passed: bool = True

    def summary(self) -> str:
        criticals = sum(1 for i in self.issues if i.severity == "CRITICAL")
        mediums = sum(1 for i in self.issues if i.severity == "MEDIUM")
        lows = sum(1 for i in self.issues if i.severity == "LOW")
        status = "PASS" if self.passed else "FAIL"
        return (
            f"RegistryPurity: {status} | "
            f"skills={self.total_skills} pkgs={self.total_packages} | "
            f"CRITICAL={criticals} MEDIUM={mediums} LOW={lows}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Semver check
# ═══════════════════════════════════════════════════════════════════════════════

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _is_semver(version: str) -> bool:
    return bool(_SEMVER_RE.match(str(version)))


# ═══════════════════════════════════════════════════════════════════════════════
# Schema conformity check
# ═══════════════════════════════════════════════════════════════════════════════

def _check_schema_conformity(registry_data: dict) -> list[RegistryIssue]:
    """Check that every skill entry has all required fields."""
    issues = []
    skills = registry_data.get("skills", {})

    for skill_name, skill_meta in skills.items():
        if not isinstance(skill_meta, dict):
            issues.append(RegistryIssue(
                "schema", "CRITICAL", skill_name,
                f"Skill entry is not a dict: {type(skill_meta).__name__}"
            ))
            continue

        # Check required fields
        for field in REQUIRED_REGISTRY_SKILL_FIELDS:
            if field not in skill_meta:
                issues.append(RegistryIssue(
                    "missing_field", "MEDIUM", skill_name,
                    f"Missing required field '{field}' — will be filled by package manifest"
                ))

        # Check source is valid
        source = skill_meta.get("source", "")
        if source and source not in ALLOWED_SOURCES:
            issues.append(RegistryIssue(
                "schema", "MEDIUM", skill_name,
                f"Invalid source '{source}' — must be one of: {sorted(ALLOWED_SOURCES)}"
            ))

        # Check version format
        version = skill_meta.get("version", "")
        if version and not _is_semver(str(version)):
            issues.append(RegistryIssue(
                "version", "LOW", skill_name,
                f"Version '{version}' is not semver (x.y.z)"
            ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# Duplicate detection
# ═══════════════════════════════════════════════════════════════════════════════

def _check_duplicates(registry_data: dict) -> list[RegistryIssue]:
    """Check that no skill appears in multiple packages."""
    issues = []
    packages = registry_data.get("packages", {})
    skill_to_packages: dict[str, list[str]] = {}

    for pkg_name, pkg_meta in packages.items():
        pkg_skills = pkg_meta.get("skills", [])
        for skill_name in pkg_skills:
            if skill_name not in skill_to_packages:
                skill_to_packages[skill_name] = []
            skill_to_packages[skill_name].append(pkg_name)

    for skill_name, pkgs in skill_to_packages.items():
        if len(pkgs) > 1:
            issues.append(RegistryIssue(
                "duplicate", "CRITICAL", skill_name,
                f"Skill '{skill_name}' defined in multiple packages: {', '.join(pkgs)}"
            ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-reference integrity
# ═══════════════════════════════════════════════════════════════════════════════

def _check_cross_references(registry_data: dict) -> list[RegistryIssue]:
    """Check that packages reference skills that exist in the skills section."""
    issues = []
    skills = registry_data.get("skills", {})
    packages = registry_data.get("packages", {})

    registered_skills = set(skills.keys())

    for pkg_name, pkg_meta in packages.items():
        pkg_skills = pkg_meta.get("skills", [])
        for skill_name in pkg_skills:
            if skill_name not in registered_skills:
                issues.append(RegistryIssue(
                    "cross_ref", "MEDIUM", skill_name,
                    f"Package '{pkg_name}' references skill '{skill_name}' "
                    f"not found in registry skills section"
                ))

    # Reverse: skills referencing packages that don't exist
    for skill_name, skill_meta in skills.items():
        pkg_name = skill_meta.get("package", "")
        if pkg_name and pkg_name not in packages:
            issues.append(RegistryIssue(
                "cross_ref", "LOW", skill_name,
                f"Skill '{skill_name}' references package '{pkg_name}' "
                f"not found in registry packages section"
            ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# Hidden definition source detection
# ═══════════════════════════════════════════════════════════════════════════════

def _check_hidden_sources(registry_data: dict) -> list[RegistryIssue]:
    """Detect skills that may have hidden definition sources."""
    issues = []
    skills = registry_data.get("skills", {})

    for skill_name, skill_meta in skills.items():
        # Skills with minimal metadata may be defined elsewhere
        fields_present = sum(1 for f in REQUIRED_REGISTRY_SKILL_FIELDS if f in skill_meta)
        if fields_present < 3:
            issues.append(RegistryIssue(
                "schema", "LOW", skill_name,
                f"Skill has minimal registry metadata ({fields_present}/{len(REQUIRED_REGISTRY_SKILL_FIELDS)} fields) "
                f"— ensure all metadata is in SKILL.md frontmatter, not hardcoded in Python"
            ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# Main validator
# ═══════════════════════════════════════════════════════════════════════════════

def validate_registry(registry_data: dict) -> PurityReport:
    """Run all purity checks on the registry.

    Pure function. No disk I/O after data is loaded.

    Args:
        registry_data: Parsed registry.json dict.

    Returns:
        PurityReport with all issues and pass/fail status.
    """
    all_issues: list[RegistryIssue] = []

    # Run all checks
    all_issues.extend(_check_schema_conformity(registry_data))
    all_issues.extend(_check_duplicates(registry_data))
    all_issues.extend(_check_cross_references(registry_data))
    all_issues.extend(_check_hidden_sources(registry_data))

    # Sort by severity
    severity_order = {"CRITICAL": 0, "MEDIUM": 1, "LOW": 2}
    all_issues.sort(key=lambda i: (severity_order.get(i.severity, 9), i.location))

    # Pass if no CRITICAL issues
    has_critical = any(i.severity == "CRITICAL" for i in all_issues)

    skills = registry_data.get("skills", {})
    packages = registry_data.get("packages", {})

    return PurityReport(
        total_skills=len(skills),
        total_packages=len(packages),
        issues=all_issues,
        passed=not has_critical,
    )


def validate_registry_from_disk(registry_path: str = None) -> PurityReport:
    """Load registry.json from disk and validate.

    Args:
        registry_path: Path to registry.json. Uses default location if None.

    Returns:
        PurityReport.
    """
    if registry_path is None:
        registry_path = str(
            Path(__file__).resolve().parent.parent / "registry.json"
        )

    try:
        data = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        report = PurityReport()
        report.issues.append(RegistryIssue(
            "schema", "CRITICAL", registry_path,
            f"Cannot load registry: {e}"
        ))
        report.passed = False
        return report

    return validate_registry(data)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI — for testing / inspection
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    report = validate_registry_from_disk()

    print(report.summary())
    print()

    if report.issues:
        print(f"Issues found: {len(report.issues)}")
        for i in report.issues:
            print(f"  [{i.severity}] {i.issue_type}: {i.location} — {i.detail}")
    else:
        print("Registry is pure. No issues found.")

    sys.exit(0 if report.passed else 1)
