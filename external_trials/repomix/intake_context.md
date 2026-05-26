This file is a merged representation of the entire codebase, combined into a single document by Repomix.

# File Summary

## Purpose
This file contains a packed representation of the entire repository's contents.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
```
__init__.py
clone_plan.py
repo_intake.py
repo_profiles.py
rules.py
tool_registry.py
```

# Files

## File: __init__.py
```python
"""
SystemKernel v3.0 — Repo Intake Pipeline.

Deterministic repository assessment without network access.
Evaluates external repos for DIRECT_CLONE, EXTERNAL_EXTENSION,
ARCHITECTURE_REFERENCE, or REJECT decisions.
"""

from v3.intake.repo_intake import (
    DECISION_ARCHITECTURE_REFERENCE,
    DECISION_DIRECT_CLONE,
    DECISION_EXTERNAL_EXTENSION,
    DECISION_REJECT,
    DECISIONS,
    INTENDED_USE_ARCHITECTURE,
    INTENDED_USE_CLAUDE_CODE,
    INTENDED_USE_SYSTEMKERNEL,
    INTENDED_USE_UNKNOWN,
    PRIORITIES,
    PRIORITY_A,
    PRIORITY_B,
    PRIORITY_C,
    PRIORITY_D,
    PRIORITY_S,
    RepoIntakeDecision,
    RepoIntakeInput,
    RepoIntakeReport,
    RepoSignals,
    analyze_local_repo,
    analyze_repo_snapshot,
    compute_report_hash,
    decide_repo_intake,
    write_report,
)

from v3.intake.rules import (
    INTAKE_RULES,
    REPO_TYPE_AGENT_RUNTIME,
    REPO_TYPE_CLAUDE_CODE_EXTENSION,
    REPO_TYPE_CONTEXT_TOOL,
    REPO_TYPE_DOCS_ONLY,
    REPO_TYPE_MEMORY_SYSTEM,
    REPO_TYPE_OBSERVABILITY_TOOL,
    REPO_TYPE_SKILL_SYSTEM,
    REPO_TYPE_UNKNOWN,
    REPO_TYPES,
    IntakeRule,
    apply_rules,
    classify_repo_type,
    get_rules_table,
)

from v3.intake.repo_profiles import (
    PROFILES,
    RepoProfile,
    get_all_profiles,
    get_profile,
    list_profiles,
)

from v3.intake.tool_registry import (
    CLONE_NOW,
    EXTERNAL_EVAL,
    INSPECT_ONLY,
    REFERENCE_ONLY,
    USE_MODE_ARCHITECTURE_REFERENCE,
    USE_MODE_DIRECT_TOOL,
    USE_MODE_EXTERNAL_SERVICE,
    USE_MODE_FORMAT_REFERENCE,
    USE_MODE_SOURCE_REFERENCE,
    USE_MODES,
    ExternalToolEntry,
    ExternalToolRegistry,
    build_registry_from_intake_reports,
    build_registry_from_profiles,
    recommend_clone_order,
    write_registry,
    write_clone_plan,
)

from v3.intake.clone_plan import (
    POST_CLONE_ACTIONS,
    POST_CLONE_EVALUATE_EXTERNAL,
    POST_CLONE_EXTRACT_FORMAT,
    POST_CLONE_INSPECT_ONLY,
    POST_CLONE_NONE,
    POST_CLONE_READ_DOCS,
    POST_CLONE_RUN_CLI_HELP,
    ClonePlan,
    ClonePlanItem,
    create_clone_plan,
    filter_clone_now,
    summarize_plan,
    write_clone_plan_markdown,
)

__all__ = [
    # Decision constants
    "DECISION_DIRECT_CLONE",
    "DECISION_EXTERNAL_EXTENSION",
    "DECISION_ARCHITECTURE_REFERENCE",
    "DECISION_REJECT",
    "DECISIONS",
    # Priority constants
    "PRIORITY_S",
    "PRIORITY_A",
    "PRIORITY_B",
    "PRIORITY_C",
    "PRIORITY_D",
    "PRIORITIES",
    # Intent constants
    "INTENDED_USE_CLAUDE_CODE",
    "INTENDED_USE_SYSTEMKERNEL",
    "INTENDED_USE_ARCHITECTURE",
    "INTENDED_USE_UNKNOWN",
    # Data classes
    "RepoIntakeInput",
    "RepoSignals",
    "RepoIntakeDecision",
    "RepoIntakeReport",
    "IntakeRule",
    "RepoProfile",
    # Analysis
    "analyze_local_repo",
    "analyze_repo_snapshot",
    "decide_repo_intake",
    "compute_report_hash",
    "write_report",
    # Rules
    "INTAKE_RULES",
    "apply_rules",
    "classify_repo_type",
    "get_rules_table",
    # Repo types
    "REPO_TYPE_AGENT_RUNTIME",
    "REPO_TYPE_MEMORY_SYSTEM",
    "REPO_TYPE_OBSERVABILITY_TOOL",
    "REPO_TYPE_CLAUDE_CODE_EXTENSION",
    "REPO_TYPE_SKILL_SYSTEM",
    "REPO_TYPE_CONTEXT_TOOL",
    "REPO_TYPE_DOCS_ONLY",
    "REPO_TYPE_UNKNOWN",
    "REPO_TYPES",
    # Profiles
    "PROFILES",
    "get_profile",
    "list_profiles",
    "get_all_profiles",
    # Tool Registry
    "ExternalToolEntry",
    "ExternalToolRegistry",
    "build_registry_from_intake_reports",
    "build_registry_from_profiles",
    "recommend_clone_order",
    "write_registry",
    "write_clone_plan",
    "USE_MODE_DIRECT_TOOL",
    "USE_MODE_SOURCE_REFERENCE",
    "USE_MODE_EXTERNAL_SERVICE",
    "USE_MODE_FORMAT_REFERENCE",
    "USE_MODE_ARCHITECTURE_REFERENCE",
    "USE_MODES",
    "CLONE_NOW",
    "INSPECT_ONLY",
    "EXTERNAL_EVAL",
    "REFERENCE_ONLY",
    # Clone Plan
    "ClonePlanItem",
    "ClonePlan",
    "create_clone_plan",
    "filter_clone_now",
    "summarize_plan",
    "write_clone_plan_markdown",
    "POST_CLONE_INSPECT_ONLY",
    "POST_CLONE_RUN_CLI_HELP",
    "POST_CLONE_READ_DOCS",
    "POST_CLONE_EVALUATE_EXTERNAL",
    "POST_CLONE_EXTRACT_FORMAT",
    "POST_CLONE_NONE",
    "POST_CLONE_ACTIONS",
]
```

## File: clone_plan.py
```python
"""
Clone Plan — Safe, auditable clone plan for external repositories.

Translates ExternalToolRegistry entries into ClonePlanItems with
explicit post-clone actions and forbidden post-clone actions.

Key safety rules:
  - DIRECT_CLONE does NOT mean "integrate into kernel"
  - Large application repos (AppFlowy, JupyterLab) → inspect_only
  - External service repos → evaluate_external_service (no local install)
  - Architecture references → NOT cloned at all

Zero network. Zero clone. Plan only.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Post-clone action constants
# ═══════════════════════════════════════════════════════════════════════

POST_CLONE_INSPECT_ONLY = "inspect_only"
POST_CLONE_RUN_CLI_HELP = "run_cli_help"
POST_CLONE_READ_DOCS = "read_docs"
POST_CLONE_EVALUATE_EXTERNAL = "evaluate_external_service"
POST_CLONE_EXTRACT_FORMAT = "extract_format_reference"
POST_CLONE_NONE = "none"

POST_CLONE_ACTIONS = (
    POST_CLONE_INSPECT_ONLY,
    POST_CLONE_RUN_CLI_HELP,
    POST_CLONE_READ_DOCS,
    POST_CLONE_EVALUATE_EXTERNAL,
    POST_CLONE_EXTRACT_FORMAT,
    POST_CLONE_NONE,
)


# ═══════════════════════════════════════════════════════════════════════
# ClonePlanItem
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ClonePlanItem:
    """One item in a clone plan.

    Fields:
        name: Repository name
        repo_url: GitHub URL
        target_path: Where to clone (F:/Claude/Github/...)
        priority: S | A | B | C | D
        clone_now: Whether to clone now (True for direct_tool + format_reference)
        reason: Why this item is in the plan
        post_clone_action: What to do after cloning
        forbidden_post_clone_actions: What NOT to do after cloning
    """

    name: str
    repo_url: str = ""
    target_path: str = ""
    priority: str = "D"
    clone_now: bool = False
    reason: str = ""
    post_clone_action: str = POST_CLONE_NONE
    forbidden_post_clone_actions: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "repo_url": self.repo_url,
            "target_path": self.target_path,
            "priority": self.priority,
            "clone_now": self.clone_now,
            "reason": self.reason,
            "post_clone_action": self.post_clone_action,
            "forbidden_post_clone_actions": list(self.forbidden_post_clone_actions),
        }


# ═══════════════════════════════════════════════════════════════════════
# ClonePlan
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ClonePlan:
    """Complete clone plan for external repositories.

    Fields:
        root_dir: Root directory for clones (F:/Claude/Github/)
        items: All plan items
        plan_hash: Deterministic hash of the plan
        safety_notes: Human-readable safety notes
    """

    root_dir: str = "F:\\Claude\\Github"
    items: Tuple[ClonePlanItem, ...] = ()
    plan_hash: str = ""
    safety_notes: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "root_dir": self.root_dir,
            "items": [item.to_dict() for item in self.items],
            "plan_hash": self.plan_hash,
            "safety_notes": list(self.safety_notes),
            "summary": {
                "total": len(self.items),
                "clone_now": sum(1 for i in self.items if i.clone_now),
                "inspect_only": sum(1 for i in self.items
                                    if i.post_clone_action == POST_CLONE_INSPECT_ONLY),
                "external_eval": sum(1 for i in self.items
                                     if i.post_clone_action == POST_CLONE_EVALUATE_EXTERNAL),
                "reference_only": sum(1 for i in self.items
                                      if i.post_clone_action == POST_CLONE_NONE),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def create_clone_plan(registry, root_dir: str = "F:\\Claude\\Github") -> ClonePlan:
    """Create a clone plan from an ExternalToolRegistry.

    Maps use_mode to clone decisions and post-clone actions:

      direct_tool        → clone_now=True,  post: run_cli_help
      format_reference   → clone_now=True,  post: extract_format_reference
      source_reference   → clone_now=False, post: inspect_only
      external_service   → clone_now=False, post: evaluate_external_service
      architecture_ref   → clone_now=False, post: none (not cloned)
    """
    items = []
    safety_notes = [
        "PLAN ONLY — no actual cloning is performed by this module.",
        "DIRECT_CLONE repos are external tools, NOT kernel modules.",
        "Large application repos (AppFlowy, JupyterLab) are inspect-only despite DIRECT_CLONE decision.",
        "External service repos must NOT be installed locally without review.",
        "Architecture reference repos are NOT cloned at all.",
        "All clones target F:/Claude/Github/ — outside the kernel boundary.",
        "No repo may be integrated into the kernel without a separate audit.",
    ]

    for entry in registry.entries:
        use_mode = entry.use_mode

        if use_mode == "direct_tool":
            clone_now = True
            post_action = POST_CLONE_RUN_CLI_HELP
            reason = f"Direct CLI tool — clone for local use. CC value={entry.claude_code_value}/10."
            forbidden = (
                "do_not_integrate_into_kernel",
                "do_not_modify_kernel_boundary",
                "do_not_embed_as_kernel_module",
            )
        elif use_mode == "format_reference":
            clone_now = True
            post_action = POST_CLONE_EXTRACT_FORMAT
            reason = "Format reference — clone to study file formats and conventions."
            forbidden = (
                "do_not_integrate_into_kernel",
                "do_not_execute_skills_directly",
                "do_not_embed_as_kernel_module",
            )
        elif use_mode == "source_reference":
            clone_now = False
            post_action = POST_CLONE_INSPECT_ONLY
            reason = "Large application — inspect source code for design patterns only."
            forbidden = (
                "do_not_run_as_dependency",
                "do_not_integrate_into_kernel",
                "do_not_modify_kernel_boundary",
                "do_not_execute_without_review",
            )
        elif use_mode == "external_service":
            clone_now = False
            post_action = POST_CLONE_EVALUATE_EXTERNAL
            reason = f"External service — evaluate via API only. Risk={entry.kernel_risk}/10."
            forbidden = (
                "do_not_import_directly",
                "do_not_install_locally_without_review",
                "do_not_integrate_into_kernel",
                "do_not_modify_kernel_boundary",
            )
        else:
            clone_now = False
            post_action = POST_CLONE_NONE
            reason = "Architecture reference only — not cloned. Study design patterns from documentation."
            forbidden = (
                "do_not_clone",
                "do_not_import",
                "do_not_integrate",
                "do_not_run_as_dependency",
            )

        item = ClonePlanItem(
            name=entry.name,
            repo_url=entry.repo_url,
            target_path=entry.target_dir if clone_now else "",
            priority=entry.priority,
            clone_now=clone_now,
            reason=reason,
            post_clone_action=post_action,
            forbidden_post_clone_actions=forbidden,
        )
        items.append(item)

    # Deterministic hash
    hash_input = json.dumps(
        [i.to_dict() for i in items], sort_keys=True, ensure_ascii=False)
    plan_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return ClonePlan(
        root_dir=root_dir,
        items=tuple(items),
        plan_hash=plan_hash,
        safety_notes=tuple(safety_notes),
    )


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def filter_clone_now(plan: ClonePlan) -> list:
    """Return only items marked clone_now=True."""
    return [i for i in plan.items if i.clone_now]


def summarize_plan(plan: ClonePlan) -> str:
    """Return a human-readable summary of the clone plan."""
    lines = [
        "=" * 60,
        "  Clone Plan Summary",
        "=" * 60,
        f"",
        f"  Root directory:  {plan.root_dir}",
        f"  Plan hash:       {plan.plan_hash}",
        f"  Total items:     {len(plan.items)}",
        f"",
    ]

    clone_now = [i for i in plan.items if i.clone_now]
    inspect = [i for i in plan.items if i.post_clone_action == POST_CLONE_INSPECT_ONLY]
    ext_eval = [i for i in plan.items if i.post_clone_action == POST_CLONE_EVALUATE_EXTERNAL]
    ref_only = [i for i in plan.items if i.post_clone_action == POST_CLONE_NONE]

    if clone_now:
        lines.append(f"  Clone Now ({len(clone_now)}):")
        for item in clone_now:
            lines.append(f"    [{item.priority}] {item.name} → {item.target_path}")
            lines.append(f"          Action: {item.post_clone_action}")
        lines.append("")

    if inspect:
        lines.append(f"  Inspect Only ({len(inspect)}):")
        for item in inspect:
            lines.append(f"    [{item.priority}] {item.name}")
            lines.append(f"          Action: {item.post_clone_action}")
        lines.append("")

    if ext_eval:
        lines.append(f"  External Evaluation ({len(ext_eval)}):")
        for item in ext_eval:
            lines.append(f"    [{item.priority}] {item.name}")
            lines.append(f"          Action: {item.post_clone_action}")
        lines.append("")

    if ref_only:
        lines.append(f"  Reference Only ({len(ref_only)}):")
        for item in ref_only:
            lines.append(f"    [{item.priority}] {item.name}")
        lines.append("")

    lines.append("  Safety Notes:")
    for note in plan.safety_notes:
        lines.append(f"    - {note}")

    return "\n".join(lines)


def write_clone_plan_markdown(plan: ClonePlan, path: str) -> str:
    """Write the clone plan as a Markdown file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    md = []
    md.append("# SystemKernel v3.0 — GitHub Clone Plan")
    md.append("")
    md.append("> **PLAN ONLY** — No actual cloning is performed by this module.")
    md.append("> All items require manual review before execution.")
    md.append("")
    md.append(f"- **Root directory:** `{plan.root_dir}`")
    md.append(f"- **Plan hash:** `{plan.plan_hash}`")
    md.append(f"- **Total items:** {len(plan.items)}")
    md.append("")

    # Clone Now
    clone_now = [i for i in plan.items if i.clone_now]
    if clone_now:
        md.append("## Clone Now")
        md.append("")
        md.append("| Priority | Repository | Target Path | Post-Clone Action |")
        md.append("|----------|------------|-------------|-------------------|")
        for item in clone_now:
            md.append(f"| {item.priority} | {item.name} | `{item.target_path}` | {item.post_clone_action} |")
        md.append("")
        for item in clone_now:
            md.append(f"### {item.name}")
            md.append(f"- **URL:** {item.repo_url}")
            md.append(f"- **Reason:** {item.reason}")
            md.append(f"- **Post-clone:** `{item.post_clone_action}`")
            forbidden = ", ".join(item.forbidden_post_clone_actions)
            md.append(f"- **Forbidden:** {forbidden}")
            md.append("")

    # Inspect Only
    inspect = [i for i in plan.items if i.post_clone_action == POST_CLONE_INSPECT_ONLY]
    if inspect:
        md.append("## Inspect Only")
        md.append("")
        md.append("| Priority | Repository | Post-Clone Action |")
        md.append("|----------|------------|-------------------|")
        for item in inspect:
            md.append(f"| {item.priority} | {item.name} | {item.post_clone_action} |")
        md.append("")
        for item in inspect:
            md.append(f"### {item.name}")
            md.append(f"- **URL:** {item.repo_url}")
            md.append(f"- **Reason:** {item.reason}")
            forbidden = ", ".join(item.forbidden_post_clone_actions)
            md.append(f"- **Forbidden:** {forbidden}")
            md.append("")

    # External Evaluation
    ext_eval = [i for i in plan.items if i.post_clone_action == POST_CLONE_EVALUATE_EXTERNAL]
    if ext_eval:
        md.append("## External Service Evaluation")
        md.append("")
        md.append("| Priority | Repository | Post-Clone Action |")
        md.append("|----------|------------|-------------------|")
        for item in ext_eval:
            md.append(f"| {item.priority} | {item.name} | {item.post_clone_action} |")
        md.append("")
        for item in ext_eval:
            md.append(f"### {item.name}")
            md.append(f"- **URL:** {item.repo_url}")
            md.append(f"- **Reason:** {item.reason}")
            forbidden = ", ".join(item.forbidden_post_clone_actions)
            md.append(f"- **Forbidden:** {forbidden}")
            md.append("")

    # Reference Only
    ref_only = [i for i in plan.items if i.post_clone_action == POST_CLONE_NONE]
    if ref_only:
        md.append("## Architecture Reference Only")
        md.append("")
        md.append("| Priority | Repository |")
        md.append("|----------|------------|")
        for item in ref_only:
            md.append(f"| {item.priority} | {item.name} |")
        md.append("")
        for item in ref_only:
            md.append(f"### {item.name}")
            md.append(f"- **URL:** {item.repo_url}")
            md.append(f"- **Reason:** {item.reason}")
            md.append("")

    # Safety notes
    md.append("## Safety Notes")
    md.append("")
    for note in plan.safety_notes:
        md.append(f"- {note}")

    md.append("")

    content = "\n".join(md)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return os.path.abspath(path)
```

## File: repo_intake.py
```python
"""
Repo Intake Pipeline — Deterministic repository assessment.

Evaluates whether an external repo should be:
  - DIRECT_CLONE — cloned into F:/Claude/Github for active use
  - EXTERNAL_EXTENSION — used as external service/extension
  - ARCHITECTURE_REFERENCE — studied for design patterns only
  - REJECT — not suitable for any integration

Zero network. Zero git clone. Analyzes metadata, signals, and synthetic snapshots.
All scoring is deterministic. Reports carry stable hashes.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Decision constants
# ═══════════════════════════════════════════════════════════════════════

DECISION_DIRECT_CLONE = "DIRECT_CLONE"
DECISION_EXTERNAL_EXTENSION = "EXTERNAL_EXTENSION"
DECISION_ARCHITECTURE_REFERENCE = "ARCHITECTURE_REFERENCE"
DECISION_REJECT = "REJECT"

DECISIONS = (DECISION_DIRECT_CLONE, DECISION_EXTERNAL_EXTENSION,
             DECISION_ARCHITECTURE_REFERENCE, DECISION_REJECT)

PRIORITY_S = "S"
PRIORITY_A = "A"
PRIORITY_B = "B"
PRIORITY_C = "C"
PRIORITY_D = "D"

PRIORITIES = (PRIORITY_S, PRIORITY_A, PRIORITY_B, PRIORITY_C, PRIORITY_D)

INTENDED_USE_CLAUDE_CODE = "claude_code_enhancement"
INTENDED_USE_SYSTEMKERNEL = "systemkernel_extension"
INTENDED_USE_ARCHITECTURE = "architecture_reference"
INTENDED_USE_UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════
# RepoIntakeInput
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RepoIntakeInput:
    """Input for repo intake assessment.

    Fields:
        name: Repository name (e.g. "LangGraph")
        url: GitHub URL or identifier
        local_path: Optional local filesystem path if already cloned
        category_hint: Optional category hint for classification
        intended_use: How the developer intends to use this repo
    """

    name: str = ""
    url: str = ""
    local_path: str = ""
    category_hint: str = ""
    intended_use: str = INTENDED_USE_UNKNOWN

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "local_path": self.local_path,
            "category_hint": self.category_hint,
            "intended_use": self.intended_use,
        }


# ═══════════════════════════════════════════════════════════════════════
# RepoSignals
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RepoSignals:
    """Detected signals from repo metadata / snapshot analysis.

    Fields:
        has_readme: README.md or similar found
        has_license: LICENSE file found
        language_hints: Detected languages (e.g. ["python", "typescript"])
        dependency_files: Found dependency manifests (requirements.txt, package.json, etc.)
        has_cli: CLI entry point detected
        has_mcp: MCP (Model Context Protocol) integration detected
        has_plugin_manifest: Plugin/system manifest found
        has_skill_manifest: Skill definition found
        has_tests: Test directory or test files found
        has_docs: Documentation directory found
        has_examples: Examples directory found
        banned_dependency_hits: Count of banned kernel dependencies
        heavy_dependency_hits: Count of heavy framework dependencies
        llm_dependency_hits: Count of LLM SDK dependencies
        memory_dependency_hits: Count of memory/vector DB dependencies
        framework_dependency_hits: Count of agent framework dependencies
        kernel_risk_flags: List of kernel integrity risk indicators
    """

    has_readme: bool = False
    has_license: bool = False
    language_hints: Tuple[str, ...] = ()
    dependency_files: Tuple[str, ...] = ()
    has_cli: bool = False
    has_mcp: bool = False
    has_plugin_manifest: bool = False
    has_skill_manifest: bool = False
    has_tests: bool = False
    has_docs: bool = False
    has_examples: bool = False
    banned_dependency_hits: int = 0
    heavy_dependency_hits: int = 0
    llm_dependency_hits: int = 0
    memory_dependency_hits: int = 0
    framework_dependency_hits: int = 0
    kernel_risk_flags: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "has_readme": self.has_readme,
            "has_license": self.has_license,
            "language_hints": list(self.language_hints),
            "dependency_files": list(self.dependency_files),
            "has_cli": self.has_cli,
            "has_mcp": self.has_mcp,
            "has_plugin_manifest": self.has_plugin_manifest,
            "has_skill_manifest": self.has_skill_manifest,
            "has_tests": self.has_tests,
            "has_docs": self.has_docs,
            "has_examples": self.has_examples,
            "banned_dependency_hits": self.banned_dependency_hits,
            "heavy_dependency_hits": self.heavy_dependency_hits,
            "llm_dependency_hits": self.llm_dependency_hits,
            "memory_dependency_hits": self.memory_dependency_hits,
            "framework_dependency_hits": self.framework_dependency_hits,
            "kernel_risk_flags": list(self.kernel_risk_flags),
        }


# ═══════════════════════════════════════════════════════════════════════
# RepoIntakeDecision
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RepoIntakeDecision:
    """Decision output of repo intake assessment.

    Fields:
        decision: DIRECT_CLONE | EXTERNAL_EXTENSION | ARCHITECTURE_REFERENCE | REJECT
        priority: S | A | B | C | D
        claude_code_value_score: Value for Claude Code enhancement (0-10)
        systemkernel_value_score: Value for SystemKernel extension (0-10)
        complexity_risk_score: Risk of adding complexity (0-10, lower is better)
        purity_risk_score: Risk to kernel purity (0-10, lower is better)
        maintenance_risk_score: Maintenance burden risk (0-10, lower is better)
        final_score: Composite score (higher = better candidate)
        reasons: Human-readable reasons for the decision
        recommended_target_dir: Where to place the repo if cloned
        allowed_actions: What the developer may do with this repo
        forbidden_actions: What the developer must NOT do with this repo
    """

    decision: str = DECISION_REJECT
    priority: str = PRIORITY_D
    claude_code_value_score: float = 0.0
    systemkernel_value_score: float = 0.0
    complexity_risk_score: float = 10.0
    purity_risk_score: float = 10.0
    maintenance_risk_score: float = 10.0
    final_score: float = 0.0
    reasons: Tuple[str, ...] = ()
    recommended_target_dir: str = ""
    allowed_actions: Tuple[str, ...] = ()
    forbidden_actions: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "priority": self.priority,
            "claude_code_value_score": self.claude_code_value_score,
            "systemkernel_value_score": self.systemkernel_value_score,
            "complexity_risk_score": self.complexity_risk_score,
            "purity_risk_score": self.purity_risk_score,
            "maintenance_risk_score": self.maintenance_risk_score,
            "final_score": round(self.final_score, 2),
            "reasons": list(self.reasons),
            "recommended_target_dir": self.recommended_target_dir,
            "allowed_actions": list(self.allowed_actions),
            "forbidden_actions": list(self.forbidden_actions),
        }

    @property
    def is_direct_clone(self) -> bool:
        return self.decision == DECISION_DIRECT_CLONE

    @property
    def is_external(self) -> bool:
        return self.decision == DECISION_EXTERNAL_EXTENSION

    @property
    def is_reference(self) -> bool:
        return self.decision == DECISION_ARCHITECTURE_REFERENCE

    @property
    def is_rejected(self) -> bool:
        return self.decision == DECISION_REJECT


# ═══════════════════════════════════════════════════════════════════════
# RepoIntakeReport
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RepoIntakeReport:
    """Full intake report combining input, signals, and decision.

    Fields:
        input: Original RepoIntakeInput
        signals: Detected RepoSignals
        decision: Computed RepoIntakeDecision
        report_hash: Deterministic hash of the entire report
    """

    input: RepoIntakeInput = field(default_factory=RepoIntakeInput)
    signals: RepoSignals = field(default_factory=RepoSignals)
    decision: RepoIntakeDecision = field(default_factory=RepoIntakeDecision)
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "input": self.input.to_dict(),
            "signals": self.signals.to_dict(),
            "decision": self.decision.to_dict(),
            "report_hash": self.report_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Analysis: local repo
# ═══════════════════════════════════════════════════════════════════════

def analyze_local_repo(path: str) -> RepoSignals:
    """Analyze a locally-cloned repository and extract signals.

    Does NOT execute any code. Only inspects file structure.
    Deterministic for the same filesystem state.
    """
    if not os.path.isdir(path):
        return RepoSignals()

    files = set()
    for root_dir, dirs, filenames in os.walk(path):
        # Skip hidden dirs and common ignores
        dirs[:] = [d for d in dirs if not d.startswith(".")
                    and d not in ("node_modules", "__pycache__", ".git",
                                  "venv", ".venv", "dist", "build")]
        for fn in filenames:
            files.add(fn.lower())

    has_readme = any(f.startswith("readme") for f in files)
    has_license = any("license" in f for f in files)

    # Language hints
    lang_hints = []
    if any(f.endswith(".py") for f in files):
        lang_hints.append("python")
    if any(f.endswith((".ts", ".tsx")) for f in files):
        lang_hints.append("typescript")
    if any(f.endswith((".js", ".jsx")) for f in files):
        lang_hints.append("javascript")
    if any(f.endswith(".rs") for f in files):
        lang_hints.append("rust")
    if any(f.endswith(".go") for f in files):
        lang_hints.append("go")

    # Dependency files
    dep_files = []
    dep_patterns = [
        "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
        "package.json", "cargo.toml", "go.mod", "pom.xml", "build.gradle",
        "gemfile", "composer.json",
    ]
    for dp in dep_patterns:
        if dp in files:
            dep_files.append(dp)

    # Structural signals
    has_cli = "cli" in set(os.path.basename(root_dir).lower()
                           for root_dir, _, _ in os.walk(path)
                           if root_dir != path) or any("cli" in f for f in files)
    has_mcp = any("mcp" in f for f in files)
    has_plugin = any("manifest" in f for f in files)
    has_skill = any("skill" in f for f in files)

    has_tests = any(d == "tests" or d == "test"
                    for root_dir, dirs, _ in os.walk(path)
                    for d in dirs)
    has_docs = any(d in ("docs", "doc", "documentation")
                   for root_dir, dirs, _ in os.walk(path)
                   for d in dirs)
    has_examples = any(d in ("examples", "example", "demo")
                       for root_dir, dirs, _ in os.walk(path)
                       for d in dirs)

    return RepoSignals(
        has_readme=has_readme,
        has_license=has_license,
        language_hints=tuple(sorted(set(lang_hints))),
        dependency_files=tuple(sorted(set(dep_files))),
        has_cli=has_cli,
        has_mcp=has_mcp,
        has_plugin_manifest=has_plugin,
        has_skill_manifest=has_skill,
        has_tests=has_tests,
        has_docs=has_docs,
        has_examples=has_examples,
    )


# ═══════════════════════════════════════════════════════════════════════
# Analysis: snapshot (synthetic files dict)
# ═══════════════════════════════════════════════════════════════════════

def analyze_repo_snapshot(
    name: str,
    url: str,
    files: dict,
    *,
    known_dependencies: Optional[list] = None,
) -> RepoSignals:
    """Analyze a synthetic repo snapshot from a dict of filename→content.

    Useful for testing and for pre-built profiles without network access.

    Args:
        name: Repo name
        url: Repo URL
        files: Dict mapping relative paths (e.g. "README.md") to file content
        known_dependencies: Optional list of known dependency names

    Returns:
        RepoSignals with all detectable signals.
    """
    file_names = set(f.lower() for f in files.keys())
    dir_names = set()
    for f in files.keys():
        parts = f.lower().replace("\\", "/").split("/")
        for i in range(len(parts) - 1):
            dir_names.add(parts[i])

    # Basic signals
    has_readme = any(f.startswith("readme") for f in file_names)
    has_license = any("license" in f for f in file_names)

    # Language hints from file extensions
    lang_hints = []
    ext_map = {
        ".py": "python", ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
        ".rs": "rust", ".go": "go", ".java": "java",
        ".rb": "ruby", ".php": "php",
    }
    for fn in file_names:
        for ext, lang in ext_map.items():
            if fn.endswith(ext):
                lang_hints.append(lang)
                break

    # Dependency files
    dep_files = []
    dep_patterns = [
        "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
        "package.json", "cargo.toml", "go.mod",
    ]
    for dp in dep_patterns:
        if dp in file_names:
            dep_files.append(dp)

    # Structural signals from directory names
    has_cli = "cli" in dir_names or any("cli" in f for f in file_names)
    has_mcp = "mcp" in dir_names or any("mcp" in f for f in file_names)
    has_plugin = any("manifest" in f for f in file_names)
    has_skill = any("skill" in f for f in file_names)
    has_tests = "tests" in dir_names or "test" in dir_names
    has_docs = "docs" in dir_names or "doc" in dir_names
    has_examples = "examples" in dir_names or "example" in dir_names or "demo" in dir_names

    # Dependency analysis from content
    deps = set(known_dependencies or [])
    # Scan dependency files for well-known packages
    for fn in file_names:
        if fn in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"):
            content = files.get(fn, files.get(list(files.keys())[0], ""))
            deps.update(_extract_python_deps(content))
        elif fn == "package.json":
            content = files.get(fn, "")
            deps.update(_extract_node_deps(content))

    # Classify dependencies
    banned = _classify_dependencies(deps)

    return RepoSignals(
        has_readme=has_readme,
        has_license=has_license,
        language_hints=tuple(sorted(set(lang_hints))),
        dependency_files=tuple(sorted(set(dep_files))),
        has_cli=has_cli,
        has_mcp=has_mcp,
        has_plugin_manifest=has_plugin,
        has_skill_manifest=has_skill,
        has_tests=has_tests,
        has_docs=has_docs,
        has_examples=has_examples,
        banned_dependency_hits=banned["banned"],
        heavy_dependency_hits=banned["heavy"],
        llm_dependency_hits=banned["llm"],
        memory_dependency_hits=banned["memory"],
        framework_dependency_hits=banned["framework"],
        kernel_risk_flags=tuple(banned["flags"]),
    )


def _extract_python_deps(content: str) -> list:
    """Extract python dependency names from requirements.txt / pyproject.toml content."""
    deps = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        # requirements.txt: package==version or package>=version
        pkg = line.split("==")[0].split(">=")[0].split("<")[0].split("~=")[0].strip()
        if pkg and not pkg.startswith("-"):
            deps.append(pkg.lower())
    return deps


def _extract_node_deps(content: str) -> list:
    """Extract node dependency names from package.json content."""
    deps = []
    try:
        data = json.loads(content)
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for pkg in data.get(section, {}):
                deps.append(pkg.lower())
    except (json.JSONDecodeError, TypeError):
        pass
    return deps


def _classify_dependencies(deps: set) -> dict:
    """Classify dependencies into risk categories.

    Returns:
        dict with counts for banned, heavy, llm, memory, framework, and flags.
    """
    banned_kernel = {
        "openai", "anthropic", "langchain", "langchain-core", "langchain-community",
        "llamaindex", "chromadb", "qdrant", "qdrant-client",
        "pinecone", "pinecone-client", "weaviate", "weaviate-client", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "scipy", "sklearn",
    }
    heavy = {
        "torch", "tensorflow", "jax", "pyspark", "ray",
        "kubernetes", "docker", "grpcio", "neo4j",
    }
    llm = {
        "openai", "anthropic", "langchain", "langchain-core", "langchain-community",
        "llamaindex", "crewai", "autogen", "semantic-kernel",
        "transformers", "sentence_transformers",
    }
    memory = {
        "chromadb", "qdrant", "qdrant-client", "pinecone", "pinecone-client",
        "weaviate", "weaviate-client", "milvus",
        "mem0", "graphiti", "pgvector", "elasticsearch",
        "redis", "lancedb",
    }
    framework = {
        "langchain", "langchain-core", "langchain-community",
        "crewai", "autogen", "semantic-kernel",
        "dspy", "haystack", "langflow",
    }

    flags = []
    banned_count = 0
    heavy_count = 0
    llm_count = 0
    memory_count = 0
    framework_count = 0

    for dep in deps:
        dep_lower = dep.lower()
        if dep_lower in banned_kernel:
            banned_count += 1
            flags.append(f"BANNED_DEP:{dep_lower}")
        if dep_lower in heavy:
            heavy_count += 1
            flags.append(f"HEAVY_DEP:{dep_lower}")
        if dep_lower in llm:
            llm_count += 1
            flags.append(f"LLM_DEP:{dep_lower}")
        if dep_lower in memory:
            memory_count += 1
            flags.append(f"MEMORY_DEP:{dep_lower}")
        if dep_lower in framework:
            framework_count += 1
            flags.append(f"FRAMEWORK_DEP:{dep_lower}")

    return {
        "banned": banned_count,
        "heavy": heavy_count,
        "llm": llm_count,
        "memory": memory_count,
        "framework": framework_count,
        "flags": tuple(sorted(set(flags))),
    }


# ═══════════════════════════════════════════════════════════════════════
# Scoring Engine
# ═══════════════════════════════════════════════════════════════════════

def decide_repo_intake(
    inp: RepoIntakeInput,
    signals: RepoSignals,
) -> RepoIntakeDecision:
    """Compute intake decision from input and signals.

    Scoring model (deterministic):

    Claude Code value (0-10):
      +2  has_readme
      +2  has_cli
      +2  has_mcp
      +1  has_skill_manifest
      +1  has_examples
      +1  has_tests
      +1  has_docs
      -2  banned_dependency_hits
      -1  heavy_dependency_hits

    SystemKernel value (0-10):
      +2  has_plugin_manifest
      +2  has_tests
      +2  has_license
      +1  has_readme
      +1  has_docs
      +1  has_examples
      -2  llm_dependency_hits
      -2  framework_dependency_hits
      -1  memory_dependency_hits

    Risk scores (0-10, 10 = highest risk, 0 = no risk):
      complexity_risk = heavy_deps*2 + framework_deps*1.5 + (not has_readme)*2
      purity_risk = banned_deps*3 + llm_deps*2 + framework_deps*1
      maintenance_risk = (not has_license)*3 + heavy_deps*1.5 + (not has_tests)*2

    Decision logic:
      - REJECT: banned_deps > 0 AND no license AND no readme
      - ARCHITECTURE_REFERENCE: framework_deps >= 2 OR llm_deps >= 2
      - EXTERNAL_EXTENSION: memory_deps > 0 OR heavy_deps > 0
      - DIRECT_CLONE: low risk + high value + has_readme + has_license
    """
    reasons = []

    # ── Value scores ──
    cc_value = 5.0
    if signals.has_readme:    cc_value += 2.0
    if signals.has_cli:       cc_value += 2.0
    if signals.has_mcp:       cc_value += 2.0
    if signals.has_skill_manifest: cc_value += 1.0
    if signals.has_examples:  cc_value += 1.0
    if signals.has_tests:     cc_value += 1.0
    if signals.has_docs:      cc_value += 1.0
    cc_value -= signals.banned_dependency_hits * 2.0
    cc_value -= signals.heavy_dependency_hits * 1.0
    cc_value = max(0.0, min(10.0, cc_value))

    sk_value = 5.0
    if signals.has_plugin_manifest: sk_value += 2.0
    if signals.has_tests:     sk_value += 2.0
    if signals.has_license:   sk_value += 2.0
    if signals.has_readme:    sk_value += 1.0
    if signals.has_docs:      sk_value += 1.0
    if signals.has_examples:  sk_value += 1.0
    sk_value -= signals.llm_dependency_hits * 2.0
    sk_value -= signals.framework_dependency_hits * 2.0
    sk_value -= signals.memory_dependency_hits * 1.0
    sk_value = max(0.0, min(10.0, sk_value))

    # ── Risk scores (0=best, 10=worst) ──
    complexity_risk = 0.0
    complexity_risk += signals.heavy_dependency_hits * 2.0
    complexity_risk += signals.framework_dependency_hits * 1.5
    if not signals.has_readme:
        complexity_risk += 2.0
    if signals.banned_dependency_hits > 0:
        complexity_risk += 1.0
    complexity_risk = min(10.0, complexity_risk)

    purity_risk = 0.0
    purity_risk += signals.banned_dependency_hits * 3.0
    purity_risk += signals.llm_dependency_hits * 2.0
    purity_risk += signals.framework_dependency_hits * 1.0
    purity_risk = min(10.0, purity_risk)

    maintenance_risk = 0.0
    if not signals.has_license:
        maintenance_risk += 3.0
    maintenance_risk += signals.heavy_dependency_hits * 1.5
    if not signals.has_tests:
        maintenance_risk += 2.0
    if not signals.has_readme:
        maintenance_risk += 1.0
    maintenance_risk = min(10.0, maintenance_risk)

    # ── Decision logic ──
    decision = DECISION_REJECT

    # Auto-reject: banned deps + no license + no readme = too risky
    if signals.banned_dependency_hits >= 2 and not signals.has_license and not signals.has_readme:
        decision = DECISION_REJECT
        reasons.append("HIGH_RISK: multiple banned deps, no license, no readme")

    # Auto-reject: no readme AND no files at all
    if not signals.has_readme and not signals.language_hints and not signals.dependency_files:
        decision = DECISION_REJECT
        reasons.append("NO_CONTENT: no readme, no code signals, no dependency files")

    if decision == DECISION_REJECT and not reasons:
        # Not auto-rejected — evaluate based on dependency signals
        if signals.framework_dependency_hits >= 1:
            decision = DECISION_ARCHITECTURE_REFERENCE
            reasons.append("ARCHITECTURE_REFERENCE: agent framework dependencies detected")
        elif signals.llm_dependency_hits >= 1:
            decision = DECISION_EXTERNAL_EXTENSION
            reasons.append("EXTERNAL_EXTENSION: LLM SDK dependencies detected")
        elif signals.memory_dependency_hits > 0 or signals.heavy_dependency_hits > 0:
            decision = DECISION_EXTERNAL_EXTENSION
            reasons.append("EXTERNAL_EXTENSION: memory/heavy deps require external deployment")
        elif signals.banned_dependency_hits > 0:
            decision = DECISION_ARCHITECTURE_REFERENCE
            reasons.append("ARCHITECTURE_REFERENCE: banned kernel dependencies detected")
        elif (cc_value >= 7.0 or sk_value >= 7.0) and signals.has_readme and signals.has_license:
            decision = DECISION_DIRECT_CLONE
            reasons.append("DIRECT_CLONE: high value, well-documented, low risk")
        elif signals.has_readme and signals.has_license:
            decision = DECISION_EXTERNAL_EXTENSION
            reasons.append("EXTERNAL_EXTENSION: documented but moderate value")
        else:
            decision = DECISION_ARCHITECTURE_REFERENCE
            reasons.append("ARCHITECTURE_REFERENCE: insufficient documentation or value signals")

    # ── Priority ──
    if decision == DECISION_DIRECT_CLONE:
        if cc_value >= 8.0 and sk_value >= 6.0:
            priority = PRIORITY_S
        elif cc_value >= 7.0:
            priority = PRIORITY_A
        else:
            priority = PRIORITY_B
    elif decision == DECISION_EXTERNAL_EXTENSION:
        priority = PRIORITY_B if cc_value >= 5.0 else PRIORITY_C
    elif decision == DECISION_ARCHITECTURE_REFERENCE:
        priority = PRIORITY_C if signals.has_readme else PRIORITY_D
    else:
        priority = PRIORITY_D

    # ── Final score ──
    final_score = (cc_value + sk_value) / 2.0 - (complexity_risk + purity_risk) / 4.0
    final_score = max(0.0, round(final_score, 2))

    # ── Target dir ──
    if decision == DECISION_DIRECT_CLONE:
        target = f"F:/Claude/Github/{inp.name.lower().replace(' ', '-')}"
    elif decision == DECISION_EXTERNAL_EXTENSION:
        target = f"F:/Claude/Github/_extensions/{inp.name.lower().replace(' ', '-')}"
    elif decision == DECISION_ARCHITECTURE_REFERENCE:
        target = f"F:/Claude/Reference/{inp.name.lower().replace(' ', '-')}"
    else:
        target = ""

    # ── Allowed / forbidden actions ──
    allowed = []
    forbidden = []

    if decision == DECISION_DIRECT_CLONE:
        allowed = ("clone_to_github", "import_as_extension", "run_locally", "study_architecture")
        forbidden = ("modify_kernel_for_integration", "embed_as_kernel_module")
    elif decision == DECISION_EXTERNAL_EXTENSION:
        allowed = ("clone_to_github_extensions", "run_as_external_service", "import_via_api", "study_architecture")
        forbidden = ("directly_import_into_kernel", "embed_as_kernel_module", "modify_kernel_boundary")
    elif decision == DECISION_ARCHITECTURE_REFERENCE:
        allowed = ("study_architecture", "extract_design_patterns", "document_findings")
        forbidden = ("clone_to_github", "import_into_project", "run_as_dependency", "embed_as_kernel_module")
    else:
        allowed = ("document_rejection_reason",)
        forbidden = ("clone", "import", "integrate", "reference_as_architecture")

    return RepoIntakeDecision(
        decision=decision,
        priority=priority,
        claude_code_value_score=round(cc_value, 1),
        systemkernel_value_score=round(sk_value, 1),
        complexity_risk_score=round(complexity_risk, 1),
        purity_risk_score=round(purity_risk, 1),
        maintenance_risk_score=round(maintenance_risk, 1),
        final_score=final_score,
        reasons=tuple(reasons),
        recommended_target_dir=target,
        allowed_actions=tuple(allowed),
        forbidden_actions=tuple(forbidden),
    )


# ═══════════════════════════════════════════════════════════════════════
# Report I/O
# ═══════════════════════════════════════════════════════════════════════

def write_report(report: RepoIntakeReport, path: str) -> str:
    """Write an intake report to a JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)


def compute_report_hash(inp: RepoIntakeInput, signals: RepoSignals,
                        decision: RepoIntakeDecision) -> str:
    """Deterministic hash of an intake report."""
    parts = [
        json.dumps(inp.to_dict(), sort_keys=True, ensure_ascii=False),
        json.dumps(signals.to_dict(), sort_keys=True, ensure_ascii=False),
        decision.decision,
        decision.priority,
        str(decision.final_score),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
```

## File: repo_profiles.py
```python
"""
Repo Intake Profiles — Pre-built profiles for 14 known repositories.

Each profile contains:
  - name, url, category_hint, intended_use, known_risks, expected_decision
  - A synthetic file snapshot for signal extraction

Zero network required. Profiles are static data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from v3.intake.repo_intake import (
    DECISION_ARCHITECTURE_REFERENCE,
    DECISION_DIRECT_CLONE,
    DECISION_EXTERNAL_EXTENSION,
    DECISION_REJECT,
    INTENDED_USE_ARCHITECTURE,
    INTENDED_USE_CLAUDE_CODE,
    INTENDED_USE_SYSTEMKERNEL,
    INTENDED_USE_UNKNOWN,
    RepoIntakeInput,
    RepoSignals,
    analyze_repo_snapshot,
)


@dataclass(frozen=True)
class RepoProfile:
    """Pre-built profile for a known repository.

    Fields:
        name: Repository name
        url: GitHub URL
        category_hint: Category for type classification
        intended_use: How the developer intends to use this repo
        known_risks: List of known risk factors
        expected_decision: Expected intake decision
        files: Synthetic file snapshot dict (filename → content)
        known_dependencies: Pre-classified dependencies
    """

    name: str
    url: str
    category_hint: str = ""
    intended_use: str = INTENDED_USE_UNKNOWN
    known_risks: Tuple[str, ...] = ()
    expected_decision: str = DECISION_REJECT
    files: dict = field(default_factory=dict)
    known_dependencies: Tuple[str, ...] = ()

    def to_input(self) -> RepoIntakeInput:
        return RepoIntakeInput(
            name=self.name,
            url=self.url,
            category_hint=self.category_hint,
            intended_use=self.intended_use,
        )

    def analyze(self) -> RepoSignals:
        return analyze_repo_snapshot(
            name=self.name,
            url=self.url,
            files=self.files,
            known_dependencies=list(self.known_dependencies),
        )


# ═══════════════════════════════════════════════════════════════════════
# 14 Pre-built Profiles
# ═══════════════════════════════════════════════════════════════════════

PROFILES: Tuple[RepoProfile, ...] = (

    # 1. LangGraph — Agent framework by LangChain
    RepoProfile(
        name="LangGraph",
        url="https://github.com/langchain-ai/langgraph",
        category_hint="agent_runtime",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Heavy langchain dependency",
            "Agent execution model conflicts with SystemKernel",
            "LLM-driven control flow",
        ),
        expected_decision=DECISION_ARCHITECTURE_REFERENCE,
        files={
            "README.md": "# LangGraph\nBuild stateful, multi-actor agents with LLMs.",
            "LICENSE": "MIT License",
            "pyproject.toml": "[project]\nname = \"langgraph\"\ndependencies = [\"langchain-core\"]",
            "src/langgraph/__init__.py": "",
            "tests/test_graph.py": "",
            "docs/index.md": "# LangGraph Docs",
            "examples/agent.py": "",
        },
        known_dependencies=("langchain-core",),
    ),

    # 2. CrewAI — Multi-agent orchestration
    RepoProfile(
        name="CrewAI",
        url="https://github.com/crewAIInc/crewAI",
        category_hint="agent_runtime",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Multi-agent framework",
            "LLM dependency (openai/anthropic)",
            "Competing execution model",
        ),
        expected_decision=DECISION_ARCHITECTURE_REFERENCE,
        files={
            "README.md": "# CrewAI\nMulti-agent orchestration framework.",
            "LICENSE": "MIT License",
            "pyproject.toml": "[project]\nname = \"crewai\"\ndependencies = [\"openai\", \"langchain\"]",
            "src/crewai/__init__.py": "",
            "tests/test_crew.py": "",
            "docs/intro.md": "# CrewAI Docs",
        },
        known_dependencies=("openai", "langchain"),
    ),

    # 3. OpenAI Swarm — Lightweight agent swarm
    RepoProfile(
        name="OpenAI Swarm",
        url="https://github.com/openai/swarm",
        category_hint="agent_runtime",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "OpenAI API dependency",
            "Experimental agent framework",
        ),
        expected_decision=DECISION_EXTERNAL_EXTENSION,
        files={
            "README.md": "# Swarm\nExperimental framework for multi-agent orchestration.",
            "LICENSE": "MIT License",
            "pyproject.toml": "[project]\nname = \"swarm\"\ndependencies = [\"openai\"]",
            "src/swarm/__init__.py": "",
            "tests/test_swarm.py": "",
        },
        known_dependencies=("openai",),
    ),

    # 4. Anthropic Skills — Skill definitions for Claude Code
    RepoProfile(
        name="Anthropic Skills",
        url="https://github.com/anthropics/skills",
        category_hint="skill_system",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# Anthropic Skills\nSkill definitions for Claude Code.",
            "LICENSE": "MIT License",
            "skills/manifest.json": '{"skills": []}',
            "skills/example/SKILL.md": "# Example Skill",
            "tests/test_skills.py": "",
            "docs/README.md": "# Skills Docs",
        },
        known_dependencies=(),
    ),

    # 5. mem0 — Memory layer for AI
    RepoProfile(
        name="mem0",
        url="https://github.com/mem0ai/mem0",
        category_hint="memory_system",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Vector database dependency",
            "LLM embedding dependency",
            "Memory system conflicts with SK",
        ),
        expected_decision=DECISION_EXTERNAL_EXTENSION,
        files={
            "README.md": "# mem0\nMemory layer for AI applications.",
            "LICENSE": "Apache 2.0",
            "pyproject.toml": "[project]\nname = \"mem0\"\ndependencies = [\"qdrant-client\", \"chromadb\"]",
            "src/mem0/__init__.py": "",
            "tests/test_memory.py": "",
        },
        known_dependencies=("qdrant-client", "chromadb"),
    ),

    # 6. Graphiti — Knowledge graph memory
    RepoProfile(
        name="Graphiti",
        url="https://github.com/getzep/graphiti",
        category_hint="memory_system",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Neo4j/graph database dependency",
            "LLM-based entity extraction",
            "Memory system conflicts with SK",
        ),
        expected_decision=DECISION_EXTERNAL_EXTENSION,
        files={
            "README.md": "# Graphiti\nKnowledge graph-based memory for AI.",
            "LICENSE": "Apache 2.0",
            "pyproject.toml": "[project]\nname = \"graphiti\"\ndependencies = [\"neo4j\", \"openai\"]",
            "src/graphiti/__init__.py": "",
            "tests/test_graph.py": "",
        },
        known_dependencies=("neo4j", "openai"),
    ),

    # 7. Repomix — Repository context packer
    RepoProfile(
        name="Repomix",
        url="https://github.com/yamadashy/repomix",
        category_hint="context_tool",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# Repomix\nPack repository contents for AI context.",
            "LICENSE": "MIT License",
            "package.json": '{"name": "repomix", "dependencies": {"commander": "^11.0"}}',
            "src/cli.ts": "",
            "tests/cli.test.ts": "",
            "docs/README.md": "# Repomix Docs",
        },
        known_dependencies=(),
    ),

    # 8. ccusage — Claude Code usage tracker
    RepoProfile(
        name="ccusage",
        url="https://github.com/anthropics/ccusage",
        category_hint="claude_code_extension",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# ccusage\nTrack Claude Code usage and costs.",
            "LICENSE": "MIT License",
            "pyproject.toml": "[project]\nname = \"ccusage\"\ndependencies = []",
            "src/ccusage/cli.py": "",
            "tests/test_cli.py": "",
        },
        known_dependencies=(),
    ),

    # 9. Continue — IDE extension for AI
    RepoProfile(
        name="Continue",
        url="https://github.com/continuedev/continue",
        category_hint="claude_code_extension",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(
            "IDE-specific integration",
            "LLM API dependencies",
        ),
        expected_decision=DECISION_EXTERNAL_EXTENSION,
        files={
            "README.md": "# Continue\nAI code assistant for IDEs.",
            "LICENSE": "Apache 2.0",
            "package.json": '{"name": "continue", "dependencies": {"openai": "^4.0"}}',
            "src/extension.ts": "",
            "tests/extension.test.ts": "",
        },
        known_dependencies=("openai",),
    ),

    # 10. AppFlowy — Notion alternative
    RepoProfile(
        name="AppFlowy",
        url="https://github.com/AppFlowy-IO/appflowy",
        category_hint="application",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Large Flutter/Rust codebase",
            "Heavy dependency footprint",
        ),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# AppFlowy\nOpen-source Notion alternative.",
            "LICENSE": "AGPL 3.0",
            "Cargo.toml": "[package]\nname = \"appflowy\"",
            "src/main.rs": "",
            "tests/integration.rs": "",
        },
        known_dependencies=(),
    ),

    # 11. JupyterLab — Notebook interface
    RepoProfile(
        name="JupyterLab",
        url="https://github.com/jupyterlab/jupyterlab",
        category_hint="application",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Very large codebase",
            "Heavy extension system",
        ),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# JupyterLab\nWeb-based interactive development environment.",
            "LICENSE": "BSD 3-Clause",
            "pyproject.toml": "[project]\nname = \"jupyterlab\"",
            "package.json": '{"name": "@jupyterlab/application"}',
            "src/__init__.py": "",
            "tests/test_app.py": "",
            "docs/index.rst": "JupyterLab Docs",
            "examples/notebook.ipynb": "",
        },
        known_dependencies=(),
    ),

    # 12. SuperClaude — Claude Code enhancements
    RepoProfile(
        name="SuperClaude",
        url="https://github.com/anthropics/SuperClaude",
        category_hint="claude_code_extension",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# SuperClaude\nEnhancements and utilities for Claude Code.",
            "LICENSE": "MIT License",
            "skills/manifest.json": '{"skills": []}',
            "skills/code-review/SKILL.md": "# Code Review Skill",
            "tests/test_skills.py": "",
        },
        known_dependencies=(),
    ),

    # 13. awesome-claude-code — Curated list
    RepoProfile(
        name="awesome-claude-code",
        url="https://github.com/anthropics/awesome-claude-code",
        category_hint="docs_only",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Documentation only, no runnable code",
        ),
        expected_decision=DECISION_ARCHITECTURE_REFERENCE,
        files={
            "README.md": "# Awesome Claude Code\nCurated list of Claude Code resources.",
        },
        known_dependencies=(),
    ),

    # 14. Awesome-Prompt-Engineering — Curated list
    RepoProfile(
        name="Awesome-Prompt-Engineering",
        url="https://github.com/promptslab/Awesome-Prompt-Engineering",
        category_hint="docs_only",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Documentation only, no runnable code",
        ),
        expected_decision=DECISION_ARCHITECTURE_REFERENCE,
        files={
            "README.md": "# Awesome Prompt Engineering\nCurated prompt engineering resources.",
        },
        known_dependencies=(),
    ),
)


# ═══════════════════════════════════════════════════════════════════════
# Profile lookup
# ═══════════════════════════════════════════════════════════════════════

def get_profile(name: str) -> RepoProfile | None:
    """Look up a profile by name (case-insensitive)."""
    name_lower = name.lower()
    for p in PROFILES:
        if p.name.lower() == name_lower:
            return p
    return None


def list_profiles() -> list:
    """List all profile names and URLs."""
    return [{"name": p.name, "url": p.url} for p in PROFILES]


def get_all_profiles() -> Tuple[RepoProfile, ...]:
    """Return all profiles."""
    return PROFILES
```

## File: rules.py
```python
"""
Repo Intake Rules — Interpretable classifier rules.

Each rule is a self-contained condition→decision mapping that can be
read and understood independently. Rules are applied in priority order.
The first matching rule wins.

All rules are deterministic — same inputs always produce same outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

from v3.intake.repo_intake import (
    DECISION_ARCHITECTURE_REFERENCE,
    DECISION_DIRECT_CLONE,
    DECISION_EXTERNAL_EXTENSION,
    DECISION_REJECT,
    RepoIntakeDecision,
    RepoIntakeInput,
    RepoSignals,
)


# ═══════════════════════════════════════════════════════════════════════
# Repo type classification
# ═══════════════════════════════════════════════════════════════════════

REPO_TYPE_AGENT_RUNTIME = "agent_runtime"
REPO_TYPE_MEMORY_SYSTEM = "memory_system"
REPO_TYPE_OBSERVABILITY_TOOL = "observability_tool"
REPO_TYPE_CLAUDE_CODE_EXTENSION = "claude_code_extension"
REPO_TYPE_SKILL_SYSTEM = "skill_system"
REPO_TYPE_CONTEXT_TOOL = "context_tool"
REPO_TYPE_DOCS_ONLY = "docs_only"
REPO_TYPE_UNKNOWN = "unknown"

REPO_TYPES = (
    REPO_TYPE_AGENT_RUNTIME,
    REPO_TYPE_MEMORY_SYSTEM,
    REPO_TYPE_OBSERVABILITY_TOOL,
    REPO_TYPE_CLAUDE_CODE_EXTENSION,
    REPO_TYPE_SKILL_SYSTEM,
    REPO_TYPE_CONTEXT_TOOL,
    REPO_TYPE_DOCS_ONLY,
    REPO_TYPE_UNKNOWN,
)


def classify_repo_type(signals: RepoSignals, name: str = "") -> str:
    """Classify a repository into one of 8 types based on signals.

    Classification is deterministic and based on structural signals only.
    No LLM, no network, no semantic analysis.

    Priority order:
      1. agent_runtime — framework deps present
      2. memory_system — memory/vector DB deps present
      3. observability_tool — traces/metrics/logging signals
      4. claude_code_extension — MCP or Claude Code integration
      5. skill_system — skill manifests, plugin manifests
      6. context_tool — CLI tools that process context/files
      7. docs_only — documentation with no code signals
      8. unknown — none of the above
    """
    name_lower = name.lower()

    # 1. Agent runtime: has framework deps
    if signals.framework_dependency_hits > 0:
        return REPO_TYPE_AGENT_RUNTIME

    # 2. Memory system: has memory/vector DB deps
    if signals.memory_dependency_hits > 0:
        return REPO_TYPE_MEMORY_SYSTEM

    # 3. Observability tool: name hints
    obs_keywords = ("trace", "metric", "observe", "monitor", "log", "telemetry")
    if any(kw in name_lower for kw in obs_keywords):
        return REPO_TYPE_OBSERVABILITY_TOOL

    # 4. Claude Code extension: MCP or Claude Code integration
    if signals.has_mcp:
        return REPO_TYPE_CLAUDE_CODE_EXTENSION
    cc_keywords = ("claude", "mcp", "anthropic")
    if any(kw in name_lower for kw in cc_keywords) and not signals.framework_dependency_hits:
        return REPO_TYPE_CLAUDE_CODE_EXTENSION

    # 5. Skill system: skill or plugin manifests
    if signals.has_skill_manifest or signals.has_plugin_manifest:
        return REPO_TYPE_SKILL_SYSTEM

    # 6. Context tool: CLI tool with file processing hints
    if signals.has_cli and signals.language_hints:
        ctx_keywords = ("context", "repo", "pack", "bundle", "parse", "tree")
        if any(kw in name_lower for kw in ctx_keywords):
            return REPO_TYPE_CONTEXT_TOOL

    # 7. Docs only: has readme but no code signals
    if (signals.has_readme and not signals.language_hints
            and not signals.dependency_files and not signals.has_cli):
        return REPO_TYPE_DOCS_ONLY

    return REPO_TYPE_UNKNOWN


# ═══════════════════════════════════════════════════════════════════════
# Interpretable rules
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class IntakeRule:
    """A single interpretable intake rule.

    Fields:
        rule_id: Unique rule identifier
        priority: Application priority (lower = applied first)
        description: Human-readable description of what the rule does
        condition: Short condition description (e.g. "framework_deps >= 1")
        decision: The decision this rule produces
        rationale: Why this decision is made
    """

    rule_id: str
    priority: int
    description: str
    condition: str
    decision: str
    rationale: str


# Priority-ordered rules (lowest priority number = applied first)
INTAKE_RULES: Tuple[IntakeRule, ...] = (
    IntakeRule(
        rule_id="R01",
        priority=1,
        description="Pure CLI tool with documentation and low risk → direct clone",
        condition="has_cli AND has_readme AND has_license AND framework_deps=0 AND llm_deps=0 AND banned_deps=0 AND (cc_value>=7 OR sk_value>=7)",
        decision=DECISION_DIRECT_CLONE,
        rationale="Well-documented CLI tools with no risky dependencies are safe to clone and use directly.",
    ),
    IntakeRule(
        rule_id="R02",
        priority=2,
        description="Agent framework dependency → architecture reference only",
        condition="framework_deps >= 1",
        decision=DECISION_ARCHITECTURE_REFERENCE,
        rationale="Agent frameworks (LangGraph, CrewAI, etc.) embed their own execution models. Study their design but do not integrate into the kernel.",
    ),
    IntakeRule(
        rule_id="R03",
        priority=3,
        description="LLM SDK dependency → external extension",
        condition="llm_deps >= 1",
        decision=DECISION_EXTERNAL_EXTENSION,
        rationale="LLM SDKs must run as external services, never inside the kernel boundary. Use via API only.",
    ),
    IntakeRule(
        rule_id="R04",
        priority=4,
        description="Memory/vector DB dependency → external extension",
        condition="memory_deps > 0 OR heavy_deps > 0",
        decision=DECISION_EXTERNAL_EXTENSION,
        rationale="Memory systems and heavy frameworks require external deployment. Never embed into the kernel.",
    ),
    IntakeRule(
        rule_id="R05",
        priority=5,
        description="Banned kernel dependency → architecture reference",
        condition="banned_deps > 0",
        decision=DECISION_ARCHITECTURE_REFERENCE,
        rationale="Banned dependencies violate kernel purity. Study design from a distance only.",
    ),
    IntakeRule(
        rule_id="R06",
        priority=6,
        description="Documented project with moderate value → external extension",
        condition="has_readme AND has_license AND NOT (R01-R05 matched)",
        decision=DECISION_EXTERNAL_EXTENSION,
        rationale="Documented but not high enough value for direct clone. Use as external service.",
    ),
    IntakeRule(
        rule_id="R07",
        priority=7,
        description="No readme and no code signals → reject",
        condition="NOT has_readme AND NOT language_hints AND NOT dependency_files",
        decision=DECISION_REJECT,
        rationale="Repository has no discoverable content. Cannot assess value or risk.",
    ),
    IntakeRule(
        rule_id="R08",
        priority=8,
        description="High risk: multiple banned deps with no license or readme → reject",
        condition="banned_deps >= 2 AND NOT has_license AND NOT has_readme",
        decision=DECISION_REJECT,
        rationale="Too many purity risks with no documentation or license. Unsafe to integrate.",
    ),
    IntakeRule(
        rule_id="R09",
        priority=9,
        description="Insufficient documentation or value → architecture reference",
        condition="default fallthrough",
        decision=DECISION_ARCHITECTURE_REFERENCE,
        rationale="When in doubt, study architecture but do not integrate. Default conservative position.",
    ),
)


# ═══════════════════════════════════════════════════════════════════════
# Rule-based classification (alternative to scoring engine)
# ═══════════════════════════════════════════════════════════════════════

def apply_rules(
    inp: RepoIntakeInput,
    signals: RepoSignals,
) -> Tuple[str, str]:
    """Apply interpretable rules and return (decision, matched_rule_id).

    This is a rule-based alternative to the numeric scoring engine.
    Produces the same decisions but with explicit rule attribution.

    Returns:
        (decision, rule_id) — rule_id is the matched rule or "" if no match.
    """
    # Rule R08: high risk reject
    if (signals.banned_dependency_hits >= 2
            and not signals.has_license
            and not signals.has_readme):
        return (DECISION_REJECT, "R08")

    # Rule R07: no content reject
    if (not signals.has_readme
            and not signals.language_hints
            and not signals.dependency_files):
        return (DECISION_REJECT, "R07")

    # Rule R02: framework deps → architecture reference
    if signals.framework_dependency_hits >= 1:
        return (DECISION_ARCHITECTURE_REFERENCE, "R02")

    # Rule R03: LLM deps → external extension
    if signals.llm_dependency_hits >= 1:
        return (DECISION_EXTERNAL_EXTENSION, "R03")

    # Rule R04: memory/heavy deps → external extension
    if signals.memory_dependency_hits > 0 or signals.heavy_dependency_hits > 0:
        return (DECISION_EXTERNAL_EXTENSION, "R04")

    # Rule R05: banned deps → architecture reference
    if signals.banned_dependency_hits > 0:
        return (DECISION_ARCHITECTURE_REFERENCE, "R05")

    # Compute cc_value and sk_value for R01 check
    cc_value = 5.0
    if signals.has_readme:    cc_value += 2.0
    if signals.has_cli:       cc_value += 2.0
    if signals.has_mcp:       cc_value += 2.0
    if signals.has_skill_manifest: cc_value += 1.0
    if signals.has_examples:  cc_value += 1.0
    if signals.has_tests:     cc_value += 1.0
    if signals.has_docs:      cc_value += 1.0
    cc_value -= signals.banned_dependency_hits * 2.0
    cc_value -= signals.heavy_dependency_hits * 1.0

    sk_value = 5.0
    if signals.has_plugin_manifest: sk_value += 2.0
    if signals.has_tests:     sk_value += 2.0
    if signals.has_license:   sk_value += 2.0
    if signals.has_readme:    sk_value += 1.0
    if signals.has_docs:      sk_value += 1.0
    if signals.has_examples:  sk_value += 1.0
    sk_value -= signals.llm_dependency_hits * 2.0
    sk_value -= signals.framework_dependency_hits * 2.0
    sk_value -= signals.memory_dependency_hits * 1.0

    # Rule R01: high value documented → direct clone
    if ((cc_value >= 7.0 or sk_value >= 7.0)
            and signals.has_readme
            and signals.has_license):
        return (DECISION_DIRECT_CLONE, "R01")

    # Rule R06: documented but moderate → external extension
    if signals.has_readme and signals.has_license:
        return (DECISION_EXTERNAL_EXTENSION, "R06")

    # Rule R09: default → architecture reference
    return (DECISION_ARCHITECTURE_REFERENCE, "R09")


def get_rules_table() -> list:
    """Return all rules as a list of dicts for display/reporting."""
    return [
        {
            "rule_id": r.rule_id,
            "priority": r.priority,
            "description": r.description,
            "condition": r.condition,
            "decision": r.decision,
        }
        for r in sorted(INTAKE_RULES, key=lambda r: r.priority)
    ]
```

## File: tool_registry.py
```python
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
```
