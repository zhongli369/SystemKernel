# Usage Report Adapter Architecture — Phase 7E

## Overview

The Usage Report Adapter (`v3/external/usage_report.py`) is a **read-only, zero-dependency wrapper** that consumes pre-generated JSON output from the external `ccusage` CLI tool. It is NOT a kernel module, NOT a runtime feature, and ccusage remains an external tool.

## Design Principles

### ccusage Remains External

`ccusage` is an npm package executed manually or via scheduled task. The adapter never invokes it. The adapter only parses JSON files that have already been written to disk.

### Adapter Consumes JSON Only

The adapter reads ccusage JSON from a file path. It does not:
- Import the ccusage npm package
- Execute `npx ccusage` or any subprocess
- Require network access
- Use bun, npm, or any JS runtime

### Usage Report Is NOT a Truth Source

Every `UsageReportSummary` has `truth_source: false`. This is enforced:
- In the dataclass default
- In `verify_summary()` which rejects any summary with `truth_source=True`
- In all generated reports

### Relationship to SystemKernel Metrics

| Aspect | ccusage Adapter | SystemKernel Observability |
|--------|----------------|---------------------------|
| Source | External npm tool | Internal kernel hooks |
| Scope | Claude Code usage/cost | Kernel routing + execution |
| Dependency | None (JSON file input) | None (removable) |
| Truth authority | None (always false) | Trace/Metric records |
| Purpose | Dev tool for cost awareness | Kernel observability |

The adapter output is complementary to, but entirely independent of, kernel Observability metrics. The kernel does not consume ccusage data and ccusage data does not influence kernel behavior.

## Architecture

```
External World (manual or cron)
  npx ccusage@latest daily --json
       │
       ▼
  external_trials/ccusage/daily.json   ← Static JSON file
       │
       ▼
  v3/external/usage_report.py          ← Read-only adapter
       │
       ├── parse_ccusage_json()        → tuple[UsageDayRecord, ...]
       ├── summarize()                 → UsageReportSummary
       ├── write_summary()             → JSON report on disk
       └── verify_summary()            → bool (invariants check)
       │
       ▼
  v3/cli/systemkernel.py               ← Developer CLI
       │
       ├── usage inspect <path>        → Print summary
       └── usage summarize <path>      → Write normalized JSON
```

## Data Types

### UsageDayRecord (frozen)
- date, total_tokens, input_tokens, output_tokens
- cache_creation_tokens, cache_read_tokens
- cost_usd, models (tuple), agents (tuple)

### UsageReportSummary (frozen)
- source_tool, record_count, total_tokens, total_cost_usd
- cache_read_ratio, model_count, agent_count
- date_start, date_end, sensitive_text_detected
- report_hash, truth_source (always False), warnings

### UsageReportConfig (frozen)
- input_path, source_tool, redaction_enabled
- max_records, include_model_breakdown, include_agent_breakdown
- dry_run

## Safety Constraints

1. Standard library only — zero external Python dependencies
2. Deterministic ordering — records sorted by date, models/agents sorted alphabetically
3. truth_source always False — enforced by verification
4. No external command execution — no subprocess, no os.system
5. No ccusage import — verified by test suite
6. Graceful handling of missing optional fields — warnings collected, no crashes
7. Report hash — deterministic SHA-256 for comparison across runs

## Test Coverage

32 tests covering:
- Fixture parsing and record creation
- Token/cost aggregation
- Cache read ratio computation
- Model and agent counting
- Date range ordering
- Missing optional field handling
- Sensitive text detection (always false for ccusage output)
- Deterministic report hashing
- truth_source enforcement
- write_summary output validation
- verify_summary boundary cases (truth_source=True, bad ratios, negative cost)
- CLI inspect and summarize commands
- No ccusage import, no network imports, no subprocess calls
- No v3/kernel modifications
- Complexity gate not REJECT
- Developer CLI tests regression pass
- Kernel invariants purity=100
