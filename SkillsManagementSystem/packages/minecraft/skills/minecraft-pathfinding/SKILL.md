---
name: minecraft-pathfinding
description: Implement Minecraft pathfinding, navigation, and movement systems using mineflayer-pathfinder. Use when discussing bot navigation, A* pathfinding, movement optimization, terrain traversal, or autonomous exploration in Minecraft.
---

# Minecraft Pathfinding & Navigation

Design and optimize navigation systems for Minecraft bots using mineflayer-pathfinder and Moves-based pathfinding.

## Trigger

- "bot navigation"
- "minecraft pathfinding"
- "bot movement"
- "A* pathfinding"
- "bot can't reach"
- "navigation stuck"
- "autonomous exploration"
- "waypoint navigation"

## Architecture

### Movement Abstraction Layer

```
High-level Goal ("go to village")
        │
        ▼
Waypoint Planner (decompose into waypoints)
        │
        ▼
Pathfinding Engine (A* with Moves)
        │
        ▼
Movement Executor (step-by-step traversal)
        │
        ▼
Safety Validator (check each step)
```

### Movement Types

```typescript
enum MovementMode {
  WALK = "walk",           // Standard ground movement
  SPRINT = "sprint",       // Fast ground movement (food cost)
  SWIM = "swim",           // Water traversal
  CLIMB = "climb",         // Ladders/vines
  BOAT = "boat",           // Boat navigation
  ELYTRA = "elytra",       // Elytra flight
  PILLAR = "pillar",       // Vertical up (place blocks under)
  DIG_DOWN = "dig_down",   // Vertical down (staircase pattern)
  BRIDGE = "bridge",       // Horizontal across air (place blocks)
}
```

## Pathfinding Configuration

### Moves Configuration

```typescript
import { Movements, goals } from "mineflayer-pathfinder";

const moves = new Movements(bot, mcData);

// Terrain cost multipliers (lower = preferred)
moves.allowParkour = true;
moves.allowSprinting = true;
moves.canDig = true;           // Allow breaking blocks in path
moves.placeCost = 200;         // Cost to place a block
moves.breakCost = 150;         // Cost to break a block
moves.entityCost = 100;        // Cost to go through entities
moves.liquidCost = 3;          // Water/lava traversal cost
moves.scaffoldCost = 180;      // Scaffolding cost

// Danger zones
moves.dontMineUnderFallingBlock = true;
moves.maxDropDown = 4;         // Max fall distance (blocks)
```

### Goal Types

```typescript
goals.GoalBlock(x, y, z)       // Reach exact block
goals.GoalNear(x, y, z, range) // Get within range
goals.GoalXZ(x, z)             // Reach XZ coordinate (any Y)
goals.GoalNearXZ(x, z, range)  // Near XZ coordinate
goals.GoalY(y)                  // Reach Y level
goals.GoalFollow(entity, range) // Follow entity
goals.GoalInvert(goal)          // Move away from goal
goals.GoalCompositeAny(goals)   // Satisfy any goal
goals.GoalCompositeAll(goals)   // Satisfy all goals
```

## Optimization Strategies

### Chunk-Aware Pathfinding
- Pre-load chunks along the path before computing
- Cache chunk data with TTL (30s default)
- Use view distance to determine planning horizon

### Incremental Pathfinding
- Compute full path once, then replan only when blocked
- Store the last N waypoints for reuse
- Detect "stuck" state: no position change for 3s → replan

### Exploration Patterns

```
Spiral:   Start at center, expand outward in spiral
Grid:     Divide area into grid cells, visit each
Frontier: Explore unknown chunks at the edge of known territory
POI:      Navigate between points of interest
```

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Bot vibrates in place | Path oscillating between two blocks | Increase goal tolerance to 1.5 blocks |
| Bot gets stuck on corners | Collision box edge case | Toggle sprint off briefly, retry with slight offset |
| Path through lava | Moves configured dangerously | Set `liquidCost` very high or block lava |
| Cant reach goal | Goal in unreachable location | Use GoalNear instead of GoalBlock |
| Bot digs straight down | `canDig: true` without safety | Check for drops > 3 blocks before digging |
| Path too expensive | No viable path found | Fall back to teleport (if OP) or report failure |

## Safety Validator

Before each movement step, validate:
1. Is the destination block loaded?
2. Is the destination within world border?
3. Will the move cause fall damage (> 3 blocks)?
4. Is there lava/water at the destination?
5. Is there a risk of suffocation?
6. Can the bot fit in the destination (1x2 space)?

## Performance Metrics

- Target: path computation < 100ms for < 100 block distance
- Cache hit rate: > 80% for movement in loaded chunks
- Stuck detection: < 3s to identify and replan
- Replan overhead: reuse 70%+ of previous path
