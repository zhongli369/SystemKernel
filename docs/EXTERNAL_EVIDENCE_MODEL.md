# External Evidence Model

**Version:** 1.0.0 | **Phase:** 3 | **Date:** 2026-05-26
**Status:** Active | **Enforcement:** `v3/external/evidence.py`, `v3/external/evidence_policy.py`

---

## Why an Evidence Model Exists

Before Phase 3, external tool outputs (Repomix context packs, ccusage reports)
had no unified representation. Each adapter produced its own result type with
no standard way to track provenance, validate integrity, or enforce the
"evidence, not truth" contract.

The evidence model standardizes this. Every external capability output is
wrapped as an `EvidenceRecord` with deterministic hashing, provenance tracking,
and mandatory `truth_source=False`.

---

## Core Principle

**External outputs are EVIDENCE, never TRUTH.**

The kernel's `EventStore` is the single source of truth. External tools produce
data that may be useful, but is never authoritative. This is enforced at the
type level: `truth_source` is always `False` on every record and every bundle.

---

## Evidence Types

| Type | Constant | Description |
|------|----------|-------------|
| Context Pack | `EVIDENCE_TYPE_CONTEXT_PACK` | Repomix-style code context exports |
| Usage Report | `EVIDENCE_TYPE_USAGE_REPORT` | Token/cost usage data |
| Memory Signal | `EVIDENCE_TYPE_MEMORY_SIGNAL` | Memory intelligence output |
| Agent Result | `EVIDENCE_TYPE_AGENT_RESULT` | Autonomous agent output |
| IDE Context | `EVIDENCE_TYPE_IDE_CONTEXT` | IDE workspace context |
| Skill Reference | `EVIDENCE_TYPE_SKILL_REFERENCE` | Skill format/metadata |
| Eval Result | `EVIDENCE_TYPE_EVAL_RESULT` | Evaluation harness output |
| Generic | `EVIDENCE_TYPE_GENERIC` | Fallback for unknown types |

---

## Trust Levels

| Level | Constant | Use |
|-------|----------|-----|
| Low | `TRUST_LOW` | External npm/pip tools, third-party services |
| Medium | `TRUST_MEDIUM` | Well-known tools with inspected output |
| High | `TRUST_HIGH` | Kernel-blessed, deterministic, fully tested adapters |

---

## Evidence Record Structure

```
EvidenceRecord (frozen)
  evidence_id:    str           — SHA-256(adapter_id:source_hash:output_hash)[:16]
  evidence_type:  str           — one of ALL_EVIDENCE_TYPES
  source:         EvidenceSource | None
  provenance:     EvidenceProvenance | None
  payload_summary: str          — truncated summary of actual output
  payload_ref:    str           — path/URI to full output if stored externally
  risk_flags:     tuple[str]    — risk indicators (unverified, network_access, etc.)
  confidence:     float         — 0.0 to 1.0
  truth_source:   bool          — ALWAYS False
  evidence_hash:  str           — deterministic hash of the record
```

### EvidenceSource

Where evidence came from — the adapter and collection context.

### EvidenceProvenance

Chain of hashes proving where evidence came from: `input_hash → output_hash → command_hash → adapter_spec_hash → registry_hash`.

---

## Evidence Bundle

A collection of evidence records, sorted deterministically by `evidence_id`.
Duplicates are rejected at bundle construction time. Bundles support JSON
serialization for storage and reporting.

---

## Evidence Policy

Policies govern how evidence is collected and validated:

| Rule | Default | Description |
|------|---------|-------------|
| `max_payload_summary_bytes` | 500 | Max inline payload size |
| `require_provenance` | True | Every record must have provenance |
| `allow_low_trust_sources` | True | Low-trust sources allowed (but flagged) |
| `max_records_per_bundle` | 1000 | Prevents bundle bloat |
| `forbidden_risk_flags` | () | Risk flags blocked by policy |

---

## Risk Flags

| Flag | Meaning |
|------|---------|
| `unverified` | Output not independently verified |
| `external_io` | External I/O involved |
| `network_access` | Network access required |
| `file_system_write` | Writes to filesystem |
| `subprocess` | Spawns subprocesses |
| `user_data` | Contains or touches user data |
| `third_party` | Third-party service dependency |

---

## How Future Adapters Use This

When Phase 5 (Autonomous Agents) runs an agent, the result is:

1. Collected as `make_evidence_record(adapter_id="openhands", ...)`
2. Wrapped with deterministic provenance
3. Validated against the evidence policy
4. Bundled for storage/reporting
5. Never treated as truth (`truth_source=False`)

The evidence model provides the wrapper — each adapter provides the payload.

---

## Anti-Overengineering

- No new runtime capability added
- No external tool execution
- No new dependencies
- All evidence is projection-only (read, store, report)
- Policy is configuration, not enforcement
- Reuses Phase 1 hash computation pattern

---

*SystemKernel v4.0 Phase 3 — External Evidence Model*
