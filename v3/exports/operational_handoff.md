# SystemKernel v3.0 — Operational Handoff

**Version:** 3.0.0
**Handoff Hash:** d333e3bc560fd0ae

---

## Verification Checklist

| ID | Title | Command | Expected | Required | Status |
|----|-------|---------|----------|----------|--------|
| H001 | Run kernel invariants | `python v3/tests/test_kernel_invariants.py` | All kernel invariants pass; purity score 100/100 | YES | PENDING |
| H002 | Run release freeze tests | `python v3/tests/test_release_freeze.py` | All release freeze tests pass | YES | PENDING |
| H003 | Run CLI doctor | `python v3/cli/systemkernel.py doctor` | All health checks pass; HEALTH: OK | YES | PENDING |
| H004 | Run golden path | `python examples/golden_path/run_golden_path.py` | GOLDEN PATH COMPLETE; all 6 steps succeed | YES | PENDING |
| H005 | Run complexity gate | `python v3/cli/systemkernel.py quality` | Complexity verdict: ACCEPT or REVIEW (not REJECT) | YES | PENDING |
| H006 | Inspect release notes | `python -c "from v3.release.release_notes import generate_rel...` | Release notes contain version 3.0.0 and all completed phases | YES | PENDING |
| H007 | Inspect clone plan | `python v3/cli/systemkernel.py intake clone-list` | Clone plan printed; PLAN ONLY; no actual cloning performed | YES | PENDING |
| H008 | Verify memory removable | `python -c "import json; d=json.load(open('v3/exports/memory_...` | Removability: YES | YES | PENDING |
| H009 | Verify no network/clone assumption | `python v3/tests/test_baseline_packaging.py` | Test that verifies no network/clone/install commands in verify script | YES | PENDING |
| H010 | Run baseline packaging tests | `python v3/tests/test_baseline_packaging.py` | All 21 baseline packaging tests pass | YES | PENDING |
| H011 | Run verification script | `python scripts/verify_v3_baseline.py` | All checks PASS; exit code 0 | YES | PENDING |
| H012 | Verify package manifest | `python -c "from v3.release.package_manifest import build_pac...` | Package manifest verification: OK | YES | PENDING |

---

## Verification Commands

Run these commands in order to verify the v3.0 baseline:

1. `python v3/tests/test_kernel_invariants.py`
2. `python v3/tests/test_release_freeze.py`
3. `python v3/tests/test_baseline_packaging.py`
4. `python v3/tests/test_golden_path.py`
5. `python v3/tests/test_complexity_budget.py`
6. `python v3/tests/test_developer_cli.py`
7. `python v3/cli/systemkernel.py doctor`
8. `python v3/cli/systemkernel.py status`
9. `python v3/cli/systemkernel.py reports summary`
10. `python examples/golden_path/run_golden_path.py`
11. `python scripts/verify_v3_baseline.py`

Or run the single verification script:

```bash
python scripts/verify_v3_baseline.py
```

---

## Rollback Guidance

SystemKernel v3.0 is a baseline release. Rollback means reverting
to the previous commit before Phase 4-6 changes were applied.

Git rollback:
  git log --oneline -20          # find the pre-v3.0 commit
  git checkout <commit-hash>     # detach to that commit
  # OR: git revert <range>       # create revert commits

Data safety:
  - All memory data is in v3/checkpoints/ and v3/traces/
  - These are append-only JSONL — no data loss on rollback
  - Metrics are in v3/metrics/ — append-only
  - Kernel source is unchanged by operation

What rollback does NOT affect:
  - External tool installations (separate repos)
  - Git history (immutable)
  - System configuration outside this repo

Safe rollback procedure:
  1. Run: python scripts/verify_v3_baseline.py  (confirm current state)
  2. Note the current commit hash
  3. git checkout <target-commit>
  4. Run: python scripts/verify_v3_baseline.py  (confirm restored state)
  5. Validate that expected behavior is restored

---

## Known Limitations

1. Single-machine only — no distributed execution. Event store is local JSONL.
2. No real-time streaming — execution is batch-oriented.
3. Memory is lexical only — semantic index uses tokenization, not embeddings.
4. 14 repo profiles — intake pipeline covers 14 known repos.
5. No MCP server — CLI is the primary interface.
6. No web UI — stdout text output only.
7. Windows paths — default paths use F:/Claude/ conventions.
8. No incremental adoption path — requires full SystemKernel runtime.
9. Verification script requires Python 3.10+ (standard library only).
10. Golden path uses temporary directories — cleaned up after each run.
11. Checkpoint data is session-scoped — no cross-session replay guarantee.
12. No automated baseline archival — manual git tag required.

---

## Complexity Gate Policy

The complexity gate has three verdicts:

- **ACCEPT** — complexity is within budget; proceed freely.
- **REVIEW** — complexity exceeds benefit threshold; manual review
  recommended but does not block release.
- **REJECT** — complexity severely exceeds budget; release blocked.

Current policy: REVIEW is a warning, not a gate. Only REJECT blocks.
The v3.0 baseline targets REVIEW at worst.

---

## External Tool Clone Policy

External tools referenced in the external tool registry and clone plan
are NOT part of SystemKernel. They are separate repositories with their
own licenses, maintainers, and security postures.

Rules:

1. Clone external tools into `F:/Claude/Github/` — outside kernel boundary.
2. Do NOT integrate external tools into kernel source tree.
3. All clone operations require manual review and execution.
4. No automated git clone in any kernel module.
5. External tools are separately audited before integration.

---

## What NOT to Modify After Freeze

The following are FROZEN and must not be modified without a new
major version (v4.0):

- Kernel execution pipeline order (lint → typecheck → test → report)
- EventBus routing table (13 deterministic rules)
- Adapter resolve() semantics (deterministic, empty binding on no match)
- TaskSystem state machine (backlog → active → done)
- Registry schema (9 required fields per skill)
- ExecutionLoop retry policy (max 2 attempts)
- Sandbox configuration (timeouts, filesystem scope)
- Observability contract (write-only, append-only, removable)
- Memory boundary (kernel must not import from v3.memory)

Safe to add (future phases):

- New test files
- New export reports
- New documentation files
- New examples
- New CLI commands (that don't modify kernel behavior)
- New external tool profiles in the intake registry

---

*SystemKernel v3.0 Operational Handoff — Phase 6A*
*Generated: d333e3bc560fd0ae*
