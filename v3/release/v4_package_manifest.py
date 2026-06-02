"""
V4 Package Manifest — Phase 12.

Describes what is included in the v4.0 release package.
Lists included paths, excluded patterns, and required artifacts.

No execution. No external tools. No new providers.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class V4PackageManifest:
    version: str = "4.0"
    included_paths: Tuple[str, ...] = ()
    excluded_patterns: Tuple[str, ...] = ()
    required_artifacts: Tuple[str, ...] = ()
    manifest_hash: str = ""
    package_ready: bool = False

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "included_paths": list(self.included_paths),
            "excluded_patterns": list(self.excluded_patterns),
            "required_artifacts": list(self.required_artifacts),
            "manifest_hash": self.manifest_hash,
            "package_ready": self.package_ready,
        }


def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        data.pop("manifest_hash", None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


_INCLUDED_PATHS = (
    "v3/",                    # All v3 source
    "docs/",                  # Documentation
    "scripts/",               # Verification scripts
    "CLAUDE.md",              # Project instructions
    "README.md",              # Readme
)

_EXCLUDED_PATTERNS = (
    "v3/checkpoints/",        # Runtime checkpoint data
    "v3/traces/",             # Runtime trace data
    "v3/metrics/",            # Runtime metric data
    "v3/memory/data/",        # Memory projection data
    "external_trials/",       # External trial clones
    "__pycache__/",           # Python cache
    "*.pyc",                   # Compiled Python
    "*.pyo",                   # Optimized Python
    ".git/",                  # Git repository
    "v3/exports/",            # Generated exports (regenerated on demand)
)

_REQUIRED_ARTIFACTS = (
    "v3/kernel/__init__.py",
    "v3/external/__init__.py",
    "v3/external/capability_contract.py",
    "v3/external/capability_registry.py",
    "v3/external/default_capabilities.py",
    "v3/external/evidence.py",
    "v3/external/context_plane.py",
    "v3/external/memory_intelligence.py",
    "v3/external/agent_worker.py",
    "v3/external/workspace_context.py",
    "v3/external/skill_evolution.py",
    "v3/external/orchestration_policy.py",
    "v3/evals/__init__.py",
    "v3/evals/evaluation_harness.py",
    "v3/evals/benefit_complexity.py",
    "v3/evals/regression_matrix.py",
    "v3/ops/__init__.py",
    "v3/ops/v4_ops.py",
    "v3/ops/runbook.py",
    "v3/release/__init__.py",
    "v3/release/v4_baseline_guard.py",
    "v3/release/v4_validation_matrix.py",
    "v3/release/v4_inventory.py",
    "v3/release/v4_release_notes.py",
    "v3/release/v4_tag_metadata.py",
    "v3/release/v4_package_manifest.py",
    "v3/quality/__init__.py",
    "v3/quality/complexity_budget.py",
    "v3/quality/phase_gate.py",
    "v3/cli/systemkernel.py",
    "v3/tests/test_kernel_invariants.py",
    "v3/tests/test_v4_baseline_guard.py",
    "v3/tests/test_capability_contract.py",
    "v3/tests/test_capability_registry.py",
    "v3/tests/test_external_evidence.py",
    "v3/tests/test_orchestration_policy.py",
    "v3/tests/test_evaluation_harness.py",
    "v3/tests/test_v4_productization_ops.py",
    "v3/tests/test_v4_release_freeze.py",
    "scripts/verify_v4_baseline.py",
    "CLAUDE.md",
)


def build_v4_package_manifest() -> V4PackageManifest:
    """Build the v4.0 package manifest."""

    manifest = V4PackageManifest(
        version="4.0",
        included_paths=_INCLUDED_PATHS,
        excluded_patterns=_EXCLUDED_PATTERNS,
        required_artifacts=_REQUIRED_ARTIFACTS,
        package_ready=True,
    )
    object.__setattr__(manifest, "manifest_hash", _compute_hash(manifest))
    return manifest


def write_v4_package_manifest(path: str) -> str:
    """Write v4 package manifest to a JSON file."""
    manifest = build_v4_package_manifest()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
    return os.path.abspath(path)


def verify_v4_package_manifest(manifest: V4PackageManifest) -> bool:
    """Verify all required artifacts exist on disk."""
    import os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    for artifact in manifest.required_artifacts:
        full = _os.path.join(root, artifact)
        if not _os.path.exists(full):
            return False
    return True
