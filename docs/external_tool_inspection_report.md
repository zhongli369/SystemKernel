# External Tool Pool — Inspection Report

**Date:** 2026-05-26
**Phase:** 7A — External Tool Inspection
**Clone Report:** `docs/external_tools_clone_report.md`

---

## Executive Summary

Three external repositories were inspected in read-only mode. All three are viable
for their intended use modes and should remain external. No integration into the
SystemKernel source tree is recommended at this time.

| Repo | Use Mode | Integration Risk | Immediate Value | Recommend |
|------|----------|-----------------|-----------------|-----------|
| Repomix | direct_tool | LOW | HIGH | Call externally via `npx repomix` |
| ccusage | direct_tool | MEDIUM | MEDIUM | Call externally via `bunx ccusage` |
| Anthropic Skills | format_reference | NONE | HIGH | Study SKILL.md conventions only |

---

## 1. Repomix

### 1.1 Identity

| Field | Value |
|-------|-------|
| Package | `repomix` v1.14.0 |
| Author | Kazuki Yamada (yamadashy) |
| License | MIT |
| Language | TypeScript (Node.js >= 22) |
| CLI entry | `bin/repomix.cjs` → `lib/cli/cliRun.js` |
| Config | `repomix.config.json` (JSON5, also .ts/.js) |
| Repository | https://github.com/yamadashy/repomix |

### 1.2 Capabilities

- **Codebase packing**: Single command packs an entire repo into one AI-friendly file
- **Output formats**: XML (default), Markdown, JSON, Plain text
- **Token counting**: Per-file and aggregate, configurable encoding (o200k_base, cl100k_base)
- **Code compression**: Tree-sitter based (`--compress`), ~70% token reduction
- **Security**: Built-in Secretlint scanning, binary file exclusion
- **Git integration**: Auto-respects .gitignore, can include git diffs/logs
- **Remote repos**: `--remote user/repo` to clone and pack without manual checkout
- **Stdin piping**: `--stdin` for flexible file list input
- **Split output**: `--split-output 1mb` for large codebases
- **Agent Skills generation**: `--skill-generate` produces Claude Agent Skills format
- **Docker**: `ghcr.io/yamadashy/repomix` container available

### 1.3 MCP Support

Full MCP server via `repomix --mcp`. Three Claude Code plugins:
- `repomix-mcp` — foundation MCP server plugin
- `repomix-commands` — slash commands (`/repomix-commands:pack-local`, `/repomix-commands:pack-remote`)
- `repomix-explorer` — AI-powered repository analysis agent

**7 MCP tools**: `pack_codebase`, `attach_packed_output`, `pack_remote_repository`,
`read_repomix_output`, `grep_repomix_output`, `file_system_read_file`,
`file_system_read_directory`.

### 1.4 Integration Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| External CLI call | SAFE | `npx repomix` needs no install, no config changes |
| MCP integration | SAFE | Already designed as MCP server |
| Direct integration | NOT RECOMMENDED | Node.js dependency, adds complexity to Python kernel |
| Import as library | NOT RECOMMENDED | TypeScript ESM, not compatible with Python kernel |
| Security risk | LOW | Secretlint built in; runs locally only |

### 1.5 SystemKernel Value

- **Context optimization**: Could serve as a preprocessor, packing code for kernel analysis
- **Observability integration**: Output token counts could feed into kernel metrics
- **Golden path**: Already generates output formats that kernel reports could consume
- **Skill generation**: `--skill-generate` produces SKILL.md format that aligns with Anthropic Skills conventions

### 1.6 Safe Next Actions

- Run `npx repomix` manually in a test directory to observe output
- Review `repomix-output.xml` format for potential kernel report consumption
- Document the CLI options most relevant to SystemKernel workflows
- Evaluate token-count integration with kernel observability metrics

### 1.7 Forbidden Actions

- Do NOT add `repomix` as a Python dependency
- Do NOT import repomix internals into kernel
- Do NOT automate repomix execution without manual audit
- Do NOT run `npm install` inside the cloned repo directory

---

## 2. ccusage

### 2.1 Identity

| Field | Value |
|-------|-------|
| Package | `ccusage` v20.0.4 (monorepo) |
| Author | ryoppippi |
| License | MIT |
| Language | TypeScript + Rust (hybrid, pnpm workspaces) |
| CLI entry | `apps/ccusage/src/cli.ts` |
| Config | `ccusage.example.json` (JSON schema, IDE autocomplete) |
| Repository | https://github.com/ryoppippi/ccusage |

### 2.2 Capabilities

- **15 source agents**: Claude Code, Codex, OpenCode, Amp, Droid, Codebuff,
  Hermes Agent, pi-agent, Goose, OpenClaw, Kilo, Kimi, Qwen, GitHub Copilot CLI,
  Gemini CLI
- **Report types**: Daily, Weekly, Monthly, Session, 5-hour Blocks, Statusline
- **Output formats**: Colorized terminal table, JSON (`--json` flag)
- **Cost tracking**: USD costs per day/month/session
- **Model breakdown**: Per-model cost with `--breakdown` flag
- **Cache tokens**: Separate tracking for cache creation and cache read tokens
- **Filtering**: Date range (`--since`, `--until`), project (`--project`),
  instances (`--instances`), timezone (`--timezone`)
- **Offline mode**: `--offline` using pre-cached pricing data
- **Compact mode**: `--compact` for narrow terminals and screenshots

### 2.3 MCP

The `.mcp.json` at repo root configures external MCP servers (context7, grep)
used during development — these are NOT ccusage's own MCP server. ccusage does
not appear to expose its own MCP server interface.

### 2.4 Data Source Coupling

ccusage reads Claude Code JSONL data from local filesystem paths. The specific
file format assumptions are:
- Claude Code conversation JSONL files in project directories
- Session metadata files for session grouping
- Pricing data from LiteLLM (cached/shipped at build time)

**Risk**: Tight coupling to Claude Code's internal JSONL format. Format changes
in Claude Code could break ccusage until upstream updates.

### 2.5 Integration Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| External CLI call | SAFE | `bunx ccusage` needs no install |
| JSON output integration | SAFE | `--json` flag produces structured output |
| Direct integration | NOT RECOMMENDED | Rust+TypeScript hybrid, not Python-compatible |
| Data format risk | MEDIUM | Coupled to Claude Code JSONL format |
| Security risk | LOW | Reads local files only, no network in `--offline` mode |

### 2.6 SystemKernel Value

- **Usage-cost observability**: JSON output could be consumed by kernel
  observability reports as an external data source
- **Metrics mapping**: ccusage metrics (token usage, cost, model breakdown)
  could map to kernel metric types (execution_latency_ms, skill_hit, etc.)
- **Report augmentation**: Monthly/daily cost reports could complement kernel
  complexity budget and validation reports
- **Statusline**: Compact statusline output could integrate with kernel CLI
  status command

### 2.7 Safe Next Actions

- Run `bunx ccusage daily --json` manually to inspect JSON output format
- Compare JSON schema to kernel metric types for potential mapping
- Document the data flow: ccusage JSON → kernel metrics ingestion
- Evaluate if ccusage report data complements kernel observability

### 2.8 Forbidden Actions

- Do NOT add ccusage as a Python dependency
- Do NOT import ccusage internals into kernel
- Do NOT hardcode ccusage JSON schema in kernel modules
- Do NOT run `pnpm install` inside the cloned repo directory
- Do NOT run automated ccusage against kernel traces without manual audit

---

## 3. Anthropic Skills

### 3.1 Identity

| Field | Value |
|-------|-------|
| Repository | `anthropic-skills` |
| Owner | Anthropic |
| License | Apache 2.0 (most skills); Proprietary/source-available (docx, pdf, pptx, xlsx) |
| Language | Markdown + scripts (Python, JavaScript) |
| Structure | `skills/<name>/SKILL.md` per skill |
| Skill count | 17 |
| Spec | `spec/agent-skills-spec.md` (redirects to agentskills.io) |

### 3.2 Skill Inventory

| Skill | Category | Has Scripts | Has References |
|-------|----------|-------------|----------------|
| algorithmic-art | Creative & Design | YES | NO |
| brand-guidelines | Creative & Design | NO | NO |
| canvas-design | Creative & Design | YES | NO |
| claude-api | Development & Technical | NO | NO |
| doc-coauthoring | Development & Technical | NO | NO |
| docx | Document Skills | YES | NO |
| frontend-design | Creative & Design | NO | NO |
| internal-comms | Enterprise & Communication | NO | NO |
| mcp-builder | Development & Technical | YES | YES |
| pdf | Document Skills | YES | NO |
| pptx | Document Skills | YES | NO |
| skill-creator | Development & Technical | YES | YES |
| slack-gif-creator | Creative & Design | YES | NO |
| theme-factory | Creative & Design | NO | NO |
| webapp-testing | Development & Technical | YES | NO |
| web-artifacts-builder | Development & Technical | YES | NO |
| xlsx | Document Skills | YES | NO |

### 3.3 SKILL.md Conventions

#### Frontmatter (YAML)
```yaml
---
name: skill-name          # required, lowercase, hyphens
description: "..."        # required, primary trigger mechanism
license: ...             # optional
compatibility: ...       # optional, rarely needed
---
```

#### Body Structure
- Markdown instructions under 500 lines (progressive disclosure level 2)
- Imperative form preferred
- Examples with Input/Output pairs
- Guidelines as bullet lists
- "Why" explanations over heavy-handed "MUST" statements

#### Directory Layout
```
skill-name/
├── SKILL.md (required)
├── scripts/     - Executable code for deterministic tasks
├── references/  - Docs loaded into context as needed
└── assets/      - Files used in output (templates, icons, fonts)
```

#### Progressive Disclosure (3 levels)
1. **Metadata** — name + description, always in context (~100 words)
2. **SKILL.md body** — in context when skill triggers (<500 lines ideal)
3. **Bundled resources** — as needed (unlimited)

### 3.4 Differences from SystemKernel

| Dimension | Anthropic Skills | SystemKernel |
|-----------|-----------------|--------------|
| Purpose | Instruction templates for Claude | Event-sourced execution kernel |
| Content | Markdown with YAML frontmatter | Python modules, frozen dataclasses |
| Triggering | Claude reads description and decides | Adapter.resolve() deterministic routing |
| Persistence | File-based (SKILL.md on disk) | Memory system (JSONL checkpoints, traces, metrics) |
| Execution | Claude follows instructions | ExecutionLoop.run() deterministic pipeline |
| Nesting | No nested skills | TaskSystem with steps and substeps |
| Observability | None | Full tracing, metrics, replay |
| Determinism | No guarantee (LLM interpretation) | Same input → same output guaranteed |

### 3.5 Reusable Concepts

| Concept | Applicability | Notes |
|---------|--------------|-------|
| YAML frontmatter (name + description) | HIGH | Directly applicable to SystemKernel skill packages |
| Progressive disclosure pattern | MEDIUM | Kernel already has this via adapter → task → execution |
| scripts/references/assets layout | HIGH | Can adopt for `SkillsManagementSystem/packages/<name>/` |
| Description as primary trigger | MEDIUM | Kernel uses `INTENT_HINTS` dict, could adopt description-based matching |
| 500-line SKILL.md soft limit | MEDIUM | Could apply to skill package README/spec files |
| Skill packaging (.skill file) | LOW | Kernel skills are Python packages, not .skill files |

### 3.6 Safe Next Actions

- Study `template/SKILL.md` as canonical starting format
- Compare `skill-creator/SKILL.md` evaluation loop with kernel golden path
- Review `mcp-builder/SKILL.md` for MCP server patterns (kernel may add MCP later)
- Document SKILL.md conventions in kernel developer docs
- Consider adopting YAML frontmatter for kernel skill package manifests

### 3.7 Forbidden Actions

- Do NOT copy SKILL.md files into SystemKernel tree
- Do NOT install Anthropic Skills as Claude Code skills (separate decision)
- Do NOT use proprietary skills (docx, pdf, pptx, xlsx) as reference for
  kernel code — they are source-available, not open source
- Do NOT integrate Anthropic Skills runtime into kernel

---

## Safety Confirmation

| Check | Status |
|-------|--------|
| v3 runtime files modified | NO |
| kernel modules modified | NO |
| release modules modified | NO |
| quality modules modified | NO |
| intake modules modified | NO |
| CLI modules modified | NO |
| memory system modified | NO |
| cloned repos modified | NO |
| dependency install run | NO |
| external code executed | NO |
| git pull executed | NO |
| git push executed | NO |
| destructive commands run | NO |
| more repos cloned | NO |

---

*External Tool Pool Inspection Report — Phase 7A — 2026-05-26*
