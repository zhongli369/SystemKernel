# SystemKernel — Calling Protocol Specification v1.0

This is a CALLING PROTOCOL, not documentation.

It defines the stable public interfaces, execution contracts, and routing boundaries
that external systems must adhere to. Internal implementation details are intentionally
absent — those are private to each subsystem.

---

## 1. Public Interface

SystemKernel exposes exactly three public subsystems. Every interaction with SystemKernel
goes through one of these.

### 1.1 Adapter — Routing Entrypoint

**Import path:** `SkillsManagementSystem.core.adapter`

**Data types (frozen, all fields required unless noted):**

```
CapabilityRequest
  intent:   str    — "refactor" | "decouple" | "stabilize" | "optimize" | "cleanup" | ""
  context:  str    — free-text description of the target or situation
  source:   str    — optional audit label, e.g. "repoanalyzer" | "tasksystem" (default "")

CapabilityBinding
  skill_id:      str
  confidence:    float
  alternatives:  tuple[str, ...]
  reason:        str
```

**Stable functions:**

| Function | Signature | Returns | Purpose |
|----------|-----------|---------|---------|
| `resolve` | `(CapabilityRequest) -> CapabilityBinding` | Binding with skill_id, confidence, alternatives, reason | Route an intent+context to a skill. The ONE AND ONLY routing entrypoint. |
| `get_registry_info` | `() -> dict` | Dict with `all_skills` key containing list of `{name, ...}` entries | Inspect the full skill registry. Read-only. |
| `get_skill_metadata` | `(skill_name: str) -> dict` | Dict of skill metadata, or `{}` if not found | Look up a single skill's metadata. Read-only. |

**Constants:**

```
INTENT_HINTS: dict[str, str]
  "refactor"   → "refactor code improve structure reduce coupling"
  "decouple"   → "decouple modules reduce dependencies extract interfaces"
  "stabilize"  → "stabilize add error handling logging tests entry point"
  "optimize"   → "optimize simplify pipeline reduce dependency count"
  "cleanup"    → "cleanup audit deduplicate remove unused code"
```

Intent hints are read-only reference data. Callers use `resolve()` — they do not need to
read INTENT_HINTS directly, but it is available for inspection.

### 1.2 ExecutionLoop — Execution + Verification

**Import path:** `ExecutionLoop.loop`

**Data types (frozen, all fields required):**

```
ResolvedCapability
  skill_id:   str
  confidence: float = 1.0

ExecutionRequest
  capability:    ResolvedCapability   — the pre-resolved skill to execute
  target:        str                  — file path or description of what changed
  verification:  tuple[str, ...]      — check names ("lint", "typecheck", "test") or shell commands

ExecutionResult
  success:              bool
  corrected:            bool
  verification_passed:  bool
  attempt:              int               — 1 or 2
  correction_remaining: bool              — True if one more correction is allowed
  summary:              str               — human-readable verification output
```

**Stable functions:**

| Function | Signature | Returns | Purpose |
|----------|-----------|---------|---------|
| `run` | `(ExecutionRequest, *, correction_attempted=False, cwd=".") -> ExecutionResult` | Verification result | Run the bounded verification loop. Max 2 attempts (initial + 1 correction). |

**Call sequence:**

```
1. run(request)                        → first verification
2. If result.correction_remaining:
     caller applies ONE correction
3. run(request, correction_attempted=True) → final verification
4. Stop. No further corrections.
```

**Named checks** (available as verification strings):

| Check | Command |
|-------|---------|
| `"lint"` | `ruff check .` |
| `"typecheck"` | `mypy .` |
| `"test"` | `pytest -q --tb=short` |

Custom shell commands are also accepted as verification strings.

**Optional persistence:**

| Function | Signature | Purpose |
|----------|-----------|---------|
| `write_summary_to_task` | `(ExecutionResult, task_id: str, task_system_path: str) -> bool` | Persist execution summary to TaskSystem context log. Optional — caller decides. |

### 1.3 TaskSystem — Task Orchestration

**Location:** `TaskSystem/` (file-based system)

TaskSystem is accessed through its core functions in `TaskSystem.core.task_manager`.
It manages task lifecycle: backlog → active → done (reopen allowed).

Key operations: create task, decompose into steps, track status, persist progress.
TaskSystem does NOT execute skills. It delegates skill selection to Adapter.

---

## 2. Execution Contract

### 2.1 Lifecycle

```
Request (intent + context)
        │
        ▼
┌─────────────────────┐
│  Adapter.resolve()  │  ← Skill routing (returns binding, does NOT execute)
└─────────┬───────────┘
          │ CapabilityBinding { skill_id, confidence, alternatives }
          ▼
┌─────────────────────┐
│  TaskSystem         │  ← Task creation, step decomposition, status tracking
└─────────┬───────────┘
          │ Task with assigned skill_id
          ▼
┌─────────────────────┐
│  ExecutionLoop.run()│  ← Execution + verification (max 2 attempts)
└─────────┬───────────┘
          │ ExecutionResult { success, verification_passed, summary }
          ▼
        Result
```

### 2.2 Determinism Guarantee

The same `CapabilityRequest` always produces the same `CapabilityBinding`.
The routing path is single-trace: no branching, no fallback, no retry-with-alternative-strategy.

### 2.3 Hard Fail Contract

When `Adapter.resolve()` cannot match a skill:

- Returns `CapabilityBinding(skill_id="", confidence=0.0, alternatives=(), reason="No skill matched...")`
- No second-pass routing occurs inside SystemKernel
- No default/fallback skill is substituted
- The caller is responsible for handling the empty binding

### 2.4 Separation of Concerns

| Concern | Owner | Must NOT |
|---------|-------|----------|
| Skill routing | Adapter | Execute |
| Skill matching | SkillSystem | Execute, hold state |
| Task lifecycle | TaskSystem | Route skills, execute |
| Execution + verify | ExecutionLoop | Route skills, create tasks |

---

## 3. Routing Contract

### 3.1 Single Authority

`Adapter.resolve()` is the only function that resolves an intent to a skill.
Every call site in every system must route through it.

### 3.2 Only Valid Import

```python
from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest

binding = resolve(CapabilityRequest(
    intent="refactor",
    context="reduce coupling in utils/helpers.py",
    source="repoanalyzer"
))
# binding.skill_id     → the resolved skill
# binding.confidence   → match confidence
# binding.alternatives → backup options (for external fallback only)
# binding.reason       → human-readable explanation
```

Any import path that does not go through `SkillsManagementSystem.core.adapter` to reach
SkillSystem functionality is a contract violation.

### 3.3 SkillSystem is a Black Box

From the caller's perspective, SkillSystem is opaque:

- Input: query string (derived from intent + context)
- Output: `CapabilityBinding` (skill_id, confidence, alternatives, reason)

Internal matching algorithms, registry structure, alias resolution, and tag matching
are private and may evolve without notice. Callers must not depend on them.

### 3.4 Metadata Access

For inspection purposes only (NOT for routing):

- `get_registry_info()` — list all registered skills
- `get_skill_metadata(name)` — look up a specific skill

These are read-only. They do not affect routing state.

---

## 4. Forbidden Behaviors

These are global bans. No external system may do any of the following when interacting
with SystemKernel.

### 4.1 Routing Bypasses

- Direct import of any SkillSystem module other than `adapter`
- Direct access to `registry.json`
- Any alternative skill resolution mechanism
- Subprocess invocation for skill routing
- `importlib` for module discovery or routing
- `sys.path.insert` or `sys.path.append` inside function bodies

### 4.2 Duplicate Logic

- Copying or redefining INTENT_HINTS anywhere outside adapter.py
- Implementing `if intent == "X": skill = "Y"` decision chains
- `match intent:` patterns for skill selection
- Any intent-to-skill mapping that shadows Adapter's routing

### 4.3 Shadow Routing

- "Try Adapter first, then try my own logic" patterns
- Second-pass routing when Adapter returns empty
- Parallel skill evaluation systems
- Fallback heuristics that inspect skill internals

### 4.4 Execution Bypasses

- Executing skills without going through ExecutionLoop (in OS mode)
- ExecutionLoop must not create tasks or route skills
- ExecutionLoop must not persist state (caller decides)

---

## 5. Extension Rules

### 5.1 Allowed (Safe, No Approval Required)

- Add new skill entries to the SkillSystem registry
- Add new `INTENT_HINTS` entries (additive only — never remove or rename existing)
- Extend ExecutionLoop named checks with new verification types
- Add new task types in TaskSystem (must route through Adapter for skill selection)

### 5.2 Forbidden (Contract Change — Requires Freeze Override)

- Adding new routing layers or entrypoints
- Modifying `CapabilityRequest` or `CapabilityBinding` field signatures
- Changing the single-trace execution model
- Adding new kernel subsystems beyond the 4 core components
- Introducing parallel or alternative execution frameworks

### 5.3 Freeze Override Process

1. Document the justification for violating an invariant
2. Update `architecture_guard.py` to reflect the new contract
3. Re-validate all existing tests and guard checks
4. Bump the CLAUDE.md version

---

## 6. Governance

### 6.1 Enforcement

`architecture_guard.py` is the automated enforcement tool for this contract.
It runs static analysis across all Python files and detects violations of the
routing, import, and decision-path rules defined here.

- Run: `python architecture_guard.py` or `python architecture_guard.py --json`
- CRITICAL violations → contract breach → block merge
- MEDIUM violations → require written justification

### 6.2 Stability Guarantee

The public interfaces documented in Section 1 are stable. Their signatures,
return types, and behavioral contracts will not change without a freeze override.

Internal implementations of SkillSystem, TaskSystem, and ExecutionLoop may evolve
as long as the public contracts remain unchanged.

### 6.3 Version

Current: **v1.0**
Status: **FROZEN**
Stability Score: **100/100**
