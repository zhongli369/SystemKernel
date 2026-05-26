# Kernel/

Core execution boundary. ZERO LLM. Deterministic only.

## Modules

| File | Status | Description |
|------|--------|-------------|
| `execution_engine.py` | ★ v3 new | State + Checkpoint + Reducer execution engine |
| `observability.py` | ★ v3 upgraded | Trace + metrics + ccusage bridge |
| `adapter.py` | → v2 | Skill routing (unchanged) |
| `task_system.py` | → v2 | Task lifecycle (unchanged) |
| `event_bus.py` | → v2 | Event ingestion (unchanged) |

## Rules

- No LLM imports (openai, anthropic, groq)
- No AI decisions
- Deterministic: same input → same output
- All hooks: try/except/pass
