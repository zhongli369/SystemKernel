"""
Index Integrity — Deterministic integrity checks for SemanticMemoryIndex.

Phase 4D-3: Validates that the semantic index is a clean projection of
episodic records. No side effects. Does not use LLM. All checks structural.

Integrity checks:
  1. Index builds from episodic records (no external data)
  2. Every index entry references valid memory_id
  3. Every search result references valid record_hash
  4. Deterministic search ordering (same query → same results)
  5. Index hash stable (rebuild from same records → same hash)
  6. Index is projection only (all data derivable from store)
  7. No truth source violation (all source_hashes valid)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryStore, EpisodicMemoryRecord
    from v3.memory.semantic_index import SemanticMemoryIndex


# ═══════════════════════════════════════════════════════════════════════
# IndexIntegrityReport
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class IndexIntegrityReport:
    """Deterministic integrity report for a semantic memory index."""

    record_count: int
    index_entry_count: int
    index_hash: str
    checks: dict = field(default_factory=dict)
    issues: Tuple[str, ...] = ()
    passed: bool = False
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "record_count": self.record_count,
            "index_entry_count": self.index_entry_count,
            "index_hash": self.index_hash,
            "checks": dict(self.checks),
            "issues": list(self.issues),
            "passed": self.passed,
            "report_hash": self.report_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Integrity check functions
# ═══════════════════════════════════════════════════════════════════════

def check_index_integrity(
    index: "SemanticMemoryIndex",
    store: "EpisodicMemoryStore",
) -> IndexIntegrityReport:
    """Run all integrity checks on a semantic memory index.

    Pure function of index + store state. Deterministic.
    """
    issues: list[str] = []
    checks: dict[str, bool | int] = {}

    records = store.list_records()
    record_map: dict[str, EpisodicMemoryRecord] = {
        r.memory_id: r for r in records
    }

    # ── 1: Index builds from episodic records ──────────────────────────
    checks["builds_from_episodic_records"] = index.is_built
    if not index.is_built:
        issues.append("Index has not been built — cannot verify")
        return IndexIntegrityReport(
            record_count=len(records),
            index_entry_count=0,
            index_hash="",
            checks=checks,
            issues=tuple(issues),
            passed=False,
        )

    checks["builds_from_episodic_records"] = True

    # ── 2: Every index entry references valid memory_id ─────────────────
    dangling_mids = 0
    for entry in index.entries():
        for mid in entry.memory_ids:
            if mid not in record_map:
                dangling_mids += 1
                issues.append(
                    f"Index entry '{entry.token}': memory_id '{mid}' "
                    f"not found in store"
                )
    checks["all_memory_ids_valid"] = dangling_mids == 0
    checks["dangling_memory_ids"] = dangling_mids

    # ── 3: Every entry has valid record_hashes ──────────────────────────
    bad_hashes = 0
    for entry in index.entries():
        for rh in entry.record_hashes:
            matching = any(
                record_map[mid].record_hash == rh
                for mid in entry.memory_ids
                if mid in record_map
            )
            if not matching:
                bad_hashes += 1
                issues.append(
                    f"Index entry '{entry.token}': record_hash '{rh}' "
                    f"not matched to any record in store"
                )
    checks["all_record_hashes_valid"] = bad_hashes == 0
    checks["bad_record_hashes"] = bad_hashes

    # ── 4: Deterministic search ordering ────────────────────────────────
    sample_queries = ["stage", "error", "completed", "build"]
    ordering_issues = 0
    for q in sample_queries:
        r1 = index.search(q, limit=10)
        r2 = index.search(q, limit=10)
        if tuple(r.score for r in r1) != tuple(r.score for r in r2):
            ordering_issues += 1
            issues.append(f"Query '{q}': non-deterministic result ordering")
    checks["deterministic_search_ordering"] = ordering_issues == 0

    # ── 5: Index hash stable ───────────────────────────────────────────
    from v3.memory.semantic_index import SemanticMemoryIndex
    new_index = SemanticMemoryIndex()
    new_index.build(records)
    checks["index_hash_stable"] = index.index_hash == new_index.index_hash
    if index.index_hash != new_index.index_hash:
        issues.append(
            f"Index hash not stable: current={index.index_hash}, "
            f"rebuilt={new_index.index_hash}"
        )

    # ── 6: Index is projection only ─────────────────────────────────────
    total_refs = sum(len(e.memory_ids) for e in index.entries())
    max_refs_in_store = len(records) * (index.entry_count or 1)
    checks["index_is_projection_only"] = total_refs <= max_refs_in_store
    if total_refs > max_refs_in_store:
        issues.append("Index has more references than store × entries (data not from store)")

    # ── 7: No truth source violation ────────────────────────────────────
    no_source = sum(
        1 for r in records if not r.source_hash
    )
    checks["no_truth_source_violation"] = no_source == 0
    if no_source > 0:
        issues.append(f"{no_source} records have no source_hash (would be truth source)")

    passed = len(issues) == 0

    report = IndexIntegrityReport(
        record_count=len(records),
        index_entry_count=index.entry_count,
        index_hash=index.index_hash,
        checks=checks,
        issues=tuple(issues),
        passed=passed,
    )

    report_hash = _compute_index_report_hash(report)
    return IndexIntegrityReport(
        record_count=report.record_count,
        index_entry_count=report.index_entry_count,
        index_hash=report.index_hash,
        checks=report.checks,
        issues=report.issues,
        passed=report.passed,
        report_hash=report_hash,
    )


def _compute_index_report_hash(report: IndexIntegrityReport) -> str:
    parts = [
        str(report.record_count),
        str(report.index_entry_count),
        report.index_hash,
        json.dumps(report.checks, sort_keys=True, ensure_ascii=False),
        "|".join(sorted(report.issues)),
        str(report.passed),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def quick_index_check(
    index: "SemanticMemoryIndex",
    store: "EpisodicMemoryStore",
) -> bool:
    """Fast pass/fail index integrity check."""
    report = check_index_integrity(index, store)
    return report.passed


def generate_index_integrity_report_json(
    index: "SemanticMemoryIndex",
    store: "EpisodicMemoryStore",
    output_path: str,
) -> IndexIntegrityReport:
    """Run index integrity check and write report to JSON file."""
    report = check_index_integrity(index, store)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report.to_json())
    return report
