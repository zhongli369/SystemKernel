# Context Engineering Plane

**Version:** 1.0.0 | **Phase:** 4 | **Date:** 2026-05-26
**Status:** Active | **Enforcement:** `v3/external/context_plane.py`

---

## Purpose

The Context Engineering Plane formalizes the Repomix context-pack adapter
into a proper v4.0 component using Phase 1-3 contracts:

- **Phase 1** Capability Adapter Contract — adapter identity and lifecycle
- **Phase 2** Intelligence Plane Registry — registered as `repomix_context_pack`
- **Phase 3** External Evidence Model — all outputs are EVIDENCE, never TRUTH

Before Phase 4, the context-pack adapter (`v3/external/context_pack.py`)
worked in isolation. The Context Engineering Plane wraps it with budget
policy enforcement, sensitive pattern detection, evidence mapping, and
structured reporting.

---

## Budget Policy

Every context pack operation is validated against a `ContextBudgetPolicy`
before any tool execution:

| Constraint | Default | Description |
|------------|---------|-------------|
| `max_files` | 500 | Maximum files to include |
| `max_bytes` | 10 MB | Maximum output size |
| `max_tokens` | 200,000 | Maximum token estimate |
| `allowed_styles` | markdown, xml, json, plain | Supported output formats |
| `require_subdir_target` | true | Repo root must be explicitly allowed |
| `sensitive_patterns` | API_KEY, SECRET, TOKEN, etc. | Patterns flagged on detection |

Budget status can be:
- **pass** — all constraints within limits
- **review** — near budget limits (80%+), manual review recommended
- **blocked** — budget exceeded or policy violation

---

## Sensitive Pattern Detection

When inspecting an existing context pack, the plane scans for common
secrets patterns:

- `API_KEY`, `SECRET`, `TOKEN`, `PASSWORD`
- Private key headers (RSA, OpenSSH, PGP)
- `AUTH_TOKEN`, `ACCESS_KEY`, `SECRET_KEY`

Sensitive hits are reported in the inspection result and mapped to
evidence risk flags.

---

## Context Pack as Evidence

Every context pack output is EVIDENCE, never TRUTH.

The pipeline: `target → plan → inspect → evidence → report`

1. **Plan** — estimate size, files, tokens; validate against budget
2. **Inspect** — read existing file; detect sections, sensitive patterns
3. **Evidence** — wrap plan + inspection as `EvidenceRecords` in an `EvidenceBundle`
4. **Report** — combine all into a `ContextEngineeringReport`

At every stage, `truth_source` is `False`.

---

## Relationship to Repomix

The Context Engineering Plane uses Repomix (`npx repomix`) as a tool,
but never directly. The existing `ContextPackAdapter` in
`v3/external/context_pack.py` is the only code that constructs Repomix
commands, and only when explicitly opted in via `allow_execute=True`.

The plane itself:
- Plans context packs (no execution)
- Inspects existing outputs (read-only)
- Maps results to evidence (projection only)

---

## How Future Tools Plug In

When tools like LlamaIndex (LlamaPack) or DSPy-style context compilers
become available, they plug into the same plane:

1. Define a new adapter spec (Phase 1 contract)
2. Register in the capability registry (Phase 2)
3. Implement `plan_context_pack` with the new adapter
4. Output `EvidenceRecords` with `truth_source=False` (Phase 3)
5. The existing budget policy, inspection, and reporting layers apply
   without modification

The Context Engineering Plane is the single entry point for all context
packing tools — Repomix today, others tomorrow.

---

## CLI Usage

```bash
# Plan a context pack (no execution)
python v3/cli/systemkernel.py context-plane plan v3/tests --output ctx.md

# Inspect an existing context pack
python v3/cli/systemkernel.py context-plane inspect ctx.md

# Build evidence bundle
python v3/cli/systemkernel.py context-plane evidence ctx.md --target v3/tests
```

---

## Anti-Overengineering

- Existing `context_pack.py` reused, not replaced
- `EvidenceRecord`/`EvidenceBundle` reused from Phase 3
- `CapabilityRegistry` reused from Phase 2
- No new runtime capability added
- No external tool execution
- No new dependencies
- `truth_source` always `False`

---

*SystemKernel v4.0 Phase 4 — Context Engineering Plane*
