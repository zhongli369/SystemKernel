"""
Archive Manifest — Baseline archive manifest for SystemKernel v3.0.

Defines what goes into a v3.0 baseline archive: reports, docs, examples,
tests, and what is explicitly excluded. Does NOT create zip/tar archives.
Manifest-only — archive creation is the caller's responsibility.

Phase 6B: Baseline archive + tag prep. No runtime changes.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# ArchiveManifest
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ArchiveManifest:
    """Complete archive manifest for SystemKernel v3.0 baseline.

    Describes what a v3.0 baseline archive should contain and
    explicitly exclude. Does NOT create archives — manifest only.
    """

    version: str = "3.0.0"
    archive_name: str = "systemkernel-v3.0.0-baseline"
    included_reports: Tuple[str, ...] = ()
    included_docs: Tuple[str, ...] = ()
    included_examples: Tuple[str, ...] = ()
    included_tests: Tuple[str, ...] = ()
    excluded_patterns: Tuple[str, ...] = ()
    archive_hash: str = ""
    archive_ready: bool = False

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "archive_name": self.archive_name,
            "included_reports": list(self.included_reports),
            "included_docs": list(self.included_docs),
            "included_examples": list(self.included_examples),
            "included_tests": list(self.included_tests),
            "excluded_patterns": list(self.excluded_patterns),
            "archive_hash": self.archive_hash,
            "archive_ready": self.archive_ready,
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


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def build_archive_manifest(v3_root: Optional[str] = None) -> ArchiveManifest:
    """Build the archive manifest for v3.0 baseline.

    Lists all files that SHOULD be included in a baseline archive
    and all patterns that SHOULD be excluded. Does NOT create archives.
    """
    if v3_root is None:
        v3_root = _resolve_v3_root()
    root = _resolve_root()

    # ── Included reports (key exports) ──
    exports_dir = os.path.join(v3_root, "exports")
    key_reports = [
        "kernel_validity_report.json",
        "memory_system_report.json",
        "memory_removability_report.json",
        "complexity_budget_report.json",
        "release_inventory.json",
        "release_validation_matrix.json",
        "external_tool_registry.json",
        "github_clone_plan.json",
        "github_clone_plan.md",
        "systemkernel_v3_release_notes.md",
        "package_manifest.json",
        "operational_handoff.json",
        "operational_handoff.md",
        "phase_4d_completion_report.md",
        "phase_5a_gate_report.md",
        "phase_5b_cli_report.md",
        "phase_5c_examples_report.md",
        "phase_5d_repo_intake_report.md",
        "phase_5e_external_registry_report.md",
        "phase_5f_release_freeze_report.md",
        "phase_6a_packaging_report.md",
    ]
    included_reports = tuple(
        r for r in key_reports
        if os.path.exists(os.path.join(exports_dir, r))
    )

    # ── Included docs ──
    docs_dir = os.path.join(root, "docs")
    key_docs = [
        "OPERATIONS.md",
        "ARCHITECTURE_OVERVIEW.md",
        "KERNEL_BOUNDARY.md",
        "QUICKSTART.md",
        "complexity-risk-report.md",
    ]
    included_docs = tuple(
        d for d in key_docs
        if os.path.exists(os.path.join(docs_dir, d))
    )

    # ── Included examples ──
    key_examples = [
        "examples/golden_path/run_golden_path.py",
        "examples/golden_path/expected_summary.json",
        "examples/golden_path/README.md",
        "examples/basic_usage.py",
    ]
    included_examples = tuple(
        e for e in key_examples
        if os.path.exists(os.path.join(root, e))
    )

    # ── Included tests ──
    tests_dir = os.path.join(v3_root, "tests")
    if os.path.isdir(tests_dir):
        test_files = sorted(
            f for f in os.listdir(tests_dir)
            if f.startswith("test_") and f.endswith(".py")
        )
        included_tests = tuple(f"v3/tests/{t}" for t in test_files)
    else:
        included_tests = ()

    # ── Excluded patterns ──
    excluded_patterns = (
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        ".git/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".pytest_cache/",
        "checkpoints/",
        "traces/",
        "metrics/",
        "*.egg-info/",
        ".DS_Store",
        "Thumbs.db",
    )

    # ── Compute archive hash ──
    hash_parts = [
        "|".join(included_reports),
        "|".join(included_docs),
        "|".join(included_examples),
        "|".join(included_tests),
        "|".join(excluded_patterns),
    ]
    archive_hash = hashlib.sha256(
        "||".join(hash_parts).encode("utf-8")
    ).hexdigest()[:16]

    # ── Archive ready ──
    archive_ready = (
        len(included_reports) > 0
        and len(included_docs) > 0
        and len(included_examples) > 0
        and len(included_tests) > 0
    )

    return ArchiveManifest(
        version="3.0.0",
        archive_name="systemkernel-v3.0.0-baseline",
        included_reports=included_reports,
        included_docs=included_docs,
        included_examples=included_examples,
        included_tests=included_tests,
        excluded_patterns=excluded_patterns,
        archive_hash=archive_hash,
        archive_ready=archive_ready,
    )


# ═══════════════════════════════════════════════════════════════════════
# Writer
# ═══════════════════════════════════════════════════════════════════════

def write_archive_manifest(manifest: ArchiveManifest, path: str) -> str:
    """Write archive manifest to JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)


# ═══════════════════════════════════════════════════════════════════════
# Verifier
# ═══════════════════════════════════════════════════════════════════════

def verify_archive_manifest(manifest: ArchiveManifest) -> Tuple[bool, list]:
    """Verify archive manifest for completeness and correctness.

    Returns (ok, issues) where issues is a list of problem descriptions.
    """
    issues = []

    if not manifest.archive_name:
        issues.append("archive_name is empty")

    if not manifest.included_reports:
        issues.append("No reports included in archive")

    if not manifest.included_docs:
        issues.append("No docs included in archive")

    if not manifest.included_examples:
        issues.append("No examples included in archive")

    if not manifest.included_tests:
        issues.append("No tests included in archive")

    if not manifest.excluded_patterns:
        issues.append("No excluded patterns defined")

    # Check __pycache__ is excluded
    if "__pycache__/" not in manifest.excluded_patterns:
        issues.append("__pycache__/ not in excluded patterns")

    # Check .git/ is excluded
    if ".git/" not in manifest.excluded_patterns:
        issues.append(".git/ not in excluded patterns")

    # Check golden path is included
    gp_found = any("golden_path" in e for e in manifest.included_examples)
    if not gp_found:
        issues.append("Golden path example not in included examples")

    # Check key reports
    for key in ("kernel_validity_report.json", "package_manifest.json",
                "operational_handoff.json"):
        if key not in manifest.included_reports:
            issues.append(f"Key report missing: {key}")

    if not manifest.archive_hash:
        issues.append("archive_hash is empty")

    if not manifest.archive_ready:
        issues.append("archive_ready is False")

    return len(issues) == 0, issues
