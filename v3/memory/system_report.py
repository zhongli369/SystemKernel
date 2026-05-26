"""
MemorySystemReport — Unified integrity report across all memory subsystems.

Phase 4D-6: Generates a single report covering store integrity, index integrity,
recall integrity, compaction integrity, removability, and projection-only verdict.

All checks are structural and deterministic. The report is a pure projection
of current subsystem state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryStore
    from v3.memory.semantic_index import SemanticMemoryIndex
    from v3.memory.compaction import CompactionResult


# ═══════════════════════════════════════════════════════════════════════
# MemorySystemReport
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MemorySystemReport:
    """Unified integrity report covering the full memory subsystem.

    Fields:
        store_integrity: Episodic store integrity check result
        index_integrity: Semantic index integrity check result
        compaction_integrity: Compaction integrity check result
        total_records: Total episodic records
        total_indexed_entries: Total semantic index entries
        total_compacted_records: Total compacted records
        removability_verdict: "YES" if memory is removable, "NO" otherwise
        projection_only_verdict: "YES" if all outputs are projections
        source_of_truth_verdict: "YES" if events remain source of truth
        report_hash: Deterministic hash of all report fields
    """

    store_integrity: dict = field(default_factory=dict)
    index_integrity: dict = field(default_factory=dict)
    compaction_integrity: dict = field(default_factory=dict)
    total_records: int = 0
    total_indexed_entries: int = 0
    total_compacted_records: int = 0
    removability_verdict: str = "YES"
    projection_only_verdict: str = "YES"
    source_of_truth_verdict: str = "YES"
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "store_integrity": dict(self.store_integrity),
            "index_integrity": dict(self.index_integrity),
            "compaction_integrity": dict(self.compaction_integrity),
            "counts": {
                "total_records": self.total_records,
                "total_indexed_entries": self.total_indexed_entries,
                "total_compacted_records": self.total_compacted_records,
            },
            "verdicts": {
                "removability": self.removability_verdict,
                "projection_only": self.projection_only_verdict,
                "source_of_truth": self.source_of_truth_verdict,
            },
            "report_hash": self.report_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# System report generation
# ═══════════════════════════════════════════════════════════════════════

def generate_system_report(
    store: "EpisodicMemoryStore",
    index: "Optional[SemanticMemoryIndex]" = None,
    compaction_result: "Optional[CompactionResult]" = None,
    compaction_policy=None,
    original_records: Optional[Tuple] = None,
) -> dict:
    """Generate a unified memory system report.

    Runs integrity checks on all available subsystems and produces a
    single verdict report.

    Args:
        store: EpisodicMemoryStore instance
        index: Optional SemanticMemoryIndex instance
        compaction_result: Optional CompactionResult
        compaction_policy: Optional CompactionPolicy
        original_records: Optional original records for compaction integrity

    Returns:
        dict with the full system report (can be serialized to JSON).
    """
    # Store integrity
    store_report = store.verify_integrity()
    store_valid = store_report.get("valid", False)

    # Index integrity
    index_valid = True
    index_report = {}
    index_entry_count = 0
    if index is not None:
        index_report = index.verify_integrity()
        index_valid = index_report.get("valid", True)
        index_entry_count = index.entry_count

    # Compaction integrity
    compaction_valid = True
    compaction_report = {}
    compacted_count = 0
    if compaction_result is not None:
        from v3.memory.compaction_integrity import check_compaction_integrity
        from v3.memory.compaction import CompactionPolicy
        policy = compaction_policy or CompactionPolicy()
        recs = original_records or store.list_records()
        comp_report = check_compaction_integrity(compaction_result, recs, policy)
        compaction_valid = comp_report.valid
        compaction_report = comp_report.to_dict()
        compacted_count = compaction_result.output_count

    # Removability verdict
    removable = "YES"
    if not store_valid:
        removable = "NO"

    # Projection-only verdict
    projection_only = "YES"
    if store_valid and store_report.get("checks", {}).get("memory_not_truth_source") is False:
        projection_only = "NO"
    if not index_valid:
        projection_only = "PARTIAL"
    if not compaction_valid:
        projection_only = "PARTIAL"

    # Source-of-truth verdict
    source_of_truth = "YES"
    if store_report.get("checks", {}).get("all_have_source_hash") is False:
        source_of_truth = "NO"
    if not store_valid:
        source_of_truth = "PARTIAL"

    total_records = store.record_count

    report_data = {
        "store_integrity": {
            "valid": store_valid,
            "checks": store_report.get("checks", {}),
            "issues": store_report.get("issues", []),
        },
        "index_integrity": {
            "available": index is not None,
            "valid": index_valid,
            "checks": index_report.get("checks", {}),
            "issues": index_report.get("issues", []),
            "entries": index_entry_count,
        },
        "compaction_integrity": {
            "available": compaction_result is not None,
            "valid": compaction_valid,
            "checks": compaction_report.get("checks", {}),
            "issues": compaction_report.get("issues", []),
            "compacted_records": compacted_count,
        },
        "counts": {
            "total_records": total_records,
            "total_indexed_entries": index_entry_count,
            "total_compacted_records": compacted_count,
        },
        "verdicts": {
            "removability": removable,
            "projection_only": projection_only,
            "source_of_truth": source_of_truth,
        },
    }

    # Compute deterministic hash
    parts = [
        json.dumps(report_data["store_integrity"], sort_keys=True, ensure_ascii=False),
        json.dumps(report_data["index_integrity"], sort_keys=True, ensure_ascii=False),
        json.dumps(report_data["compaction_integrity"], sort_keys=True, ensure_ascii=False),
        str(total_records),
        str(index_entry_count),
        str(compacted_count),
        removable,
        projection_only,
        source_of_truth,
    ]
    report_data["report_hash"] = hashlib.sha256(
        "|".join(parts).encode("utf-8")
    ).hexdigest()[:16]

    return report_data


def write_system_report_json(
    store: "EpisodicMemoryStore",
    output_path: str,
    index: "Optional[SemanticMemoryIndex]" = None,
    compaction_result: "Optional[CompactionResult]" = None,
) -> str:
    """Generate and write a system report to a JSON file.

    Returns the absolute path written.
    """
    report_data = generate_system_report(store, index, compaction_result)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2, sort_keys=True)
    return output_path
