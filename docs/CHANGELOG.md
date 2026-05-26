# Changelog

All notable changes to SystemKernel will be documented in this file.

---

## [3.0.0] — 2026-05-26 — "Deterministic Kernel"

### Phase 4: Runtime / Observability / Memory

- Deterministic event-sourced execution engine with fixed pipeline
- Checkpoint/restore with crash recovery and replay
- Time-travel debugging (rewind, fork, diff)
- Episodic memory store (append-only JSONL)
- Semantic index (lexical, no embeddings)
- Memory compaction with deterministic dedup
- Truth-linked recall with provenance
- Runtime observability graph, metrics, and telemetry
- **Memory fully removable** — kernel behavior unchanged without it
- Kernel purity score: 100/100

### Phase 5: Productization + Governance

- **5A:** Complexity budget gate (ACCEPT/REVIEW/REJECT)
- **5B:** Developer CLI (12 commands: status, quality, memory, reports, doctor, intake)
- **5C:** Golden path end-to-end demonstration (13 deterministic events)
- **5D:** Repo intake pipeline (14 profiles, 9 rules, 5 decision types)
- **5E:** External tool registry + GitHub clone plan
- **5F:** Release freeze — validation matrix (40 checks), inventory, release notes

### Phase 6: Packaging + Archive

- **6A:** Baseline packaging — package manifest (160 entries), operational handoff, verification script (35 checks)
- **6B:** Baseline archive + tag prep — tag metadata, archive manifest, changelog, pre-tag verification

### Safety Invariants

| # | Invariant | Status |
|---|-----------|--------|
| 1 | Single-loop execution (no nested loops) | ENFORCED |
| 2 | Memory does not interfere with execution | ENFORCED |
| 3 | Tool adapters are LLM-free | ENFORCED |
| 4 | Pipeline stages are immutable (fixed order) | ENFORCED |
| 5 | Memory is side-effect only (projection) | ENFORCED |
| 6 | Observability is read-only (writes, never decides) | ENFORCED |

### By the Numbers

| Metric | Value |
|--------|-------|
| Kernel purity | 100/100 |
| Memory removable | YES |
| Complexity gate | REVIEW |
| Python modules | 50+ |
| Test functions | 255+ selected |
| CLI commands | 12 |
| External tools evaluated | 14 |
| Validation checks | 40 |
| System invariants | 6 |
| Package manifest entries | 160 |
| Verification checks | 35 |

### Known Limitations

1. Single-machine only — no distributed execution
2. No real-time streaming — execution is batch-oriented
3. Memory is lexical only — semantic index uses tokenization, not embeddings
4. 14 repo profiles — intake pipeline covers 14 known repos
5. No MCP server — CLI is the primary interface
6. No web UI — stdout text output only
7. Windows paths — default paths use `F:/Claude/` conventions
8. No incremental adoption path — requires full SystemKernel runtime

### Forbidden Integrations

The following MUST NOT be integrated into the SystemKernel source tree:

- **LLM SDKs:** openai, anthropic, langchain, llamaindex, transformers
- **Vector databases:** chromadb, qdrant, pinecone, weaviate, milvus
- **Agent frameworks:** crewai, autogen, langgraph
- **External memory tools:** mem0, graphiti (adapters exist in `v3/integrations/` but are NOT linked into kernel)
- **Network libraries:** requests, httpx, urllib3, aiohttp
- **ML frameworks:** torch, tensorflow, sklearn, scipy

External tools are evaluated through the intake pipeline and clone plan
(`v3/exports/github_clone_plan.md`) but are NEVER integrated into the
kernel boundary.

### Upgrade Policy

SystemKernel v3.0 is a **baseline release**. Future versions:

- Must not decrease kernel purity below 100
- Must not make memory non-removable
- Must not introduce LLM imports into kernel/
- Must not add new truth sources
- Must pass complexity gate (not REJECT)
- Must pass all existing tests (regression)

Breaking changes require a new major version (v4.0).

---

## Version History

| Version | Date | Codename | Summary |
|---------|------|----------|---------|
| 3.0.0 | 2026-05-26 | Deterministic Kernel | Event-sourced kernel + memory + observability + packaging |
| 2.0 | 2026-05-23 | — | EventBus + Kernel Hardening + Observability |
| 1.0 | — | — | Deterministic AI routing + execution kernel |
