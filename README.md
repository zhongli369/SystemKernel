# SystemKernel

**A deterministic AI routing and execution kernel with a pluggable intelligence plane.**

SystemKernel is not a framework, not a library. It is a kernel: a minimal,
deterministic core that routes capabilities, orchestrates tasks, enforces
verified execution, and records every decision as an immutable event. Above
that core sits a pluggable intelligence plane — context, memory, evaluation,
and agent workers — that can be attached, removed, or replaced without
affecting kernel behavior.

---

## Architecture

```
SystemKernel
├── v3/kernel/          ● Frozen deterministic core
│   ├── event_store          Immutable event log (source of truth)
│   ├── execution_engine     Execute + verify, max 2 attempts
│   ├── invariants           Kernel purity enforcement (100/100)
│   ├── checkpoint           Save/restore execution state
│   ├── replay               Trace replay engine
│   ├── observability        Deterministic tracing + metrics
│   ├── truth_model          Evidence vs truth classification
│   └── complexity_budget    Ability+10% vs complexity+300% gate
│
├── v3/cli/             ● Developer operations surface
│   ├── systemkernel         Entrypoint (541 LOC, 82% reduction from v3)
│   ├── core_commands        Status, doctor, capability summary
│   ├── external_commands    Context-pack, usage-report, repomix
│   ├── intelligence_commands  Memory, agent-worker, workspace
│   └── eval_ops_commands    Evaluation harness, orchestration
│
├── v3/external/        ● Pluggable intelligence plane (removable)
│   ├── context_pack         Context generation via external providers
│   ├── context_plane        Context engineering policy
│   ├── agent_worker         Subagent dispatch, parallel, worktree isolation
│   ├── memory_intelligence  Episodic/semantic/procedural memory
│   ├── skill_evolution      Registry, contracts, package management
│   ├── capability_registry  JSON-driven capability contracts
│   ├── evidence             Evidence model (truth_source always false)
│   ├── orchestration_policy Evaluation harness, routing, verification gates
│   ├── workspace_context    Checkpoint/replay, snapshot management
│   └── usage_report         Token usage, complexity budget tracking
│
├── v3/evals/           ● Evaluation & selection (stdlib only)
│   ├── evaluation_harness   Automated invariant verification
│   ├── provider_trial_selection  Deterministic 10-dimension scoring
│   ├── benefit_complexity   Complexity gate enforcement
│   └── regression_matrix    Cross-subsystem regression detection
│
├── v3/intake/          ● External repository intake
│   ├── repo_intake         Clone + analyze external repos
│   ├── clone_plan          Intake planning and safety checks
│   └── tool_registry       External tool capability mapping
│
├── v3/integrations/    ● External provider adapters (stubs)
│   ├── repomix/            Context pack generation
│   ├── ccusage/            Claude Code usage reports
│   ├── mem0/               External memory service
│   └── graphiti/           Knowledge graph service
│
├── v3/tests/           ● Test suites
├── v3/quality/         ● Phase gate enforcement
├── v3/exports/         ● Phase reports and evidence bundles
├── scripts/            ● verify_v3_baseline.py, verify_v4_baseline.py
├── api.py              ● Single entry point for external callers
├── architecture_guard.py ● Architecture drift detection
└── external_trials/    ● Controlled external provider trial outputs
```

---

## Core Principles

- **Pure Kernel** — Zero LLM in `v3/kernel/`. Adapter, TaskSystem, EventBus,
  ExecutionLoop, Observability are LLM-free. Stability: 96/100.
- **EventStore as Source of Truth** — Every decision, route, execution, and
  validation is an immutable event. Everything else is derived.
- **External Outputs are Evidence, Not Truth** — Agent outputs, LLM responses,
  and external tool results are recorded as evidence. `truth_source` is always
  `false` for external data. They never directly mutate kernel state.
- **Memory is Removable** — Delete the memory plane; the kernel continues to
  function. Memory enhances; it does not depend.
- **Complexity Gate** — ability +10% must not cost complexity +300%.
  Enforced by `benefit_complexity.py` and phase gates.
- **External Providers are Trials, Not Dependencies** — Repomix, ccusage, ECC,
  mem0, Graphiti, OpenHands, Continue are external capability providers scored
  and trialed through the intelligence plane. They are never embedded in the
  kernel.

---

## Quick Start

```python
from api import resolve_skill, run_skill, create_task_safe

# Route intent to skill
binding = resolve_skill(intent="refactor", context="decouple utils/helpers.py")
if binding.skill_id:
    task = create_task_safe(title=f"[{binding.skill_id}] Refactor")
    result = run_skill(skill_id=binding.skill_id, target="./src")
    print(f"Success: {result.success}, Verified: {result.verification_passed}")
```

```bash
# Kernel status & health
python v3/cli/systemkernel.py status
python v3/cli/systemkernel.py doctor

# Verification
python scripts/verify_v3_baseline.py
python scripts/verify_v4_baseline.py

# Architecture drift check
python architecture_guard.py
python architecture_guard.py --json

# Context pack generation (external provider trial)
python v3/cli/systemkernel.py context-pack plan ./src --output ctx.md
```

---

## Versions

| Tag | Description |
|-----|-------------|
| `systemkernel-v3.0.0-baseline` | Deterministic Runtime Kernel (frozen core, 5 subsystems) |
| `systemkernel-v4.0.0-pluggable-intelligence` | Pluggable Intelligence Plane + Provider Trial Selection |

---

## What Is Intentionally Not Included

- **No real mem0 / Graphiti / OpenHands / AutoGen / Continue / ECC
  integration** — These are scored as external capability providers through
  deterministic trial selection. Adapters exist as stubs; actual execution
  requires explicit `--allow-execute`.
- **No external provider execution by default** — The Repomix controlled
  trial (Phase 14B) is the sole external execution performed, and it was
  confined to `external_trials/repomix/` with `truth_source=false`.
- **No kernel LLM dependency** — Zero LLM imports in `v3/kernel/`, CLI,
  evals, or intake. The intelligence plane may use LLMs externally, but
  it is removable.
- **ECC is an external provider, not an internal component** — SystemKernel
  models ECC interfaces in the intelligence plane. ECC capabilities arrive
  through the pluggable plane, never through kernel modification.

---

## Repository

https://github.com/zhongli369/SystemKernel
