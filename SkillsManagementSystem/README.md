# Skill System v3.5 — Capability Registry + Suggestion Engine

## Architecture

Skill System is a **pure passive system** — it provides skill metadata and
suggestions but has **no execution authority** and **no workflow control**.

| Role | Responsibility |
|------|---------------|
| Skill Registry | Skill metadata storage, package mapping, keyword tags, descriptions |
| Query System | `find_skill()`, `search_skill()`, `list_skills()` — pure lookup |
| Suggestion Engine | `suggest_skill(task_context)` — pure function, keyword-matching only |

### What Skill System Does NOT Do

- Does NOT execute skills
- Does NOT control workflows
- Does NOT auto-route tasks
- Does NOT modify TaskSystem state
- Does NOT trigger CLI commands or subprocesses
- Does NOT interact with filesystem outside registry scope

### Relationship with TaskSystem v3.5

```
TaskSystem v3.5  ←→  Skill System (this repo)
(workflow         (capability registry +
 controller)       suggestion engine)

Claude = reasoning + execution layer
```

Skill System only responds to requests. TaskSystem is the sole workflow controller.

---

## Core Module (`core.py`)

Three classes, all pure:

### SkillRegistry

```python
from core import load_registry_from_disk

registry = load_registry_from_disk()
registry.get_skill("debugger")       # → {version, description, package, ...}
registry.list_skills(package="base") # → skills in base package
registry.list_packages()             # → all packages
```

### QuerySystem

```python
from core import create_query_system

query = create_query_system()
query.find_skill("debugging")   # → [{name, score, description, package}, ...]
query.search_skill("pdf")       # → alias for find_skill
query.list_skills()             # → all skills
```

### SuggestionEngine

```python
from core import create_suggestion_engine

engine = create_suggestion_engine()
result = engine.suggest_skill({
    "task_id": "task-001",
    "step_id": "step-03",
    "step_content": "Debug the authentication middleware error",
    "context_log": "500 error in /api/auth/login",
})
# → [Skill Suggestion Only]
# {
#   "skill": "debugger",
#   "package": "base",
#   "confidence": 0.65,
#   "reason": "Keyword match: 'error, debug' → debugger (confidence: 0.65)",
#   "applicable_step": "step-03",
#   "alternatives": [...]
# }
```

---

## Suggestion Engine (`suggestion_engine.py`)

Convenience entry point with standard v3.5 I/O format.

### Standard Input

```json
{
  "task_id": "string (required)",
  "step_id": "string",
  "step_content": "string",
  "context_log": "string (optional)"
}
```

### Standard Output — [Skill Suggestion Only]

```json
{
  "skill": "string | null",
  "package": "string | null",
  "confidence": "float (0.0 ~ 1.0)",
  "reason": "string",
  "applicable_step": "string",
  "alternatives": "[{skill, package, confidence}, ...]"
}
```

### Keyword Matching Rules

Simple keyword matching only — no embedding models, no agent planning:

| Keywords | → Skill | Package |
|----------|---------|---------|
| schema, db, sql, migration, entity, model | repo-analyzer | base |
| bug, error, exception, crash, debug, fix | debugger | base |
| refactor, improve, clean up, optimize, code smell | code-review | base |
| research, investigate, study, survey, paper | researcher | base |
| design, architecture, system design, pattern | repo-analyzer | base |
| review, inspect, audit, check, analyze | code-review | base |
| algorithm, data structure, complexity, big o | algorithm-explainer | dsa |
| pdf, docx, xlsx, pptx, document, spreadsheet | docx | office |
| frontend, ui, react, vue, css, component, web | frontend-design | dev |
| api, claude, anthropic, sdk, prompt caching | claude-api | dev |
| mcp, model context protocol, server | mcp-builder | dev |
| test, testing, playwright, e2e | webapp-testing | dev |
| art, canvas, design, poster, visual, brand | canvas-design | dev |
| skill, create skill, new skill | skill-creator | base |

---

## Classify Engine (`classify.py`)

Auto-classifies a skill into the best-fit package based on SKILL.md content.

```python
from classify import classify_skill_pure, parse_skill_md

# Pure — no disk access
skill_data = parse_skill_md(Path("skills/my-skill"))
result = classify_skill_pure(skill_data, manifests)

# Convenience — reads SKILL.md from disk
result = classify_skill("skills/my-skill")
```

---

## Packages

| Package | Skills | Description |
|---------|--------|-------------|
| `base` | code-review, debugger, repo-analyzer, reflective-reasoning, researcher, skill-creator | Core reasoning & analysis |
| `dsa` | algorithm-explainer | Data structures & algorithms |
| `office` | docx, xlsx, pptx, pdf | Office document processing |
| `dev` | claude-api, frontend-design, mcp-builder, webapp-testing, +8 more | Developer tools |
| `finance` | (planned) | Finance & trading |
| `vercel-agent-skills` | react-best-practices, next-best-practices, +5 more | Vercel official skills (external) |
| `find-skill` | find-skills | Skill ecosystem discovery (external) |

---

## Directory Structure

```
F:\Claude\SkillsManagementSystem\
├── core.py                  # SkillRegistry, QuerySystem, SuggestionEngine
├── suggestion_engine.py     # Convenience entry point — suggest_skill()
├── classify.py              # Auto-classification (classify_skill_pure)
├── register.py              # Skill registration CLI
├── package_builder.py       # Package creation
├── registry.json            # Central registry data
├── data\
│   ├── lazyload_rules.json  # Package-matching keyword rules
│   ├── profiles.json        # Installation profiles
│   └── usage_stats.json     # Usage statistics
├── packages\                # Installed skill packages
│   ├── base\
│   ├── dsa\
│   ├── office\
│   ├── dev\
│   └── finance\
├── scripts\
│   ├── find_skill.py        # Skill search (pure registry lookup)
│   ├── health.py            # System health check
│   ├── profiles.py          # Profile management
│   ├── snapshots.py         # System state snapshots
│   └── stats.py             # Usage statistics tracker
├── shared\                   # Shared resources (office-scripts)
└── snapshots\               # System snapshot storage
```

### Removed (v3.5)

- `scripts/auto_router.py` — execution pipeline removed
- `scripts/auto_load.py` — absorbed into `core.py` SuggestionEngine

---

## Commands

### Skill Search

```
python scripts/find_skill.py "debug react component"
python scripts/find_skill.py "pdf" --json
```

### Health Check

```
python scripts/health.py health-check
python scripts/health.py health-check --json
```

### Registration

```
python register.py <skill_path> --package <name>
python register.py <skill_path> --auto
python register.py <skill_path> --auto --dry-run
```

### Package Creation

```
python package_builder.py <name> --description "..." --tags "a,b" --keywords "x,y"
```

### Stats

```
python scripts/stats.py summary
python scripts/stats.py recent --n 5
```

### Snapshots

```
python scripts/snapshots.py snapshot-save --label "pre-refactor"
python scripts/snapshots.py snapshot-list
```

### Profiles

```
python scripts/profiles.py create-profile <name> --packages base,office
python scripts/profiles.py list-profiles
```

---

## Safety Constraints

Skill System MUST NEVER:
- Modify TaskSystem data
- Modify task or step state
- Trigger CLI commands
- Interact with filesystem outside registry scope
- Execute external tools
- Initiate workflows

All APIs return suggestions only — never actions.
