---
name: memory-architecture
description: Design long-term memory systems for AI agents with event storage, importance scoring, retrieval, and summarization. Use when discussing agent memory, memory architecture, long-term memory, or context retention for AI agents.
---

# Memory Architecture

Design long-term memory systems for AI agents. Memory is not chat logs — it's structured knowledge about events, locations, relationships, and experiences.

## Trigger

- "memory system"
- "agent memory"
- "long-term memory"
- "memory architecture"
- "context retention"
- "memory retrieval"
- "memory importance"

## Memory Architecture Overview

```
┌─────────────────────────────────────────────┐
│              MEMORY SYSTEM                   │
│                                              │
│  Events → Importance Scoring → Storage       │
│           │                     │            │
│           ▼                     ▼            │
│     High Importance    ┌──────────────┐      │
│     → Permanent Store  │  SQLite DB   │      │
│                        │  (structured)│      │
│     Low Importance     └──────┬───────┘      │
│     → Summarize &            │              │
│       Compress               ▼              │
│                     ┌──────────────┐         │
│                     │ Vector Store  │         │
│                     │ (embeddings)  │         │
│                     └──────────────┘         │
│                                              │
│  Retrieval: hybrid (keyword + vector)        │
└─────────────────────────────────────────────┘
```

## Memory Types

```typescript
enum MemoryType {
  EVENT = "event",               // Something that happened
  LOCATION = "location",         // A place the agent visited
  RELATIONSHIP = "relationship", // Information about a player
  SKILL = "skill",               // Learned capability
  FAILURE = "failure",           // Something that went wrong
  SUCCESS = "success",           // Something that worked well
  PREFERENCE = "preference",     // Player preference
  TASK = "task",                 // A task (completed or pending)
  EMOTIONAL = "emotional",       // An emotionally significant moment
  KNOWLEDGE = "knowledge",       // General knowledge about the world
}

interface MemoryEntry {
  id: string;
  type: MemoryType;
  timestamp: number;              // Unix ms
  gameTime: number;               // In-game tick
  summary: string;                // 1-2 sentence summary
  details: string;                // Full description (may be summarized later)
  importance: number;             // 1-10, computed at creation
  emotionalValence: number;       // -1.0 to 1.0 (negative to positive)
  tags: string[];                 // For keyword retrieval
  relatedEntityIds: string[];     // Players, mobs, etc.
  location?: Vec3;                // Where it happened
  contextWindow: string;          // Raw context at time of event
  embedding?: number[];           // Vector embedding for semantic search
  decayed: boolean;               // Whether importance has been decayed
  lastAccessedAt: number;         // For cache replacement
  accessCount: number;            // How often retrieved
}
```

## Importance Scoring

```typescript
function calculateImportance(event: MemoryCandidate): number {
  let score = 0;

  // Base scores by type
  score += typeBaseScore[event.type];        // 1-5

  // Player interaction bonus
  if (event.involvesPlayer) score += 3;

  // Emotional significance
  score += Math.abs(event.emotionalValence) * 2;  // 0-2

  // Rarity bonus (unusual events are more important)
  if (event.isRare) score += 2;

  // Danger/threat level
  if (event.threatLevel > 5) score += event.threatLevel / 2;

  // Task relevance
  if (event.relatesToActiveTask) score += 2;

  // Recency boost (temporary, decays)
  score += Math.max(0, 3 - hoursSince(event.timestamp) / 4);

  return Math.min(10, Math.max(1, Math.round(score)));
}

const typeBaseScore: Record<MemoryType, number> = {
  event: 3,
  location: 4,
  relationship: 5,
  skill: 4,
  failure: 5,
  success: 4,
  preference: 5,
  task: 4,
  emotional: 5,
  knowledge: 3,
};
```

## Storage Schema (SQLite)

```sql
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  game_time INTEGER,
  summary TEXT NOT NULL,
  details TEXT,
  importance REAL NOT NULL DEFAULT 5.0,
  emotional_valence REAL DEFAULT 0.0,
  tags TEXT,                    -- JSON array
  related_entities TEXT,        -- JSON array
  location_x REAL,
  location_y REAL,
  location_z REAL,
  context_window TEXT,
  embedding BLOB,               -- Serialized float32 array
  decayed INTEGER DEFAULT 0,
  last_accessed_at INTEGER,
  access_count INTEGER DEFAULT 0
);

CREATE INDEX idx_memories_timestamp ON memories(timestamp);
CREATE INDEX idx_memories_type ON memories(type);
CREATE INDEX idx_memories_importance ON memories(importance);
CREATE INDEX idx_memories_tags ON memories(tags);

-- For time-based decay queries
CREATE INDEX idx_memories_decay ON memories(decayed, timestamp);

-- Full-text search for keyword retrieval
CREATE VIRTUAL TABLE memories_fts USING fts5(
  summary, details, tags, content=memories
);
```

## Memory Retrieval

```typescript
interface RetrievalQuery {
  types?: MemoryType[];
  tags?: string[];
  timeRange?: { start: number; end: number };
  importanceMin?: number;
  entityIds?: string[];
  location?: { near: Vec3; radius: number };
  semanticQuery?: string;    // For vector search
  limit: number;             // Max results
}

async function retrieveMemories(
  query: RetrievalQuery
): Promise<MemoryEntry[]> {
  // Hybrid search: combine keyword + vector
  const keywordResults = await keywordSearch(query);
  const vectorResults = query.semanticQuery
    ? await vectorSearch(query.semanticQuery, query.limit * 2)
    : [];

  // Merge and rerank
  const merged = mergeResults(keywordResults, vectorResults);
  return merged
    .sort((a, b) => b.importance * b.recency - a.importance * a.recency)
    .slice(0, query.limit);
}
```

## Memory Decay & Compression

### Time-Based Decay

```typescript
function decayImportance(memory: MemoryEntry): number {
  const ageInHours = (Date.now() - memory.timestamp) / 3600000;

  // Exponential decay with floor
  const halfLife = memory.type === "emotional" ? 72 : 24; // hours
  const decayed = memory.importance * Math.pow(0.5, ageInHours / halfLife);

  return Math.max(1, decayed);  // Floor at 1, never delete
}
```

### Compression

Low-importance, old memories are compressed:

```typescript
async function compressMemoryGroup(
  memories: MemoryEntry[]
): Promise<MemoryEntry> {
  // Use LLM to summarize a group of related memories
  const summary = await llm.summarize({
    instruction: "Summarize these related events into 1-2 sentences:",
    events: memories.map(m => `- ${m.summary}`),
  });

  return {
    ...memories[0],
    summary: summary.text,
    details: `Compressed from ${memories.length} events:\n` +
      memories.map(m => `- ${m.summary}`).join("\n"),
    importance: Math.min(10, Math.max(...memories.map(m => m.importance)) - 2),
    decayed: true,
  };
}

// Run periodically (every 100 memories or every hour)
async function compressionCycle(): Promise<void> {
  const oldMemories = await getCompressibleMemories({
    olderThan: Date.now() - 24 * 3600000,
    importanceBelow: 4,
    groupBy: "tags",  // Group related memories
  });
  // Compress each group, replace with single summary
}
```

## Memory Injection into LLM Context

Only the most relevant memories should enter the LLM context:

```typescript
async function getContextMemories(
  currentSituation: AgentContext
): Promise<MemoryEntry[]> {
  // 1. Always include: last 5 high-importance memories
  const recent = await retrieveRecent({ limit: 5, importanceMin: 5 });

  // 2. Semantic search: memories related to current situation
  const relevant = await retrieveMemories({
    semanticQuery: describeSituation(currentSituation),
    limit: 5,
  });

  // 3. Entity-specific: memories about nearby players/mobs
  const entityMemories = await getMemoriesForEntities(
    currentSituation.nearbyEntityIds
  );

  // Merge, deduplicate, limit to top 5-8
  return deduplicateAndRank([...recent, ...relevant, ...entityMemories])
    .slice(0, 8);
}
```

## Memory Maintenance

Run as background tasks:
- **Decay**: Recalculate importance every hour for memories > 24h old
- **Compression**: Group and summarize low-importance old memories daily
- **Embedding**: Generate embeddings for new memories (batch, async)
- **Cleanup**: Remove memories with importance < 1.0 and > 30 days old
- **Vacuum**: SQLite VACUUM weekly to reclaim space
