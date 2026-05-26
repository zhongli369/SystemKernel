# SystemKernel v3.0 — Release Notes

**Version:** 3.0.0
**Codename:** Deterministic Kernel
**Date:** 2026-05-25
**Status:** STABLE BASELINE — Feature Freeze

---

## What Is SystemKernel v3.0

SystemKernel is a deterministic AI execution kernel. It routes intents to
skills, executes them via a fixed verification pipeline (lint → typecheck →
test → report), and records every decision as an immutable event stream.

It is NOT an agent framework. It is NOT an LLM orchestrator. It is a
**kernel** — small, auditable, and guaranteed to produce the same output
for the same input.

### Core Architecture

```
External Events → EventBus → Adapter → TaskSystem → ExecutionLoop → Observability
                      ↑                        ↓
                      └── Memory (removable projection)
```

### Three Execution Paths

1. **Intent (normative):** CapabilityRequest → Adapter.resolve() → TaskSystem → ExecutionLoop
2. **Event:** External trigger → EventBus.ingest() → validate → route → dispatch
3. **Short (demo):** Adapter.resolve() → ExecutionLoop (skips TaskSystem)

---

## Completed Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 4 | Runtime / Observability / Memory | COMPLETE |
| 5A | Complexity Budget Gate | COMPLETE |
| 5B | Developer CLI | COMPLETE |
| 5C | Golden Path + Documentation | COMPLETE |
| 5D | Repo Intake Pipeline | COMPLETE |
| 5E | External Tool Registry + Clone Plan | COMPLETE |
| 5F | Release Freeze + Validation | COMPLETE |

---

## Major Capabilities

### Kernel (v3/kernel/)
- Deterministic event-sourced execution engine
- Single-loop guarantee (no nested execution)
- Fixed pipeline: lint → typecheck → test → [custom] → report
- Max 2 attempts (initial + 1 error-based correction)
- Checkpoint/restore with crash recovery
- Replay from event stream (deterministic)
- Time-travel debugging (rewind, fork, diff)
- Invariant telemetry
- Memory gateway (isolated boundary)

### Memory (v3/memory/)
- Episodic store (append-only JSONL)
- Semantic index (lexical, no embeddings)
- Compaction (deterministic dedup + merge)
- Truth-linked recall with provenance
- Integrity checking (store, index, compaction)
- Unified runtime facade
- **Fully removable** — kernel behavior unchanged without it

### Quality (v3/quality/)
- Complexity budget gate (ACCEPT/REVIEW/REJECT)
- AST-based module analysis
- Directory-level complexity scoring
- Benefit scoring with policy-driven thresholds
- Phase gate evaluation

### CLI (v3/cli/)
- `systemkernel status` — kernel purity, test count, memory status
- `systemkernel quality` — run complexity gate
- `systemkernel memory report` — memory system report
- `systemkernel reports list|summary` — export report management
- `systemkernel doctor` — health checks (19 checks)
- `systemkernel intake profile|list|summarize` — repo assessment
- `systemkernel intake registry` — external tool registry
- `systemkernel intake clone-plan` — GitHub clone plan
- `systemkernel intake clone-list` — recommended clone order

### Repo Intake (v3/intake/)
- Deterministic assessment of 14 external repositories
- 5 decision types: DIRECT_CLONE, EXTERNAL_EXTENSION, ARCHITECTURE_REFERENCE, REJECT
- 9 interpretable rules (priority-ordered)
- Pre-built profiles (no network needed)
- External tool registry with use_mode classification
- Safe clone plan with explicit forbidden actions

### Golden Path (examples/golden_path/)
- End-to-end execution demonstration
- 13 deterministic events
- Memory candidate generation + recall
- Full report suite

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Kernel purity | 100/100 |
| Memory removable | YES |
| Complexity gate | REVIEW |
| Python modules | 45 |
| Test functions | 388 |
| External tools evaluated | 14 |
| CLI commands | 12 |
| Validation checks | 40 |
| System invariants | 6 |

---

## What Is Intentionally NOT Included

SystemKernel v3.0 makes explicit exclusions. These are design decisions,
not gaps:

1. **No LLM SDK anywhere in kernel/** — no openai, anthropic, langchain, etc.
2. **No vector database** — no chromadb, qdrant, pinecone, etc. in kernel
3. **No agent framework** — not langchain, crewai, autogen, etc.
4. **No network access** — kernel does not make HTTP calls
5. **No AI decision-making in pipeline** — EventBus, ExecutionLoop, Adapter are deterministic
6. **No direct external repo integration** — all external tools go through registry + clone plan
7. **No new truth sources** — events are the single source of truth
8. **No model training or inference** — this is an execution kernel, not an ML system

---

## Safety Invariants

| # | Invariant | Status |
|---|-----------|--------|
| 1 | Single-loop execution (no nested loops) | ENFORCED |
| 2 | Memory does not interfere with execution | ENFORCED |
| 3 | Tool adapters are LLM-free | ENFORCED |
| 4 | Pipeline stages are immutable (fixed order) | ENFORCED |
| 5 | Memory is side-effect only (projection) | ENFORCED |
| 6 | Observability is read-only (writes, never decides) | ENFORCED |

---

## Known Limitations

1. **Single-machine only** — no distributed execution. Event store is local JSONL.
2. **No real-time streaming** — execution is batch-oriented.
3. **Memory is lexical only** — semantic index uses tokenization, not embeddings.
4. **14 repo profiles** — intake pipeline covers 14 known repos. Extending requires adding profiles.
5. **No MCP server** — CLI is the primary interface. No MCP protocol support.
6. **No web UI** — stdout text output only.
7. **Windows paths** — default paths use `F:/Claude/` conventions. Portable elsewhere.
8. **No incremental adoption path** — requires full SystemKernel runtime.

---

## Upgrade Policy

SystemKernel v3.0 is a **baseline release**. Future versions:

- Must not decrease kernel purity below 100
- Must not make memory non-removable
- Must not introduce LLM imports into kernel/
- Must not add new truth sources
- Must pass complexity gate (not REJECT)
- Must pass all existing tests (regression)

Breaking changes require a new major version (v4.0).

---

## Next Phase Recommendations

1. **Stabilization** — run v3.0 in production-like scenarios, collect telemetry
2. **MCP Integration** — add MCP server for tool-based interaction
3. **Performance profiling** — measure execution latency, identify bottlenecks
4. **Extended profiles** — add more repo profiles to the intake pipeline
5. **Package distribution** — make SystemKernel installable via pip

---

## Release Hashes

| Artifact | Hash |
|----------|------|
| Validation matrix | (see release_validation_matrix.json) |
| Project inventory | (see release_inventory.json) |
---

*SystemKernel v3.0 "Deterministic Kernel" — 2026-05-25*
*Feature freeze. No new runtime capabilities.*


<!-- Release notes hash: 485ebad204822353 -->
