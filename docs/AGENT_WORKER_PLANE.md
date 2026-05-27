# Agent Worker Plane

**Version:** 1.0.0 | **Phase:** 6 | **Date:** 2026-05-27
**Status:** Active | **Enforcement:** `v3/external/agent_worker.py`

---

## Purpose

The Agent Worker Plane defines contracts for external agent worker
providers (OpenHands, SWE-agent, AutoGen, Continue) WITHOUT integrating
them. Agent workers are external proposal generators — they may propose
plans, patches, or artifacts but cannot mutate kernel truth or execute
automatically.

All proposals are EVIDENCE, never TRUTH. All real workers are
disabled/blocked by default policy.

---

## Why Agent Workers Are External Providers

Agent workers require capabilities that the kernel forbids:

| Provider | LLM | Network | File Mod | Cmd Exec | Sandbox | External Svc |
|----------|-----|---------|----------|----------|---------|-------------|
| OpenHands | Yes | Yes | Yes | Yes | Yes | Yes |
| SWE-agent | Yes | No | Yes | Yes | No | Yes |
| AutoGen | Yes | No | Yes | Yes | No | Yes |
| Continue | Yes | No | Yes | No | No | Yes |
| **Deterministic Mock** | **No** | **No** | **No** | **No** | **No** | **No** |

Under the default policy, all real agent workers are blocked. Only the
deterministic mock provider (no LLM, no network, no file modification,
no command execution) is allowed for testing the plane contracts.

---

## Why Proposals Are Evidence Only

Agent worker proposals (`AgentWorkerProposal`) contain:

- `proposed_plan` — a suggested plan (string only)
- `proposed_files` — suggested file paths (metadata only, not written)
- `proposed_commands` — suggested commands (strings only, not executed)

They do NOT:
- Mutate the filesystem
- Execute commands
- Become source of truth
- Run automatically

All proposals carry `truth_source=False`. Agent workers produce proposals;
humans review them; the kernel remains unchanged.

---

## Default Policy

The `default_agent_worker_policy()` is maximally conservative:

| Rule | Value |
|------|-------|
| Allow LLM providers | False |
| Allow network | False |
| Allow file modification | False |
| Allow command execution | False |
| Allow external services | False |
| Require sandbox | True |
| Require human approval | True |
| Max runtime | 300s |
| Max proposals | 10 |

This means only `deterministic_mock_agent` passes by default. To trial
a real agent worker, each flag must be explicitly enabled with documented
reasoning.

---

## How Future Agent Worker Trials Can Be Approved

1. Define a provider profile (Phase 6 contract)
2. Default policy blocks it
3. Create a trial-specific policy that selectively enables flags:
   ```python
   trial_policy = AgentWorkerPolicy(
       allow_llm_providers=True,           # Specific justification
       require_sandbox=True,               # Non-negotiable
       require_human_approval=True,        # Non-negotiable
       max_runtime_seconds=120,            # Limited blast radius
       max_proposals=5,
   )
   ```
4. Validate provider against trial policy
5. Run task with `dry_run=True` (non-negotiable without human approval)
6. Map results to evidence (never truth)
7. Human reviews proposals before any action

---

## How Agent Worker Proposals May Be Used

The pipeline for human-reviewed agent proposals:

1. External agent worker produces `AgentWorkerResult` with proposals
2. Each proposal is mapped to an `EvidenceRecord` in an `EvidenceBundle`
3. Human reviews the evidence and individual proposals
4. Human decides which proposals (if any) to act on
5. Human executes approved actions manually

The agent worker plane never executes directly. The human is the gate.

---

## CLI Usage

```bash
# List all agent worker profiles and policy status
python v3/cli/systemkernel.py agent-worker profiles

# Generate deterministic mock agent worker result
python v3/cli/systemkernel.py agent-worker mock --proposals 3

# Build evidence bundle from mock result
python v3/cli/systemkernel.py agent-worker evidence
```

---

## Anti-Overengineering

- No agent framework imports (OpenHands, SWE-agent, AutoGen, Continue)
- No LLM integration
- No sandbox implementation
- No command execution
- No filesystem modification
- Phase 1 contract, Phase 3 evidence model reused
- `truth_source` always `False`
- `dry_run` always `True` by default
- `require_human_approval` always `True` by default

---

*SystemKernel v4.0 Phase 6 — Agent Worker Plane*
