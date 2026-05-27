# Provider Trial Selection Report — Phase 14A

**Recommended:** `repomix`
**Rejected:** openhands, mem0, graphiti
**Deferred:** ecc, continue
**Risk:** low

## Ranking

| Rank | Candidate | Score | Risk Ratio | Verdict |
|------|-----------|-------|-----------|---------|
| 1 | `repomix` | 303 | 0.09 | **recommended** |
| 2 | `ccusage` | 245 | 0.11 | **acceptable** |
| 3 | `anthropic_skills` | 43 | 0.8 | **acceptable** |
| 4 | `ecc` | 0 | 1.7 | **defer** |
| 5 | `continue` | 0 | 4.4 | **defer** |
| 6 | `openhands` | 0 | 19.0 | **reject** |
| 7 | `mem0` | 0 | 20.5 | **reject** |
| 8 | `graphiti` | 0 | 20.5 | **reject** |

## Score Details

| Candidate | Cap Gain | Cpx Δ | K Risk | M Risk | Dep Risk | Exec Risk | Rev | Adapter | Evidence | MSR |
|-----------|----------|-------|--------|--------|----------|-----------|-----|---------|----------|-----|
| `repomix` | 9 | 1 | 0 | 0 | 0 | 1 | 10 | 9 | 9 | 9 |
| `ccusage` | 7 | 1 | 0 | 0 | 0 | 1 | 10 | 9 | 7 | 5 |
| `anthropic_skills` | 5 | 5 | 1 | 0 | 2 | 0 | 10 | 0 | 0 | 1 |
| `ecc` | 5 | 6 | 2 | 0 | 5 | 4 | 8 | 0 | 0 | 3 |
| `continue` | 3 | 7 | 2 | 1 | 6 | 6 | 5 | 0 | 0 | 1 |
| `openhands` | 2 | 9 | 6 | 4 | 9 | 10 | 1 | 0 | 0 | 0 |
| `mem0` | 2 | 9 | 5 | 8 | 9 | 10 | 1 | 0 | 0 | 0 |
| `graphiti` | 2 | 9 | 5 | 8 | 9 | 10 | 1 | 0 | 0 | 0 |

## Recommended Next Trial

**repomix** — see ranking above for rationale.

## Safety

- **No provider executed** — this is a selection phase only.
- **No network used** — all scoring is deterministic and local.
- **No install run** — no dependencies added.
- **Kernel not modified** — scoring is external to kernel.