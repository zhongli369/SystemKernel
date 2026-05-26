# Tests/

v3.0 test suite.

## Test Files

| File | Target |
|------|--------|
| `test_execution_engine.py` | ExecutionEngine, State, Checkpoint |
| `test_tool_adapter.py` | ToolAdapter protocol, repomix adapter |
| `test_memory_service.py` | MemoryService, mem0/graphiti adapters |
| `test_observability.py` | ObservabilityService, ccusage bridge |

## Run

```bash
cd F:\Claude\SystemKernel\v3
python -m pytest tests/ -v
```
