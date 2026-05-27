"""
ECC / everything-claude-code — Positioning Analysis (Phase 13A).

Stdlib only. Read-only analysis. No ECC installation, execution, or integration.

ECC is treated as a future external harness enhancement provider.
SystemKernel uses/evaluates ECC, never becomes an ECC clone.

This module defines the ECC capability mapping, positioning report,
and forbidden-action guard. It does NOT implement an ECC adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parent.parent.parent

# ── ECC identity constants ───────────────────────────────────────────────────

ECC_REPO_NAME = "ECC / everything-claude-code"
ECC_REPO_URL = "https://github.com/affaan-m/everything-claude-code"
ECC_CATEGORY_HINT = "harness_enhancement / skill_system / tool_system"
ECC_INTENDED_USE = "architecture_reference + future_external_provider"
ECC_USE_MODE = "source_reference / future_harness_provider"

ECC_EXPECTED_DECISION = "EXTERNAL_EXTENSION"

ECC_ALLOWED_ACTIONS = (
    "inspect docs",
    "compare taxonomy",
    "map to SystemKernel capability types",
    "generate evidence in future",
)

ECC_FORBIDDEN_ACTIONS = (
    "install ECC",
    "run ECC",
    "import ECC",
    "modify kernel",
    "overwrite CLAUDE.md",
    "copy ECC wholesale",
    "turn SystemKernel into ECC clone",
)

ECC_RECOMMENDED_ROLE = "external_harness_reference_only"


# ── Frozen dataclasses ───────────────────────────────────────────────────────

def _hash_content(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _hash_dict(d: dict) -> str:
    raw = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ECCCapabilityMapping:
    """Maps one ECC capability area to a SystemKernel plane."""
    ecc_area: str
    systemkernel_plane: str
    use_mode: str  # learn | reference | external_provider | reject
    reuse_strategy: str
    risk_level: str  # low | medium | high
    notes: str
    mapping_hash: str


@dataclass(frozen=True)
class ECCPositioningReport:
    """Full ECC positioning analysis report."""
    repo_name: str
    repo_url: str
    recommended_role: str
    mappings: Tuple[ECCCapabilityMapping, ...]
    reusable_patterns: Tuple[str, ...]
    forbidden_patterns: Tuple[str, ...]
    overlap_with_systemkernel: Tuple[str, ...]
    differentiation_strategy: str
    complexity_risk: str  # low | medium | high
    clone_now: str  # YES | NO | MAYBE
    integrate_now: str  # NO (always)
    report_hash: str


# ── Capability mapping builder ───────────────────────────────────────────────

def build_ecc_capability_mapping() -> Tuple[ECCCapabilityMapping, ...]:
    """Build the deterministic ECC capability mapping.

    Maps ECC capability areas to SystemKernel planes with reuse strategies.
    """
    mappings = [
        ECCCapabilityMapping(
            ecc_area="ECC skills / skill system",
            systemkernel_plane="Skill Evolution Plane",
            use_mode="reference",
            reuse_strategy="learn taxonomy, compare metadata, do not copy",
            risk_level="low",
            notes="ECC skill taxonomy is a useful reference for registry structure. No skill code is reused.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC doctor / repair",
            systemkernel_plane="Productization + Ops",
            use_mode="learn",
            reuse_strategy="learn UX patterns, do not copy implementation",
            risk_level="low",
            notes="ECC self-healing UX is well-designed. SystemKernel has its own doctor/ops via v4_ops.py and runbook.py.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC cross-harness abstraction (Codex/Cursor/etc.)",
            systemkernel_plane="Capability Registry",
            use_mode="reference",
            reuse_strategy="architecture reference for multi-harness patterns",
            risk_level="low",
            notes="SystemKernel is a single kernel, not a multi-harness adapter. Reference for future multi-IDE support.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC memory optimization",
            systemkernel_plane="Memory Intelligence Plane",
            use_mode="learn",
            reuse_strategy="compare compaction/recall patterns, do not copy",
            risk_level="low",
            notes="ECC memory patterns (compression, indexing) may inform SystemKernel Memory Intelligence evolution.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC workflows / instincts",
            systemkernel_plane="Orchestration Policy",
            use_mode="reference",
            reuse_strategy="reference for policy pattern design",
            risk_level="low",
            notes="ECC workflow/instinct system is a reference for orchestration policy UX. Not copied.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC plugin / install system",
            systemkernel_plane="External Registry + Skill Management",
            use_mode="reference",
            reuse_strategy="source reference for package management patterns",
            risk_level="low",
            notes="SystemKernel has its own skill package system. ECC's plugin design can inform future improvements.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC security scanning",
            systemkernel_plane="Evaluation Harness",
            use_mode="external_provider",
            reuse_strategy="possible future evidence provider for security eval",
            risk_level="medium",
            notes="Security scanning is a natural fit for eval harness. Could provide evidence in future, not now.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC CLAUDE.md / project initialization",
            systemkernel_plane="Context Plane",
            use_mode="reference",
            reuse_strategy="reference CLAUDE.md generation patterns",
            risk_level="low",
            notes="SystemKernel CLAUDE.md is manually governed. ECC init patterns may inspire tooling.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC tool system",
            systemkernel_plane="External Adapters (disabled)",
            use_mode="reject",
            reuse_strategy="do not adopt; SystemKernel has its own external adapter model",
            risk_level="high",
            notes="SystemKernel external tool model is contract-based with evidence bundling. ECC tool system is different architecture.",
            mapping_hash="",
        ),
        ECCCapabilityMapping(
            ecc_area="ECC agent / subagent system",
            systemkernel_plane="Agent Worker Plane",
            use_mode="reject",
            reuse_strategy="do not adopt; SystemKernel agent worker design is skill-driven, not task-driven",
            risk_level="high",
            notes="Architecture conflict. SystemKernel agents are skill-dispatched via deterministic routing; ECC agents are LLM-driven.",
            mapping_hash="",
        ),
    ]

    # Populate hashes after construction
    result = []
    for m in mappings:
        raw = f"{m.ecc_area}|{m.systemkernel_plane}|{m.use_mode}|{m.reuse_strategy}|{m.risk_level}"
        h = _hash_content(raw)
        result.append(ECCCapabilityMapping(
            ecc_area=m.ecc_area,
            systemkernel_plane=m.systemkernel_plane,
            use_mode=m.use_mode,
            reuse_strategy=m.reuse_strategy,
            risk_level=m.risk_level,
            notes=m.notes,
            mapping_hash=h,
        ))

    return tuple(sorted(result, key=lambda m: m.ecc_area))


# ── Positioning report builder ───────────────────────────────────────────────

def build_ecc_positioning_report() -> ECCPositioningReport:
    """Build the full ECC positioning analysis report."""
    mappings = build_ecc_capability_mapping()

    reusable_patterns = (
        "skill taxonomy structure as registry reference",
        "doctor/self-repair UX patterns for ops improvements",
        "cross-harness abstraction patterns for future multi-IDE support",
        "memory compaction/indexing patterns as design reference",
        "workflow/instinct model as orchestration policy UX reference",
        "plugin/install system as package management reference",
    )

    forbidden_patterns = (
        "install ECC — no install, no execution, no dependency",
        "run ECC — no execution of ECC commands or workflows",
        "import ECC — no Python import of ECC modules",
        "modify kernel — no kernel changes based on ECC",
        "overwrite CLAUDE.md — SystemKernel CLAUDE.md is manually governed",
        "copy ECC wholesale — reference patterns, never copy code",
        "turn SystemKernel into ECC clone — must remain deterministic kernel",
        "add ECC to kernel imports — ECC is external, never in kernel boundary",
        "expand CLI for ECC — no new CLI surface for ECC operations",
        "ECC-driven agent dispatch — agent routing remains deterministic",
    )

    overlap_with_systemkernel = (
        "skill management and taxonomy",
        "project initialization / CLAUDE.md generation",
        "memory optimization and compaction",
        "workflow / instinct / policy patterns",
        "external tool wrapping",
        "security / quality scanning",
        "cross-harness / multi-IDE abstraction",
    )

    differentiation = (
        "ECC = harness enhancement kit (skills, tools, UX, workflows). "
        "SystemKernel = deterministic governance/runtime/evidence kernel. "
        "ECC enhances HOW developers use AI tools. "
        "SystemKernel governs WHAT gets executed and verifies it happened. "
        "ECC is a toolbelt; SystemKernel is a kernel. "
        "They are complementary, not competing. "
        "SystemKernel may use ECC as an external capability provider in future, "
        "but must never embed ECC logic in the kernel boundary."
    )

    complexity_risk = "medium"

    report_data = {
        "repo": ECC_REPO_NAME,
        "recommended_role": ECC_RECOMMENDED_ROLE,
        "mapping_count": len(mappings),
        "use_modes": {"learn": 0, "reference": 0, "external_provider": 0, "reject": 0},
    }
    for m in mappings:
        if m.use_mode in report_data["use_modes"]:
            report_data["use_modes"][m.use_mode] += 1

    report_hash = _hash_dict(report_data)

    return ECCPositioningReport(
        repo_name=ECC_REPO_NAME,
        repo_url=ECC_REPO_URL,
        recommended_role=ECC_RECOMMENDED_ROLE,
        mappings=mappings,
        reusable_patterns=reusable_patterns,
        forbidden_patterns=forbidden_patterns,
        overlap_with_systemkernel=overlap_with_systemkernel,
        differentiation_strategy=differentiation,
        complexity_risk=complexity_risk,
        clone_now="MAYBE",
        integrate_now="NO",
        report_hash=report_hash,
    )


# ── Report writer ────────────────────────────────────────────────────────────

def write_ecc_positioning_report(report: ECCPositioningReport, output_dir: str) -> dict:
    """Write ECC positioning reports (JSON, MD, phase report). Returns paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── JSON ──
    json_data = {
        "phase": "13A",
        "title": "ECC Intake + Positioning Analysis",
        "repo_name": report.repo_name,
        "repo_url": report.repo_url,
        "recommended_role": report.recommended_role,
        "complexity_risk": report.complexity_risk,
        "clone_now": report.clone_now,
        "integrate_now": report.integrate_now,
        "report_hash": report.report_hash,
        "mappings": [
            {
                "ecc_area": m.ecc_area,
                "systemkernel_plane": m.systemkernel_plane,
                "use_mode": m.use_mode,
                "reuse_strategy": m.reuse_strategy,
                "risk_level": m.risk_level,
                "notes": m.notes,
                "mapping_hash": m.mapping_hash,
            }
            for m in report.mappings
        ],
        "reusable_patterns": list(report.reusable_patterns),
        "forbidden_patterns": list(report.forbidden_patterns),
        "overlap_with_systemkernel": list(report.overlap_with_systemkernel),
        "differentiation_strategy": report.differentiation_strategy,
    }
    json_path = out / "ecc_positioning_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str)

    # ── Markdown ──
    md_lines = [
        "# ECC Positioning Report — Phase 13A",
        "",
        f"**Repo:** [{report.repo_name}]({report.repo_url})",
        f"**Recommended role:** `{report.recommended_role}`",
        f"**Clone now:** {report.clone_now}",
        f"**Integrate now:** {report.integrate_now}",
        f"**Complexity risk:** {report.complexity_risk.upper()}",
        "",
        "## Differentiation Strategy",
        "",
        report.differentiation_strategy,
        "",
        "## Capability Mapping",
        "",
        "| ECC Area | SystemKernel Plane | Use Mode | Reuse Strategy | Risk |",
        "|----------|-------------------|----------|---------------|------|",
    ]
    for m in report.mappings:
        md_lines.append(
            f"| {m.ecc_area} | {m.systemkernel_plane} | `{m.use_mode}` | {m.reuse_strategy} | {m.risk_level} |"
        )

    md_lines += [
        "",
        "## Reusable Patterns",
        "",
    ]
    for p in report.reusable_patterns:
        md_lines.append(f"- {p}")

    md_lines += [
        "",
        "## Forbidden Patterns",
        "",
    ]
    for p in report.forbidden_patterns:
        md_lines.append(f"- **FORBIDDEN:** {p}")

    md_lines += [
        "",
        "## Overlap with SystemKernel",
        "",
    ]
    for o in report.overlap_with_systemkernel:
        md_lines.append(f"- {o}")

    md_lines += [
        "",
        "## Decision Log",
        "",
        "- **Phase 13A Decision:** ECC intake complete. No integration, no clone, no adapter.",
        "- **Next real action:** Manual review of ECC repo (read-only) if user grants clone permission.",
        "- **Future trial phase:** Requires explicit user authorization, separate phase gate.",
    ]

    md_path = out / "ecc_positioning_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # ── Phase report ──
    phase_lines = [
        "# Phase 13A — ECC Intake + Positioning Analysis",
        "",
        f"**Date:** 2026-05-27",
        f"**Status:** COMPLETE",
        "",
        "## Summary",
        "",
        f"- Repo: [{report.repo_name}]({report.repo_url})",
        f"- Role: {report.recommended_role}",
        f"- Clone now: {report.clone_now}",
        f"- Integrate now: {report.integrate_now}",
        f"- Mappings: {len(report.mappings)} capability areas mapped",
        f"- Use modes: learn/reference/external_provider/reject",
        "",
        "## Key Decisions",
        "",
        "1. **ECC is an external reference, not a dependency.**",
        "2. **No ECC installation, execution, or import.**",
        "3. **SystemKernel must never become an ECC clone.**",
        "4. **Future ECC usage would go through the pluggable intelligence plane.**",
        "5. **ECC security scanning is the only candidate for future external_provider use.**",
        "",
        "## Differentiation",
        "",
        report.differentiation_strategy,
        "",
        "## Complexity Gate",
        "",
        f"- Current risk: **{report.complexity_risk.upper()}**",
        "- Phase 13C simplification audit risk was also MEDIUM.",
        "- Adding ECC positioning (no code, no adapter) does not increase risk.",
        "- Full ECC integration would push risk to HIGH. Rejected.",
        "",
        "## Recommendation",
        "",
        "**Proceed to simplification pass (Phase 13D) before any real provider trial.**",
        "proceed_to_real_provider_trial: NO (not until complexity risk is LOW)",
        "proceed_to_simplification_pass: YES (13D CLI Surface Compression recommended)",
        "stop: NO",
        "",
        "## Next Phase",
        "",
        "Phase 13D — CLI Surface Compression (systemkernel.py 3076 LOC / 57 subcommands).",
    ]

    phase_path = out / "phase_13a_ecc_intake_report.md"
    with open(phase_path, "w", encoding="utf-8") as f:
        f.write("\n".join(phase_lines))

    return {
        "json": str(json_path),
        "md": str(md_path),
        "phase_report": str(phase_path),
    }


# ── Forbidden action guard ───────────────────────────────────────────────────

def check_ecc_forbidden_actions(action: str) -> bool:
    """Return True if action is allowed, False if forbidden.

    This is a static safety check — it does not execute anything.
    """
    for forbidden in ECC_FORBIDDEN_ACTIONS:
        keywords = forbidden.lower().split()
        action_lower = action.lower()
        # All keywords must match for it to count as forbidden
        if all(kw in action_lower for kw in keywords):
            return False
    return True


# ── CLI entry ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  ECC / everything-claude-code — Positioning Analysis")
    print("  Phase 13A — ECC Intake")
    print("=" * 60)
    print()

    report = build_ecc_positioning_report()

    print(f"  Repo:              {report.repo_name}")
    print(f"  URL:               {report.repo_url}")
    print(f"  Recommended role:  {report.recommended_role}")
    print(f"  Clone now:         {report.clone_now}")
    print(f"  Integrate now:     {report.integrate_now}")
    print(f"  Complexity risk:   {report.complexity_risk.upper()}")
    print(f"  Mappings:          {len(report.mappings)}")
    print()

    print("  Capability Mapping:")
    for m in report.mappings:
        print(f"    [{m.use_mode:>18}] {m.ecc_area}")
        print(f"                      → {m.systemkernel_plane}")
    print()

    print("  Forbidden Actions (abridged):")
    for f in report.forbidden_patterns[:5]:
        print(f"    - {f}")
    print(f"    ... ({len(report.forbidden_patterns)} total)")
    print()

    # Write reports
    exports_dir = ROOT / "v3" / "exports"
    paths = write_ecc_positioning_report(report, str(exports_dir))
    print("  Reports written:")
    for k, v in paths.items():
        print(f"    {k}: {v}")
    print()

    print("  Differentiation:", report.differentiation_strategy[:120], "...")
    print()

    print("  Recommendation:")
    print("    proceed_to_real_provider_trial: NO")
    print("    proceed_to_simplification_pass: YES (Phase 13D)")
    print("    stop: NO")
    print()

    print("  Phase 13A complete.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
