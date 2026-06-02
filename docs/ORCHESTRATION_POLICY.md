# Orchestration Policy Layer — Phase 9

## Overview

The Orchestration Policy Layer defines a deterministic policy system for
planning which external capability adapters may be used together. It is
NOT an execution engine. It is NOT an AI planner.

## Core Principle

**Orchestration decides what is allowed to be planned.** It does not
execute tools, agents, or mutate kernel truth. It produces dry-run plans
and policy reports only.

## Orchestration Flow

```
OrchestrationRequest → OrchestrationPolicy → Registry entries →
  plan_orchestration() → OrchestrationPlan → evidence bundle
```

Every step in this flow is deterministic. Same request + policy + registry
= same plan, always.

## Policy Profiles

Six policy profiles are defined:

| Profile | Types | Dry-Run | Risk | Execution |
|---------|-------|---------|------|-----------|
| safe_context_only | context, usage | Yes | medium | No |
| skill_evolution_review | skill | Yes | medium | No |
| memory_intelligence_review | memory | Yes | low | No |
| agent_worker_review | agent | Yes | low | No |
| full_external_review | all 8 types | Yes | high | No |
| ecc_harness_review | skill, tool, eval, context | Yes | medium | No |

## ECC Harness Review Profile

The ECC (everything-claude-code) harness review profile is a FUTURE
placeholder. ECC should be usable by SystemKernel as an external capability
source, but SystemKernel must not become an ECC clone.

- **Repo:** https://github.com/affaan-m/everything-claude-code
- **Status:** NOT integrated, NOT cloned, NOT installed
- **Capability types:** skill, tool, eval, context
- **Forbidden types:** agent, ide, memory, usage
- **Execution:** dry_run_only — no install, no repair, no hook modification
- **Role:** Future external harness enhancement provider

OpenHands, AutoGen, SWE-agent, Continue, and other agent/IDE providers
remain external and are not integrated through this plane.

## What is NOT Allowed

- Workflow engine
- Autonomous planning
- Adapter execution
- Another runtime loop
- File modification
- Network access
- Registry updates
- Memory mutation

## Evidence Mapping

All orchestration plans are converted to EvidenceBundle records:
- evidence_type = generic
- trust_level = TRUST_LOW
- truth_source = False
- collection_mode = dry_run

## Default Policy Invariants

- dry_run_only = True
- allow_external_execution = False
- allow_file_modification = False
- allow_network = False
- allow_registry_updates = False
- allow_memory_mutation = False
- require_human_approval = True

## Files

- `v3/external/orchestration_policy.py` — Core dataclasses and functions
- `v3/external/orchestration_profiles.py` — Policy profiles
- `v3/tests/test_orchestration_policy.py` — Test suite
- `v3/tests/fixtures/orchestration_request.json` — Test fixture
