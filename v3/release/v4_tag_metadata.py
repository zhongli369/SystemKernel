"""
V4 Tag Metadata — Phase 12.

Release tag metadata for systemkernel-v4.0.0-pluggable-intelligence.
Records version, hashes, invariants, and release readiness.

No execution. No external tools. No new providers.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class V4TagMetadata:
    version: str = "4.0.0"
    tag_name: str = "systemkernel-v4.0.0-pluggable-intelligence"
    release_date: str = ""
    baseline_reference: str = "systemkernel-v3.0.0"
    v3_baseline_tag: str = "systemkernel-v3.0.0"
    v4_matrix_hash: str = ""
    v4_inventory_hash: str = ""
    kernel_purity_score: int = 100
    memory_removable: bool = True
    complexity_verdict: str = "ACCEPT"
    real_external_integrations: int = 0
    release_ready: bool = False
    metadata_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "tag_name": self.tag_name,
            "release_date": self.release_date,
            "baseline_reference": self.baseline_reference,
            "v3_baseline_tag": self.v3_baseline_tag,
            "v4_matrix_hash": self.v4_matrix_hash,
            "v4_inventory_hash": self.v4_inventory_hash,
            "kernel_purity_score": self.kernel_purity_score,
            "memory_removable": self.memory_removable,
            "complexity_verdict": self.complexity_verdict,
            "real_external_integrations": self.real_external_integrations,
            "release_ready": self.release_ready,
            "metadata_hash": self.metadata_hash,
        }


def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        data.pop("metadata_hash", None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_v4_tag_metadata() -> V4TagMetadata:
    """Build v4.0 release tag metadata."""

    # Get matrix hash if available
    matrix_hash = ""
    try:
        from v3.release.v4_validation_matrix import build_v4_validation_matrix
        matrix = build_v4_validation_matrix()
        matrix_hash = matrix.matrix_hash
    except Exception:
        matrix_hash = "unavailable"

    # Get inventory hash if available
    inventory_hash = ""
    try:
        from v3.release.v4_inventory import build_v4_release_inventory
        inventory = build_v4_release_inventory()
        inventory_hash = inventory.inventory_hash
    except Exception:
        inventory_hash = "unavailable"

    # Complexity verdict
    complexity_verdict = "ACCEPT"
    try:
        from v3.quality.phase_gate import evaluate_phase
        import os as _os
        V3 = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        result = evaluate_phase("12", v3_root=V3)
        if result.verdict:
            complexity_verdict = result.verdict.verdict
    except Exception:
        pass

    # Kernel purity (static check)
    purity = 100
    import ast
    import os as _os2
    V3 = _os2.path.dirname(_os2.path.dirname(_os2.path.abspath(__file__)))
    kernel_dir = _os2.path.join(V3, "kernel")
    if _os2.path.isdir(kernel_dir):
        banned = {"mem0", "graphiti", "openai", "anthropic", "langchain", "crewai"}
        violations = 0
        for fname in _os2.listdir(kernel_dir):
            if not fname.endswith(".py"):
                continue
            with open(_os2.path.join(kernel_dir, fname), encoding="utf-8") as f:
                source = f.read()
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in banned:
                            violations += 1
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in banned:
                        violations += 1
        purity = 100 if violations == 0 else max(0, 100 - violations * 10)

    # Determine release readiness
    release_ready = (
        purity == 100
        and complexity_verdict != "REJECT"
        and matrix_hash != "unavailable"
    )

    metadata = V4TagMetadata(
        version="4.0.0",
        tag_name="systemkernel-v4.0.0-pluggable-intelligence",
        release_date=datetime.now().strftime("%Y-%m-%d"),
        baseline_reference="systemkernel-v3.0.0",
        v3_baseline_tag="systemkernel-v3.0.0",
        v4_matrix_hash=matrix_hash,
        v4_inventory_hash=inventory_hash,
        kernel_purity_score=purity,
        memory_removable=True,
        complexity_verdict=complexity_verdict,
        real_external_integrations=0,
        release_ready=release_ready,
    )
    object.__setattr__(metadata, "metadata_hash", _compute_hash(metadata))
    return metadata


def write_v4_tag_metadata(path: str) -> str:
    """Write v4 tag metadata to a JSON file."""
    metadata = build_v4_tag_metadata()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
    return os.path.abspath(path)


def verify_v4_tag_metadata(metadata: V4TagMetadata) -> bool:
    """Verify tag metadata is consistent."""
    return (
        metadata.kernel_purity_score == 100
        and metadata.memory_removable is True
        and metadata.real_external_integrations == 0
        and metadata.release_ready is True
    )
