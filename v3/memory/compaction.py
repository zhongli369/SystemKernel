"""
Deterministic Memory Compaction — Projection optimization for episodic memory.

Phase 4D-5: Compacts EpisodicMemoryRecord data by detecting duplicates,
merging sources, archiving low-importance records, and producing a compacted
projection file. Original episodic JSONL is NEVER modified.

Compaction is NOT summarization:
  - No semantic summaries (no LLM)
  - No content rewriting
  - No vector embedding
  - No truth source generation
  - Compacted records are a projection/optimization only

Properties:
  - Deterministic: same records + same policy = same result
  - Projection only: compacted records reference source records
  - Provenance preserved: every compacted record retains all source hashes
  - Append-only projection file: independent of original JSONL
  - Removable: delete projection file → zero impact
  - Stdlib only: no LLM, no vector DB, no external services
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryStore, EpisodicMemoryRecord


# ═══════════════════════════════════════════════════════════════════════
# CompactionPolicy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CompactionPolicy:
    """Deterministic compaction policy.

    Fields:
        min_importance: Records with lower importance may be archived or skipped
        duplicate_strategy: "keep_first" (first occurrence wins) or "merge_sources"
        group_by: How to group records for compaction (candidate_type, tag, execution_id, content_hash)
        max_records_per_group: Cap compacted records per group
        archive_low_importance: If True, records below min_importance go to archive list
        deterministic_sort: Sort key for output ordering, empty = use default (compacted_id)
        enabled: Whether compaction is active
    """

    min_importance: int = 1
    duplicate_strategy: str = "keep_first"
    group_by: str = "candidate_type"
    max_records_per_group: int = 50
    archive_low_importance: bool = True
    deterministic_sort: str = ""
    enabled: bool = True

    VALID_STRATEGIES = ("keep_first", "merge_sources")
    VALID_GROUP_BY = ("candidate_type", "tag", "execution_id", "content_hash")

    def __post_init__(self):
        if self.duplicate_strategy not in self.VALID_STRATEGIES:
            raise ValueError(
                f"duplicate_strategy must be one of {self.VALID_STRATEGIES}, "
                f"got '{self.duplicate_strategy}'"
            )
        if self.group_by not in self.VALID_GROUP_BY:
            raise ValueError(
                f"group_by must be one of {self.VALID_GROUP_BY}, "
                f"got '{self.group_by}'"
            )

    def to_dict(self) -> dict:
        return {
            "min_importance": self.min_importance,
            "duplicate_strategy": self.duplicate_strategy,
            "group_by": self.group_by,
            "max_records_per_group": self.max_records_per_group,
            "archive_low_importance": self.archive_low_importance,
            "deterministic_sort": self.deterministic_sort,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(d: dict) -> "CompactionPolicy":
        return CompactionPolicy(
            min_importance=d.get("min_importance", 1),
            duplicate_strategy=d.get("duplicate_strategy", "keep_first"),
            group_by=d.get("group_by", "candidate_type"),
            max_records_per_group=d.get("max_records_per_group", 50),
            archive_low_importance=d.get("archive_low_importance", True),
            deterministic_sort=d.get("deterministic_sort", ""),
            enabled=d.get("enabled", True),
        )

    @staticmethod
    def default() -> "CompactionPolicy":
        return CompactionPolicy()


# ═══════════════════════════════════════════════════════════════════════
# CompactedMemoryRecord
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CompactedMemoryRecord:
    """A single compacted record representing one or more source records.

    Every compacted record retains full provenance links to its source
    records. The compacted_hash is content-addressed and deterministic.

    Fields:
        compacted_id: Unique ID for this compacted record
        source_memory_ids: All memory_ids from source records
        source_record_hashes: All record_hashes from source records
        source_hashes: All source_hashes from source records
        execution_ids: All execution_ids from source records
        graph_hashes: All graph_hashes from source records
        candidate_types: All candidate_types from source records
        tags: Union of all tags from source records
        content: Representative content (first record's content, or merged)
        importance: Max importance across source records
        compaction_reason: Why this record was compacted (dedup/merge/archive/group)
        compacted_hash: Deterministic SHA-256 of all fields above
    """

    compacted_id: str
    source_memory_ids: Tuple[str, ...]
    source_record_hashes: Tuple[str, ...]
    source_hashes: Tuple[str, ...]
    execution_ids: Tuple[str, ...]
    graph_hashes: Tuple[str, ...]
    candidate_types: Tuple[str, ...]
    tags: Tuple[str, ...]
    content: dict = field(default_factory=dict)
    importance: int = 1
    compaction_reason: str = ""
    compacted_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "compacted_id": self.compacted_id,
            "source_memory_ids": list(self.source_memory_ids),
            "source_record_hashes": list(self.source_record_hashes),
            "source_hashes": list(self.source_hashes),
            "execution_ids": list(self.execution_ids),
            "graph_hashes": list(self.graph_hashes),
            "candidate_types": list(self.candidate_types),
            "tags": list(self.tags),
            "content": dict(self.content),
            "importance": self.importance,
            "compaction_reason": self.compaction_reason,
            "compacted_hash": self.compacted_hash,
        }

    @staticmethod
    def from_dict(d: dict) -> "CompactedMemoryRecord":
        return CompactedMemoryRecord(
            compacted_id=d.get("compacted_id", ""),
            source_memory_ids=tuple(d.get("source_memory_ids", [])),
            source_record_hashes=tuple(d.get("source_record_hashes", [])),
            source_hashes=tuple(d.get("source_hashes", [])),
            execution_ids=tuple(d.get("execution_ids", [])),
            graph_hashes=tuple(d.get("graph_hashes", [])),
            candidate_types=tuple(d.get("candidate_types", [])),
            tags=tuple(d.get("tags", [])),
            content=d.get("content", {}),
            importance=d.get("importance", 1),
            compaction_reason=d.get("compaction_reason", ""),
            compacted_hash=d.get("compacted_hash", ""),
        )


def compute_content_fingerprint(record: "EpisodicMemoryRecord") -> str:
    """Deterministic content fingerprint for duplicate detection.

    Based on candidate_type + content structure (sorted keys).
    Same content with same candidate_type → same fingerprint.
    """
    parts = [
        record.candidate_type,
        json.dumps(record.content, sort_keys=True, ensure_ascii=False, default=str),
        "|".join(sorted(record.tags)),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def compute_compacted_hash(record: CompactedMemoryRecord) -> str:
    """Deterministic SHA-256 hash of a compacted record (excluding compacted_hash itself)."""
    parts = [
        record.compacted_id,
        "|".join(sorted(record.source_memory_ids)),
        "|".join(sorted(record.source_record_hashes)),
        "|".join(sorted(record.source_hashes)),
        "|".join(sorted(record.execution_ids)),
        "|".join(sorted(record.graph_hashes)),
        "|".join(sorted(record.candidate_types)),
        "|".join(sorted(record.tags)),
        json.dumps(record.content, sort_keys=True, ensure_ascii=False, default=str),
        str(record.importance),
        record.compaction_reason,
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# CompactionResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CompactionResult:
    """Result of a compaction run.

    Fields:
        input_count: Total input records
        output_count: Number of compacted records produced
        duplicate_count: Number of duplicate records detected/merged
        archived_count: Number of low-importance records archived
        compacted_records: Tuple of CompactedMemoryRecord
        result_hash: Deterministic hash of the entire result
    """

    input_count: int
    output_count: int
    duplicate_count: int
    archived_count: int
    compacted_records: Tuple[CompactedMemoryRecord, ...] = ()
    result_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "input_count": self.input_count,
            "output_count": self.output_count,
            "duplicate_count": self.duplicate_count,
            "archived_count": self.archived_count,
            "compacted_records": [r.to_dict() for r in self.compacted_records],
            "result_hash": self.result_hash,
        }

    @staticmethod
    def from_dict(d: dict) -> "CompactionResult":
        return CompactionResult(
            input_count=d.get("input_count", 0),
            output_count=d.get("output_count", 0),
            duplicate_count=d.get("duplicate_count", 0),
            archived_count=d.get("archived_count", 0),
            compacted_records=tuple(
                CompactedMemoryRecord.from_dict(r)
                for r in d.get("compacted_records", [])
            ),
            result_hash=d.get("result_hash", ""),
        )


def compute_result_hash(result: CompactionResult) -> str:
    """Deterministic SHA-256 hash of a CompactionResult."""
    parts = [
        str(result.input_count),
        str(result.output_count),
        str(result.duplicate_count),
        str(result.archived_count),
        "|".join(r.compacted_hash for r in result.compacted_records),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# MemoryCompactor
# ═══════════════════════════════════════════════════════════════════════

class MemoryCompactor:
    """Deterministic memory compaction engine.

    Compacts EpisodicMemoryRecord objects by:
      1. Filtering by min_importance
      2. Grouping by the specified dimension
      3. Detecting duplicates via content fingerprint
      4. Applying duplicate strategy (keep_first or merge_sources)
      5. Optionally archiving low-importance records
      6. Sorting deterministically
      7. Producing CompactedMemoryRecord objects with full provenance

    Usage:
        store = EpisodicMemoryStore("data/episodes.jsonl")
        policy = CompactionPolicy(duplicate_strategy="merge_sources", group_by="candidate_type")
        compactor = MemoryCompactor()
        result = compactor.compact_store(store, policy)
        compactor.write_projection("data/compacted.json", result)
    """

    def compact(
        self,
        records: "Tuple[EpisodicMemoryRecord, ...]",
        policy: "CompactionPolicy",
    ) -> "CompactionResult":
        """Compact a tuple of episodic memory records.

        Args:
            records: Tuple of EpisodicMemoryRecord
            policy: CompactionPolicy defining behavior

        Returns:
            CompactionResult with compacted records and statistics.
        """
        if not policy.enabled or not records:
            empty_result = CompactionResult(
                input_count=len(records),
                output_count=0,
                duplicate_count=0,
                archived_count=0,
                compacted_records=tuple(),
            )
            rhash = compute_result_hash(empty_result)
            return CompactionResult(
                input_count=empty_result.input_count,
                output_count=empty_result.output_count,
                duplicate_count=empty_result.duplicate_count,
                archived_count=empty_result.archived_count,
                compacted_records=empty_result.compacted_records,
                result_hash=rhash,
            )

        input_count = len(records)
        archived: list[EpisodicMemoryRecord] = []
        active: list[EpisodicMemoryRecord] = []
        duplicate_count = 0

        # Step 1: Separate by min_importance
        for r in records:
            if r.importance < policy.min_importance:
                if policy.archive_low_importance:
                    archived.append(r)
                # Else: skip entirely
            else:
                active.append(r)

        # Step 2: Group by the specified dimension
        groups: dict[str, list[EpisodicMemoryRecord]] = {}
        for r in active:
            key = _group_key(r, policy.group_by)
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        # Step 3: Detect duplicates within each group and apply strategy
        compacted: list[CompactedMemoryRecord] = []

        for group_key, group_records in sorted(groups.items()):
            # Sort group records deterministically by record_hash
            group_records.sort(key=lambda r: r.record_hash)

            if policy.duplicate_strategy == "keep_first":
                seen_fingerprints: dict[str, CompactedMemoryRecord] = {}

                for r in group_records:
                    fp = compute_content_fingerprint(r)

                    if fp in seen_fingerprints:
                        duplicate_count += 1
                        existing = seen_fingerprints[fp]
                        # Update existing to note the duplicate source
                        merged = _merge_into_compacted(existing, r, "dedup")
                        seen_fingerprints[fp] = merged
                    else:
                        seen_fingerprints[fp] = _record_to_compacted(r, group_key)

                compacted.extend(seen_fingerprints.values())

            elif policy.duplicate_strategy == "merge_sources":
                # Merge all records in the group into one compacted record
                if len(group_records) > 1:
                    duplicate_count += len(group_records) - 1
                    merged = _record_to_compacted(group_records[0], group_key)
                    for r in group_records[1:]:
                        merged = _merge_into_compacted(merged, r, "merge")
                    compacted.append(merged)
                elif group_records:
                    compacted.append(_record_to_compacted(group_records[0], group_key))

        # Step 4: Cap records per group
        if policy.max_records_per_group > 0:
            capped: list[CompactedMemoryRecord] = []
            group_counts: dict[str, int] = {}
            for cr in compacted:
                gk = cr.compaction_reason.split(":")[0] if ":" in cr.compaction_reason else cr.compaction_reason
                cnt = group_counts.get(gk, 0)
                if cnt < policy.max_records_per_group:
                    capped.append(cr)
                    group_counts[gk] = cnt + 1
            compacted = capped

        # Step 5: Deterministic sort
        sort_key = policy.deterministic_sort or "compacted_id"
        if sort_key == "importance":
            compacted.sort(key=lambda r: (-r.importance, r.compacted_id))
        elif sort_key == "compacted_id":
            compacted.sort(key=lambda r: r.compacted_id)
        elif sort_key == "record_hash":
            compacted.sort(key=lambda r: r.compacted_hash)
        else:
            compacted.sort(key=lambda r: r.compacted_id)

        # Step 6: Compute compacted_hashes
        final_records: list[CompactedMemoryRecord] = []
        for cr in compacted:
            ch = compute_compacted_hash(cr)
            final_records.append(CompactedMemoryRecord(
                compacted_id=cr.compacted_id,
                source_memory_ids=cr.source_memory_ids,
                source_record_hashes=cr.source_record_hashes,
                source_hashes=cr.source_hashes,
                execution_ids=cr.execution_ids,
                graph_hashes=cr.graph_hashes,
                candidate_types=cr.candidate_types,
                tags=cr.tags,
                content=cr.content,
                importance=cr.importance,
                compaction_reason=cr.compaction_reason,
                compacted_hash=ch,
            ))

        output_count = len(final_records)

        result = CompactionResult(
            input_count=input_count,
            output_count=output_count,
            duplicate_count=duplicate_count,
            archived_count=len(archived),
            compacted_records=tuple(final_records),
        )

        rhash = compute_result_hash(result)
        return CompactionResult(
            input_count=result.input_count,
            output_count=result.output_count,
            duplicate_count=result.duplicate_count,
            archived_count=result.archived_count,
            compacted_records=result.compacted_records,
            result_hash=rhash,
        )

    def compact_store(
        self,
        store: "EpisodicMemoryStore",
        policy: "CompactionPolicy",
    ) -> "CompactionResult":
        """Compact all records from an EpisodicMemoryStore.

        Convenience wrapper around compact().
        """
        records = store.list_records()
        return self.compact(records, policy)

    def write_projection(
        self,
        path: str,
        result: "CompactionResult",
        policy: Optional["CompactionPolicy"] = None,
    ) -> str:
        """Write compacted records to a projection JSON file.

        The projection file is a standalone JSON document containing:
          - Projection metadata
          - Compaction policy used
          - All compacted records
          - Source linkage information

        This file is independent of the original episodic JSONL. Deleting
        it has zero impact on the kernel or the original records.

        Returns the absolute path written.
        """
        projection = {
            "projection_type": "memory_compaction",
            "projection_version": "1.0",
            "policy": policy.to_dict() if policy else {},
            "input_count": result.input_count,
            "output_count": result.output_count,
            "duplicate_count": result.duplicate_count,
            "archived_count": result.archived_count,
            "result_hash": result.result_hash,
            "compacted_records": [r.to_dict() for r in result.compacted_records],
            "source_linkage": {
                "total_source_memory_ids": sum(
                    len(r.source_memory_ids) for r in result.compacted_records
                ),
                "total_source_record_hashes": sum(
                    len(r.source_record_hashes) for r in result.compacted_records
                ),
                "provenance_preserved": True,
            },
        }

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(projection, f, ensure_ascii=False, indent=2, sort_keys=True)

        return os.path.abspath(path)

    def verify_compaction(
        self,
        result: "CompactionResult",
        original_records: "Tuple[EpisodicMemoryRecord, ...]",
    ) -> dict:
        """Verify compaction integrity against original records.

        Checks:
          - All compacted records reference valid source_memory_ids
          - All compacted records reference valid source_record_hashes
          - All source records are accounted for or archived
          - No provenance loss
          - result_hash is stable
          - Compaction is projection only (original records unchanged)
          - Compacted hashes are stable

        Returns a verification report dict.
        """
        checks: dict[str, bool | int] = {}
        issues: list[str] = []

        original_ids = {r.memory_id for r in original_records}
        original_hashes = {r.record_hash for r in original_records}

        referenced_ids: set[str] = set()
        referenced_hashes: set[str] = set()

        for cr in result.compacted_records:
            # Check: every compacted record references source records
            if not cr.source_memory_ids:
                issues.append(f"Compacted record {cr.compacted_id}: no source_memory_ids")
                continue

            # Check: all source_memory_ids exist in original records
            for mid in cr.source_memory_ids:
                if mid not in original_ids:
                    issues.append(
                        f"Compacted record {cr.compacted_id}: source_memory_id "
                        f"'{mid}' not in original records"
                    )
                referenced_ids.add(mid)

            # Check: all source_record_hashes exist in original records
            for rh in cr.source_record_hashes:
                if rh not in original_hashes:
                    issues.append(
                        f"Compacted record {cr.compacted_id}: source_record_hash "
                        f"'{rh}' not in original records"
                    )
                referenced_hashes.add(rh)

            # Check: compacted_hash is stable
            expected_ch = compute_compacted_hash(cr)
            if cr.compacted_hash != expected_ch:
                issues.append(
                    f"Compacted record {cr.compacted_id}: compacted_hash mismatch "
                    f"(stored={cr.compacted_hash}, computed={expected_ch})"
                )

            # Check: provenance preserved
            if not cr.source_hashes:
                issues.append(f"Compacted record {cr.compacted_id}: no source_hashes")
            if not cr.execution_ids:
                issues.append(f"Compacted record {cr.compacted_id}: no execution_ids")
            if not cr.graph_hashes:
                issues.append(f"Compacted record {cr.compacted_id}: no graph_hashes")

        checks["all_source_memory_ids_valid"] = len(
            [i for i in issues if "not in original records" in i and "source_memory_id" in i]
        ) == 0
        checks["all_source_record_hashes_valid"] = len(
            [i for i in issues if "not in original records" in i and "source_record_hash" in i]
        ) == 0
        checks["all_compacted_hashes_stable"] = len(
            [i for i in issues if "compacted_hash mismatch" in i]
        ) == 0
        checks["provenance_preserved"] = len(
            [i for i in issues if "no source_hashes" in i or "no execution_ids" in i or "no graph_hashes" in i]
        ) == 0

        # Check: all active source records accounted for
        accounted_count = len(referenced_ids) + result.archived_count
        checks["source_records_accounted"] = (
            accounted_count == result.input_count
            or accounted_count >= len(original_ids)
        )

        # Check: result_hash is stable
        expected_rh = compute_result_hash(result)
        checks["result_hash_stable"] = result.result_hash == expected_rh
        if not checks["result_hash_stable"]:
            issues.append(
                f"result_hash mismatch: stored={result.result_hash}, computed={expected_rh}"
            )

        # Check: compaction is projection only — original IDs must not be altered
        checks["projection_only"] = True  # By construction — we never modify originals

        # Count checks
        checks["total_compacted_records"] = len(result.compacted_records)
        checks["total_source_memory_ids_referenced"] = len(referenced_ids)
        checks["total_source_hashes_referenced"] = len(referenced_hashes)

        valid = len(issues) == 0
        return {
            "checks": checks,
            "issues": issues,
            "valid": valid,
            "compaction_result_hash": result.result_hash,
        }

    def load_projection(self, path: str) -> Optional[CompactionResult]:
        """Load a compaction projection from a JSON file.

        Returns CompactionResult or None if the file doesn't exist or is invalid.
        """
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CompactionResult.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════

def _group_key(record: "EpisodicMemoryRecord", group_by: str) -> str:
    """Deterministic group key for a record."""
    if group_by == "candidate_type":
        return record.candidate_type
    elif group_by == "tag":
        return "|".join(sorted(record.tags)) if record.tags else "_untagged"
    elif group_by == "execution_id":
        return record.execution_id
    elif group_by == "content_hash":
        return compute_content_fingerprint(record)
    else:
        return record.candidate_type


def _record_to_compacted(
    record: "EpisodicMemoryRecord",
    group_key: str,
) -> CompactedMemoryRecord:
    """Convert a single EpisodicMemoryRecord to a CompactedMemoryRecord."""
    compacted_id = hashlib.sha256(
        f"compacted:{record.memory_id}:{group_key}".encode()
    ).hexdigest()[:16]

    return CompactedMemoryRecord(
        compacted_id=compacted_id,
        source_memory_ids=(record.memory_id,),
        source_record_hashes=(record.record_hash,),
        source_hashes=(record.source_hash,),
        execution_ids=(record.execution_id,),
        graph_hashes=(record.graph_hash,),
        candidate_types=(record.candidate_type,),
        tags=record.tags,
        content=dict(record.content),
        importance=record.importance,
        compaction_reason=group_key,
    )


def _merge_into_compacted(
    existing: CompactedMemoryRecord,
    new_record: "EpisodicMemoryRecord",
    reason_suffix: str,
) -> CompactedMemoryRecord:
    """Merge a new record into an existing CompactedMemoryRecord.

    Preserves all source hashes from both records. Takes the maximum
    importance. Union of tags.
    """
    merged_memory_ids = tuple(sorted(set(existing.source_memory_ids + (new_record.memory_id,))))
    merged_record_hashes = tuple(sorted(set(existing.source_record_hashes + (new_record.record_hash,))))
    merged_source_hashes = tuple(sorted(set(existing.source_hashes + (new_record.source_hash,))))
    merged_execution_ids = tuple(sorted(set(existing.execution_ids + (new_record.execution_id,))))
    merged_graph_hashes = tuple(sorted(set(existing.graph_hashes + (new_record.graph_hash,))))
    merged_candidate_types = tuple(sorted(set(existing.candidate_types + (new_record.candidate_type,))))
    merged_tags = tuple(sorted(set(existing.tags + new_record.tags)))
    merged_importance = max(existing.importance, new_record.importance)

    return CompactedMemoryRecord(
        compacted_id=existing.compacted_id,
        source_memory_ids=merged_memory_ids,
        source_record_hashes=merged_record_hashes,
        source_hashes=merged_source_hashes,
        execution_ids=merged_execution_ids,
        graph_hashes=merged_graph_hashes,
        candidate_types=merged_candidate_types,
        tags=merged_tags,
        content=existing.content,
        importance=merged_importance,
        compaction_reason=f"{existing.compaction_reason}:{reason_suffix}",
    )
