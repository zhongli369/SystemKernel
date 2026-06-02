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
# v4.1: Direction & Quality intelligence adapters
# ═══════════════════════════════════════════════════════════════════════

def _make_gstack_direction_spec() -> ExternalCapabilityAdapterSpec:
    """gstack direction intelligence adapter spec.

    Methodology-based. Analysis only. No LLM. No external execution.
    Approved by default — produces advisory direction signals only.
    """
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="gstack_direction_intelligence",
        name="gstack Direction Intelligence",
        capability_type=CapabilityType.direction.value,
        execution_modes=(
            CapabilityExecutionMode.inspect_only.value,
            CapabilityExecutionMode.dry_run.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="direction_intelligence_request",
            required_fields=("task_intent",),
            optional_fields=("project_context", "system_state_refs"),
            max_input_bytes=50000,
            allows_filesystem_read=False,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=False,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="direction_intelligence_result",
            output_fields=("signals", "intent_clusters", "priority_ranking", "risk_assessment"),
            max_output_bytes=100000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("analyze", "inspect"),
        forbidden_actions=("no_execute", "no_decision", "no_kernel_modification",
                           "no_network", "no_external_service"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.low.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


def _make_superpowers_quality_spec() -> ExternalCapabilityAdapterSpec:
    """superpowers quality intelligence adapter spec.

    Methodology-based. Analysis only. No LLM. No external execution.
    Approved by default — produces advisory quality signals only.
    """
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="superpowers_quality_intelligence",
        name="superpowers Quality Intelligence",
        capability_type=CapabilityType.quality.value,
        execution_modes=(
            CapabilityExecutionMode.inspect_only.value,
            CapabilityExecutionMode.dry_run.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="quality_intelligence_request",
            required_fields=("target_content", "target_type"),
            optional_fields=("target_refs",),
            max_input_bytes=200000,
            allows_filesystem_read=False,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=False,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="quality_intelligence_result",
            output_fields=("signals", "quality_score", "defects", "improvements"),
            max_output_bytes=100000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("analyze", "inspect"),
        forbidden_actions=("no_execute", "no_decision", "no_code_modification",
                           "no_network", "no_external_service"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.low.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════
# Phase 16b-1: Core Providers (crawl4ai, jina-reader, trivy)
# ═══════════════════════════════════════════════════════════════════════

def _make_crawl4ai_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="crawl4ai",
        name="Crawl4AI Web Crawler",
        capability_type=CapabilityType.context.value,
        execution_modes=(
            CapabilityExecutionMode.explicit_execute.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="crawl_request",
            required_fields=("url",),
            max_input_bytes=2000,
            allows_filesystem_read=False,
            allows_filesystem_write=False,
            allows_network=True,
            requires_approval=True,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="markdown_content",
            output_fields=("markdown",),
            max_output_bytes=500000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("crawl",),
        forbidden_actions=("write", "execute", "delete"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.medium.value,
        version="0.8.6",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec))
    return spec


def _make_jina_reader_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="jina-reader",
        name="Jina Reader URL-to-Markdown",
        capability_type=CapabilityType.context.value,
        execution_modes=(
            CapabilityExecutionMode.explicit_execute.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="jina_read_request",
            required_fields=("url",),
            max_input_bytes=2000,
            allows_filesystem_read=False,
            allows_filesystem_write=False,
            allows_network=True,
            requires_approval=False,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="plain_text_content",
            output_fields=("markdown",),
            max_output_bytes=500000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("read",),
        forbidden_actions=("write", "execute", "delete"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.low.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec))
    return spec


def _make_trivy_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="trivy",
        name="Trivy Vulnerability Scanner",
        capability_type=CapabilityType.tool.value,
        execution_modes=(
            CapabilityExecutionMode.explicit_execute.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="trivy_scan_request",
            required_fields=("target_path",),
            max_input_bytes=4000,
            allows_filesystem_read=True,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=True,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="vulnerability_report",
            output_fields=("json",),
            max_output_bytes=2000000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("scan_fs", "scan_image"),
        forbidden_actions=("write", "execute", "delete", "network"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.high.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec))
    return spec


# ═══════════════════════════════════════════════════════════════════════
# Phase 16c: L2 Tool Interface — In-process tool management specs
# ═══════════════════════════════════════════════════════════════════════

def _make_tool_selector_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="tool_selector",
        name="Context-Aware Tool Selector",
        capability_type=CapabilityType.tool.value,
        execution_modes=(
            CapabilityExecutionMode.inspect_only.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="tool_selector_request",
            required_fields=("task_type",),
            optional_fields=("max_tools",),
            max_input_bytes=2000,
            allows_filesystem_read=False,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=False,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="tool_selector_result",
            output_fields=("selected", "excluded", "reason_map"),
            max_output_bytes=50000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("inspect", "analyze"),
        forbidden_actions=("no_execute", "no_network", "no_filesystem",
                           "no_kernel_integration"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.low.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


def _make_tool_dedup_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="tool_dedup",
        name="Tool Deduplication Detector",
        capability_type=CapabilityType.tool.value,
        execution_modes=(
            CapabilityExecutionMode.inspect_only.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="tool_dedup_request",
            required_fields=(),
            optional_fields=("threshold",),
            max_input_bytes=1000,
            allows_filesystem_read=False,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=False,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="tool_dedup_result",
            output_fields=("duplicates", "unique_tools", "overlap_scores"),
            max_output_bytes=100000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("inspect", "analyze"),
        forbidden_actions=("no_execute", "no_network", "no_filesystem",
                           "no_kernel_integration"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.low.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


def _make_tool_conflicts_spec() -> ExternalCapabilityAdapterSpec:
    spec = ExternalCapabilityAdapterSpec(
        adapter_id="tool_conflicts",
        name="Tool Conflict Detector",
        capability_type=CapabilityType.tool.value,
        execution_modes=(
            CapabilityExecutionMode.inspect_only.value,
        ),
        input_contract=CapabilityInputContract(
            schema_name="tool_conflicts_request",
            required_fields=("selected_tools",),
            optional_fields=(),
            max_input_bytes=5000,
            allows_filesystem_read=False,
            allows_filesystem_write=False,
            allows_network=False,
            requires_approval=False,
        ),
        output_contract=CapabilityOutputContract(
            schema_name="tool_conflicts_result",
            output_fields=("conflicts", "safe_pairs"),
            max_output_bytes=50000,
            contains_evidence=True,
            contains_artifacts=False,
            truth_source=False,
            provenance_required=True,
        ),
        allowed_actions=("inspect", "analyze"),
        forbidden_actions=("no_execute", "no_network", "no_filesystem",
                           "no_kernel_integration"),
        removable=True,
        truth_source=False,
        risk_level=CapabilityRiskLevel.low.value,
        version="1.0.0",
    )
    object.__setattr__(spec, "spec_hash", compute_stable_hash(spec, "spec"))
    return spec


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

    # gstack direction intelligence — approved, methodology-based, analysis-only
    gstack_spec = _make_gstack_direction_spec()
    gstack_entry = CapabilityRegistryEntry(
        adapter_id="gstack_direction_intelligence",
        spec=gstack_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="inspect_only",
        approval_required=False,
        owner="v4.1 Direction Plane",
        notes="gstack methodology adapter. Analysis-only direction signals. "
              "No external execution. No LLM. truth_source=False.",
    )
    object.__setattr__(gstack_entry, "entry_hash", compute_stable_hash(gstack_entry))
    entries.append(gstack_entry)

    # superpowers quality intelligence — approved, methodology-based, analysis-only
    superpowers_spec = _make_superpowers_quality_spec()
    superpowers_entry = CapabilityRegistryEntry(
        adapter_id="superpowers_quality_intelligence",
        spec=superpowers_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="inspect_only",
        approval_required=False,
        owner="v4.1 Quality Plane",
        notes="superpowers methodology adapter. Analysis-only quality signals. "
              "No external execution. No LLM. truth_source=False.",
    )
    object.__setattr__(superpowers_entry, "entry_hash", compute_stable_hash(superpowers_entry))
    entries.append(superpowers_entry)

    # Phase 16b-1: Core Providers
    crawl4ai_spec = _make_crawl4ai_spec()
    crawl4ai_entry = CapabilityRegistryEntry(
        adapter_id="crawl4ai",
        spec=crawl4ai_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="explicit_execute",
        approval_required=True,
        owner="Phase 16b-1",
        notes="URL to Markdown crawler. subprocess + CLI. truth_source=False.",
    )
    object.__setattr__(crawl4ai_entry, "entry_hash", compute_stable_hash(crawl4ai_entry))
    entries.append(crawl4ai_entry)

    jina_spec = _make_jina_reader_spec()
    jina_entry = CapabilityRegistryEntry(
        adapter_id="jina-reader",
        spec=jina_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="explicit_execute",
        approval_required=False,
        owner="Phase 16b-1",
        notes="URL to text via HTTP GET. No CLI needed. stdlib urllib. truth_source=False.",
    )
    object.__setattr__(jina_entry, "entry_hash", compute_stable_hash(jina_entry))
    entries.append(jina_entry)

    trivy_spec = _make_trivy_spec()
    trivy_entry = CapabilityRegistryEntry(
        adapter_id="trivy",
        spec=trivy_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="explicit_execute",
        approval_required=True,
        owner="Phase 16b-1",
        notes="Vulnerability scanner. HIGH/CRITICAL only. truth_source=False.",
    )
    object.__setattr__(trivy_entry, "entry_hash", compute_stable_hash(trivy_entry))
    entries.append(trivy_entry)

    # Phase 16c: L2 Tool Interface — in-process tool management
    tool_selector_spec = _make_tool_selector_spec()
    tool_selector_entry = CapabilityRegistryEntry(
        adapter_id="tool_selector",
        spec=tool_selector_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="inspect_only",
        approval_required=False,
        owner="Phase 16c",
        notes="Context-aware tool filtering by task type. In-process, deterministic, no LLM.",
    )
    object.__setattr__(tool_selector_entry, "entry_hash", compute_stable_hash(tool_selector_entry))
    entries.append(tool_selector_entry)

    tool_dedup_spec = _make_tool_dedup_spec()
    tool_dedup_entry = CapabilityRegistryEntry(
        adapter_id="tool_dedup",
        spec=tool_dedup_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="inspect_only",
        approval_required=False,
        owner="Phase 16c",
        notes="Jaccard-similarity-based tool deduplication. In-process, deterministic, no LLM.",
    )
    object.__setattr__(tool_dedup_entry, "entry_hash", compute_stable_hash(tool_dedup_entry))
    entries.append(tool_dedup_entry)

    tool_conflicts_spec = _make_tool_conflicts_spec()
    tool_conflicts_entry = CapabilityRegistryEntry(
        adapter_id="tool_conflicts",
        spec=tool_conflicts_spec,
        lifecycle_state=STATE_APPROVED,
        enabled=True,
        maturity="stable",
        execution_mode_default="inspect_only",
        approval_required=False,
        owner="Phase 16c",
        notes="Declarative tool conflict detection. In-process, deterministic, no LLM.",
    )
    object.__setattr__(tool_conflicts_entry, "entry_hash", compute_stable_hash(tool_conflicts_entry))
    entries.append(tool_conflicts_entry)

    return build_registry(tuple(entries))
