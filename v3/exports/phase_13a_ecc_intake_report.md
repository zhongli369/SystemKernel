# Phase 13A — ECC Intake + Positioning Analysis

**Date:** 2026-05-27
**Status:** COMPLETE

## Summary

- Repo: [ECC / everything-claude-code](https://github.com/affaan-m/everything-claude-code)
- Role: external_harness_reference_only
- Clone now: MAYBE
- Integrate now: NO
- Mappings: 10 capability areas mapped
- Use modes: learn/reference/external_provider/reject

## Key Decisions

1. **ECC is an external reference, not a dependency.**
2. **No ECC installation, execution, or import.**
3. **SystemKernel must never become an ECC clone.**
4. **Future ECC usage would go through the pluggable intelligence plane.**
5. **ECC security scanning is the only candidate for future external_provider use.**

## Differentiation

ECC = harness enhancement kit (skills, tools, UX, workflows). SystemKernel = deterministic governance/runtime/evidence kernel. ECC enhances HOW developers use AI tools. SystemKernel governs WHAT gets executed and verifies it happened. ECC is a toolbelt; SystemKernel is a kernel. They are complementary, not competing. SystemKernel may use ECC as an external capability provider in future, but must never embed ECC logic in the kernel boundary.

## Complexity Gate

- Current risk: **MEDIUM**
- Phase 13C simplification audit risk was also MEDIUM.
- Adding ECC positioning (no code, no adapter) does not increase risk.
- Full ECC integration would push risk to HIGH. Rejected.

## Recommendation

**Proceed to simplification pass (Phase 13D) before any real provider trial.**
proceed_to_real_provider_trial: NO (not until complexity risk is LOW)
proceed_to_simplification_pass: YES (13D CLI Surface Compression recommended)
stop: NO

## Next Phase

Phase 13D — CLI Surface Compression (systemkernel.py 3076 LOC / 57 subcommands).