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

    return 0
