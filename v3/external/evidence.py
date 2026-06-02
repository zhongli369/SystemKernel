"""
External Evidence Model — Phase 3.

Unified evidence representation for all external capability outputs.
Every external tool output is EVIDENCE, never TRUTH.

Evidence is projection-only — it records what happened, never drives
kernel behavior directly. The EventStore remains the single truth source.

Stdlib only. No external dependencies. No external tool execution.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Evidence Types
# ═══════════════════════════════════════════════════════════════════════

EVIDENCE_TYPE_CONTEXT_PACK = "context_pack"
EVIDENCE_TYPE_USAGE_REPORT = "usage_report"
EVIDENCE_TYPE_MEMORY_SIGNAL = "memory_signal"
EVIDENCE_TYPE_AGENT_RESULT = "agent_result"
EVIDENCE_TYPE_IDE_CONTEXT = "ide_context"
EVIDENCE_TYPE_SKILL_REFERENCE = "skill_reference"
EVIDENCE_TYPE_EVAL_RESULT = "eval_result"
EVIDENCE_TYPE_DIRECTION_SIGNAL = "direction_signal"
EVIDENCE_TYPE_QUALITY_SIGNAL = "quality_signal"
EVIDENCE_TYPE_GENERIC = "generic"

ALL_EVIDENCE_TYPES = (
    EVIDENCE_TYPE_CONTEXT_PACK,
    EVIDENCE_TYPE_USAGE_REPORT,
    EVIDENCE_TYPE_MEMORY_SIGNAL,
    EVIDENCE_TYPE_AGENT_RESULT,
    EVIDENCE_TYPE_IDE_CONTEXT,
    EVIDENCE_TYPE_SKILL_REFERENCE,
    EVIDENCE_TYPE_EVAL_RESULT,
    EVIDENCE_TYPE_DIRECTION_SIGNAL,
    EVIDENCE_TYPE_QUALITY_SIGNAL,
    EVIDENCE_TYPE_GENERIC,
)

# Trust levels
TRUST_LOW = "low"
TRUST_MEDIUM = "medium"
TRUST_HIGH = "high"
ALL_TRUST_LEVELS = (TRUST_LOW, TRUST_MEDIUM, TRUST_HIGH)


# ═══════════════════════════════════════════════════════════════════════
# Evidence Source
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvidenceSource:
    """Where evidence came from — the adapter and its collection context."""
    adapter_id: str = ""
    capability_type: str = ""
    source_uri: str = ""           # file path, URL, or service endpoint
    source_hash: str = ""          # hash of the raw source content
    collected_by: str = ""         # who/what collected (CLI user, automated, etc.)
    collection_mode: str = ""      # dry_run, inspect_only, explicit_execute, etc.
    source_trust_level: str = TRUST_LOW
    source_hash_value: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "capability_type": self.capability_type,
            "source_uri": self.source_uri,
            "source_hash": self.source_hash,
            "collected_by": self.collected_by,
            "collection_mode": self.collection_mode,
            "source_trust_level": self.source_trust_level,
            "source_hash_value": self.source_hash_value,
        }


# ═══════════════════════════════════════════════════════════════════════
# Evidence Provenance
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvidenceProvenance:
    """Chain of hashes proving where evidence came from and how it was produced."""
    input_hash: str = ""
    output_hash: str = ""
    command_hash: str = ""          # hash of the command/tool invocation
    adapter_spec_hash: str = ""     # hash of the ExternalCapabilityAdapterSpec
    registry_hash: str = ""         # hash of the CapabilityRegistry at collection time
    collected_at: str = ""
    provenance_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "command_hash": self.command_hash,
            "adapter_spec_hash": self.adapter_spec_hash,
            "registry_hash": self.registry_hash,
            "collected_at": self.collected_at,
            "provenance_hash": self.provenance_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Evidence Record
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvidenceRecord:
    """One evidence record — the output of one external capability execution.

    truth_source is ALWAYS False. Evidence records what happened; the
    kernel's EventStore is the only truth.
    """
    evidence_id: str = ""
    evidence_type: str = EVIDENCE_TYPE_GENERIC
    source: Optional[EvidenceSource] = None
    provenance: Optional[EvidenceProvenance] = None
    payload_summary: str = ""       # truncated summary of the actual output
    payload_ref: str = ""           # path or URI to full output if stored externally
    risk_flags: Tuple[str, ...] = ()
    confidence: float = 0.0
    truth_source: bool = False      # MUST always be False — enforced
    evidence_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "source": self.source.to_dict() if self.source else None,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "payload_summary": self.payload_summary,
            "payload_ref": self.payload_ref,
            "risk_flags": list(self.risk_flags),
            "confidence": self.confidence,
            "truth_source": self.truth_source,
            "evidence_hash": self.evidence_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Evidence Bundle
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvidenceBundle:
    """A collection of evidence records bundled for storage or reporting.

    Records are sorted deterministically by evidence_id.
    truth_source is ALWAYS False at the bundle level.
    """
    bundle_id: str = ""
    records: Tuple[EvidenceRecord, ...] = ()
    bundle_type: str = ""
    created_at: str = ""
    truth_source: bool = False      # MUST always be False — enforced
    bundle_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "bundle_id": self.bundle_id,
            "records": [r.to_dict() for r in self.records],
            "bundle_type": self.bundle_type,
            "created_at": self.created_at,
            "truth_source": self.truth_source,
            "bundle_hash": self.bundle_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Evidence Validation Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvidenceValidationReport:
    """Result of validating an evidence bundle or record."""
    valid: bool = True
    record_count: int = 0
    invalid_records: Tuple[str, ...] = ()
    missing_provenance: Tuple[str, ...] = ()
    truth_source_violations: Tuple[str, ...] = ()
    duplicate_evidence_ids: Tuple[str, ...] = ()
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "record_count": self.record_count,
            "invalid_records": list(self.invalid_records),
            "missing_provenance": list(self.missing_provenance),
            "truth_source_violations": list(self.truth_source_violations),
            "duplicate_evidence_ids": list(self.duplicate_evidence_ids),
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash Computation
# ═══════════════════════════════════════════════════════════════════════

def compute_evidence_hash(obj, prefix: str = "") -> str:
    """Deterministic SHA-256 hash for evidence objects.

    Same input → same hash. Always. Uses sorted JSON keys.
    """
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        # Remove the hash field itself to avoid circularity
        for key in ("evidence_hash", "source_hash_value", "provenance_hash",
                     "bundle_hash", "report_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)

    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    full_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if prefix:
        return f"{prefix}:{full_hash[:16]}"
    return full_hash[:16]


# ═══════════════════════════════════════════════════════════════════════
# Constructors
# ═══════════════════════════════════════════════════════════════════════

def make_evidence_record(
    adapter_id: str,
    evidence_type: str,
    capability_type: str,
    input_data: dict,
    output_data: dict,
    payload_summary: str = "",
    payload_ref: str = "",
    source_uri: str = "",
    collected_by: str = "",
    collection_mode: str = "inspect_only",
    adapter_spec_hash: str = "",
    registry_hash: str = "",
    risk_flags: Tuple[str, ...] = (),
    confidence: float = 0.0,
    source_trust_level: str = TRUST_LOW,
) -> EvidenceRecord:
    """Create a deterministic EvidenceRecord from external capability output.

    evidence_id = hash(adapter_id + source_hash + output_hash) — deterministic.
    truth_source = ALWAYS False.
    """
    input_hash = compute_evidence_hash(input_data, "input")
    output_hash = compute_evidence_hash(output_data, "output")
    source_hash = compute_evidence_hash({"uri": source_uri, "adapter": adapter_id})

    now = datetime.now(timezone.utc).isoformat()

    provenance = EvidenceProvenance(
        input_hash=input_hash,
        output_hash=output_hash,
        command_hash=compute_evidence_hash({"adapter": adapter_id, "mode": collection_mode}),
        adapter_spec_hash=adapter_spec_hash,
        registry_hash=registry_hash,
        collected_at=now,
    )
    object.__setattr__(provenance, "provenance_hash",
                       compute_evidence_hash(provenance, "prov"))

    source = EvidenceSource(
        adapter_id=adapter_id,
        capability_type=capability_type,
        source_uri=source_uri,
        source_hash=source_hash,
        collected_by=collected_by,
        collection_mode=collection_mode,
        source_trust_level=source_trust_level,
    )
    object.__setattr__(source, "source_hash_value",
                       compute_evidence_hash(source, "src"))

    # Deterministic evidence_id
    evidence_id_input = f"{adapter_id}:{source_hash}:{output_hash}"
    evidence_id = hashlib.sha256(evidence_id_input.encode("utf-8")).hexdigest()[:16]

    record = EvidenceRecord(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source=source,
        provenance=provenance,
        payload_summary=payload_summary,
        payload_ref=payload_ref,
        risk_flags=risk_flags,
        confidence=confidence,
        truth_source=False,  # HARD — always False
    )
    object.__setattr__(record, "evidence_hash",
                       compute_evidence_hash(record, "evidence"))
    return record


def build_evidence_bundle(
    records: Tuple[EvidenceRecord, ...],
    bundle_type: str = "",
) -> EvidenceBundle:
    """Build an evidence bundle from records.

    Records are sorted by evidence_id. Duplicates raise ValueError.
    """
    # Check for duplicates
    ids = [r.evidence_id for r in records]
    if len(ids) != len(set(ids)):
        seen = set()
        dups = set()
        for i in ids:
            if i in seen:
                dups.add(i)
            seen.add(i)
        raise ValueError(f"Duplicate evidence_ids in bundle: {dups}")

    # Sort by evidence_id
    sorted_records = tuple(sorted(records, key=lambda r: r.evidence_id))

    now = datetime.now(timezone.utc).isoformat()
    bundle_input = ":".join(r.evidence_id for r in sorted_records)
    bundle_id = hashlib.sha256(bundle_input.encode("utf-8")).hexdigest()[:16]

    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        records=sorted_records,
        bundle_type=bundle_type,
        created_at=now,
        truth_source=False,
    )
    object.__setattr__(bundle, "bundle_hash",
                       compute_evidence_hash(bundle, "bundle"))
    return bundle


# ═══════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════

def validate_evidence_record(record: EvidenceRecord) -> EvidenceValidationReport:
    """Validate a single evidence record against contract rules."""
    violations = []
    missing_prov = []
    ts_violations = []

    if record.truth_source is not False:
        ts_violations.append(f"{record.evidence_id}: truth_source must be False")

    if record.provenance is None:
        missing_prov.append(record.evidence_id)

    if not record.evidence_id:
        violations.append("evidence_id empty")
    if record.evidence_type not in ALL_EVIDENCE_TYPES:
        violations.append(f"Unknown evidence_type: {record.evidence_type}")

    return EvidenceValidationReport(
        valid=(len(violations) == 0 and len(missing_prov) == 0
               and len(ts_violations) == 0),
        record_count=1,
        invalid_records=tuple(violations),
        missing_provenance=tuple(missing_prov),
        truth_source_violations=tuple(ts_violations),
    )


def validate_evidence_bundle(bundle: EvidenceBundle) -> EvidenceValidationReport:
    """Validate an evidence bundle against contract rules."""
    invalid = []
    missing_prov = []
    ts_violations = []
    dups = []

    if bundle.truth_source is not False:
        ts_violations.append("bundle: truth_source must be False")

    seen_ids = set()
    for r in bundle.records:
        if r.truth_source is not False:
            ts_violations.append(f"{r.evidence_id}: truth_source must be False")
        if r.provenance is None:
            missing_prov.append(r.evidence_id)
        if r.evidence_type not in ALL_EVIDENCE_TYPES:
            invalid.append(r.evidence_id)
        if r.evidence_id in seen_ids:
            dups.append(r.evidence_id)
        seen_ids.add(r.evidence_id)

    return EvidenceValidationReport(
        valid=(len(invalid) == 0 and len(missing_prov) == 0
               and len(ts_violations) == 0 and len(dups) == 0),
        record_count=len(bundle.records),
        invalid_records=tuple(invalid),
        missing_provenance=tuple(missing_prov),
        truth_source_violations=tuple(ts_violations),
        duplicate_evidence_ids=tuple(dups),
    )


# ═══════════════════════════════════════════════════════════════════════
# Adapter-Specific Converters
# ═══════════════════════════════════════════════════════════════════════

def evidence_from_context_pack_result(
    result,  # ContextPackResult
    registry_hash: str = "",
    adapter_spec_hash: str = "",
) -> EvidenceRecord:
    """Convert a ContextPackResult into an EvidenceRecord.

    The result is EVIDENCE, not truth. The context pack output is a
    developer convenience, never authoritative.
    """
    import json as _json

    payload_data = {}
    if hasattr(result, "to_dict"):
        payload_data = result.to_dict()
    elif hasattr(result, "__dict__"):
        payload_data = {k: v for k, v in result.__dict__.items()
                       if not k.startswith("_")}

    summary_parts = []
    if hasattr(result, "file_count"):
        summary_parts.append(f"files={result.file_count}")
    if hasattr(result, "total_bytes"):
        summary_parts.append(f"bytes={result.total_bytes}")
    if hasattr(result, "path"):
        summary_parts.append(f"path={result.path}")
    payload_summary = "; ".join(summary_parts) if summary_parts else "context pack result"

    return make_evidence_record(
        adapter_id="repomix_context_pack",
        evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
        capability_type="context",
        input_data={"target": getattr(result, "path", "")},
        output_data=payload_data,
        payload_summary=payload_summary,
        payload_ref=getattr(result, "path", ""),
        source_uri=getattr(result, "path", ""),
        collected_by="systemkernel",
        collection_mode="inspect_only",
        adapter_spec_hash=adapter_spec_hash,
        registry_hash=registry_hash,
        risk_flags=(),
        confidence=1.0,
        source_trust_level=TRUST_MEDIUM,
    )


def evidence_from_usage_report_summary(
    summary,  # UsageReportSummary
    registry_hash: str = "",
    adapter_spec_hash: str = "",
) -> EvidenceRecord:
    """Convert a UsageReportSummary into an EvidenceRecord.

    The summary is EVIDENCE, not truth. Cost and token data are developer
    convenience, never authoritative.
    """
    payload_data = {}
    if hasattr(summary, "to_dict"):
        payload_data = summary.to_dict()
    elif hasattr(summary, "__dict__"):
        payload_data = {k: v for k, v in summary.__dict__.items()
                       if not k.startswith("_")}

    summary_parts = []
    if hasattr(summary, "total_tokens"):
        summary_parts.append(f"tokens={summary.total_tokens}")
    if hasattr(summary, "total_cost"):
        summary_parts.append(f"cost={summary.total_cost}")
    if hasattr(summary, "cache_read_ratio"):
        summary_parts.append(f"cache_ratio={summary.cache_read_ratio}")
    payload_summary = "; ".join(summary_parts) if summary_parts else "usage report summary"

    return make_evidence_record(
        adapter_id="ccusage_usage_report",
        evidence_type=EVIDENCE_TYPE_USAGE_REPORT,
        capability_type="usage",
        input_data={"source": "ccusage_json"},
        output_data=payload_data,
        payload_summary=payload_summary,
        payload_ref="",
        source_uri="ccusage_json_output",
        collected_by="systemkernel",
        collection_mode="inspect_only",
        adapter_spec_hash=adapter_spec_hash,
        registry_hash=registry_hash,
        risk_flags=(),
        confidence=1.0,
        source_trust_level=TRUST_LOW,  # external npm tool
    )


# ═══════════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════════

def write_evidence_bundle(bundle: EvidenceBundle, path: str) -> str:
    """Write evidence bundle to JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)
    return os.path.abspath(path)


def load_evidence_bundle(path: str) -> EvidenceBundle:
    """Load evidence bundle from JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for r_data in data.get("records", []):
        src_data = r_data.get("source")
        source = EvidenceSource(**src_data) if src_data else None
        prov_data = r_data.get("provenance")
        provenance = EvidenceProvenance(**prov_data) if prov_data else None

        record = EvidenceRecord(
            evidence_id=r_data.get("evidence_id", ""),
            evidence_type=r_data.get("evidence_type", EVIDENCE_TYPE_GENERIC),
            source=source,
            provenance=provenance,
            payload_summary=r_data.get("payload_summary", ""),
            payload_ref=r_data.get("payload_ref", ""),
            risk_flags=tuple(r_data.get("risk_flags", [])),
            confidence=r_data.get("confidence", 0.0),
            truth_source=r_data.get("truth_source", False),
            evidence_hash=r_data.get("evidence_hash", ""),
        )
        records.append(record)

    return EvidenceBundle(
        bundle_id=data.get("bundle_id", ""),
        records=tuple(records),
        bundle_type=data.get("bundle_type", ""),
        created_at=data.get("created_at", ""),
        truth_source=data.get("truth_source", False),
        bundle_hash=data.get("bundle_hash", ""),
    )
