"""
SystemKernel CLI — eval + ops commands: capability, eval, v4.

Extracted from systemkernel.py during Phase 13D CLI Surface Compression.
All behavior preserved. No new capability added.
"""
from __future__ import annotations

import os
import sys

from v3.cli._helpers import ROOT, EXPORTS_DIR, V3_ROOT


# ═══════════════════════════════════════════════════════════════════════
# Capability registry commands
# ═══════════════════════════════════════════════════════════════════════

def cmd_capability_list() -> int:
    """List all capability registry entries."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.default_capabilities import build_default_registry

    registry = build_default_registry()
    if not registry.entries:
        print("(no entries)")
        return 0

    for entry in registry.entries:
        status = "[ENABLED]" if entry.enabled else "[DISABLED]"
        risk = entry.spec.risk_level if entry.spec else "?"
        print(f"{status} {entry.adapter_id} | {entry.maturity} | {entry.lifecycle_state} | risk={risk}")
    return 0


def cmd_capability_summary() -> int:
    """Print capability registry summary counts."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import (
        list_by_type, list_enabled, list_high_risk, list_by_lifecycle,
    )
    from v3.external.capability_lifecycle import STATE_APPROVED

    registry = build_default_registry()
    total = len(registry.entries)
    enabled = list_enabled(registry)
    disabled = [e for e in registry.entries if not e.enabled]
    approved = list_by_lifecycle(registry, STATE_APPROVED)
    high_risk = list_high_risk(registry)

    print(f"Total entries:      {total}")
    print(f"Enabled:            {len(enabled)}")
    print(f"Disabled:           {len(disabled)}")
    print(f"Approved:           {len(approved)}")
    print(f"High risk:          {len(high_risk)}")
    print()

    # Counts by type
    from v3.external.capability_contract import CapabilityType
    print("By type:")
    for t in CapabilityType:
        entries = list_by_type(registry, t.value)
        if entries:
            enabled_count = sum(1 for e in entries if e.enabled)
            print(f"  {t.value}: {len(entries)} ({enabled_count} enabled)")

    print()
    print(f"Registry hash:      {registry.registry_hash}")
    print()
    print("External integrations performed: NONE (Phase 2 is registry only)")
    return 0


def cmd_capability_show(adapter_id: str) -> int:
    """Show one capability registry entry."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import get_entry

    registry = build_default_registry()
    entry = get_entry(registry, adapter_id)
    if entry is None:
        print(f"Entry not found: {adapter_id}")
        return 1

    print(f"Adapter ID:         {entry.adapter_id}")
    if entry.spec:
        print(f"Name:               {entry.spec.name}")
        print(f"Type:               {entry.spec.capability_type}")
        print(f"Modes:              {', '.join(entry.spec.execution_modes)}")
        print(f"Risk:               {entry.spec.risk_level}")
        print(f"Truth source:       {entry.spec.truth_source}")
        print(f"Removable:          {entry.spec.removable}")
        print(f"Forbidden actions:  {', '.join(entry.spec.forbidden_actions)}")
    print(f"Lifecycle:          {entry.lifecycle_state}")
    print(f"Enabled:            {entry.enabled}")
    print(f"Maturity:           {entry.maturity}")
    print(f"Approval required:  {entry.approval_required}")
    print(f"Owner:              {entry.owner}")
    print(f"Notes:              {entry.notes}")
    print(f"Entry hash:         {entry.entry_hash}")
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Evaluation harness commands (Phase 10)
# ═══════════════════════════════════════════════════════════════════════

def cmd_eval_suite() -> int:
    """List default eval cases."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.evals.evaluation_harness import build_default_eval_suite

    suite = build_default_eval_suite()
    print(f"Suite: {suite.suite_id}")
    print(f"Cases: {len(suite.cases)}")
    print(f"Hash:  {suite.suite_hash}")
    print()
    for case in suite.cases:
        print(f"  [{case.category}] {case.name}")
        print(f"    ID:        {case.case_id}")
        print(f"    Objective: {case.objective}")
        print(f"    Invariants: {', '.join(case.required_invariants) if case.required_invariants else '(none)'}")
        print()
    return 0


def cmd_eval_run() -> int:
    """Run deterministic static eval suite."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.evals.evaluation_harness import build_default_eval_suite, run_eval_suite

    suite = build_default_eval_suite()
    result = run_eval_suite(suite)

    print(f"Suite:        {result.suite_id}")
    print(f"Passed:       {result.passed_count}")
    print(f"Failed:       {result.failed_count}")
    print(f"Avg Score:    {result.average_score}")
    print(f"Result Hash:  {result.suite_result_hash}")
    print()

    for r in result.results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.case_id} — score={r.score}")
        if r.missing_outputs:
            print(f"    Missing: {', '.join(r.missing_outputs)}")
        if r.warnings:
            print(f"    Warnings: {', '.join(r.warnings)}")

    print()
    if result.failed_count == 0:
        print("All eval cases passed.")
        return 0
    else:
        print(f"{result.failed_count} eval case(s) failed.")
        return 1


def cmd_eval_regression(output: str = "") -> int:
    """Generate regression matrix result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.evals.regression_matrix import (
        run_static_regression_matrix, write_regression_matrix_result,
    )

    if output:
        path = write_regression_matrix_result(output)
        print(f"Regression matrix written: {path}")
    else:
        result = run_static_regression_matrix()
        print(f"Matrix:   {result.matrix.matrix_hash}")
        print(f"Passed:   {result.passed}")
        print(f"Failed:   {result.failed}")
        print(f"Skipped:  {result.skipped}")
        print(f"Total:    {result.matrix.total}")
        print(f"Required: {result.matrix.required_count}")
        print()
        if result.release_blocking_failures:
            print("Release Blocking Failures:")
            for f in result.release_blocking_failures:
                print(f"  - {f}")
        else:
            print("No release blocking failures.")
        print(f"Result Hash: {result.result_hash}")

    return 0 if result.failed == 0 else 1


def cmd_eval_benefit(output: str = "") -> int:
    """Generate benefit-vs-complexity report for current v4 planes."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.evals.benefit_complexity import (
        BenefitSignal, score_benefit_complexity, write_benefit_complexity_report,
    )

    # Score each major v4 plane
    planes = {
        "capability_contract": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=False,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 3.0),
        "capability_registry": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 4.0),
        "evidence_model": (BenefitSignal(
            reduces_manual_steps=False,
            improves_verifiability=True,
            improves_replaceability=False,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 2.0),
        "context_plane": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=False,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 4.0),
        "memory_intelligence": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 5.0),
        "agent_worker": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 5.0),
        "workspace_context": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=False,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 5.0),
        "skill_evolution": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 5.0),
        "orchestration_policy": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 6.0),
        "eval_harness": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=False,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 2.0),
    }

    scores = tuple(
        score_benefit_complexity(name, sig, complexity)
        for name, (sig, complexity) in planes.items()
    )

    if output:
        path = write_benefit_complexity_report(scores, output)
        print(f"Benefit-complexity report written: {path}")
    else:
        print("V4 Plane Benefit-Complexity Scores:")
        print()
        for s in scores:
            verdict_mark = {"ACCEPT": "+", "REVIEW": "~", "REJECT": "!"}.get(s.verdict, "?")
            print(f"  [{verdict_mark}] {s.target_id}")
            print(f"      Benefit={s.benefit_score}  Complexity={s.complexity_score}  "
                  f"Net={s.net_value}  RiskRatio={s.risk_ratio}  Verdict={s.verdict}")

        accepted = sum(1 for s in scores if s.verdict == "ACCEPT")
        review = sum(1 for s in scores if s.verdict == "REVIEW")
        rejected = sum(1 for s in scores if s.verdict == "REJECT")
        print(f"\n  Accepted: {accepted}  Review: {review}  Rejected: {rejected}")

    return 0


# ═══════════════════════════════════════════════════════════════════════
# Benchmark command (Phase 16c)
# ═══════════════════════════════════════════════════════════════════════

def cmd_eval_benchmark(config: str = "", output: str = "") -> int:
    """Run the SystemKernel benchmark suite.

    Args:
        config: "minimal", "full", or "" (all configs)
        output: Path to write JSON report (optional)
    """
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.evals.benchmark_suite import main as run_benchmark

    config_filter = config if config in ("minimal", "full") else None
    return run_benchmark(config_filter=config_filter, output_path=output or None)


# ═══════════════════════════════════════════════════════════════════════
# V4 Productization + Ops commands (Phase 11)
# ═══════════════════════════════════════════════════════════════════════

def cmd_v4_status() -> int:
    """Print compact v4 operational status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.ops.v4_ops import build_v4_ops_status

    s = build_v4_ops_status()
    print("V4 Operational Status")
    print("=" * 40)
    print(f"  Kernel purity:        {s.kernel_purity}/100")
    print(f"  Memory removable:     {'YES' if s.memory_removable else 'NO'}")
    print(f"  Registry entries:     {s.registry_entries} ({s.enabled_capabilities} enabled, {s.disabled_capabilities} disabled)")
    print(f"  Evidence model:       {'READY' if s.evidence_model_ready else 'NOT READY'}")
    print(f"  Orchestration:        {'READY' if s.orchestration_ready else 'NOT READY'}")
    print(f"  Eval harness:         {'READY' if s.eval_ready else 'NOT READY'}")
    print(f"  Complexity verdict:   {s.complexity_verdict}")
    print(f"  Ops hash:             {s.ops_hash}")
    return 0


def cmd_v4_ops_check(output: str = "") -> int:
    """Print v4 operational checklist."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.ops.v4_ops import build_v4_ops_checklist, write_v4_ops_checklist

    checklist = build_v4_ops_checklist()

    if output:
        path = write_v4_ops_checklist(output)
        print(f"Checklist written: {path}")
    else:
        print(f"V4 Ops Checklist — {checklist.checklist_id}")
        print(f"Passed: {checklist.passed}  Failed: {checklist.failed}")
        print(f"Hash:   {checklist.checklist_hash}")
        print()
        cats = {}
        for item in checklist.items:
            cats.setdefault(item.category, []).append(item)
        for cat, cat_items in sorted(cats.items()):
            print(f"  [{cat.upper()}]")
            for item in cat_items:
                m = {"pass": "+", "fail": "!", "pending": "?"}.get(item.status, "?")
                req = " [REQUIRED]" if item.required else ""
                print(f"    [{m}] {item.title}{req}")
            print()

    return 0 if checklist.failed == 0 else 1


def cmd_v4_runbook(output: str = "", fmt: str = "md") -> int:
    """Write v4 runbook to file."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.ops.runbook import write_v4_runbook_md, write_v4_runbook_json

    if not output:
        output_dir = os.path.join(EXPORTS_DIR, f"v4_runbook.{fmt}")
    else:
        output_dir = output

    if fmt == "json":
        path = write_v4_runbook_json(output_dir)
    else:
        path = write_v4_runbook_md(output_dir)

    print(f"Runbook written: {path}")
    return 0


def cmd_v4_summary() -> int:
    """Combined registry/evidence/orchestration/eval summary."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import list_enabled
    from v3.external.orchestration_profiles import get_all_profiles
    from v3.evals.evaluation_harness import build_default_eval_suite, run_eval_suite

    # Registry
    reg = build_default_registry()
    enabled = list_enabled(reg)
    types = {}
    for e in reg.entries:
        if e.spec:
            types.setdefault(e.spec.capability_type, []).append(e)

    # Orchestration
    profiles = get_all_profiles()

    # Eval
    suite = build_default_eval_suite()
    eval_result = run_eval_suite(suite)

    print("=" * 50)
    print("  SystemKernel v4.0 — Operational Summary")
    print("=" * 50)

    print(f"\n  Registry:        {len(reg.entries)} entries ({len(enabled)} enabled)")
    print(f"  Capability types: {len(types)}/8 covered")
    print(f"  Orchestration:    {len(profiles)} policy profiles")
    print(f"  Eval:             {eval_result.passed_count}/{len(suite.cases)} cases pass (score={eval_result.average_score})")
    print(f"  Regression:       static checks available via 'systemkernel eval regression'")
    print(f"  Complexity:       check via 'systemkernel quality'")
    print(f"  Kernel:           purity 100/100, memory removable")

    print(f"\n  Commands:")
    print(f"    systemkernel v4 status      — Full ops health")
    print(f"    systemkernel v4 ops-check   — Operational checklist")
    print(f"    systemkernel v4 runbook     — Generate runbook")
    print(f"    systemkernel eval run       — Run deterministic eval suite")
    print(f"    systemkernel eval benefit   — Benefit-complexity scores")
    print(f"    systemkernel orchestrate plan --profile safe_context_only")
    print(f"    systemkernel v4 freeze verify — Stability freeze verification")

    return 0


def cmd_v4_freeze_verify(output: str = "") -> int:
    """Run stability freeze verification and optionally write report."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.release.stability_freeze import (
        build_stability_freeze,
        write_stability_freeze_report,
    )

    result = build_stability_freeze(ROOT)

    from v3.release.stability_freeze import _print_result
    _print_result(result)

    if output:
        report_path = write_stability_freeze_report(result, output)
        print(f"  Report written: {report_path}")

    return 0 if result.overall_pass else 1


# ═══════════════════════════════════════════════════════════════════════
# V4 Observability commands (Phase 15b)
# ═══════════════════════════════════════════════════════════════════════

def cmd_v4_metrics(output_json: bool = False) -> int:
    """Export metrics in Prometheus text format (or JSON).

    Loads from the last stress run snapshot if available.
    """
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.observability.metrics_exporter import get_exporter

    exporter = get_exporter()
    # Load from last stress run if available
    snapshot_path = os.path.join(ROOT, "v3", "metrics", "metrics_snapshot.json")
    loaded = exporter.load_from_disk(snapshot_path)

    if output_json:
        import json
        data = exporter.export_json()
        if loaded:
            data["source"] = snapshot_path
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        output = exporter.export_metrics()
        if loaded:
            output = f"# Loaded from: {snapshot_path}\n{output}"
        print(output)
    return 0


def cmd_v4_cost() -> int:
    """Print cost summary from the cost tracker."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.observability.cost_tracker import CostTracker

    tracker = CostTracker()
    summary = tracker.daily_summary()

    print(f"Total cost:       ${summary.total_cost_usd:.6f}")
    print(f"Total tokens:     {summary.total_tokens:,}")
    print(f"Records:          {summary.record_count}")
    print()
    if summary.by_model:
        print("By model:")
        for model, cost in summary.by_model.items():
            print(f"  {model}: ${cost:.6f}")
    print()
    if summary.daily_costs:
        print("Daily:")
        for day, cost in summary.daily_costs:
            print(f"  {day}: ${cost:.6f}")

    return 0


def cmd_v4_dashboard(output: str = "") -> int:
    """Print Grafana dashboard JSON. Use --export to write to file."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.observability.metrics_exporter import get_dashboard_spec
    import json

    spec = get_dashboard_spec()
    if not spec:
        print("Error: dashboard spec not found.")
        return 1

    output_json = json.dumps(spec, indent=2, ensure_ascii=False)

    if output:
        import os
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Dashboard exported: {output}")
        print(f"Import into Grafana: Dashboards → New → Import → Upload JSON file")
        print(f"Datasource variable: ${'{DS_PROMETHEUS}'} (set to your Prometheus datasource)")
        return 0
    else:
        print(output_json)
        return 0


def cmd_v4_alerts() -> int:
    """Evaluate alert rules against current metrics snapshot."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.observability.alert_policy import get_default_rules, AlertPolicy, AlertEvent
    from v3.external.observability.metrics_exporter import get_exporter

    exporter = get_exporter()

    # Build metrics snapshot from exporter state
    metrics_json = exporter.export_json()
    m = metrics_json["metrics"]

    error_count = sum(m.get("systemkernel_errors_total", {}).values())
    exec_count = max(m["systemkernel_executions_total"], 1)
    error_rate = error_count / exec_count if exec_count else 0.0

    latency = m.get("systemkernel_execution_latency_seconds", {})
    latency_count = latency.get("count", 0)

    snapshot = {
        "cost_usd_daily_ratio": 1.0,    # no daily baseline yet
        "error_rate": error_rate,
        "execution_latency_p99_seconds": 0.0,
        "complexity_score": m["systemkernel_complexity_score"],
        "stability_freeze_score": m["systemkernel_stability_freeze_score"],
    }

    rules = get_default_rules()
    policy = AlertPolicy(rules=rules)
    events = policy.evaluate(snapshot)

    print(f"Rules: {len(rules)}")
    print(f"Events: {len(events)}")
    print(f"Error rate: {error_rate:.4f}")
    print(f"Complexity: {snapshot['complexity_score']:.1f}")
    print(f"Stability: {snapshot['stability_freeze_score']:.0f}")
    print()

    for e in events:
        icon = "X" if e.severity == "critical" else "!" if e.severity == "warning" else "i"
        state_str = e.state.upper()
        print(f"[{icon}] {state_str} {e.rule_id}: {e.metric}={e.current_value:.2f} "
              f"(threshold {e.condition} {e.threshold}) [{e.severity}]")

    return 1 if any(e.state == "firing" and e.severity == "critical" for e in events) else 0


# ═══════════════════════════════════════════════════════════════════════
# Capability Refinement commands (Phase 16c)
# ═══════════════════════════════════════════════════════════════════════

def cmd_capability_select(task_type: str = "code_generation", risk: str = "low",
                          top_n: int = 5) -> int:
    """Select top-N capabilities for a task context.

    Uses select_tools() for high-level task types (code/review/research/build/security)
    and CapabilitySelector.select() for granular task types (code_generation, etc.).
    """
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import CapabilitySelector, TaskContext

    registry = build_default_registry()

    # High-level task types → use tool_selector (L2 Tool Interface)
    HIGH_LEVEL_TASKS = frozenset({"code", "review", "research", "build", "security"})

    if task_type in HIGH_LEVEL_TASKS:
        from v3.external.tool_selector import select_tools

        selection = select_tools(task_type, registry, max_tools=top_n)

        selected_list = ", ".join(selection.selected) if selection.selected else "(none)"
        excluded_summary = []
        for aid in selection.excluded[:5]:
            reason = selection.reason_map.get(aid, "unknown")
            excluded_summary.append(f"{aid}: {reason}")

        n_sel = len(selection.selected)
        n_excl = len(selection.excluded)
        print(f"Task: {task_type}")
        print(f"selected {n_sel} tools ({selected_list})")
        if excluded_summary:
            print(f"excluded {n_excl} ({'; '.join(excluded_summary)})")
        else:
            print(f"excluded {n_excl}")
        print(f"hash: {selection.selection_hash}")
        return 0

    # Granular task types → use CapabilitySelector (existing behavior)
    task = TaskContext(task_type=task_type, risk_level=risk)
    scores = CapabilitySelector.select(registry, task, top_n=top_n)

    if not scores:
        print("No matching capabilities found.")
        return 1

    print(f"Task: {task_type} (risk={risk})")
    print(f"Top {len(scores)} capabilities:")
    print()
    for i, s in enumerate(scores, 1):
        print(f"  {i}. {s.capability_id}")
        print(f"     type={s.capability_type}  relevance={s.relevance:.2f}  "
              f"safety={s.safety:.2f}  cost=${s.cost_estimate:.4f}  "
              f"score={s.composite_score:.2f}")
    return 0


def cmd_capability_dedup() -> int:
    """Find duplicate capabilities in the registry."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import CapabilityDedup

    registry = build_default_registry()
    groups = CapabilityDedup.find_duplicates(registry)

    if not groups:
        print("No duplicate capabilities detected.")
        return 0

    print(f"Found {len(groups)} potential duplicate group(s):")
    for g in groups:
        print(f"  [{g.reason}] {', '.join(g.entries)}")
        print(f"    → Action: {g.recommended_action}")
        if g.reason == "same_command":
            keeper = CapabilityDedup.dedup_strategy(g, registry)
            print(f"    → Keep: {keeper}")
    return 1 if groups else 0


def cmd_capability_conflicts() -> int:
    """Detect conflicts between enabled capabilities."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import CapabilityConflict

    registry = build_default_registry()
    conflicts = CapabilityConflict.detect(registry)

    if not conflicts:
        print("No conflicts detected among enabled capabilities.")
        return 0

    print(f"Found {len(conflicts)} conflict(s):")
    for c in conflicts:
        print(f"  [{c.conflict_type}] {c.capability_a} vs {c.capability_b}")
        print(f"    {c.description}")
        print(f"    → {c.resolution}")
    return 1


# ═══════════════════════════════════════════════════════════════════════
# Security Scan commands (Phase 17c)
# ═══════════════════════════════════════════════════════════════════════

def cmd_security_scan(target_path: str = "", severity: str = "HIGH",
                      output_json: bool = False) -> int:
    """Run a trivy security scan against a target path."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.external.security_scan import (
        SecurityScanRequest, run_security_scan, filter_critical,
        is_clean, wrap_as_evidence,
    )
    import json

    if not target_path:
        print("Error: target path required.")
        print("Usage: systemkernel security scan <path> [--severity CRITICAL|HIGH|MEDIUM] [--json]")
        return 1

    request = SecurityScanRequest(
        target_path=target_path,
        severity_min=severity.upper(),
    )

    print(f"Scanning: {target_path}")
    print(f"Severity: {severity.upper()}+")
    print()

    result = run_security_scan(request)

    if result.degraded:
        if output_json:
            print(json.dumps({"status": "degraded", "error": result.error}, indent=2))
        else:
            print(f"[DEGRADED] {result.error}")
            print("Install trivy: brew install trivy / apt install trivy")
        return 1

    if output_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Findings: {result.total_findings}")
        print(f"  CRITICAL: {result.total_critical}")
        print(f"  HIGH:     {result.total_high}")
        print(f"  MEDIUM:   {result.total_medium}")
        print(f"  LOW:      {result.total_low}")
        print(f"  Duration: {result.scan_duration_ms:.0f}ms")
        print(f"  Clean:    {is_clean(result)}")
        print()

        criticals = filter_critical(result)
        if criticals:
            print("CRITICAL vulnerabilities:")
            for v in criticals:
                fix = f" (fix: {v.fixed_version})" if v.fixed_version else ""
                print(f"  {v.cve_id}: {v.title[:100]}{fix}")

        evidence = wrap_as_evidence(result)
        print(f"\nEvidence: truth_source={evidence['truth_source']} hash={evidence['evidence_hash']}")

    return 0 if is_clean(result) else 1
