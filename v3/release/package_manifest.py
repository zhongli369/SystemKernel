"""
Package Manifest — Reproducible release package manifest for SystemKernel v3.0.

Catalogues every file in the v3.0 baseline with content hashes, subsystem
membership, and artifact type classification. Deterministic manifest hash.

Phase 6A: Baseline packaging. No new runtime capabilities.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# PackageManifestEntry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PackageManifestEntry:
    """One entry in the release package manifest."""

    path: str = ""
    subsystem: str = ""
    artifact_type: str = ""  # source, test, report, doc, example, cli, release
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


# ═══════════════════════════════════════════════════════════════════════
# PackageManifest
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PackageManifest:
    """Complete release package manifest for SystemKernel v3.0."""

    version: str = "3.0.0"
    created_at: str = ""
    entries: Tuple[PackageManifestEntry, ...] = ()
    required_count: int = 0
    optional_count: int = 0
    manifest_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "entries": [e.to_dict() for e in self.entries],
            "required_count": self.required_count,
            "optional_count": self.optional_count,
            "manifest_hash": self.manifest_hash,
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


def _compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of file content."""
    try:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()[:16]
    except (OSError, PermissionError):
        return "0" * 16


def _classify_artifact(relpath: str, subsystem: str) -> str:
    """Classify a file artifact type from its path and subsystem."""
    if subsystem == "tests":
        return "test"
    if subsystem == "exports":
        return "report"
    if subsystem == "docs":
        return "doc"
    if subsystem == "examples":
        return "example"
    if subsystem == "cli":
        return "cli"
    if subsystem == "release":
        return "release"
    if subsystem == "scripts":
        return "cli"
    return "source"


def _is_transient(fname: str, dirname: str) -> bool:
    """Check if a path represents a transient/cache artifact."""
    transient_dirs = {"__pycache__", ".git", ".mypy_cache", ".ruff_cache",
                       ".pytest_cache", "node_modules", ".tox", ".eggs"}
    transient_extensions = {".pyc", ".pyo", ".egg-info"}
    transient_prefixes = ("tmp-", "temp-", ".~")

    parts = dirname.replace("\\", "/").split("/")
    for part in parts:
        if part in transient_dirs or part.startswith("."):
            return True

    if any(fname.endswith(ext) for ext in transient_extensions):
        return True
    if any(fname.startswith(pre) for pre in transient_prefixes):
        return True

    return False


def _walk_subsystem(base_dir: str, rel_prefix: str, subsystem: str,
                    required: bool = True) -> list:
    """Walk a subsystem directory and produce manifest entries."""
    entries = []
    if not os.path.isdir(base_dir):
        return entries

    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames[:] = sorted(d for d in dirnames
                            if not d.startswith(".") and d != "__pycache__")

        for fname in sorted(filenames):
            if _is_transient(fname, dirpath):
                continue

            fpath = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(fpath)
            except OSError:
                size = 0

            rel = os.path.relpath(fpath, _resolve_root()).replace("\\", "/")
            file_hash = _compute_file_hash(fpath)
            artifact_type = _classify_artifact(rel, subsystem)

            entries.append(PackageManifestEntry(
                path=rel,
                subsystem=subsystem,
                artifact_type=artifact_type,
                required=required,
                hash=file_hash,
                size_bytes=size,
            ))

    return entries


def _walk_tests(tests_dir: str) -> list:
    """Walk test files specifically."""
    entries = []
    if not os.path.isdir(tests_dir):
        return entries

    for fname in sorted(os.listdir(tests_dir)):
        if not fname.endswith(".py"):
            continue
        if _is_transient(fname, tests_dir):
            continue
        fpath = os.path.join(tests_dir, fname)
        try:
            size = os.path.getsize(fpath)
        except OSError:
            size = 0

        rel = os.path.relpath(fpath, _resolve_root()).replace("\\", "/")
        file_hash = _compute_file_hash(fpath)
        is_required = fname.startswith("test_")

        entries.append(PackageManifestEntry(
            path=rel,
            subsystem="tests",
            artifact_type="test",
            required=is_required,
            hash=file_hash,
            size_bytes=size,
        ))

    return entries


def _walk_exports(exports_dir: str) -> list:
    """Walk export/report files."""
    entries = []
    if not os.path.isdir(exports_dir):
        return entries

    for fname in sorted(os.listdir(exports_dir)):
        if _is_transient(fname, exports_dir):
            continue
        fpath = os.path.join(exports_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            size = os.path.getsize(fpath)
        except OSError:
            size = 0

        rel = os.path.relpath(fpath, _resolve_root()).replace("\\", "/")
        file_hash = _compute_file_hash(fpath)
        # Phase reports and release artifacts are required; transient data is optional
        is_required = any(key in fname for key in (
            "release_", "kernel_validity", "memory_system", "complexity_budget",
            "phase_", "external_tool_registry", "github_clone_plan",
            "architect", "golden_path_report"
        )) or fname.endswith(".md")

        artifact_type = "report"

        entries.append(PackageManifestEntry(
            path=rel,
            subsystem="exports",
            artifact_type=artifact_type,
            required=is_required,
            hash=file_hash,
            size_bytes=size,
        ))

    return entries


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def build_package_manifest(v3_root: Optional[str] = None) -> PackageManifest:
    """Build the complete release package manifest for v3.0 baseline.

    Deterministic: same filesystem state → same manifest → same hash.
    """
    if v3_root is None:
        v3_root = _resolve_v3_root()
    root = _resolve_root()

    from datetime import datetime, timezone

    all_entries = []

    # Kernel source (all .py required)
    kernel_dir = os.path.join(v3_root, "kernel")
    all_entries.extend(_walk_subsystem(kernel_dir, "v3/kernel", "kernel"))

    # Memory source (all .py required)
    memory_dir = os.path.join(v3_root, "memory")
    all_entries.extend(_walk_subsystem(memory_dir, "v3/memory", "memory"))

    # Quality source (all .py required)
    quality_dir = os.path.join(v3_root, "quality")
    all_entries.extend(_walk_subsystem(quality_dir, "v3/quality", "quality"))

    # Intake source (all .py required)
    intake_dir = os.path.join(v3_root, "intake")
    all_entries.extend(_walk_subsystem(intake_dir, "v3/intake", "intake"))

    # CLI source (all .py required)
    cli_dir = os.path.join(v3_root, "cli")
    all_entries.extend(_walk_subsystem(cli_dir, "v3/cli", "cli"))

    # Release source (all .py required)
    release_dir = os.path.join(v3_root, "release")
    all_entries.extend(_walk_subsystem(release_dir, "v3/release", "release"))

    # Tools source
    tools_dir = os.path.join(v3_root, "tools")
    all_entries.extend(_walk_subsystem(tools_dir, "v3/tools", "tools"))

    # Packages
    packages_dir = os.path.join(v3_root, "packages")
    all_entries.extend(_walk_subsystem(packages_dir, "v3/packages", "packages"))

    # Integrations (optional — connectors to external tools)
    integrations_dir = os.path.join(v3_root, "integrations")
    all_entries.extend(_walk_subsystem(integrations_dir, "v3/integrations",
                                       "integrations", required=False))

    # Config files (required)
    config_dir = os.path.join(v3_root, "config")
    all_entries.extend(_walk_subsystem(config_dir, "v3/config", "config"))

    # Tests (required test_ files)
    tests_dir = os.path.join(v3_root, "tests")
    all_entries.extend(_walk_tests(tests_dir))

    # Exports (reports — phase reports required, data optional)
    exports_dir = os.path.join(v3_root, "exports")
    all_entries.extend(_walk_exports(exports_dir))

    # Main entry point
    main_py = os.path.join(v3_root, "main.py")
    if os.path.exists(main_py):
        all_entries.append(PackageManifestEntry(
            path="v3/main.py",
            subsystem="kernel",
            artifact_type="source",
            required=True,
            hash=_compute_file_hash(main_py),
            size_bytes=os.path.getsize(main_py),
        ))

    # Docs (optional — informative)
    docs_dir = os.path.join(root, "docs")
    if os.path.isdir(docs_dir):
        all_entries.extend(_walk_subsystem(docs_dir, "docs", "docs",
                                           required=False))

    # Examples / golden path (required)
    examples_dir = os.path.join(root, "examples")
    if os.path.isdir(examples_dir):
        all_entries.extend(_walk_subsystem(examples_dir, "examples", "examples"))

    # Scripts (required — verification script)
    scripts_dir = os.path.join(root, "scripts")
    if os.path.isdir(scripts_dir):
        all_entries.extend(_walk_subsystem(scripts_dir, "scripts", "scripts"))

    # Sort deterministically by path
    entries_tuple = tuple(sorted(all_entries, key=lambda e: e.path))

    required_count = sum(1 for e in entries_tuple if e.required)
    optional_count = len(entries_tuple) - required_count

    # Compute manifest hash (hash of all entry dicts)
    hash_input = json.dumps(
        [e.to_dict() for e in entries_tuple], sort_keys=True, ensure_ascii=False)
    manifest_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return PackageManifest(
        version="3.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        entries=entries_tuple,
        required_count=required_count,
        optional_count=optional_count,
        manifest_hash=manifest_hash,
    )


def write_package_manifest(manifest: PackageManifest, path: str) -> str:
    """Write package manifest to JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)


# ═══════════════════════════════════════════════════════════════════════
# Verification
# ═══════════════════════════════════════════════════════════════════════

def verify_package_manifest(manifest: PackageManifest) -> Tuple[bool, list]:
    """Verify a package manifest for structural correctness.

    Returns (ok, issues) where issues is a list of problem descriptions.
    """
    issues = []

    if not manifest.entries:
        issues.append("Manifest has zero entries")
        return False, issues

    if manifest.required_count + manifest.optional_count != len(manifest.entries):
        issues.append(
            f"Count mismatch: required={manifest.required_count} + "
            f"optional={manifest.optional_count} != total={len(manifest.entries)}"
        )

    # Check required source files exist
    required_subsystems = {"kernel", "memory", "quality", "intake", "cli", "release"}
    found_subsystems = set(e.subsystem for e in manifest.entries if e.required)
    missing_subsystems = required_subsystems - found_subsystems
    if missing_subsystems:
        issues.append(f"Missing required subsystems: {missing_subsystems}")

    # Check tests are present
    test_entries = [e for e in manifest.entries if e.artifact_type == "test"]
    if not test_entries:
        issues.append("No test entries in manifest")

    # Check golden path is present
    golden_path = [e for e in manifest.entries if "golden_path" in e.path
                   and e.artifact_type == "example"]
    if not golden_path:
        issues.append("No golden path entries in manifest")

    # Check docs present
    doc_entries = [e for e in manifest.entries if e.artifact_type == "doc"]
    if not doc_entries:
        issues.append("No docs entries in manifest")

    # Check no transient caches
    transient_patterns = ("__pycache__", ".pyc", ".egg-info", "__pycache__/")
    transient_entries = [e for e in manifest.entries
                         if any(p in e.path for p in transient_patterns)]
    if transient_entries:
        issues.append(f"Transient cache entries found: {[e.path for e in transient_entries]}")

    # Check manifest hash is set
    if not manifest.manifest_hash:
        issues.append("Manifest hash is empty")

    # Check hashes are non-zero
    zero_hash_entries = [e for e in manifest.entries
                         if e.hash == "0" * 16 and e.size_bytes > 0]
    if zero_hash_entries:
        issues.append(f"Entries with zero hash but non-zero size: "
                      f"{[e.path for e in zero_hash_entries]}")

    return len(issues) == 0, issues
