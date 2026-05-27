# Skill Evolution Plane — Phase 8

## Overview

The Skill Evolution Plane defines proposal-only contracts for external skill
evolution providers. It allows future systems to propose skill improvements,
SKILL.md alignment, registry updates, or new skill packages — but never
automatically.

## Core Principle

**Skill evolution is proposal-only.** Any change to skills, registry,
or packages requires explicit human approval and tests. Skill evolution
outputs are evidence/proposals, never truth.

## Providers

Three provider profiles are defined (only one allowed by default):

| Provider | Type | Allowed | LLM | Mod | Reg | Inst |
|----------|------|---------|-----|-----|-----|------|
| anthropic_skills_format | anthropic_skills_like | NO | Y | Y | Y | Y |
| superclaude_pattern | superclaude_like | NO | Y | Y | Y | N |
| deterministic_mock_skill_evolution | deterministic_mock | YES | N | N | N | N |

## What is NOT Allowed

- Self-modifying agents
- Automatic skill generation
- Real skill file modification
- Registry.json updates without human approval
- Skill installation
- External LLM execution for skill evolution
- Proposals treated as truth sources

## How Anthropic Skills and SuperClaude Inform This Plane

### Anthropic Skills (SKILL.md)

Anthropic's SKILL.md convention (frontmatter with name/description/triggers)
provides a structured format for skill metadata. A future Anthropic Skills
provider could:

1. Read existing SKILL.md files in `SkillsManagementSystem/packages/*/`
2. Compare against the Anthropic Skills format specification
3. Propose alignment changes (add missing frontmatter, fix descriptions)
4. Output format_alignment proposals

All such proposals would require human approval. No automatic updates.

### SuperClaude Patterns

SuperClaude patterns for skill taxonomy and organization could inform a
future taxonomy alignment provider that:

1. Analyzes existing skill categorization
2. Compares against known taxonomy patterns
3. Proposes reorganization or new categories
4. Outputs taxonomy proposals

Again, all proposals require human approval.

## Proposal Types

| Type | Description | Automatic? |
|------|-------------|------------|
| create_skill | Propose a new skill package | NO |
| update_skill | Propose updates to an existing skill | NO |
| deprecate_skill | Propose deprecation of a skill | NO |
| registry_update | Propose registry.json changes | NO |
| format_alignment | Propose SKILL.md format alignment | NO |
| test_addition | Propose adding tests to a skill | NO |
| docs_update | Propose documentation updates | NO |

## Gap Signal Types

| Signal | Meaning |
|--------|---------|
| missing_skill | No skill exists for a given intent |
| outdated_skill | Existing skill is outdated |
| poor_description | Skill description is unclear |
| missing_tests | Skill package lacks tests |
| registry_mismatch | registry.json differs from manifest.json |
| format_alignment | SKILL.md doesn't match format spec |
| duplicate_skill | Two skills cover the same intent |

## Default Policy

```
allow_llm_providers            = False
allow_skill_file_modification  = False
allow_registry_update          = False
allow_skill_installation       = False
require_tests_for_changes      = True
require_human_approval         = True
max_proposals                  = 10
```

Only `deterministic_mock` providers pass this policy.

## Future Approval Workflow (NOT implemented)

The intended future workflow (not yet implemented) would be:

1. Provider generates proposals (evidence only, truth_source=False)
2. Human reviews proposals
3. Human creates a TaskSystem task for approved changes
4. ExecutionLoop runs lint → typecheck → test on changes
5. Human approves final result
6. Changes are applied manually

This workflow is DESIGNED but NOT ACTIVE. No step runs automatically.

## Evidence Mapping

All proposals are converted to EvidenceBundle records with:
- evidence_type = EVIDENCE_TYPE_SKILL_REFERENCE
- trust_level = TRUST_LOW
- truth_source = False
- collection_mode = inspect_only

## Anti-Overengineering Gates

- No self-modifying agent
- Evidence model reused (not duplicated)
- No automatic evolution behavior
- No new runtime capability

## Files

- `v3/external/skill_evolution.py` — Core dataclasses and functions
- `v3/external/skill_evolution_policy.py` — Policy definitions
- `v3/external/skill_evolution_profiles.py` — Provider profiles
- `v3/tests/test_skill_evolution_plane.py` — Test suite
- `v3/tests/fixtures/skill_evolution_input.json` — Test fixture
