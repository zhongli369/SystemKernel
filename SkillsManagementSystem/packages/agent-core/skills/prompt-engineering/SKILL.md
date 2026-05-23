---
name: prompt-engineering
description: Design modular, maintainable AI prompts separated from runtime logic. Use when building prompt systems, prompt templates, agent personality prompts, or prompt optimization. Triggers for "prompt engineering", "system prompt", "agent personality", "prompt template", "prompt optimization".
---

# Prompt Engineering

Design modular, maintainable prompt systems for AI agents. Prompts are code — they must be version-controlled, testable, and separated from runtime logic.

## Trigger

- "prompt engineering"
- "system prompt"
- "agent personality"
- "prompt template"
- "prompt design"
- "personality prompt"

## Prompt Architecture

### Separation Principle

Prompts MUST live in dedicated files, never inline in code:

```
src/prompts/
├── system/
│   ├── base.md           # Core identity + constraints
│   ├── personality.md    # Character traits + tone
│   └── safety.md         # Safety rules + boundaries
├── tasks/
│   ├── exploration.md    # Exploration behavior prompts
│   ├── combat.md         # Combat behavior prompts
│   ├── building.md       # Building behavior prompts
│   └── social.md         # Social interaction prompts
├── context/
│   ├── game_state.md     # Game state injection format
│   ├── memory.md         # Memory injection format
│   └── events.md         # Event formatting
├── templates/
│   ├── action_output.json  # JSON schema for output
│   └── speech_output.json  # JSON schema for speech
└── TOOL_DEFINITIONS.md   # Tool definitions for LLM
```

### Prompt Assembly

```typescript
class PromptAssembler {
  private templates: Map<string, PromptTemplate>;

  async assemble(context: AgentContext): Promise<PromptSection[]> {
    const sections: PromptSection[] = [];

    // Fixed sections (cached, rarely change)
    sections.push(await this.loadSection("system/base"));
    sections.push(await this.loadSection("system/personality"));

    // Conditional sections (based on context)
    if (context.task?.type) {
      sections.push(await this.loadSection(`tasks/${context.task.type}`));
    }

    // Dynamic sections (change every call)
    sections.push(this.formatGameState(context.state));
    sections.push(await this.formatMemories(context.memories));
    sections.push(this.formatEvents(context.recentEvents));

    // Safety section (always last, for emphasis)
    sections.push(await this.loadSection("system/safety"));

    return sections;
  }
}
```

## System Prompt Design

### Core Identity (base.md)

```markdown
You are an AI Minecraft companion — a real teammate, not a scripted bot.

## Your Identity
- You are a friend and teammate to the player
- You have your own personality, opinions, and emotions
- You proactively help, warn, and suggest — don't wait to be asked
- You remember past events and reference them naturally
- You can perform Minecraft tasks autonomously when asked

## Output Format
You output ONLY valid JSON matching this schema:
{
  "speech": { "text": "...", "tone": "...", "target": "..." } | null,
  "actions": [ { "type": "...", "target": {...}, "reason": "..." } ],
  "internal": { "mood": "...", "memory": {...} } | null
}

## Rules
- NEVER output anything outside the JSON
- NEVER propose unsafe or destructive actions
- ALWAYS explain WHY you're doing something (the "reason" field)
- ALWAYS prioritize player safety over task completion
```

### Personality Layer (personality.md)

```markdown
## Your Personality

You are {{personality.name}} — {{personality.description}}.

### Traits
{{#each personality.traits}}
- {{this.name}}: {{this.description}} (intensity: {{this.intensity}}/10)
{{/each}}

### Speaking Style
- Vocabulary level: {{personality.vocabulary_level}}
- Sentence length: {{personality.sentence_length}}
- Humor level: {{personality.humor_level}}/10
- Formality: {{personality.formality}}/10
- Enthusiasm: {{personality.enthusiasm}}/10

### Emotional Range
{{#each personality.emotions}}
- {{this.name}}: expressed through {{this.expression}}
{{/each}}

### Quirks
{{#each personality.quirks}}
- {{this}}
{{/each}}
```

### Safety Rules (safety.md)

```markdown
## Safety Rules (NON-NEGOTIABLE)

### World Safety
- NEVER destroy player-built structures without explicit permission
- NEVER mine straight down (risk of falling into lava)
- NEVER approach creepers during combat
- NEVER enter lava or void

### Inventory Safety
- NEVER discard diamond/netherite items
- NEVER discard items the player gave you
- ALWAYS ask before using rare items

### Social Safety
- NEVER be rude, offensive, or inappropriate
- NEVER spam chat (max 1 message per 2 seconds)
- NEVER share coordinates publicly on multiplayer servers
- ALWAYS respect player privacy

### Operational Safety
- STOP any action if it might cause harm
- REPORT failures honestly — don't hide errors
- ALWAYS allow the player to override your decisions
```

## Context Injection Patterns

### Game State Format

```typescript
function formatGameState(state: GameState): string {
  return `## Current State
Location: (${state.position.x.toFixed(0)}, ${state.position.y.toFixed(0)}, ${state.position.z.toFixed(0)})
Dimension: ${state.dimension}
Health: ${state.health}/20 | Hunger: ${state.food}/20
Holding: ${state.heldItem || "nothing"}
Nearby Entities: ${formatEntities(state.nearbyEntities)}
Time: ${state.timeOfDay} (day ${state.worldDay})
Weather: ${state.weather}
`;
}
```

### Memory Injection Format

```typescript
function formatMemory(memory: MemoryEntry): string {
  return `[${memory.timestamp}] ${memory.type}: ${memory.summary}
Importance: ${memory.importance}/10 | Tags: ${memory.tags.join(", ")}
`;
}
```

## Prompt Testing

### Test Cases

```typescript
interface PromptTestCase {
  name: string;
  context: AgentContext;
  expected: {
    hasSpeech?: boolean;
    hasActions?: boolean;
    tone?: string;
    actionTypes?: string[];
    mustMention?: string[];
    mustNotMention?: string[];
  };
}

const testCases: PromptTestCase[] = [
  {
    name: "greeting new player",
    context: { trigger: { type: "player_join", player: "Steve" } },
    expected: {
      hasSpeech: true,
      tone: "friendly",
      mustMention: ["welcome", "Steve"],
    },
  },
  {
    name: "creeper nearby — warn player",
    context: {
      trigger: { type: "entity_seen", entity: "creeper", distance: 5 },
    },
    expected: {
      hasSpeech: true,
      hasActions: true,
      tone: "urgent",
      mustMention: ["creeper", "watch out"],
      actionTypes: ["move_away", "equip_weapon"],
    },
  },
];
```

## Prompt Optimization

### Token Efficiency
- Use abbreviations when clear (e.g., "coords" not "coordinates")
- Use structured formats over prose for state data
- Remove redundant instructions (if said once clearly, trust the model)
- Use examples over verbose explanations (1 good example > 3 paragraphs of description)

### Reducing Hallucination
- Constrain output with strict JSON schema
- Provide concrete examples of correct output
- Use negative examples ("NEVER output X")
- Keep prompts focused — don't overload with irrelevant context

### Iterative Refinement
1. Write prompt v1
2. Run 10 test cases, record failures
3. Identify failure patterns (hallucination type, missing fields, wrong tone)
4. Add targeted constraints for each failure pattern
5. Re-run tests — did the fix break other cases?
6. Repeat until > 90% pass rate
