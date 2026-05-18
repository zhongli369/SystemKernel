import argparse
import json
import os
import sys

from core.parser import parse_repo
from core.enrich_pipeline import run_enrich_pipeline
from core.dependency_pipeline import run_dependency_pipeline
from core.graph_pipeline import run_graph_pipeline
from core.interpretation_pipeline import run_interpretation_pipeline
from core.system_insights_pipeline import run_system_insights_pipeline
from core.task_planning_pipeline import run_task_planning_pipeline

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def cmd_scan(args):
    target_path = os.path.abspath(args.path)

    if not os.path.isdir(target_path):
        print(f"Error: '{args.path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {target_path}")
    structure = parse_repo(target_path)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "repo_map.json")

    from core.output_contract import wrap_output
    repo_id = os.path.basename(target_path)

    with open(output_path, "w", encoding="utf-8") as f:
        wrapped = wrap_output(repo_id, "scan", structure.to_dict())
        json.dump(wrapped, f, indent=2, ensure_ascii=False)

    print(f"Output: {output_path}")
    print(f"Files: {structure.stats.total_files}")
    print(f"Folders: {structure.stats.total_folders}")

    if structure.stats.language_distribution:
        print("Language distribution:")
        for lang, count in structure.stats.language_distribution.items():
            print(f"  {lang}: {count}")


def cmd_enrich(args):
    target_path = os.path.abspath(args.path)

    if not os.path.isdir(target_path):
        print(f"Error: '{args.path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Enriching repo_map.json for: {target_path}")

    try:
        output_path = run_enrich_pipeline(target_path, OUTPUT_DIR)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from core.output_contract import unwrap_output

    print(f"Output: {output_path}")

    # Print summary
    with open(output_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    entrypoints = [f for f in data["files"] if f["is_entrypoint"]]
    entrypoint_names = [f["name"] for f in entrypoints]
    roles = {}
    for f in data["files"]:
        r = f["role"]
        roles[r] = roles.get(r, 0) + 1

    print(f"\nEntry points: {entrypoint_names}")
    print(f"Role distribution:")
    for role, count in sorted(roles.items()):
        print(f"  {role}: {count}")


def cmd_graph(args):
    target_path = os.path.abspath(args.path)

    if not os.path.isdir(target_path):
        print(f"Error: '{args.path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Building dependency graph for: {target_path}")

    try:
        output_path = run_dependency_pipeline(target_path, OUTPUT_DIR)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from core.output_contract import unwrap_output

    print(f"Output: {output_path}")

    with open(output_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    stats = data["stats"]
    print(f"\nTotal edges: {stats['total_edges']}")
    print(f"Unique nodes: {stats['unique_nodes']}")

    if stats["total_edges"] > 0:
        edges = data["edges"]
        # Show edges by confidence tier
        high = sum(1 for e in edges if e["confidence"] >= 1.0)
        medium = sum(1 for e in edges if 0.7 <= e["confidence"] < 1.0)
        low = sum(1 for e in edges if e["confidence"] < 0.7)
        print(f"  High confidence (1.0): {high}")
        print(f"  Medium confidence (0.7-0.99): {medium}")
        if low:
            print(f"  Low confidence (<0.7): {low}")

        # Show first few edges as sample
        print(f"\nSample edges (first 10):")
        for edge in edges[:10]:
            print(f"  {edge['from']} → {edge['to']}  [{edge['language']}, {edge['confidence']}]")


def cmd_analyze(args):
    target_path = os.path.abspath(args.path)

    if not os.path.isdir(target_path):
        print(f"Error: '{args.path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing dependency graph for: {target_path}")

    try:
        output_path = run_graph_pipeline(target_path, OUTPUT_DIR)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from core.output_contract import unwrap_output

    print(f"Output: {output_path}")

    with open(output_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    stats = data["stats"]
    print(f"\nTotal nodes: {stats['total_nodes']}")
    print(f"Total edges: {stats['total_edges']}")

    isolated = stats["isolated_nodes"]
    if isolated:
        print(f"\nIsolated nodes ({len(isolated)}):")
        for node in isolated[:20]:
            print(f"  {node}")
        if len(isolated) > 20:
            print(f"  ... and {len(isolated) - 20} more")

    reachability = stats.get("entrypoint_reachability", {})
    if reachability:
        print(f"\nEntrypoint reachability:")
        for ep, reachable in reachability.items():
            print(f"  {ep} → {len(reachable)} reachable nodes")

    fan_stats = stats.get("fan_stats", {})
    if fan_stats:
        # Show top fan-out nodes
        sorted_by_fan_out = sorted(
            fan_stats.items(), key=lambda x: x[1]["fan_out"], reverse=True
        )
        print(f"\nTop 5 by fan-out:")
        for node, fan in sorted_by_fan_out[:5]:
            print(f"  {node}  in={fan['fan_in']}  out={fan['fan_out']}")

        # Show top fan-in nodes
        sorted_by_fan_in = sorted(
            fan_stats.items(), key=lambda x: x[1]["fan_in"], reverse=True
        )
        print(f"\nTop 5 by fan-in:")
        for node, fan in sorted_by_fan_in[:5]:
            if fan["fan_in"] > 0:
                print(f"  {node}  in={fan['fan_in']}  out={fan['fan_out']}")


def cmd_interpret(args):
    target_path = os.path.abspath(args.path)

    if not os.path.isdir(target_path):
        print(f"Error: '{args.path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Interpreting dependency graph for: {target_path}")

    try:
        output_path = run_interpretation_pipeline(target_path, OUTPUT_DIR)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from core.output_contract import unwrap_output

    print(f"Output: {output_path}")

    with open(output_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    stats = data["stats"]
    print(f"\nTotal nodes: {stats['total_nodes']}")
    print(f"Total edges: {stats['total_edges']}")

    cd = stats.get("criticality_distribution", {})
    if cd:
        print(f"\nCriticality distribution:")
        for level in ("high", "medium", "low"):
            print(f"  {level}: {cd.get(level, 0)}")

    srd = stats.get("system_role_distribution", {})
    if srd:
        print(f"\nSystem role distribution:")
        for role, count in sorted(srd.items()):
            print(f"  {role}: {count}")

    dtd = stats.get("dependency_type_distribution", {})
    if dtd:
        print(f"\nDependency type distribution:")
        for dt, count in sorted(dtd.items(), key=lambda x: -x[1]):
            print(f"  {dt}: {count}")

    print(f"\nTop 5 criticality scores:")
    nodes_sorted = sorted(data["nodes"], key=lambda x: -x["criticality_score"])
    for n in nodes_sorted[:5]:
        print(f"  {n['id']}")
        print(f"    criticality={n['criticality_score']}  system_role={n['system_role']}  impact={n['impact_level']}")


def cmd_insights(args):
    target_path = os.path.abspath(args.path)

    if not os.path.isdir(target_path):
        print(f"Error: '{args.path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Generating system insights for: {target_path}")

    try:
        output_path = run_system_insights_pipeline(target_path, OUTPUT_DIR)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from core.output_contract import unwrap_output

    print(f"Output: {output_path}")

    with open(output_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    health = data["system_health"]
    print(f"\n=== System Health ===")
    print(f"Overall score: {health['overall_score']}")
    print(f"Risk level: {health['risk_level']}")

    bottlenecks = data["bottlenecks"]
    if bottlenecks:
        print(f"\n=== Bottlenecks ({len(bottlenecks)}) ===")
        for b in bottlenecks:
            print(f"  [{b['severity'].upper()}] {b['node_id']}")
            print(f"    type={b['bottleneck_type']}  fan_in={b['fan_in']}  fan_out={b['fan_out']}")
            print(f"    {b['reason']}")
    else:
        print(f"\nNo bottlenecks detected.")

    coupling = data["coupling_metrics"]
    print(f"\n=== Coupling ===")
    print(f"Avg coupling score: {coupling['avg_coupling_score']}")
    if coupling["high_coupling_nodes"]:
        print(f"High coupling nodes ({len(coupling['high_coupling_nodes'])}):")
        for nid in coupling["high_coupling_nodes"]:
            print(f"  {nid}")
    if coupling["low_cohesion_nodes"]:
        print(f"Low cohesion nodes ({len(coupling['low_cohesion_nodes'])}):")
        for nid in coupling["low_cohesion_nodes"]:
            print(f"  {nid}")

    layers = data["architecture_layers"]
    print(f"\n=== Architecture Layers ===")
    for layer_name, nodes in layers.items():
        print(f"  {layer_name}: {len(nodes)} nodes")

    if health["fragile_modules"]:
        print(f"\nFragile modules: {health['fragile_modules']}")
    if health["refactor_candidates"]:
        print(f"\nRefactor candidates: {health['refactor_candidates']}")


def cmd_plan(args):
    target_path = os.path.abspath(args.path)

    if not os.path.isdir(target_path):
        print(f"Error: '{args.path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Generating task plan for: {target_path}")

    try:
        output_path = run_task_planning_pipeline(target_path, OUTPUT_DIR)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from core.output_contract import unwrap_output

    print(f"Output: {output_path}")

    with open(output_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = unwrap_output(raw)

    summary = data["summary"]
    print(f"\n=== Task Plan Summary ===")
    print(f"Total tasks: {summary['total_tasks']}")
    print(f"High priority (P0+P1): {summary['high_priority_tasks']}")
    print(f"Risk distribution: {summary['risk_distribution']}")

    tasks = data["tasks"]
    by_type = {}
    for t in tasks:
        tp = t["type"]
        by_type[tp] = by_type.get(tp, 0) + 1
    print(f"\nTask type distribution:")
    for tp, count in sorted(by_type.items()):
        print(f"  {tp}: {count}")

    print(f"\nExecution order (first 10):")
    for task_id in data["execution_order"][:10]:
        task = next(t for t in tasks if t["task_id"] == task_id)
        print(f"  [{task['priority']}] {task_id}: {task['title']}")
        print(f"    impact={task['impact_score']}  risk={task['risk_level']}  steps={len(task['steps'])}")

    if len(data["execution_order"]) > 10:
        print(f"  ... and {len(data['execution_order']) - 10} more")


def main():
    parser = argparse.ArgumentParser(
        prog="repo-analyzer",
        description="Repo Analyzer — Repository Analysis Tool",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Phase 1: Scan repository structure")
    scan_parser.add_argument("path", help="Path to the repository root")
    scan_parser.set_defaults(func=cmd_scan)

    enrich_parser = subparsers.add_parser("enrich", help="Phase 1.5: Enrich with semantic layer")
    enrich_parser.add_argument("path", help="Path to the repository root")
    enrich_parser.set_defaults(func=cmd_enrich)

    graph_parser = subparsers.add_parser("graph", help="Phase 2-A: Extract dependency edges")
    graph_parser.add_argument("path", help="Path to the repository root")
    graph_parser.set_defaults(func=cmd_graph)

    analyze_parser = subparsers.add_parser("analyze", help="Phase 2-B: Build and analyze dependency graph")
    analyze_parser.add_argument("path", help="Path to the repository root")
    analyze_parser.set_defaults(func=cmd_analyze)

    interpret_parser = subparsers.add_parser("interpret", help="Phase 2.5: Interpret graph with semantic layer")
    interpret_parser.add_argument("path", help="Path to the repository root")
    interpret_parser.set_defaults(func=cmd_interpret)

    insights_parser = subparsers.add_parser("insights", help="Phase 3: Generate system intelligence insights")
    insights_parser.add_argument("path", help="Path to the repository root")
    insights_parser.set_defaults(func=cmd_insights)

    plan_parser = subparsers.add_parser("plan", help="Phase 4: Generate task plan from insights")
    plan_parser.add_argument("path", help="Path to the repository root")
    plan_parser.set_defaults(func=cmd_plan)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
