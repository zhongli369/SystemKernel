# ccusage Manual Trial Report

**Date:** 2026-05-26
**Phase:** 7D — ccusage Manual Trial
**Status:** COMPLETE

---

## Trial Command

```
npx ccusage@latest daily --json
```

**Note:** `HTTP_PROXY`/`HTTPS_PROXY` were temporarily unset (non-running proxy at `127.0.0.1:7890`). ccusage v20.0.5 was downloaded and executed via npx — no manual install, no global install, no modification to the local `F:\Claude\Github\ccusage` clone.

## Environment / Tool Availability

| Tool | Available | Version |
|------|-----------|---------|
| node | YES | v24.15.0 |
| npm | YES | 11.12.1 |
| npx | YES | 11.12.1 |
| bun | NO | Not installed |

## Output

| Field | Value |
|-------|-------|
| Path | `external_trials/ccusage/daily.json` |
| Size | 11,507 bytes (~11 KB) |
| Valid JSON | YES |
| Daily records | 10 |
| Date range | 2026-05-13 to 2026-05-26 |
| Agent sources detected | claude, codex, openclaw |

## Schema Summary

### Top-level structure
```json
{
  "daily": [ ... ],
  "totals": { ... }
}
```

### Per-record fields
| Field | Type | Description |
|-------|------|-------------|
| agent | string | "all" (aggregated across detected sources) |
| cacheCreationTokens | number | Tokens from cache creation |
| cacheReadTokens | number | Tokens read from cache |
| inputTokens | number | Input/prompt tokens |
| outputTokens | number | Output/completion tokens |
| totalTokens | number | Sum of all tokens |
| totalCost | number | Cost in USD |
| period | string | Date (YYYY-MM-DD) |
| metadata | object | `{ agents: [...detected_sources] }` |
| modelBreakdowns | array | Per-model token and cost breakdown |
| modelsUsed | array | Model names used that day |

### Model breakdown per day
| Field | Type | Description |
|-------|------|-------------|
| modelName | string | Model identifier (e.g. "deepseek-v4-pro") |
| inputTokens | number | Input tokens for this model |
| outputTokens | number | Output tokens for this model |
| cacheCreationTokens | number | Cache creation tokens |
| cacheReadTokens | number | Cache read tokens |
| cost | number | Cost in USD for this model |

### Totals structure
| Field | Value |
|-------|-------|
| totalTokens | 648,907,149 |
| inputTokens | 14,746,103 |
| outputTokens | 4,248,854 |
| cacheReadTokens | 629,912,192 |
| totalCost | $24.19 |

## Detected Data Sources

ccusage detected usage data from:
- **claude** — Claude Code (primary source, deepseek-v4-pro, deepseek-v4-flash)
- **codex** — Codex (using gpt-5.5)
- **openclaw** — OpenClaw (using deepseek-chat)

Models observed: deepseek-v4-pro, deepseek-v4-flash, gpt-5.5, [openclaw] deepseek-chat

## Sensitive Content Assessment

| Check | Result |
|-------|--------|
| API keys / secrets | NONE detected |
| Prompt text | NONE (aggregate token counts only) |
| Conversation content | NONE |
| File paths | NONE |
| Personal data | NONE |

The "token" keyword hit in the schema scan is a false positive — field names
like `inputTokens`, `cacheReadTokens` are schema metadata, not sensitive content.

## Usefulness Assessment

| Criterion | Rating | Notes |
|-----------|--------|-------|
| JSON validity | GOOD | Clean structured output |
| Schema consistency | GOOD | Predictable field names |
| Date range coverage | GOOD | 10 days of data detected |
| Multi-agent detection | GOOD | Found claude + codex + openclaw |
| Model-level detail | GOOD | Per-model breakdowns with costs |
| Sensitive data risk | LOW | Aggregate numbers only, no prompts |
| Offline support | GOOD | `--offline` flag available |
| Token metrics | GOOD | Input, output, cache create, cache read all separate |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Coupling to Claude Code JSONL format | MEDIUM | Upstream format changes could break ccusage |
| npx network dependency | LOW | Version pinned; `--offline` works after first fetch |
| Cost tracking accuracy | LOW | Uses LiteLLM pricing; may lag model launches |
| Multi-agent data path assumptions | MEDIUM | Must know where each agent stores its data |
| No MCP server interface | LOW | CLI + JSON output is sufficient for external consumption |
| Rust binary dependency | MEDIUM | ccusage uses native Rust binaries; platform-specific |

## Recommendation

**Proceed to external usage adapter design: YES**

ccusage provides clean, structured JSON output with token and cost metrics
that could complement SystemKernel observability. The data is aggregate-only
(no prompt text), making it safe for report consumption.

A future "ccusage adapter" could:
- Shell out to `npx ccusage daily --json`
- Parse the JSON and extract totals
- Map to kernel metric types (execution tokens, cost, model breakdown)
- Generate a complementing usage report under v3/exports/
- Remain strictly external — never imported as a Python module

**Integration performed: NO**

No SystemKernel integration was performed. ccusage was called as an external
CLI tool with no code changes to any kernel module.

---

*ccusage Manual Trial Report — Phase 7D — 2026-05-26*
