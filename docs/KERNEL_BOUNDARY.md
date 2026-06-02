# KERNEL_BOUNDARY.md — SystemKernel Boundary Specification v1.0

> **Status:** FROZEN — changes require a Freeze Override (CLAUDE.md Section 5.3)
> **Adopted:** 2026-05-23
> **Phase:** 0 — Kernel Boundary Freeze

---

## 1. Kernel Definition

### SystemKernel IS

A **deterministic routing + execution kernel** for AI skill calls.
It is the single source of truth for:

- **Routing** — intent + context → skill binding (stateless, deterministic)
- **Task Lifecycle** — backlog → active → done state machine
- **Execution Validation** — bounded verification gate (init + 1 retry)
- **Event Ingestion** — (Phase 1) external trigger normalization

### SystemKernel IS NOT

| NOT this | Why |
|----------|-----|
| Agent Framework | No autonomous behavior, no reasoning, no planning |
| AI Operating System | No process model, no resource scheduling, no memory management |
| Prompt Engine | No prompt generation, no prompt optimization, no LLM orchestration |
| Memory Brain | No cognitive architecture, no knowledge graphs, no belief state |
| Workflow AI Platform | No business process automation, no multi-step autonomous chains |
| Skill Runtime | Does not execute skills — skills execute themselves; Kernel only validates |
| SDK | No API client ownership, no model-specific logic |

### One-sentence identity

> SystemKernel is the traffic control center and quality gate for all AI skill calls.
> It decides WHERE a request goes and verifies it COMPLETED correctly.
> It does not decide WHAT to do or HOW to do it.

---

## 2. Allowed Responsibilities

Only these four concerns may exist inside Kernel:

| # | Responsibility | Module | One-sentence description |
|---|---------------|--------|--------------------------|
| 1 | **Skill Routing** | Adapter | Map intent + context to best-matching skill — deterministic, stateless, no execution |
| 2 | **Task Lifecycle** | TaskSystem | Manage task state machine: backlog → active → done, with step decomposition |
| 3 | **Execution Validation** | ExecutionLoop | Run verification checks against changed code, bounded retry (max 2 attempts) |
| 4 | **Event Ingestion** | EventBus (Phase 1) | Normalize external triggers into Kernel-internal events |

### Cross-module rules

- Adapter resolves but NEVER executes
- TaskSystem orchestrates but NEVER routes skills
- ExecutionLoop validates but NEVER creates tasks
- EventBus ingests but NEVER decides

---

## 3. Forbidden Responsibilities (Global Ban)

Any capability matching these categories is banned from Kernel.
It must live in a skill or an external system.

| Category | Examples | Where they belong |
|----------|----------|-------------------|
| **Agent Autonomy** | Self-directed planning, goal decomposition, autonomous iteration | Skill (external) |
| **Reasoning Engine** | Chain-of-thought, logical inference, decision trees | Claude / LLM |
| **Memory Cognition** | Belief state, knowledge graphs, episodic memory, context understanding | Skill (memory package) |
| **Long-chain Planning** | Multi-step autonomous workflows, autonomous decomposition | TaskSystem steps (human-defined) |
| **Prompt Orchestration** | Prompt templates, prompt optimization, system prompt management | Skill (external) |
| **Business Workflows** | CI/CD logic, deployment pipelines, approval chains | External system |
| **UI Logic** | Web dashboards, CLI formatting beyond raw output, interactive menus | External system |
| **SDK Ownership** | Anthropic SDK, OpenAI SDK, model-specific logic | Skill (claude-api) |
| **Self-modifying Logic** | Code that rewrites Kernel internals, dynamic capability patching | NEVER — this is a kill switch |
| **Probabilistic Routing** | Embedding similarity, semantic search, ML-based matching | NEVER |
| **Skill Execution** | Running skill code, invoking LLMs, calling APIs on behalf of skills | Skill runtime (external) |
| **Content Generation** | Creating text, code, images, audio | Skill / LLM |

---

## 4. Deterministic Requirements

### 4.1 Same Input → Same Output

`Adapter.resolve(CapabilityRequest)` must produce the same `CapabilityBinding` for the
same inputs, regardless of when or how many times it is called.

### 4.2 Forbidden Non-determinism

| Pattern | Status | Reason |
|---------|--------|--------|
| Module-level singleton caches (`_registry_cache`, `_PKG_KEYWORDS_CACHE`) | EXISTS — must be documented | Can cause different results after `reload_registry()` |
| Filesystem state affecting routing (`_check_installed`) | EXISTS — constrained | Installed status only adds +0.05 bonus; does not gate routing |
| Random / probabilistic selection | NOT present | All tie-breaking is alphabetical |
| Time-based decisions | NOT present | No timestamps affect routing |
| External API calls during routing | NOT present | All data is pre-loaded from disk |

### 4.3 Hard Fail Contract

When `Adapter.resolve()` cannot match a skill:

```
CapabilityBinding(skill_id="", confidence=0.0, alternatives=(), reason="No skill matched...")
```

- No second-pass routing inside Kernel
- No default/fallback skill substitution
- No probabilistic guessing
- Caller decides what to do with empty binding

### 4.4 NO_MATCH is a valid answer

"SystemKernel says NO_MATCH" is a correct and expected output.
It is not a failure. It is the system doing its job.

---

## 5. Complexity Budget Rules

### 5.1 New Capability Gate

Before ANY new capability enters Kernel, answer these 5 questions:

| # | Question | If NO → REJECTED |
|---|----------|-----------------|
| 1 | **Deletable?** Can this capability be removed without breaking Kernel? | ❌ |
| 2 | **Replaceable?** Can a different implementation be swapped in? | ❌ |
| 3 | **Disableable?** Can it be turned off at runtime? | ❌ |
| 4 | **Boundary-clean?** Does it stay within 1 of the 4 allowed responsibilities? | ❌ |
| 5 | **Non-LLM?** Can it work without calling an LLM? | ❌ (prefer non-LLM) |

### 5.2 Phase Budget

Each development phase introduces at most **1 new core module**.

| Phase | New Module | Cap |
|-------|-----------|-----|
| 0 | None (freeze only) | 0 |
| 1 | EventBus | 1 |
| 2 | None (harden existing) | 0 |
| 3 | Metrics | 1 |

Violating this rule is the #1 cause of framework death.

### 5.3 Kernel Size Invariant

```
Kernel code < Skill ecosystem code
```

At all times. If Kernel grows faster than skills, it is becoming a framework.
Currently: Kernel ~3500 lines, Skills ~80+ files — healthy ratio.

### 5.4 All new capability must be externalized

```
Pluggable → Removable → Replaceable → Disableable
```

Any capability that cannot satisfy all four is a Kernel boundary violation.

---

## 6. Boundary Enforcement

### 6.1 Automated Guards

| Tool | Checks |
|------|--------|
| `architecture_guard.py` | Banned imports, hidden decision points, sys.path hacks in function bodies |
| `drift_detector.py` | CLAUDE.md claims vs actual code reality |

### 6.2 Manual Review Gates

- No module may import another module's internals (only public API)
- No `sys.path.insert` inside function bodies
- No hardcoded skill metadata in routing code (must be in registry.json or manifest.json)
- No second entry points that shadow Adapter

### 6.3 Current Boundary Violations (tracked for Phase 2 resolution)

| ID | Severity | Violation | Location |
|----|----------|-----------|----------|
| BV-001 | HIGH | Hardcoded external skill metadata (167 lines) in routing engine | `capability_registry.py:_EXTERNAL_SKILL_METADATA` |
| BV-002 | HIGH | Hardcoded local skill capabilities (200+ lines) in routing engine | `capability_registry.py:_LOCAL_SKILL_CAPABILITIES` |
| BV-003 | MEDIUM | Module-level singleton registry cache breaks strict determinism | `routing_pipeline.py:_registry_cache` |
| BV-004 | MEDIUM | Module-level keyword cache | `package_router.py:_PKG_KEYWORDS_CACHE` |
| BV-005 | MEDIUM | Parallel classification system shadows Adapter routing | `classify.py` |
| BV-006 | MEDIUM | TaskManager does skill routing internally | `task_manager.py:suggest_skills_for_step()` |
| BV-007 | LOW | Runtime sys.path manipulation | `ExecutionLoop/loop.py:203` |
| BV-008 | LOW | Compatibility wrapper as second entry point | `suggestion_engine.py` |

Resolution target: Phase 2 (Kernel Hardening).

---

## 7. Version

- **Version:** v1.0
- **Status:** FROZEN
- **Adopted:** 2026-05-23 — Phase 0 Kernel Boundary Freeze
- **Supersedes:** Informal conventions in CLAUDE.md
- **Governed by:** SystemKernel/CLAUDE.md Section 5 (Extension Rules)
