#!/usr/bin/env python3
"""
snapshots.py — System state snapshots for Skill Package Manager.

Usage:
    python scripts/snapshots.py snapshot-save [--label "..."]
    python scripts/snapshots.py snapshot-list
    python scripts/snapshots.py snapshot-load <filename>
    python scripts/snapshots.py snapshot-delete <filename>
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = SCRIPT_DIR / "registry.json"
SNAPSHOTS_DIR = SCRIPT_DIR / "snapshots"
INDEX_PATH = SNAPSHOTS_DIR / "index.json"


def load_registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_index():
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text(
            json.dumps({"entries": []}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return {"entries": []}
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] Corrupted snapshots index.json: {e}")
        sys.exit(1)


def save_index(idx):
    tmp = str(INDEX_PATH) + ".tmp"
    Path(tmp).write_text(
        json.dumps(idx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    Path(tmp).replace(INDEX_PATH)


def snapshot_save(label=""):
    registry = load_registry()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    filename = f"snapshot_{ts.replace(':', '-')}.json"
    filepath = SNAPSHOTS_DIR / filename

    snapshot = {
        "version": "1.0.0",
        "timestamp": ts,
        "label": label,
        "registry_version": registry.get("version", "unknown"),
        "packages": {},
        "skills": {},
        "total_packages": len(registry.get("packages", {})),
        "total_skills": len(registry.get("skills", {})),
    }

    for pkg_name, pkg in registry.get("packages", {}).items():
        snapshot["packages"][pkg_name] = {
            "display_name": pkg.get("display_name", pkg_name),
            "version": pkg.get("version", "?"),
            "skills": list(pkg.get("skills", [])),
        }

    for skill_name, skill in registry.get("skills", {}).items():
        snapshot["skills"][skill_name] = {
            "version": skill.get("version", "?"),
            "package": skill.get("package", "?"),
            "description": skill.get("description", "")[:200],
        }

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    idx = load_index()
    idx["entries"].append({
        "filename": filename,
        "timestamp": ts,
        "label": label,
        "packages": snapshot["total_packages"],
        "skills": snapshot["total_skills"],
    })
    save_index(idx)

    print(f"[INFO] Snapshot saved: {filename}")
    print(f"       Packages: {snapshot['total_packages']}, Skills: {snapshot['total_skills']}")
    return {"filename": filename, "timestamp": ts}


def snapshot_list():
    idx = load_index()
    if not idx["entries"]:
        print("[INFO] No snapshots found")
        return
    print(f"=== Snapshots ({len(idx['entries'])} total) ===")
    for entry in reversed(idx["entries"]):
        label = f" — {entry['label']}" if entry.get("label") else ""
        print(f"  {entry['filename']}{label}")
        print(f"    {entry['timestamp']}  |  {entry['packages']} packages, {entry['skills']} skills")


def snapshot_load(filename):
    filepath = SNAPSHOTS_DIR / filename
    if not filepath.exists():
        print(f"[ERROR] Snapshot not found: {filename}")
        return

    try:
        snap = json.loads(filepath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] Corrupted snapshot: {e}")
        return

    registry = load_registry()
    current_pkgs = set(registry.get("packages", {}).keys())
    snap_pkgs = set(snap.get("packages", {}).keys())
    current_skills = set(registry.get("skills", {}).keys())
    snap_skills = set(snap.get("skills", {}).keys())

    added_pkgs = current_pkgs - snap_pkgs
    removed_pkgs = snap_pkgs - current_pkgs
    added_skills = current_skills - snap_skills
    removed_skills = snap_skills - current_skills

    print(f"=== Snapshot: {filename} ===")
    print(f"  Timestamp: {snap.get('timestamp', '?')}")
    print(f"  Registry version: {snap.get('registry_version', '?')}")
    print(f"  Current packages: {len(current_pkgs)}, Snapshot packages: {len(snap_pkgs)}")
    print(f"  Current skills:   {len(current_skills)}, Snapshot skills:   {len(snap_skills)}")
    print()

    if added_pkgs:
        print(f"  Added packages (+{len(added_pkgs)}): {', '.join(sorted(added_pkgs))}")
    if removed_pkgs:
        print(f"  Removed packages (-{len(removed_pkgs)}): {', '.join(sorted(removed_pkgs))}")
    if added_skills:
        print(f"  Added skills (+{len(added_skills)}): {', '.join(sorted(added_skills))}")
    if removed_skills:
        print(f"  Removed skills (-{len(removed_skills)}): {', '.join(sorted(removed_skills))}")
    if not (added_pkgs or removed_pkgs or added_skills or removed_skills):
        print("  No differences — system matches snapshot exactly.")


def snapshot_delete(filename):
    filepath = SNAPSHOTS_DIR / filename
    if not filepath.exists():
        print(f"[ERROR] Snapshot not found: {filename}")
        return
    filepath.unlink()
    idx = load_index()
    idx["entries"] = [e for e in idx["entries"] if e["filename"] != filename]
    save_index(idx)
    print(f"[INFO] Snapshot deleted: {filename}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/snapshots.py <command> [options]", file=sys.stderr)
        print("  snapshot-save [--label ...]", file=sys.stderr)
        print("  snapshot-list", file=sys.stderr)
        print("  snapshot-load <filename>", file=sys.stderr)
        print("  snapshot-delete <filename>", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "snapshot-save":
        label = ""
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--label" and i + 1 < len(args):
                label = args[i + 1]
                i += 2
            else:
                i += 1
        snapshot_save(label=label)

    elif cmd == "snapshot-list":
        snapshot_list()

    elif cmd == "snapshot-load":
        if len(sys.argv) < 3:
            print("[ERROR] snapshot-load requires a filename", file=sys.stderr)
            sys.exit(1)
        snapshot_load(sys.argv[2])

    elif cmd == "snapshot-delete":
        if len(sys.argv) < 3:
            print("[ERROR] snapshot-delete requires a filename", file=sys.stderr)
            sys.exit(1)
        snapshot_delete(sys.argv[2])

    else:
        print(f"[ERROR] Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
