"""
External Evidence Policy — Phase 3.

Policy rules governing how evidence is collected, validated, stored,
and redacted. The policy is a configuration object, not a runtime enforcer.
All enforcement happens at collection time (make_evidence_record,
build_evidence_bundle).

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Risk Flags (closed set)
# ═══════════════════════════════════════════════════════════════════════

RISK_FLAG_UNVERIFIED = "unverified"
RISK_FLAG_EXTERNAL_IO = "external_io"
RISK_FLAG_NETWORK_ACCESS = "network_access"
RISK_FLAG_FILE_SYSTEM_WRITE = "file_system_write"
RISK_FLAG_SUBPROCESS = "subprocess"
RISK_FLAG_USER_DATA = "user_data"
RISK_FLAG_THIRD_PARTY = "third_party"

ALL_RISK_FLAGS = (
    RISK_FLAG_UNVERIFIED,
    RISK_FLAG_EXTERNAL_IO,
    RISK_FLAG_NETWORK_ACCESS,
    RISK_FLAG_FILE_SYSTEM_WRITE,
    RISK_FLAG_SUBPROCESS,
    RISK_FLAG_USER_DATA,
    RISK_FLAG_THIRD_PARTY,
)


# ═══════════════════════════════════════════════════════════════════════
# Evidence Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvidencePolicy:
    """Policy configuration for evidence collection and validation.

    This defines the rules that evidence records and bundles must satisfy.
    It is a frozen configuration, not a runtime enforcer — enforcement
    is applied by validate_against_policy() at collection time.
    """
    max_payload_summary_bytes: int = 500
    require_provenance: bool = True
    allow_low_trust_sources: bool = True
    max_records_per_bundle: int = 1000
    forbidden_risk_flags: Tuple[str, ...] = ()
    policy_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "max_payload_summary_bytes": self.max_payload_summary_bytes,
            "require_provenance": self.require_provenance,
            "allow_low_trust_sources": self.allow_low_trust_sources,
            "max_records_per_bundle": self.max_records_per_bundle,
            "forbidden_risk_flags": list(self.forbidden_risk_flags),
            "policy_hash": self.policy_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Default Policy
# ═══════════════════════════════════════════════════════════════════════

def default_evidence_policy() -> EvidencePolicy:
    """Return the default evidence policy.

    Defaults:
      - 500 bytes max payload summary (prevents evidence from carrying
        large payloads inline)
      - Provenance required (every record must have provenance chain)
      - Low-trust sources allowed (but flagged)
      - 1000 max records per bundle (prevents bundle bloat)
      - No forbidden risk flags (all flags allowed; trust-based
        decisions handled at display time)
    """
    policy = EvidencePolicy(
        max_payload_summary_bytes=500,
        require_provenance=True,
        allow_low_trust_sources=True,
        max_records_per_bundle=1000,
        forbidden_risk_flags=(),
    )
    policy_hash = hashlib.sha256(
        json.dumps(policy.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    object.__setattr__(policy, "policy_hash", policy_hash)
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Policy Validation
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvidencePolicyViolation:
    """One policy violation found during validation."""
    evidence_id: str = ""
    rule: str = ""
    detail: str = ""
    severity: str = "warning"  # warning | error

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "rule": self.rule,
            "detail": self.detail,
            "severity": self.severity,
        }


def validate_against_policy(
    record_or_bundle,
    policy: EvidencePolicy,
) -> Tuple[EvidencePolicyViolation, ...]:
    """Validate an EvidenceRecord or EvidenceBundle against a policy.

    Returns a tuple of violations. Empty tuple means compliant.
    """
    from v3.external.evidence import (
        EvidenceBundle,
        EvidenceRecord,
        TRUST_LOW,
    )

    violations = []

    if isinstance(record_or_bundle, EvidenceBundle):
        records = record_or_bundle.records
        bundle_id = record_or_bundle.bundle_id

        # Check max records per bundle
        if len(records) > policy.max_records_per_bundle:
            violations.append(EvidencePolicyViolation(
                evidence_id=bundle_id,
                rule="max_records_per_bundle",
                detail=f"Bundle has {len(records)} records, max is {policy.max_records_per_bundle}",
                severity="error",
            ))

        for r in records:
            violations.extend(
                _validate_one_record(r, policy)
            )
    elif isinstance(record_or_bundle, EvidenceRecord):
        violations.extend(
            _validate_one_record(record_or_bundle, policy)
        )
    else:
        violations.append(EvidencePolicyViolation(
            evidence_id="unknown",
            rule="type",
            detail=f"Expected EvidenceRecord or EvidenceBundle, got {type(record_or_bundle).__name__}",
            severity="error",
        ))

    return tuple(violations)


def _validate_one_record(
    record,
    policy: EvidencePolicy,
) -> list:
    """Validate a single EvidenceRecord against policy. Returns list of violations."""
    violations = []
    eid = record.evidence_id

    # Check payload summary length
    if len(record.payload_summary) > policy.max_payload_summary_bytes:
        violations.append(EvidencePolicyViolation(
            evidence_id=eid,
            rule="max_payload_summary_bytes",
            detail=f"Payload summary is {len(record.payload_summary)} bytes, max is {policy.max_payload_summary_bytes}",
            severity="warning",
        ))

    # Check provenance required
    from v3.external.evidence import TRUST_LOW
    if policy.require_provenance and record.provenance is None:
        violations.append(EvidencePolicyViolation(
            evidence_id=eid,
            rule="require_provenance",
            detail="Evidence record is missing provenance",
            severity="error",
        ))

    # Check low-trust sources
    if (not policy.allow_low_trust_sources
            and record.source is not None
            and record.source.source_trust_level == TRUST_LOW):
        violations.append(EvidencePolicyViolation(
            evidence_id=eid,
            rule="allow_low_trust_sources",
            detail=f"Low-trust source not allowed by policy: {record.source.adapter_id}",
            severity="error",
        ))

    # Check forbidden risk flags
    for flag in record.risk_flags:
        if flag in policy.forbidden_risk_flags:
            violations.append(EvidencePolicyViolation(
                evidence_id=eid,
                rule="forbidden_risk_flags",
                detail=f"Evidence carries forbidden risk flag: {flag}",
                severity="error",
            ))

    return violations


# ═══════════════════════════════════════════════════════════════════════
# Payload Redaction
# ═══════════════════════════════════════════════════════════════════════

def redact_payload_summary(
    summary: str,
    max_bytes: int,
    truncation_marker: str = "... [truncated]",
) -> str:
    """Redact a payload summary to fit within max_bytes.

    If the summary exceeds max_bytes, it is truncated and a marker appended.
    The marker itself fits within the byte budget.

    Returns the original summary if it already fits.
    """
    summary_bytes = summary.encode("utf-8")
    if len(summary_bytes) <= max_bytes:
        return summary

    marker_bytes = truncation_marker.encode("utf-8")
    available = max_bytes - len(marker_bytes)
    if available <= 0:
        return truncation_marker[:max_bytes]

    # Truncate at available bytes, then walk back to a valid UTF-8 boundary
    truncated = summary_bytes[:available]
    # Decode with error handling to avoid splitting multi-byte characters
    truncated_str = truncated.decode("utf-8", errors="ignore")
    return truncated_str + truncation_marker


# ═══════════════════════════════════════════════════════════════════════
# Policy Hash
# ═══════════════════════════════════════════════════════════════════════

def compute_policy_hash(policy: EvidencePolicy) -> str:
    """Compute a deterministic hash for an EvidencePolicy."""
    return hashlib.sha256(
        json.dumps(policy.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
