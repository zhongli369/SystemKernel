"""
SystemKernel v3.0 — Developer CLI.

One-command runtime for status, quality, memory, reports, and health checks.
All commands wrap existing facades. Zero new runtime capability.
Standard library only. Deterministic output.

Usage:
    python v3/cli/systemkernel.py status
    python v3/cli/systemkernel.py quality
    python v3/cli/systemkernel.py memory report
    python v3/cli/systemkernel.py reports list
    python v3/cli/systemkernel.py reports summary
    python v3/cli/systemkernel.py doctor
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from v3.cli.core_commands import (
    cmd_status,
    cmd_quality,
    cmd_memory_report,
    cmd_reports_list,
    cmd_reports_summary,
    cmd_doctor,
)
from v3.cli.external_commands import (
    cmd_intake_profile,
    cmd_intake_list,
    cmd_intake_summarize,
    cmd_intake_registry,
    cmd_intake_clone_plan,
    cmd_intake_clone_list,
    cmd_context_pack_plan,
    cmd_context_pack_inspect,
    cmd_context_pack_generate,
    cmd_usage_inspect,
    cmd_usage_summarize,
)
from v3.cli.intelligence_commands import (
    cmd_context_plane_plan,
    cmd_context_plane_inspect,
    cmd_context_plane_evidence,
    cmd_memory_intel_profiles,
    cmd_memory_intel_mock,
    cmd_memory_intel_evidence,
    cmd_workspace_profiles,
    cmd_workspace_mock,
    cmd_workspace_evidence,
    cmd_agent_worker_profiles,
    cmd_agent_worker_mock,
    cmd_agent_worker_evidence,
    cmd_skill_evolution_profiles,
    cmd_skill_evolution_mock,
    cmd_skill_evolution_evidence,
    cmd_orchestrate_policies,
    cmd_orchestrate_plan,
    cmd_orchestrate_evidence,
)
from v3.cli.eval_ops_commands import (
    cmd_capability_list,
    cmd_capability_summary,
    cmd_capability_show,
    cmd_eval_suite,
    cmd_eval_run,
    cmd_eval_regression,
    cmd_eval_benefit,
    cmd_v4_status,
    cmd_v4_ops_check,
    cmd_v4_runbook,
    cmd_v4_summary,
    cmd_v4_freeze_verify,
    cmd_v4_metrics,
    cmd_v4_cost,
    cmd_v4_dashboard,
    cmd_v4_alerts,
    cmd_capability_select,
    cmd_capability_dedup,
    cmd_capability_conflicts,
    cmd_security_scan,
    cmd_eval_benchmark,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="systemkernel",
        description="SystemKernel v4.1 Developer CLI",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # status
    sub.add_parser("status", help="Print system status summary")

    # quality
    sub.add_parser("quality", help="Run complexity budget gate")

    # memory report
    sub.add_parser("memory", help="Memory operations").add_argument(
        "memory_action", choices=["report"], nargs="?", default="report",
        help="Memory action (default: report)"
    )

    # reports
    reports_parser = sub.add_parser("reports", help="Report operations")
    reports_parser.add_argument(
        "reports_action", choices=["list", "summary"], nargs="?", default="list",
        help="Reports action (default: list)"
    )

    # doctor
    sub.add_parser("doctor", help="Run health checks")

    # intake
    intake_parser = sub.add_parser("intake", help="Repo intake operations")
    intake_sub = intake_parser.add_subparsers(dest="intake_action", help="Intake actions")

    intake_profile_parser = intake_sub.add_parser("profile", help="Show intake profile for a repo")
    intake_profile_parser.add_argument("name", help="Profile name (e.g. Repomix, LangGraph)")

    intake_sub.add_parser("list", help="List all known repo profiles")
    intake_sub.add_parser("summarize", help="Summarize all repo profiles with decisions")

    intake_registry_parser = intake_sub.add_parser("registry", help="Generate external tool registry")
    intake_registry_parser.add_argument("--output", default=None,
                                        help="Output path (default: v3/exports/external_tool_registry.json)")

    intake_clone_plan_parser = intake_sub.add_parser("clone-plan", help="Generate GitHub clone plan")
    intake_clone_plan_parser.add_argument("--output-dir", default=None,
                                          help="Output directory (default: v3/exports/)")

    intake_sub.add_parser("clone-list", help="List recommended clone order (no actual cloning)")

    # context-pack
    cp_parser = sub.add_parser("context-pack", help="External context pack operations")
    cp_sub = cp_parser.add_subparsers(dest="cp_action", help="Context pack actions")

    cp_plan_parser = cp_sub.add_parser("plan", help="Plan a context pack (no execution)")
    cp_plan_parser.add_argument("target", help="Target directory path")
    cp_plan_parser.add_argument("--output", required=True, help="Output file path")
    cp_plan_parser.add_argument("--style", default="markdown",
                                choices=["markdown", "xml", "json", "plain"],
                                help="Output format (default: markdown)")

    cp_inspect_parser = cp_sub.add_parser("inspect", help="Inspect an existing context pack")
    cp_inspect_parser.add_argument("path", help="Path to context pack output file")

    cp_gen_parser = cp_sub.add_parser("generate", help="Generate a context pack (requires --allow-execute)")
    cp_gen_parser.add_argument("target", help="Target directory path")
    cp_gen_parser.add_argument("--output", required=True, help="Output file path")
    cp_gen_parser.add_argument("--style", default="markdown",
                               choices=["markdown", "xml", "json", "plain"],
                               help="Output format (default: markdown)")
    cp_gen_parser.add_argument("--allow-execute", action="store_true",
                               help="Explicitly allow external command execution")

    # usage
    usage_parser = sub.add_parser("usage", help="External usage report operations")
    usage_sub = usage_parser.add_subparsers(dest="usage_action", help="Usage actions")

    usage_inspect_parser = usage_sub.add_parser("inspect", help="Inspect ccusage JSON output")
    usage_inspect_parser.add_argument("path", help="Path to ccusage JSON output file")

    usage_summarize_parser = usage_sub.add_parser("summarize", help="Write normalized usage summary")
    usage_summarize_parser.add_argument("path", help="Path to ccusage JSON output file")
    usage_summarize_parser.add_argument("--output", required=True, help="Output JSON path")

    # context-plane
    ctxpl_parser = sub.add_parser("context-plane", help="Context engineering plane operations")
    ctxpl_sub = ctxpl_parser.add_subparsers(dest="ctxpl_action", help="Context plane actions")

    ctxpl_plan_parser = ctxpl_sub.add_parser("plan", help="Plan a context pack (no execution)")
    ctxpl_plan_parser.add_argument("target", help="Target directory path")
    ctxpl_plan_parser.add_argument("--output", default="", help="Output file path")
    ctxpl_plan_parser.add_argument("--style", default="markdown",
                                   choices=["markdown", "xml", "json", "plain"],
                                   help="Output format (default: markdown)")

    ctxpl_inspect_parser = ctxpl_sub.add_parser("inspect", help="Inspect an existing context pack")
    ctxpl_inspect_parser.add_argument("path", help="Path to context pack output file")

    ctxpl_evidence_parser = ctxpl_sub.add_parser("evidence", help="Build evidence bundle from context pack")
    ctxpl_evidence_parser.add_argument("path", help="Path to context pack output file")
    ctxpl_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")
    ctxpl_evidence_parser.add_argument("--target", default="", help="Original target path (for plan context)")

    # memory-intel
    mi_parser = sub.add_parser("memory-intel", help="Memory intelligence plane operations")
    mi_sub = mi_parser.add_subparsers(dest="mi_action", help="Memory intelligence actions")

    mi_sub.add_parser("profiles", help="List memory intelligence provider profiles")

    mi_mock_parser = mi_sub.add_parser("mock", help="Generate deterministic mock memory intelligence result")
    mi_mock_parser.add_argument("--provider", default="deterministic_mock_memory",
                               help="Provider ID (default: deterministic_mock_memory)")
    mi_mock_parser.add_argument("--signals", type=int, default=3,
                               help="Number of mock signals to generate (default: 3)")

    mi_evidence_parser = mi_sub.add_parser("evidence", help="Build evidence bundle from memory intelligence result")
    mi_evidence_parser.add_argument("--provider", default="deterministic_mock_memory",
                                   help="Provider ID (default: deterministic_mock_memory)")
    mi_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # workspace
    ws_parser = sub.add_parser("workspace", help="Workspace context plane operations")
    ws_sub = ws_parser.add_subparsers(dest="ws_action", help="Workspace actions")

    ws_sub.add_parser("profiles", help="List workspace provider profiles")

    ws_mock_parser = ws_sub.add_parser("mock", help="Generate deterministic mock workspace snapshot")
    ws_mock_parser.add_argument("--provider", default="deterministic_mock_workspace",
                               help="Provider ID (default: deterministic_mock_workspace)")
    ws_mock_parser.add_argument("--files", type=int, default=3,
                               help="Number of mock file refs (default: 3)")
    ws_mock_parser.add_argument("--diagnostics", type=int, default=2,
                               help="Number of mock diagnostics (default: 2)")

    ws_evidence_parser = ws_sub.add_parser("evidence", help="Build evidence bundle from workspace snapshot")
    ws_evidence_parser.add_argument("--provider", default="deterministic_mock_workspace",
                                   help="Provider ID (default: deterministic_mock_workspace)")
    ws_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # agent-worker
    aw_parser = sub.add_parser("agent-worker", help="Agent worker plane operations")
    aw_sub = aw_parser.add_subparsers(dest="aw_action", help="Agent worker actions")

    aw_sub.add_parser("profiles", help="List agent worker provider profiles")

    aw_mock_parser = aw_sub.add_parser("mock", help="Generate deterministic mock agent worker result")
    aw_mock_parser.add_argument("--provider", default="deterministic_mock_agent",
                               help="Provider ID (default: deterministic_mock_agent)")
    aw_mock_parser.add_argument("--proposals", type=int, default=2,
                               help="Number of mock proposals to generate (default: 2)")

    aw_evidence_parser = aw_sub.add_parser("evidence", help="Build evidence bundle from agent worker result")
    aw_evidence_parser.add_argument("--provider", default="deterministic_mock_agent",
                                   help="Provider ID (default: deterministic_mock_agent)")
    aw_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # skill-evolution
    se_parser = sub.add_parser("skill-evolution", help="Skill evolution plane operations")
    se_sub = se_parser.add_subparsers(dest="se_action", help="Skill evolution actions")

    se_sub.add_parser("profiles", help="List skill evolution provider profiles")

    se_mock_parser = se_sub.add_parser("mock", help="Generate deterministic mock skill evolution result")
    se_mock_parser.add_argument("--provider", default="deterministic_mock_skill_evolution",
                               help="Provider ID (default: deterministic_mock_skill_evolution)")
    se_mock_parser.add_argument("--proposals", type=int, default=2,
                               help="Number of mock proposals to generate (default: 2)")
    se_mock_parser.add_argument("--signals", type=int, default=3,
                               help="Number of mock gap signals (default: 3)")

    se_evidence_parser = se_sub.add_parser("evidence", help="Build evidence bundle from skill evolution result")
    se_evidence_parser.add_argument("--provider", default="deterministic_mock_skill_evolution",
                                   help="Provider ID (default: deterministic_mock_skill_evolution)")
    se_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # orchestrate
    orch_parser = sub.add_parser("orchestrate", help="Orchestration policy layer operations")
    orch_sub = orch_parser.add_subparsers(dest="orch_action", help="Orchestration actions")

    orch_sub.add_parser("policies", help="List orchestration policy profiles")

    orch_plan_parser = orch_sub.add_parser("plan", help="Build dry-run orchestration plan")
    orch_plan_parser.add_argument("--profile", default="safe_context_only",
                                 help="Policy profile ID (default: safe_context_only)")
    orch_plan_parser.add_argument("--objective", default="Dry-run orchestration plan",
                                 help="Objective text for the plan")

    orch_evidence_parser = orch_sub.add_parser("evidence", help="Build evidence bundle from orchestration plan")
    orch_evidence_parser.add_argument("--profile", default="safe_context_only",
                                     help="Policy profile ID (default: safe_context_only)")
    orch_evidence_parser.add_argument("--objective", default="Dry-run orchestration plan",
                                     help="Objective text for the plan")
    orch_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # eval
    eval_parser = sub.add_parser("eval", help="Evaluation and regression harness operations")
    eval_sub = eval_parser.add_subparsers(dest="eval_action", help="Eval actions")

    eval_sub.add_parser("suite", help="List default eval cases")

    eval_sub.add_parser("run", help="Run deterministic static eval suite")

    eval_reg_parser = eval_sub.add_parser("regression", help="Generate regression matrix result")
    eval_reg_parser.add_argument("--output", default="", help="Output JSON path")

    eval_ben_parser = eval_sub.add_parser("benefit", help="Generate benefit-vs-complexity report")
    eval_ben_parser.add_argument("--output", default="", help="Output JSON path")

    eval_bench_parser = eval_sub.add_parser("benchmark", help="Run SystemKernel benchmark suite")
    eval_bench_parser.add_argument("--config", default="", choices=["", "minimal", "full"],
                                   help="Harness config filter (default: all)")
    eval_bench_parser.add_argument("--output", default="",
                                   help="Output JSON path (e.g., --output benchmark_report.json)")

    # v4
    v4_parser = sub.add_parser("v4", help="V4 productization and ops commands")
    v4_sub = v4_parser.add_subparsers(dest="v4_action", help="V4 actions")

    v4_sub.add_parser("status", help="Print compact v4 operational status")

    v4_ops_check_parser = v4_sub.add_parser("ops-check", help="Print v4 operational checklist")
    v4_ops_check_parser.add_argument("--output", default="", help="Output JSON path")

    v4_runbook_parser = v4_sub.add_parser("runbook", help="Write v4 runbook")
    v4_runbook_parser.add_argument("--output", default="", help="Output directory (default: v3/exports/)")
    v4_runbook_parser.add_argument("--format", default="md", choices=["md", "json"],
                                    help="Output format (default: md)")

    v4_sub.add_parser("summary", help="Combined registry/evidence/orchestration/eval summary")

    v4_sub.add_parser("metrics", help="Export metrics in Prometheus text format")
    v4_metrics_json = v4_sub.add_parser("metrics-json", help="Export metrics in JSON format")
    v4_sub.add_parser("cost", help="Print cost summary")
    v4_dashboard_parser = v4_sub.add_parser("dashboard", help="Output Grafana dashboard JSON")
    v4_dashboard_parser.add_argument("--export", default="",
                                     help="Export to file (e.g., --export systemkernel-dashboard.json)")
    v4_sub.add_parser("alerts", help="Evaluate alert rules against current metrics")

    # freeze
    v4_freeze_parser = v4_sub.add_parser("freeze", help="Stability freeze operations")
    v4_freeze_sub = v4_freeze_parser.add_subparsers(dest="freeze_action", help="Freeze actions")

    v4_freeze_verify_parser = v4_freeze_sub.add_parser("verify", help="Verify stability freeze invariants")
    v4_freeze_verify_parser.add_argument("--output", default="", help="Output JSON path for report")

    # capability
    cap_parser = sub.add_parser("capability", help="Capability registry operations")
    cap_sub = cap_parser.add_subparsers(dest="cap_action", help="Capability actions")

    cap_sub.add_parser("list", help="List all capability registry entries")

    cap_sub.add_parser("summary", help="Print capability registry summary counts")

    cap_show_parser = cap_sub.add_parser("show", help="Show one capability registry entry")
    cap_show_parser.add_argument("adapter_id", help="Adapter ID to show")

    cap_select_parser = cap_sub.add_parser("select", help="Select top-N capabilities for a task")
    cap_select_parser.add_argument("--task-type", default="code_generation", choices=[
        "code_generation", "context_gathering", "security_scan", "memory_query",
        "cost_analysis", "execution_orchestration",
        "code", "review", "research", "build", "security",
    ], help="Task type (default: code_generation)")
    cap_select_parser.add_argument("--risk", default="low",
                                   choices=["low", "medium", "high"],
                                   help="Risk level (default: low)")
    cap_select_parser.add_argument("--top-n", type=int, default=5,
                                   help="Number of results (default: 5)")

    cap_sub.add_parser("dedup", help="Find duplicate capabilities")
    cap_sub.add_parser("conflicts", help="Detect capability conflicts")

    # security
    sec_parser = sub.add_parser("security", help="Security scanning operations")
    sec_sub = sec_parser.add_subparsers(dest="sec_action", help="Security actions")

    sec_scan_parser = sec_sub.add_parser("scan", help="Run trivy security scan")
    sec_scan_parser.add_argument("target", help="Target path to scan")
    sec_scan_parser.add_argument("--severity", default="HIGH",
                                 choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                                 help="Minimum severity (default: HIGH)")
    sec_scan_parser.add_argument("--json", action="store_true",
                                 help="Output as JSON")

    return parser


def main(argv: Optional[list] = None) -> int:
    """Main entry point. Returns exit code."""
    parser = build_parser()

    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    if args.command == "status":
        return cmd_status()
    elif args.command == "quality":
        return cmd_quality()
    elif args.command == "memory":
        if args.memory_action == "report":
            return cmd_memory_report()
        else:
            print(f"Unknown memory action: {args.memory_action}")
            return 1
    elif args.command == "reports":
        if args.reports_action == "list":
            return cmd_reports_list()
        elif args.reports_action == "summary":
            return cmd_reports_summary()
        else:
            print(f"Unknown reports action: {args.reports_action}")
            return 1
    elif args.command == "doctor":
        return cmd_doctor()
    elif args.command == "intake":
        if args.intake_action == "profile":
            return cmd_intake_profile(args.name)
        elif args.intake_action == "list":
            return cmd_intake_list()
        elif args.intake_action == "summarize":
            return cmd_intake_summarize()
        elif args.intake_action == "registry":
            return cmd_intake_registry(getattr(args, "output", None))
        elif args.intake_action == "clone-plan":
            return cmd_intake_clone_plan(getattr(args, "output_dir", None))
        elif args.intake_action == "clone-list":
            return cmd_intake_clone_list()
        else:
            print(f"Unknown intake action: {args.intake_action}")
            return 1
    elif args.command == "context-pack":
        if args.cp_action == "plan":
            return cmd_context_pack_plan(
                args.target, args.output,
                style=getattr(args, "style", "markdown"),
            )
        elif args.cp_action == "inspect":
            return cmd_context_pack_inspect(args.path)
        elif args.cp_action == "generate":
            return cmd_context_pack_generate(
                args.target, args.output,
                style=getattr(args, "style", "markdown"),
                allow_execute=getattr(args, "allow_execute", False),
            )
        else:
            print(f"Unknown context-pack action: {args.cp_action}")
            return 1
    elif args.command == "usage":
        if args.usage_action == "inspect":
            return cmd_usage_inspect(args.path)
        elif args.usage_action == "summarize":
            return cmd_usage_summarize(args.path, args.output)
        else:
            print(f"Unknown usage action: {args.usage_action}")
            return 1
    elif args.command == "context-plane":
        if args.ctxpl_action == "plan":
            return cmd_context_plane_plan(
                args.target,
                output=getattr(args, "output", ""),
                style=getattr(args, "style", "markdown"),
            )
        elif args.ctxpl_action == "inspect":
            return cmd_context_plane_inspect(args.path)
        elif args.ctxpl_action == "evidence":
            return cmd_context_plane_evidence(
                args.path,
                output=getattr(args, "output", ""),
                target=getattr(args, "target", ""),
            )
        else:
            print(f"Unknown context-plane action: {args.ctxpl_action}")
            return 1
    elif args.command == "memory-intel":
        if args.mi_action == "profiles":
            return cmd_memory_intel_profiles()
        elif args.mi_action == "mock":
            return cmd_memory_intel_mock(
                provider_id=getattr(args, "provider", "deterministic_mock_memory"),
                signals=getattr(args, "signals", 3),
            )
        elif args.mi_action == "evidence":
            return cmd_memory_intel_evidence(
                provider_id=getattr(args, "provider", "deterministic_mock_memory"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown memory-intel action: {args.mi_action}")
            return 1
    elif args.command == "workspace":
        if args.ws_action == "profiles":
            return cmd_workspace_profiles()
        elif args.ws_action == "mock":
            return cmd_workspace_mock(
                provider_id=getattr(args, "provider", "deterministic_mock_workspace"),
                files=getattr(args, "files", 3),
                diagnostics=getattr(args, "diagnostics", 2),
            )
        elif args.ws_action == "evidence":
            return cmd_workspace_evidence(
                provider_id=getattr(args, "provider", "deterministic_mock_workspace"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown workspace action: {args.ws_action}")
            return 1
    elif args.command == "agent-worker":
        if args.aw_action == "profiles":
            return cmd_agent_worker_profiles()
        elif args.aw_action == "mock":
            return cmd_agent_worker_mock(
                provider_id=getattr(args, "provider", "deterministic_mock_agent"),
                proposals=getattr(args, "proposals", 2),
            )
        elif args.aw_action == "evidence":
            return cmd_agent_worker_evidence(
                provider_id=getattr(args, "provider", "deterministic_mock_agent"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown agent-worker action: {args.aw_action}")
            return 1
    elif args.command == "skill-evolution":
        if args.se_action == "profiles":
            return cmd_skill_evolution_profiles()
        elif args.se_action == "mock":
            return cmd_skill_evolution_mock(
                provider_id=getattr(args, "provider", "deterministic_mock_skill_evolution"),
                proposals=getattr(args, "proposals", 2),
                signals=getattr(args, "signals", 3),
            )
        elif args.se_action == "evidence":
            return cmd_skill_evolution_evidence(
                provider_id=getattr(args, "provider", "deterministic_mock_skill_evolution"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown skill-evolution action: {args.se_action}")
            return 1
    elif args.command == "orchestrate":
        if args.orch_action == "policies":
            return cmd_orchestrate_policies()
        elif args.orch_action == "plan":
            return cmd_orchestrate_plan(
                profile_id=getattr(args, "profile", "safe_context_only"),
                objective=getattr(args, "objective", "Dry-run orchestration plan"),
            )
        elif args.orch_action == "evidence":
            return cmd_orchestrate_evidence(
                profile_id=getattr(args, "profile", "safe_context_only"),
                objective=getattr(args, "objective", "Dry-run orchestration plan"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown orchestrate action: {args.orch_action}")
            return 1
    elif args.command == "capability":
        if args.cap_action == "list":
            return cmd_capability_list()
        elif args.cap_action == "summary":
            return cmd_capability_summary()
        elif args.cap_action == "show":
            return cmd_capability_show(args.adapter_id)
        elif args.cap_action == "select":
            return cmd_capability_select(
                task_type=getattr(args, "task_type", "code_generation"),
                risk=getattr(args, "risk", "low"),
                top_n=getattr(args, "top_n", 5),
            )
        elif args.cap_action == "dedup":
            return cmd_capability_dedup()
        elif args.cap_action == "conflicts":
            return cmd_capability_conflicts()
        else:
            print(f"Unknown capability action: {args.cap_action}")
            return 1
    elif args.command == "security":
        if args.sec_action == "scan":
            return cmd_security_scan(
                target_path=args.target,
                severity=getattr(args, "severity", "HIGH"),
                output_json=getattr(args, "json", False),
            )
        else:
            print(f"Unknown security action: {getattr(args, 'sec_action', 'none')}")
            return 1
    elif args.command == "eval":
        if args.eval_action == "suite":
            return cmd_eval_suite()
        elif args.eval_action == "run":
            return cmd_eval_run()
        elif args.eval_action == "regression":
            return cmd_eval_regression(
                output=getattr(args, "output", ""),
            )
        elif args.eval_action == "benefit":
            return cmd_eval_benefit(
                output=getattr(args, "output", ""),
            )
        elif args.eval_action == "benchmark":
            return cmd_eval_benchmark(
                config=getattr(args, "config", ""),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown eval action: {args.eval_action}")
            return 1
    elif args.command == "v4":
        if args.v4_action == "status":
            return cmd_v4_status()
        elif args.v4_action == "ops-check":
            return cmd_v4_ops_check(
                output=getattr(args, "output", ""),
            )
        elif args.v4_action == "runbook":
            return cmd_v4_runbook(
                output=getattr(args, "output", ""),
                fmt=getattr(args, "format", "md"),
            )
        elif args.v4_action == "summary":
            return cmd_v4_summary()
        elif args.v4_action == "metrics":
            return cmd_v4_metrics(output_json=False)
        elif args.v4_action == "metrics-json":
            return cmd_v4_metrics(output_json=True)
        elif args.v4_action == "cost":
            return cmd_v4_cost()
        elif args.v4_action == "dashboard":
            return cmd_v4_dashboard(
                output=getattr(args, "export", ""),
            )
        elif args.v4_action == "alerts":
            return cmd_v4_alerts()
        elif args.v4_action == "freeze":
            if args.freeze_action == "verify":
                return cmd_v4_freeze_verify(
                    output=getattr(args, "output", ""),
                )
            else:
                print(f"Unknown freeze action: {args.freeze_action}")
                return 1
        else:
            print(f"Unknown v4 action: {args.v4_action}")
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
