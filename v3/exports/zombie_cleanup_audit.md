# Zombie Code & Stale Version Cleanup — Audit Report

**Generated**: 2026-06-02T08:30:14.315689+00:00
**Audit Hash**: `870a0ed8bebd17e7`
**Scanned Files**: 160
**Total Findings**: 14

## Summary

| Category | Count |
|----------|------:|
| zombie_code | 1 |
| stale_version | 5 |
| stale_test | 1 |
| docs_drift | 3 |
| stale_report | 4 |
| duplicate_helper | 0 |
| human_review | 0 |

- **Safe Auto-Fix Candidates**: 0 remove + 0 update
- **Human Review Needed**: 8

## Safe to Remove

### ZC-002: __pycache__

- **Category**: `zombie_code`
- **Path**: `v3/**/__pycache__/`
- **Confidence**: high
- **Risk**: low
- **Evidence**: 19 __pycache__ directories found in v3/ source tree. These are build artifacts that should be gitignored, not committed.

### ZC-103: *.pyc

- **Category**: `stale_version`
- **Path**: `v3/release/__pycache__/`
- **Confidence**: high
- **Risk**: low
- **Evidence**: 15 compiled .pyc files committed in v3/release/__pycache__/. These are build artifacts that should be cleaned and gitignored.

### ZC-404: *.crash

- **Category**: `stale_report`
- **Path**: `v3/checkpoints/*.crash`
- **Confidence**: high
- **Risk**: low
- **Evidence**: 1 .crash checkpoint files found. These are crash artifacts from testing/debugging, not needed for release.

## Needs Update

### ZC-101: ArchiveManifest.included_reports

- **Category**: `stale_version`
- **Path**: `v3/release/archive_manifest.py`
- **Confidence**: high
- **Risk**: low
- **Evidence**: archive_manifest.py references 8 non-existent phase reports: phase_4d_completion_report.md, phase_5a_gate_report.md, phase_5b_cli_report.md, phase_5c_examples_report.md... These are v3.0-era reports that no longer exist.

### ZC-102: _BUILD_BLACKLIST

- **Category**: `stale_version`
- **Path**: `v3/release/v4_inventory.py`
- **Confidence**: high
- **Risk**: low
- **Evidence**: v4_inventory.py blacklists 6 v3_*.py files, but none exist on disk. The blacklist is a dead code remnant from v3→v4 migration.

### ZC-104: build_parser() docstring

- **Category**: `stale_version`
- **Path**: `v3/cli/systemkernel.py`
- **Confidence**: high
- **Risk**: low
- **Evidence**: CLI parser docstring says 'SystemKernel v3.0 Developer CLI' but current version is v4.1.

## Needs Human Review

### ZC-001: main()

- **Category**: `stale_version`
- **Path**: `v3/main.py`
- **Confidence**: high
- **Risk**: low
- **Evidence**: v3/main.py still references 'Phase 2' and 'Next: Phase 3' but codebase is v4.1. This is a demo entry point from v3.0 early development.

### ZC-201: v3_release_* reference

- **Category**: `stale_test`
- **Path**: `v3/tests/test_baseline_packaging.py`
- **Confidence**: medium
- **Risk**: low
- **Evidence**: References v3.0-era release module names that are blacklisted in v4_inventory.py.

### ZC-301: Case-insensitive filesystem detected

- **Category**: `docs_drift`
- **Path**: `docs/`
- **Confidence**: high
- **Risk**: medium
- **Evidence**: docs/ and Docs/ resolve to the same physical directory on this case-insensitive filesystem. Git tracks them as docs/ but v4_inventory.py references Docs/. On Linux CI this would be a real path mismatch. Consider normalizing to one case.

### ZC-302: Version info

- **Category**: `docs_drift`
- **Path**: `README.md`
- **Confidence**: medium
- **Risk**: low
- **Evidence**: References v3.0 but not v4.1

### ZC-303: ECC positioning

- **Category**: `docs_drift`
- **Path**: `Docs/ECC_POSITIONING.md vs CLAUDE.md`
- **Confidence**: low
- **Risk**: medium
- **Evidence**: ECC description may differ between Docs/ECC_POSITIONING.md and CLAUDE.md. Verify both agree ECC is execution-only infrastructure.

### ZC-401: Phase build reports

- **Category**: `stale_report`
- **Path**: `v3/exports/phase_*`
- **Confidence**: medium
- **Risk**: low
- **Evidence**: 22 phase-specific reports exist. These are intermediate build artifacts from completed phases. Some may be kept as release inventory evidence; others are stale. Examples: phase_6_agent_worker_report.md, phase_6a_packaging_report.md, phase_6b_archive_report.md, phase_7_external_tools_summary.md...

### ZC-402: Duplicate JSON+MD reports

- **Category**: `stale_report`
- **Path**: `v3/exports/`
- **Confidence**: medium
- **Risk**: low
- **Evidence**: 6 report topic(s) have both JSON and MD versions. May be intentional (machine + human readable) or stale duplication. Pairs: ecc_positioning_report.json + ecc_positioning_report.md, ecc_global_enablement_report.md + ecc_global_enablement_summary.json, provider_trial_selection.json + provider_trial_selection_report.md...

### ZC-403: usage_sample.jsonl

- **Category**: `stale_report`
- **Path**: `v3/exports/usage_sample.jsonl`
- **Confidence**: medium
- **Risk**: low
- **Evidence**: Runtime data file found in v3/exports/. Should be in runtime data path (v3/traces/ or v3/metrics/), not exports.

## Do Not Touch (Protected)

The following paths are protected and MUST NOT be modified:

| Path | Reason |
|------|--------|
| v3/kernel/ | Frozen deterministic core |
| v3/memory/ runtime | Memory intelligence plane (removable) |
| v3/release/ (v4_* files) | Release freeze artifacts |
| v3/checkpoints/ | Runtime checkpoint data |
| v3/traces/ | Runtime trace data |
| v3/metrics/ | Runtime metric data |
| scripts/verify_v*_baseline.py | Baseline verification scripts |
| api.py | Public API surface (frozen) |
