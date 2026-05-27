# SystemKernel v4.0.0 — Pluggable Intelligence Plane

Release date: 2026-05-27
Tag: systemkernel-v4.0.0-pluggable-intelligence

---

## What is SystemKernel v4.0

SystemKernel v4.0 is a governance and pluggable intelligence boundary release. It defines how external AI systems can be evaluated, registered, evidenced, planned, and governed — without integrating any real external providers.

The kernel remains deterministic, LLM-free, and memory-removable. All v4 additions are read-only planning planes that operate at the boundary, never inside the kernel.

## Difference from v3.0

v3.0 established the deterministic kernel boundary: Adapter, TaskSystem, ExecutionLoop, EventBus, Observability — all LLM-free, all pure-Python, all memory-removable.

v4.0 adds the **Pluggable Intelligence Plane** — a governance layer that:

- Defines a Capability Contract for external AI providers
- Maintains a Capability Registry (read-only, file-based)
- Records Evidence Bundles with explicit `truth_source=False`
- Plans Context Packs without executing external tools
- Defines memory, agent, workspace, and skill-evolution planes as read-only schemas
- Provides Orchestration Policy profiles (dry-run only)
- Includes a deterministic Evaluation Harness with benefit-complexity scoring
- Ships operational tooling: status, checklists, runbooks

## Completed Phases (0–12)

- **Phase 0:** Kernel Boundary & Constitution
- **Phase 1:** EventBus
- **Phase 2:** Kernel Hardening
- **Phase 3:** Observability (Traces + Metrics + Replay)
- **Phase 4:** TaskSystem + ExecutionLoop Integration
- **Phase 5:** Complexity Budget & Quality Gate
- **Phase 5A:** Complexity Budget Hardening
- **Phase 6:** Architecture Guard + Drift Detection
- **Phase 7:** Memory Intelligence Plane (read-only schema)
- **Phase 7.5:** Memory Compaction Integrity
- **Phase 8:** External Evidence Model
- **Phase 8.5:** External Tools Clone Report
- **Phase 9:** Capability Registry + Context Plane + Agent Worker + Workspace + Skill Evolution + Orchestration
- **Phase 9.5:** Complexity Sanity Check
- **Phase 10:** Evaluation Harness + Regression Matrix
- **Phase 11:** Productization + Ops
- **Phase 12:** Release Freeze

## Pluggable Intelligence Plane Overview

The v4 Pluggable Intelligence Plane is a governance boundary. It wraps the deterministic kernel and provides structured, read-only interfaces for evaluating external AI capabilities.

### Capability Contract

Defines the contract external AI providers must satisfy. All external capabilities are evaluated against this contract before registry entry.

### Capability Registry

File-based registry of 10 capability adapters across 8 types. 2 enabled (safe-context-only), 8 disabled (including ECC as future placeholder).

### Evidence Model

EvidenceBundle records with explicit `truth_source=False`. All external evidence is TRUST_LOW by default. Never used for kernel decisions.

### Context Engineering Plane

Plans context packs for codebase analysis. Dry-run by default. Budget policy limits scope. No external tool execution.

### Memory Intelligence Plane

Read-only schema for memory compaction, episodic projection, and integrity checks. No runtime memory decisions.

### Agent Worker Plane

Read-only schema for agent worker lifecycle. Defines worker states, task queues, and capability contracts. No agent execution.

### Workspace Plane

Read-only schema for workspace isolation. Defines file scoping, sandbox boundaries. No runtime enforcement.

### Skill Evolution Plane

Read-only schema for skill proposals. Dry-run only. Skills are proposed, never auto-modified.

### Orchestration Policy

6 policy profiles for orchestrating capability adapters. All dry-run. ECC profile (ecc_harness_review) disabled placeholder.

## Evaluation Harness

Deterministic eval suite with 19 cases across 8 categories. Benefit-complexity scoring prevents ability+10 complexity+300 regressions. 35 regression checks across 13 categories. All local, no network, no LLM.

## Productization + Ops

Day-to-day operational tooling:

- `v4 status` — operational health snapshot
- `v4 ops-check` — 22-item checklist across 8 categories
- `v4 runbook` — 11-section operational runbook
- `v4 summary` — compact operational summary

## ECC Handling

ECC (everything-claude-code) is treated as a **disabled future placeholder**.

- Listed as `ecc_harness_review` orchestration profile — disabled, dry-run only
- Covers 4 of 8 capability types: skill, tool, eval, context
- Never auto-installed, auto-cloned, or auto-executed
- Requires a formal Phase 12+ trial gate before any integration
- SystemKernel must not become an ECC clone or dependency

## What Is Intentionally NOT Included

- Real external provider integration (Mem0, Graphiti, OpenHands, AutoGen, Continue, ECC)
- LLM/AI imports in kernel modules
- Network access from any kernel or release module
- External tool execution through the kernel boundary
- New truth sources (truth_source always False for external data)
- Agent execution or autonomous decision-making
- IDE API access
- Runtime memory intelligence decisions
- Auto-modification of registry or skills

## Safety Invariants

- Kernel purity: 100/100 — zero LLM imports in kernel
- Memory removable: YES — kernel runs without memory subsystem
- Deterministic routing: same input always produces same output
- No external execution: all orchestration is dry-run
- No truth source elevation: external data truth_source=False
- Complexity gate: benefit must exceed complexity cost
- Read-only ops: all operational commands are side-effect-free

## Complexity Guard

Complexity budget enforced by `v3/quality/complexity_budget.py`. Risk ratio = complexity / benefit. REJECT at >3.0, REVIEW at >2.0. New truth sources and lost memory removability are automatic rejection.

## Known Limitations

- No real provider integration — all external capabilities are schemas and dry-run plans
- Evidence model is trust-low by design — not suitable for automated decisions
- Orchestration is planning-only — no execution engine
- Memory intelligence is schema-only — no runtime compaction or projection
- Agent worker is schema-only — no actual agent lifecycle management
- Context packs are planned but not auto-generated from external sources
- ECC is listed but fully disabled — no integration timeline

## Next Possible Directions

- Formal provider trials with explicit safety gates (post-Phase 12)
- ECC evaluation with trial harness (requires human approval)
- Automated context pack generation from safe local sources
- Memory compaction with integrity verification (read-only projection)
- Agent worker lifecycle management with capability contract validation
- Skill evolution proposal pipeline with automated regression checks
- Cross-plane integration testing framework

---

SystemKernel v4.0.0 — Pluggable Intelligence Plane
Generated: 2026-05-27 13:51:37
PURE KERNEL | MEMORY REMOVABLE | ZERO EXTERNAL INTEGRATION