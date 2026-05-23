# Kernel Constitution v2

SystemKernel machine-enforceable contract. Every rule in this document is
checkable by `architecture_guard.py`.

Current: **v2.0** | Stability: **96/100** | Subsystems: **5**

---

## 1. Kernel Boundary

### IN kernel

| Subsystem | Import | Responsibility |
|-----------|--------|----------------|
| Adapter | `SkillsManagementSystem.core.adapter` | Route intent→skill. Does NOT execute. |
| TaskSystem | `TaskSystem.core.task_manager` | Task lifecycle (backlog→active→done). Does NOT route or execute. |
| EventBus | `EventBus` | Ingest external events. Does NOT classify or use LLMs. |
| ExecutionLoop | `ExecutionLoop.loop` | Execute + verify. Does NOT route or create tasks. |
| Observability | `Observability` | Record traces + metrics. Does NOT decide, predict, or alert. |

### NOT in kernel

- Skill packages (`SkillsManagementSystem/packages/`) — ecosystem, not kernel
- RepoAnalyzer — consumer of kernel APIs
- CC日志/ — external logging, governed separately
- Any LLM, classifier, predictor, or autonomous decision system

### Valid imports (exhaustive)

```python
from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest, get_registry_info, get_skill_metadata
from TaskSystem.core.task_manager import create_task, start_task, complete_task, ...    # public functions only
from ExecutionLoop.loop import run, ExecutionRequest, ResolvedCapability, ExecutionResult
from EventBus import ingest, ingest_cli, ingest_github, ingest_filewatch, EventResult
from Observability import trace, metrics, replay                                       # record only, never decide
```

All other imports from kernel internals are contract violations.

---

## 2. System Modules

### 2.1 Adapter

```
resolve(CapabilityRequest) → CapabilityBinding
get_registry_info()         → dict
get_skill_metadata(name)    → dict
INTENT_HINTS                → dict (read-only reference)
```

**Must NOT:** Execute skills, hold state, use LLMs, re-route on empty.

**Empty binding contract:** `CapabilityBinding(skill_id="", confidence=0.0, alternatives=(), reason="...")` — no fallback, no retry.

### 2.2 ExecutionLoop

```
run(ExecutionRequest, *, correction_attempted=False, cwd=".") → ExecutionResult
extract_report(ExecutionResult) → dict
write_summary_to_task(ExecutionResult, task_id) → bool         # optional
```

**Must NOT:** Route skills, create tasks, make AI decisions, persist state (caller decides).

**Pipeline:** `lint → typecheck → test → [custom] → report` — FIXED, always this order.

**Retry:** Max 2 attempts (initial + 1 correction based on error log output only).

### 2.3 TaskSystem

```
create_task(title) → dict
start_task(task_id) → dict
complete_task(task_id) → dict
add_step(task_id, content) → dict
done_step(task_id, step_id) → dict
bind_skill(task_id, step_id, skill_name) → dict
```

**State machine:** `backlog → active → done` (reopen: done→active allowed).
No other transitions valid.

**Must NOT:** Route skills, execute skills, use LLMs.

### 2.4 EventBus

```
ingest(raw_event: dict) → EventResult
ingest_cli(argv: list[str]) → EventResult
ingest_github(headers: dict, body: dict) → EventResult
ingest_filewatch(path: str, change_type: str) → EventResult
```

**Pipeline:** `Source → normalize → validate → route → dispatch → TaskSystem`

**Must NOT:** Use LLMs anywhere, classify events, prioritize, use semantic analysis.

### 2.5 Observability

```
trace.record_span(stage, data, trace_id, parent_span_id) → TraceSpan
trace.get_trace_chain(trace_id, date_str) → list[TraceSpan]
metrics.record_metric(metric_type, value, tags, trace_id) → MetricPoint
metrics.get_metric_summary(metric_type, date_str) → dict
replay.replay_trace(trace_id, mode, date_str) → ReplayResult
```

**Must NOT:** Decide, predict, alert, detect anomalies, use LLMs, influence kernel behavior.

**Hook contract (ALL kernel files):**
```python
try:
    from Observability.trace import record_span
    record_span(stage="...", data={...}, trace_id=tid)
except Exception:
    pass
```

---

## 3. Execution Model (3 Paths)

### Path 1: Intent (normative)

```
CapabilityRequest → Adapter.resolve() → CapabilityBinding
                                       → TaskSystem (create task)
                                       → ExecutionLoop.run()
                                       → ExecutionResult
```

### Path 2: Event

```
External trigger → EventBus.ingest() → validate → route → dispatch → TaskSystem
                → EventResult { task_id }
```

### Path 3: Short (demo only)

```
Adapter.resolve() → bind skill_id → ExecutionLoop.run()
(Skips TaskSystem — for demos and one-shot operations only.)
```

---

## 4. ExecutionLoop Contract

### Fixed pipeline (immutable order)

```
1. lint      → ruff check .
2. typecheck → mypy .
3. test      → pytest -q --tb=short
4. [custom]  → shell command (run only if named checks all pass)
5. report    → standardized JSON
```

Stop at first failure. No reordering. No conditional execution.

### Sandbox

```
timeout_per_check: 300s
timeout_total:     600s
filesystem_scope:  . (cwd)
max_output_bytes:  50000
```

### Retry policy

```
attempt 1: run pipeline, return result
if correction_remaining:
  caller applies ONE correction based on error log
attempt 2: run pipeline again, return final result
STOP. No further corrections.
```

Correction basis: **error log output only.** No AI decisions.

### JSON report schema (mandatory output)

```
{
  task_id:       str,
  skill_id:      str,
  attempts:      int (1 or 2),
  lint:          "pass"|"fail"|"skipped",
  typecheck:     "pass"|"fail"|"skipped",
  tests:         "pass"|"fail"|"skipped",
  duration_ms:   int,
  error_summary: str
}
```

---

## 5. EventBus Contract

### Pipeline (3 stages, 0 LLM)

```
raw_event → validate() → route() → dispatch()
              │            │          │
              │            │          └─ TaskSystem function call
              │            └─ Deterministic lookup table (13 rules)
              └─ Structural check (UUID, closed event type, ISO-8601)
```

### Event sources (closed set)

| Source | Event types |
|--------|-------------|
| CLI | `cli.task.{create,start,complete,list}` |
| GitHub | `github.{issue,pr,push}.*` |
| FileWatch | `file.{created,changed,deleted}` |

### FileWatch whitelist

Only 5 files trigger `action=create_task`:
`CLAUDE.md`, `registry.json`, `manifest.json`,
`.claude/settings.json`, `.claude/settings.local.json`

All other file events → `action=skip`.

### Routing table

13 deterministic rules. Action set: `create_task | start_task | complete_task | skip`.
Priority set: `P0 | P1 | P2`.

---

## 6. Adapter Contract

### Single entrypoint

```
resolve(CapabilityRequest(intent, context, source)) → CapabilityBinding
```

### Determinism

Same `CapabilityRequest` → same `CapabilityBinding`. Always. No exceptions.

### Empty binding

```
skill_id=""  confidence=0.0  alternatives=()  reason="No skill matched..."
```

No second-pass routing. No fallback. No default skill. Caller handles.

### Metadata (read-only, NOT for routing)

```
get_registry_info()      → { "all_skills": [...] }
get_skill_metadata(name) → { ... } or {}
```

### INTENT_HINTS (closed set, additive only)

```
refactor   → "refactor code improve structure reduce coupling"
decouple   → "decouple modules reduce dependencies extract interfaces"
stabilize  → "stabilize add error handling logging tests entry point"
optimize   → "optimize simplify pipeline reduce dependency count"
cleanup    → "cleanup audit deduplicate remove unused code"
```

---

## 7. TaskSystem Contract

### State machine

```
backlog → active → done
              ↑        │
              └────────┘ (reopen only)
```

`validate_transition(old, new)` enforces this. No other transitions.

### Task operations

```
create   — new task in backlog, auto-generated ID
start    — backlog → active, sets started_at
complete — active → done, sets completed_at
```

### Step operations

```
add_step   — append step with auto-suggested skills
done_step  — mark step done
bind_skill — bind skill_name to step
```

Steps are dicts: `{id, content, status, suggested_skills, selected_skill, ...}`

### Skill suggestion

`suggest_skills_for_step()` delegates to `Adapter.resolve()`. No local keyword matching.

---

## 8. Observability Contract

### Guarantees

| Guarantee | Rule |
|-----------|------|
| Write-only | Records behavior, never drives it |
| Append-only | JSONL, never modified after write |
| Removable | Delete `Observability/` or `traces/` or `metrics/` → zero kernel impact |
| Non-blocking | All hooks: `try: except Exception: pass` |
| No intelligence | Zero LLM calls, zero decisions, zero anomaly detection |

### Trace chain

```
event → task → routing → execution → validation
  │       │        │          │            │
  └───────┴────────┴──────────┴────────────┘
              same trace_id propagates
              parent_span_id links lineage
```

### 6 trace stages

`event | task | routing | execution | validation | replay`

### 7 metric types

`routing_latency_ms | execution_latency_ms | validation_passed | retry | skill_hit | event_throughput | trace_span_count`

### Hook locations

| Subsystem | Records |
|-----------|---------|
| EventBus.ingest() | event span, task span, routing_latency_ms, event_throughput |
| Adapter.resolve() | routing span, routing_latency_ms, skill_hit |
| ExecutionLoop.run() | execution span, validation span, execution_latency_ms, validation_passed, retry |
| TaskSystem.create_task() | task span |

### Storage

```
traces/   → YYYY-MM-DD/trace.jsonl       (partitioned by date)
metrics/  → {metric_type}/YYYY-MM-DD.jsonl (partitioned by type + date)
```

### Replay

Reads historical traces from disk. Does NOT re-execute, re-route, or re-decide.
Modes: `full | execution_only | routing_only`.

---

## 9. Registry Rules

### Authority

`registry.json` + package `manifest.json` + SKILL.md frontmatter = single source of truth.

### Requirements

- 0 hardcoded Python skill dicts in code
- `capability_registry.py` reads from JSON files only
- Skills removable: delete from registry → ceases to exist

### Schema (per skill)

```
skill_id, version, category, inputs, outputs, constraints, deterministic, source, validator
```

All 9 fields required.

---

## 10. Data Schemas

### 10.1 Adapter

```
CapabilityRequest (frozen)
  intent:   str
  context:  str
  source:   str = ""

CapabilityBinding (frozen)
  skill_id:      str
  confidence:    float
  alternatives:  tuple[str, ...]
  reason:        str
```

### 10.2 ExecutionLoop

```
ResolvedCapability (frozen)
  skill_id:   str
  confidence: float = 1.0

ExecutionRequest (frozen)
  capability:    ResolvedCapability
  target:        str
  verification:  tuple[str, ...]

ExecutionResult (frozen)
  success:              bool
  corrected:            bool
  verification_passed:  bool
  attempt:              int
  correction_remaining: bool
  summary:              str

SandboxConfig (frozen)
  timeout_per_check: int = 300
  timeout_total:     int = 600
  filesystem_scope:  str = "."
  max_output_bytes:  int = 50000
```

### 10.3 EventBus

```
Event (frozen)
  event_id:   str
  event_type: str      — 13 closed-set values
  source:     str      — "cli"|"github"|"filewatch"
  payload:    dict
  timestamp:  str      — ISO-8601

RoutingDecision (frozen)
  event_id:  str
  action:    str      — "create_task"|"start_task"|"complete_task"|"skip"
  title:     str
  priority:  str      — "P0"|"P1"|"P2"
  reason:    str
  metadata:  dict

EventResult (frozen)
  event:              Optional[Event]
  validation_errors:  tuple[ValidationError, ...]
  decision:           Optional[RoutingDecision]
  task_id:            Optional[str]
  success:            bool
  trace:              str
```

### 10.4 Observability

```
TraceSpan (frozen)
  span_id:         str
  trace_id:        str
  parent_span_id:  str
  stage:           str      — TRACE_STAGES
  timestamp:       str      — ISO-8601
  data:            dict
  metadata:        dict

MetricPoint (frozen)
  timestamp:   str
  metric_type: str
  value:       float
  tags:        dict
  trace_id:    str

ReplayResult (frozen)
  trace_id:      str
  mode:          str      — "full"|"execution_only"|"routing_only"
  spans:         tuple[TraceSpan, ...]
  timeline:      str
  stage_count:   int
  deterministic: bool
```

### 10.5 TaskSystem

```
Task (dict, file-based JSON)
  id:             str
  title:          str
  status:         str      — "backlog"|"active"|"done"
  created_at:     str
  updated_at:     str
  started_at:     str|null
  completed_at:   str|null
  steps:          list[dict]
  notes:          str
  context_log:    list[str]
  event_log:      list[str]
  current_focus:  str
  tags:           list[str]
  priority:       str      — "P0"|"P1"|"P2"
```

---

## 11. System Invariants

### Determinism

| Rule | Scope |
|------|-------|
| Same CapabilityRequest → same CapabilityBinding | Adapter |
| Same event → same RoutingDecision → same task | EventBus |
| Same ExecutionRequest → same check sequence | ExecutionLoop |
| Same trace data → same ReplayResult | Observability |

### Zero LLM

| Rule | Scope |
|------|-------|
| No LLM import, call, or API anywhere in pipeline | EventBus |
| No LLM import, call, or API anywhere in module | ExecutionLoop |
| No LLM import, call, or API anywhere in module | Observability |
| No LLM-based routing or classification | Adapter, TaskSystem |

### Routing

| Rule |
|------|
| `Adapter.resolve()` is the ONLY route from intent to skill |
| No direct import of `routing_pipeline`, `capability_registry`, `alias_resolver`, `tag_matcher`, `routing_engine`, `package_router`, `external_skill_adapter` |
| No `if intent == "X": skill = "Y"` anywhere outside adapter.py |
| No `match intent:` patterns for skill selection |
| No "try Adapter first, then fallback" patterns |
| No subprocess or importlib for routing |
| No `sys.path.insert/append` inside function bodies |
| `INTENT_HINTS` may only exist in `adapter.py` |

### Execution

| Rule |
|------|
| Pipeline order is FIXED: lint → typecheck → test → [custom] → report |
| Max 2 attempts (initial + 1 correction based on error log) |
| ExecutionLoop must NOT import routing modules, create tasks, or use LLMs |
| ExecutionLoop must NOT persist state — caller decides |

### Registry

| Rule |
|------|
| Registry is the ONLY source of truth for skill existence |
| 0 hardcoded Python skill dicts in code |
| `capability_registry.py` reads from data files only |
| `classify.py` must NOT be imported by any routing module |

### Observability

| Rule |
|------|
| All kernel hooks: `try: except Exception: pass` |
| Zero LLM/AI imports in Observability/ |
| Zero decision-making function calls in Observability/ |
| Delete Observability/ → kernel behavior unchanged |

### Architecture enforcement

| Tool | Checks |
|------|--------|
| `architecture_guard.py` | Banned imports, hidden decisions, sys.path hacks, LLM imports, registry purity, observability purity |
| `drift_detector.py` | CLAUDE.md claims vs code reality |
| `hooks/pre-commit` | Drift detector on commit |

---

## 12. Legacy / Deprecated

| Item | Status | Action |
|------|--------|--------|
| `SkillsManagementSystem/core.py` (12.5KB) | Shadowed by `core/` package | Remove or rename to `core_legacy.py` |
| `SkillsManagementSystem/classify.py` (340 lines) | DEV TOOL ONLY | Remove once all callers migrated |
| `SkillsManagementSystem/suggestion_engine.py` (129 lines) | Deprecated | Remove once TaskSystem callers use Adapter |
| `SkillsManagementSystem/data/skill_capabilities.json` | Transitional | Migrate to SKILL.md frontmatter |

### Tracked discrepancies (summary)

```
HIGH (3):
  DRIFT-001 — No code implements full Adapter→TaskSystem→ExecutionLoop chain (normative diagram)
  DRIFT-002 — write_summary_to_task() uses deferred sys.path.insert
  DRIFT-011 — 4 packages missing manifest.json (agent-core, memory, minecraft, voice)

MEDIUM (4):
  DRIFT-004 — Legacy core.py v3.5 shadowed
  DRIFT-005 — suggestion_engine.py sys.path.insert
  DRIFT-006 — task_manager.py absolute import dependency
  DRIFT-007 — RepoAnalyzer internals undocumented

LOW (4):
  DRIFT-015 — skill_capabilities.json transitional
  DRIFT-016 — classify.py deprecated
  DRIFT-017 — suggestion_engine.py deprecated
  DRIFT-018 — Observability hooks in kernel files (non-blocking, documented)
```
