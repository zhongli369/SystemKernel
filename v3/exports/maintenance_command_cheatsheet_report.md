# Maintenance Task 01 — Command Usage Cheatsheet

**Task ID:** MT-01  
**Date:** 2026-06-02  
**Type:** Documentation / UX (non-code, zero complexity impact)  
**Freeze Compliance:** SF-01–SF-07 all PASS (unchanged)

## Summary

Created `Docs/SYSTEMKERNEL_COMMANDS_CHEATSHEET.md` — a scenario-organized command reference for both humans and Claude Code agents interacting with SystemKernel v4.1.

## Motivation

The existing `v3/exports/v4_runbook.md` is a comprehensive safety/ops manual organized by subsystem. It's excellent for understanding boundaries but not ideal for the question: "I need to do X — which command?"

The cheatsheet complements the runbook by organizing commands by **intent** (health check, change validation, capability selection, etc.) rather than by architecture layer.

## What Was Produced

- `Docs/SYSTEMKERNEL_COMMANDS_CHEATSHEET.md` — 8 sections, 40+ commands, scenario map table

## What Was NOT Touched

- No CLI code changes
- No kernel modifications
- No registry updates
- No new capabilities
- No freeze invariant changes

## Placement

- `Docs/` — alongside project-level documentation (new directory under SystemKernel root)
- Separated from `v3/exports/` (which holds architecture/phase reports) to keep docs user-facing

## Follow-Up Candidates (Not Started)

- **MT-02**: Dead code / cohesion audit (audit-only, no cleanup)
- **MT-03**: CLI surface compression — verify all commands in cheatsheet have consistent help text
- **MT-04**: Docs drift audit — compare CLAUDE.md, runbook, and cheatsheet for stale references
