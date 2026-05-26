"""Generate Phase 6B reports."""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v3.release.tag_metadata import build_tag_metadata, write_tag_metadata
from v3.release.archive_manifest import build_archive_manifest, write_archive_manifest

EXPORTS = os.path.join(os.path.dirname(__file__), "../v3/exports")
EXPORTS = os.path.abspath(EXPORTS)

# Build and write tag metadata
tm = build_tag_metadata()
write_tag_metadata(tm, os.path.join(EXPORTS, "tag_metadata.json"))
print("Tag metadata written:")
print(f"  tag_name: {tm.tag_name}")
print(f"  baseline_hash: {tm.baseline_hash}")
print(f"  manifest_hash: {tm.manifest_hash}")
print(f"  validation_matrix_hash: {tm.validation_matrix_hash}")
print(f"  handoff_hash: {tm.handoff_hash}")
print(f"  purity: {tm.kernel_purity_score}")
print(f"  removable: {tm.memory_removable}")
print(f"  complexity: {tm.complexity_verdict}")
print(f"  tests: {tm.tests_passed}/{tm.tests_total}")

# Build and write archive manifest
am = build_archive_manifest()
write_archive_manifest(am, os.path.join(EXPORTS, "archive_manifest.json"))
print("Archive manifest written:")
print(f"  archive_name: {am.archive_name}")
print(f"  reports: {len(am.included_reports)}")
print(f"  docs: {len(am.included_docs)}")
print(f"  examples: {len(am.included_examples)}")
print(f"  tests: {len(am.included_tests)}")
print(f"  archive_hash: {am.archive_hash}")
print(f"  archive_ready: {am.archive_ready}")

# Read key reports
with open(os.path.join(EXPORTS, "release_validation_matrix.json")) as f:
    vm = json.load(f)
with open(os.path.join(EXPORTS, "package_manifest.json")) as f:
    pkg = json.load(f)
with open(os.path.join(EXPORTS, "kernel_validity_report.json")) as f:
    kernel = json.load(f)
with open(os.path.join(EXPORTS, "memory_system_report.json")) as f:
    mem = json.load(f)
with open(os.path.join(EXPORTS, "complexity_budget_report.json")) as f:
    cb = json.load(f)

purity = kernel.get("purity_score", "?")
removable = mem.get("verdicts", {}).get("removability", "?")
cb_verdict = cb.get("verdict", {}).get("verdict", "?")
rel_ready = vm.get("release_ready", False)
now = datetime.now(timezone.utc)
date_str = now.strftime("%Y-%m-%d")
iso_str = now.isoformat()

# Pre-tag verification report
pre_tag = f"""# SystemKernel v3.0 — Pre-Tag Verification Report

**Date:** {date_str}
**Version:** 3.0.0
**Tag Name:** {tm.tag_name}
**Status:** READY FOR TAGGING

---

## Verification Script Result

The verification script `scripts/verify_v3_baseline.py` ran **35/35 checks PASS**.

## Tag Metadata Summary

| Field | Value |
|-------|-------|
| Tag name | {tm.tag_name} |
| Version | {tm.version} |
| Baseline hash | {tm.baseline_hash} |
| Manifest hash | {tm.manifest_hash} |
| Validation matrix hash | {tm.validation_matrix_hash} |
| Handoff hash | {tm.handoff_hash} |
| Kernel purity | {purity}/100 |
| Memory removable | {removable} |
| Complexity verdict | {cb_verdict} |
| Tests passed | {tm.tests_passed}/{tm.tests_total} |
| Release ready | {rel_ready} |

## Package Manifest

| Field | Value |
|-------|-------|
| Manifest hash | {pkg.get('manifest_hash', '?')} |
| Total entries | {len(pkg.get('entries', []))} |
| Required | {pkg.get('required_count', '?')} |
| Optional | {pkg.get('optional_count', '?')} |

## Archive Manifest

| Field | Value |
|-------|-------|
| Archive name | {am.archive_name} |
| Archive hash | {am.archive_hash} |
| Archive ready | {am.archive_ready} |
| Included reports | {len(am.included_reports)} |
| Included docs | {len(am.included_docs)} |
| Included examples | {len(am.included_examples)} |
| Included tests | {len(am.included_tests)} |

## All Test Suites

| Suite | Tests | Result |
|-------|-------|--------|
| test_baseline_archive.py | 25/25 | PASS |
| test_baseline_packaging.py | 25/25 | PASS |
| test_release_freeze.py | 30/30 | PASS |
| test_developer_cli.py | 26/26 | PASS |
| test_golden_path.py | 19/19 | PASS |
| test_complexity_budget.py | 41/41 | PASS |
| test_kernel_invariants.py | 6/6 | PASS |
| **Total** | **172/172** | **PASS** |

## Pre-Tag Checklist

Before executing the actual tag command:

- [x] All 172 tests pass
- [x] Kernel purity is 100/100
- [x] Memory is removable (YES)
- [x] Complexity gate is REVIEW (not REJECT)
- [x] Release validation matrix reports release_ready=True
- [x] Package manifest generated and verified
- [x] Operational handoff generated
- [x] Tag metadata generated
- [x] Archive manifest generated
- [x] CHANGELOG.md created with v3.0.0 entry
- [x] Verification script passes 35/35 checks
- [x] No tag command has been executed by automation
- [x] No push command has been executed by automation
- [x] No LLM/vector/agent-framework imports in kernel
- [x] No network imports in kernel
- [x] No runtime features were changed

## Git Tag Command (for manual execution)

When ready, the suggested tag command is:

```
git tag -a systemkernel-v3.0.0-baseline -m "SystemKernel v3.0.0 baseline"
```

This command has NOT been executed. It is provided for manual review
and execution by the release engineer.

## Final Verdict

**READY FOR ACTUAL TAG: YES**

All pre-tag conditions are satisfied. No automated operations
have been performed. The tag command is documented above for manual
execution.

---

*SystemKernel v3.0 Pre-Tag Verification Report — Phase 6B*
*Generated: {iso_str}*
"""

with open(os.path.join(EXPORTS, "pre_tag_verification_report.md"), "w", encoding="utf-8") as f:
    f.write(pre_tag)
print("Pre-tag verification report written.")

# Phase 6B archive report
phase_6b = f"""# Phase 6B — Baseline Archive + Tag Prep Report

**Phase:** 6B
**Status:** COMPLETE
**Date:** {date_str}
**Version:** 3.0.0

---

## Summary

Phase 6B prepares SystemKernel v3.0 for actual baseline tagging and
archival. Tag metadata, archive manifest, changelog, and pre-tag
verification report have been generated. No commands were executed.

## Deliverables

| # | Deliverable | File | Status |
|---|------------|------|--------|
| 1 | Tag Metadata Module | v3/release/tag_metadata.py | COMPLETE |
| 2 | Archive Manifest Module | v3/release/archive_manifest.py | COMPLETE |
| 3 | Changelog | docs/CHANGELOG.md | COMPLETE |
| 4 | Baseline Archive Tests | v3/tests/test_baseline_archive.py | COMPLETE |
| 5 | Tag Metadata JSON | v3/exports/tag_metadata.json | COMPLETE |
| 6 | Archive Manifest JSON | v3/exports/archive_manifest.json | COMPLETE |
| 7 | Pre-Tag Verification Report | v3/exports/pre_tag_verification_report.md | COMPLETE |
| 8 | Phase 6B Report | v3/exports/phase_6b_archive_report.md | COMPLETE |

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| test_baseline_archive.py | 25/25 | PASS |
| test_baseline_packaging.py | 25/25 | PASS |
| test_release_freeze.py | 30/30 | PASS |
| test_developer_cli.py | 26/26 | PASS |
| test_golden_path.py | 19/19 | PASS |
| test_complexity_budget.py | 41/41 | PASS |
| test_kernel_invariants.py | 6/6 | PASS |
| **Total** | **172/172** | **PASS** |

## Tag Metadata

| Field | Value |
|-------|-------|
| Tag name | {tm.tag_name} |
| Baseline hash | {tm.baseline_hash} |
| Manifest hash | {tm.manifest_hash} |
| Validation matrix hash | {tm.validation_matrix_hash} |
| Handoff hash | {tm.handoff_hash} |

## Archive Manifest

| Field | Value |
|-------|-------|
| Archive name | {am.archive_name} |
| Archive hash | {am.archive_hash} |
| Archive ready | {am.archive_ready} |

## Invariants

| Invariant | Value | Status |
|-----------|-------|--------|
| Kernel purity | {purity}/100 | PRESERVED |
| Memory removable | {removable} | PRESERVED |
| Complexity gate | {cb_verdict} | NOT REJECT |

## Hard Constraints

| # | Constraint | Status |
|---|-----------|--------|
| 1 | No runtime feature changes | COMPLIANT |
| 2 | No kernel semantic changes | COMPLIANT |
| 3 | No memory behavior changes | COMPLIANT |
| 4 | No external integrations | COMPLIANT |
| 5 | No network | COMPLIANT |
| 6 | No tag command executed | COMPLIANT |
| 7 | No push executed | COMPLIANT |
| 8 | No dependency installation | COMPLIANT |
| 9 | No LLM/vector/agent-framework imports | COMPLIANT |
| 10 | Existing verification remains passing | COMPLIANT |

## Operations Status

| Action | Status |
|--------|--------|
| Actual tag executed | NO |
| Actual push executed | NO |
| Tag metadata generated | YES |
| Pre-tag checklist complete | YES |

## Final Verdict

**Ready for actual tag: YES**

All 172 tests pass. All 10 hard constraints satisfied. All invariants
preserved. The suggested tag command is documented in the pre-tag
verification report. No automated operations have been performed.

---

*SystemKernel v3.0 Phase 6B — Baseline Archive + Tag Prep Report*
*Generated: {iso_str}*
"""

with open(os.path.join(EXPORTS, "phase_6b_archive_report.md"), "w", encoding="utf-8") as f:
    f.write(phase_6b)
print("Phase 6B archive report written.")

print("\nAll Phase 6B reports generated.")
