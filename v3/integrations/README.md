# Integrations/

External repository integration points. Not SystemKernel code.

## Mapped Repositories

| Directory | External Path | Status |
|-----------|--------------|--------|
| `repomix/` | `F:\Claude\Github\repomix` | cloned (Phase 1) |
| `ccusage/` | `F:\Claude\Github\ccusage` | cloned (Phase 1) |
| `mem0/` | `F:\Claude\Github\mem0` | placeholder |
| `graphiti/` | `F:\Claude\Github\graphiti` | placeholder |

## Adapters (Phase 2)

| File | Implements | Backend | Status |
|------|-----------|--------|--------|
| `mem0_adapter.py` | `MemoryAdapter` | mem0 (Qdrant) | skeleton |
| `graphiti_adapter.py` | `MemoryAdapter` | graphiti (Neo4j/FalkorDB) | skeleton |

Both adapters implement `MemoryAdapter` from `memory/memory_adapter_base.py`.
They are wired through `MemoryGateway` in `kernel/memory_gateway.py`.
Kernel NEVER imports these directly — only through the gateway.

## Memory Isolation Boundary

```
Kernel (ExecutionEngine)
    │
    └── emit() ──► MemoryGateway (kernel/memory_gateway.py)
                        │
                        ├── subscribe() ──► InProcessMemoryAdapter (default)
                        ├── subscribe() ──► Mem0Adapter (Phase 2b)
                        └── subscribe() ──► GraphitiAdapter (Phase 2b)
```

## Setup

```bash
# repomix
cd F:\Claude\Github\repomix && npm install

# ccusage
cd F:\Claude\Github\ccusage && npm install

# mem0 (Phase 2b — backend wiring)
# cd F:\Claude\Github\mem0 && pip install mem0ai qdrant-client

# graphiti (Phase 2b — backend wiring)
# cd F:\Claude\Github\graphiti && pip install graphiti-core falkordb
```
