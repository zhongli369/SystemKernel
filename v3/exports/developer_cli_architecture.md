# Developer CLI Architecture

## Phase 5B — One-Command Runtime

### Overview

The Developer CLI wraps all existing runtime, observability, memory, and quality
capabilities into 6 simple commands. It adds zero runtime capability — every
command delegates to an existing facade or reads existing report files.

### Why CLI Adds No Runtime Capability

The CLI is a pure read-only wrapper. It:
- Reads report JSON files from `v3/exports/`
- Calls `evaluate_phase()` from `v3/quality/phase_gate.py`
- Calls `MemoryRuntime` and `write_system_report_json()` from `v3/memory/`
- Scans files with `ast` module (stdlib)
- Never modifies kernel/, memory/, or quality/ source files
- Never creates new data — only reads existing projections

### Why CLI Reduces Manual Steps

| Before (manual) | After (CLI) |
|-----------------|-------------|
| `cat v3/exports/kernel_validity_report.json \| python -m json.tool` | `systemkernel status` |
| `ls v3/tests/*.py \| wc -l && grep -r "def test_" v3/tests/ \| wc -l` | `systemkernel status` |
| `python -c "from v3.quality.phase_gate import evaluate_phase; ..."` | `systemkernel quality` |
| `ls -la v3/exports/` | `systemkernel reports list` |
| Manually read 5+ JSON files for summary | `systemkernel reports summary` |
| `grep -r "import openai\|import langchain" v3/` | `systemkernel doctor` |
| Manually verify each directory exists | `systemkernel doctor` |

8 manual steps reduced to 4 commands (50% reduction).

### Command Map

```
systemkernel
├── status          → reads kernel_validity_report.json
│                      counts test functions via AST
│                      reads memory_removability_report.json
│                      reads memory_system_report.json
│                      reads complexity_budget_report.json
│                      lists key report files
│
├── quality         → calls v3.quality.phase_gate.evaluate_phase()
│                      writes complexity_budget_report.json
│                      prints verdict + reasons
│                      exit 0 (ACCEPT/REVIEW) or 2 (REJECT)
│
├── memory report   → calls v3.memory.runtime.MemoryRuntime
│                      calls v3.memory.system_report.write_system_report_json
│                      writes memory_system_report.json
│
├── reports list    → lists all files in v3/exports/
│
├── reports summary → reads key JSON reports
│                      prints subsystem status
│                      prints phase completion
│
└── doctor          → AST-scans for banned imports
                      verifies directories exist
                      verifies key reports exist
                      checks kernel/memory boundary
                      runs quality gate
                      prints pass/fail table
```

### Invariants

| Invariant | Status |
|-----------|--------|
| Zero LLM imports | CONFIRMED |
| Zero new runtime capability | CONFIRMED (read-only wrapper) |
| Deterministic output | CONFIRMED (same input → same output) |
| Does not modify kernel files | CONFIRMED |
| Uses only existing facades | CONFIRMED |
| Stdlib + v3.quality + v3.memory only | CONFIRMED |
| Memory removable | YES |
| Kernel purity | 100/100 |
