# SystemKernel v4.0 — Pluggable Intelligence Plane

**Version:** 4.0.0 | **Codename:** Pluggable Intelligence Plane
**Baseline:** v3.0.0 (commit `13f2069`) | **Date:** 2026-05-26

---

## Vision

v3.0 is a deterministic execution kernel — 100% pure, zero LLM, fixed pipeline.
v4.0 extends this with a **pluggable intelligence plane**: optional, removable,
isolated modules that add AI capabilities WITHOUT compromising kernel purity.

Every intelligence module is:
- **Outside the kernel boundary** — never imported by kernel code
- **Removable** — delete the module, kernel behavior is unchanged
- **Swapable** — replace one provider with another (e.g., OpenAI → local model)
- **Deterministically gated** — same input always produces the same routing decision

---

## 12-Phase Roadmap

### Phase 0 — v3 Baseline Protection (CURRENT)

Freeze v3.0 kernel state. Create baseline guard with protected paths, forbidden
dependency checks, and automated verification. Ensure v4.0 work can always be
validated against the v3.0 baseline.

**Deliverables:** V4_ROADMAP.md, V4_INVARIANTS.md, v4_baseline_guard.py,
baseline guard tests, guard reports.

**Gate:** All baseline guard tests pass. Kernel invariants 100/100.

---

### Phase 1 — Capability Adapter Contract

Formalize the Adapter contract for pluggable intelligence. Define the
CapabilityAdapter abstract base class: `can_handle(intent) → bool`,
`execute(request) → result`, `health_check() → status`. Every v4.0
intelligence module implements this contract.

**Deliverables:** `v4/intelligence/adapter_contract.py`, contract tests.

**Gate:** Adapter contract tests pass. No kernel modifications.

---

### Phase 2 — LLM Provider Abstraction

Define a provider-agnostic LLM interface. Support multiple backends:
OpenAI, Anthropic, local models (ollama, llama.cpp). Provider selection
is configuration-driven, never hardcoded.

**Deliverables:** `v4/intelligence/providers/` with abstract base + at least
one concrete provider, provider config schema, provider tests.

**Gate:** Swap providers without code changes. Provider tests pass.

---

### Phase 3 — Memory Intelligence

Replace v3.0 lexical memory with pluggable semantic memory. Support
vector stores (ChromaDB, Qdrant, Milvus) as optional backends behind
a common MemoryBackend interface. Memory is an intelligence module,
not a kernel subsystem.

**Deliverables:** `v4/intelligence/memory/` with MemoryBackend ABC,
at least one vector store adapter, semantic search API, memory tests.

**Gate:** Memory module removable. Kernel invariants 100/100 with memory deleted.

---

### Phase 4 — Smart Routing

Extend the deterministic Adapter with an optional AI router. When enabled,
routes intents using embeddings + similarity search. Falls back to
deterministic routing when disabled. Deterministic path is ALWAYS available.

**Deliverables:** `v4/intelligence/smart_router.py`, embedding-based
intent matching, fallback chain: AI → deterministic → empty binding.

**Gate:** Deterministic routing unchanged when AI router is disabled/removed.

---

### Phase 5 — Autonomous Execution Agent

Pluggable agent loop that can chain multiple skill executions. Agent
observes execution results, decides next step, invokes next skill.
Agent is fully removable — without it, execution is the standard
single-pass pipeline.

**Deliverables:** `v4/intelligence/agent_loop.py`, agent configuration
schema, agent execution traces, agent tests.

**Gate:** Agent removable. Standard ExecutionLoop behavior unchanged.

---

### Phase 6 — Observability Intelligence

Optional AI-powered observability: anomaly detection on trace patterns,
cost prediction from usage trends, bottleneck identification. All
intelligence is read-only — never modifies kernel behavior.

**Deliverables:** `v4/intelligence/smart_observability.py`,
anomaly detector, cost predictor, observability tests.

**Gate:** Observability intelligence removable. Write-only contract preserved.

---

### Phase 7 — Event Intelligence

Pluggable event classification and prioritization. AI-powered event
understanding that augments (never replaces) the deterministic routing
table. Deterministic routing always takes precedence.

**Deliverables:** `v4/intelligence/smart_events.py`, event classifier,
priority suggester, event intelligence tests.

**Gate:** Deterministic EventBus unchanged when intelligence module removed.

---

### Phase 8 — Tool Intelligence

Pluggable tool selection and adaptation. AI-powered tool recommendation
based on task context. Tools remain external — intelligence only advises
which tool to use, never executes tools directly.

**Deliverables:** `v4/intelligence/smart_tools.py`, tool recommender,
tool adaptation hints, tool intelligence tests.

**Gate:** External tool boundary preserved. No tool execution from intelligence plane.

---

### Phase 9 — Intent Understanding

Natural language intent parsing. Converts freeform user requests into
structured CapabilityRequest objects. Purely additive — existing
structured intent API remains the primary interface.

**Deliverables:** `v4/intelligence/intent_parser.py`, NL→structured
intent converter, confidence scoring, intent parser tests.

**Gate:** Structured CapabilityRequest API unchanged. Parser removable.

---

### Phase 10 — Self-Testing Intelligence

AI-powered test generation from execution traces. Suggests test cases
based on observed failures and edge cases. Tests are suggestions only —
never automatically added to the test suite.

**Deliverables:** `v4/intelligence/test_suggester.py`, trace→test
generator, test quality scoring, test suggester tests.

**Gate:** No automatic test modification. Suggester removable.

---

### Phase 11 — Documentation Intelligence

AI-powered documentation generation from code and execution traces.
Produces draft docs that require human review. Never publishes
without explicit approval.

**Deliverables:** `v4/intelligence/doc_generator.py`, code→doc
generator, trace→doc generator, doc generator tests.

**Gate:** No automatic doc publishing. Generator removable.

---

### Phase 12 — Intelligence Plane Integration

Final integration phase. End-to-end tests across all intelligence
modules. Full removal test (delete entire v4/intelligence/ → kernel
behaves identically to v3.0 baseline). Release freeze.

**Deliverables:** Integration test suite, removal verification,
v4.0 release notes, operational handoff.

**Gate:** All 12 phases complete. Full removal test passes.
Kernel invariants 100/100 with and without intelligence plane.

---

## Architecture Principle

```
┌──────────────────────────────────────────┐
│         INTELLIGENCE PLANE (v4.0)         │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐ │
│  │Router│ │Memory│ │Agent │ │Observab..│ │  ← All removable
│  └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘ │
│     │        │        │          │        │
│     └────────┼────────┼──────────┘        │
│              │        │                   │
│   ═══════════╪════════╪══════════════════ │  ← Adapter Contract
│              │        │                   │
│  ┌───────────┴────────┴─────────────────┐ │
│  │       DETERMINISTIC KERNEL (v3.0)    │ │
│  │  Adapter │ TaskSys │ ExecLoop │ ... │ │  ← Immutable
│  └──────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

The kernel never knows the intelligence plane exists.
The intelligence plane decorates the kernel through the adapter contract.
Remove the top half → you have pure v3.0.
