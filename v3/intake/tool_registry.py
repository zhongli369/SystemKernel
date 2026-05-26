"""
External Tool Registry — Maps repo intake decisions to tool use modes.

Translates Phase 5D RepoIntakeDecision results into actionable
ExternalToolEntry records with explicit allowed/forbidden actions.

Use modes:
  - direct_tool: Clone into F:/Claude/Github/ for direct CLI/tool use
  - source_reference: Clone for source code study only (inspect, don't run)
  - external_service: Evaluate as external service via API only
  - format_reference: Study format/structure (e.g. SKILL.md format)
  - architecture_reference: Study architecture/design patterns only

Zero network. Zero clone. Plan only.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Use mode constants
# ═══════════════════════════════════════════════════════════════════════

USE_MODE_DIRECT_TOOL = "direct_tool"
USE_MODE_SOURCE_REFERENCE = "source_reference"
USE_MODE_EXTERNAL_SERVICE = "external_service"
USE_MODE_FORMAT_REFERENCE = "format_reference"
USE_MODE_ARCHITECTURE_REFERENCE = "architecture_reference"

USE_MODES = (
    USE_MODE_DIRECT_TOOL,
    USE_MODE_SOURCE_REFERENCE,
    USE_MODE_EXTERNAL_SERVICE,
    USE_MODE_FORMAT_REFERENCE,
    USE_MODE_ARCHITECTURE_REFERENCE,
)

# Clone action categories
CLONE_NOW = "clone_now"
INSPECT_ONLY = "inspect_only"
EXTERNAL_EVAL = "external_evaluation"
REFERENCE_ONLY = "reference_only"


# ═══════════════════════════════════════════════════════════════════════
# ExternalToolEntry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExternalToolEntry:
    """One entry in the external tool registry.

    Fields:
        name: Tool/repo name
        repo_url: GitHub URL
        decision: Intake decision (DIRECT_CLONE, etc.)
        priority: S | A | B | C | D
        target_dir: Where the repo would be cloned
        use_mode: How the tool should be used
        allowed_actions: What may be done with this tool
        forbidden_actions: What must NOT be done
        systemkernel_touchpoints: Valid interaction points with SystemKernel
        claude_code_value: Value score for Claude Code usage (0-10)
        kernel_risk: Risk to kernel purity (0-10, lower is better)
        notes: Human-readable notes
    """

    name: str
    repo_url: str = ""
    decision: str = ""
    priority: str = "D"
    target_dir: str = ""
    use_mode: str = USE_MODE_ARCHITECTURE_REFERENCE
    allowed_actions: Tuple[str, ...] = ()
    forbidden_actions: Tuple[str, ...] = ()
    systemkernel_touchpoints: Tuple[str, ...] = ()
    claude_code_value: float = 0.0
    kernel_risk: float = 10.0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "repo_url": self.repo_url,
            "decision": self.decision,
            "priority": self.priority,
            "target_dir": self.target_dir,
            "use_mode": self.use_mode,
            "allowed_actions": list(self.allowed_actions),
            "forbidden_actions": list(self.forbidden_actions),
            "systemkernel_touchpoints": list(self.systemkernel_touchpoints),
            "claude_code_value": self.claude_code_value,
            "kernel_risk": self.kernel_risk,
            "notes": self.notes,
        }

    @property
    def is_clone_now(self) -> bool:
        return self.use_mode in (USE_MODE_DIRECT_TOOL, USE_MODE_FORMAT_REFERENCE)

    @property
    def is_inspect_only(self) -> bool:
        return self.use_mode == USE_MODE_SOURCE_REFERENCE

    @property
    def is_external_eval(self) -> bool:
        return self.use_mode == USE_MODE_EXTERNAL_SERVICE

    @property
    def is_reference_only(self) -> bool:
        return self.use_mode == USE_MODE_ARCHITECTURE_REFERENCE


# ═══════════════════════════════════════════════════════════════════════
# ExternalToolRegistry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExternalToolRegistry:
    """Complete external tool registry.

    Fields:
        entries: All tool entries
        registry_hash: Deterministic hash of the registry
        direct_clone_count: Number of direct_tool entries
        external_extension_count: Number of external_service entries
        architecture_reference_count: Number of architecture_reference entries
        reject_count: Number of rejected entries
    """

    entries: Tuple[ExternalToolEntry, ...] = ()
    registry_hash: str = ""
    direct_clone_count: int = 0
    external_extension_count: int = 0
    architecture_reference_count: int = 0
    reject_count: int = 0

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "registry_hash": self.registry_hash,
            "counts": {
                "total": len(self.entries),
                "direct_clone": self.direct_clone_count,
                "external_extension": self.external_extension_count,
                "architecture_reference": self.architecture_reference_count,
                "reject": self.reject_count,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def get_clone_now(self) -> Tuple[ExternalToolEntry, ...]:
        return tuple(e for e in self.entries if e.is_clone_now)

    def get_inspect_only(self) -> Tuple[ExternalToolEntry, ...]:
        return tuple(e for e in self.entries if e.is_inspect_only)

    def get_external(self) -> Tuple[ExternalToolEntry, ...]:
        return tuple(e for e in self.entries if e.is_external_eval)

    def get_reference(self) -> Tuple[ExternalToolEntry, ...]:
        return tuple(e for e in self.entries if e.is_reference_only)


# ═══════════════════════════════════════════════════════════════════════
# Decision → Use Mode mapping
# ═══════════════════════════════════════════════════════════════════════

def _map_decision_to_use_mode(
    name: str,
    decision: str,
    cc_value: float,
    purity_risk: float,
    known_risks: Tuple[str, ...],
    category_hint: str,
) -> str:
    """Map an intake decision + context to a use mode.

    This is the central mapping that prevents DIRECT_CLONE from being
    misinterpreted as "integrate into kernel." DIRECT_CLONE repos are
    still external tools — they just happen to be safe to clone locally.
    """
    name_lower = name.lower()

    # ── Format references (skill definitions, templates) ──
    if "skill" in name_lower and decision == "DIRECT_CLONE":
        return USE_MODE_FORMAT_REFERENCE

    # ── Direct tools (CLI tools with high CC value) ──
    if decision == "DIRECT_CLONE" and cc_value >= 7.0:
        # AppFlowy, JupyterLab, SuperClaude — large codebases or application repos
        # These get DIRECT_CLONE from the engine but should be inspect_only
        large_app_names = {"appflowy", "jupyterlab", "superclaude"}
        if name_lower in large_app_names:
            return USE_MODE_SOURCE_REFERENCE
        return USE_MODE_DIRECT_TOOL

    # ── External services ──
    if decision == "EXTERNAL_EXTENSION":
        return USE_MODE_EXTERNAL_SERVICE

    # ── Architecture references ──
    if decision == "ARCHITECTURE_REFERENCE":
        return USE_MODE_ARCHITECTURE_REFERENCE

    # ── Rejected ──
    return USE_MODE_ARCHITECTURE_REFERENCE


def _build_allowed_actions(use_mode: str, name: str) -> Tuple[str, ...]:
    """Determine allowed actions based on use mode."""
    if use_mode == USE_MODE_DIRECT_TOOL:
        return (
            "clone_to_github",
            "run_locally_as_tool",
            "use_cli_interface",
            "read_source_code",
            "study_architecture",
        )
    elif use_mode == USE_MODE_SOURCE_REFERENCE:
        return (
            "clone_to_github_for_inspection",
            "read_source_code",
            "study_architecture",
            "extract_design_patterns",
        )
    elif use_mode == USE_MODE_EXTERNAL_SERVICE:
        return (
            "evaluate_via_api",
            "study_architecture",
            "read_documentation",
            "test_external_integration",
        )
    elif use_mode == USE_MODE_FORMAT_REFERENCE:
        return (
            "clone_to_github",
            "read_source_code",
            "study_file_formats",
            "extract_format_patterns",
            "use_as_template_reference",
        )
    else:
        return (
            "study_architecture",
            "extract_design_patterns",
            "document_findings",
        )


def _build_forbidden_actions(use_mode: str, name: str,
                              purity_risk: float) -> Tuple[str, ...]:
    """Determine forbidden actions based on use mode and risk."""
    common = ("do_not_integrate_into_kernel", "do_not_modify_kernel_boundary")

    if use_mode in (USE_MODE_DIRECT_TOOL, USE_MODE_FORMAT_REFERENCE):
        return common + ("do_not_embed_as_kernel_module",)
    elif use_mode == USE_MODE_SOURCE_REFERENCE:
        return common + (
            "do_not_run_as_dependency",
            "do_not_embed_as_kernel_module",
            "do_not_execute_without_review",
        )
    elif use_mode == USE_MODE_EXTERNAL_SERVICE:
        return common + (
            "do_not_import_directly",
            "do_not_embed_as_kernel_module",
            "do_not_install_locally_without_review",
        )
    else:
        return common + (
            "do_not_clone",
            "do_not_import",
            "do_not_integrate",
            "do_not_run_as_dependency",
        )


def _build_touchpoints(use_mode: str, name: str) -> Tuple[str, ...]:
    """Define valid SystemKernel touchpoints."""
    if use_mode == USE_MODE_DIRECT_TOOL:
        return ("cli_invocation", "output_parsing", "filesystem_io")
    elif use_mode == USE_MODE_SOURCE_REFERENCE:
        return ("source_code_study", "architecture_analysis")
    elif use_mode == USE_MODE_EXTERNAL_SERVICE:
        return ("api_evaluation", "integration_design")
    elif use_mode == USE_MODE_FORMAT_REFERENCE:
        return ("format_study", "template_extraction", "skill_definition_reference")
    else:
        return ("architecture_study", "pattern_extraction")


# ═══════════════════════════════════════════════════════════════════════
# Builder functions
# ═══════════════════════════════════════════════════════════════════════

def build_registry_from_profiles() -> ExternalToolRegistry:
    """Build the external tool registry from all 14 pre-built repo profiles.

    Uses Phase 5D intake decisions and maps them to tool use modes.
    """
    from v3.intake.repo_profiles import get_all_profiles
    from v3.intake.repo_intake import decide_repo_intake

    profiles = get_all_profiles()
    entries = []

    for p in profiles:
        inp = p.to_input()
        signals = p.analyze()
        decision = decide_repo_intake(inp, signals)

        use_mode = _map_decision_to_use_mode(
            name=p.name,
            decision=decision.decision,
            cc_value=decision.claude_code_value_score,
            purity_risk=decision.purity_risk_score,
            known_risks=p.known_risks,
            category_hint=p.category_hint,
        )

        allowed = _build_allowed_actions(use_mode, p.name)
        forbidden = _build_forbidden_actions(use_mode, p.name, decision.purity_risk_score)
        touchpoints = _build_touchpoints(use_mode, p.name)

        entry = ExternalToolEntry(
            name=p.name,
            repo_url=p.url,
            decision=decision.decision,
            priority=decision.priority,
            target_dir=decision.recommended_target_dir,
            use_mode=use_mode,
            allowed_actions=allowed,
            forbidden_actions=forbidden,
            systemkernel_touchpoints=touchpoints,
            claude_code_value=decision.claude_code_value_score,
            kernel_risk=decision.purity_risk_score,
            notes=_build_notes(p.name, use_mode, decision, p.known_risks),
        )
        entries.append(entry)

    return _finalize_registry(tuple(entries))


def build_registry_from_intake_reports(reports: list) -> ExternalToolRegistry:
    """Build registry from a list of RepoIntakeReport objects."""
    entries = []

    for report in reports:
        decision = report.decision
        inp = report.input

        use_mode = _map_decision_to_use_mode(
            name=inp.name,
            decision=decision.decision,
            cc_value=decision.claude_code_value_score,
            purity_risk=decision.purity_risk_score,
            known_risks=(),
            category_hint=inp.category_hint,
        )

        allowed = _build_allowed_actions(use_mode, inp.name)
        forbidden = _build_forbidden_actions(use_mode, inp.name, decision.purity_risk_score)
        touchpoints = _build_touchpoints(use_mode, inp.name)

        entry = ExternalToolEntry(
            name=inp.name,
            repo_url=inp.url,
            decision=decision.decision,
            priority=decision.priority,
            target_dir=decision.recommended_target_dir,
            use_mode=use_mode,
            allowed_actions=allowed,
            forbidden_actions=forbidden,
            systemkernel_touchpoints=touchpoints,
            claude_code_value=decision.claude_code_value_score,
            kernel_risk=decision.purity_risk_score,
            notes=_build_notes(inp.name, use_mode, decision, ()),
        )
        entries.append(entry)

    return _finalize_registry(tuple(entries))


def _build_notes(name: str, use_mode: str, decision,
                 known_risks: Tuple[str, ...]) -> str:
    """Build human-readable notes for a tool entry."""
    notes_map = {
        "Repomix": "CLI context packer — safe to clone and use as a local tool. No kernel integration needed.",
        "ccusage": "Claude Code usage tracker — safe to clone, CLI tool only. Useful for monitoring CC costs.",
        "Anthropic Skills": "Skill definition format reference. Clone to study SKILL.md structure and conventions. Do not execute skills.",
        "SuperClaude": "Claude Code enhancement utilities. Inspect source for patterns. Contains skill definitions that may overlap with existing skills.",
        "JupyterLab": "Very large codebase. Inspect architecture for notebook/IDE patterns. Not suitable for direct integration.",
        "AppFlowy": "Large Flutter/Rust application. Inspect for Notion-like document model patterns. AGPL license requires care.",
        "mem0": "Memory layer for AI. Evaluate as external service only. Vector DB + LLM deps conflict with kernel constraints.",
        "Graphiti": "Knowledge graph memory. Evaluate as external service only. Neo4j + OpenAI deps conflict with kernel constraints.",
        "Continue": "IDE extension for AI. Evaluate as external service. OpenAI dependency. Useful for IDE integration patterns.",
        "OpenAI Swarm": "Lightweight agent swarm. Evaluate as external service. OpenAI dependency. Study swarm patterns.",
        "LangGraph": "Agent framework. Architecture reference only. Heavy langchain dependency. Study state machine patterns.",
        "CrewAI": "Multi-agent orchestration. Architecture reference only. OpenAI + langchain deps. Study role-based agent patterns.",
        "awesome-claude-code": "Curated resource list. Architecture reference for discovering tools and patterns.",
        "Awesome-Prompt-Engineering": "Curated prompt engineering resources. Reference for prompt design patterns.",
    }
    return notes_map.get(name, f"{use_mode}: {decision.decision} (priority {decision.priority})")


def _finalize_registry(entries: Tuple[ExternalToolEntry, ...]) -> ExternalToolRegistry:
    """Compute counts and hash for a registry."""
    direct = sum(1 for e in entries if e.use_mode == USE_MODE_DIRECT_TOOL)
    ext = sum(1 for e in entries if e.use_mode == USE_MODE_EXTERNAL_SERVICE)
    arch = sum(1 for e in entries if e.use_mode in (
        USE_MODE_ARCHITECTURE_REFERENCE, USE_MODE_SOURCE_REFERENCE, USE_MODE_FORMAT_REFERENCE))
    rejected = sum(1 for e in entries if e.decision == "REJECT")

    hash_input = json.dumps(
        [e.to_dict() for e in entries], sort_keys=True, ensure_ascii=False)
    registry_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return ExternalToolRegistry(
        entries=entries,
        registry_hash=registry_hash,
        direct_clone_count=direct,
        external_extension_count=ext,
        architecture_reference_count=arch,
        reject_count=rejected,
    )


# ═══════════════════════════════════════════════════════════════════════
# Clone ordering
# ═══════════════════════════════════════════════════════════════════════

def recommend_clone_order(registry: ExternalToolRegistry) -> list:
    """Recommend clone order for clone_now entries, sorted by priority + CC value."""
    clone_now = [e for e in registry.entries if e.is_clone_now]
    # Sort: priority (S > A > B > C > D), then by CC value descending
    priority_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    clone_now.sort(key=lambda e: (priority_order.get(e.priority, 5), -e.claude_code_value))
    return [e.name for e in clone_now]


# ═══════════════════════════════════════════════════════════════════════
# I/O
# ═══════════════════════════════════════════════════════════════════════

def write_registry(registry: ExternalToolRegistry, path: str) -> str:
    """Write registry to a JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)


def write_clone_plan(registry: ExternalToolRegistry, path: str,
                     root_dir: str = "F:\\Claude\\Github") -> str:
    """Write a clone plan JSON file from the registry. Returns absolute path."""
    from v3.intake.clone_plan import create_clone_plan
    plan = create_clone_plan(registry, root_dir=root_dir)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)
