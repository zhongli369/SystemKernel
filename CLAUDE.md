# Claude Code / Codex Agent Guidance — SystemKernel

Instructions for any AI agent (Claude Code, Codex, or future) working in
this repository. These rules protect kernel purity, event sourcing
integrity, and the complexity budget.

---

## 1. Kernel Purity (Non-Negotiable)

- **Never modify `v3/kernel/` unless explicitly asked.** The kernel is the
  deterministic core. Changes to it require justification, re-validation,
  and a version bump.
- **Preserve kernel purity at 100/100.** The kernel has zero LLM calls,
  zero probabilistic routing, zero shadow logic. Do not introduce any.
- **Do not integrate external tools directly into the kernel.** External
  tools (mem0, Graphiti, OpenHands, AutoGen, Continue, ECC) belong in the
  pluggable intelligence plane, never in `v3/kernel/`.
- **Do not add LLM imports, calls, or APIs to any kernel subsystem.**
  Adapter, TaskSystem, EventBus, ExecutionLoop, and Observability must
  remain LLM-free.

## 2. Event Sourcing

- **Treat EventStore as the source of truth.** Every decision, route,
  execution, and validation is an immutable event. The event log is truth;
  everything else is derived.
- **Treat external outputs as evidence only.** Agent outputs, LLM
  responses, and external tool results are evidence recorded in the event
  log. They never directly mutate kernel state.
- **Do not modify or delete event records.** Events are append-only.

## 3. Safety

- **Do not run network/install/clone commands without explicit approval.**
  This includes `pip install`, `npm install`, `git clone`, `curl`, API
  calls to external services, and any command that reaches the network.
- **Always run safety checks before commit:**
  ```bash
  python scripts/verify_v4_baseline.py
  python v3/tests/test_kernel_invariants.py
  ```
- **Use the Complexity Gate.** Before adding any capability, ask: does
  ability +10% cost complexity +300%? If yes, find a simpler approach.
- **Do not stage unrelated files.** Only stage what was explicitly
  requested. Check `git diff --cached --name-only` before committing.

## 4. Protected Paths

These paths must not be modified without explicit instruction:

| Path | Reason |
|------|--------|
| `v3/kernel/` | Frozen deterministic core |
| `v3/memory/` | Memory intelligence plane (removable) |
| `v3/release/` | Release artifacts |
| `scripts/verify_v3_baseline.py` | v3 baseline verification |
| `scripts/verify_v4_baseline.py` | v4 baseline verification |

## 5. Dirty / Unrelated Files

- **Leave dirty and untracked files alone unless explicitly asked to touch
  them.** The repository may contain in-progress work, experimental
  checkpoints, and generated reports. Do not clean, stage, or modify these
  files without explicit instruction.
- **Do not run `git reset`, `git clean`, or `git add -A`.** Stage specific
  files only.

## 6. ECC Rule (v4.1)

- **ECC is execution-only infrastructure.** ECC CANNOT influence kernel decisions.
  ECC outputs are execution traces only, never decision inputs.
- **ECC must NOT be exposed via SystemKernel API.** Not in `list_capabilities`,
  not in `query_external_signals`, not in any public export.
- **ECC (everything-claude-code) is an external capability provider, not
  an internal dependency.** SystemKernel may model ECC interfaces in the
  intelligence plane, but ECC is never required for kernel operation.
- **SystemKernel should use/evaluate ECC, not become an ECC clone.** Do
  not port ECC internals into the kernel.

## 7. Architecture Enforcement

```bash
# Run before any commit touching kernel or intelligence plane
python architecture_guard.py
python architecture_guard.py --json

# Stability freeze verification (v4.1)
python v3/release/stability_freeze.py --verify
python v3/cli/systemkernel.py v4 freeze verify
```

A passing architecture guard means zero CRITICAL violations and stability score ≥ 96/100.
A passing stability freeze means all 7 SF invariants pass:
  SF-01 API Surface Freeze, SF-02 Capability Freeze, SF-03 Signal Contract Freeze,
  SF-04 Injection Pipeline Freeze, SF-05 Internal Protection, SF-06 ECC Rule,
  SF-07 Complexity Guard.

## 8. Git

- **Never force push.** Ever.
- **Never move or recreate existing tags.** Tags are immutable markers.
- **Stage only the files requested.** Verify with `git diff --cached
  --name-only` before committing.
- **Do not amend published commits.** Create new commits.

---

*Kernel Constitution v2. Governance v4.1 Stable. Stability Freeze active.*
