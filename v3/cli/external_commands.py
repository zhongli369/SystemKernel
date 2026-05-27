"""
SystemKernel CLI — external commands: intake, context-pack, usage.

Extracted from systemkernel.py during Phase 13D CLI Surface Compression.
All behavior preserved. No new capability added.
"""
from __future__ import annotations

import json
import os
import sys

from v3.cli._helpers import ROOT, EXPORTS_DIR


# ═══════════════════════════════════════════════════════════════════════
# Command: intake profile
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_profile(name: str) -> int:
    """Show intake assessment for a specific known repo profile."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.repo_profiles import get_profile
    from v3.intake.repo_intake import decide_repo_intake, compute_report_hash
    from v3.intake.rules import apply_rules, classify_repo_type

    profile = get_profile(name)
    if profile is None:
        print(f"Unknown profile: {name}")
        print(f"Use 'intake list' to see available profiles.")
        return 1

    inp = profile.to_input()
    signals = profile.analyze()
    decision = decide_repo_intake(inp, signals)
    rule_decision, rule_id = apply_rules(inp, signals)
    repo_type = classify_repo_type(signals, profile.name)
    report_hash = compute_report_hash(inp, signals, decision)

    print("=" * 60)
    print(f"  Repo Intake — {profile.name}")
    print("=" * 60)

    print(f"\n  URL:                  {profile.url}")
    print(f"  Category:             {profile.category_hint or repo_type}")
    print(f"  Repo Type:            {repo_type}")
    print(f"  Intended Use:         {profile.intended_use}")

    print(f"\n  Signals:")
    print(f"    README:             {'YES' if signals.has_readme else 'NO'}")
    print(f"    LICENSE:            {'YES' if signals.has_license else 'NO'}")
    print(f"    Languages:          {', '.join(signals.language_hints) or 'none'}")
    print(f"    CLI:                {'YES' if signals.has_cli else 'NO'}")
    print(f"    MCP:                {'YES' if signals.has_mcp else 'NO'}")
    print(f"    Tests:              {'YES' if signals.has_tests else 'NO'}")
    print(f"    Docs:               {'YES' if signals.has_docs else 'NO'}")

    print(f"\n  Dependency Risks:")
    print(f"    Banned:             {signals.banned_dependency_hits}")
    print(f"    Heavy:              {signals.heavy_dependency_hits}")
    print(f"    LLM:                {signals.llm_dependency_hits}")
    print(f"    Memory:             {signals.memory_dependency_hits}")
    print(f"    Framework:          {signals.framework_dependency_hits}")

    print(f"\n  Decision:")
    print(f"    Verdict:            {decision.decision}")
    print(f"    Priority:           {decision.priority}")
    print(f"    CC Value:           {decision.claude_code_value_score}/10")
    print(f"    SK Value:           {decision.systemkernel_value_score}/10")
    print(f"    Complexity Risk:    {decision.complexity_risk_score}/10")
    print(f"    Purity Risk:        {decision.purity_risk_score}/10")
    print(f"    Maintenance Risk:   {decision.maintenance_risk_score}/10")
    print(f"    Final Score:        {decision.final_score}")
    print(f"    Rule Match:         {rule_id} → {rule_decision}")
    print(f"    Report Hash:        {report_hash}")

    if decision.reasons:
        print(f"\n  Reasons:")
        for r in decision.reasons:
            print(f"    - {r}")

    if profile.known_risks:
        print(f"\n  Known Risks:")
        for r in profile.known_risks:
            print(f"    - {r}")

    print(f"\n  Target:              {decision.recommended_target_dir}")
    print(f"  Allowed:             {', '.join(decision.allowed_actions)}")
    print(f"  Forbidden:           {', '.join(decision.forbidden_actions)}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake list
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_list() -> int:
    """List all known repo profiles."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.repo_profiles import get_all_profiles

    profiles = get_all_profiles()

    print("=" * 60)
    print("  Repo Intake — Known Profiles")
    print("=" * 60)

    print(f"\n  {'Name':<35} {'Expected':<25} {'Category'}")
    print(f"  {'-'*35} {'-'*25} {'-'*20}")

    for p in profiles:
        print(f"  {p.name:<35} {p.expected_decision:<25} {p.category_hint or 'unknown':<20}")

    print(f"\n  Total: {len(profiles)} profiles")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake summarize
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_summarize() -> int:
    """Summarize all repo profiles with full intake decisions."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.repo_profiles import get_all_profiles
    from v3.intake.repo_intake import decide_repo_intake, compute_report_hash
    from v3.intake.rules import apply_rules, classify_repo_type

    profiles = get_all_profiles()

    print("=" * 60)
    print("  Repo Intake — Summary")
    print("=" * 60)

    # Count decisions
    counts = {"DIRECT_CLONE": 0, "EXTERNAL_EXTENSION": 0,
              "ARCHITECTURE_REFERENCE": 0, "REJECT": 0}

    results = []
    for p in profiles:
        inp = p.to_input()
        signals = p.analyze()
        decision = decide_repo_intake(inp, signals)
        rule_decision, rule_id = apply_rules(inp, signals)
        repo_type = classify_repo_type(signals, p.name)
        report_hash = compute_report_hash(inp, signals, decision)

        counts[decision.decision] = counts.get(decision.decision, 0) + 1

        results.append({
            "name": p.name,
            "decision": decision.decision,
            "priority": decision.priority,
            "cc_value": decision.claude_code_value_score,
            "sk_value": decision.systemkernel_value_score,
            "final_score": decision.final_score,
            "rule_id": rule_id,
            "rule_decision": rule_decision,
            "repo_type": repo_type,
            "report_hash": report_hash,
            "expected": p.expected_decision,
            "match": "MATCH" if decision.decision == p.expected_decision else "MISMATCH",
        })

    # Print table
    print(f"\n  {'Name':<35} {'Decision':<25} {'Score':<8} {'Expected':<25} {'Match'}")
    print(f"  {'-'*35} {'-'*25} {'-'*8} {'-'*25} {'-'*8}")

    for r in results:
        flag = " !" if r["match"] == "MISMATCH" else ""
        print(f"  {r['name']:<35} {r['decision']:<25} {r['final_score']:<8.1f} "
              f"{r['expected']:<25} {r['match']}{flag}")

    # Summary counts
    print(f"\n  Decision Distribution:")
    for dec in ("DIRECT_CLONE", "EXTERNAL_EXTENSION", "ARCHITECTURE_REFERENCE", "REJECT"):
        c = counts.get(dec, 0)
        bar = "#" * c
        print(f"    {dec:<25} {c:>2}  {bar}")

    # Direct clone candidates
    clones = [r for r in results if r["decision"] == "DIRECT_CLONE"]
    if clones:
        print(f"\n  DIRECT_CLONE Candidates ({len(clones)}):")
        for r in clones:
            print(f"    - {r['name']} (score={r['final_score']:.1f}, priority={r['priority']})")

    # Mismatches
    mismatches = [r for r in results if r["match"] == "MISMATCH"]
    if mismatches:
        print(f"\n  MISMATCHES ({len(mismatches)}):")
        for r in mismatches:
            print(f"    - {r['name']}: expected {r['expected']}, got {r['decision']}")

    print(f"\n  Total: {len(profiles)} profiles")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake registry
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_registry(output_path: str = None) -> int:
    """Generate the external tool registry from all profiles."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.tool_registry import build_registry_from_profiles, write_registry

    print("=" * 60)
    print("  SystemKernel v3.0 — External Tool Registry")
    print("=" * 60)
    print()
    print("  PLAN ONLY — no network access, no cloning performed.")
    print()

    registry = build_registry_from_profiles()

    if output_path is None:
        output_path = os.path.join(EXPORTS_DIR, "external_tool_registry.json")

    write_registry(registry, output_path)

    print(f"  Entries:              {len(registry.entries)}")
    print(f"  Direct clone:         {registry.direct_clone_count}")
    print(f"  External extension:   {registry.external_extension_count}")
    print(f"  Architecture ref:     {registry.architecture_reference_count}")
    print(f"  Rejected:             {registry.reject_count}")
    print(f"  Registry hash:        {registry.registry_hash}")
    print()

    # Breakdown by use mode
    print(f"  Use Mode Breakdown:")
    for entry in registry.entries:
        print(f"    [{entry.priority}] {entry.name:<30} → {entry.use_mode}")

    print(f"\n  Registry written:     {output_path}")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake clone-plan
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_clone_plan(output_dir: str = None) -> int:
    """Generate the GitHub clone plan (JSON + Markdown)."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.tool_registry import build_registry_from_profiles
    from v3.intake.clone_plan import create_clone_plan, filter_clone_now, summarize_plan
    from v3.intake.clone_plan import write_clone_plan_markdown

    print("=" * 60)
    print("  SystemKernel v3.0 — GitHub Clone Plan")
    print("=" * 60)
    print()
    print("  PLAN ONLY — no actual cloning is performed.")
    print("  All items require manual review before execution.")
    print()

    registry = build_registry_from_profiles()
    plan = create_clone_plan(registry, root_dir="F:\\Claude\\Github")

    if output_dir is None:
        output_dir = EXPORTS_DIR

    json_path = os.path.join(output_dir, "github_clone_plan.json")
    md_path = os.path.join(output_dir, "github_clone_plan.md")

    # Write JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)

    # Write Markdown
    write_clone_plan_markdown(plan, md_path)

    clone_now = filter_clone_now(plan)
    inspect = [i for i in plan.items if i.post_clone_action == "inspect_only"]
    ext_eval = [i for i in plan.items if i.post_clone_action == "evaluate_external_service"]
    ref_only = [i for i in plan.items if i.post_clone_action == "none"]

    print(f"  Clone Now ({len(clone_now)}):")
    for item in clone_now:
        print(f"    [{item.priority}] {item.name} → {item.target_path}")
        print(f"          Post-clone: {item.post_clone_action}")

    print(f"\n  Inspect Only ({len(inspect)}):")
    for item in inspect:
        print(f"    [{item.priority}] {item.name}")

    print(f"\n  External Evaluation ({len(ext_eval)}):")
    for item in ext_eval:
        print(f"    [{item.priority}] {item.name}")

    print(f"\n  Reference Only ({len(ref_only)}):")
    for item in ref_only:
        print(f"    [{item.priority}] {item.name}")

    print(f"\n  Plan hash:            {plan.plan_hash}")
    print(f"  JSON written:         {json_path}")
    print(f"  Markdown written:     {md_path}")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake clone-list
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_clone_list() -> int:
    """Print recommended clone order. Does NOT clone."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.tool_registry import build_registry_from_profiles, recommend_clone_order

    print("=" * 60)
    print("  SystemKernel v3.0 — Recommended Clone Order")
    print("=" * 60)
    print()
    print("  PLAN ONLY — no actual cloning is performed.")
    print("  Run these commands manually when ready:")
    print()

    registry = build_registry_from_profiles()
    order = recommend_clone_order(registry)

    for i, name in enumerate(order, 1):
        entry = None
        for e in registry.entries:
            if e.name == name:
                entry = e
                break
        if entry:
            print(f"  {i}. git clone {entry.repo_url} {entry.target_dir}")
            print(f"     Use mode: {entry.use_mode}")
            print(f"     Priority: {entry.priority}")
            print()

    print(f"  Total clone-now items: {len(order)}")
    print()
    print("  SAFETY REMINDER:")
    print("    - These are EXTERNAL tools, not kernel modules.")
    print("    - Clone into F:/Claude/Github/ — outside kernel boundary.")
    print("    - Do NOT integrate into SystemKernel without separate audit.")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: context-pack plan
# ═══════════════════════════════════════════════════════════════════════

def cmd_context_pack_plan(target: str, output: str, style: str = "markdown") -> int:
    """Plan a context pack command. Does NOT execute."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

    config = ContextPackConfig(
        target_path=target,
        output_path=output,
        style=style,
    )
    result = ContextPackAdapter.plan(config)

    print("=" * 60)
    print("  SystemKernel v3.0 — Context Pack Plan")
    print("=" * 60)
    print()
    print(f"  Status:               {result.status}")
    print(f"  Target:               {result.target_path}")
    print(f"  Output:               {result.output_path}")
    print(f"  Estimated size:       {result.size_bytes:,} bytes")
    print(f"  Estimated tokens:     {result.token_estimate:,}")
    print(f"  Estimated files:      {len(result.included_files)}")
    print(f"  Truth source:         {result.truth_source}")

    if result.command:
        print(f"\n  Planned command:")
        print(f"    {result.command}")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")

    if result.included_files:
        print(f"\n  Files to include ({len(result.included_files)}):")
        for f in result.included_files[:20]:
            print(f"    - {f}")
        if len(result.included_files) > 20:
            print(f"    ... and {len(result.included_files) - 20} more")

    print()
    if result.status == "blocked":
        return 1
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: context-pack inspect
# ═══════════════════════════════════════════════════════════════════════

def cmd_context_pack_inspect(path: str) -> int:
    """Inspect an existing context pack output file. Read-only."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_pack import ContextPackAdapter

    result = ContextPackAdapter.inspect_output(path)
    verified = ContextPackAdapter.verify_pack(result)

    print("=" * 60)
    print("  SystemKernel v3.0 — Context Pack Inspect")
    print("=" * 60)
    print()
    print(f"  Status:               {result.status}")
    print(f"  Path:                 {result.output_path}")
    print(f"  Size:                 {result.size_bytes:,} bytes")
    print(f"  Lines:                {result.line_count:,}")
    print(f"  Token estimate:       {result.token_estimate:,}")
    print(f"  Pack hash:            {result.pack_hash}")
    print(f"  Truth source:         {result.truth_source}")
    print(f"  Verified:             {verified}")
    print(f"  Included files:       {len(result.included_files)}")

    if result.included_files:
        print()
        for f in result.included_files[:30]:
            print(f"    - {f}")
        if len(result.included_files) > 30:
            print(f"    ... and {len(result.included_files) - 30} more")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")

    print()
    return 0 if result.status == "generated" else 1


# ═══════════════════════════════════════════════════════════════════════
# Command: context-pack generate
# ═══════════════════════════════════════════════════════════════════════

def cmd_context_pack_generate(target: str, output: str, style: str = "markdown",
                               allow_execute: bool = False) -> int:
    """Generate a context pack. Requires --allow-execute flag."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

    if not allow_execute:
        print("ERROR: --allow-execute flag is required to generate a context pack.")
        print()
        print("This flag confirms you understand:")
        print("  1. An external tool (npx repomix) will be executed")
        print("  2. Network access may be required on first run")
        print("  3. The generated pack is NOT a truth source")
        print("  4. The generated pack will be written to disk")
        print()
        print("Run with --allow-execute to proceed.")
        return 1

    config = ContextPackConfig(
        target_path=target,
        output_path=output,
        style=style,
    )
    result = ContextPackAdapter.generate(config, allow_execute=True)

    print("=" * 60)
    print("  SystemKernel v3.0 — Context Pack Generate")
    print("=" * 60)
    print()
    print(f"  Status:               {result.status}")
    print(f"  Target:               {result.target_path}")
    print(f"  Output:               {result.output_path}")

    if result.status == "generated":
        print(f"  Size:                 {result.size_bytes:,} bytes")
        print(f"  Lines:                {result.line_count:,}")
        print(f"  Token estimate:       {result.token_estimate:,}")
        print(f"  Pack hash:            {result.pack_hash}")
        print(f"  Included files:       {len(result.included_files)}")
        print(f"  Truth source:         {result.truth_source}")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")

    print()
    return 0 if result.status == "generated" else 1


# ═══════════════════════════════════════════════════════════════════════
# Command: usage inspect
# ═══════════════════════════════════════════════════════════════════════

def cmd_usage_inspect(path: str) -> int:
    """Inspect ccusage JSON output and print summary."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.usage_report import UsageReportAdapter

    print("=" * 60)
    print("  SystemKernel v3.0 — Usage Report Inspect")
    print("=" * 60)

    if not os.path.exists(path):
        print(f"\n  ERROR: File not found: {path}")
        return 1

    try:
        summary = UsageReportAdapter.inspect(path)
    except Exception as e:
        print(f"\n  ERROR: Failed to parse usage data: {e}")
        return 1

    verified = UsageReportAdapter.verify_summary(summary)

    print(f"\n  Source tool:          {summary.source_tool}")
    print(f"  Records:              {summary.record_count}")
    print(f"  Date range:           {summary.date_start} → {summary.date_end}")
    print(f"  Total tokens:         {summary.total_tokens:,}")
    print(f"  Total cost:           ${summary.total_cost_usd:,.6f}")
    print(f"  Cache read ratio:     {summary.cache_read_ratio:.4f}")
    print(f"  Models:               {summary.model_count}")
    print(f"  Agents:               {summary.agent_count}")
    print(f"  Sensitive detected:   {summary.sensitive_text_detected}")
    print(f"  Report hash:          {summary.report_hash}")
    print(f"  Truth source:         {summary.truth_source}")
    print(f"  Verified:             {verified}")

    if summary.warnings:
        print(f"\n  Warnings ({len(summary.warnings)}):")
        for w in summary.warnings:
            print(f"    - {w}")

    print()
    return 0 if verified else 1


# ═══════════════════════════════════════════════════════════════════════
# Command: usage summarize
# ═══════════════════════════════════════════════════════════════════════

def cmd_usage_summarize(path: str, output: str) -> int:
    """Read ccusage JSON output and write normalized usage summary."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.usage_report import UsageReportAdapter

    print("=" * 60)
    print("  SystemKernel v3.0 — Usage Report Summarize")
    print("=" * 60)

    if not os.path.exists(path):
        print(f"\n  ERROR: File not found: {path}")
        return 1

    try:
        summary = UsageReportAdapter.inspect(path)
    except Exception as e:
        print(f"\n  ERROR: Failed to parse usage data: {e}")
        return 1

    UsageReportAdapter.write_summary(summary, output)

    print(f"\n  Input:                {path}")
    print(f"  Output:               {output}")
    print(f"  Records:              {summary.record_count}")
    print(f"  Total tokens:         {summary.total_tokens:,}")
    print(f"  Total cost:           ${summary.total_cost_usd:,.6f}")
    print(f"  Report hash:          {summary.report_hash}")
    print(f"  Truth source:         {summary.truth_source}")
    print(f"\n  Summary written.")
    print()
    return 0
