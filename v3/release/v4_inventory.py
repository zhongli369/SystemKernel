"""
V4 Release Inventory — Phase 12.

Read-only inventory of all v4 release artifacts.
Categorizes files by subsystem and artifact type.
Excludes runtime data, checkpoints, traces, and external clones.

No execution. No external tools. No new providers.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class V4InventoryEntry:
    path: str = ""
    subsystem: str = ""
    artifact_type: str = ""
    required: bool = True
    hash: str = ""
    size_bytes: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "subsystem": self.subsystem,
            "artifact_type": self.artifact_type,
            "required": self.required,
            "hash": self.hash,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class V4ReleaseInventory:
    version: str = "4.0"
    entries: Tuple[V4InventoryEntry, ...] = ()
    subsystem_counts: dict = None
    artifact_counts: dict = None
    inventory_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "entries": [e.to_dict() for e in self.entries],
            "subsystem_counts": self.subsystem_counts or {},
            "artifact_counts": self.artifact_counts or {},
            "inventory_hash": self.inventory_hash,
        }

    def __post_init__(self):
        if self.subsystem_counts is None:
            object.__setattr__(self, "subsystem_counts", {})
        if self.artifact_counts is None:
            object.__setattr__(self, "artifact_counts", {})


def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        data.pop("inventory_hash", None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _resolve_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_EXCLUDED_PATTERNS = [
    "checkpoints",
    "traces",
    "metrics",
    "memory/data",
    "external_trials",
    "__pycache__",
]


_EXCLUDED_EXTENSIONS = {".pyc", ".pyo"}


_SUBSYSTEM_MAP = {
    "external": "external",
    "evals": "evals",
    "ops": "ops",
    "release": "release",
    "tests": "tests",
    "kernel": "kernel",
    "memory": "memory",
    "quality": "quality",
    "cli": "cli",
}

_ARTIFACT_MAP = {
    ".py": "source",
    ".json": "fixture",
    ".md": "doc",
    ".txt": "doc",
}


def _is_excluded(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part in _EXCLUDED_PATTERNS or part.endswith(".pyc"):
            return True
    for ext in _EXCLUDED_EXTENSIONS:
        if rel_path.endswith(ext):
            return True
    # Exclude memory data files
    if "memory/data" in rel_path.replace("\\", "/"):
        return True
    return False


def _classify_subsystem(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    if len(parts) >= 2:
        top = parts[1] if parts[0] == "v3" else parts[0]
        return _SUBSYSTEM_MAP.get(top, "other")
    return "root"


def _classify_artifact_type(rel_path: str) -> str:
    _, ext = os.path.splitext(rel_path)
    return _ARTIFACT_MAP.get(ext, "other")


_BUILD_BLACKLIST = {
    "v3/release/v3_validation_matrix.py",
    "v3/release/v3_inventory.py",
    "v3/release/v3_release_notes.py",
    "v3/release/v3_tag_metadata.py",
    "v3/release/v3_package_manifest.py",
    "v3/release/v3_baseline_guard.py",
}


def build_v4_release_inventory() -> V4ReleaseInventory:
    """Build a complete inventory of v4 release artifacts."""
    V3 = _resolve_root()
    entries = []

    # Walk v3/ directory
    for dirpath, dirnames, filenames in os.walk(V3):
        # Filter excluded directories
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_PATTERNS and d != "__pycache__"]

        for fname in filenames:
            if fname.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, os.path.dirname(V3)).replace("\\", "/")

            if _is_excluded(rel):
                continue

            size = os.path.getsize(full)
            subsystem = _classify_subsystem(rel)
            artifact_type = _classify_artifact_type(rel)
            required = "test_" not in fname and "checkpoint" not in rel

            entry = V4InventoryEntry(
                path=rel,
                subsystem=subsystem,
                artifact_type=artifact_type,
                required=required,
                hash="",
                size_bytes=size,
            )
            object.__setattr__(entry, "hash", _compute_hash(entry)[:12])
            entries.append(entry)

    # Also include Docs/
    docs_dir = os.path.join(os.path.dirname(V3), "Docs")
    if os.path.isdir(docs_dir):
        for dirpath, dirnames, filenames in os.walk(docs_dir):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, os.path.dirname(V3)).replace("\\", "/")
                size = os.path.getsize(full)
                entry = V4InventoryEntry(
                    path=rel,
                    subsystem="docs",
                    artifact_type="doc",
                    required=False,
                    hash="",
                    size_bytes=size,
                )
                object.__setattr__(entry, "hash", _compute_hash(entry)[:12])
                entries.append(entry)

    # Sort by path
    entries.sort(key=lambda e: e.path)

    # Count by subsystem
    sub_counts = {}
    for e in entries:
        sub_counts[e.subsystem] = sub_counts.get(e.subsystem, 0) + 1

    # Count by artifact type
    art_counts = {}
    for e in entries:
        art_counts[e.artifact_type] = art_counts.get(e.artifact_type, 0) + 1

    inventory = V4ReleaseInventory(
        version="4.0",
        entries=tuple(entries),
        subsystem_counts=sub_counts,
        artifact_counts=art_counts,
    )
    object.__setattr__(inventory, "inventory_hash", _compute_hash(inventory))
    return inventory


def write_v4_release_inventory(path: str) -> str:
    """Write v4 release inventory to a JSON file."""
    inventory = build_v4_release_inventory()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(inventory.to_dict(), f, indent=2, ensure_ascii=False, default=str)
    return os.path.abspath(path)


def verify_v4_release_inventory(inventory: V4ReleaseInventory) -> bool:
    """Verify inventory has required subsystems."""
    required_subsystems = {"external", "evals", "ops", "tests", "release", "kernel"}
    present = set(inventory.subsystem_counts.keys())
    return required_subsystems.issubset(present)
