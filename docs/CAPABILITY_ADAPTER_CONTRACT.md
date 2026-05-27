# Capability Adapter Contract

**Version:** 1.0.0 | **Phase:** 1 | **Date:** 2026-05-26
**Status:** Active | **Enforcement:** `v3/external/capability_contract.py`

---

## Why This Contract Exists

SystemKernel v3.0 is a deterministic execution kernel — 100% pure, zero LLM.
External tools (Repomix, ccusage, mem0, Graphiti, OpenHands, AutoGen, etc.)
provide valuable capabilities but are inherently non-deterministic, may
require network access, and may introduce AI/LLM dependencies.

The Capability Adapter Contract defines a universal boundary that allows
these tools to be used safely without contaminating the kernel.

**Core principle:** External systems provide EVIDENCE, never TRUTH.

---

## Adapter as Boundary

```
┌─────────────────────────────────────────────────┐
│                 KERNEL (Deterministic)            │
│  Adapter │ TaskSystem │ ExecutionLoop │ EventBus │
│              │                                   │
│              │ Capability Adapter Contract        │
│              │ (THIS DOCUMENT)                    │
│              │                                   │
│  ┌───────────┴──────────────────────────────┐    │
│  │       EXTERNAL CAPABILITY ADAPTERS         │    │
│  │  context │ memory │ agent │ ide │ eval ... │    │
│  │  ALL removable. ALL truth_source=false.    │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

Adapters live OUTSIDE the kernel boundary in `v3/external/`. They may read
external tool output or, when explicitly approved, execute external tools
as subprocesses. They never import external tools as Python dependencies.

---

## External Outputs Are Evidence Only

Every external tool output is treated as **evidence**, not truth:

- `truth_source` is ALWAYS `false` — enforced by the contract validator
- All evidence includes provenance (tool name, version, invocation, timestamp)
- Evidence hashes are deterministic and verifiable
- The kernel never consumes evidence directly — adapters produce
  developer-facing reports

This is the same model used by Repomix (context packs) and ccusage
(usage reports) in Phase 7.

---

## Execution Modes

| Mode | Description | Approval Required |
|------|-------------|-------------------|
| `dry_run` | Plan only, zero side effects | No |
| `inspect_only` | Read existing output, no execution | No |
| `explicit_execute` | Execute with `--allow-execute` flag | **Yes** |
| `external_service` | Talk to running external service | **Yes** |
| `disabled` | Explicitly disabled | N/A |

Approval is required for:
- `explicit_execute` mode
- Any network access
- Any filesystem write

---

## Approval Model

1. **Dry-run and inspect-only** modes require no approval — they are read-only.
2. **Explicit execution** requires the `--allow-execute` CLI flag.
3. **Network access** requires explicit approval in the input contract.
4. **Filesystem write** requires explicit approval in the input contract.
5. **Critical-risk** adapters default to `disabled` — they cannot run without
   explicit reconfiguration.

---

## Lifecycle Model

Every adapter follows a gated lifecycle:

```
proposed → registered → inspected → trialed → adapter_ready → approved
                                                      ↓
                                              (can also go to)
                                                      ↓
                                               rejected / disabled / deprecated
```

**Forward progression is gated:** you cannot skip from `proposed` to `approved`.
Each state must be earned.

**Terminal states:** `rejected`, `disabled`, and `deprecated` require manual
intervention to reopen (back to `proposed` only).

**Active states:** `approved` and `adapter_ready` — adapters in these states
are considered usable.

---

## How Existing Adapters Fit

### Repomix (context pack adapter)

| Field | Value |
|-------|-------|
| Capability Type | `context` |
| Execution Modes | `dry_run`, `inspect_only`, `explicit_execute` |
| Risk Level | `medium` |
| truth_source | `false` |
| removable | `true` |

Already conforms to the contract. Phase 7C implementation matches the
contract requirements exactly.

### ccusage (usage report adapter)

| Field | Value |
|-------|-------|
| Capability Type | `usage` |
| Execution Modes | `inspect_only` |
| Risk Level | `low` |
| truth_source | `false` |
| removable | `true` |

Already conforms. Phase 7E implementation is a pure inspect-only adapter.

---

## Future Adapters

The contract supports these planned v4.0 adapters:

| Adapter | Type | Phase | Notes |
|---------|------|-------|-------|
| mem0 | `memory` | 3 | Memory intelligence backend |
| Graphiti | `memory` | 3 | Graph-based memory |
| OpenHands | `agent` | 5 | Autonomous agent executor |
| AutoGen | `agent` | 5 | Multi-agent framework |
| Continue | `ide` | IDE integration | Workspace provider |
| Anthropic Skills | `skill` | TBD | Skill format reference |

Each will implement `ExternalCapabilityAdapterSpec` and follow the
lifecycle from `proposed` through to `approved`.

---

## Validation Rules Summary

1. `adapter_id` must be non-empty and deterministic
2. `truth_source` must always be `false` (enforced at multiple levels)
3. `removable` must always be `true`
4. `forbidden_actions` must not be empty
5. `explicit_execute` mode requires `requires_approval: true`
6. `allows_network` requires `requires_approval: true`
7. `allows_filesystem_write` requires `requires_approval: true`
8. `critical` risk adapters must include `disabled` in execution modes
9. Output contract `truth_source` must be `false`
10. All hashes are deterministic (SHA-256, sorted JSON keys)

---

## Enforcement

```bash
# Validate an adapter spec
python -c "
from v3.external.capability_contract import ExternalCapabilityAdapterSpec, validate_adapter_spec
spec = ExternalCapabilityAdapterSpec(
    adapter_id='my-adapter',
    name='My Adapter',
    capability_type='tool',
    forbidden_actions=('no_network',),
)
valid, errors = validate_adapter_spec(spec)
print('Valid:', valid, errors)
"

# Check lifecycle transition
python -c "
from v3.external.capability_lifecycle import validate_lifecycle_transition, STATE_PROPOSED, STATE_REGISTERED
valid, reason = validate_lifecycle_transition(STATE_PROPOSED, STATE_REGISTERED)
print('Valid:', valid, reason)
"

# Run contract tests
python v3/tests/test_capability_contract.py
```

---

*SystemKernel v4.0 Phase 1 — Capability Adapter Contract*
