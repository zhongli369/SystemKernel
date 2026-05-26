# Memory/

Memory subsystem — OUTSIDE kernel boundary.

## Architecture

```
EventBus → MemoryService.add()  → mem0 (episodic)
                                → graphiti (semantic)

Kernel   → MemoryService.search() → deterministic query (zero LLM)
```

## Design

- LLM allowed for write (mem0 extraction, graphiti entity resolution)
- Zero LLM for read (search is deterministic)
- Removable: kernel functions without this package
- Communication: EventBus for writes, direct API for reads

## Adapters

| Adapter | Backend | Purpose |
|---------|---------|---------|
| `mem0_adapter.py` | Qdrant + SQLite | Episodic memory |
| `graphiti_adapter.py` | Neo4j/FalkorDB | Semantic knowledge graph |
