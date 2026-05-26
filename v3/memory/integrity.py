"""
Memory Integrity — Deterministic integrity checks for episodic memory store.

Phase 4D-2: Projects the store state into an integrity report. No side effects.
Does not modify the store. Does not use LLM. All checks are structural.

Integrity checks:
  1. Every record has source execution_id
  2. Every record has source_hash (graph + event traceability)
  3. Every record has deterministic record_hash
  4. No duplicate record_hash
  5. All records JSON serializable (verified during store load)
  6. Append-only ordering consistent (timestamps monotonic within execution)
  7. Records are trace-linked (source_hash references valid)
  8. Memory is not truth source (records have source_hash → events are upstream)
  9. All record_hashes compute correctly
 10. No dangling records (every record has a valid candidate_id)

Returns a deterministic IntegrityReport — same store state → same report.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryStore, EpisodicMemoryRecord


# ═══════════════════════════════════════════════════════════════════════
# IntegrityReport
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class IntegrityReport:
    """Deterministic integrity report for an episodic memory store.

    All checks are structural — no AI, no heuristics, no external services.
    report_hash is content-addressed (deterministic).
    """

    store_path: str
    total_records: int
    checks: dict = field(default_factory=dict)
    issues: Tuple[str, ...] = ()
    passed: bool = False
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "store_path": self.store_path,
            "total_records": self.total_records,
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

def check_integrity(store: "EpisodicMemoryStore") -> IntegrityReport:
    """Run all integrity checks on an episodic memory store.

    Pure function of store state. Deterministic — same store → same report.
    """
    records = store.list_records()
    issues: list[str] = []
    checks: dict[str, bool | int] = {}

    # ── 1: Every record has execution_id ──────────────────────────────
    missing_eid = sum(1 for r in records if not r.execution_id)
    checks["all_have_execution_id"] = missing_eid == 0
    if missing_eid > 0:
        issues.append(f"{missing_eid} records missing execution_id")

    # ── 2: Every record has source_hash ───────────────────────────────
    missing_sh = sum(1 for r in records if not r.source_hash)
    checks["all_have_source_hash"] = missing_sh == 0
    if missing_sh > 0:
        issues.append(f"{missing_sh} records missing source_hash")

    # ── 3: All record_hashes are valid ────────────────────────────────
    from v3.memory.episodic_store import compute_record_hash
    hash_mismatches = 0
    for r in records:
        expected = compute_record_hash(r)
        if r.record_hash != expected:
            hash_mismatches += 1
            issues.append(
                f"Record {r.memory_id}: record_hash mismatch "
                f"(stored={r.record_hash}, computed={expected})"
            )
    checks["all_record_hashes_valid"] = hash_mismatches == 0

    # ── 4: No duplicate record_hashes ─────────────────────────────────
    seen_hashes: set[str] = set()
    dupes = 0
    for r in records:
        if r.record_hash in seen_hashes:
            dupes += 1
            issues.append(f"Duplicate record_hash: {r.record_hash} ({r.memory_id})")
        seen_hashes.add(r.record_hash)
    checks["no_duplicate_hashes"] = dupes == 0
    checks["unique_record_hashes"] = len(seen_hashes)

    # ── 5: Records JSON serializable ──────────────────────────────────
    json_errors = 0
    for r in records:
        try:
            json.dumps(r.to_dict(), ensure_ascii=False)
        except (TypeError, ValueError) as e:
            json_errors += 1
            issues.append(f"Record {r.memory_id}: not JSON serializable: {e}")
    checks["all_json_serializable"] = json_errors == 0

    # ── 6: Append-only ordering (timestamps monotonic per execution) ──
    ordering_issues = 0
    by_execution: dict[str, list[EpisodicMemoryRecord]] = {}
    for r in records:
        by_execution.setdefault(r.execution_id, []).append(r)
    for eid, recs in by_execution.items():
        for i in range(1, len(recs)):
            if recs[i].created_at < recs[i - 1].created_at:
                ordering_issues += 1
                issues.append(
                    f"Execution {eid}: timestamp regression at record "
                    f"{recs[i].memory_id}"
                )
    checks["append_only_ordering_valid"] = ordering_issues == 0

    # ── 7: Records are trace-linked ───────────────────────────────────
    from v3.memory.episodic_store import compute_source_hash
    trace_issues = 0
    for r in records:
        expected_sh = compute_source_hash(
            r.execution_id, r.graph_hash, r.event_ids,
        )
        if r.source_hash != expected_sh:
            trace_issues += 1
            issues.append(
                f"Record {r.memory_id}: source_hash trace link broken "
                f"(stored={r.source_hash}, computed={expected_sh})"
            )
    checks["all_trace_linked"] = trace_issues == 0

    # ── 8: Memory is not truth source ─────────────────────────────────
    # Every record must have a non-empty source_hash → events are upstream
    no_source = sum(1 for r in records if not r.source_hash)
    checks["memory_not_truth_source"] = no_source == 0
    if no_source > 0:
        issues.append(f"{no_source} records have no source (would be truth source)")

    # ── 9: All records have valid candidate_ids ───────────────────────
    no_cid = sum(1 for r in records if not r.candidate_id)
    checks["all_have_candidate_id"] = no_cid == 0
    if no_cid > 0:
        issues.append(f"{no_cid} records missing candidate_id")

    # ── 10: All records have content ──────────────────────────────────
    no_content = sum(1 for r in records if not r.content)
    checks["all_have_content"] = no_content == 0
    if no_content > 0:
        issues.append(f"{no_content} records missing content")

    passed = len(issues) == 0

    report = IntegrityReport(
        store_path=store.path,
        total_records=len(records),
        checks=checks,
        issues=tuple(issues),
        passed=passed,
    )

    report_hash = _compute_report_hash(report)
    return IntegrityReport(
        store_path=report.store_path,
        total_records=report.total_records,
        checks=report.checks,
        issues=report.issues,
        passed=report.passed,
        report_hash=report_hash,
    )


def _compute_report_hash(report: IntegrityReport) -> str:
    """Deterministic hash of an integrity report."""
    parts = [
        report.store_path,
        str(report.total_records),
        json.dumps(report.checks, sort_keys=True, ensure_ascii=False),
        "|".join(sorted(report.issues)),
        str(report.passed),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Quick integrity summary (for gateway/adapter use)
# ═══════════════════════════════════════════════════════════════════════

def quick_integrity_check(store: "EpisodicMemoryStore") -> bool:
    """Fast pass/fail integrity check. Returns True if store is clean."""
    report = check_integrity(store)
    return report.passed


def generate_integrity_report_json(
    store: "EpisodicMemoryStore",
    output_path: str,
) -> IntegrityReport:
    """Run integrity check and write report to JSON file. Returns report."""
    report = check_integrity(store)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report.to_json())
    return report
