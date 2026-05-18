#!/usr/bin/env python3
"""
health.py — System health check for Skill Package Manager.

Usage:
    python scripts/health.py health-check [--json]
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = SCRIPT_DIR / "registry.json"
PACKAGES_DIR = SCRIPT_DIR / "packages"


def load_registry():
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[ERROR] Cannot load registry.json: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Registry Health
# ---------------------------------------------------------------------------

def check_registry_health(registry):
    issues = []

    # Required top-level keys
    for key in ["packages", "skills", "sources", "indexes", "shared"]:
        if key not in registry:
            issues.append({"severity": "error", "msg": f"Missing top-level key: {key}"})

    if "version" not in registry:
        issues.append({"severity": "error", "msg": "Missing registry version field"})

    # Validate each package entry
    for pkg_name, pkg in registry.get("packages", {}).items():
        for field in ["display_name", "version", "installable", "skills"]:
            if field not in pkg:
                issues.append({"severity": "warn", "msg": f"Package '{pkg_name}' missing '{field}'"})

    # Validate each skill entry
    for skill_name, skill in registry.get("skills", {}).items():
        for field in ["version", "description", "package"]:
            if field not in skill:
                issues.append({"severity": "warn", "msg": f"Skill '{skill_name}' missing '{field}'"})

        # Cross-reference: skill's package must exist
        pkg_ref = skill.get("package")
        if pkg_ref and pkg_ref not in registry.get("packages", {}):
            issues.append({"severity": "error", "msg": f"Skill '{skill_name}' references unknown package '{pkg_ref}'"})

    # Cross-reference: package skills must exist in registry.skills
    for pkg_name, pkg in registry.get("packages", {}).items():
        for skill_name in pkg.get("skills", []):
            if skill_name not in registry.get("skills", {}):
                issues.append({"severity": "warn", "msg": f"Package '{pkg_name}' lists skill '{skill_name}' not in registry.skills"})

    return issues


# ---------------------------------------------------------------------------
# Manifest Health
# ---------------------------------------------------------------------------

def check_manifest_health(registry):
    issues = []

    for pkg_name, pkg in registry.get("packages", {}).items():
        if pkg.get("external"):
            manifest_path = PACKAGES_DIR / pkg_name / "manifest.json"
            if not manifest_path.exists():
                issues.append({"severity": "warn", "msg": f"External package '{pkg_name}' has no manifest.json"})
                continue
            else:
                # External packages don't need to match local conventions
                pass

        manifest_path = PACKAGES_DIR / pkg_name / "manifest.json"
        if not manifest_path.exists():
            issues.append({"severity": "error", "msg": f"Package '{pkg_name}' has no manifest.json"})
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            issues.append({"severity": "error", "msg": f"Manifest for '{pkg_name}' is invalid JSON: {e}"})
            continue

        # Name consistency
        if manifest.get("name") != pkg_name:
            issues.append({"severity": "warn", "msg": f"Manifest name '{manifest.get('name')}' != directory '{pkg_name}'"})

        # Skills list consistency
        man_skills = set(manifest.get("skills", []))
        reg_skills = set(pkg.get("skills", []))
        if man_skills != reg_skills:
            only_man = man_skills - reg_skills
            only_reg = reg_skills - man_skills
            if only_man:
                issues.append({"severity": "warn", "msg": f"Package '{pkg_name}': manifest has skills not in registry: {sorted(only_man)}"})
            if only_reg:
                issues.append({"severity": "warn", "msg": f"Package '{pkg_name}': registry has skills not in manifest: {sorted(only_reg)}"})

        # Installable consistency
        if manifest.get("installable") != pkg.get("installable", True):
            issues.append({"severity": "warn", "msg": f"Package '{pkg_name}': manifest installable={manifest.get('installable')} != registry installable={pkg.get('installable', True)}"})

    return issues


# ---------------------------------------------------------------------------
# Duplicate Detection
# ---------------------------------------------------------------------------

def check_duplicates(registry):
    issues = []

    # Check for skills appearing in multiple packages
    skill_packages = {}
    for pkg_name, pkg in registry.get("packages", {}).items():
        for skill_name in pkg.get("skills", []):
            if skill_name not in skill_packages:
                skill_packages[skill_name] = []
            skill_packages[skill_name].append(pkg_name)

    for skill_name, pkgs in skill_packages.items():
        if len(pkgs) > 1:
            issues.append({"severity": "error", "msg": f"Skill '{skill_name}' claimed by multiple packages: {pkgs}"})

    # Package name duplicates (not possible in dict, but check display_names)
    display_names = {}
    for pkg_name, pkg in registry.get("packages", {}).items():
        dn = pkg.get("display_name", pkg_name)
        if dn not in display_names:
            display_names[dn] = []
        display_names[dn].append(pkg_name)

    for dn, pkgs in display_names.items():
        if len(pkgs) > 1:
            issues.append({"severity": "warn", "msg": f"Duplicate display_name '{dn}': {pkgs}"})

    return issues


# ---------------------------------------------------------------------------
# Orphan Detection
# ---------------------------------------------------------------------------

def check_orphans(registry):
    issues = []

    # Skills whose package doesn't exist
    for skill_name, skill in registry.get("skills", {}).items():
        pkg = skill.get("package", "")
        if pkg and pkg not in registry.get("packages", {}):
            issues.append({"severity": "error", "msg": f"Orphan skill '{skill_name}' — package '{pkg}' not found"})
        elif not pkg:
            issues.append({"severity": "warn", "msg": f"Skill '{skill_name}' has no package reference"})

    # Packages with no corresponding directory
    for pkg_name in registry.get("packages", {}):
        pkg_dir = PACKAGES_DIR / pkg_name
        if not pkg_dir.exists() and not registry["packages"][pkg_name].get("external"):
            issues.append({"severity": "warn", "msg": f"Package '{pkg_name}' has no local directory"})

    # Skills in registry.skills but not in any package skills list
    all_pkg_skills = set()
    for pkg in registry.get("packages", {}).values():
        all_pkg_skills.update(pkg.get("skills", []))
    for skill_name in registry.get("skills", {}):
        if skill_name not in all_pkg_skills:
            issues.append({"severity": "warn", "msg": f"Skill '{skill_name}' in registry.skills but not listed in any package"})

    # Empty packages
    for pkg_name, pkg in registry.get("packages", {}).items():
        if not pkg.get("skills"):
            issues.append({"severity": "info", "msg": f"Package '{pkg_name}' has no skills"})

    return issues


# ---------------------------------------------------------------------------
# Package Source Validation
# ---------------------------------------------------------------------------

def check_invalid_sources(registry):
    issues = []

    for pkg_name, pkg in registry.get("packages", {}).items():
        external = pkg.get("external", False)
        install_cmd = pkg.get("install_command", "")

        if not install_cmd:
            issues.append({"severity": "warn", "msg": f"Package '{pkg_name}' has no install_command"})
        elif external and install_cmd.startswith("install "):
            issues.append({"severity": "info", "msg": f"External package '{pkg_name}' uses local install_command: {install_cmd}"})

    # Shared dependencies resolution
    for skill_name, skill in registry.get("skills", {}).items():
        for dep in skill.get("shared_dependencies", []):
            dep_key = dep.replace("shared/", "")
            if dep_key not in registry.get("shared", {}):
                issues.append({"severity": "warn", "msg": f"Skill '{skill_name}' depends on unresolved shared: {dep}"})

    return issues


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_health_check():
    registry = load_registry()

    sections = {
        "registry": check_registry_health(registry),
        "manifest": check_manifest_health(registry),
        "duplicates": check_duplicates(registry),
        "orphans": check_orphans(registry),
        "sources": check_invalid_sources(registry),
    }

    results = {}
    total_errors = 0
    total_warnings = 0
    total_info = 0

    for section_name, issues in sections.items():
        errors = sum(1 for i in issues if i["severity"] == "error")
        warnings = sum(1 for i in issues if i["severity"] == "warn")
        infos = sum(1 for i in issues if i["severity"] == "info")
        results[section_name] = {
            "passed": errors == 0,
            "issues": issues,
            "counts": {"errors": errors, "warnings": warnings, "info": infos},
        }
        total_errors += errors
        total_warnings += warnings
        total_info += infos

    return {
        "passed": total_errors == 0,
        "sections": results,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "total_info": total_info,
    }


def format_report(result):
    section_labels = {
        "registry": "Registry Health",
        "manifest": "Manifest Health",
        "duplicates": "Duplicate Detection",
        "orphans": "Orphan Skills Detection",
        "sources": "Package Source Validation",
    }

    lines = []
    total_checks = 0
    passed_checks = 0

    for section_key, label in section_labels.items():
        section = result["sections"][section_key]
        total_checks += 1
        if section["passed"]:
            passed_checks += 1

        lines.append(f"=== {label} ===")
        if not section["issues"]:
            lines.append("[PASS] No issues found")
        for issue in section["issues"]:
            tag = {"error": "FAIL", "warn": "WARN", "info": "INFO"}[issue["severity"]]
            lines.append(f"[{tag}] {issue['msg']}")
        lines.append("")

    lines.append("=== Final Status ===")
    lines.append(f"  Checks passed: {passed_checks}/{total_checks}")
    lines.append(f"  Errors:        {result['total_errors']}")
    lines.append(f"  Warnings:      {result['total_warnings']}")
    lines.append(f"  Info:          {result['total_info']}")
    lines.append(f"  Overall:       {'HEALTHY' if result['passed'] else 'UNHEALTHY'}")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "health-check":
        print("Usage: python scripts/health.py health-check [--json]", file=sys.stderr)
        sys.exit(1)

    use_json = "--json" in sys.argv
    result = run_health_check()

    if use_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_report(result))

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
