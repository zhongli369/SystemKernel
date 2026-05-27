# SystemKernel v3.0 — Architecture Overview

## What SystemKernel Is

SystemKernel is a **deterministic execution kernel** for AI-assisted development.
It's not an agent framework. It doesn't make decisions. It doesn't call LLMs.

It provides five things:
1. **Execution Engine** — runs pipelines deterministically
2. **Event Sourcing** — every state change is an immutable event
3. **Observability** — traces, metrics, and telemetry (write-only, never decides)
4. **Memory** — external projection of execution history (removable, advisory)
5. **Quality Gate** — blocks complexity without benefit

## What SystemKernel Is NOT

| SystemKernel | Agent Frameworks (LangGraph, CrewAI, etc.) |
|---|---|
| Deterministic execution | LLM-driven decision making |
| Events are truth | Conversations are truth |
| Memory is optional projection | Memory is required context |
| Zero LLM in kernel | LLMs everywhere |
| Purity is enforced | Purity is aspirational |
| Complexity is gated | Complexity grows unbounded |

## Core Architecture

### 1. Events are the Source of Truth

Every state transition in SystemKernel is an **ExecutionEvent** — an immutable,
hash-chained record. There are exactly 13 event types:
`EXECUTION_STARTED`, `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`,
`EXECUTION_COMPLETED`, `EXECUTION_FAILED`, etc.

Events are the **only authoritative record** of what happened.
Everything else is a projection.

### 2. Checkpoints are Optimization, Not Truth

Checkpoints are snapshots that speed up recovery. They are **not authoritative**.
If a checkpoint disagrees with events, events win. Always.

### 3. Memory is an External Projection

Memory (`v3/memory/`) is completely outside the kernel boundary (`v3/kernel/`).
The kernel communicates with memory through three contract files only:
- `memory_contract.py` — types for write/read requests
- `memory_candidate.py` — how events project into memory records
- `memory_gateway.py` — pluggable adapter interface

**Memory is removable.** Delete `v3/memory/` and the kernel works unchanged.
Memory writes that fail do not affect execution. Memory reads that return
empty results are always valid.

### 4. Observability is Write-Only

Observability records traces, metrics, and telemetry. It **never** makes
decisions, never predicts, never alerts. Every hook is wrapped in:
```python
try:
    record_span(...)
except Exception:
    pass
```
Delete `v3/traces/` → kernel works. Delete `v3/metrics/` → kernel works.

### 5. The Complexity Gate

The quality gate (`v3/quality/`) performs structural analysis on the codebase
to ensure complexity doesn't grow without proportional benefit.

Five immutable rules:
1. `complexity > benefit * 2` → REVIEW
2. `complexity > benefit * 3` → REJECT
3. New truth source appears → REJECT
4. Kernel purity breaks → REJECT
5. Memory removability breaks → REJECT

## The Pipeline

```
User Intent / External Trigger
        |
        v
  Adapter.resolve()       — route intent to skill
        |
        v
  TaskSystem              — manage task lifecycle
        |
        v
  ExecutionEngine.run()   — deterministic pipeline execution
        |
        +-- emit events   — immutable state transitions
        |
        v
  Observability           — record traces + metrics (write-only)
        |
        v
  Memory (optional)       — project events → episodic store → index → recall
        |
        v
  Quality Gate            — structural complexity analysis
```

## How It Differs from Other Tools

### vs LangGraph
LangGraph is an LLM agent framework. Edges and nodes can call LLMs.
SystemKernel's pipeline is deterministic — no LLM calls in kernel.

### vs CrewAI
CrewAI orchestrates multiple AI agents. SystemKernel orchestrates
deterministic pipeline stages. Zero AI in kernel.

### vs mem0 / Graphiti
These are AI memory systems with embeddings and vector search.
SystemKernel's memory is token-based (inverted index), deterministic,
and requires zero external services.

### vs Traditional Observability (Datadog, Grafana)
These are monitoring platforms that detect anomalies and alert.
SystemKernel's observability is write-only — it records but never decides.

## The Kernel Boundary

Everything inside `v3/kernel/` is the **kernel**. It must be:
- Deterministic
- Zero LLM
- Self-contained (no external services)
- Independent of memory, observability, and quality

Everything outside `v3/kernel/` (memory, quality, cli, examples) is the
**ecosystem**. It can use the kernel's public APIs but the kernel never
imports from them.

## Why This Matters

AI-assisted development faces a fundamental problem: **complexity grows
faster than understanding.** SystemKernel addresses this by:

1. Making events the single source of truth (no ambiguity)
2. Making all other outputs projections (auditable, replayable)
3. Gating complexity (no new code without proportional benefit)
4. Keeping the kernel pure (the core is small, testable, and understandable)
