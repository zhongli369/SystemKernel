"""
Default Capability Adapters — Phase 2.

Defines default ExternalCapabilityAdapterSpec entries for existing
Phase 7 adapters and placeholder specs for future v4.0 adapters.

Placeholders are DISABLED. They exist to test registry shape and
roadmap readiness. They do NOT imply integration.
"""

from __future__ import annotations

from typing import Tuple

from v3.external.capability_contract import (
    CapabilityExecutionMode,
    CapabilityInputContract,
    CapabilityOutputContract,
    CapabilityRiskLevel,
    CapabilityType,
    ExternalCapabilityAdapterSpec,
    compute_stable_hash,
)
from v3.external.capability_registry import (
    CapabilityRegistryEntry,
    CapabilityRegistry,
    build_registry,
)
from v3.external.capability_lifecycle import (
    STATE_APPROVED,
    STATE_DISABLED,
    STATE_PROPOSED,
    STATE_REGISTERED,
)


# ═══════════════════════════════════════════════════════════════════════
# Phase 7: Existing adapters (integrated, approved)
# ═══════════════════════════════════════════════════════════════════════

def _make_repomix_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="repomix_context_pack",
        name="Repomix Context Pack Generator",
        capability_type=CapabilityType.context.value,
        execution_modes=(
            CapabilityExecutionMode.dry_run.value,
            CapabilityExecutionMode.inspect_only.value,
            CapabilityExecutionMode.explicit_execute.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="context_pack_request",
            required_fields=("target",),
            optional_fields=("output", "style"),
            max_input_bytes=10000,
            allows_filesystem_read=True,
            allows_filesystem_write=True,
            allows_network=True,
            requires_approval=True,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="context_pack_result",
            output_fields=("content", "file_count", "total_bytes"),
            max_output_bytes=500000,
            contains_evidence=True,
            contains_artifacts=True,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("plan", "inspect", "generate"),
        forbidden_actions=("no_auto_execute", "no_kernel_integration"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.medium.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


def _make_ccusage_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="ccusage_usage_report",
        name="Claude Code Usage Reporter",
        capability_type=CapabilityType.usage.value,
        execution_modes=(
            CapabilityExecutionMode.inspect_only.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="usage_report_request",
            required_fields=("path",),
            optional_fields=("output",),
            max_input_bytes=10000,
            allows_filesystem_read=True,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=False,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="usage_report_summary",
            output_fields=("total_tokens", "total_cost", "cache_read_ratio"),
            max_output_bytes=50000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("inspect", "summarize"),
        forbidden_actions=("no_execute_ccusage", "no_network", "no_kernel_integration"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.low.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


def _make_anthropic_skills_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="anthropic_skills_format_reference",
        name="Anthropic Skills Format Reference",
        capability_type=CapabilityType.skill.value,
        execution_modes=(
            CapabilityExecutionMode.inspect_only.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="skills_format_request",
            required_fields=("path",),
            optional_fields=(),
            max_input_bytes=50000,
            allows_filesystem_read=True,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=False,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="skills_format_reference",
            output_fields=("skill_count", "format_version", "categories"),
            max_output_bytes=100000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("inspect",),
        forbidden_actions=("no_auto_execute", "no_skill_execution", "no_kernel_integration"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.low.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


# ═══════════════════════════════════════════════════════════════════════
# Phase 3-5: Future adapters (disabled placeholders)
# ═══════════════════════════════════════════════════════════════════════

def _make_placeholder_spec(
    adapter_id: str,
    name: str,
    capability_type: str,
    notes: str,
) -> ExternalCapabilityAdapterSpec:
    """Create a disabled placeholder spec for a future adapter."""
    spec = ExternalCapabilityAdapterSpec(
        adapter_id=adapter_id,
        name=name,
        capability_type=capability_type,
        execution_modes=(CapabilityExecutionMode.disabled.value,),
        input_contract=CapabilityInputContract(
            schema_name="placeholder",
            required_fields=(),
            optional_fields=(),
            max_input_bytes=0,
            allows_filesystem_read=False,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=True,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="placeholder",
            output_fields=(),
            max_output_bytes=0,
            contains_evidence=False,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=(),
        forbidden_actions=(
            "no_execute", "no_network", "no_filesystem",
            "no_kernel_integration", "placeholder_only",
        ),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.medium.value,
        version="0.0.0-placeholder",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


FUTURE_PLACEHOLDERS = (
    ("mem0_memory_intelligence", "mem0 Memory Intelligence", CapabilityType.memory.value,
     "Phase 3 — Memory intelligence backend. Not yet integrated."),
    ("graphiti_temporal_kg", "Graphiti Temporal Knowledge Graph", CapabilityType.memory.value,
     "Phase 3 — Graph-based temporal memory. Not yet integrated."),
    ("openhands_agent_worker", "OpenHands Agent Worker", CapabilityType.agent.value,
     "Phase 5 — Autonomous agent executor. Not yet integrated."),
    ("autogen_multi_agent", "AutoGen Multi-Agent Framework", CapabilityType.agent.value,
     "Phase 5 — Multi-agent orchestration. Not yet integrated."),
    ("continue_workspace_context", "Continue Workspace Context", CapabilityType.ide.value,
     "Future — IDE/workspace context provider. Not yet integrated."),
    ("swe_agent_worker", "SWE-Agent Worker", CapabilityType.agent.value,
     "Phase 5 — Software engineering agent. Not yet integrated."),
    ("letta_memory_agent", "Letta Memory Agent", CapabilityType.memory.value,
     "Future — Memory-augmented agent framework. Not yet integrated."),
)


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def build_default_registry() -> CapabilityRegistry:
    """Build the default capability registry with all known adapters.

    Includes:
      - 2 approved/integrated adapters (repomix, ccusage)
      - 1 registered but experimental (anthropic skills)
      - 7 disabled placeholders (future v4.0 adapters)
    """
    entries = []

    # Repomix — integrated and approved
    repomix_spec = _make_repomix_spec()
    repomix_entry = CapabilityRegistryEntry(
        adapter_id="repomix_context_pack",
        spec=repomix_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="dry_run",
        approval_required=True,
        owner="Phase 7C",
        notes="Context pack generator. Integrated and tested. 31 tests.",
    )
    object.__setattr__(repomix_entry, "entry_hash", compute_stable_hash(repomix_entry))
    entries.append(repomix_entry)

    # ccusage — integrated and approved
    ccusage_spec = _make_ccusage_spec()
    ccusage_entry = CapabilityRegistryEntry(
        adapter_id="ccusage_usage_report",
        spec=ccusage_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="inspect_only",
        approval_required=False,
        owner="Phase 7E",
        notes="Claude Code usage reporter. Inspect-only. Integrated and tested. 32 tests.",
    )
    object.__setattr__(ccusage_entry, "entry_hash", compute_stable_hash(ccusage_entry))
    entries.append(ccusage_entry)

    # Anthropic Skills — registered but disabled (deferred)
    anthropic_spec = _make_anthropic_skills_spec()
    anthropic_entry = CapabilityRegistryEntry(
        adapter_id="anthropic_skills_format_reference",
        spec=anthropic_spec,
        lifecycle_state=STATE_REGISTERED,
        enabled=False,
        maturity="experimental",
        execution_mode_default="inspect_only",
        approval_required=False,
        owner="Phase 7B",
        notes="Deferred to Skill Format Alignment phase. Inspected only, not integrated.",
    )
    object.__setattr__(anthropic_entry, "entry_hash",
                       compute_stable_hash(anthropic_entry))
    entries.append(anthropic_entry)

    # Future placeholders — all disabled
    for adapter_id, name, cap_type, notes in FUTURE_PLACEHOLDERS:
        spec = _make_placeholder_spec(adapter_id, name, cap_type, notes)
        entry = CapabilityRegistryEntry(
            adapter_id=adapter_id,
            spec=spec,
            lifecycle_state=STATE_DISABLED,
            enabled=False,
            maturity="experimental",
            execution_mode_default="disabled",
            approval_required=True,
            owner="v4.0 Roadmap",
            notes=notes,
        )
        object.__setattr__(entry, "entry_hash", compute_stable_hash(entry))
        entries.append(entry)

    return build_registry(tuple(entries))
