"""
Operational Handoff — Handoff checklist and verification for SystemKernel v3.0.

Produces a structured operational handoff with versioned checklist items,
verification commands, rollback guidance, and known limitations.

Phase 6A: Baseline packaging. No new runtime capabilities.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# HandoffChecklistItem
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class HandoffChecklistItem:
    """One item in the operational handoff checklist."""

    id: str = ""
    title: str = ""
    command: str = ""
    expected: str = ""
    required: bool = True
    status: str = "PENDING"  # PENDING, PASS, FAIL

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "command": self.command,
            "expected": self.expected,
            "required": self.required,
            "status": self.status,
        }


# ═══════════════════════════════════════════════════════════════════════
# OperationalHandoff
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OperationalHandoff:
    """Complete operational handoff for SystemKernel v3.0."""

    version: str = "3.0.0"
    checklist: Tuple[HandoffChecklistItem, ...] = ()
    verification_commands: Tuple[str, ...] = ()
    rollback_notes: str = ""
    known_limitations: Tuple[str, ...] = ()
    handoff_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "checklist": [c.to_dict() for c in self.checklist],
            "verification_commands": list(self.verification_commands),
            "rollback_notes": self.rollback_notes,
            "known_limitations": list(self.known_limitations),
            "handoff_hash": self.handoff_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _resolve_root() -> str:
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def build_handoff() -> OperationalHandoff:
    """Build the complete operational handoff for v3.0 baseline.

    Deterministic: same code → same checklist → same handoff_hash.
    """

    checklist = (
        HandoffChecklistItem(
            id="H001",
            title="Run kernel invariants",
            command="python v3/tests/test_kernel_invariants.py",
            expected="All kernel invariants pass; purity score 100/100",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H002",
            title="Run release freeze tests",
            command="python v3/tests/test_release_freeze.py",
            expected="All release freeze tests pass",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H003",
            title="Run CLI doctor",
            command="python v3/cli/systemkernel.py doctor",
            expected="All health checks pass; HEALTH: OK",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H004",
            title="Run golden path",
            command="python examples/golden_path/run_golden_path.py",
            expected="GOLDEN PATH COMPLETE; all 6 steps succeed",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H005",
            title="Run complexity gate",
            command="python v3/cli/systemkernel.py quality",
            expected="Complexity verdict: ACCEPT or REVIEW (not REJECT)",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H006",
            title="Inspect release notes",
            command="python -c \"from v3.release.release_notes import generate_release_notes; print(generate_release_notes())\"",
            expected="Release notes contain version 3.0.0 and all completed phases",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H007",
            title="Inspect clone plan",
            command="python v3/cli/systemkernel.py intake clone-list",
            expected="Clone plan printed; PLAN ONLY; no actual cloning performed",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H008",
            title="Verify memory removable",
            command="python -c \"import json; d=json.load(open('v3/exports/memory_system_report.json')); print(d.get('verdicts',{}).get('removability','?'))\"",
            expected="Removability: YES",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H009",
            title="Verify no network/clone assumption",
            command="python v3/tests/test_baseline_packaging.py",
            expected="Test that verifies no network/clone/install commands in verify script",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H010",
            title="Run baseline packaging tests",
            command="python v3/tests/test_baseline_packaging.py",
            expected="All 21 baseline packaging tests pass",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H011",
            title="Run verification script",
            command="python scripts/verify_v3_baseline.py",
            expected="All checks PASS; exit code 0",
            required=True,
            status="PENDING",
        ),
        HandoffChecklistItem(
            id="H012",
            title="Verify package manifest",
            command="python -c \"from v3.release.package_manifest import build_package_manifest, verify_package_manifest; m=build_package_manifest(); ok,_=verify_package_manifest(m); print('OK' if ok else 'FAIL')\"",
            expected="Package manifest verification: OK",
            required=True,
            status="PENDING",
        ),
    )

    verification_commands = (
        "python v3/tests/test_kernel_invariants.py",
        "python v3/tests/test_release_freeze.py",
        "python v3/tests/test_baseline_packaging.py",
        "python v3/tests/test_golden_path.py",
        "python v3/tests/test_complexity_budget.py",
        "python v3/tests/test_developer_cli.py",
        "python v3/cli/systemkernel.py doctor",
        "python v3/cli/systemkernel.py status",
        "python v3/cli/systemkernel.py reports summary",
        "python examples/golden_path/run_golden_path.py",
        "python scripts/verify_v3_baseline.py",
    )

    rollback_notes = (
        "SystemKernel v3.0 is a baseline release. Rollback means reverting\n"
        "to the previous commit before Phase 4-6 changes were applied.\n"
        "\n"
        "Git rollback:\n"
        "  git log --oneline -20          # find the pre-v3.0 commit\n"
        "  git checkout <commit-hash>     # detach to that commit\n"
        "  # OR: git revert <range>       # create revert commits\n"
        "\n"
        "Data safety:\n"
        "  - All memory data is in v3/checkpoints/ and v3/traces/\n"
        "  - These are append-only JSONL — no data loss on rollback\n"
        "  - Metrics are in v3/metrics/ — append-only\n"
        "  - Kernel source is unchanged by operation\n"
        "\n"
        "What rollback does NOT affect:\n"
        "  - External tool installations (separate repos)\n"
        "  - Git history (immutable)\n"
        "  - System configuration outside this repo\n"
        "\n"
        "Safe rollback procedure:\n"
        "  1. Run: python scripts/verify_v3_baseline.py  (confirm current state)\n"
        "  2. Note the current commit hash\n"
        "  3. git checkout <target-commit>\n"
        "  4. Run: python scripts/verify_v3_baseline.py  (confirm restored state)\n"
        "  5. Validate that expected behavior is restored"
    )

    known_limitations = (
        "Single-machine only — no distributed execution. Event store is local JSONL.",
        "No real-time streaming — execution is batch-oriented.",
        "Memory is lexical only — semantic index uses tokenization, not embeddings.",
        "14 repo profiles — intake pipeline covers 14 known repos.",
        "No MCP server — CLI is the primary interface.",
        "No web UI — stdout text output only.",
        "Windows paths — default paths use F:/Claude/ conventions.",
        "No incremental adoption path — requires full SystemKernel runtime.",
        "Verification script requires Python 3.10+ (standard library only).",
        "Golden path uses temporary directories — cleaned up after each run.",
        "Checkpoint data is session-scoped — no cross-session replay guarantee.",
        "No automated baseline archival — manual version tagging required.",
    )

    # Compute handoff hash
    checklist_dicts = [c.to_dict() for c in checklist]
    hash_input = json.dumps({
        "version": "3.0.0",
        "checklist": checklist_dicts,
        "verification_commands": list(verification_commands),
        "known_limitations": list(known_limitations),
    }, sort_keys=True, ensure_ascii=False)
    handoff_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return OperationalHandoff(
        version="3.0.0",
        checklist=checklist,
        verification_commands=verification_commands,
        rollback_notes=rollback_notes,
        known_limitations=known_limitations,
        handoff_hash=handoff_hash,
    )


# ═══════════════════════════════════════════════════════════════════════
# Writers
# ═══════════════════════════════════════════════════════════════════════

def write_handoff_json(handoff: OperationalHandoff, path: str) -> str:
    """Write operational handoff to JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(handoff.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)


def write_handoff_md(handoff: OperationalHandoff, path: str) -> str:
    """Write operational handoff to Markdown file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    lines = []
    lines.append("# SystemKernel v3.0 — Operational Handoff")
    lines.append("")
    lines.append(f"**Version:** {handoff.version}")
    lines.append(f"**Handoff Hash:** {handoff.handoff_hash}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Verification Checklist")
    lines.append("")
    lines.append("| ID | Title | Command | Expected | Required | Status |")
    lines.append("|----|-------|---------|----------|----------|--------|")
    for c in handoff.checklist:
        req = "YES" if c.required else "NO"
        cmd_short = c.command[:60] + ("..." if len(c.command) > 60 else "")
        lines.append(f"| {c.id} | {c.title} | `{cmd_short}` | {c.expected} | {req} | {c.status} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Verification Commands")
    lines.append("")
    lines.append("Run these commands in order to verify the v3.0 baseline:")
    lines.append("")
    for i, cmd in enumerate(handoff.verification_commands, 1):
        lines.append(f"{i}. `{cmd}`")
    lines.append("")
    lines.append("Or run the single verification script:")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/verify_v3_baseline.py")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Rollback Guidance")
    lines.append("")
    for line in handoff.rollback_notes.split("\n"):
        lines.append(line)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Known Limitations")
    lines.append("")
    for i, lim in enumerate(handoff.known_limitations, 1):
        lines.append(f"{i}. {lim}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Complexity Gate Policy")
    lines.append("")
    lines.append("The complexity gate has three verdicts:")
    lines.append("")
    lines.append("- **ACCEPT** — complexity is within budget; proceed freely.")
    lines.append("- **REVIEW** — complexity exceeds benefit threshold; manual review")
    lines.append("  recommended but does not block release.")
    lines.append("- **REJECT** — complexity severely exceeds budget; release blocked.")
    lines.append("")
    lines.append("Current policy: REVIEW is a warning, not a gate. Only REJECT blocks.")
    lines.append("The v3.0 baseline targets REVIEW at worst.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## External Tool Clone Policy")
    lines.append("")
    lines.append("External tools referenced in the external tool registry and clone plan")
    lines.append("are NOT part of SystemKernel. They are separate repositories with their")
    lines.append("own licenses, maintainers, and security postures.")
    lines.append("")
    lines.append("Rules:")
    lines.append("")
    lines.append("1. Clone external tools into `F:/Claude/Github/` — outside kernel boundary.")
    lines.append("2. Do NOT integrate external tools into kernel source tree.")
    lines.append("3. All clone operations require manual review and execution.")
    lines.append("4. No automated git clone in any kernel module.")
    lines.append("5. External tools are separately audited before integration.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## What NOT to Modify After Freeze")
    lines.append("")
    lines.append("The following are FROZEN and must not be modified without a new")
    lines.append("major version (v4.0):")
    lines.append("")
    lines.append("- Kernel execution pipeline order (lint → typecheck → test → report)")
    lines.append("- EventBus routing table (13 deterministic rules)")
    lines.append("- Adapter resolve() semantics (deterministic, empty binding on no match)")
    lines.append("- TaskSystem state machine (backlog → active → done)")
    lines.append("- Registry schema (9 required fields per skill)")
    lines.append("- ExecutionLoop retry policy (max 2 attempts)")
    lines.append("- Sandbox configuration (timeouts, filesystem scope)")
    lines.append("- Observability contract (write-only, append-only, removable)")
    lines.append("- Memory boundary (kernel must not import from v3.memory)")
    lines.append("")
    lines.append("Safe to add (future phases):")
    lines.append("")
    lines.append("- New test files")
    lines.append("- New export reports")
    lines.append("- New documentation files")
    lines.append("- New examples")
    lines.append("- New CLI commands (that don't modify kernel behavior)")
    lines.append("- New external tool profiles in the intake registry")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*SystemKernel v3.0 Operational Handoff — Phase 6A*")
    lines.append(f"*Generated: {handoff.handoff_hash}*")
    lines.append("")

    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return os.path.abspath(path)
