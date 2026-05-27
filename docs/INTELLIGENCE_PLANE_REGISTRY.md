# Intelligence Plane Registry

**Version:** 1.0.0 | **Phase:** 2 | **Date:** 2026-05-26
**Status:** Active | **Enforcement:** `v3/external/capability_registry.py`

---

## Why a Registry Exists

Before Phase 2, external tool information was scattered across CLI commands,
export reports, and documentation files. Adding a new tool required touching
multiple files. Querying "what tools do we have?" meant reading code.

The registry standardizes this into a single, deterministic, queryable data
structure. Every external capability — integrated, deferred, or planned — has
one authoritative registry entry.

---

## How This Reduces Future Integration Complexity

When Phase 3 (Memory Intelligence) starts, the mem0 adapter won't need to
invent its own registration, listing, or validation logic. It plugs into
the existing registry:

1. Create an `ExternalCapabilityAdapterSpec` (Phase 1 contract)
2. Create a `CapabilityRegistryEntry` with the spec
3. Add the entry to the default registry
4. Existing CLI commands (`capability list`, `capability show`) work immediately
5. Existing validation (`validate_registry`) enforces contract rules
6. Existing lifecycle tracking applies

Each future adapter saves ~200 lines of boilerplate.

---

## Registered vs. Integrated

| Status | Meaning | Example |
|--------|---------|---------|
| **Registered** | Listed in registry, spec defined | anthropic_skills |
| **Inspected** | External tool reviewed | - |
| **Trialed** | Dry-run tested, output validated | - |
| **Adapter Ready** | Adapter code written and tested | - |
| **Approved** | **Integrated** — adapter is active | repomix, ccusage |

The registry tracks these states. Being "registered" does not mean
"integrated." Placeholders are registered but explicitly disabled.

---

## Enabled vs. Approved

- **Enabled** means the adapter can be invoked (if its other gates pass).
- **Approved** means the adapter has passed all lifecycle gates.

An adapter can be approved but temporarily disabled (maintenance, security
issue). An adapter cannot be enabled if it has not passed lifecycle gates
(critical risk adapters must be approved before enabling).

---

## Lifecycle State Meanings

| State | Meaning | Can Execute? |
|-------|---------|--------------|
| `proposed` | Submitted for consideration | No |
| `registered` | Formally listed in registry | No |
| `inspected` | External tool reviewed, safe | No |
| `trialed` | Dry-run tested, output validated | dry_run only |
| `adapter_ready` | Adapter code written and tested | dry_run + inspect_only |
| `approved` | Fully integrated and verified | All allowed modes |
| `disabled` | Explicitly turned off | No |
| `rejected` | Rejected from integration | No |
| `deprecated` | Was approved, now retired | No (legacy only) |

---

## Why Placeholders Are Disabled

The 7 future adapters (mem0, Graphiti, OpenHands, AutoGen, Continue,
SWE-Agent, Letta) exist in the registry as `state=disabled, enabled=false`.
This serves three purposes:

1. **Registry shape validation** — ensures the registry can handle all planned
   capability types (context, memory, agent, ide, etc.)
2. **Roadmap visibility** — the registry doubles as a v4.0 roadmap checklist
3. **Integration readiness** — when Phase 3 starts, the mem0 placeholder
   transitions from `disabled` to `proposed` and starts the lifecycle

Placeholders do NOT imply integration. They do NOT import external modules.
They do NOT execute external tools. They are data entries only.

---

## How Repomix and ccusage Fit

Both are fully integrated (approved), enabled, and stable:

| Adapter | Type | Status | Tests |
|---------|------|--------|-------|
| `repomix_context_pack` | context | approved, enabled | 31 |
| `ccusage_usage_report` | usage | approved, enabled | 32 |

They serve as the reference implementation for all future adapters.

---

## Why Future Adapters Are Not Integrated Yet

| Adapter | Reason |
|---------|--------|
| mem0 | Phase 3 — requires memory intelligence plane |
| Graphiti | Phase 3 — requires graph-based memory model |
| OpenHands | Phase 5 — requires autonomous agent framework |
| AutoGen | Phase 5 — requires multi-agent orchestration |
| Continue | Future — IDE integration out of current scope |
| SWE-Agent | Phase 5 — Software engineering agent |
| Letta | Future — memory-augmented agent framework |

Each will follow the same contract and lifecycle once its phase begins.

---

## CLI Usage

```bash
# List all registry entries
python v3/cli/systemkernel.py capability list

# Print summary counts
python v3/cli/systemkernel.py capability summary

# Show one entry
python v3/cli/systemkernel.py capability show repomix_context_pack
```

---

## Anti-Overengineering

This phase added one dataclass (`CapabilityRegistryEntry`), one container
(`CapabilityRegistry`), and query/mutation functions. It reused Phase 1
contracts. It did not create parallel registries, new file formats, or
new abstraction layers.

**Did this reduce future adapter integration complexity?** YES — each
future adapter saves ~200 lines of registration/listing/validation code.

**New runtime capability added?** NO — the registry is read-only data
with CLI inspection commands.

---

*SystemKernel v4.0 Phase 2 — Intelligence Plane Registry*
