#!/usr/bin/env python3
"""
profiles.py — Profile management for Skill Package Manager.

Usage:
    python scripts/profiles.py create-profile <name> --packages pkg1,pkg2 [--desc "..."]
    python scripts/profiles.py list-profiles
    python scripts/profiles.py load-profile <name>
    python scripts/profiles.py delete-profile <name>
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = SCRIPT_DIR / "registry.json"
DATA_DIR = SCRIPT_DIR / "data"
PROFILES_PATH = DATA_DIR / "profiles.json"

DEFAULT_PROFILES = {
    "version": "1.0.0",
    "active_profile": None,
    "profiles": {},
}


def load_registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_profiles():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PROFILES_PATH.exists():
        PROFILES_PATH.write_text(
            json.dumps(DEFAULT_PROFILES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("[INFO] Created default profiles.json")
        return dict(DEFAULT_PROFILES)
    try:
        return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] Corrupted profiles.json: {e}")
        sys.exit(1)


def save_profiles(data):
    tmp = str(PROFILES_PATH) + ".tmp"
    Path(tmp).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    Path(tmp).replace(PROFILES_PATH)


def create_profile(name, packages, description=""):
    registry = load_registry()
    valid_packages = set(registry.get("packages", {}).keys())

    # Validate all packages exist
    invalid = [p for p in packages if p not in valid_packages]
    if invalid:
        print(f"[WARN] Unknown packages: {', '.join(invalid)}")
        print(f"       Available: {', '.join(sorted(valid_packages))}")

    profiles = load_profiles()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    profiles["profiles"][name] = {
        "description": description,
        "packages": packages,
        "created": now,
        "updated": now,
    }
    save_profiles(profiles)
    print(f"[INFO] Profile created: {name} ({len(packages)} packages)")


def list_profiles():
    profiles = load_profiles()
    if not profiles["profiles"]:
        print("[INFO] No profiles found")
        return
    print(f"=== Profiles ({len(profiles['profiles'])} total) ===")
    active = profiles.get("active_profile")
    for name, p in profiles["profiles"].items():
        marker = " *active*" if name == active else ""
        pkgs = ", ".join(p["packages"])
        desc = f" — {p['description']}" if p.get("description") else ""
        print(f"  {name}{marker}{desc}")
        print(f"    packages: {pkgs}")
        print(f"    updated:  {p.get('updated', '?')}")


def load_profile(name):
    profiles = load_profiles()
    if name not in profiles["profiles"]:
        print(f"[ERROR] Profile '{name}' does not exist")
        return

    registry = load_registry()
    profile = profiles["profiles"][name]
    profiles["active_profile"] = name
    save_profiles(profiles)

    print(f"[INFO] Loading profile: {name}")
    if profile.get("description"):
        print(f"       {profile['description']}")

    actions = []
    for pkg in profile["packages"]:
        pkg_data = registry.get("packages", {}).get(pkg, {})
        install_cmd = pkg_data.get("install_command", f"install {pkg}")
        status = "installed" if pkg in registry.get("packages", {}) else "unknown"

        print(f"  {pkg:12s} — {status}")
        if status != "installed":
            actions.append(install_cmd)

    if actions:
        print(f"\n[INFO] Run these commands to install missing packages:")
        for cmd in actions:
            print(f"  $ {cmd}")
    else:
        print(f"[INFO] All packages are available. No installation needed.")


def delete_profile(name):
    profiles = load_profiles()
    if name not in profiles["profiles"]:
        print(f"[ERROR] Profile '{name}' does not exist")
        return
    del profiles["profiles"][name]
    if profiles["active_profile"] == name:
        profiles["active_profile"] = None
        print(f"[INFO] Cleared active profile")
    save_profiles(profiles)
    print(f"[INFO] Profile deleted: {name}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/profiles.py <command> [options]", file=sys.stderr)
        print("  create-profile <name> --packages pkg1,pkg2 [--desc ...]", file=sys.stderr)
        print("  list-profiles", file=sys.stderr)
        print("  load-profile <name>", file=sys.stderr)
        print("  delete-profile <name>", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "create-profile":
        if len(sys.argv) < 3:
            print("[ERROR] create-profile requires a name", file=sys.stderr)
            sys.exit(1)
        name = sys.argv[2]
        packages = []
        description = ""
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == "--packages" and i + 1 < len(args):
                packages = [p.strip() for p in args[i + 1].split(",") if p.strip()]
                i += 2
            elif args[i] == "--desc" and i + 1 < len(args):
                description = args[i + 1]
                i += 2
            else:
                i += 1
        if not packages:
            print("[ERROR] --packages is required (comma-separated list)", file=sys.stderr)
            sys.exit(1)
        create_profile(name, packages, description)

    elif cmd == "list-profiles":
        list_profiles()

    elif cmd == "load-profile":
        if len(sys.argv) < 3:
            print("[ERROR] load-profile requires a name", file=sys.stderr)
            sys.exit(1)
        load_profile(sys.argv[2])

    elif cmd == "delete-profile":
        if len(sys.argv) < 3:
            print("[ERROR] delete-profile requires a name", file=sys.stderr)
            sys.exit(1)
        delete_profile(sys.argv[2])

    else:
        print(f"[ERROR] Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
