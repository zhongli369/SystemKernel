---
name: minecraft-bot
description: Design, build, and debug Mineflayer-based Minecraft bots. Use when the user mentions Mineflayer, Minecraft bot, bot architecture, bot lifecycle, connection handling, or Minecraft automation. Triggers for phrases like "create a Minecraft bot", "Mineflayer bot", "bot joins server", "Minecraft agent architecture".
---

# Minecraft Bot (Mineflayer)

Design and implement Mineflayer-based Minecraft bots with robust architecture patterns.

## Trigger

- "create a Minecraft bot"
- "Mineflayer bot"
- "bot joins server"
- "Minecraft agent"
- "bot connection handling"
- "bot lifecycle"
- "bot auto-reconnect"

## Architecture Principles

### Separation of Concerns

The bot layer is the RUNTIME layer — it handles deterministic Minecraft actions. The LLM/AI layer handles reasoning and planning. Never mix them.

```
AI Layer (LLM)     → decisions, planning, conversation
         │
         ▼
Bot Runtime Layer   → execution, movement, combat, inventory
         │
         ▼
Mineflayer API      → raw protocol actions
```

### Bot Lifecycle

```
INIT → CONNECT → SPAWN → READY → ACTIVE → DISCONNECT → CLEANUP
                    │        │        │
                    ▼        ▼        ▼
                (error)  (timeout)  (kicked)
                    │        │        │
                    └────────┴────────┘
                             │
                             ▼
                        RECONNECT (exponential backoff)
```

## Core Bot Class Design

```typescript
interface IBotCore {
  // Lifecycle
  connect(options: ConnectOptions): Promise<void>;
  disconnect(): void;
  getState(): BotState;

  // Actions (runtime layer — no LLM here)
  moveTo(position: Vec3): Promise<void>;
  breakBlock(position: Vec3): Promise<void>;
  placeBlock(position: Vec3, blockType: string): Promise<void>;
  attack(target: Entity): Promise<void>;
  collectBlock(position: Vec3): Promise<void>;
  useItem(item: Item): Promise<void>;
  interact(entity: Entity): Promise<void>;

  // Events
  on(event: BotEvent, handler: Function): void;
  emit(event: BotEvent, data: any): void;
}

enum BotState {
  INIT = "init",
  CONNECTING = "connecting",
  SPAWNING = "spawning",
  READY = "ready",
  ACTIVE = "active",
  DISCONNECTED = "disconnected",
  ERROR = "error",
}
```

## Connection Manager

- Always use exponential backoff for reconnection (1s, 2s, 4s, 8s, 16s, max 30s)
- Implement heartbeat/ping monitoring
- Handle kick events with reason parsing
- Support both offline and Microsoft authentication
- Never store credentials in code — use env vars or config files

## Event System

The bot must emit structured events upward to the agent layer:

```
minecraft:chat        → { player, message }
minecraft:damage      → { source, amount, type }
minecraft:death       → { reason, position }
minecraft:entity_seen → { entity, position, distance }
minecraft:block_mined → { block, position, tool }
minecraft:player_join → { username }
minecraft:player_leave → { username }
minecraft:error       → { type, message, recoverable }
```

## Safety Rules

- Never allow the LLM to call Mineflayer methods directly
- Always validate positions before movement (within world bounds)
- Implement action timeouts (default 5s, configurable)
- Rate-limit chat messages (max 1 per 500ms)
- Implement anti-spam for movements (cooldown between pathfinding calls)
- Log all actions with timestamps for debugging

## Performance

- Cache block knowledge locally (don't re-query same chunk)
- Use Vec3 pooling to avoid GC pressure
- Batch inventory operations
- Use prismarine-physics for efficient physics calculations
- Keep pathfinding state between movements when possible

## Error Handling

- Distinguish recoverable vs fatal errors
- Recoverable: timeout, chunk not loaded, temporary kick
- Fatal: banned, authentication failure, incompatible version
- Always attempt graceful disconnect before process exit
