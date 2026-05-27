# ECC Positioning Report — Phase 13A

**Repo:** [ECC / everything-claude-code](https://github.com/affaan-m/everything-claude-code)
**Recommended role:** `external_harness_reference_only`
**Clone now:** MAYBE
**Integrate now:** NO
**Complexity risk:** MEDIUM

## Differentiation Strategy

ECC = harness enhancement kit (skills, tools, UX, workflows). SystemKernel = deterministic governance/runtime/evidence kernel. ECC enhances HOW developers use AI tools. SystemKernel governs WHAT gets executed and verifies it happened. ECC is a toolbelt; SystemKernel is a kernel. They are complementary, not competing. SystemKernel may use ECC as an external capability provider in future, but must never embed ECC logic in the kernel boundary.

## Capability Mapping

| ECC Area | SystemKernel Plane | Use Mode | Reuse Strategy | Risk |
|----------|-------------------|----------|---------------|------|
| ECC CLAUDE.md / project initialization | Context Plane | `reference` | reference CLAUDE.md generation patterns | low |
| ECC agent / subagent system | Agent Worker Plane | `reject` | do not adopt; SystemKernel agent worker design is skill-driven, not task-driven | high |
| ECC cross-harness abstraction (Codex/Cursor/etc.) | Capability Registry | `reference` | architecture reference for multi-harness patterns | low |
| ECC doctor / repair | Productization + Ops | `learn` | learn UX patterns, do not copy implementation | low |
| ECC memory optimization | Memory Intelligence Plane | `learn` | compare compaction/recall patterns, do not copy | low |
| ECC plugin / install system | External Registry + Skill Management | `reference` | source reference for package management patterns | low |
| ECC security scanning | Evaluation Harness | `external_provider` | possible future evidence provider for security eval | medium |
| ECC skills / skill system | Skill Evolution Plane | `reference` | learn taxonomy, compare metadata, do not copy | low |
| ECC tool system | External Adapters (disabled) | `reject` | do not adopt; SystemKernel has its own external adapter model | high |
| ECC workflows / instincts | Orchestration Policy | `reference` | reference for policy pattern design | low |

## Reusable Patterns

- skill taxonomy structure as registry reference
- doctor/self-repair UX patterns for ops improvements
- cross-harness abstraction patterns for future multi-IDE support
- memory compaction/indexing patterns as design reference
- workflow/instinct model as orchestration policy UX reference
- plugin/install system as package management reference

## Forbidden Patterns

- **FORBIDDEN:** install ECC — no install, no execution, no dependency
- **FORBIDDEN:** run ECC — no execution of ECC commands or workflows
- **FORBIDDEN:** import ECC — no Python import of ECC modules
- **FORBIDDEN:** modify kernel — no kernel changes based on ECC
- **FORBIDDEN:** overwrite CLAUDE.md — SystemKernel CLAUDE.md is manually governed
- **FORBIDDEN:** copy ECC wholesale — reference patterns, never copy code
- **FORBIDDEN:** turn SystemKernel into ECC clone — must remain deterministic kernel
- **FORBIDDEN:** add ECC to kernel imports — ECC is external, never in kernel boundary
- **FORBIDDEN:** expand CLI for ECC — no new CLI surface for ECC operations
- **FORBIDDEN:** ECC-driven agent dispatch — agent routing remains deterministic

## Overlap with SystemKernel

- skill management and taxonomy
- project initialization / CLAUDE.md generation
- memory optimization and compaction
- workflow / instinct / policy patterns
- external tool wrapping
- security / quality scanning
- cross-harness / multi-IDE abstraction

## Decision Log

- **Phase 13A Decision:** ECC intake complete. No integration, no clone, no adapter.
- **Next real action:** Manual review of ECC repo (read-only) if user grants clone permission.
- **Future trial phase:** Requires explicit user authorization, separate phase gate.