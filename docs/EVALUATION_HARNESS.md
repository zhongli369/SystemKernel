# Evaluation Harness — Phase 10

## Why Evaluation Exists

The v4 Pluggable Intelligence Plane adds multiple external capability
planes (context, memory, agent, workspace, skill evolution, orchestration).
Without measurement, there is no way to tell whether these planes deliver
real engineering value or just architectural bloat.

The evaluation harness answers:
- Does each plane have the right structure?
- Do invariants hold after all plane additions?
- What is the benefit-vs-complexity ratio?
- Are there regression failures that block release?

## How It Prevents "ability +10%, complexity +300%"

Every new plane must pass three gates:

1. **Eval suite** — structural checks: do files exist, are dataclasses
   well-formed, do invariants hold?
2. **Benefit/complexity scoring** — measures benefit signals against
   complexity cost. risk_ratio > 3 is an automatic REJECT.
3. **Regression matrix** — verifies that all existing test suites and
   invariants still pass after new plane additions.

A plane that adds 10% ability but 300% complexity will fail the
benefit/complexity gate (risk_ratio > 3 → REJECT).

## Deterministic Local Evals

All evals are:
- **Deterministic** — same input produces same output, always
- **Local** — no network, no external tools, no subprocess
- **Structural** — check existence, shape, invariants, not subjective quality
- **No LLM** — zero AI/LLM imports or calls in evaluation code

## Eval Categories

| Category | What It Checks |
|----------|---------------|
| context | Context plane files and budget policy |
| memory | Memory intelligence profiles and evidence mapping |
| agent | Agent worker profiles and mock determinism |
| workspace | Workspace provider profiles and mock snapshots |
| skill | Skill evolution proposals and profile listing |
| orchestration | Policy enforcement and plan determinism |
| registry | Registry entry validity and type coverage |
| evidence | Evidence record and bundle structure |

## Benefit/Complexity Scoring

### Benefit Signals

| Signal | Weight |
|--------|--------|
| reduces_manual_steps | +1.0 |
| improves_verifiability | +1.0 |
| improves_replaceability | +1.0 |
| improves_safety_boundary | +1.0 |
| improves_debuggability | +1.0 |
| avoids_new_truth_source | +1.5 (required gate) |
| avoids_runtime_dependency | +1.0 |

Max benefit: 7.5.

### Verdict Thresholds

| Condition | Verdict |
|-----------|---------|
| New truth source introduced | REJECT |
| Runtime dependency introduced | REJECT |
| risk_ratio > 3 | REJECT |
| risk_ratio > 2 | REVIEW |
| Otherwise | ACCEPT |

### Risk Ratio

risk_ratio = complexity_score / benefit_score

A module with complexity_score=15.0 and benefit_score=5.0 has
risk_ratio=3.0 → REVIEW (borderline). At complexity_score=20.0 against
benefit_score=5.0, risk_ratio=4.0 → REJECT.

## Regression Matrix

36 checks spanning:
- Kernel invariants (7)
- V4 baseline guard (1)
- Capability contract (2)
- Registry (3)
- Evidence (3)
- Context plane (2)
- Memory intelligence (3)
- Agent worker (3)
- Workspace (2)
- Skill evolution (3)
- Orchestration policy (3)
- Complexity gate (2)
- Evaluation harness self-check (1)

Each check references an existing test or file. Release-blocking
failures are tracked separately.

## What It Does NOT Measure Yet

- Runtime performance (no benchmarking)
- Subjective code quality
- Integration test coverage with real providers
- User-facing UX
- Cross-project adoption metrics

## Future Extension Path

- Add quantitative benchmarks when measurable
- Add cross-project regression references
- Add historical trend tracking (per-phase score evolution)
- Add provider-specific integration test stubs (still mock/dry-run)

## CLI Commands

```bash
python v3/cli/systemkernel.py eval suite       # List default eval cases
python v3/cli/systemkernel.py eval run         # Run deterministic eval suite
python v3/cli/systemkernel.py eval regression  # Generate regression matrix
python v3/cli/systemkernel.py eval benefit     # Benefit-vs-complexity report
```

## Files

- `v3/evals/evaluation_harness.py` — Core eval dataclasses and runner
- `v3/evals/benefit_complexity.py` — Benefit-complexity scoring
- `v3/evals/regression_matrix.py` — Regression check matrix
- `v3/evals/__init__.py` — Exports
- `v3/tests/test_evaluation_harness.py` — Test suite
