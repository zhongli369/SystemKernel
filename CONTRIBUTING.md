# Contributing to SystemKernel

SystemKernel is a frozen deterministic kernel. Its architecture is governed by strict contract rules — contributions must respect those boundaries.

## Core Principle

> **SystemKernel provides routing, orchestration, and verification. It does not provide agent logic, probabilistic decision-making, or execution frameworks.**

All contributions must reinforce this principle, not dilute it.

## What CAN Be Contributed

- **New skills** added to the SkillSystem registry
- **New `INTENT_HINTS` entries** in `adapter.py` (additive only — never remove or rename existing entries)
- **New named verification checks** in `ExecutionLoop.loop._NAMED_CHECKS`
- **New task types** in TaskSystem (must route through Adapter for skill selection)
- **Documentation improvements** (README, examples, inline docstrings that don't change API semantics)
- **Bug fixes** in SkillSystem internal matching logic (as long as public contracts are preserved)

## What MUST NOT Be Contributed

### New Routing Systems
- No alternative routing entrypoints
- No new intent-to-skill mapping layers
- No "try Adapter first, then try my own logic" patterns
- No shadow skill resolution systems

### Duplicate Intent Maps
- No copies of `INTENT_HINTS` anywhere outside `adapter.py`
- No `if intent == "X": skill = "Y"` decision chains
- No `match intent:` patterns for skill selection

### Execution Bypasses
- No custom execution loops that bypass `ExecutionLoop.run()`
- No parallel verification systems
- No execution frameworks that embed routing logic

### Internal Access
- No direct imports from SkillSystem internals (`routing_pipeline`, `capability_registry`, `alias_resolver`, `tag_matcher`, `routing_engine`, `package_router`, `external_skill_adapter`)
- No direct access to `registry.json`
- No `sys.path.insert` / `sys.path.append` inside function bodies
- No `importlib` for module discovery or routing
- No `subprocess.run` / `subprocess.Popen` for skill routing

## Pre-Commit Checklist

Before submitting a change, verify:

1. **Architecture guard passes:**
   ```bash
   python architecture_guard.py
   ```
   Must show: `FREEZE STATUS: PASSED` with stability score 100/100.

2. **No CRITICAL violations.** These block merges. No exceptions.

3. **MEDIUM violations require written justification** in the PR description explaining why the violation is necessary and why no alternative exists within the contract.

4. **Public API signatures are unchanged.** `CapabilityRequest`, `CapabilityBinding`, `ExecutionRequest`, `ExecutionResult` field names and types are frozen.

5. **No new import paths have been created** that bypass Adapter.

## Freeze Override Process

If a change *requires* modifying a frozen contract (structural changes, new subsystems, API field changes):

1. Document the justification — why the current contract cannot accommodate the change
2. Update `architecture_guard.py` to reflect the new contract boundaries
3. Re-validate all existing tests and guard checks
4. Bump the CLAUDE.md protocol version
5. Obtain explicit approval — frozen contracts are not changed lightly

Freeze overrides are rare. Most needs can be met through additive changes within the existing contract.

## PR Guidelines

- Keep changes minimal and focused
- One concern per PR (new skill, bug fix, doc update — not all three)
- Link to the specific contract rule being respected or the freeze override being exercised
- PRs that introduce routing bypasses, duplicate logic, or shadow systems will be rejected

## Questions?

If you're unsure whether a change is allowed, ask before coding. The contract rules in `CLAUDE.md` and the checks in `architecture_guard.py` are authoritative.
