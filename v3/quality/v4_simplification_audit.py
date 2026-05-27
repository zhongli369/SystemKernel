"""
SystemKernel v4.0 — Simplification / API Surface Reduction Audit.

Standard library only. AST-based static analysis. No dynamic imports.
Audit-first: identifies opportunities, does NOT refactor.

Phase 13C — v4 Simplification Audit.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Frozen dataclasses ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ModuleSurfaceMetrics:
    """Static surface metrics for a single Python module."""
    path: str
    loc: int
    dataclass_count: int
    public_function_count: int
    private_function_count: int
    public_export_count: int
    cli_command_count: int
    test_count: int
    report_count: int
    dependency_count: int
    complexity_score: float
    surface_hash: str


@dataclass(frozen=True)
class SimplificationOpportunity:
    """A single simplification opportunity detected during audit."""
    opportunity_id: str
    category: str  # see CATEGORIES
    target_path: str
    description: str
    expected_complexity_reduction: float
    behavior_risk: str  # low | medium | high
    recommended_action: str  # keep | simplify_later | simplify_now | do_not_touch
    reason: str
    opportunity_hash: str


@dataclass(frozen=True)
class SimplificationAuditReport:
    """Full audit report aggregating all findings."""
    modules_analyzed: int
    total_loc: int
    total_public_api: int
    total_exports: int
    opportunities: tuple
    safe_now_count: int
    defer_count: int
    do_not_touch_count: int
    ability_plus_10_complexity_plus_300_risk: str  # low | medium | high
    report_hash: str


# ── Constants ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent

AUDIT_TARGETS = [
    "v3/external",
    "v3/evals",
    "v3/ops",
    "v3/release",
    "v3/cli",
    "v3/tests",
    "v3/quality",
]

DO_NOT_TOUCH_PATHS = {
    "v3/kernel",
    "v3/memory/memory_adapter_base.py",
    "v3/memory/episodic_store.py",
    "v3/memory/semantic_index.py",
    "v3/memory/recall.py",
    "v3/memory/retrieval.py",
    "v3/memory/runtime.py",
    "v3/memory/provenance.py",
    "v3/memory/compaction.py",
    "v3/memory/compaction_integrity.py",
    "v3/memory/index_integrity.py",
    "v3/memory/integrity.py",
    "v3/memory/system_report.py",
    "v3/memory/memory_service.py",
    "v3/memory/episodic_adapter.py",
    "v3/release",
    "scripts/verify_v3_baseline.py",
    "scripts/verify_v4_baseline.py",
}

CATEGORIES = {
    "duplicate_helper",
    "excessive_exports",
    "oversized_module",
    "redundant_report",
    "cli_surface_sprawl",
    "duplicated_policy_logic",
    "docs_overlap",
    "fixture_overlap",
    "no_action",
}

Oversized_threshold_lines = 600
EXCESSIVE_EXPORTS_THRESHOLD = 15
CLI_SPRAWL_THRESHOLD = 30
COMPLEXITY_HIGH_WATERMARK = 25.0

# ── AST analysis helpers ─────────────────────────────────────────────────────

def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _hash_dict(d: dict) -> str:
    raw = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _is_public(name: str) -> bool:
    return not name.startswith("_") or name.startswith("__") and name.endswith("__")


def _count_lines(filepath: Path) -> int:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _extract_docstring(node) -> Optional[str]:
    return ast.get_docstring(node)


# ── Module surface analysis ──────────────────────────────────────────────────

def analyze_module_surface(rel_path: str) -> ModuleSurfaceMetrics:
    """Analyze a single Python module's surface metrics via AST walk."""
    full_path = ROOT / rel_path
    source = ""
    loc = 0
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        loc = len(source.splitlines())
    except Exception:
        return ModuleSurfaceMetrics(
            path=rel_path, loc=0, dataclass_count=0,
            public_function_count=0, private_function_count=0,
            public_export_count=0, cli_command_count=0,
            test_count=0, report_count=0, dependency_count=0,
            complexity_score=0.0, surface_hash=_hash_content(""),
        )

    tree = None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        pass

    dataclass_count = 0
    public_func_count = 0
    private_func_count = 0
    public_export_count = 0
    cli_command_count = 0
    test_count = 0
    report_count = 0
    dependency_count = 0

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Detect dataclasses via @dataclass decorator
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name) and dec.id == "dataclass":
                        dataclass_count += 1
                        break
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "dataclass":
                        dataclass_count += 1
                        break

            if isinstance(node, ast.FunctionDef):
                name = node.name
                if name == "cmd_status":
                    # approximate: detect CLI dispatch functions in systemkernel.py
                    pass
                if name.startswith("test_"):
                    test_count += 1
                elif _is_public(name):
                    public_func_count += 1
                else:
                    private_func_count += 1

            # Detect CLI subcommand registrations (argparse add_parser calls)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "add_parser":
                        cli_command_count += 1

            # Count imports as dependency proxy
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                dependency_count += 1

            # Detect report generation via "report" or "Report" in function names
            if isinstance(node, ast.FunctionDef):
                if "report" in node.name.lower() or "generate" in node.name.lower():
                    report_count += 1

        # Count __all__ exports
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            public_export_count = len(node.value.elts)

    # Complexity score: weighted combination
    complexity_score = (
        (loc / 100.0) * 0.3
        + public_func_count * 1.0
        + public_export_count * 0.5
        + cli_command_count * 2.0
        + dependency_count * 0.2
        + dataclass_count * 0.8
    )
    complexity_score = round(complexity_score, 2)

    surface_hash = _hash_content(
        f"{rel_path}:{loc}:{dataclass_count}:{public_func_count}:{public_export_count}:{cli_command_count}"
    )

    return ModuleSurfaceMetrics(
        path=rel_path,
        loc=loc,
        dataclass_count=dataclass_count,
        public_function_count=public_func_count,
        private_function_count=private_func_count,
        public_export_count=public_export_count,
        cli_command_count=cli_command_count,
        test_count=test_count,
        report_count=report_count,
        dependency_count=dependency_count,
        complexity_score=complexity_score,
        surface_hash=surface_hash,
    )


# ── Opportunity detection ────────────────────────────────────────────────────

def find_simplification_opportunities(
    all_metrics: list[ModuleSurfaceMetrics],
) -> list[SimplificationOpportunity]:
    """Detect simplification opportunities from module surface metrics."""
    opportunities = []
    oid = 0

    # Sort metrics by complexity_score descending
    sorted_metrics = sorted(all_metrics, key=lambda m: m.complexity_score, reverse=True)

    # ── oversized_module ──
    for m in sorted_metrics:
        if m.loc > Oversized_threshold_lines:
            oid += 1
            opportunities.append(SimplificationOpportunity(
                opportunity_id=f"SIMPLIFY-{oid:03d}",
                category="oversized_module",
                target_path=m.path,
                description=f"Module exceeds {Oversized_threshold_lines} lines ({m.loc} LOC). Consider extracting helper modules.",
                expected_complexity_reduction=round(m.complexity_score * 0.3, 2),
                behavior_risk="medium",
                recommended_action="simplify_later",
                reason="Large modules increase cognitive load. Safe to split if public API preserved.",
                opportunity_hash=_hash_content(f"oversized:{m.path}:{m.loc}"),
            ))

    # ── excessive_exports ──
    for m in sorted_metrics:
        if m.public_export_count > EXCESSIVE_EXPORTS_THRESHOLD:
            oid += 1
            opportunities.append(SimplificationOpportunity(
                opportunity_id=f"SIMPLIFY-{oid:03d}",
                category="excessive_exports",
                target_path=m.path,
                description=f"Module exports {m.public_export_count} public symbols. Reduce to core API surface.",
                expected_complexity_reduction=round(m.public_export_count * 0.15, 2),
                behavior_risk="medium",
                recommended_action="simplify_later",
                reason="Large __all__ inflates API surface. Audit which exports are actually consumed.",
                opportunity_hash=_hash_content(f"exports:{m.path}:{m.public_export_count}"),
            ))

    # ── cli_surface_sprawl ──
    for m in sorted_metrics:
        if m.cli_command_count > CLI_SPRAWL_THRESHOLD:
            oid += 1
            opportunities.append(SimplificationOpportunity(
                opportunity_id=f"SIMPLIFY-{oid:03d}",
                category="cli_surface_sprawl",
                target_path=m.path,
                description=f"CLI module has {m.cli_command_count} subcommands. Consider grouping or removing rarely used commands.",
                expected_complexity_reduction=round(m.cli_command_count * 0.25, 2),
                behavior_risk="medium",
                recommended_action="simplify_later",
                reason="57 CLI subcommands is a large surface. Audit which are used and which are scaffolding.",
                opportunity_hash=_hash_content(f"cli:{m.path}:{m.cli_command_count}"),
            ))

    # ── duplicated_policy_logic ──
    policy_files = [m for m in all_metrics if "policy" in m.path.lower() and m.path.endswith(".py")]
    if len(policy_files) >= 3:
        oid += 1
        policy_paths = ", ".join(p.path for p in policy_files[:5])
        opportunities.append(SimplificationOpportunity(
            opportunity_id=f"SIMPLIFY-{oid:03d}",
            category="duplicated_policy_logic",
            target_path="v3/external/",
            description=f"Multiple policy modules detected ({len(policy_files)} files). Consider consolidating shared policy logic.",
            expected_complexity_reduction=round(len(policy_files) * 1.2, 2),
            behavior_risk="medium",
            recommended_action="simplify_later",
            reason=f"Policy files ({policy_paths}) may share validation patterns. Consolidate into shared base.",
            opportunity_hash=_hash_content(f"policy:{policy_paths}"),
        ))

    # ── duplicate_helper ──
    profile_files = [m for m in all_metrics if "profiles" in m.path.lower() and m.path.endswith(".py")]
    if len(profile_files) >= 3:
        oid += 1
        profile_paths = ", ".join(p.path for p in profile_files[:5])
        opportunities.append(SimplificationOpportunity(
            opportunity_id=f"SIMPLIFY-{oid:03d}",
            category="duplicate_helper",
            target_path="v3/external/",
            description=f"Multiple profiles modules ({len(profile_files)} files). Consider unifying profile loading.",
            expected_complexity_reduction=round(len(profile_files) * 0.8, 2),
            behavior_risk="low",
            recommended_action="simplify_later",
            reason=f"Profile modules ({profile_paths}) follow similar patterns. A shared loader reduces duplication.",
            opportunity_hash=_hash_content(f"profiles:{profile_paths}"),
        ))

    # ── redundant_report ──
    report_heavy = [m for m in all_metrics if m.report_count >= 5]
    for m in report_heavy:
        oid += 1
        opportunities.append(SimplificationOpportunity(
            opportunity_id=f"SIMPLIFY-{oid:03d}",
            category="redundant_report",
            target_path=m.path,
            description=f"Module generates {m.report_count} report functions. Audit for overlap in generated reports.",
            expected_complexity_reduction=round(m.report_count * 0.4, 2),
            behavior_risk="low",
            recommended_action="simplify_later",
            reason="Multiple report generators may produce overlapping output. Consolidate where safe.",
            opportunity_hash=_hash_content(f"reports:{m.path}:{m.report_count}"),
        ))

    # ── docs_overlap ──
    docs_dir = ROOT / "Docs"
    exports_docs = list((ROOT / "v3" / "exports").glob("*.md"))
    if docs_dir.exists() and exports_docs:
        oid += 1
        opportunities.append(SimplificationOpportunity(
            opportunity_id=f"SIMPLIFY-{oid:03d}",
            category="docs_overlap",
            target_path="Docs/ + v3/exports/*.md",
            description=f"Documentation exists in both Docs/ ({len(list(docs_dir.glob('*.md')))}) and v3/exports/ ({len(exports_docs)} .md files). Consider consolidating.",
            expected_complexity_reduction=2.0,
            behavior_risk="low",
            recommended_action="simplify_later",
            reason="Two documentation directories create maintenance burden. Consolidate into one location.",
            opportunity_hash=_hash_content(f"docs_overlap:{len(list(docs_dir.glob('*.md')))}:{len(exports_docs)}"),
        ))

    # ── fixture_overlap ──
    fixture_dir = ROOT / "v3" / "tests" / "fixtures"
    if fixture_dir.exists():
        fixture_count = len(list(fixture_dir.glob("*.json")))
        if fixture_count >= 5:
            oid += 1
            opportunities.append(SimplificationOpportunity(
                opportunity_id=f"SIMPLIFY-{oid:03d}",
                category="fixture_overlap",
                target_path="v3/tests/fixtures/",
                description=f"{fixture_count} JSON test fixtures. Audit for unused or overlapping fixture data.",
                expected_complexity_reduction=1.0,
                behavior_risk="low",
                recommended_action="simplify_later",
                reason="Test fixtures may accumulate cruft. Safe to audit and prune unused ones.",
                opportunity_hash=_hash_content(f"fixtures:{fixture_count}"),
            ))

    # ── do_not_touch for release-critical paths ──
    for m in all_metrics:
        if any(m.path.startswith(dnt) or dnt in m.path for dnt in ["v3/release", "v3/kernel"]):
            # Already covered; skip extra opportunities for these
            pass

    # ── no_action for already-clean modules ──
    clean_modules = [m for m in all_metrics
                     if m.loc < 200
                     and m.public_export_count < 5
                     and m.cli_command_count == 0
                     and m.complexity_score < 5.0]
    for m in clean_modules[:3]:  # log top 3 cleanest
        oid += 1
        opportunities.append(SimplificationOpportunity(
            opportunity_id=f"SIMPLIFY-{oid:03d}",
            category="no_action",
            target_path=m.path,
            description=f"Module {m.path} is already lean ({m.loc} LOC, complexity {m.complexity_score}). No simplification needed.",
            expected_complexity_reduction=0.0,
            behavior_risk="low",
            recommended_action="keep",
            reason="Module is already minimal. No action recommended.",
            opportunity_hash=_hash_content(f"clean:{m.path}"),
        ))

    # Deduplicate by opportunity_hash
    seen = set()
    unique = []
    for opp in opportunities:
        if opp.opportunity_hash not in seen:
            seen.add(opp.opportunity_hash)
            unique.append(opp)
    return unique


# ── Audit report builder ─────────────────────────────────────────────────────

def build_v4_simplification_audit() -> SimplificationAuditReport:
    """Build the full v4 simplification audit report."""
    all_metrics = []

    for target in AUDIT_TARGETS:
        target_path = ROOT / target
        if not target_path.exists():
            continue
        py_files = list(target_path.rglob("*.py"))
        for py_file in py_files:
            rel = str(py_file.relative_to(ROOT)).replace("\\", "/")
            metrics = analyze_module_surface(rel)
            all_metrics.append(metrics)

    opportunities = find_simplification_opportunities(all_metrics)
    opportunities = sorted(opportunities, key=lambda o: (
        0 if o.recommended_action == "simplify_now" else
        1 if o.recommended_action == "simplify_later" else
        2 if o.recommended_action == "keep" else 3,
        -o.expected_complexity_reduction,
    ))

    safe_now = sum(1 for o in opportunities if o.recommended_action == "simplify_now")
    defer = sum(1 for o in opportunities if o.recommended_action == "simplify_later")
    do_not = sum(1 for o in opportunities if o.recommended_action == "do_not_touch")

    total_loc = sum(m.loc for m in all_metrics)
    total_api = sum(m.public_function_count for m in all_metrics)
    total_exp = sum(m.public_export_count for m in all_metrics)

    # Assess risk of ability+10% complexity+300%
    avg_complexity = sum(m.complexity_score for m in all_metrics) / max(len(all_metrics), 1)
    risk = "low"
    if avg_complexity > 20:
        risk = "high"
    elif avg_complexity > 12:
        risk = "medium"

    report_dict = {
        "modules_analyzed": len(all_metrics),
        "total_loc": total_loc,
        "total_public_api": total_api,
        "total_exports": total_exp,
        "opportunity_count": len(opportunities),
        "safe_now": safe_now,
        "defer": defer,
        "do_not_touch": do_not,
        "risk": risk,
    }
    report_hash = _hash_dict(report_dict)

    return SimplificationAuditReport(
        modules_analyzed=len(all_metrics),
        total_loc=total_loc,
        total_public_api=total_api,
        total_exports=total_exp,
        opportunities=tuple(opportunities),
        safe_now_count=safe_now,
        defer_count=defer,
        do_not_touch_count=do_not,
        ability_plus_10_complexity_plus_300_risk=risk,
        report_hash=report_hash,
    )


# ── Report writer ────────────────────────────────────────────────────────────

def write_simplification_audit(report: SimplificationAuditReport, output_dir: str) -> dict:
    """Write audit report as JSON, MD, and phase report. Returns paths written."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── JSON report ──
    json_data = {
        "phase": "13C",
        "title": "v4 Simplification / API Surface Reduction Audit",
        "modules_analyzed": report.modules_analyzed,
        "total_loc": report.total_loc,
        "total_public_api": report.total_public_api,
        "total_exports": report.total_exports,
        "safe_now_count": report.safe_now_count,
        "defer_count": report.defer_count,
        "do_not_touch_count": report.do_not_touch_count,
        "ability_plus_10_complexity_plus_300_risk": report.ability_plus_10_complexity_plus_300_risk,
        "report_hash": report.report_hash,
        "opportunities": [
            {
                "id": o.opportunity_id,
                "category": o.category,
                "target_path": o.target_path,
                "description": o.description,
                "expected_complexity_reduction": o.expected_complexity_reduction,
                "behavior_risk": o.behavior_risk,
                "recommended_action": o.recommended_action,
                "reason": o.reason,
            }
            for o in report.opportunities
        ],
    }
    json_path = out / "v4_simplification_audit.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str)

    # ── Markdown report ──
    md_lines = [
        "# SystemKernel v4.0 — Simplification Audit Report",
        "",
        f"**Phase:** 13C — v4 Simplification / API Surface Reduction Audit",
        f"**Modules analyzed:** {report.modules_analyzed}",
        f"**Total LOC:** {report.total_loc}",
        f"**Total public API functions:** {report.total_public_api}",
        f"**Total exports:** {report.total_exports}",
        f"**Ability+10% Complexity+300% risk:** **{report.ability_plus_10_complexity_plus_300_risk.upper()}**",
        "",
        "## Summary",
        "",
        f"- Safe to simplify now: **{report.safe_now_count}**",
        f"- Defer to later: **{report.defer_count}**",
        f"- Do not touch: **{report.do_not_touch_count}**",
        "",
        "## Do Not Touch (Protected)",
        "",
    ]
    for path in sorted(DO_NOT_TOUCH_PATHS):
        md_lines.append(f"- `{path}`")

    md_lines += [
        "",
        "## Simplification Opportunities",
        "",
    ]
    for o in report.opportunities:
        md_lines.append(f"### {o.opportunity_id}: {o.category} — [{o.recommended_action}]")
        md_lines.append(f"- **Target:** `{o.target_path}`")
        md_lines.append(f"- **Description:** {o.description}")
        md_lines.append(f"- **Complexity reduction:** {o.expected_complexity_reduction}")
        md_lines.append(f"- **Risk:** {o.behavior_risk}")
        md_lines.append(f"- **Reason:** {o.reason}")
        md_lines.append("")

    # Top 10 largest modules section
    md_lines.append("## Appendix: Audit Target Directories")
    md_lines.append("")
    for target in AUDIT_TARGETS:
        md_lines.append(f"- `{target}/`")

    md_path = out / "v4_simplification_audit.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # ── Phase report ──
    phase_lines = [
        "# Phase 13C — v4 Simplification / API Surface Reduction Audit",
        "",
        f"**Date:** 2026-05-27",
        f"**Status:** COMPLETE",
        "",
        "## Audit Results",
        "",
        f"- Modules analyzed: {report.modules_analyzed}",
        f"- Total LOC in audit scope: {report.total_loc}",
        f"- Total public API functions: {report.total_public_api}",
        f"- Total public exports: {report.total_exports}",
        "",
        "## Risk Assessment",
        "",
        f"- Ability+10% Complexity+300% risk: **{report.ability_plus_10_complexity_plus_300_risk.upper()}**",
        f"- Safe simplification candidates: {report.safe_now_count}",
        f"- Deferred candidates: {report.defer_count}",
        f"- Do not touch: {report.do_not_touch_count}",
        "",
        "## Top Opportunities",
        "",
    ]
    top = [o for o in report.opportunities if o.recommended_action != "keep"][:10]
    for i, o in enumerate(top, 1):
        phase_lines.append(f"{i}. **[{o.category}]** {o.description} — risk={o.behavior_risk}, action={o.recommended_action}")

    phase_lines += [
        "",
        "## Recommendation",
        "",
    ]
    if report.ability_plus_10_complexity_plus_300_risk == "low":
        phase_lines.append("**proceed_to_ecc_intake** — Risk is low. v4 may proceed to ECC intake phase.")
        phase_lines.append("simplify_first: NO (no blocking issues)")
        phase_lines.append("stop: NO")
    elif report.ability_plus_10_complexity_plus_300_risk == "medium":
        phase_lines.append("**proceed_to_ecc_intake** — Risk is medium. Proceed with caution; consider simplification before intake.")
        phase_lines.append("simplify_first: MAYBE (defer opportunities exist)")
        phase_lines.append("stop: NO")
    else:
        phase_lines.append("**simplify_first** — Risk is high. Address simplification opportunities before ECC intake.")
        phase_lines.append("proceed_to_ecc_intake: NO (blocked on simplification)")
        phase_lines.append("stop: YES (until simplification completes)")

    phase_path = out / "phase_13c_simplification_audit_report.md"
    with open(phase_path, "w", encoding="utf-8") as f:
        f.write("\n".join(phase_lines))

    return {
        "json": str(json_path),
        "md": str(md_path),
        "phase_report": str(phase_path),
    }


# ── CLI entry ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  SystemKernel v4.0 — Simplification Audit (Phase 13C)")
    print("=" * 60)
    print()

    report = build_v4_simplification_audit()

    print(f"  Modules analyzed: {report.modules_analyzed}")
    print(f"  Total LOC:        {report.total_loc}")
    print(f"  Public API:       {report.total_public_api}")
    print(f"  Exports:          {report.total_exports}")
    print(f"  Safe now:         {report.safe_now_count}")
    print(f"  Defer:            {report.defer_count}")
    print(f"  Do not touch:     {report.do_not_touch_count}")
    print(f"  Risk (A+10/C+300): {report.ability_plus_10_complexity_plus_300_risk.upper()}")
    print()

    # Write reports
    exports_dir = ROOT / "v3" / "exports"
    paths = write_simplification_audit(report, str(exports_dir))
    print("  Reports written:")
    for k, v in paths.items():
        print(f"    {k}: {v}")
    print()

    # Print top opportunities
    print("  Top Simplification Opportunities:")
    print()
    top = [o for o in report.opportunities if o.recommended_action != "keep" and o.recommended_action != "no_action"][:10]
    for i, o in enumerate(top, 1):
        print(f"  {i}. [{o.category}] {o.description[:80]}")
        print(f"     risk={o.behavior_risk}, action={o.recommended_action}, reduction={o.expected_complexity_reduction}")
        print()

    if not top:
        print("  (No actionable opportunities found.)")
        print()

    print("  Recommendation:", end=" ")
    if report.ability_plus_10_complexity_plus_300_risk == "low":
        print("proceed_to_ecc_intake")
    elif report.ability_plus_10_complexity_plus_300_risk == "medium":
        print("proceed_to_ecc_intake (caution)")
    else:
        print("simplify_first")

    print()
    print("  Audit complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
