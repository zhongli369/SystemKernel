---
name: agent-architecture
description: Design AI agent system architecture with separation of planning and execution. Use when discussing agent design, AI agent architecture, multi-agent systems, agent runtime, or agent orchestration. Triggers for "agent architecture", "AI agent design", "agent system", "multi-agent".
---

# Agent Architecture

Design production-grade AI agent systems with clean separation between the reasoning layer (LLM) and the execution layer (runtime).

## Trigger

- "agent architecture"
- "AI agent design"
- "agent system"
- "multi-agent"
- "agent runtime"
- "agent orchestration"
- "planning vs execution"

## Core Principle: Planning-Execution Separation

The LLM must NEVER directly control real-time actions. It produces structured intents; the runtime layer executes them safely.

```
┌─────────────────────────────────────────┐
│            REASONING LAYER               │
│  ┌─────────┐  ┌────────┐  ┌──────────┐  │
│  │ Planner │  │ Memory  │  │Personality│  │
│  │ (LLM)   │  │ System  │  │ System   │  │
│  └────┬────┘  └────────┘  └──────────┘  │
│       │                                  │
│       │ Structured Intent (JSON Schema)  │
└───────┼──────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│            EXECUTION LAYER               │
│  ┌──────────┐  ┌────────┐  ┌─────────┐  │
│  │ Action   │  │ Safety │  │ Event   │  │
│  │ Executor │  │ Guard  │  │ Bus     │  │
│  └────┬─────┘  └────────┘  └─────────┘  │
│       │                                  │
│       │ Mineflayer API Calls             │
└───────┼──────────────────────────────────┘
        │
        ▼
   Minecraft Server
```

## Agent Layers

### Layer 1: Perception (Input)
- Game state events (position, health, inventory, nearby entities)
- Chat messages from other players
- Voice input (if voice pipeline active)
- System events (time, weather, damage, death)

### Layer 2: Context Assembly
- Gather relevant memories (recent events, player relationships)
- Current task state and progress
- Environmental context (biome, time of day, nearby threats)
- Recent conversation history (last 10-20 messages)

### Layer 3: Reasoning (LLM Call)
- Structured prompt with context injection
- Streaming output for low latency
- Produces: plan updates, speech text, action intents
- JSON schema enforced output

### Layer 4: Output Processing
- Parse LLM output into structured actions
- Validate against safety rules
- Route to appropriate executor (speech → TTS, action → runtime, memory → storage)

## Intent Schema Design

```typescript
interface AgentOutput {
  // What the agent wants to say (if anything)
  speech?: {
    text: string;
    tone: "friendly" | "urgent" | "calm" | "excited" | "concerned";
    target?: string; // player name, or "everyone"
  };

  // What the agent wants to do
  actions: ActionIntent[];

  // Internal state updates
  internal?: {
    mood_update?: string;
    memory_save?: MemoryEntry;
    task_update?: TaskStateChange;
  };
}

interface ActionIntent {
  id: string;
  type: ActionType;
  target: Target;
  priority: number;
  reason: string; // WHY the agent wants to do this (for debugging)
}
```

## Context Window Management

The LLM context is expensive and limited. Be strategic:

```
Priority 1: System prompt + personality     (~500 tokens, fixed)
Priority 2: Current game state              (~200 tokens, dynamic)
Priority 3: Active task + goal              (~200 tokens, dynamic)
Priority 4: Recent events (last 2 min)      (~500 tokens, sliding window)
Priority 5: Recent conversation (last 10)   (~500 tokens, sliding window)
Priority 6: Relevant memories (top 3-5)     (~300 tokens, retrieved)
Priority 7: Available tools reference       (~300 tokens, fixed)
────────────────────────────────────────────
TOTAL:                                      (~2500 tokens base + response)
```

## Event-Driven Runtime

The agent should be event-driven, not polling:

```typescript
class AgentRuntime {
  private eventBus: EventBus;

  // Events from Minecraft
  onGameEvent(event: GameEvent): void {
    // Route to appropriate handler
    // Batch low-priority events
    // Wake LLM for high-priority events
  }

  // Threshold-based LLM invocation
  private shouldWakeLLM(event: GameEvent): boolean {
    // Always wake for: chat messages, damage, death, player join/leave
    // Wake if: enough events accumulated, or high importance score
    // Don't wake for: routine block updates, ambient sounds
  }

  // Periodic self-reflection (every 30-60s)
  private async selfReflect(): Promise<void> {
    // Agent checks: "Am I doing what I should be doing?"
    // Can trigger task reprioritization
  }
}
```

## Multi-Agent Extension Points

Design for future multi-agent support:

```typescript
interface AgentIdentity {
  id: string;
  name: string;
  role: "companion" | "builder" | "explorer" | "guard" | "worker";
  personality: PersonalityProfile;
}

interface AgentMessage {
  from: string;      // Agent ID
  to: string;        // Agent ID or "broadcast"
  type: "task_assign" | "status_report" | "help_request" | "coordination";
  payload: any;
  timestamp: number;
}
```

## Safety Architecture

```typescript
class SafetyGuard {
  // Pre-execution checks
  validateIntent(intent: ActionIntent): ValidationResult;

  // Rate limiting
  checkRateLimit(actionType: ActionType): boolean;

  // Resource protection
  checkInventorySafety(action: ActionIntent): boolean;

  // World safety
  checkWorldSafety(action: ActionIntent): boolean;

  // Social safety
  checkChatSafety(message: string): boolean;
}
```
