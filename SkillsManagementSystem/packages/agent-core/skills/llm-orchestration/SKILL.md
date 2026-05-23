---
name: llm-orchestration
description: Design structured LLM orchestration with tool calling, JSON schema enforcement, streaming output, and model-specific optimization for DeepSeek V4 and Claude. Use when discussing LLM integration, tool calling patterns, structured output, or model optimization for AI agents.
---

# LLM Orchestration

Orchestrate LLM calls with structured output, tool calling, and streaming for real-time AI agents. Primary model: DeepSeek V4. Personality layer optional: Claude API.

## Trigger

- "LLM orchestration"
- "tool calling"
- "structured output"
- "DeepSeek integration"
- "streaming LLM"
- "JSON schema"
- "function calling"

## Model-Specific Configuration

### DeepSeek V4 (Primary — Reasoning + Action)

```typescript
const deepseekConfig = {
  model: "deepseek-chat",  // or "deepseek-reasoner" for complex planning
  max_tokens: 2048,
  temperature: 0.7,
  stream: true,            // ALWAYS stream for low latency
  response_format: { type: "json_object" },  // Structured output

  // System prompt for Minecraft agent
  system: `You are an AI Minecraft companion. You control actions through structured JSON output.
You must ONLY output valid JSON matching the schema. No other text.`,

  // Tools definition (for tool-calling capable models)
  tools: minecraftToolDefinitions,
  tool_choice: "auto",
};
```

### Claude API (Optional — Personality + Complex Reasoning)

```typescript
const claudeConfig = {
  model: "claude-sonnet-4-6",
  max_tokens: 2048,
  temperature: 0.7,
  stream: true,

  // Claude-specific: extended thinking for complex planning
  thinking: {
    type: "enabled",
    budget_tokens: 1000,   // Only for complex planning tasks
  },

  // Tools available
  tools: minecraftToolDefinitions,
};
```

## Streaming Output Handler

```typescript
class StreamingLLMHandler {
  private buffer: string = "";
  private parser: JSONStreamParser;

  constructor() {
    this.parser = new JSONStreamParser();
  }

  // Called for each streaming chunk
  onChunk(chunk: string): void {
    this.buffer += chunk;
    const results = this.parser.feed(chunk);

    for (const result of results) {
      if (result.type === "partial") {
        // Partial parse — emit early for low latency
        this.handlePartial(result.data);
      } else if (result.type === "complete") {
        // Full parse — validate against schema
        this.handleComplete(result.data);
      }
    }
  }

  private handlePartial(data: Partial<AgentOutput>): void {
    // If speech text is available, start TTS immediately
    if (data.speech?.text) {
      this.emit("speech_token", data.speech.text);
    }
    // If action is ready, start execution
    if (data.actions?.length) {
      this.emit("actions_ready", data.actions);
    }
  }
}
```

## JSON Streaming Parser

Parse JSON from LLM streaming output incrementally:

```typescript
class JSONStreamParser {
  private buffer: string = "";
  private depth: number = 0;
  private inString: boolean = false;

  feed(chunk: string): ParseResult[] {
    const results: ParseResult[] = [];
    this.buffer += chunk;

    // Try parsing at natural boundaries
    const boundaries = this.findBoundaries();
    for (const boundary of boundaries) {
      const slice = this.buffer.slice(0, boundary);
      try {
        const parsed = JSON.parse(slice);
        results.push({ type: "complete", data: parsed });
        this.buffer = this.buffer.slice(boundary);
      } catch {
        // Incomplete JSON, wait for more
      }
    }
    return results;
  }
}
```

## Tool Calling Architecture

### Tool Definition

```typescript
interface ToolDefinition {
  name: string;
  description: string;    // When should the LLM use this tool?
  parameters: JSONSchema; // Strict schema for arguments
}

const minecraftTools: ToolDefinition[] = [
  {
    name: "move_to",
    description: "Move the bot to a specific location. Use for navigation.",
    parameters: {
      type: "object",
      properties: {
        x: { type: "number" },
        y: { type: "number" },
        z: { type: "number" },
        reason: { type: "string", description: "Why are you moving here?" },
      },
      required: ["x", "y", "z"],
    },
  },
  {
    name: "mine_block",
    description: "Mine/break a block at the given position.",
    parameters: {
      type: "object",
      properties: {
        x: { type: "number" },
        y: { type: "number" },
        z: { type: "number" },
        tool: { type: "string", description: "Preferred tool (optional)" },
      },
      required: ["x", "y", "z"],
    },
  },
  {
    name: "speak",
    description: "Say something in chat or to a specific player.",
    parameters: {
      type: "object",
      properties: {
        text: { type: "string", maxLength: 200 },
        target: { type: "string", description: "Player name or 'everyone'" },
        tone: { enum: ["friendly", "urgent", "calm", "excited", "concerned"] },
      },
      required: ["text"],
    },
  },
  // ... more tool definitions
];
```

### Tool Execution Loop

```typescript
async function toolCallingLoop(
  llm: LLMClient,
  context: AgentContext
): Promise<void> {
  let turn = 0;
  const MAX_TURNS = 3; // Max tool call rounds per LLM invocation

  while (turn < MAX_TURNS) {
    const response = await llm.chat({
      messages: context.messages,
      tools: minecraftTools,
      stream: true,
    });

    if (response.content) {
      // LLM wants to speak
      handleSpeech(response.content);
    }

    if (response.tool_calls?.length) {
      // Execute tools in parallel if independent
      const results = await executeToolCalls(response.tool_calls);
      // Feed results back for next turn
      context.messages.push({
        role: "tool",
        content: JSON.stringify(results),
      });
    } else {
      break; // No more tool calls, LLM is done
    }
    turn++;
  }
}
```

## Prompt Assembly Pipeline

```typescript
async function assemblePrompt(
  context: AgentContext
): Promise<ChatMessage[]> {
  return [
    // Layer 1: System prompt (fixed)
    { role: "system", content: SYSTEM_PROMPT },

    // Layer 2: Current state (dynamic, compact)
    { role: "system", content: formatGameState(context.state) },

    // Layer 3: Active task
    { role: "system", content: formatActiveTask(context.task) },

    // Layer 4: Recent events (sliding window)
    ...formatRecentEvents(context.events, maxTokens: 500),

    // Layer 5: Relevant memories (top-k retrieval)
    ...await formatMemories(context.memories, topK: 5),

    // Layer 6: Conversation history
    ...context.conversation.slice(-10),

    // Layer 7: Current trigger event
    { role: "user", content: formatTrigger(context.trigger) },
  ];
}
```

## Model Fallback Strategy

```
Primary:   DeepSeek V4 (fast, cheap)
          │
          ▼ (fallback on timeout or error)
Secondary: DeepSeek V4 retry (1 attempt)
          │
          ▼ (fallback on repeated failure)
Emergency: Claude Haiku 4.5 (fast, reliable, more expensive)
```

## Performance Optimization

- **Prompt caching**: Cache system prompt and tool definitions (they don't change)
- **Context pruning**: Remove old events beyond retention window
- **Token budget**: Hard cap at 4000 tokens input, 2048 tokens output
- **Batching**: Batch non-urgent LLM calls (e.g., self-reflection)
- **Pre-compute**: Maintain pre-formatted state strings, update incrementally

## Error Recovery

- LLM timeout (5s): retry once, then fall back
- Invalid JSON output: retry with stricter prompt, then fall back to free-text
- Tool call with invalid args: return error, let LLM correct
- Rate limit hit: exponential backoff (1s, 2s, 4s)
- Empty response: re-prompt with "You must respond with..."

## Latency Budget

```
Prompt assembly:     50ms
LLM API overhead:   100ms
LLM TTFT:           400ms (time to first token)
LLM generation:     600ms (streaming)
Output parsing:      50ms
─────────────────────────
Total LLM latency:  ~1200ms
```
