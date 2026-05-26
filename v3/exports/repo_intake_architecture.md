# Repo Intake Pipeline — Architecture

## SystemKernel v3.0 Phase 5D

### Overview

The Repo Intake Pipeline is a **deterministic, zero-network** system for evaluating
whether external GitHub repositories should be integrated into the developer's
working environment.

It produces one of four decisions for each repo:
- **DIRECT_CLONE** — safe to clone and use directly
- **EXTERNAL_EXTENSION** — use as external service via API only
- **ARCHITECTURE_REFERENCE** — study design patterns, don't integrate
- **REJECT** — not suitable for any integration

### Architecture

```
RepoProfile (static data, 14 pre-built)
    │
    ├── RepoIntakeInput (name, url, category, intended use)
    │
    ├── analyze_repo_snapshot() → RepoSignals
    │       │
    │       ├── File extension → language hints
    │       ├── Directory names → CLI/MCP/tests/docs signals
    │       ├── Dependency files → parsed deps
    │       └── _classify_dependencies() → risk counts
    │
    ├── decide_repo_intake() → RepoIntakeDecision
    │       │
    │       ├── Claude Code value (0-10)
    │       ├── SystemKernel value (0-10)
    │       ├── Complexity risk (0-10)
    │       ├── Purity risk (0-10)
    │       ├── Maintenance risk (0-10)
    │       └── Decision rules (9 priority-ordered)
    │
    └── apply_rules() → (decision, rule_id)
            │
            └── Interpretable rule matching
```

### Scoring Model

**Claude Code Value (0-10):**
- +2 has_readme, +2 has_cli, +2 has_mcp
- +1 has_skill_manifest, +1 has_examples, +1 has_tests, +1 has_docs
- -2 per banned dep, -1 per heavy dep
- Base: 5.0, capped [0, 10]

**SystemKernel Value (0-10):**
- +2 has_plugin_manifest, +2 has_tests, +2 has_license
- +1 has_readme, +1 has_docs, +1 has_examples
- -2 per LLM dep, -2 per framework dep, -1 per memory dep
- Base: 5.0, capped [0, 10]

**Risk Scores (0-10, lower is better):**
- Complexity: heavy×2 + framework×1.5 + (no readme)×2 + (banned>0)×1
- Purity: banned×3 + llm×2 + framework×1
- Maintenance: (no license)×3 + heavy×1.5 + (no tests)×2 + (no readme)×1

### Decision Rules (Priority Order)

| Rule | Condition | Decision |
|------|-----------|----------|
| R01 | Pure CLI + README + license + low risk + high value | DIRECT_CLONE |
| R02 | Framework deps >= 1 | ARCHITECTURE_REFERENCE |
| R03 | LLM deps >= 1 | EXTERNAL_EXTENSION |
| R04 | Memory/heavy deps > 0 | EXTERNAL_EXTENSION |
| R05 | Banned deps > 0 | ARCHITECTURE_REFERENCE |
| R06 | Has README + license (moderate value) | EXTERNAL_EXTENSION |
| R07 | No readme + no code signals | REJECT |
| R08 | Banned>=2 + no license + no readme | REJECT |
| R09 | Default fallthrough | ARCHITECTURE_REFERENCE |

### Repo Type Classification

8 types: `agent_runtime`, `memory_system`, `observability_tool`,
`claude_code_extension`, `skill_system`, `context_tool`, `docs_only`, `unknown`

### Module Structure

```
v3/intake/
├── __init__.py          # Public API exports
├── repo_intake.py       # Core: dataclasses, analysis, scoring, I/O (~450 lines)
├── rules.py             # Interpretable rules + repo type classification (~230 lines)
└── repo_profiles.py     # 14 pre-built repo profiles (~280 lines)
```

### CLI Integration

```
python v3/cli/systemkernel.py intake list       # List all 14 profiles
python v3/cli/systemkernel.py intake profile <n> # Detailed profile assessment
python v3/cli/systemkernel.py intake summarize   # All decisions + distribution
```

### Invariants Maintained

| Invariant | Status |
|-----------|--------|
| Zero network access | CONFIRMED — no urllib, requests, httpx, socket |
| Kernel purity | CONFIRMED — zero banned imports in intake/ |
| Deterministic | CONFIRMED — stable hashes, rule-match verified |
| Memory boundary | CONFIRMED — intake/ outside kernel boundary |
| Complexity REVIEW | CONFIRMED — gate not REJECT |
| All profiles match | CONFIRMED — 14/14 scoring = expected |
| Rules match scoring | CONFIRMED — 14/14 rule decisions = scoring decisions |
