# SystemKernel

**A deterministic AI routing and execution kernel with a pluggable intelligence plane.**

SystemKernel is not a framework, not a library. It is a kernel: a minimal,
deterministic core that routes capabilities, orchestrates tasks, enforces
verified execution, and records every decision as an immutable event. Above
that core sits a pluggable intelligence plane — memory, context, evaluation,
and agent workers — that can be attached, removed, or replaced without
affecting kernel behavior.

---

## Versions

### v3.0 — Deterministic Runtime Kernel

The frozen deterministic core. Five subsystems, zero LLM:

| Subsystem | Responsibility |
|-----------|---------------|
| Adapter | Route intent → skill. Deterministic. Does NOT execute. |
| TaskSystem | Task lifecycle (backlog → active → done). Does NOT route or execute. |
| EventBus | Ingest external events. 13 deterministic rules. No classification. |
| ExecutionLoop | Execute + verify (max 2 attempts). Does NOT route or create tasks. |
| Observability | Record traces + metrics. Does NOT decide, predict, or alert. |

Tag: `systemkernel-v3.0.0-baseline`

### v4.0 — Pluggable Intelligence Plane

Adds intelligence capabilities as removable, external planes. The kernel
remains pure — intelligence is attached, not embedded:

- **Memory Intelligence Plane** — episodic, semantic, and procedural memory
  with compaction, recall, and indexing. Fully removable.
- **Agent Worker Plane** — subagent dispatch, parallel execution, worktree
  isolation, skill-driven worker lifecycle.
- **Workspace Plane** — checkpoint/replay, snapshot management, trace
  replay, evidence model.
- **Context Plane** — usage adapter, complexity budget, context packing,
  token optimization.
- **Skill Evolution Plane** — registry, capability contracts, skill
  metadata, package management.
- **Orchestration Policy** — evaluation harness, routing policy,
  verification gates, complexity gate.
- **Evidence Model** — external outputs are evidence, never truth.
  EventStore is the sole source of truth.

Tag: `systemkernel-v4.0.0-pluggable-intelligence`

---

## Core Principles

- **Pure Kernel** — The v3 deterministic core has no LLM calls, no
  probabilistic routing, no shadow logic. Stability: 96/100.
- **EventStore as Source of Truth** — Every decision, route, execution,
  and validation is recorded as an immutable event. The event log is truth;
  everything else is derived.
- **External Outputs are Evidence, Not Truth** — Agent outputs, LLM
  responses, external tool results are evidence recorded in the event log.
  They never directly mutate kernel state.
- **Memory is Removable** — Delete the memory plane and the kernel
  continues to function. Memory enhances; it does not depend.
- **Zero LLM in Kernel** — No LLM import, call, or API exists in Adapter,
  TaskSystem, EventBus, ExecutionLoop, or Observability.
- **Complexity Gate** — Every capability addition is measured against a
  complexity budget. The rule: ability +10% must not cost complexity +300%.

---

## Major Capabilities

| Capability | Description |
|-----------|-------------|
| Event Sourcing | Immutable event log as system source of truth |
| Checkpoint / Replay | Save and replay execution traces |
| Observability Graph | Trace chains, metric points, span lineage |
| External Memory Runtime | Episodic, semantic, procedural memory planes |
| Context Plane | Usage adapter, complexity budget, token optimization |
| Capability Contract | Typed, frozen dataclasses for every subsystem boundary |
| Registry | JSON-driven skill registry with manifest + SKILL.md authority |
| Evidence Model | External outputs treated as evidence, not kernel state |
| Agent Worker Plane | Subagent dispatch, parallel workers, worktree isolation |
| Workspace Plane | Snapshots, trace replay, checkpoint management |
| Skill Evolution Plane | Registry, contracts, package management |
| Orchestration Policy | Evaluation harness, verification gates, routing policy |
| Evaluation Harness | Automated verification of kernel invariants and baselines |

---

## Quick Commands

```bash
# Verify v3 deterministic baseline
python scripts/verify_v3_baseline.py

# Verify v4 pluggable intelligence baseline
python scripts/verify_v4_baseline.py

# Kernel status
python v3/cli/systemkernel.py v4 status

# Kernel summary
python v3/cli/systemkernel.py v4 summary

# Run evaluation harness
python v3/cli/systemkernel.py eval run
```

---

## Release Tags

| Tag | Description |
|-----|-------------|
| `systemkernel-v3.0.0-baseline` | Deterministic Runtime Kernel (frozen core) |
| `systemkernel-v4.0.0-pluggable-intelligence` | Pluggable Intelligence Plane |

---

## What Is Intentionally Not Included

- **No real mem0 / Graphiti / OpenHands / AutoGen / Continue / ECC
  integration** — These are referenced as external capability providers.
  The kernel models their interfaces but does not bundle or call them.
- **No external provider execution by default** — External tool adapters
  exist as stubs. Actual execution requires explicit configuration.
- **No kernel LLM dependency** — The kernel has zero LLM imports. The
  intelligence plane may use LLMs, but it is external and removable.

---

## ECC Positioning

ECC (everything-claude-code) is treated as a future external harness
enhancement provider. SystemKernel should use and evaluate ECC, not become
an ECC clone. ECC capabilities — when integrated — arrive through the
pluggable intelligence plane, never through kernel modification.

---

## Repository

https://github.com/zhongli369/SystemKernel
