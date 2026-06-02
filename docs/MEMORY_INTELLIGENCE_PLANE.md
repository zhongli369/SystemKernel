# Memory Intelligence Plane

**Version:** 1.0.0 | **Phase:** 5 | **Date:** 2026-05-26
**Status:** Active | **Enforcement:** `v3/external/memory_intelligence.py`

---

## Purpose

The Memory Intelligence Plane defines contracts for external memory
intelligence providers (mem0, Graphiti, Letta) WITHOUT integrating them.

SystemKernel already has a deterministic Memory Runtime (`v3/memory/`)
that handles episodic storage, semantic indexing, recall, and compaction.
The Memory Intelligence Plane is an outer layer — it defines how future
external systems may suggest memory operations, but those suggestions are
always EVIDENCE, never TRUTH, and never direct mutations.

---

## Deterministic Memory Runtime vs. Memory Intelligence Plane

| Aspect | Memory Runtime | Memory Intelligence Plane |
|--------|---------------|--------------------------|
| Location | `v3/memory/` | `v3/external/` |
| Deterministic | Yes | Provider-dependent |
| LLM-free | Yes | Provider-dependent |
| External services | Never | Provider-dependent |
| Source of truth | Projection from events | Evidence only |
| Mutates kernel memory | Yes (projection) | No (suggestions only) |
| Removable | Yes | Always |

The runtime is the trusted deterministic core. The intelligence plane
is an untrusted evidence layer on top.

---

## Why mem0 / Graphiti / Letta Are External Providers

All three require capabilities that the kernel forbids:

| Provider | LLM | Vector DB | Graph DB | External Service |
|----------|-----|-----------|----------|-----------------|
| mem0 | Yes | Yes | No | Yes |
| Graphiti | Yes | No | Yes | Yes |
| Letta | Yes | No | No | Yes |
| **Deterministic Mock** | **No** | **No** | **No** | **No** |

Under the default policy, all real providers are blocked. Only the
deterministic mock provider (no LLM, no DB, no external service) is
allowed for testing the plane contracts.

---

## Why Signals Are Suggestions / Evidence Only

Memory signals (`add`, `update`, `delete`, `noop`, `temporal_fact`,
`entity_link`, `retrieval_hint`) are SUGGESTIONS from an external
provider. They do NOT:

- Mutate kernel memory directly
- Override the deterministic runtime
- Become source of truth
- Execute automatically

Delete and update signals are explicitly marked as suggestion-only
(`SUGGESTION_ONLY_SIGNAL_TYPES`). All signals carry `truth_source=False`.

---

## Default Policy

The `default_memory_intelligence_policy()` is maximally conservative:

| Rule | Value |
|------|-------|
| Allow LLM providers | False |
| Allow vector DB providers | False |
| Allow graph DB providers | False |
| Allow external services | False |
| Max signals | 100 |
| Require provenance | True |

This means only `deterministic_mock_memory` passes by default. To trial
a real provider, each flag must be explicitly enabled with documented
reasoning.

---

## How Future Provider Trials Can Be Approved

1. Define a provider profile (Phase 5 contract)
2. Default policy blocks it
3. Create a trial-specific policy that selectively enables flags:
   ```python
   trial_policy = MemoryIntelligencePolicy(
       allow_llm_providers=True,          # Specific justification
       allow_external_services=True,       # Specific justification
       max_signals=10,                     # Limited blast radius
   )
   ```
4. Validate provider against trial policy
5. Run trial in `inspect_only` or `dry_run` mode
6. Map results to evidence (never truth)
7. Human reviews signals before any memory operations

---

## How Memory Intelligence Evidence May Evolve Memory

The pipeline for human-reviewed memory evolution:

1. External provider produces `MemorySignals` (evidence)
2. Signals mapped to `EvidenceRecords` in an `EvidenceBundle`
3. Human reviews the evidence and individual signals
4. Human issues explicit `MemoryWriteRequest` to the deterministic runtime
5. Runtime projects memory (deterministic, verifiable)

The intelligence plane never writes directly. The human is the gate.

---

## CLI Usage

```bash
# List all provider profiles and policy status
python v3/cli/systemkernel.py memory-intel profiles

# Generate deterministic mock result
python v3/cli/systemkernel.py memory-intel mock --signals 3

# Build evidence bundle from mock result
python v3/cli/systemkernel.py memory-intel evidence
```

---

## Anti-Overengineering

- No duplication of v3/memory runtime
- No second memory store
- No vector search implementation
- No graph DB implementation
- No LLM extraction
- No external service calls
- Phase 1 contract, Phase 3 evidence model reused
- `truth_source` always `False`

---

*SystemKernel v4.0 Phase 5 — Memory Intelligence Plane*
