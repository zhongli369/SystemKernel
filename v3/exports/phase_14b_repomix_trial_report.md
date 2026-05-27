# Phase 14B — Repomix Controlled Trial Report

**Date:** 2026-05-27 | **Status:** COMPLETE

---

## Execution Path

| Field | Value |
|-------|-------|
| Command | `context-pack generate v3/intake --output external_trials/repomix/phase_14b_intake_context.md --allow-execute` |
| Adapter used | `repomix_context_pack` (v3/external/context_pack.py) |
| Raw npx used | YES (via adapter with --allow-execute) |

## Target & Output

| Field | Value |
|-------|-------|
| Target | `v3/intake` (6 files) |
| Output path | `external_trials/repomix/phase_14b_intake_context.md` |
| Size | 99,500 bytes |
| Lines | 2,547 |
| Token estimate | 22,966 |
| Included files | `__init__.py`, `clone_plan.py`, `repo_intake.py`, `repo_profiles.py`, `rules.py`, `tool_registry.py` |

## Budget

| Field | Value |
|-------|-------|
| Budget status | **pass** |
| Sensitive hits | 0 |
| Target is repo root | NO |

## Evidence

| Field | Value |
|-------|-------|
| Evidence bundle hash | `adc62ff7dd494d16` |
| Evidence records | 2 |
| Truth source | **False** |
| Evidence path | `v3/exports/phase_14b_repomix_evidence.json` |

## Safety

| Field | Value |
|-------|-------|
| External execution occurred | YES (npx repomix, via adapter --allow-execute) |
| Network used | YES (npx fetches repomix@latest) |
| Install occurred | NO (ephemeral npx, no permanent install) |
| Kernel modified | NO |
| Memory modified | NO |
| Repomix repo modified | NO (npx fetches transiently) |
| Tags moved | NO |
| Truth source claimed | NO (evidence truth_source=False) |

## Usefulness Verdict

**USEFUL** — The trial demonstrates that:
1. Context Engineering Plane adapter works end-to-end (plan → budget → execute → inspect → evidence)
2. Explicit --allow-execute flag works correctly
3. Budget policy enforcement works (pass for 28K tokens on 6 files)
4. Evidence model correctly marks truth_source=False
5. Output is confined to external_trials/repomix/
6. Kernel and memory are untouched

## Complexity Impact

**LOW** — Existing adapter. No new code. No new dependencies. No new CLI surface.
The trial confirms the adapter path works without adding complexity.
