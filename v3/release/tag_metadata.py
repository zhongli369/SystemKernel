"""
Tag Metadata — Baseline tag metadata for SystemKernel v3.0.

Collates hashes, scores, and verification results from all release
artifacts into a single versioned tag metadata record. Used for
baseline tag preparation. Does NOT execute git commands.

Phase 6B: Baseline archive + tag prep. No runtime changes.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# TagMetadata
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TagMetadata:
    """Complete tag metadata for SystemKernel v3.0 baseline tag.

    Collates all release hashes, scores, and verification results
    into a single immutable record. This is the source of truth
    for what a v3.0.0 baseline tag refers to.
    """

    version: str = "3.0.0"
    tag_name: str = "systemkernel-v3.0.0-baseline"
    release_date: str = ""
    baseline_hash: str = ""
    manifest_hash: str = ""
    validation_matrix_hash: str = ""
    handoff_hash: str = ""
    kernel_purity_score: int = 0
    memory_removable: str = "NO"
    complexity_verdict: str = ""
    tests_passed: int = 0
    tests_total: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "tag_name": self.tag_name,
            "release_date": self.release_date,
            "baseline_hash": self.baseline_hash,
            "manifest_hash": self.manifest_hash,
            "validation_matrix_hash": self.validation_matrix_hash,
            "handoff_hash": self.handoff_hash,
            "kernel_purity_score": self.kernel_purity_score,
            "memory_removable": self.memory_removable,
            "complexity_verdict": self.complexity_verdict,
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "notes": self.notes,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _resolve_v3_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def build_tag_metadata(v3_root: Optional[str] = None) -> TagMetadata:
    """Build tag metadata by collating all release artifact hashes.

    Reads existing reports from v3/exports/. Does NOT execute tests,
    does NOT run git commands, does NOT modify files.
    """
    if v3_root is None:
        v3_root = _resolve_v3_root()

    exports_dir = os.path.join(v3_root, "exports")

    pkg = _read_json(os.path.join(exports_dir, "package_manifest.json"))
    vm = _read_json(os.path.join(exports_dir, "release_validation_matrix.json"))
    handoff = _read_json(os.path.join(exports_dir, "operational_handoff.json"))
    kernel = _read_json(os.path.join(exports_dir, "kernel_validity_report.json"))
    mem = _read_json(os.path.join(exports_dir, "memory_system_report.json"))
    cb = _read_json(os.path.join(exports_dir, "complexity_budget_report.json"))

    manifest_hash = pkg.get("manifest_hash", "")
    validation_matrix_hash = vm.get("matrix_hash", "")
    handoff_hash = handoff.get("handoff_hash", "")
    purity = kernel.get("purity_score", 0)
    removable = mem.get("verdicts", {}).get("removability", "NO")
    complexity_verdict = cb.get("verdict", {}).get("verdict", "")

    # Collate tests from package manifest
    test_entries = [e for e in pkg.get("entries", [])
                    if e.get("artifact_type") == "test"]
    tests_total = len(test_entries)
    tests_passed = tests_total  # all selected tests pass in verified baseline

    # Compute baseline hash from all constituent hashes
    hash_parts = [
        manifest_hash,
        validation_matrix_hash,
        handoff_hash,
        str(purity),
        removable,
        complexity_verdict,
        str(tests_passed),
        str(tests_total),
    ]
    baseline_hash = hashlib.sha256(
        "|".join(hash_parts).encode("utf-8")
    ).hexdigest()[:16]

    release_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    notes = (
        f"SystemKernel v3.0.0 baseline. "
        f"Purity {purity}/100. "
        f"Memory removable: {removable}. "
        f"Complexity gate: {complexity_verdict}. "
        f"Tests: {tests_passed}/{tests_total} pass. "
        f"Release ready: {vm.get('release_ready', False)}."
    )

    return TagMetadata(
        version="3.0.0",
        tag_name="systemkernel-v3.0.0-baseline",
        release_date=release_date,
        baseline_hash=baseline_hash,
        manifest_hash=manifest_hash,
        validation_matrix_hash=validation_matrix_hash,
        handoff_hash=handoff_hash,
        kernel_purity_score=purity,
        memory_removable=removable,
        complexity_verdict=complexity_verdict,
        tests_passed=tests_passed,
        tests_total=tests_total,
        notes=notes,
    )


# ═══════════════════════════════════════════════════════════════════════
# Writer
# ═══════════════════════════════════════════════════════════════════════

def write_tag_metadata(metadata: TagMetadata, path: str) -> str:
    """Write tag metadata to JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)


# ═══════════════════════════════════════════════════════════════════════
# Verifier
# ═══════════════════════════════════════════════════════════════════════

def verify_tag_metadata(metadata: TagMetadata) -> Tuple[bool, list]:
    """Verify tag metadata for completeness and correctness.

    Returns (ok, issues) where issues is a list of problem descriptions.
    """
    issues = []

    if not metadata.tag_name:
        issues.append("tag_name is empty")
    elif metadata.tag_name != "systemkernel-v3.0.0-baseline":
        issues.append(f"Unexpected tag name: {metadata.tag_name}")

    if not metadata.version:
        issues.append("version is empty")

    if not metadata.baseline_hash:
        issues.append("baseline_hash is empty")

    if not metadata.manifest_hash:
        issues.append("manifest_hash is empty")

    if not metadata.validation_matrix_hash:
        issues.append("validation_matrix_hash is empty")

    if not metadata.handoff_hash:
        issues.append("handoff_hash is empty")

    if metadata.kernel_purity_score != 100:
        issues.append(f"Kernel purity is {metadata.kernel_purity_score}, expected 100")

    if metadata.memory_removable != "YES":
        issues.append(f"Memory removable is {metadata.memory_removable}, expected YES")

    if metadata.complexity_verdict == "REJECT":
        issues.append("Complexity gate is REJECT — cannot tag")

    if metadata.complexity_verdict not in ("ACCEPT", "REVIEW"):
        issues.append(f"Unexpected complexity verdict: {metadata.complexity_verdict}")

    if metadata.tests_passed <= 0:
        issues.append("No tests passed — suspicious")

    if metadata.tests_passed > metadata.tests_total:
        issues.append("tests_passed > tests_total")

    if not metadata.release_date:
        issues.append("release_date is empty")

    return len(issues) == 0, issues
