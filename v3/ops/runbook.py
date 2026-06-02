"""
V4 Runbook — Phase 11.

Deterministic, read-only runbook for v4 day-to-day operations.
Documents safe commands, inspection procedures, and operational boundaries.

No execution. No external tools. No new providers.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Tuple


# ═══════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RunbookSection:
    """One section of the v4 operational runbook."""
    section_id: str = ""
    title: str = ""
    purpose: str = ""
    commands: Tuple[str, ...] = ()
    safety_notes: Tuple[str, ...] = ()
    section_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "purpose": self.purpose,
            "commands": list(self.commands),
            "safety_notes": list(self.safety_notes),
            "section_hash": self.section_hash,
        }


@dataclass(frozen=True)
class V4Runbook:
    """Complete v4 operational runbook."""
    version: str = "4.0"
    sections: Tuple[RunbookSection, ...] = ()
    runbook_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "sections": [s.to_dict() for s in self.sections],
            "runbook_hash": self.runbook_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash helper
# ═══════════════════════════════════════════════════════════════════════

def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        for key in ("section_hash", "runbook_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Runbook builder
# ═══════════════════════════════════════════════════════════════════════

def build_v4_runbook() -> V4Runbook:
    """Build the complete v4 operational runbook.

    Covers daily checks, inspection procedures, dry-run planning,
    eval/regression, safety boundaries, and ECC handling.
    """
    sections = []

    def _add(title, purpose, commands, safety_notes):
        s = RunbookSection(
            section_id="",
            title=title,
            purpose=purpose,
            commands=tuple(commands),
            safety_notes=tuple(safety_notes),
        )
        object.__setattr__(s, "section_id", _compute_hash(s)[:16])
        object.__setattr__(s, "section_hash", _compute_hash(s))
        sections.append(s)

    _add(
        "Daily Status Check",
        "Quick health check of all v4 subsystems. Run this daily or after any change.",
        [
            "python v3/cli/systemkernel.py status",
            "python v3/cli/systemkernel.py quality",
            "python v3/cli/systemkernel.py v4 status",
        ],
        (
            "All commands are read-only — no side effects.",
            "If any check fails, investigate before running further commands.",
        ),
    )

    _add(
        "Capability Registry Review",
        "Review registered external capability adapters and their status.",
        [
            "python v3/cli/systemkernel.py capability summary",
            "python v3/cli/systemkernel.py capability list",
            "python v3/cli/systemkernel.py capability show <adapter_id>",
        ],
        (
            "Registry is the single source of truth for external capability existence.",
            "Never enable a disabled adapter without passing the trial gate first.",
            "Do not add registry entries without Phase 2 compliance checks.",
        ),
    )

    _add(
        "Evidence Inspection",
        "Inspect evidence bundles to verify external adapter outputs are recorded correctly.",
        [
            "python v3/cli/systemkernel.py context-plane evidence <path>",
            "python v3/cli/systemkernel.py memory-intel evidence",
            "python v3/cli/systemkernel.py agent-worker evidence",
            "python v3/cli/systemkernel.py workspace evidence",
            "python v3/cli/systemkernel.py skill-evolution evidence",
        ],
        (
            "All evidence records have truth_source=False — evidence is NOT truth.",
            "Evidence is always TRUST_LOW by default.",
            "Never base kernel decisions on evidence alone.",
        ),
    )

    _add(
        "Context Pack Planning",
        "Plan context packs for codebase analysis without executing external tools.",
        [
            "python v3/cli/systemkernel.py context-plane plan <target> --output ctx.md",
            "python v3/cli/systemkernel.py context-plane inspect <path>",
        ],
        (
            "Context pack planning is dry-run by default — no files are read outside budget.",
            "Use --allow-execute only when you fully trust the target directory.",
        ),
    )

    _add(
        "Usage Report Inspection",
        "Inspect Claude Code usage reports for operational insights.",
        [
            "python v3/cli/systemkernel.py usage inspect <ccusage.json>",
            "python v3/cli/systemkernel.py usage summarize <ccusage.json> --output report.json",
        ],
        (
            "Usage reports are external evidence, not kernel truth.",
            "Do not use usage data for automated decision-making.",
        ),
    )

    _add(
        "Orchestration Dry-Run",
        "Plan capability adapter orchestration without executing anything.",
        [
            "python v3/cli/systemkernel.py orchestrate policies",
            "python v3/cli/systemkernel.py orchestrate plan --profile safe_context_only",
            "python v3/cli/systemkernel.py orchestrate plan --profile full_external_review",
            "python v3/cli/systemkernel.py orchestrate evidence --profile safe_context_only",
        ],
        (
            "All orchestration is dry-run only — nothing is executed.",
            "Orchestration plans are PLANS, not truth sources.",
            "ECC profile (ecc_harness_review) is disabled and must stay disabled.",
        ),
    )

    _add(
        "Eval / Regression Check",
        "Run deterministic eval suite and regression matrix to verify v4 integrity.",
        [
            "python v3/cli/systemkernel.py eval suite",
            "python v3/cli/systemkernel.py eval run",
            "python v3/cli/systemkernel.py eval regression",
            "python v3/cli/systemkernel.py eval benefit",
        ],
        (
            "All evals are deterministic and local — no network, no LLM.",
            "Regression failures that are 'release blocking' must be fixed before merging.",
            "Benefit-complexity REJECT means the change adds too much complexity for too little benefit.",
        ),
    )

    _add(
        "Complexity Gate Check",
        "Verify complexity budget is not exceeded by recent changes.",
        [
            "python v3/cli/systemkernel.py quality",
        ],
        (
            "Complexity gate REJECT blocks all further changes.",
            "REVIEW means the change needs justification before proceeding.",
            "ACCEPT means complexity is within budget for the benefit provided.",
        ),
    )

    _add(
        "Ops Dashboard — Grafana Monitoring",
        "Export and import the SystemKernel operations dashboard into Grafana "
        "for real-time monitoring of execution, cost, errors, latency, provider "
        "health, and capability usage (9 panels, Prometheus datasource).",
        [
            "python v3/cli/systemkernel.py v4 dashboard",
            "python v3/cli/systemkernel.py v4 dashboard --export systemkernel-dashboard.json",
            "python v3/cli/systemkernel.py v4 metrics",
            "python v3/cli/systemkernel.py v4 metrics --json",
            "python v3/cli/systemkernel.py v4 alerts",
        ],
        (
            "Dashboard import: Grafana → Dashboards → New → Import → Upload systemkernel-dashboard.json.",
            "Set the DS_PROMETHEUS variable to your Prometheus datasource after import.",
            "All metrics are exported in Prometheus text format — no prometheus_client dependency.",
            "Alerts evaluate against current metric values — FIRING alerts require investigation.",
            "Critical alerts (error_rate_high, freeze_violation) require immediate response.",
            "Complexity_approaching_review (INFO) means architecture review recommended.",
        ),
    )

    _add(
        "What NOT to Do",
        "Operational boundaries that must not be crossed.",
        [],
        (
            "DO NOT execute external tools through the kernel boundary.",
            "DO NOT enable blocked providers (OpenHands, AutoGen, Mem0, Graphiti, etc.) without a formal trial.",
            "DO NOT modify v3/kernel/ files — kernel is sealed.",
            "DO NOT modify v3/memory/ runtime behavior.",
            "DO NOT add new truth sources — truth_source must always be False for external data.",
            "DO NOT add LLM/AI imports to kernel modules.",
            "DO NOT install or clone ECC — it is a future external provider, not a dependency.",
            "DO NOT modify registry.json or skill files through automation — use proposal-only skill evolution.",
        ),
    )

    _add(
        "How ECC is Treated",
        "ECC (everything-claude-code) is a FUTURE external harness enhancement provider.",
        [
            "python v3/cli/systemkernel.py orchestrate plan --profile ecc_harness_review",
            "# ECC repo: https://github.com/affaan-m/everything-claude-code",
            "# Status: NOT integrated, NOT cloned, NOT installed",
        ],
        (
            "ECC is listed as ecc_harness_review profile — disabled, dry-run only.",
            "ECC capability types: skill, tool, eval, context (4 of 8).",
            "ECC must never be auto-installed, auto-cloned, or auto-executed.",
            "ECC integration requires a formal Phase 12+ trial gate.",
            "SystemKernel must not become an ECC clone or dependency.",
        ),
    )

    _add(
        "How to Propose a Real Provider Trial Safely",
        "Procedure for graduating a blocked provider to trial status.",
        [
            "# 1. Write a trial proposal documenting:",
            "#    - Provider name and capability type",
            "#    - Why the provider is needed",
            "#    - What safety boundaries apply",
            "#    - What evidence will be collected",
            "# 2. Create a skill evolution proposal (dry-run only):",
            "python v3/cli/systemkernel.py skill-evolution mock",
            "# 3. Run eval suite to verify no regressions:",
            "python v3/cli/systemkernel.py eval run",
            "# 4. Run benefit-complexity check:",
            "python v3/cli/systemkernel.py eval benefit",
            "# 5. If all gates pass, submit proposal for human review",
        ],
        (
            "Never enable a provider without explicit human approval.",
            "All trial proposals are dry-run by default.",
            "Provider enablement requires registry update — do NOT do this automatically.",
            "ECC requires its own formal trial gate before any integration.",
        ),
    )

    runbook = V4Runbook(
        version="4.0",
        sections=tuple(sections),
    )
    object.__setattr__(runbook, "runbook_hash", _compute_hash(runbook))
    return runbook


# ═══════════════════════════════════════════════════════════════════════
# Writers
# ═══════════════════════════════════════════════════════════════════════

def write_v4_runbook_md(path: str) -> str:
    """Write the v4 runbook as a Markdown file."""
    runbook = build_v4_runbook()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    lines = [
        f"# SystemKernel v4.0 — Operational Runbook",
        f"",
        f"Version: {runbook.version}",
        f"Hash: {runbook.runbook_hash}",
        f"",
        "---",
        "",
    ]

    for s in runbook.sections:
        lines.append(f"## {s.title}")
        lines.append("")
        lines.append(f"**Purpose:** {s.purpose}")
        lines.append("")
        if s.commands:
            lines.append("### Commands")
            lines.append("")
            for cmd in s.commands:
                lines.append(f"```bash")
                lines.append(cmd)
                lines.append(f"```")
                lines.append("")
        if s.safety_notes:
            lines.append("### Safety Notes")
            lines.append("")
            for note in s.safety_notes:
                lines.append(f"- {note}")
            lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return os.path.abspath(path)


def write_v4_runbook_json(path: str) -> str:
    """Write the v4 runbook as a JSON file."""
    runbook = build_v4_runbook()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(runbook.to_dict(), f, indent=2, ensure_ascii=False)
    return os.path.abspath(path)
