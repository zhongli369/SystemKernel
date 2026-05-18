#!/usr/bin/env python3
"""
register.py — Dynamic Skill Registration CLI for Skill Package Manager.

Registers a new skill into the ecosystem with three modes:

  Mode 1 — Direct:   python register.py <skill_path> --package <name>
  Mode 2 — Auto:     python register.py <skill_path> --auto
  Mode 3 — New pkg:  python register.py <skill_path> --auto  (auto-creates package
                      if classification confidence is low)

For each mode the tool:
  1. Validates the skill (SKILL.md required)
  2. Checks for name conflicts in registry
  3. Ensures the target package exists
  4. Copies the skill into the package
  5. Generates / updates metadata
  6. Updates manifest.json
  7. Updates registry.json
  8. Logs every step

Architecture invariant: Skills live inside packages only. Registry stores
package-level entries; skill-level entries reference their parent package.
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap — locate system root
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGES_DIR = SCRIPT_DIR / "packages"
REGISTRY_PATH = SCRIPT_DIR / "registry.json"

# Import sibling modules
sys.path.insert(0, str(SCRIPT_DIR))
from classify import classify_skill, parse_skill_md
from package_builder import create_package as pkg_create


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_registry():
    if not REGISTRY_PATH.exists():
        return {}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(registry):
    registry["last_updated"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_manifest(pkg_name):
    manifest_path = PACKAGES_DIR / pkg_name / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def save_manifest(pkg_name, manifest):
    manifest_path = PACKAGES_DIR / pkg_name / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_skill(skill_path):
    """Validate a skill directory has the required structure.

    Returns (True, skill_name, parsed_data) or (False, error_message, None).
    """
    skill_path = Path(skill_path).resolve()
    if not skill_path.is_dir():
        return False, f"Not a directory: {skill_path}", None

    md_path = skill_path / "SKILL.md"
    if not md_path.exists():
        return False, f"No SKILL.md found in {skill_path}", None

    parsed = parse_skill_md(skill_path)
    skill_name = parsed.get("name") or skill_path.name
    return True, skill_name, parsed


def check_name_conflict(skill_name, registry):
    """Check if skill name already exists in registry."""
    if skill_name in registry.get("skills", {}):
        existing = registry["skills"][skill_name]
        return True, f"Skill '{skill_name}' already registered in package '{existing.get('package', '?')}'"
    return False, None


def check_package_exists(pkg_name):
    """Check if a package exists."""
    manifest_path = PACKAGES_DIR / pkg_name / "manifest.json"
    if not manifest_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("installable", False):
        return False
    return True


# ---------------------------------------------------------------------------
# Metadata generation
# ---------------------------------------------------------------------------

def generate_metadata(skill_name, parsed_data):
    """Generate registry metadata for a skill from its SKILL.md."""
    desc = parsed_data.get("description", f"{skill_name} skill")
    # Truncate description to a reasonable length
    if len(desc) > 300:
        desc = desc[:297] + "..."

    metadata = {
        "version": "1.0.0",
        "description": desc,
        "package": None,  # filled in by caller
        "shared_dependencies": [],
    }

    # Preserve external flag if present
    if parsed_data.get("external"):
        metadata["external"] = True

    return metadata


# ---------------------------------------------------------------------------
# File copy
# ---------------------------------------------------------------------------

def copy_skill(skill_path, dest_dir, skill_name=None):
    """Copy skill directory to destination, renaming to skill_name if provided.
    Returns (True, dest_path) or (False, error)."""
    dest_dir = Path(dest_dir)
    target_name = skill_name or Path(skill_path).name
    dest_path = dest_dir / target_name

    if dest_path.exists():
        return False, f"Destination already exists: {dest_path}"

    try:
        shutil.copytree(str(skill_path), str(dest_path))
    except OSError as e:
        return False, f"Copy failed: {e}"

    return True, dest_path


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_add(path):
    """Stage a path with git add if git is available. Non-fatal on failure."""
    import subprocess

    try:
        repo_root = SCRIPT_DIR
        subprocess.run(
            ["git", "add", str(Path(path).relative_to(repo_root))],
            cwd=str(repo_root),
            capture_output=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Core registration
# ---------------------------------------------------------------------------

def register_skill(skill_path, pkg_name=None, auto=False, dry_run=False):
    """Register a skill into the ecosystem.

    Args:
        skill_path: Path to skill directory
        pkg_name: Target package (None when using --auto)
        auto: Auto-classify to find best package
        dry_run: Preview mode

    Returns:
        dict with status, steps performed, and details
    """
    log = []
    steps = []

    # ---- Step 1: Validate skill --------------------------------------------
    valid, result, parsed = validate_skill(skill_path)
    if not valid:
        log.append(f"[FAIL] {result}")
        return {"success": False, "error": result, "log": log}
    skill_name = result
    log.append(f"[OK]   Skill validated: {skill_name}")
    steps.append("validate")

    # ---- Step 2: Check name conflict ---------------------------------------
    registry = load_registry()
    conflict, msg = check_name_conflict(skill_name, registry)
    if conflict:
        log.append(f"[FAIL] {msg}")
        return {"success": False, "error": msg, "log": log}
    log.append(f"[OK]   No name conflict for '{skill_name}'")
    steps.append("check_conflict")

    # ---- Step 3: Determine target package ----------------------------------
    if auto:
        log.append(f"[...]  Auto-classifying skill...")
        classification = classify_skill(str(skill_path))
        best = classification["package"]
        confidence = classification["confidence"]
        severity = classification["severity"]
        matched = classification.get("matched_keywords", [])

        if best is None or severity == "low" or (confidence < 0.25):
            # Mode 3: Create new package for this skill
            log.append(
                f"[...]  Classification uncertain (conf={confidence:.2f}). "
                f"Creating new package."
            )
            pkg_name = skill_name.replace("_", "-").replace(" ", "-")
            if not dry_run:
                pkg_result = pkg_create(
                    pkg_name,
                    description=parsed.get("description", f"Package for {skill_name}"),
                    tags=[],
                    keywords=matched or [skill_name],
                )
                if not pkg_result["success"]:
                    log.append(f"[FAIL] Package creation failed: {pkg_result['error']}")
                    return {
                        "success": False,
                        "error": pkg_result["error"],
                        "log": log,
                    }
            log.append(f"[OK]   Created new package: {pkg_name}")
            steps.append("create_package")
        else:
            pkg_name = best
            log.append(
                f"[OK]   Auto-classified → '{pkg_name}' "
                f"(confidence: {confidence:.2f}, keywords: {matched})"
            )
            steps.append("auto_classify")

    elif pkg_name is None:
        log.append(
            "[FAIL] Must specify --package <name> or --auto"
        )
        return {
            "success": False,
            "error": "No target package specified",
            "log": log,
        }

    if dry_run:
        log.append(f"[DRY]  Would copy {skill_path} → {PACKAGES_DIR / pkg_name / 'skills' / skill_name}")
        log.append(f"[DRY]  Would update manifest.json for '{pkg_name}'")
        log.append(f"[DRY]  Would update registry.json")
        return {
            "success": True,
            "dry_run": True,
            "skill": skill_name,
            "package": pkg_name,
            "log": log,
        }

    # ---- Step 4: Validate package ------------------------------------------
    if not check_package_exists(pkg_name):
        log.append(f"[FAIL] Package '{pkg_name}' not found or not installable")
        return {
            "success": False,
            "error": f"Package '{pkg_name}' does not exist",
            "log": log,
        }
    log.append(f"[OK]   Target package validated: {pkg_name}")
    steps.append("validate_package")

    # ---- Step 5: Copy skill into package -----------------------------------
    dest_dir = PACKAGES_DIR / pkg_name / "skills"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ok, result = copy_skill(skill_path, dest_dir, skill_name=skill_name)
    if not ok:
        log.append(f"[FAIL] {result}")
        return {"success": False, "error": result, "log": log}
    dest_path = Path(result)
    log.append(f"[OK]   Copied skill to {dest_path}")
    steps.append("copy")

    # ---- Step 6: Update manifest.json --------------------------------------
    manifest = load_manifest(pkg_name)
    if manifest is None:
        manifest = {
            "name": pkg_name,
            "version": "1.0.0",
            "installable": True,
            "tags": [],
            "dependencies": [],
            "skills": [],
            "auto_match_keywords": [],
        }
    if skill_name not in manifest.setdefault("skills", []):
        manifest["skills"].append(skill_name)
    save_manifest(pkg_name, manifest)
    log.append(f"[OK]   Updated manifest.json for '{pkg_name}'")
    steps.append("update_manifest")

    # ---- Step 7: Update registry.json --------------------------------------
    if "skills" not in registry:
        registry["skills"] = {}
    metadata = generate_metadata(skill_name, parsed)
    metadata["package"] = pkg_name
    registry["skills"][skill_name] = metadata

    # Also update the packages list in registry
    if pkg_name in registry.get("packages", {}):
        pkg_skills = registry["packages"][pkg_name].setdefault("skills", [])
        if skill_name not in pkg_skills:
            pkg_skills.append(skill_name)

    save_registry(registry)
    log.append(f"[OK]   Updated registry.json")
    steps.append("update_registry")

    # ---- Step 8: Git add (best-effort) -------------------------------------
    if git_add(dest_path):
        log.append(f"[OK]   Git add: {dest_path.name}")
    git_add(PACKAGES_DIR / pkg_name / "manifest.json")
    git_add(REGISTRY_PATH)
    steps.append("git_add")

    log.append(f"[DONE] Skill '{skill_name}' registered to package '{pkg_name}'")
    return {
        "success": True,
        "skill": skill_name,
        "package": pkg_name,
        "path": str(dest_path),
        "steps": steps,
        "log": log,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python register.py <skill_path> [--package NAME | --auto] [--dry-run]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Modes:", file=sys.stderr)
        print("  --package NAME   Register skill to a specific package", file=sys.stderr)
        print("  --auto           Auto-classify and register to best package", file=sys.stderr)
        print("  --dry-run        Preview without making changes", file=sys.stderr)
        sys.exit(1)

    skill_path = sys.argv[1]
    pkg_name = None
    auto = False
    dry_run = False

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--package" and i + 1 < len(sys.argv):
            pkg_name = sys.argv[i + 1]
            i += 2
        elif arg == "--auto":
            auto = True
            i += 1
        elif arg == "--dry-run":
            dry_run = True
            i += 1
        else:
            i += 1

    result = register_skill(
        skill_path,
        pkg_name=pkg_name,
        auto=auto,
        dry_run=dry_run,
    )

    # Print log
    for line in result.get("log", []):
        print(f"  {line}")

    if dry_run:
        return

    if result["success"]:
        print(f"\n  Registration complete.")
        print(f"  Skill:   {result['skill']}")
        print(f"  Package: {result['package']}")
        print(f"  Path:    {result['path']}")
        print(f"  Steps:   {' → '.join(result['steps'])}")
    else:
        print(f"\n  Registration FAILED: {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
