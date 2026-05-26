"""
Provenance — Deterministic traceability chain for recall results.

Phase 4D-4: Every recall result carries a full provenance chain linking
back through the memory stack to the source events.

Chain: RecallResult → EpisodicMemoryRecord → MemoryCandidate → source events
         ↓                   ↓                    ↓               ↓
      recall_hash       record_hash         candidate_id     event_ids
                         source_hash                         execution_id
                                                            graph_hash

Provenance is the audit trail. It proves that memory retrieval is a
projection, not a truth source. Every link in the chain is verifiable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryRecord


# ═══════════════════════════════════════════════════════════════════════
# RecallProvenance
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RecallProvenance:
    """Immutable provenance chain for a single recall result.

    Every field traces back through the memory stack to source events.
    trace_valid is True only when all links in the chain are verified.

    Fields:
        memory_id: The episodic memory record ID
        record_hash: Content-addressed hash of the episodic record
        source_hash: Hash linking record to graph + events + execution
        execution_id: Which kernel execution produced this record
        graph_hash: Hash of the RuntimeGraph at write time
        event_ids: Source event IDs that contributed to the record
        candidate_id: Links to the original MemoryCandidate
        candidate_type: From CandidateType enum
        trace_valid: Whether all provenance links are verified intact
        provenance_hash: Deterministic hash of all provenance fields
    """

    memory_id: str
    record_hash: str
    source_hash: str
    execution_id: str
    graph_hash: str
    event_ids: Tuple[str, ...]
    candidate_id: str = ""
    candidate_type: str = ""
    trace_valid: bool = False
    provenance_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "record_hash": self.record_hash,
            "source_hash": self.source_hash,
            "execution_id": self.execution_id,
            "graph_hash": self.graph_hash,
            "event_ids": list(self.event_ids),
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "trace_valid": self.trace_valid,
            "provenance_hash": self.provenance_hash,
        }

    @staticmethod
    def from_dict(d: dict) -> "RecallProvenance":
        return RecallProvenance(
            memory_id=d.get("memory_id", ""),
            record_hash=d.get("record_hash", ""),
            source_hash=d.get("source_hash", ""),
            execution_id=d.get("execution_id", ""),
            graph_hash=d.get("graph_hash", ""),
            event_ids=tuple(d.get("event_ids", [])),
            candidate_id=d.get("candidate_id", ""),
            candidate_type=d.get("candidate_type", ""),
            trace_valid=d.get("trace_valid", False),
            provenance_hash=d.get("provenance_hash", ""),
        )


# ═══════════════════════════════════════════════════════════════════════
# Provenance hash (deterministic)
# ═══════════════════════════════════════════════════════════════════════

def compute_provenance_hash(prov: RecallProvenance) -> str:
    """Deterministic SHA-256 hash of provenance fields.

    Excludes provenance_hash itself and trace_valid (which is a verification
    property, not part of the provenance chain data).
    """
    parts = [
        prov.memory_id,
        prov.record_hash,
        prov.source_hash,
        prov.execution_id,
        prov.graph_hash,
        "|".join(sorted(prov.event_ids)),
        prov.candidate_id,
        prov.candidate_type,
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Provenance extraction (from EpisodicMemoryRecord)
# ═══════════════════════════════════════════════════════════════════════

def extract_provenance(record: "EpisodicMemoryRecord") -> RecallProvenance:
    """Extract provenance from an EpisodicMemoryRecord.

    Builds the provenance chain from the record's existing fields.
    trace_valid is set by verify_provenance() afterward.
    """
    prov = RecallProvenance(
        memory_id=record.memory_id,
        record_hash=record.record_hash,
        source_hash=record.source_hash,
        execution_id=record.execution_id,
        graph_hash=record.graph_hash,
        event_ids=record.event_ids,
        candidate_id=record.candidate_id,
        candidate_type=record.candidate_type,
        trace_valid=False,
    )
    # Compute and embed provenance hash
    phash = compute_provenance_hash(prov)
    return RecallProvenance(
        memory_id=prov.memory_id,
        record_hash=prov.record_hash,
        source_hash=prov.source_hash,
        execution_id=prov.execution_id,
        graph_hash=prov.graph_hash,
        event_ids=prov.event_ids,
        candidate_id=prov.candidate_id,
        candidate_type=prov.candidate_type,
        trace_valid=prov.trace_valid,
        provenance_hash=phash,
    )


# ═══════════════════════════════════════════════════════════════════════
# Provenance verification
# ═══════════════════════════════════════════════════════════════════════

def verify_provenance(prov: RecallProvenance) -> bool:
    """Verify all links in a provenance chain.

    Returns True only if every required link is present and valid:
      - memory_id non-empty
      - record_hash non-empty and 16 hex chars
      - source_hash non-empty and 16 hex chars
      - execution_id non-empty
      - graph_hash non-empty
      - candidate_id non-empty
      - provenance_hash matches recomputation
    """
    if not prov.memory_id:
        return False
    if not prov.record_hash or len(prov.record_hash) != 16:
        return False
    if not prov.source_hash or len(prov.source_hash) != 16:
        return False
    if not prov.execution_id:
        return False
    if not prov.graph_hash:
        return False
    if not prov.candidate_id:
        return False
    # Provenance hash must match
    expected = compute_provenance_hash(prov)
    if prov.provenance_hash != expected:
        return False
    return True


def verify_provenance_chain(
    result_provenance: RecallProvenance,
    record: "EpisodicMemoryRecord",
) -> dict:
    """Deep verification: check provenance against the source record.

    Returns a detailed verification report dict.
    """
    checks: dict[str, bool | str] = {}
    issues: list[str] = []

    # Match memory_id
    checks["memory_id_match"] = result_provenance.memory_id == record.memory_id
    if not checks["memory_id_match"]:
        issues.append("memory_id mismatch between provenance and record")

    # Match record_hash
    checks["record_hash_match"] = result_provenance.record_hash == record.record_hash
    if not checks["record_hash_match"]:
        issues.append("record_hash mismatch")

    # Match source_hash
    checks["source_hash_match"] = result_provenance.source_hash == record.source_hash
    if not checks["source_hash_match"]:
        issues.append("source_hash mismatch")

    # Match execution_id
    checks["execution_id_match"] = result_provenance.execution_id == record.execution_id
    if not checks["execution_id_match"]:
        issues.append("execution_id mismatch")

    # Match graph_hash
    checks["graph_hash_match"] = result_provenance.graph_hash == record.graph_hash
    if not checks["graph_hash_match"]:
        issues.append("graph_hash mismatch")

    # Match candidate_id
    checks["candidate_id_match"] = result_provenance.candidate_id == record.candidate_id
    if not checks["candidate_id_match"]:
        issues.append("candidate_id mismatch")

    # Match candidate_type
    checks["candidate_type_match"] = result_provenance.candidate_type == record.candidate_type
    if not checks["candidate_type_match"]:
        issues.append("candidate_type mismatch")

    # Record has source_hash → events are upstream
    checks["events_are_source_of_truth"] = bool(record.source_hash)
    if not checks["events_are_source_of_truth"]:
        issues.append("record has no source_hash (would be truth source)")

    # Record has execution_id
    checks["has_execution_id"] = bool(record.execution_id)
    if not checks["has_execution_id"]:
        issues.append("record has no execution_id")

    # Record has graph_hash
    checks["has_graph_hash"] = bool(record.graph_hash)
    if not checks["has_graph_hash"]:
        issues.append("record has no graph_hash")

    # Source hash traceability: recompute from record fields
    from v3.memory.episodic_store import compute_source_hash
    expected_sh = compute_source_hash(
        record.execution_id, record.graph_hash, record.event_ids,
    )
    checks["source_hash_traceable"] = record.source_hash == expected_sh
    if not checks["source_hash_traceable"]:
        issues.append(
            f"source_hash not traceable: stored={record.source_hash}, "
            f"computed={expected_sh}"
        )

    # Provenance hash stable
    expected_ph = compute_provenance_hash(result_provenance)
    checks["provenance_hash_stable"] = result_provenance.provenance_hash == expected_ph
    if not checks["provenance_hash_stable"]:
        issues.append("provenance_hash not stable")

    valid = len(issues) == 0 and all(
        v for k, v in checks.items() if isinstance(v, bool)
    )

    return {
        "checks": checks,
        "issues": issues,
        "valid": valid,
        "provenance_hash": result_provenance.provenance_hash,
    }
