# Workspace Context Plane

**Version:** 1.0.0 | **Phase:** 7 | **Date:** 2026-05-27
**Status:** Active | **Enforcement:** `v3/external/workspace_context.py`

---

## Purpose

The Workspace Context Plane defines contracts for external IDE/workspace
context providers (Continue.dev, Cline, Roo Code, VS Code) WITHOUT
integrating them. Workspace providers supply context evidence only —
read-only snapshots, diagnostics summaries, open-file metadata, and git
state summaries.

They do NOT control execution, mutate kernel truth, write files, or
execute terminal commands.

---

## Workspace Plane vs. IDE Agent

| Aspect | Workspace Plane | IDE Agent |
|--------|----------------|-----------|
| Reads files | Metadata only | Yes |
| Writes files | No | Yes |
| Executes terminal | No | Yes |
| Watches files | No | Yes |
| Uses IDE API | No | Yes |
| Source of truth | Never | Treated as truth |
| Mutates kernel | No | Would contaminate |

The Workspace Plane is a context boundary, not an agent integration.

---

## Why Continue/Cline/Roo Are External Providers

All three require capabilities that the kernel forbids:

| Provider | IDE API | File Watch | File Write | Terminal | External Svc |
|----------|---------|------------|------------|----------|-------------|
| Continue.dev | Yes | No | Yes | No | Yes |
| Cline | Yes | No | Yes | Yes | Yes |
| Roo Code | Yes | No | Yes | Yes | Yes |
| VS Code | Yes | Yes | Yes | Yes | No |
| **Deterministic Mock** | **No** | **No** | **No** | **No** | **No** |

Under the default policy, all real workspace providers are blocked. Only
the deterministic mock provider is allowed for testing the plane contracts.

---

## Why Snapshots Are Evidence Only

Workspace snapshots contain:

- `file_refs` — paths, languages, sizes, content hashes (NO file content)
- `diagnostics` — severity, source, message summaries (NO full diagnostic output)
- `git_state` — branch, HEAD, counts (NO diffs, NO file contents)
- `open_files` — file paths only
- `active_file` — single file path

They do NOT:
- Store file contents
- Execute terminal commands
- Write to the filesystem
- Watch for file changes
- Become source of truth

---

## Default Policy

The `default_workspace_context_policy()` is maximally conservative:

| Rule | Value |
|------|-------|
| Allow IDE API | False |
| Allow file watch | False |
| Allow file read | True (metadata only) |
| Allow file write | False |
| Allow terminal execution | False |
| Allow external services | False |
| Max files | 100 |
| Max diagnostics | 200 |
| Max open files | 20 |
| Require redaction | True |
| Require human approval | True |

Only `deterministic_mock_workspace` passes by default.

---

## How Future Workspace Provider Trials Can Be Approved

1. Define a provider profile (Phase 7 contract)
2. Default policy blocks it
3. Create a trial-specific policy:
   ```python
   trial_policy = WorkspaceContextPolicy(
       allow_ide_api=True,                # Specific justification
       allow_file_read=True,              # Metadata only
       allow_file_write=False,            # Non-negotiable
       allow_terminal_execution=False,    # Non-negotiable
       require_redaction=True,            # Non-negotiable
       require_human_approval=True,       # Non-negotiable
       max_files=50,
   )
   ```
4. Validate provider against trial policy
5. Take snapshots in read-only mode
6. Map snapshots to evidence (never truth)
7. Human reviews before any action

---

## CLI Usage

```bash
# List all workspace provider profiles and policy status
python v3/cli/systemkernel.py workspace profiles

# Generate deterministic mock workspace snapshot
python v3/cli/systemkernel.py workspace mock --files 5 --diagnostics 3

# Build evidence bundle from mock snapshot
python v3/cli/systemkernel.py workspace evidence
```

---

## Anti-Overengineering

- No IDE client implemented
- No file watcher implemented
- No editor integration
- No terminal control
- No file content storage — metadata and hashes only
- Phase 1 contract, Phase 3 evidence model reused
- `truth_source` always `False`
- `require_human_approval` always `True` by default

---

*SystemKernel v4.0 Phase 7 — Workspace Context Plane*
