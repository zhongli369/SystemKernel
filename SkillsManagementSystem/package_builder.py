#!/usr/bin/env python3
"""
package_builder.py — Create new packages in the Skill Package Manager.

Creates a fully registered, installable package with proper directory
structure and manifest. Registers the package in registry.json.

Usage:
    python package_builder.py <package_name>
    python package_builder.py <package_name> --description "..."
    python package_builder.py <package_name> --tags "tag1,tag2" --keywords "kw1,kw2"
    python package_builder.py <package_name> --dry-run
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGES_DIR = SCRIPT_DIR / "packages"
REGISTRY_PATH = SCRIPT_DIR / "registry.json"
MANIFEST_TEMPLATE = {
    "name": "",
    "display_name": "",
    "display_name_en": "",
    "description": "",
    "version": "1.0.0",
    "installable": True,
    "tags": [],
    "dependencies": [],
    "skills": [],
    "auto_match_keywords": [],
}


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


# ---------------------------------------------------------------------------
# Package creation
# ---------------------------------------------------------------------------

def create_package(name, description="", tags=None, keywords=None, dry_run=False):
    """Create a new package with full structure and registry entry.

    Args:
        name: Package name (kebab-case recommended)
        description: Human-readable description
        tags: List of tags
        keywords: List of auto-match keywords
        dry_run: If True, print what would happen without doing it

    Returns:
        dict with status and details
    """
    name = name.strip().lower().replace(" ", "-")

    # Validate
    if not name:
        return {"success": False, "error": "Package name is required"}

    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        return {
            "success": False,
            "error": f"Invalid package name '{name}'. Use lowercase letters, digits, and hyphens only.",
        }

    # Check for duplicate
    pkg_dir = PACKAGES_DIR / name
    if pkg_dir.exists():
        return {
            "success": False,
            "error": f"Package '{name}' already exists at {pkg_dir}",
        }

    # Check registry duplicate
    registry = load_registry()
    if name in registry.get("packages", {}):
        return {
            "success": False,
            "error": f"Package '{name}' already registered in registry.json",
        }

    manifest = dict(MANIFEST_TEMPLATE)
    manifest["name"] = name
    manifest["description"] = description or f"{name} skill package"
    manifest["tags"] = tags or []
    manifest["auto_match_keywords"] = keywords or [name]

    registry_entry = {
        "display_name": name,
        "display_name_en": f"{name.title()} Skills Pack",
        "description": description or f"{name} skill package",
        "version": "1.0.0",
        "installable": True,
        "install_command": f"install {name}",
        "skills": [],
    }

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "package": name,
            "manifest": manifest,
            "registry_entry": registry_entry,
            "paths": [str(pkg_dir), str(pkg_dir / "manifest.json"), str(pkg_dir / "skills")],
        }

    # Create directory structure
    pkg_dir.mkdir(parents=True, exist_ok=False)
    skills_dir = pkg_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=False)

    # Write manifest.json
    manifest_path = pkg_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Update registry.json
    if "packages" not in registry:
        registry["packages"] = {}
    registry["packages"][name] = registry_entry
    save_registry(registry)

    return {
        "success": True,
        "package": name,
        "manifest_path": str(manifest_path),
        "skills_dir": str(skills_dir),
        "manifest": manifest,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

import re


def main():
    if len(sys.argv) < 2:
        print("Usage: python package_builder.py <package_name> [options]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  --description TEXT   Package description", file=sys.stderr)
        print("  --tags TAG1,TAG2     Comma-separated tags", file=sys.stderr)
        print("  --keywords KW1,KW2   Comma-separated auto-match keywords", file=sys.stderr)
        print("  --dry-run            Preview without creating", file=sys.stderr)
        sys.exit(1)

    name = sys.argv[1]
    description = ""
    tags = []
    keywords = []
    dry_run = False

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--description" and i + 1 < len(sys.argv):
            description = sys.argv[i + 1]
            i += 2
        elif arg == "--tags" and i + 1 < len(sys.argv):
            tags = [t.strip() for t in sys.argv[i + 1].split(",") if t.strip()]
            i += 2
        elif arg == "--keywords" and i + 1 < len(sys.argv):
            keywords = [k.strip() for k in sys.argv[i + 1].split(",") if k.strip()]
            i += 2
        elif arg == "--dry-run":
            dry_run = True
            i += 1
        else:
            i += 1

    result = create_package(name, description, tags, keywords, dry_run)

    if dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if not result["success"]:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"  Package '{result['package']}' created successfully")
    print(f"  Manifest:  {result['manifest_path']}")
    print(f"  Skills:    {result['skills_dir']}")
    print(f"  Registry:  updated")


if __name__ == "__main__":
    main()
