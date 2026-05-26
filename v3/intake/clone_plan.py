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
