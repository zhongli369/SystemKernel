---
name: event-storage
description: Design event logging, storage, and retrieval systems for AI agents with structured event schemas. Use when implementing event sourcing, event storage, game event logging, or event-driven agent state tracking.
---

# Event Storage System

Design event logging and retrieval systems for AI agents. Every significant occurrence is an event — stored, indexed, and retrievable.

## Trigger

- "event storage"
- "event logging"
- "event sourcing"
- "game events"
- "event-driven"
- "agent events"

## Event Schema

```typescript
interface GameEvent {
  // Identity
  id: string;                    // UUID
  sequenceNumber: number;        // Monotonic, for ordering

  // Timing
  timestamp: number;             // Unix ms
  gameTick: number;              // Minecraft tick (20 ticks/sec)
  gameTime: string;              // Human-readable: "Day 5, 12:30"

  // Classification
  category: EventCategory;
  type: string;                  // Specific event type
  priority: EventPriority;

  // Content
  summary: string;               // One-line summary
  description: string;           // Detail (may be summarized later)

  // Source
  source: {
    type: "minecraft" | "agent" | "player" | "system" | "voice";
    id?: string;                 // Entity ID, player name, etc.
  };

  // Location
  location?: {
    x: number;
    y: number;
    z: number;
    dimension: string;
    biome?: string;
  };

  // Participants
  participants?: {
    entityId?: string;
    playerName?: string;
    role: "subject" | "object" | "observer";
  }[];

  // Impact
  impact: {
    importance: number;          // 1-10
    emotionalValence: number;    // -1.0 to 1.0
    affectsTask?: boolean;
    isLifeThreatening?: boolean;
    isRare?: boolean;
  };

  // Data
  data: Record<string, any>;    // Event-specific payload
}
```

## Event Categories

```typescript
enum EventCategory {
  // Minecraft game events
  WORLD = "world",             // Block updates, weather, time changes
  ENTITY = "entity",           // Mob spawns, deaths, movement
  PLAYER = "player",           // Player actions, chat, joins/leaves
  COMBAT = "combat",           // Damage, kills, PvP
  INVENTORY = "inventory",     // Item pickup, crafting, trading

  // Agent events
  AGENT_ACTION = "agent_action",   // Agent performed an action
  AGENT_DECISION = "agent_decision", // Agent made a decision
  AGENT_ERROR = "agent_error",     // Agent encountered an error
  AGENT_STATE = "agent_state",     // Agent state changed

  // System events
  SYSTEM = "system",           // Connection, performance, errors
  VOICE = "voice",             // Voice pipeline events
  MEMORY = "memory",           // Memory system events
}
```

## Event Storage (SQLite)

```sql
-- Main events table
CREATE TABLE events (
  id TEXT PRIMARY KEY,
  sequence_number INTEGER NOT NULL,
  timestamp INTEGER NOT NULL,
  game_tick INTEGER,
  game_time TEXT,

  category TEXT NOT NULL,
  type TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 5,

  summary TEXT NOT NULL,
  description TEXT,

  source_type TEXT NOT NULL,
  source_id TEXT,

  location_x REAL,
  location_y REAL,
  location_z REAL,
  dimension TEXT,
  biome TEXT,

  participants TEXT,  -- JSON array
  data TEXT,          -- JSON object (event-specific payload)

  importance INTEGER NOT NULL DEFAULT 5,
  emotional_valence REAL DEFAULT 0.0,

  -- Internal
  created_at INTEGER NOT NULL DEFAULT (unixepoch())
);

-- Indexes for common queries
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_category ON events(category);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_importance ON events(importance);
CREATE INDEX idx_events_sequence ON events(sequence_number);
CREATE INDEX idx_events_source ON events(source_type, source_id);

-- Latest events view (for quick context assembly)
CREATE VIEW recent_events AS
  SELECT * FROM events
  ORDER BY timestamp DESC
  LIMIT 100;
```

## Event Bus

```typescript
import { EventEmitter } from "events";

class EventBus extends EventEmitter {
  private storage: EventStorage;
  private sequenceNumber: number = 0;

  constructor(storage: EventStorage) {
    super();
    this.storage = storage;
    this.setMaxListeners(100);
  }

  // Publish an event (store + broadcast)
  async publish(event: Omit<GameEvent, "id" | "sequenceNumber">): Promise<void> {
    const fullEvent: GameEvent = {
      ...event,
      id: generateUUID(),
      sequenceNumber: ++this.sequenceNumber,
    };

    // Store immediately (fire and forget optional for low-priority)
    if (event.priority >= 5) {
      await this.storage.save(fullEvent);
    } else {
      this.storage.saveAsync(fullEvent); // Background save
    }

    // Broadcast to subscribers
    this.emit(`${event.category}:${event.type}`, fullEvent);
    this.emit(event.category, fullEvent);    // Broad category listener
    this.emit("*", fullEvent);               // Global listener
  }

  // Subscribe with filter
  subscribe(
    pattern: string,  // "combat:*" or "player:chat" or "*"
    handler: (event: GameEvent) => void,
    options?: { priorityMin?: number }
  ): () => void {
    const wrappedHandler = (event: GameEvent) => {
      if (!options?.priorityMin || event.priority >= options.priorityMin) {
        handler(event);
      }
    };
    this.on(pattern, wrappedHandler);
    return () => this.off(pattern, wrappedHandler); // Unsubscribe function
  }
}
```

## Event Handlers

```typescript
// Agent wake-up: which events trigger LLM invocation?
const LLM_TRIGGER_EVENTS = new Set([
  "player:chat",        // Someone spoke
  "combat:damage",      // Agent or player took damage
  "entity:creeper_nearby", // Danger nearby
  "player:join",        // Someone joined
  "player:leave",       // Someone left
  "agent_action:complete", // Action finished
  "agent_action:failed",   // Action failed
  "system:error",       // Something went wrong
  "voice:wake_word",    // "Hey [agent name]"
]);

function shouldTriggerLLM(event: GameEvent): boolean {
  const key = `${event.category}:${event.type}`;
  if (LLM_TRIGGER_EVENTS.has(key)) return true;
  if (event.importance >= 7) return true;
  if (event.impact.isLifeThreatening) return true;
  return false;
}
```

## Event Query & Retrieval

```typescript
class EventStorage {
  private db: Database;

  // Time-range query
  async getEventsInRange(
    startTime: number,
    endTime: number,
    options?: {
      categories?: EventCategory[];
      types?: string[];
      importanceMin?: number;
      limit?: number;
    }
  ): Promise<GameEvent[]> {
    let query = "SELECT * FROM events WHERE timestamp BETWEEN ? AND ?";
    const params: any[] = [startTime, endTime];

    if (options?.categories?.length) {
      query += ` AND category IN (${options.categories.map(() => "?").join(",")})`;
      params.push(...options.categories);
    }
    if (options?.importanceMin) {
      query += " AND importance >= ?";
      params.push(options.importanceMin);
    }
    query += " ORDER BY timestamp DESC";
    if (options?.limit) {
      query += " LIMIT ?";
      params.push(options.limit);
    }

    return this.db.all(query, params);
  }

  // Get recent context window for LLM
  async getContextWindow(
    windowMs: number = 120000,  // Last 2 minutes
    maxEvents: number = 20
  ): Promise<GameEvent[]> {
    return this.db.all(
      `SELECT * FROM events
       WHERE timestamp > ?
       ORDER BY importance DESC, timestamp DESC
       LIMIT ?`,
      [Date.now() - windowMs, maxEvents]
    );
  }

  // Entity timeline
  async getEntityTimeline(
    entityId: string,
    limit: number = 50
  ): Promise<GameEvent[]> {
    return this.db.all(
      `SELECT * FROM events
       WHERE source_id = ?
          OR participants LIKE ?
       ORDER BY timestamp DESC
       LIMIT ?`,
      [entityId, `%${entityId}%`, limit]
    );
  }

  // Location-based events
  async getEventsNearLocation(
    x: number, y: number, z: number,
    radius: number,
    limit: number = 20
  ): Promise<GameEvent[]> {
    return this.db.all(
      `SELECT * FROM events
       WHERE location_x BETWEEN ? AND ?
         AND location_y BETWEEN ? AND ?
         AND location_z BETWEEN ? AND ?
       ORDER BY timestamp DESC
       LIMIT ?`,
      [x - radius, x + radius, y - radius, y + radius, z - radius, z + radius, limit]
    );
  }

  // Get event statistics
  async getStats(
    category: EventCategory,
    timeRangeMs: number = 3600000  // Last hour
  ): Promise<EventStats> {
    return this.db.get(
      `SELECT
         COUNT(*) as total,
         AVG(importance) as avg_importance,
         COUNT(DISTINCT type) as unique_types,
         COUNT(DISTINCT source_id) as unique_sources
       FROM events
       WHERE category = ? AND timestamp > ?`,
      [category, Date.now() - timeRangeMs]
    );
  }
}
```

## Event Retention Policy

```typescript
async function cleanupOldEvents(storage: EventStorage): Promise<void> {
  const now = Date.now();

  // Keep all events from last 24 hours
  // Keep high-importance events (≥7) forever
  // Compress medium-importance events (4-6) after 7 days
  // Delete low-importance events (<4) after 30 days

  await storage.db.run(
    `DELETE FROM events
     WHERE timestamp < ?
       AND importance < 4
       AND category != 'player'  -- Always keep player interactions
       AND category != 'combat'  -- Always keep combat events
     `,
    [now - 30 * 24 * 3600000]
  );

  // Compress medium events
  const mediumEvents = await storage.db.all(
    `SELECT * FROM events
     WHERE timestamp < ?
       AND importance BETWEEN 4 AND 6
     ORDER BY category, type`,
    [now - 7 * 24 * 3600000]
  );
  // Summarize groups, keep summaries, delete originals
}
```
