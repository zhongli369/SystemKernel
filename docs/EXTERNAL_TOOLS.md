# External Tools

SystemKernel uses a small set of external tools for developer convenience.
These tools are **outside the kernel boundary** and are never imported as
dependencies. They run as standalone CLI processes and produce output files
that read-only adapters can consume.

## Available External Tools

### Repomix — Context Pack Generator

Generates a packed representation of a directory for AI context.

```
# Plan a context pack (no execution)
python v3/cli/systemkernel.py context-pack plan v3/intake --output trial.md

# Inspect an existing context pack
python v3/cli/systemkernel.py context-pack inspect external_trials/repomix/intake_context.md

# Generate a context pack (requires explicit --allow-execute flag)
python v3/cli/systemkernel.py context-pack generate v3/intake --output trial.md --allow-execute
```

The generate command requires `--allow-execute` because it shells out to
`npx repomix`, which may require network access on first run.

Adapter: `v3/external/context_pack.py`

### ccusage — Claude Code Usage Reporter

Reads Claude Code usage/cost data from ccusage JSON output.

```
# Inspect ccusage JSON output
python v3/cli/systemkernel.py usage inspect external_trials/ccusage/daily.json

# Write normalized usage summary
python v3/cli/systemkernel.py usage summarize external_trials/ccusage/daily.json --output summary.json
```

Neither command runs ccusage itself. You must run ccusage separately:
```
npx ccusage@latest daily --json > external_trials/ccusage/daily.json
```

Adapter: `v3/external/usage_report.py`

## What NOT to Do

- Do NOT import these tools as Python dependencies
- Do NOT run external tool commands in test suites
- Do NOT require network access in tests
- Do NOT treat external tool output as a source of truth
- Do NOT place external tool adapters in `v3/kernel/`

## Why Tools Stay Outside the Kernel

The SystemKernel is a deterministic execution kernel. External tools:

1. May require network access (npx install on first run)
2. May produce non-deterministic output (versions change)
3. May require Node.js/npm/bun runtime
4. Are not part of the kernel's fixed pipeline

The adapters (`v3/external/`) provide safe read-only access to tool output
without breaking kernel invariants.

### Key invariant

All external adapter output has `truth_source: false`. The kernel never
consumes external tool output. External adapters consume tool output and
produce developer-facing reports only.

## Future Deferred Work

| Item | Reason Deferred |
|------|----------------|
| Anthropic Skills format alignment | Skills are format references, not CLI tools. Separate phase needed. |
| Repomix optional execution policy | Current --allow-execute flag is sufficient. Formal policy may be added later. |
| ccusage dashboard/reporting | Current adapter provides summary. Visualization/reporting is out of scope. |
| Doubao TTS | **Unrelated to Phase 7.** This is a separate feature for a different project context. No TTS work was performed in Phase 7. |
