"""Phase 4 pipeline: Task Coupling Layer.

Orchestrates: load system insights + interpreted graph →
generate tasks from bottlenecks, coupling, and architecture →
compute impact scores → attach skill suggestions →
assign dependencies → build execution order → export task_plan.json
"""

import json
import os
from typing import Dict, List, Set

from core.model import (
    AnalysisTask,
    Bottleneck,
    TaskPlan,
    TaskPlanSummary,
)
from core.bottleneck_task_generator import generate_bottleneck_tasks
from core.coupling_task_builder import generate_coupling_tasks
from core.architecture_task_mapper import generate_architecture_tasks
from core.impact_task_analyzer import compute_impact_scores
from core.skill_suggestion_mapper import suggest_skills
from core.output_contract import wrap_output, unwrap_output


def _json_to_bottlenecks(raw_list: list) -> list:
    result = []
    for b in raw_list:
        result.append(Bottleneck(
            node_id=b["node_id"],
            bottleneck_type=b["bottleneck_type"],
            severity=b["severity"],
            reason=b["reason"],
            fan_in=b.get("fan_in", 0),
            fan_out=b.get("fan_out", 0),
        ))
    return result


def _determine_skip_nodes(interpreted_nodes: list) -> Set[str]:
    """Skip output JSON files and __init__.py from task generation."""
    skip: Set[str] = set()
    for n in interpreted_nodes:
        nid = n.get("id", "")
        if nid.startswith("output/") and nid.endswith(".json"):
            skip.add(nid)
        if nid.endswith("__init__.py"):
            skip.add(nid)
    return skip


def _assign_dependencies(tasks: List[AnalysisTask]) -> None:
    """Assign depends_on based on target_node overlap between tasks."""
    for i, task in enumerate(tasks):
        targets_i = set(task.target_nodes)
        for j, other in enumerate(tasks):
            if i == j:
                continue
            targets_j = set(other.target_nodes)
            if targets_i & targets_j and other.task_id < task.task_id:
                if other.task_id not in task.depends_on:
                    task.depends_on.append(other.task_id)


def _build_execution_order(tasks: List[AnalysisTask]) -> List[str]:
    """Sort tasks by priority (P0→P1→P2), then by impact_score descending."""
    prio_weight = {"P0": 0, "P1": 1, "P2": 2}
    sorted_tasks = sorted(
        tasks,
        key=lambda t: (prio_weight.get(t.priority, 99), -t.impact_score),
    )
    return [t.task_id for t in sorted_tasks]


def _build_summary(tasks: List[AnalysisTask]) -> TaskPlanSummary:
    high = sum(1 for t in tasks if t.priority in ("P0", "P1"))
    risk_dist = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for t in tasks:
        r = t.risk_level
        risk_dist[r] = risk_dist.get(r, 0) + 1
    return TaskPlanSummary(
        total_tasks=len(tasks),
        high_priority_tasks=high,
        risk_distribution=risk_dist,
    )


def run_task_planning_pipeline(repo_path: str, output_dir: str) -> str:
    """Full Phase 4 pipeline.

    Reads output/system_insights.json and output/interpreted_graph.json,
    produces output/task_plan.json.
    """
    insights_path = os.path.join(output_dir, "system_insights.json")
    interpreted_path = os.path.join(output_dir, "interpreted_graph.json")

    for p, label in [(insights_path, "insights"), (interpreted_path, "interpret")]:
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"{label} not found: {p}. Run earlier phases first."
            )

    with open(insights_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    insights_data = unwrap_output(raw)

    with open(interpreted_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    interpreted_data = unwrap_output(raw)

    # Build lookup maps from interpreted graph
    interpreted_nodes = interpreted_data.get("nodes", [])
    adjacency = interpreted_data.get("adjacency_list", {})
    # Phase 4 generators expect raw dicts (not FanInOut objects)
    fan_data = interpreted_data.get("stats", {}).get("fan_stats", {})

    criticality_map: Dict[str, float] = {}
    node_roles: Dict[str, str] = {}
    node_system_roles: Dict[str, str] = {}
    for n in interpreted_nodes:
        nid = n["id"]
        criticality_map[nid] = n.get("criticality_score", 0.0)
        node_roles[nid] = n.get("role", "")
        node_system_roles[nid] = n.get("system_role", "")

    # bottleneck_task_generator expects Bottleneck objects
    bottlenecks = _json_to_bottlenecks(insights_data.get("bottlenecks", []))

    # coupling_task_builder and architecture_task_mapper expect raw dicts
    arch_layers_dict = insights_data.get("architecture_layers", {})
    coupling_dict = insights_data.get("coupling_metrics", {})

    # Determine nodes to skip
    skip_nodes = _determine_skip_nodes(interpreted_nodes)

    # Compute repo_name for global_task_id overlay
    repo_name = os.path.basename(os.path.abspath(repo_path))

    # Generate tasks from three sources
    all_tasks: List[AnalysisTask] = []
    all_tasks.extend(generate_bottleneck_tasks(bottlenecks, repo_name))
    all_tasks.extend(generate_coupling_tasks(coupling_dict, fan_data, criticality_map, skip_nodes, repo_name))
    all_tasks.extend(generate_architecture_tasks(arch_layers_dict, criticality_map, fan_data, skip_nodes, repo_name))

    # Compute impact scores
    all_tasks = compute_impact_scores(all_tasks, fan_data, criticality_map, adjacency)

    # Attach skill suggestions to each step
    for task in all_tasks:
        for step in task.steps:
            suggested = suggest_skills(
                task_type=task.type,
                target_nodes=step.dependency_nodes,
                node_roles=node_roles,
                node_system_roles=node_system_roles,
            )
            # Merge without losing existing suggestions (deduplicate)
            merged = list(step.suggested_skills)
            for s in suggested:
                if s not in merged:
                    merged.append(s)
            step.suggested_skills = merged

    # Skill Binding Stage — resolve skill_id per task via SkillSystem v4
    skill_enabled = os.environ.get("REPOANALYZER_SKILL_EXECUTION_ENABLED", "").lower() in ("1", "true", "yes")
    if skill_enabled:
        from core.skill_integration.skill_executor import bind_skill
        for task in all_tasks:
            bind_skill(task)

    # Architecture Constraint Validation — read-only, never modifies data
    guard_mode = os.environ.get("REPOANALYZER_ARCHITECTURE_GUARD", "soft")
    if guard_mode in ("soft", "strict"):
        from core.validation import run_validation
        baseline_path = os.path.join(output_dir, ".repoanalyzer_baseline.json")
        run_validation(
            tasks=all_tasks,
            repo_name=repo_name,
            skill_enabled=skill_enabled,
            mode=guard_mode,
            baseline_path=baseline_path,
        )

    # Assign dependencies between tasks
    _assign_dependencies(all_tasks)

    # Build execution order
    execution_order = _build_execution_order(all_tasks)

    # Build summary
    summary = _build_summary(all_tasks)

    plan = TaskPlan(
        tasks=all_tasks,
        execution_order=execution_order,
        summary=summary,
    )

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "task_plan.json")

    repo_id = os.path.basename(os.path.abspath(repo_path))
    with open(output_path, "w", encoding="utf-8") as f:
        wrapped = wrap_output(repo_id, "plan", plan.to_dict())
        json.dump(wrapped, f, indent=2, ensure_ascii=False)

    return output_path
