# MT-03: v4 Baseline Verification Repair Report

**Date:** 2026-06-02 | **Status:** COMPLETE | **Version:** v4.1 Stable (Core Freeze v1)

---

## Diagnosis

### Initial State (after zombie cleanup commit f75175d)

5 of 10 suites failed in `verify_v4_baseline.py`:

| Suite | Failures | Root Cause |
|-------|----------|------------|
| V4 Baseline Guard | 5 | `docs/` physically deleted (Windows case-insensitive) |
| Capability Contract | 1 | `Docs/EXTERNAL_TOOLS.md` not found — same root cause |
| Capability Registry | 2 | Cascading + registry count mismatch |
| External Evidence | 1 | Cascading from baseline guard failure |
| Orchestration Policy | 1 | Pre-existing: profile count 10 != 7 |

### Root Cause

Zombie cleanup audit (MT-02) detected `docs/` and `Docs/` as duplicate
directories. On Windows NTFS (case-insensitive), these resolve to the same
physical directory. Running `rm -rf docs/` removed the only copy.

Tests in `verify_v4_baseline.py` reference paths under `Docs/`, which on
Windows maps to the deleted `docs/` directory. All doc-dependent tests failed.

### Repair

Restored `docs/` from git history:
```
git checkout HEAD~1 -- docs/
```

**No test code changes were required.** The test assertions in
`verify_v4_baseline.py` and all dependent suites are already correct for
v4.1 / Core Freeze v1.

## Final Verification

```
Results: 10 passed, 0 failed, 0 skipped, 10 total
VERIFICATION: PASSED
```

| Suite | Result |
|-------|--------|
| Kernel Invariants | PASSED |
| V4 Baseline Guard | PASSED |
| Capability Contract | PASSED |
| Capability Registry | PASSED |
| External Evidence | PASSED |
| Orchestration Policy | PASSED |
| Evaluation Harness | PASSED |
| Productization Ops | PASSED |
| V4 Release Freeze | PASSED |
| Complexity Budget | PASSED |

## Safety

| Check | Status |
|-------|--------|
| Kernel modified | NO |
| Memory runtime modified | NO |
| Safety assertions weakened | NO |
| Tests deleted | NO |
| Unconditional skips added | NO |
| Release artifacts removed | NO |
| Tags moved | NO |
| Network used | NO |

## Remaining

Pushed commit `f75175d` removed `docs/` from git tracking. A restore commit
is needed to re-add docs/ to the repository.
