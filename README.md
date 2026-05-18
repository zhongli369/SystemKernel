# SystemKernel — Deterministic AI Routing + Execution Kernel

**SystemKernel is NOT a framework. NOT a library. It is a deterministic kernel that routes AI capabilities, orchestrates tasks, and enforces verified execution.**

## What It Is

SystemKernel provides three things and three things only:

1. **Skill Routing (Adapter)** — Maps an intent + context to the best-matching skill. One entrypoint. Deterministic. Stateless.
2. **Task Orchestration (TaskSystem)** — Manages task lifecycle (backlog → active → done) with step decomposition and status tracking.
3. **Execution + Verification (ExecutionLoop)** — Runs verification checks against changed code with a bounded retry (max 2 attempts).

No agent frameworks. No probabilistic guessing. No shadow logic.

## Quick Start

```python
from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest
from ExecutionLoop.loop import run, ExecutionRequest, ResolvedCapability

# 1. Route intent → skill
binding = resolve(CapabilityRequest(
    intent="refactor",
    context="reduce coupling in utils/helpers.py",
    source="my-project"
))
print(f"Resolved: {binding.skill_id} (confidence: {binding.confidence:.2f})")

# 2. Execute with verification
capability = ResolvedCapability(
    skill_id=binding.skill_id,
    confidence=binding.confidence
)

result = run(ExecutionRequest(
    capability=capability,
    target="utils/helpers.py",
    verification=("lint", "typecheck")
))

# 3. Check result
print(f"Success: {result.success}")
print(f"Correction remaining: {result.correction_remaining}")
print(result.summary)
```

## System Architecture

```
Request (intent + context)
        │
        ▼
┌──────────────────────┐
│  Adapter.resolve()   │  ← Skill routing (returns binding, does NOT execute)
└──────────┬───────────┘
           │ CapabilityBinding
           ▼
┌──────────────────────┐
│  TaskSystem          │  ← Task creation, step decomposition, status tracking
└──────────┬───────────┘
           │ Task with assigned skill
           ▼
┌──────────────────────┐
│  ExecutionLoop.run() │  ← Execution + verification (max 2 attempts)
└──────────┬───────────┘
           │ ExecutionResult
           ▼
         Result
```

**Separation of concerns:**

| Concern | Owner | Must NOT |
|---------|-------|----------|
| Skill routing | Adapter | Execute |
| Skill matching | SkillSystem | Execute, hold state |
| Task lifecycle | TaskSystem | Route skills, execute |
| Execution + verify | ExecutionLoop | Route skills, create tasks |

## Public API

### Adapter (Skill Routing)

**Import:** `SkillsManagementSystem.core.adapter`

```python
from SkillsManagementSystem.core.adapter import (
    resolve, get_registry_info, get_skill_metadata,
    CapabilityRequest, CapabilityBinding, INTENT_HINTS
)

# Route intent + context → skill binding
binding = resolve(CapabilityRequest(
    intent="refactor",          # "refactor"|"decouple"|"stabilize"|"optimize"|"cleanup"|""
    context="description here", # free-text target description
    source="my-caller"          # optional audit label
))
# → CapabilityBinding(skill_id, confidence, alternatives, reason)

# Inspect the registry (read-only)
info = get_registry_info()
# → {"all_skills": [{"name": "...", ...}, ...]}

# Look up a single skill (read-only)
meta = get_skill_metadata("skill-name")
# → {"name": "...", "package": "...", ...} or {}

# Available intent hints (read-only reference)
INTENT_HINTS  # → {"refactor": "...", "decouple": "...", ...}
```

### ExecutionLoop (Verification)

**Import:** `ExecutionLoop.loop`

```python
from ExecutionLoop.loop import (
    run, write_summary_to_task,
    ExecutionRequest, ResolvedCapability, ExecutionResult
)

capability = ResolvedCapability(skill_id="some-skill", confidence=0.85)

result = run(ExecutionRequest(
    capability=capability,
    target="path/to/changed/file.py",
    verification=("lint", "typecheck", "test")  # named checks or shell commands
))
# → ExecutionResult(success, corrected, verification_passed, attempt, correction_remaining, summary)

# If result.correction_remaining is true:
#   caller applies ONE correction, then calls run() again with correction_attempted=True

# Optional: persist summary to TaskSystem
write_summary_to_task(result, task_id="task-001")
```

**Named verification checks:**

| Check | Command |
|-------|---------|
| `"lint"` | `ruff check .` |
| `"typecheck"` | `mypy .` |
| `"test"` | `pytest -q --tb=short` |

Custom shell commands are also accepted as verification strings.

### TaskSystem (Task Orchestration)

**Import:** `TaskSystem.core.task_manager`

```python
from TaskSystem.core.task_manager import (
    create_task, start_task, complete_task,
    add_step, done_step, list_steps,
    add_context_log, task_show, query_tasks,
    suggest_skills_for_step, bind_skill
)

# Create and manage tasks
task = create_task("Implement feature X")
task = start_task(task["id"])
task = complete_task(task["id"])

# Step decomposition
add_step(task["id"], "Design the interface")
add_step(task["id"], "Write tests")
done_step(task["id"], step_id=1)

# Skill binding (routes through Adapter)
skills = suggest_skills_for_step("refactor this function")
bind_skill(task["id"], step_id=2, skill_name=skills[0])

# Display
print(task_show(task["id"]))
```

TaskSystem delegates skill selection to Adapter. It never routes skills on its own.

## Contract Rules (CRITICAL)

These rules are enforced by `architecture_guard.py`. Violations of CRITICAL rules block merges.

### Routing

- **Single entrypoint:** `Adapter.resolve()` is the ONLY way to route an intent to a skill
- **No shadow routing:** No "try Adapter first, then my own logic" patterns
- **No fallback inside kernel:** When Adapter returns an empty binding, SystemKernel stops — it does not retry, fallback, or substitute
- **No subprocess routing:** `subprocess.run` / `subprocess.Popen` must not be used for skill routing
- **No sys.path hacks:** `sys.path.insert` / `sys.path.append` are banned inside function bodies
- **No `importlib`:** Module discovery for routing is forbidden
- **No direct registry access:** All metadata access must go through Adapter's `get_registry_info()` / `get_skill_metadata()`

### Execution

- **ExecutionLoop must not route skills** or create tasks
- **ExecutionLoop must be stateless** — no cached routing state
- **Max 2 attempts:** initial → one correction → stop. No infinite loops.

### Intent Maps

- **`INTENT_HINTS` exists only in `adapter.py`** — no duplicates anywhere
- **No `if intent == "X": skill = "Y"` decision chains** in any project code
- **No `match intent:` patterns** for skill selection

## Installation

### Repository Location

```
F:\Claude\SystemKernel\
```

### Import Path Setup

SystemKernel is designed to be used from sibling projects. Add the workspace root to your Python path:

```python
import sys
from pathlib import Path

workspace = Path(__file__).resolve().parent.parent  # adjust as needed
if str(workspace) not in sys.path:
    sys.path.insert(0, str(workspace))

# Now imports work:
from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest
from ExecutionLoop.loop import run, ExecutionRequest, ResolvedCapability
```

The workspace root (`F:\Claude\`) must be on `sys.path` so that `SkillsManagementSystem` and `ExecutionLoop` are importable as top-level packages.

### Running Architecture Guard

```bash
cd F:\Claude\SystemKernel
python architecture_guard.py           # human-readable output
python architecture_guard.py --json    # machine-readable output
```

A passing guard means zero CRITICAL violations and a stability score of 100/100.

## Repository Structure

```
SystemKernel/
├── SkillsManagementSystem/   ← SkillSystem (routing engine + registry)
│   └── core/
│       └── adapter.py        ← ONLY public entrypoint for routing
├── TaskSystem/               ← Task orchestration + state tracking
│   └── core/
│       └── task_manager.py   ← Task CRUD, steps, skill binding
├── ExecutionLoop/            ← Execution + verification harness
│   └── loop.py               ← Bounded verification loop (max 2 attempts)
├── architecture_guard.py     ← Contract enforcement (static analysis)
├── CLAUDE.md                 ← Calling protocol specification
├── README.md                 ← This file
└── examples/
    └── basic_usage.py        ← Minimal end-to-end example
```

## Stability Statement

**SystemKernel v1.0 is FROZEN.**

- Public API signatures (Adapter, ExecutionLoop, TaskSystem) are stable and will not change
- Only additive changes are allowed (new skills, new intent hints, new verification checks)
- No structural modifications without a freeze override
- The freeze override process requires: documented justification, `architecture_guard.py` update, full re-validation, and CLAUDE.md version bump

The internal implementation of SkillSystem (matching algorithms, registry structure, alias resolution) may evolve as long as the public contracts remain unchanged.

### Immutable Borders

- Adapter is the ONLY entry point for skill selection, metadata, and routing
- SkillSystem internals (routing_pipeline, capability_registry, etc.) are PRIVATE
- ExecutionLoop is PURE — no routing decisions, no task creation
- No new layers, entrypoints, or alternative routing systems

### Allowed Evolution

- SkillSystem internal logic improvements (routing_engine)
- Registry additions (new skills)
- Adapter `INTENT_HINTS` additions (additive only, no removal or renaming)

## Version

SystemKernel: **v1.0 (FROZEN)** | Protocol Spec: **v1.0** | Stability Score: **100/100**
