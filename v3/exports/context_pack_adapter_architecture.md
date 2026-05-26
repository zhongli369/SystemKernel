# Context Pack Adapter — Architecture

**Date:** 2026-05-26
**Phase:** 7C
**Module:** `v3/external/context_pack.py`

---

## 1. External Wrapper Model

The Context Pack Adapter wraps `npx repomix` as an external process. It never imports
Repomix as a Python dependency. The adapter lives in `v3/external/` — outside the kernel
boundary — and is accessed only through the CLI or direct import by developers.

```
User/CLI → ContextPackAdapter → npx repomix (external process)
                                    │
                                    └→ .md/.xml/.json output file
```

## 2. Why Repomix Stays Outside Kernel

| Reason | Detail |
|--------|--------|
| **Language boundary** | Repomix is TypeScript/Node.js. Kernel is Python stdlib only. |
| **Dependency purity** | Kernel must remain install-free. Repomix requires Node.js >= 22 + npm packages. |
| **Execution model** | Kernel is deterministic, in-process. Repomix is an external CLI call. |
| **Failure isolation** | If npx fails, the adapter returns a blocked/failed result. Kernel is unaffected. |
| **Security boundary** | External process — no shared memory, no import, no coupling. |

## 3. Context Pack Is NOT a Truth Source

Every `ContextPackResult` has `truth_source=False`. This is unconditional and
cannot be changed. Context packs are AI-consumable snapshots of a directory
at a point in time. They are not:

- A substitute for source files
- A configuration artifact
- An input to kernel execution
- A routable skill
- A memory record

They are developer convenience outputs only.

## 4. Safety Gates

| Gate | Where | Behavior |
|------|-------|----------|
| Repo root block | `plan()`, `generate()` | Blocks if target is repo root or v3/ root |
| Oversize block | `plan()` | Blocks if estimated output exceeds `max_bytes` |
| Execute gate | `generate()` | Refuses unless `allow_execute=True` |
| Target not found | `plan()` | Blocks if target directory doesn't exist |
| truth_source invariant | All methods | Always returns `False` |

## 5. Dry-Run vs Explicit Execution

### Plan (dry-run, default)
```
systemkernel context-pack plan v3/intake --output out.md
```
- Constructs the npx command deterministically
- Estimates size, tokens, and file count
- Never executes anything
- Always safe to run

### Generate (explicit opt-in)
```
systemkernel context-pack generate v3/intake --output out.md --allow-execute
```
- Requires `--allow-execute` flag
- Runs `npx repomix` as a subprocess
- Writes output to the specified path
- Network may be required on first run

### Inspect (read-only)
```
systemkernel context-pack inspect out.md
```
- Reads an existing pack file
- Reports size, line count, hash, included files
- Never modifies anything

## 6. Module Structure

```
v3/external/
├── __init__.py          # Public exports
└── context_pack.py      # ContextPackConfig, ContextPackResult, ContextPackAdapter
```

### Data Flow

```
ContextPackConfig → ContextPackAdapter.plan() → ContextPackResult (status=planned)
                                              → ContextPackAdapter.generate() → ContextPackResult (status=generated)
                  → ContextPackAdapter.inspect_output() → ContextPackResult (status=generated)
                  → ContextPackAdapter.verify_pack() → bool
```

## 7. Invariants

| # | Invariant | Enforcement |
|---|-----------|-------------|
| 1 | No Python import of repomix | AST scan in tests |
| 2 | truth_source always False | dataclass default + test coverage |
| 3 | plan() never executes | No subprocess call in plan() |
| 4 | generate() requires allow_execute | Explicit parameter check |
| 5 | Kernel boundary preserved | Module in v3/external/, not v3/kernel/ |
| 6 | No network in tests | Test scan for network imports |

---

*Context Pack Adapter Architecture — Phase 7C — 2026-05-26*
