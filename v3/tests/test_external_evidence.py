"""
External Evidence Model Tests — Phase 3.

32 tests for the evidence model, policy, and validation.
Stdlib only.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable

from v3.external.evidence import (
    EVIDENCE_TYPE_CONTEXT_PACK,
    EVIDENCE_TYPE_USAGE_REPORT,
    EVIDENCE_TYPE_MEMORY_SIGNAL,
    EVIDENCE_TYPE_AGENT_RESULT,
    EVIDENCE_TYPE_GENERIC,
    ALL_EVIDENCE_TYPES,
    TRUST_LOW,
    TRUST_MEDIUM,
    TRUST_HIGH,
    ALL_TRUST_LEVELS,
    EvidenceSource,
    EvidenceProvenance,
    EvidenceRecord,
    EvidenceBundle,
    EvidenceValidationReport,
    compute_evidence_hash,
    make_evidence_record,
    build_evidence_bundle,
    validate_evidence_record,
    validate_evidence_bundle,
    write_evidence_bundle,
    load_evidence_bundle,
)
from v3.external.evidence_policy import (
    RISK_FLAG_UNVERIFIED,
    RISK_FLAG_EXTERNAL_IO,
    RISK_FLAG_NETWORK_ACCESS,
    ALL_RISK_FLAGS,
    EvidencePolicy,
    EvidencePolicyViolation,
    default_evidence_policy,
    validate_against_policy,
    redact_payload_summary,
    compute_policy_hash,
)


def _run_module(module_path, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    result = subprocess.run(
        [PYTHON, module_path] + list(args),
        capture_output=True, text=True, timeout=30,
        cwd=ROOT, env=env,
    )
    return result.returncode, result.stdout, result.stderr


class TestEvidenceModel(unittest.TestCase):

    # ═══════════════════════════════════════════════════════════════════
    # EvidenceSource
    # ═══════════════════════════════════════════════════════════════════

    def test_01_evidence_source_creation(self):
        """EvidenceSource can be created with all fields."""
        src = EvidenceSource(
            adapter_id="test_adapter",
            capability_type="context",
            source_uri="file:///test/path",
            source_hash="abc123",
            collected_by="test_runner",
            collection_mode="inspect_only",
            source_trust_level=TRUST_MEDIUM,
        )
        self.assertEqual(src.adapter_id, "test_adapter")
        self.assertEqual(src.capability_type, "context")
        self.assertEqual(src.source_uri, "file:///test/path")
        self.assertEqual(src.collected_by, "test_runner")
        self.assertEqual(src.collection_mode, "inspect_only")
        self.assertEqual(src.source_trust_level, TRUST_MEDIUM)

    def test_02_evidence_source_frozen(self):
        """EvidenceSource is frozen — cannot modify after creation."""
        src = EvidenceSource(adapter_id="test")
        with self.assertRaises(Exception):
            src.adapter_id = "changed"

    def test_03_evidence_source_to_dict(self):
        """EvidenceSource.to_dict() returns all fields."""
        src = EvidenceSource(
            adapter_id="test_adapter",
            capability_type="context",
            source_uri="file:///test",
            source_hash="abc",
            collected_by="runner",
            collection_mode="inspect_only",
            source_trust_level=TRUST_LOW,
        )
        d = src.to_dict()
        self.assertEqual(d["adapter_id"], "test_adapter")
        self.assertEqual(d["capability_type"], "context")
        self.assertEqual(d["source_trust_level"], TRUST_LOW)

    # ═══════════════════════════════════════════════════════════════════
    # EvidenceProvenance
    # ═══════════════════════════════════════════════════════════════════

    def test_04_evidence_provenance_creation(self):
        """EvidenceProvenance can be created with hash chain."""
        prov = EvidenceProvenance(
            input_hash="input:abc123",
            output_hash="output:def456",
            command_hash="cmd:789",
            adapter_spec_hash="spec:xyz",
            registry_hash="reg:uvw",
            collected_at="2026-05-26T00:00:00Z",
        )
        self.assertEqual(prov.input_hash, "input:abc123")
        self.assertEqual(prov.output_hash, "output:def456")
        self.assertEqual(prov.collected_at, "2026-05-26T00:00:00Z")

    def test_05_evidence_provenance_frozen(self):
        """EvidenceProvenance is frozen."""
        prov = EvidenceProvenance(input_hash="test")
        with self.assertRaises(Exception):
            prov.input_hash = "changed"

    # ═══════════════════════════════════════════════════════════════════
    # EvidenceRecord
    # ═══════════════════════════════════════════════════════════════════

    def test_06_evidence_record_truth_source_always_false(self):
        """EvidenceRecord truth_source defaults to False and cannot be True."""
        record = EvidenceRecord(evidence_id="test-1", evidence_type=EVIDENCE_TYPE_GENERIC)
        self.assertFalse(record.truth_source)

    def test_07_evidence_record_frozen(self):
        """EvidenceRecord is frozen."""
        record = EvidenceRecord(evidence_id="test-1", evidence_type=EVIDENCE_TYPE_GENERIC)
        with self.assertRaises(Exception):
            record.evidence_id = "changed"

    def test_08_evidence_record_to_dict(self):
        """EvidenceRecord.to_dict() serializes all fields including nested."""
        src = EvidenceSource(adapter_id="test_adapter", capability_type="context")
        object.__setattr__(src, "source_hash_value", "src:hash123")
        prov = EvidenceProvenance(input_hash="in:abc", output_hash="out:def")
        object.__setattr__(prov, "provenance_hash", "prov:hash456")

        record = EvidenceRecord(
            evidence_id="ev-001",
            evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
            source=src,
            provenance=prov,
            payload_summary="test summary",
            payload_ref="/tmp/ref",
            risk_flags=("unverified",),
            confidence=0.95,
        )
        d = record.to_dict()
        self.assertEqual(d["evidence_id"], "ev-001")
        self.assertFalse(d["truth_source"])
        self.assertEqual(d["source"]["adapter_id"], "test_adapter")
        self.assertEqual(d["provenance"]["input_hash"], "in:abc")
        self.assertEqual(d["payload_summary"], "test summary")
        self.assertEqual(d["confidence"], 0.95)
        self.assertEqual(d["risk_flags"], ["unverified"])

    # ═══════════════════════════════════════════════════════════════════
    # EvidenceBundle
    # ═══════════════════════════════════════════════════════════════════

    def test_09_evidence_bundle_creation(self):
        """EvidenceBundle can be created with records tuple."""
        r1 = EvidenceRecord(evidence_id="r1", evidence_type=EVIDENCE_TYPE_GENERIC)
        r2 = EvidenceRecord(evidence_id="r2", evidence_type=EVIDENCE_TYPE_GENERIC)
        bundle = EvidenceBundle(
            bundle_id="bundle-1",
            records=(r1, r2),
            bundle_type="test_bundle",
            created_at="2026-05-26T00:00:00Z",
        )
        self.assertEqual(len(bundle.records), 2)
        self.assertEqual(bundle.bundle_type, "test_bundle")

    def test_10_evidence_bundle_truth_source_false(self):
        """EvidenceBundle truth_source always defaults to False."""
        bundle = EvidenceBundle(bundle_id="b-1")
        self.assertFalse(bundle.truth_source)

    def test_11_evidence_bundle_frozen(self):
        """EvidenceBundle is frozen."""
        bundle = EvidenceBundle(bundle_id="b-1")
        with self.assertRaises(Exception):
            bundle.bundle_id = "changed"

    # ═══════════════════════════════════════════════════════════════════
    # Hash Determinism
    # ═══════════════════════════════════════════════════════════════════

    def test_12_compute_evidence_hash_deterministic(self):
        """Same input produces same hash."""
        data = {"key": "value", "nested": {"a": 1, "b": 2}}
        h1 = compute_evidence_hash(data, "test")
        h2 = compute_evidence_hash(data, "test")
        self.assertEqual(h1, h2)

    def test_13_compute_evidence_hash_different_inputs(self):
        """Different inputs produce different hashes."""
        h1 = compute_evidence_hash({"a": 1}, "test")
        h2 = compute_evidence_hash({"a": 2}, "test")
        self.assertNotEqual(h1, h2)

    def test_14_compute_evidence_hash_dict_order_independent(self):
        """Hash is independent of key insertion order."""
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 2, "a": 1}
        self.assertEqual(
            compute_evidence_hash(d1, "test"),
            compute_evidence_hash(d2, "test"),
        )

    # ═══════════════════════════════════════════════════════════════════
    # make_evidence_record
    # ═══════════════════════════════════════════════════════════════════

    def test_15_make_evidence_record_creates_valid_record(self):
        """make_evidence_record creates a record with all fields populated."""
        record = make_evidence_record(
            adapter_id="test_adapter",
            evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
            capability_type="context",
            input_data={"target": "./src"},
            output_data={"files": 5, "bytes": 1024},
            payload_summary="files=5; bytes=1024",
            payload_ref="/tmp/output",
            source_uri="./src",
            collected_by="test_runner",
            collection_mode="inspect_only",
        )
        self.assertTrue(record.evidence_id)
        self.assertEqual(record.evidence_type, EVIDENCE_TYPE_CONTEXT_PACK)
        self.assertIsNotNone(record.source)
        self.assertIsNotNone(record.provenance)
        self.assertFalse(record.truth_source)
        self.assertTrue(record.evidence_hash)

    def test_16_make_evidence_record_deterministic_id(self):
        """Same params produce same evidence_id."""
        kwargs = dict(
            adapter_id="test_adapter",
            evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
            capability_type="context",
            input_data={"target": "./src"},
            output_data={"files": 5},
            payload_summary="test",
        )
        r1 = make_evidence_record(**kwargs)
        r2 = make_evidence_record(**kwargs)
        self.assertEqual(r1.evidence_id, r2.evidence_id)

    def test_17_make_evidence_record_different_id(self):
        """Different adapter_id or output produces different evidence_id."""
        r1 = make_evidence_record(
            adapter_id="adapter_a", evidence_type=EVIDENCE_TYPE_GENERIC,
            capability_type="tool", input_data={}, output_data={"v": 1},
        )
        r2 = make_evidence_record(
            adapter_id="adapter_b", evidence_type=EVIDENCE_TYPE_GENERIC,
            capability_type="tool", input_data={}, output_data={"v": 2},
        )
        self.assertNotEqual(r1.evidence_id, r2.evidence_id)

    # ═══════════════════════════════════════════════════════════════════
    # build_evidence_bundle
    # ═══════════════════════════════════════════════════════════════════

    def test_18_build_evidence_bundle_sorts_by_id(self):
        """build_evidence_bundle sorts records by evidence_id."""
        r1 = EvidenceRecord(evidence_id="ccc", evidence_type=EVIDENCE_TYPE_GENERIC)
        r2 = EvidenceRecord(evidence_id="aaa", evidence_type=EVIDENCE_TYPE_GENERIC)
        r3 = EvidenceRecord(evidence_id="bbb", evidence_type=EVIDENCE_TYPE_GENERIC)
        bundle = build_evidence_bundle((r1, r2, r3), bundle_type="test")
        ids = [r.evidence_id for r in bundle.records]
        self.assertEqual(ids, ["aaa", "bbb", "ccc"])

    def test_19_build_evidence_bundle_duplicates_raise(self):
        """Duplicate evidence_ids in bundle raise ValueError."""
        r1 = EvidenceRecord(evidence_id="dup", evidence_type=EVIDENCE_TYPE_GENERIC)
        r2 = EvidenceRecord(evidence_id="dup", evidence_type=EVIDENCE_TYPE_MEMORY_SIGNAL)
        with self.assertRaises(ValueError):
            build_evidence_bundle((r1, r2))

    def test_20_build_evidence_bundle_hash(self):
        """Bundle gets a deterministic hash."""
        r1 = EvidenceRecord(evidence_id="a", evidence_type=EVIDENCE_TYPE_GENERIC)
        bundle = build_evidence_bundle((r1,), bundle_type="test")
        self.assertTrue(bundle.bundle_id)
        self.assertTrue(bundle.bundle_hash)
        self.assertFalse(bundle.truth_source)

    # ═══════════════════════════════════════════════════════════════════
    # Validation
    # ═══════════════════════════════════════════════════════════════════

    def test_21_validate_evidence_record_valid(self):
        """Valid record passes validation."""
        record = make_evidence_record(
            adapter_id="test", evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
            capability_type="context", input_data={}, output_data={},
        )
        report = validate_evidence_record(record)
        self.assertTrue(report.valid)
        self.assertEqual(len(report.truth_source_violations), 0)

    def test_22_validate_evidence_record_truth_source_violation(self):
        """Record with truth_source=True is flagged."""
        record = EvidenceRecord(
            evidence_id="bad", evidence_type=EVIDENCE_TYPE_GENERIC,
            truth_source=True,
        )
        report = validate_evidence_record(record)
        self.assertFalse(report.valid)
        self.assertGreater(len(report.truth_source_violations), 0)

    def test_23_validate_evidence_record_missing_provenance(self):
        """Record without provenance is flagged."""
        record = EvidenceRecord(evidence_id="no-prov", evidence_type=EVIDENCE_TYPE_GENERIC)
        report = validate_evidence_record(record)
        self.assertFalse(report.valid)
        self.assertIn("no-prov", report.missing_provenance)

    def test_24_validate_evidence_bundle_valid(self):
        """Valid bundle passes validation."""
        r1 = make_evidence_record(
            adapter_id="a", evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
            capability_type="context", input_data={}, output_data={},
        )
        r2 = make_evidence_record(
            adapter_id="b", evidence_type=EVIDENCE_TYPE_USAGE_REPORT,
            capability_type="usage", input_data={}, output_data={},
        )
        bundle = build_evidence_bundle((r1, r2), bundle_type="test")
        report = validate_evidence_bundle(bundle)
        self.assertTrue(report.valid)
        self.assertEqual(report.record_count, 2)

    def test_25_validate_evidence_bundle_duplicates(self):
        """Bundle validation detects duplicate evidence_ids."""
        r = make_evidence_record(
            adapter_id="x", evidence_type=EVIDENCE_TYPE_GENERIC,
            capability_type="tool", input_data={}, output_data={},
        )
        # Manually create a bundle with duplicates (bypassing build check)
        bundle = EvidenceBundle(
            bundle_id="dup-bundle",
            records=(r, r),
            bundle_type="test",
            created_at="2026-05-26T00:00:00Z",
        )
        report = validate_evidence_bundle(bundle)
        self.assertFalse(report.valid)
        self.assertGreater(len(report.duplicate_evidence_ids), 0)

    # ═══════════════════════════════════════════════════════════════════
    # EvidencePolicy
    # ═══════════════════════════════════════════════════════════════════

    def test_26_evidence_policy_creation(self):
        """EvidencePolicy can be created with custom rules."""
        policy = EvidencePolicy(
            max_payload_summary_bytes=200,
            require_provenance=True,
            allow_low_trust_sources=False,
            max_records_per_bundle=50,
            forbidden_risk_flags=(RISK_FLAG_UNVERIFIED, RISK_FLAG_NETWORK_ACCESS),
        )
        self.assertEqual(policy.max_payload_summary_bytes, 200)
        self.assertTrue(policy.require_provenance)
        self.assertFalse(policy.allow_low_trust_sources)
        self.assertEqual(policy.max_records_per_bundle, 50)
        self.assertIn(RISK_FLAG_UNVERIFIED, policy.forbidden_risk_flags)

    def test_27_evidence_policy_frozen(self):
        """EvidencePolicy is frozen."""
        policy = EvidencePolicy()
        with self.assertRaises(Exception):
            policy.max_payload_summary_bytes = 999

    def test_28_default_evidence_policy(self):
        """Default policy has sensible defaults."""
        policy = default_evidence_policy()
        self.assertEqual(policy.max_payload_summary_bytes, 500)
        self.assertTrue(policy.require_provenance)
        self.assertTrue(policy.allow_low_trust_sources)
        self.assertEqual(policy.max_records_per_bundle, 1000)
        self.assertEqual(policy.forbidden_risk_flags, ())
        self.assertTrue(policy.policy_hash)

    # ═══════════════════════════════════════════════════════════════════
    # validate_against_policy
    # ═══════════════════════════════════════════════════════════════════

    def test_29_validate_against_policy_compliant_record(self):
        """Compliant record produces no violations."""
        policy = default_evidence_policy()
        record = make_evidence_record(
            adapter_id="test", evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
            capability_type="context", input_data={}, output_data={},
            payload_summary="short",
        )
        violations = validate_against_policy(record, policy)
        self.assertEqual(len(violations), 0)

    def test_30_validate_against_policy_payload_too_large(self):
        """Oversized payload summary is flagged."""
        policy = EvidencePolicy(max_payload_summary_bytes=10, require_provenance=False)
        record = make_evidence_record(
            adapter_id="test", evidence_type=EVIDENCE_TYPE_GENERIC,
            capability_type="tool", input_data={}, output_data={},
            payload_summary="This summary is way too long for 10 bytes",
            risk_flags=(),
        )
        violations = validate_against_policy(record, policy)
        self.assertGreater(len(violations), 0)
        self.assertEqual(violations[0].rule, "max_payload_summary_bytes")

    def test_31_validate_against_policy_missing_provenance(self):
        """Missing provenance is flagged when policy requires it."""
        policy = EvidencePolicy(require_provenance=True)
        record = EvidenceRecord(
            evidence_id="no-prov", evidence_type=EVIDENCE_TYPE_GENERIC,
            provenance=None,
        )
        violations = validate_against_policy(record, policy)
        self.assertTrue(any(v.rule == "require_provenance" for v in violations))

    def test_32_validate_against_policy_forbidden_risk_flag(self):
        """Forbidden risk flag triggers violation."""
        policy = EvidencePolicy(
            require_provenance=False,
            forbidden_risk_flags=(RISK_FLAG_NETWORK_ACCESS,),
        )
        record = EvidenceRecord(
            evidence_id="risky",
            evidence_type=EVIDENCE_TYPE_GENERIC,
            risk_flags=(RISK_FLAG_NETWORK_ACCESS,),
        )
        violations = validate_against_policy(record, policy)
        self.assertTrue(any(v.rule == "forbidden_risk_flags" for v in violations))

    def test_33_validate_against_policy_bundle(self):
        """Bundle validation checks all records and bundle-level rules."""
        policy = EvidencePolicy(max_payload_summary_bytes=5, require_provenance=False,
                                max_records_per_bundle=1)
        r1 = make_evidence_record(
            adapter_id="a", evidence_type=EVIDENCE_TYPE_GENERIC,
            capability_type="tool", input_data={}, output_data={},
            payload_summary="way too long",
        )
        r2 = make_evidence_record(
            adapter_id="b", evidence_type=EVIDENCE_TYPE_GENERIC,
            capability_type="tool", input_data={}, output_data={},
            payload_summary="also too long",
        )
        bundle = build_evidence_bundle((r1, r2))
        violations = validate_against_policy(bundle, policy)
        # Should have max_records_per_bundle + 2 payload violations
        self.assertGreaterEqual(len(violations), 3)

    def test_34_validate_against_policy_wrong_type(self):
        """Non-evidence object produces a type violation."""
        policy = default_evidence_policy()
        violations = validate_against_policy("not evidence", policy)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].rule, "type")

    # ═══════════════════════════════════════════════════════════════════
    # Redaction
    # ═══════════════════════════════════════════════════════════════════

    def test_35_redact_payload_summary_fits(self):
        """Summary within limit is returned unchanged."""
        original = "short summary"
        result = redact_payload_summary(original, 500)
        self.assertEqual(result, original)

    def test_36_redact_payload_summary_truncates(self):
        """Summary exceeding limit is truncated with marker."""
        original = "This is a very long summary that should be truncated"
        result = redact_payload_summary(original, 30)
        self.assertLessEqual(len(result.encode("utf-8")), 30)
        self.assertIn("[truncated]", result)
        self.assertTrue(result.startswith("This is a"))

    # ═══════════════════════════════════════════════════════════════════
    # Persistence Roundtrip
    # ═══════════════════════════════════════════════════════════════════

    def test_37_write_and_load_bundle_roundtrip(self):
        """EvidenceBundle survives JSON write/load roundtrip."""
        r1 = make_evidence_record(
            adapter_id="test", evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
            capability_type="context",
            input_data={"target": "./src"},
            output_data={"files": 3, "bytes": 2048},
            payload_summary="files=3; bytes=2048",
            payload_ref="/tmp/test",
            source_uri="./src",
            collected_by="test",
            risk_flags=(RISK_FLAG_UNVERIFIED,),
            confidence=0.9,
        )
        bundle = build_evidence_bundle((r1,), bundle_type="test_roundtrip")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            tmp_path = f.name

        try:
            written_path = write_evidence_bundle(bundle, tmp_path)
            self.assertTrue(os.path.isfile(written_path))

            loaded = load_evidence_bundle(written_path)
            self.assertEqual(loaded.bundle_id, bundle.bundle_id)
            self.assertEqual(len(loaded.records), 1)
            self.assertEqual(loaded.records[0].evidence_id,
                             bundle.records[0].evidence_id)
            self.assertEqual(loaded.records[0].payload_summary, "files=3; bytes=2048")
            self.assertEqual(loaded.records[0].confidence, 0.9)
            self.assertFalse(loaded.truth_source)
        finally:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)

    # ═══════════════════════════════════════════════════════════════════
    # Evidence Types and Trust Levels
    # ═══════════════════════════════════════════════════════════════════

    def test_38_all_evidence_types_valid(self):
        """All 10 evidence types are defined (includes v4.1 additions)."""
        self.assertEqual(len(ALL_EVIDENCE_TYPES), 10)  # +direction_signal, +quality_signal in v4.1
        self.assertIn(EVIDENCE_TYPE_CONTEXT_PACK, ALL_EVIDENCE_TYPES)
        self.assertIn(EVIDENCE_TYPE_USAGE_REPORT, ALL_EVIDENCE_TYPES)
        self.assertIn(EVIDENCE_TYPE_MEMORY_SIGNAL, ALL_EVIDENCE_TYPES)
        self.assertIn(EVIDENCE_TYPE_AGENT_RESULT, ALL_EVIDENCE_TYPES)

    def test_39_all_trust_levels_defined(self):
        """3 trust levels are defined."""
        self.assertEqual(len(ALL_TRUST_LEVELS), 3)
        self.assertIn(TRUST_LOW, ALL_TRUST_LEVELS)
        self.assertIn(TRUST_MEDIUM, ALL_TRUST_LEVELS)
        self.assertIn(TRUST_HIGH, ALL_TRUST_LEVELS)

    def test_40_all_risk_flags_defined(self):
        """7 risk flags are defined."""
        self.assertEqual(len(ALL_RISK_FLAGS), 7)
        self.assertIn(RISK_FLAG_UNVERIFIED, ALL_RISK_FLAGS)
        self.assertIn(RISK_FLAG_EXTERNAL_IO, ALL_RISK_FLAGS)
        self.assertIn(RISK_FLAG_NETWORK_ACCESS, ALL_RISK_FLAGS)

    # ═══════════════════════════════════════════════════════════════════
    # EvidenceValidationReport
    # ═══════════════════════════════════════════════════════════════════

    def test_41_evidence_validation_report_creation(self):
        """EvidenceValidationReport can be created with all fields."""
        report = EvidenceValidationReport(
            valid=False,
            record_count=3,
            invalid_records=("r1",),
            missing_provenance=("r2",),
            truth_source_violations=("r3",),
            duplicate_evidence_ids=(),
        )
        self.assertFalse(report.valid)
        self.assertEqual(report.record_count, 3)
        self.assertEqual(len(report.invalid_records), 1)
        self.assertEqual(len(report.missing_provenance), 1)

    def test_42_evidence_validation_report_to_dict(self):
        """Report serializes to dict correctly."""
        report = EvidenceValidationReport(
            valid=True,
            record_count=1,
            invalid_records=(),
            missing_provenance=(),
            truth_source_violations=(),
            duplicate_evidence_ids=(),
        )
        d = report.to_dict()
        self.assertTrue(d["valid"])
        self.assertEqual(d["record_count"], 1)
        self.assertEqual(d["invalid_records"], [])

    # ═══════════════════════════════════════════════════════════════════
    # compute_policy_hash
    # ═══════════════════════════════════════════════════════════════════

    def test_43_compute_policy_hash_deterministic(self):
        """Same policy produces same hash."""
        policy = EvidencePolicy(
            max_payload_summary_bytes=300,
            require_provenance=False,
        )
        h1 = compute_policy_hash(policy)
        h2 = compute_policy_hash(policy)
        self.assertEqual(h1, h2)

    def test_44_compute_policy_hash_different(self):
        """Different policies produce different hashes."""
        p1 = EvidencePolicy(max_payload_summary_bytes=100)
        p2 = EvidencePolicy(max_payload_summary_bytes=200)
        self.assertNotEqual(compute_policy_hash(p1), compute_policy_hash(p2))

    # ═══════════════════════════════════════════════════════════════════
    # No banned imports
    # ═══════════════════════════════════════════════════════════════════

    def test_45_no_banned_imports(self):
        """Phase 3 files must not import LLM/vector/agent frameworks."""
        BANNED = {"openai", "anthropic", "langchain", "crewai", "autogen",
                  "mem0", "graphiti", "chromadb", "qdrant", "milvus"}
        phase3_files = ["evidence.py", "evidence_policy.py"]
        for fname in phase3_files:
            fpath = os.path.join(EXTERNAL_DIR, fname)
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0].lower()
                        self.assertNotIn(root, BANNED,
                                         f"{fname} imports banned: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root = node.module.split(".")[0].lower()
                        self.assertNotIn(root, BANNED,
                                         f"{fname} imports banned: {node.module}")


class TestPhase3Regression(unittest.TestCase):

    def test_v4_baseline_guard_passes(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_v4_baseline_guard.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Baseline guard failed:\n{result.stderr[:1000]}")

    def test_kernel_invariants_passes(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_kernel_invariants.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Kernel invariants failed:\n{result.stderr[:1000]}")
        self.assertIn("purity_score == 100", result.stdout)


if __name__ == "__main__":
    unittest.main()
