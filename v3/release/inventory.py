"""
Project Inventory — Complete file/module inventory for SystemKernel v3.0.

Catalogues every module, test, report, CLI command, invariant, and
external tool registry entry. Deterministic release hash.

Phase 5F: No new runtime capabilities. Freeze only.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# InventoryEntry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class InventoryEntry:
    """One entry in the project inventory."""

    path: str = ""
    subsystem: str = ""
    kind: str = ""  # module, test, report, cli_command, invariant, config
    description: str = ""
    lines: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "subsystem": self.subsystem,
            "kind": self.kind,
            "description": self.description,
            "lines": self.lines,
        }


# ═══════════════════════════════════════════════════════════════════════
# ProjectInventory
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ProjectInventory:
    """Complete project inventory for a release."""

    release_version: str = "3.0.0"
    entries: Tuple[InventoryEntry, ...] = ()
    release_hash: str = ""
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "release_version": self.release_version,
            "entries": [e.to_dict() for e in self.entries],
            "release_hash": self.release_hash,
            "summary": self.summary,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _resolve_v3_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_root() -> str:
    return os.path.dirname(_resolve_v3_root())


def _count_lines(filepath: str) -> int:
    try:
        with open(filepath, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        return 0


def _scan_py_modules(directory: str, subsystem: str,
                     rel_prefix: str = "") -> list:
    """Scan a directory for Python modules."""
    entries = []
    if not os.path.isdir(directory):
        return entries
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = os.path.join(directory, fname)
        lines = _count_lines(fpath)
        relpath = f"{rel_prefix}/{fname}" if rel_prefix else fname
        entries.append(InventoryEntry(
            path=f"v3/{subsystem}/{fname}",
            subsystem=subsystem,
            kind="module",
            description=_extract_module_docstring(fpath),
            lines=lines,
        ))
    return entries


def _extract_module_docstring(filepath: str) -> str:
    """Extract the first line of a module docstring."""
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        doc = ast.get_docstring(tree)
        if doc:
            return doc.split("\n")[0].strip()
    except (SyntaxError, OSError):
        pass
    return ""


def _scan_test_files(tests_dir: str) -> list:
    """Scan test files and count test functions."""
    entries = []
    if not os.path.isdir(tests_dir):
        return entries
    for fname in sorted(os.listdir(tests_dir)):
        if not fname.startswith("test_") or not fname.endswith(".py"):
            continue
        fpath = os.path.join(tests_dir, fname)
        lines = _count_lines(fpath)
        test_count = _count_test_functions_in_file(fpath)
        entries.append(InventoryEntry(
            path=f"v3/tests/{fname}",
            subsystem="tests",
            kind="test",
            description=f"{test_count} test functions",
            lines=lines,
        ))
    return entries


def _count_test_functions_in_file(filepath: str) -> int:
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        return sum(1 for node in ast.walk(tree)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name.startswith("test_"))
    except (SyntaxError, OSError):
        return 0


def _scan_reports(exports_dir: str) -> list:
    """Scan export reports."""
    entries = []
    if not os.path.isdir(exports_dir):
        return entries
    for fname in sorted(os.listdir(exports_dir)):
        fpath = os.path.join(exports_dir, fname)
        if not os.path.isfile(fpath):
            continue
        size = os.path.getsize(fpath)
        if fname.endswith(".json"):
            kind = "report_json"
        elif fname.endswith(".md"):
            kind = "report_markdown"
        elif fname.endswith(".jsonl"):
            kind = "data_jsonl"
        else:
            kind = "data"
        entries.append(InventoryEntry(
            path=f"v3/exports/{fname}",
            subsystem="exports",
            kind=kind,
            description=f"{size:,} bytes",
            lines=0,
        ))
    return entries


def _extract_cli_commands(cli_path: str) -> list:
    """Extract CLI command names from systemkernel.py."""
    entries = []
    if not os.path.exists(cli_path):
        return entries
    try:
        with open(cli_path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)

        # Find subparsers added in build_parser()
        commands = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "add_parser":
                        if node.args:
                            cmd = node.args[0]
                            if isinstance(cmd, ast.Constant):
                                commands.add(cmd.value)

        for cmd in sorted(commands):
            entries.append(InventoryEntry(
                path=f"v3/cli/systemkernel.py::{cmd}",
                subsystem="cli",
                kind="cli_command",
                description=f"CLI command: {cmd}",
                lines=0,
            ))
    except (SyntaxError, OSError):
        pass
    return entries


def _extract_invariants(invariants_path: str) -> list:
    """Extract invariant names from invariants.py."""
    entries = []
    if not os.path.exists(invariants_path):
        return entries
    try:
        with open(invariants_path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ("ArchitecturalInvariant",):
                        for kw in node.keywords:
                            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                entries.append(InventoryEntry(
                                    path="v3/kernel/invariants.py",
                                    subsystem="kernel",
                                    kind="invariant",
                                    description=kw.value.value,
                                    lines=0,
                                ))
    except (SyntaxError, OSError):
        pass
    return entries


def _extract_registry_entries(registry_path: str) -> list:
    """Read external tool registry entries."""
    entries = []
    if not os.path.exists(registry_path):
        return entries
    try:
        with open(registry_path, encoding="utf-8") as f:
            data = json.load(f)
        for e in data.get("entries", []):
            entries.append(InventoryEntry(
                path=f"external_registry::{e.get('name', '?')}",
                subsystem="external_registry",
                kind="tool_entry",
                description=f"use_mode={e.get('use_mode', '?')}, priority={e.get('priority', '?')}",
                lines=0,
            ))
    except (json.JSONDecodeError, OSError):
        pass
    return entries


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def build_inventory(v3_root: Optional[str] = None) -> ProjectInventory:
    """Build complete project inventory."""
    if v3_root is None:
        v3_root = _resolve_v3_root()
    root = _resolve_root()

    all_entries = []

    # Kernel modules
    all_entries.extend(_scan_py_modules(
        os.path.join(v3_root, "kernel"), "kernel"))

    # Memory modules
    all_entries.extend(_scan_py_modules(
        os.path.join(v3_root, "memory"), "memory"))

    # Quality modules
    all_entries.extend(_scan_py_modules(
        os.path.join(v3_root, "quality"), "quality"))

    # Intake modules
    all_entries.extend(_scan_py_modules(
        os.path.join(v3_root, "intake"), "intake"))

    # CLI modules
    all_entries.extend(_scan_py_modules(
        os.path.join(v3_root, "cli"), "cli"))

    # Release modules
    all_entries.extend(_scan_py_modules(
        os.path.join(v3_root, "release"), "release"))

    # Tools modules
    tools_dir = os.path.join(v3_root, "tools")
    if os.path.isdir(tools_dir):
        all_entries.extend(_scan_py_modules(tools_dir, "tools"))

    # Test files
    all_entries.extend(_scan_test_files(os.path.join(v3_root, "tests")))

    # Reports
    all_entries.extend(_scan_reports(os.path.join(v3_root, "exports")))

    # CLI commands
    all_entries.extend(_extract_cli_commands(
        os.path.join(v3_root, "cli", "systemkernel.py")))

    # Invariants
    all_entries.extend(_extract_invariants(
        os.path.join(v3_root, "kernel", "invariants.py")))

    # External registry entries
    all_entries.extend(_extract_registry_entries(
        os.path.join(v3_root, "exports", "external_tool_registry.json")))

    # Config files
    config_dir = os.path.join(v3_root, "config")
    if os.path.isdir(config_dir):
        for fname in sorted(os.listdir(config_dir)):
            if fname.endswith((".yaml", ".yml", ".json")):
                all_entries.append(InventoryEntry(
                    path=f"v3/config/{fname}",
                    subsystem="config",
                    kind="config",
                    description="Configuration file",
                    lines=_count_lines(os.path.join(config_dir, fname)),
                ))

    # Docs
    docs_dir = os.path.join(root, "docs")
    if os.path.isdir(docs_dir):
        for fname in sorted(os.listdir(docs_dir)):
            if fname.endswith(".md"):
                all_entries.append(InventoryEntry(
                    path=f"docs/{fname}",
                    subsystem="docs",
                    kind="documentation",
                    description="Documentation",
                    lines=_count_lines(os.path.join(docs_dir, fname)),
                ))

    # Examples
    examples_dir = os.path.join(root, "examples")
    if os.path.isdir(examples_dir):
        for root_d, dirs, files in os.walk(examples_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in sorted(files):
                if fname.endswith((".py", ".md", ".json")):
                    fpath = os.path.join(root_d, fname)
                    rel = os.path.relpath(fpath, root).replace("\\", "/")
                    all_entries.append(InventoryEntry(
                        path=rel,
                        subsystem="examples",
                        kind="example",
                        description="Golden path example",
                        lines=_count_lines(fpath),
                    ))

    # Main entry point
    main_py = os.path.join(v3_root, "main.py")
    if os.path.exists(main_py):
        all_entries.append(InventoryEntry(
            path="v3/main.py",
            subsystem="kernel",
            kind="module",
            description=_extract_module_docstring(main_py),
            lines=_count_lines(main_py),
        ))

    # Build summary
    entries_tuple = tuple(all_entries)
    summary = {
        "total_entries": len(entries_tuple),
        "by_subsystem": {},
        "by_kind": {},
    }
    for e in entries_tuple:
        summary["by_subsystem"][e.subsystem] = summary["by_subsystem"].get(e.subsystem, 0) + 1
        summary["by_kind"][e.kind] = summary["by_kind"].get(e.kind, 0) + 1

    # Total lines
    total_lines = sum(e.lines for e in entries_tuple if e.lines > 0)
    summary["total_lines"] = total_lines

    # Release hash
    hash_input = json.dumps([e.to_dict() for e in entries_tuple], sort_keys=True, ensure_ascii=False)
    release_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return ProjectInventory(
        release_version="3.0.0",
        entries=entries_tuple,
        release_hash=release_hash,
        summary=summary,
    )


def compute_inventory_hash(inventory: ProjectInventory) -> str:
    """Return the deterministic hash of a project inventory."""
    return inventory.release_hash


def write_inventory(inventory: ProjectInventory, path: str) -> str:
    """Write inventory to JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(inventory.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)
