# Complexity Budget Architecture

## Phase 5A — Deterministic Value-Based Gating

### Overview

The Complexity Budget Gate ensures every phase delivers positive net value.
It blocks phases that add complexity without proportional benefit.

### Architecture

```
Source Modules (kernel/, memory/, quality/)
    |
    v
ComplexityAnalyzer (AST-based, deterministic)
    |
    +-- ModuleComplexity (loc, API, deps, side effects, truth sources)
    |
    v
compute_complexity_score()  ── weighted sum of risk factors
    |
    v
ModuleBenefit (debuggability, recoverability, determinism, etc.)
    |
    v
compute_benefit_score()     ── sum of boolean benefit fields
    |
    v
evaluate_verdict()          ── ACCEPT / REVIEW / REJECT
    |
    v
PhaseGateResult             ── final gate output
```

### Scoring Model

#### Complexity Score (weighted)

| Factor | Weight | Rationale |
|--------|--------|-----------|
| LOC / 100 | 0.25 | Maintenance burden |
| Public API count | 0.15 | Coupling surface |
| Import count | 0.10 | Dependency cost |
| Internal deps | 0.15 | Intra-system coupling |
| External deps | 0.20 | External risk |
| Has side effects | 0.50 | Non-determinism risk |
| Truth source count | 0.80 | Architectural risk (highest penalty) |
| Projection only | -0.30 | Reduces risk |
| Removable | -0.40 | Reduces risk |
| Test coverage | -0.05/test | Reduces risk |
| Report artifacts | -0.03/report | Reduces risk |

#### Benefit Score (additive)

| Benefit | Value |
|---------|-------|
| Improves debuggability | +1.0 |
| Improves recoverability | +1.0 |
| Improves determinism | +1.0 |
| Reduces manual steps | +1.0 |
| Simplifies public API | +1.0 |
| Preserves kernel purity | +0.5 |
| Preserves memory removability | +0.5 |
| Preserves truth source | +0.5 |

Max benefit score: 6.5

### Gate Rules

```
1. complexity > benefit * 2  →  REVIEW
2. complexity > benefit * 3  →  REJECT
3. New truth source appears  →  REJECT
4. Kernel purity breaks      →  REJECT
5. Memory removability breaks → REJECT
```

Rules 3-5 are immediate gates — they bypass the scoring model entirely.

### Verdict Flow

```
ModuleComplexity[] + ModuleBenefit[]
    |
    +-- Rule 4: kernel purity?    --NO--> REJECT
    +-- Rule 5: memory removable? --NO--> REJECT
    +-- Rule 3: new truth source? --YES-> REJECT
    |
    +-- Rule 2: C > B*3?          --YES-> REJECT
    +-- Rule 1: C > B*2?          --YES-> REVIEW
    +-- Net value < 0?            --YES-> REVIEW
    |
    +-- Otherwise: ACCEPT
```

### Modules

| File | Purpose |
|------|---------|
| `v3/quality/complexity_budget.py` | Core types: ModuleComplexity, ModuleBenefit, ComplexityBudgetVerdict, scoring functions |
| `v3/quality/analyze_complexity.py` | AST-based analyzer: LOC counting, import extraction, dependency tracking, truth source detection |
| `v3/quality/phase_gate.py` | Phase gate: evaluate_phase(), load_budget_policy(), write_complexity_report(), fail_if_rejected() |

### Invariants

1. Zero LLM — no AI imports anywhere in the pipeline
2. Deterministic — same code → same scores → same verdict
3. Kernel-pure — quality/ is outside kernel boundary
4. Removable — delete v3/quality/ → zero kernel impact
5. Projection only — analysis derives from code AST, never creates data
6. Stdlib only — ast, os, json, hashlib, re
