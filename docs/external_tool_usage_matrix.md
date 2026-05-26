# External Tool Usage Matrix

**Date:** 2026-05-26
**Phase:** 7A — External Tool Inspection

---

## Usage Matrix

| Tool | Current Status | Use Mode | Immediate Value | Allowed Next Step | Forbidden Action | Integration Risk | Priority |
|------|---------------|----------|-----------------|-------------------|------------------|-----------------|----------|
| **Repomix** | Cloned, not installed | direct_tool | HIGH — codebase packing for AI context | `npx repomix` manual test run | npm install -g repomix | LOW | P1 |
| **ccusage** | Cloned, not installed | direct_tool | MEDIUM — usage/cost observability | `bunx ccusage daily --json` manual test | pnpm install in cloned repo | MEDIUM | P2 |
| **Anthropic Skills** | Cloned, read-only | format_reference | HIGH — SKILL.md format reference | Study template and skill-creator conventions | Copy SKILL.md into kernel tree | NONE | P1 |

---

## Detailed Assessment

### Repomix

| Aspect | Detail |
|--------|--------|
| **CLI** | `npx repomix` or `repomix` (global) |
| **Output formats** | XML, Markdown, JSON, Plain text |
| **MCP** | Native `--mcp` flag + 3 Claude Code plugins |
| **Dependencies** | Node.js >= 22, npm packages (commander, globby, etc.) |
| **License** | MIT |
| **Config file** | `repomix.config.json` (JSON5) |
| **Security** | Built-in Secretlint, binary exclusion |
| **SystemKernel map** | Context optimizer → kernel could consume packed output |
| **Call pattern** | External process only; never import as module |
| **Why not integrate** | Node.js dependency would violate kernel purity (Python stdlib only) |
| **When to reconsider** | If kernel needed a native Python codebase packer (then write one, don't wrap this) |

### ccusage

| Aspect | Detail |
|--------|--------|
| **CLI** | `bunx ccusage` or `npx ccusage` |
| **Output formats** | Terminal table, JSON (`--json`) |
| **MCP** | Not exposed as MCP server (uses external MCP servers for dev) |
| **Dependencies** | Node.js + Rust, pnpm monorepo |
| **License** | MIT |
| **Config file** | `ccusage.example.json` (JSON schema validation) |
| **SystemKernel map** | Usage-cost data → kernel observability metrics |
| **Call pattern** | External process only; consume JSON output |
| **Why not integrate** | Rust+TypeScript hybrid, tightly coupled to Claude Code JSONL format |
| **When to reconsider** | If kernel added a usage-tracking metric type and needed a data source |

### Anthropic Skills

| Aspect | Detail |
|--------|--------|
| **Entry point** | `template/SKILL.md` — minimal template |
| **Format** | YAML frontmatter + Markdown body |
| **Spec** | https://agentskills.io/specification |
| **License** | Apache 2.0 (most), Proprietary (docx/pdf/pptx/xlsx) |
| **Dependencies** | None (Markdown + optional Python/JS scripts per skill) |
| **SystemKernel map** | SKILL.md conventions → kernel skill package format |
| **Usage pattern** | Reference only; never copy into kernel tree |
| **Why not integrate** | Different purpose (LLM instruction templates vs deterministic execution) |
| **When to reconsider** | If kernel added a skill-authoring or skill-packaging subsystem |

---

## Risk Definitions

| Level | Meaning |
|-------|---------|
| NONE | Format reference only — no runtime or code dependency |
| LOW | External process call — isolated, no shared state |
| MEDIUM | External process call with data format coupling |
| HIGH | Would require code import, shared dependency, or tight coupling |

---

## Priority Definitions

| Level | Meaning | Timeline |
|-------|---------|----------|
| P0 | Do now — blocks other work | Current phase |
| P1 | Do soon — high value, low risk | Next 1-2 phases |
| P2 | Do later — medium value or higher risk | Future phase |
| P3 | Monitor — not actionable yet | Ongoing |

---

## Decision Log

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | All 3 repos remain external | Keeps kernel Python-stdlib pure, avoids Node/Rust dependency | 2026-05-26 |
| 2 | Repomix as P1 direct_tool | Highest immediate value (context optimizer), lowest risk | 2026-05-26 |
| 3 | ccusage as P2 direct_tool | Valuable but coupled to Claude Code format; needs more study | 2026-05-26 |
| 4 | Anthropic Skills as P1 format_reference | SKILL.md conventions immediately applicable to kernel skill docs | 2026-05-26 |
| 5 | No npm/pnpm/pip install | Hard constraint — would modify external environment | 2026-05-26 |
| 6 | No MCP server wiring yet | Requires separate evaluation of MCP integration architecture | 2026-05-26 |

---

*External Tool Usage Matrix — Phase 7A — 2026-05-26*
