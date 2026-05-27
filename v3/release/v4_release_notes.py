"""
V4 Release Notes — Phase 12.

Generates Markdown release notes for SystemKernel v4.0.
Documents all phases, planes, invariants, and intentional exclusions.

No execution. No external tools. No new providers.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class V4ReleaseNotes:
    version: str = "4.0"
    content: str = ""
    notes_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "content": self.content,
            "notes_hash": self.notes_hash,
        }


def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        data.pop("notes_hash", None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_v4_release_notes() -> V4ReleaseNotes:
    """Generate v4.0 release notes in Markdown."""

    lines = []
    lines.append("# SystemKernel v4.0.0 — Pluggable Intelligence Plane")
    lines.append("")
    lines.append(f"Release date: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("Tag: systemkernel-v4.0.0-pluggable-intelligence")
    lines.append("")
    lines.append("---")
    lines.append("")

    # What is SystemKernel v4.0
    lines.append("## What is SystemKernel v4.0")
    lines.append("")
    lines.append("SystemKernel v4.0 is a governance and pluggable intelligence boundary release. "
                 "It defines how external AI systems can be evaluated, registered, evidenced, "
                 "planned, and governed — without integrating any real external providers.")
    lines.append("")
    lines.append("The kernel remains deterministic, LLM-free, and memory-removable. "
                 "All v4 additions are read-only planning planes that operate at the boundary, "
                 "never inside the kernel.")
    lines.append("")

    # Difference from v3.0
    lines.append("## Difference from v3.0")
    lines.append("")
    lines.append("v3.0 established the deterministic kernel boundary: Adapter, TaskSystem, "
                 "ExecutionLoop, EventBus, Observability — all LLM-free, all pure-Python, "
                 "all memory-removable.")
    lines.append("")
    lines.append("v4.0 adds the **Pluggable Intelligence Plane** — a governance layer that:")
    lines.append("")
    lines.append("- Defines a Capability Contract for external AI providers")
    lines.append("- Maintains a Capability Registry (read-only, file-based)")
    lines.append("- Records Evidence Bundles with explicit `truth_source=False`")
    lines.append("- Plans Context Packs without executing external tools")
    lines.append("- Defines memory, agent, workspace, and skill-evolution planes as read-only schemas")
    lines.append("- Provides Orchestration Policy profiles (dry-run only)")
    lines.append("- Includes a deterministic Evaluation Harness with benefit-complexity scoring")
    lines.append("- Ships operational tooling: status, checklists, runbooks")
    lines.append("")

    # Completed phases
    lines.append("## Completed Phases (0–12)")
    lines.append("")
    for phase in [
        ("Phase 0", "Kernel Boundary & Constitution"),
        ("Phase 1", "EventBus"),
        ("Phase 2", "Kernel Hardening"),
        ("Phase 3", "Observability (Traces + Metrics + Replay)"),
        ("Phase 4", "TaskSystem + ExecutionLoop Integration"),
        ("Phase 5", "Complexity Budget & Quality Gate"),
        ("Phase 5A", "Complexity Budget Hardening"),
        ("Phase 6", "Architecture Guard + Drift Detection"),
        ("Phase 7", "Memory Intelligence Plane (read-only schema)"),
        ("Phase 7.5", "Memory Compaction Integrity"),
        ("Phase 8", "External Evidence Model"),
        ("Phase 8.5", "External Tools Clone Report"),
        ("Phase 9", "Capability Registry + Context Plane + Agent Worker + Workspace + Skill Evolution + Orchestration"),
        ("Phase 9.5", "Complexity Sanity Check"),
        ("Phase 10", "Evaluation Harness + Regression Matrix"),
        ("Phase 11", "Productization + Ops"),
        ("Phase 12", "Release Freeze"),
    ]:
        lines.append(f"- **{phase[0]}:** {phase[1]}")
    lines.append("")

    # Pluggable Intelligence Plane overview
    lines.append("## Pluggable Intelligence Plane Overview")
    lines.append("")
    lines.append("The v4 Pluggable Intelligence Plane is a governance boundary. "
                 "It wraps the deterministic kernel and provides structured, read-only "
                 "interfaces for evaluating external AI capabilities.")
    lines.append("")

    # Each plane
    planes = [
        ("Capability Contract", "Defines the contract external AI providers must satisfy. "
         "All external capabilities are evaluated against this contract before registry entry."),
        ("Capability Registry", "File-based registry of 10 capability adapters across 8 types. "
         "2 enabled (safe-context-only), 8 disabled (including ECC as future placeholder)."),
        ("Evidence Model", "EvidenceBundle records with explicit `truth_source=False`. "
         "All external evidence is TRUST_LOW by default. Never used for kernel decisions."),
        ("Context Engineering Plane", "Plans context packs for codebase analysis. "
         "Dry-run by default. Budget policy limits scope. No external tool execution."),
        ("Memory Intelligence Plane", "Read-only schema for memory compaction, "
         "episodic projection, and integrity checks. No runtime memory decisions."),
        ("Agent Worker Plane", "Read-only schema for agent worker lifecycle. "
         "Defines worker states, task queues, and capability contracts. No agent execution."),
        ("Workspace Plane", "Read-only schema for workspace isolation. "
         "Defines file scoping, sandbox boundaries. No runtime enforcement."),
        ("Skill Evolution Plane", "Read-only schema for skill proposals. "
         "Dry-run only. Skills are proposed, never auto-modified."),
        ("Orchestration Policy", "6 policy profiles for orchestrating capability adapters. "
         "All dry-run. ECC profile (ecc_harness_review) disabled placeholder."),
    ]
    for title, desc in planes:
        lines.append(f"### {title}")
        lines.append("")
        lines.append(desc)
        lines.append("")

    # Evaluation Harness
    lines.append("## Evaluation Harness")
    lines.append("")
    lines.append("Deterministic eval suite with 19 cases across 8 categories. "
                 "Benefit-complexity scoring prevents ability+10 complexity+300 regressions. "
                 "35 regression checks across 13 categories. All local, no network, no LLM.")
    lines.append("")

    # Productization + Ops
    lines.append("## Productization + Ops")
    lines.append("")
    lines.append("Day-to-day operational tooling:")
    lines.append("")
    lines.append("- `v4 status` — operational health snapshot")
    lines.append("- `v4 ops-check` — 22-item checklist across 8 categories")
    lines.append("- `v4 runbook` — 11-section operational runbook")
    lines.append("- `v4 summary` — compact operational summary")
    lines.append("")

    # ECC handling
    lines.append("## ECC Handling")
    lines.append("")
    lines.append("ECC (everything-claude-code) is treated as a **disabled future placeholder**.")
    lines.append("")
    lines.append("- Listed as `ecc_harness_review` orchestration profile — disabled, dry-run only")
    lines.append("- Covers 4 of 8 capability types: skill, tool, eval, context")
    lines.append("- Never auto-installed, auto-cloned, or auto-executed")
    lines.append("- Requires a formal Phase 12+ trial gate before any integration")
    lines.append("- SystemKernel must not become an ECC clone or dependency")
    lines.append("")

    # Intentionally not included
    lines.append("## What Is Intentionally NOT Included")
    lines.append("")
    items = [
        "Real external provider integration (Mem0, Graphiti, OpenHands, AutoGen, Continue, ECC)",
        "LLM/AI imports in kernel modules",
        "Network access from any kernel or release module",
        "External tool execution through the kernel boundary",
        "New truth sources (truth_source always False for external data)",
        "Agent execution or autonomous decision-making",
        "IDE API access",
        "Runtime memory intelligence decisions",
        "Auto-modification of registry or skills",
    ]
    for item in items:
        lines.append(f"- {item}")
    lines.append("")

    # Safety invariants
    lines.append("## Safety Invariants")
    lines.append("")
    invariants = [
        "Kernel purity: 100/100 — zero LLM imports in kernel",
        "Memory removable: YES — kernel runs without memory subsystem",
        "Deterministic routing: same input always produces same output",
        "No external execution: all orchestration is dry-run",
        "No truth source elevation: external data truth_source=False",
        "Complexity gate: benefit must exceed complexity cost",
        "Read-only ops: all operational commands are side-effect-free",
    ]
    for inv in invariants:
        lines.append(f"- {inv}")
    lines.append("")

    # Complexity guard
    lines.append("## Complexity Guard")
    lines.append("")
    lines.append("Complexity budget enforced by `v3/quality/complexity_budget.py`. "
                 "Risk ratio = complexity / benefit. REJECT at >3.0, REVIEW at >2.0. "
                 "New truth sources and lost memory removability are automatic rejection.")
    lines.append("")

    # Known limitations
    lines.append("## Known Limitations")
    lines.append("")
    limitations = [
        "No real provider integration — all external capabilities are schemas and dry-run plans",
        "Evidence model is trust-low by design — not suitable for automated decisions",
        "Orchestration is planning-only — no execution engine",
        "Memory intelligence is schema-only — no runtime compaction or projection",
        "Agent worker is schema-only — no actual agent lifecycle management",
        "Context packs are planned but not auto-generated from external sources",
        "ECC is listed but fully disabled — no integration timeline",
    ]
    for lim in limitations:
        lines.append(f"- {lim}")
    lines.append("")

    # Next possible directions
    lines.append("## Next Possible Directions")
    lines.append("")
    directions = [
        "Formal provider trials with explicit safety gates (post-Phase 12)",
        "ECC evaluation with trial harness (requires human approval)",
        "Automated context pack generation from safe local sources",
        "Memory compaction with integrity verification (read-only projection)",
        "Agent worker lifecycle management with capability contract validation",
        "Skill evolution proposal pipeline with automated regression checks",
        "Cross-plane integration testing framework",
    ]
    for d in directions:
        lines.append(f"- {d}")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("SystemKernel v4.0.0 — Pluggable Intelligence Plane")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("PURE KERNEL | MEMORY REMOVABLE | ZERO EXTERNAL INTEGRATION")

    content = "\n".join(lines)
    notes = V4ReleaseNotes(version="4.0", content=content)
    object.__setattr__(notes, "notes_hash", _compute_hash(notes))
    return notes


def write_v4_release_notes(path: str) -> str:
    """Write v4 release notes to a Markdown file."""
    notes = build_v4_release_notes()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(notes.content)
    return os.path.abspath(path)
