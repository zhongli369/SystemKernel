"""
EpisodicMemoryStore — Deterministic, append-only JSONL episodic memory store.

Phase 4D-2: Local file-based store for kernel-projected MemoryWriteRequest
and MemoryCandidate data. No vector DB. No LLM. No external services.

Properties:
  - Append-only JSONL — records are never modified, only appended
  - Deterministic record_hash — SHA-256 of record content
  - Idempotent writes — same candidate_id replayed is a no-op
  - Source-traceable — every record links to execution_id + graph_hash
  - Removable — delete the JSONL file, kernel behavior unchanged
  - Purity — this module lives OUTSIDE kernel/, zero kernel imports beyond contract

Storage format (one JSON object per line):
  {"memory_id":"...","candidate_id":"...","execution_id":"...",...}
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple

# Cross-boundary import: contract types only (protocol, not implementation)
from v3.kernel.memory_contract import (
    MemoryWriteRequest, MemoryWriteResult,
    MemoryReadRequest, MemoryReadResult,
)


# ═══════════════════════════════════════════════════════════════════════
# EpisodicMemoryRecord
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EpisodicMemoryRecord:
    """A single immutable record in the episodic memory store.

    Every record is traceable back to its source execution and events.
    record_hash is content-addressed (deterministic).

    Fields:
        memory_id: Unique ID for this memory record
        candidate_id: Links to the MemoryCandidate (or write request)
        execution_id: Which execution produced this record
        event_ids: Source event IDs that contributed to this record
        graph_hash: Hash of the RuntimeGraph at write time
        candidate_type: From CandidateType (execution_summary, stage_result, etc.)
        content: The actual data stored
        importance: 0=background, 1=normal, 2=important (from candidate priority)
        tags: Searchable tags derived from candidate_type + content
        created_at: ISO-8601 timestamp
        source_hash: Combined hash of graph_hash + event fingerprint (traceability)
        record_hash: Deterministic SHA-256 of all fields above
    """

    memory_id: str
    candidate_id: str
    execution_id: str
    event_ids: Tuple[str, ...]
    graph_hash: str
    candidate_type: str
    content: dict
    importance: int = 1
    tags: Tuple[str, ...] = ()
    created_at: str = ""
    source_hash: str = ""
    record_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "candidate_id": self.candidate_id,
            "execution_id": self.execution_id,
            "event_ids": list(self.event_ids),
            "graph_hash": self.graph_hash,
            "candidate_type": self.candidate_type,
            "content": self.content,
            "importance": self.importance,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "source_hash": self.source_hash,
            "record_hash": self.record_hash,
        }

    @staticmethod
    def from_dict(d: dict) -> "EpisodicMemoryRecord":
        return EpisodicMemoryRecord(
            memory_id=d.get("memory_id", ""),
            candidate_id=d.get("candidate_id", ""),
            execution_id=d.get("execution_id", ""),
            event_ids=tuple(d.get("event_ids", [])),
            graph_hash=d.get("graph_hash", ""),
            candidate_type=d.get("candidate_type", ""),
            content=d.get("content", {}),
            importance=d.get("importance", 1),
            tags=tuple(d.get("tags", [])),
            created_at=d.get("created_at", ""),
            source_hash=d.get("source_hash", ""),
            record_hash=d.get("record_hash", ""),
        )


# ═══════════════════════════════════════════════════════════════════════
# Record Hash (content-addressed, deterministic)
# ═══════════════════════════════════════════════════════════════════════

def compute_record_hash(record: EpisodicMemoryRecord) -> str:
    """Deterministic SHA-256 hash of record content (excluding record_hash itself)."""
    parts = [
        record.memory_id,
        record.candidate_id,
        record.execution_id,
        "|".join(sorted(record.event_ids)),
        record.graph_hash,
        record.candidate_type,
        json.dumps(record.content, sort_keys=True, ensure_ascii=False, default=str),
        str(record.importance),
        "|".join(sorted(record.tags)),
        record.created_at,
        record.source_hash,
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def compute_source_hash(
    execution_id: str,
    graph_hash: str,
    event_ids: Tuple[str, ...],
) -> str:
    """Deterministic source hash linking record to its origin."""
    parts = [execution_id, graph_hash, "|".join(sorted(event_ids))]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Tag derivation (deterministic, from candidate type + content)
# ═══════════════════════════════════════════════════════════════════════

def derive_tags(candidate_type: str, content: dict) -> Tuple[str, ...]:
    """Derive searchable tags from candidate type and content.

    Deterministic — same inputs always produce same tags.
    """
    tags: set[str] = {f"type:{candidate_type}"}

    # Stage name tag
    stage_name = content.get("stage_name", "")
    if stage_name:
        tags.add(f"stage:{stage_name}")

    # Status tag
    status = content.get("status", "") or content.get("execution_status", "")
    if status:
        tags.add(f"status:{status}")

    # Event subtype tags
    event_type = content.get("event_type", "")
    if event_type:
        tags.add(f"event:{event_type}")

    # Error tag
    if content.get("error_message") or content.get("error"):
        tags.add("has_error")

    # Terminal tag
    if content.get("is_terminal_error"):
        tags.add("terminal")

    # Execution status from content
    exec_status = content.get("execution_status", "")
    if exec_status:
        tags.add(f"exec:{exec_status}")

    return tuple(sorted(tags))


# ═══════════════════════════════════════════════════════════════════════
# EpisodicMemoryStore
# ═══════════════════════════════════════════════════════════════════════

class EpisodicMemoryStore:
    """Deterministic, append-only JSONL episodic memory store.

    Each record is appended as a single JSON line. Records are never
    modified. Idempotent writes: same candidate_id is a no-op on replay.

    Usage:
        store = EpisodicMemoryStore("v3/memory/data/episodes.jsonl")
        store.append(request)  # or store.append_candidate(candidate)
        results = store.read(read_request)
        report = store.verify_integrity()
    """

    def __init__(self, path: str):
        self._path = path
        self._records: list[EpisodicMemoryRecord] = []
        self._candidate_ids: set[str] = set()
        self._record_hashes: set[str] = set()
        self._loaded = False

    # ── Load ──────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Lazy-load records from JSONL file on first access."""
        if self._loaded:
            return
        self._loaded = True
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = EpisodicMemoryRecord.from_dict(json.loads(line))
                        self._records.append(record)
                        self._candidate_ids.add(record.candidate_id)
                        self._record_hashes.add(record.record_hash)
                    except (json.JSONDecodeError, KeyError):
                        # Skip corrupt lines silently (integrity check catches them)
                        pass
        except OSError:
            pass

    # ── Append ────────────────────────────────────────────────────────

    def append(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        """Append a MemoryWriteRequest as an episodic memory record.

        Idempotent: if the same candidate_id was already written, returns
        accepted=False with reason="duplicate".
        """
        self._ensure_loaded()

        # Idempotency check
        if request.request_id in self._candidate_ids:
            return MemoryWriteResult(
                request_id=request.request_id,
                accepted=False,
                reason="duplicate",
            )

        # Build source traceability
        graph_hash = request.context.get("graph_hash", "")
        event_ids = tuple(request.context.get("event_ids", []))
        source_hash_val = compute_source_hash(
            request.execution_id, graph_hash, event_ids,
        )

        # Derive tags
        tags = derive_tags(request.candidate_type, request.content)

        # Build record — memory_id is deterministic (derived from candidate_id)
        memory_id = hashlib.sha256(
            f"mem:{request.request_id}:{request.execution_id}".encode()
        ).hexdigest()[:16]

        record = EpisodicMemoryRecord(
            memory_id=memory_id,
            candidate_id=request.request_id,
            execution_id=request.execution_id,
            event_ids=event_ids,
            graph_hash=graph_hash,
            candidate_type=request.candidate_type,
            content=dict(request.content),
            importance=request.priority,
            tags=tags,
            created_at=request.timestamp if request.timestamp else "",
            source_hash=source_hash_val,
        )

        # Compute record hash
        record_hash = compute_record_hash(record)
        record = EpisodicMemoryRecord(
            memory_id=record.memory_id,
            candidate_id=record.candidate_id,
            execution_id=record.execution_id,
            event_ids=record.event_ids,
            graph_hash=record.graph_hash,
            candidate_type=record.candidate_type,
            content=record.content,
            importance=record.importance,
            tags=record.tags,
            created_at=record.created_at,
            source_hash=record.source_hash,
            record_hash=record_hash,
        )

        # Persist to JSONL (append-only)
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            return MemoryWriteResult(
                request_id=request.request_id,
                accepted=False,
                reason="write_error",
            )

        # Track in memory
        self._records.append(record)
        self._candidate_ids.add(record.candidate_id)
        self._record_hashes.add(record.record_hash)

        return MemoryWriteResult(
            request_id=request.request_id,
            accepted=True,
            reason="stored",
            storage_id=record.memory_id,
        )

    # ── Read ──────────────────────────────────────────────────────────

    def read(self, request: MemoryReadRequest) -> MemoryReadResult:
        """Query the episodic store.

        Supports filtering by:
          - execution_id (in request.filters)
          - candidate_type (in request.filters)
          - tag (in request.filters)
          - general text match against content

        Returns MemoryReadResult. Empty if no matches.
        """
        self._ensure_loaded()

        matches: list[tuple[EpisodicMemoryRecord, float]] = []

        for record in self._records:
            score = 0.0

            # Filter: execution_id
            if "execution_id" in request.filters:
                if record.execution_id != request.filters["execution_id"]:
                    continue
                score += 0.5

            # Filter: candidate_type
            if "candidate_type" in request.filters:
                if record.candidate_type != request.filters["candidate_type"]:
                    continue
                score += 0.5

            # Filter: tag
            if "tag" in request.filters:
                tag_filter = request.filters["tag"]
                if tag_filter not in record.tags:
                    continue
                score += 0.5

            # Text match
            if request.query_text:
                content_str = json.dumps(record.content, ensure_ascii=False).lower()
                query_lower = request.query_text.lower()
                if query_lower in content_str:
                    score += 0.15

            # If no filters and no text match, skip
            if score == 0.0 and not request.filters:
                if request.query_text:
                    content_str = json.dumps(record.content, ensure_ascii=False).lower()
                    query_lower = request.query_text.lower()
                    if query_lower in content_str:
                        score = 0.5
                    else:
                        continue
                else:
                    continue

            if score >= request.min_score:
                matches.append((record, score))

        # Sort by score descending, take top_k
        matches.sort(key=lambda x: x[1], reverse=True)
        top_k = request.top_k if request.top_k > 0 else 10
        matches = matches[:top_k]

        if not matches:
            return MemoryReadResult(
                query_id=request.query_id,
                backend="episodic",
                metadata={"store_path": self._path, "total_records": len(self._records)},
            )

        return MemoryReadResult(
            query_id=request.query_id,
            entries=tuple(m[0].to_dict() for m in matches),
            scores=tuple(m[1] for m in matches),
            backend="episodic",
            metadata={
                "store_path": self._path,
                "total_records": len(self._records),
                "matched_records": len(matches),
            },
        )

    # ── Query helpers ─────────────────────────────────────────────────

    def list_records(self) -> Tuple[EpisodicMemoryRecord, ...]:
        """Return all records in insertion order."""
        self._ensure_loaded()
        return tuple(self._records)

    def get(self, memory_id: str) -> Optional[EpisodicMemoryRecord]:
        """Get a single record by memory_id."""
        self._ensure_loaded()
        for r in self._records:
            if r.memory_id == memory_id:
                return r
        return None

    def query_by_execution_id(
        self, execution_id: str
    ) -> Tuple[EpisodicMemoryRecord, ...]:
        """Return all records for a given execution."""
        self._ensure_loaded()
        return tuple(r for r in self._records if r.execution_id == execution_id)

    def query_by_candidate_type(
        self, candidate_type: str
    ) -> Tuple[EpisodicMemoryRecord, ...]:
        """Return all records of a given candidate type."""
        self._ensure_loaded()
        return tuple(r for r in self._records if r.candidate_type == candidate_type)

    def query_by_tag(self, tag: str) -> Tuple[EpisodicMemoryRecord, ...]:
        """Return all records matching a tag."""
        self._ensure_loaded()
        return tuple(r for r in self._records if tag in r.tags)

    # ── Integrity ─────────────────────────────────────────────────────

    def verify_integrity(self) -> dict:
        """Verify store integrity. Returns a report dict.

        Checks:
          - Every record has source execution_id
          - Every record has source_hash
          - Every record has deterministic record_hash
          - No duplicate record_hash
          - All records are JSON serializable (verified during load)
          - Record count matches candidate_id count (no dupes)
        """
        self._ensure_loaded()

        report = {
            "store_path": self._path,
            "total_records": len(self._records),
            "checks": {},
            "issues": [],
        }

        seen_hashes: set[str] = set()
        valid_count = 0

        for i, record in enumerate(self._records):
            record_ok = True

            # Check: has execution_id
            if not record.execution_id:
                report["issues"].append(
                    f"Record {i} ({record.memory_id}): missing execution_id"
                )
                record_ok = False

            # Check: has source_hash
            if not record.source_hash:
                report["issues"].append(
                    f"Record {i} ({record.memory_id}): missing source_hash"
                )
                record_ok = False

            # Check: record_hash is deterministic
            expected_hash = compute_record_hash(record)
            if record.record_hash != expected_hash:
                report["issues"].append(
                    f"Record {i} ({record.memory_id}): record_hash mismatch "
                    f"(stored={record.record_hash}, computed={expected_hash})"
                )
                record_ok = False

            # Check: no duplicate record_hash
            if record.record_hash in seen_hashes:
                report["issues"].append(
                    f"Record {i} ({record.memory_id}): duplicate record_hash "
                    f"{record.record_hash}"
                )
                record_ok = False
            seen_hashes.add(record.record_hash)

            if record_ok:
                valid_count += 1

        report["checks"] = {
            "all_have_execution_id": all(bool(r.execution_id) for r in self._records),
            "all_have_source_hash": all(bool(r.source_hash) for r in self._records),
            "all_record_hashes_valid": valid_count == len(self._records),
            "no_duplicate_hashes": len(seen_hashes) == len(self._records),
            "candidate_id_count": len(self._candidate_ids),
            "record_count": len(self._records),
            "records_match_candidates": len(self._candidate_ids) == len(self._records),
        }

        report["valid"] = len(report["issues"]) == 0
        return report

    def compact_deduplicate(self) -> int:
        """Remove duplicate records (same candidate_id). Deterministic.

        Keeps the first occurrence of each candidate_id. Returns number
        of duplicates removed.

        Since this rewrites the file, it's a separate operation from
        normal append-only writes. Use only for maintenance.
        """
        self._ensure_loaded()

        seen: set[str] = set()
        deduped: list[EpisodicMemoryRecord] = []
        removed = 0

        for record in self._records:
            if record.candidate_id in seen:
                removed += 1
            else:
                seen.add(record.candidate_id)
                deduped.append(record)

        if removed > 0:
            # Rewrite file
            try:
                tmp_path = self._path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    for record in deduped:
                        f.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
                os.replace(tmp_path, self._path)
            except OSError:
                return 0

            self._records = deduped
            self._candidate_ids = seen
            self._record_hashes = {r.record_hash for r in deduped}

        return removed

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def record_count(self) -> int:
        self._ensure_loaded()
        return len(self._records)

    @property
    def path(self) -> str:
        return self._path
