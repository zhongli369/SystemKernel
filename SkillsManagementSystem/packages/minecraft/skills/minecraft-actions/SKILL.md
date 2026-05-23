---
name: minecraft-actions
description: Implement Minecraft bot actions — block interaction, inventory management, combat, crafting, building, and tool selection. Use when the user mentions bot actions, block manipulation, bot inventory, bot combat, auto-crafting, or bot building.
---

# Minecraft Bot Actions

Design and implement deterministic action executors for Mineflayer bots. This is the runtime execution layer — the LLM sends structured intents, this layer executes them safely.

## Trigger

- "bot actions"
- "block interaction"
- "inventory management"
- "bot combat"
- "auto-crafting"
- "bot building"
- "tool selection"
- "resource collection"

## Action Execution Architecture

```
Structured Intent (from LLM)
        │
        ▼
Intent Parser (validate + normalize)
        │
        ▼
Action Planner (decompose into primitive actions)
        │
        ▼
Action Executor (run primitives sequentially)
        │
        ▼
Result Reporter (structured result back to LLM)
```

## Intent Schema

```typescript
interface ActionIntent {
  action: ActionType;
  target: ActionTarget;
  parameters?: Record<string, any>;
  priority: number;       // 1-10, higher = more urgent
  timeout?: number;       // ms, default 5000
  cancelable: boolean;    // can be interrupted by higher priority
}

type ActionType =
  | "mine_block"      | "place_block"
  | "attack_entity"   | "use_item"
  | "interact"        | "drop_item"
  | "equip"           | "craft"
  | "collect"         | "eat"
  | "open_container"  | "close_container"
  | "transfer_item"   | "throw"
  | "sleep"           | "respawn";
```

## Inventory Management

### Principles
- Auto-select best tool for the job (pickaxe for stone, axe for wood, sword for combat)
- Maintain organized inventory layout
- Prefer hotbar slots 1-5 for tools, 6-9 for food/utility
- Never discard rare items without confirmation
- Auto-sort after major operations

```typescript
// Tool selection by block type
const TOOL_PREFERENCE: Record<string, string[]> = {
  stone: ["diamond_pickaxe", "iron_pickaxe", "stone_pickaxe", "wooden_pickaxe"],
  wood: ["diamond_axe", "iron_axe", "stone_axe", "wooden_axe"],
  dirt: ["diamond_shovel", "iron_shovel", "stone_shovel", "wooden_shovel"],
  combat: ["diamond_sword", "iron_sword", "stone_sword", "wooden_sword"],
};

function selectBestTool(bot, blockType: string): Item | null {
  // Pick the first available tool from the preference list
  // Also consider efficiency enchantment level
}
```

## Combat System

### Engagement Rules
- Only engage when attack is explicitly requested
- Check equipment durability before engaging
- Maintain safe distance for ranged combat
- Retreat if health < 30%
- Prioritize nearest threat

```typescript
interface CombatConfig {
  maxEngageDistance: number;    // 16 blocks
  retreatHealthPercent: number; // 30
  shieldBlockChance: number;    // 0.8 (80% chance to block)
  usePotions: boolean;          // auto-use health potions
  strafeEnabled: boolean;       // side-to-side movement
  critJumpEnabled: boolean;     // jump for critical hits
}
```

### Entity Danger Levels

```
HOSTILE:       zombie, skeleton, creeper, spider, enderman, witch, pillager, ...
NEUTRAL:       enderman (unless stared), wolf (unless attacked), iron_golem
BOSS:          wither, ender_dragon, elder_guardian
AVOID:         creeper (charged), warden (always flee)
```

## Block Interaction

### Mining Sequence
1. Validate block exists and is mineable
2. Select best tool (or warn if missing)
3. Navigate within range (if needed)
4. Begin mining with progress tracking
5. Handle interruption (mob attack, block broken by another)
6. Collect drops automatically
7. Report result

### Placement Rules
- Never place blocks that would suffocate the bot
- Never place blocks that trap other players
- Check block support requirements
- Validate placement against physics (can it exist there?)

### Common Placements
```
Pillar up:   Jump + place block under → repeat
Bridge:      Sneak to edge → place block ahead → move forward → repeat
Scaffold:    Place temporary blocks for height → remove after use
Tower:       Same as pillar with optional staircase down
```

## Crafting

```typescript
interface CraftRequest {
  item: string;              // Item name (minecraft:iron_pickaxe)
  quantity?: number;         // Default 1
  useNearbyCraftingTable: boolean; // Search radius 16 blocks
  sourceMaterials?: string;  // Specific chest to take from
}

// Crafting execution:
// 1. Check if item exists in inventory → skip
// 2. Calculate required materials
// 3. Locate materials (inventory + nearby chests)
// 4. Navigate to crafting table (if needed)
// 5. Execute craft recipe
// 6. Report result + remaining materials
```

## Action Queue

All actions go through a priority queue:
- Priority 1-5: Background tasks (mining, collecting)
- Priority 6-8: Normal tasks (crafting, building)
- Priority 9-10: Emergency (combat, fleeing, eating)

```typescript
class ActionQueue {
  private queue: PriorityQueue<ActionIntent>;

  enqueue(intent: ActionIntent): void;
  cancel(actionId: string): boolean;
  pause(): void;
  resume(): void;
  clear(): void;

  // Higher priority cancels lower priority if cancelable
  private preempt(): void;
}
```

## Safety Guards

### Before Every Action
1. Is the bot alive and spawned?
2. Is the target within the loaded world?
3. Is there enough food/hunger?
4. Is health sufficient for the risk level?
5. Are required tools available and durable?
6. Does the action risk destroying valuable items?

### Action Timeouts
- All actions must have timeouts (default 5s)
- Timeout → clean abort → report failure
- Never leave bot in unknown state

### Anti-Stuck
- Detect repeated action failure (3x same failure)
- Escalate to higher-level planner
- Log diagnostic info for debugging
