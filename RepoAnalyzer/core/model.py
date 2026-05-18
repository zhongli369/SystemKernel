from dataclasses import dataclass, field, asdict
from typing import Dict, List


@dataclass
class FileEntry:
    path: str
    name: str
    ext: str
    size: int
    language: str
    role: str = ""
    importance_score: float = 0.0
    is_entrypoint: bool = False
    tags: List[str] = field(default_factory=list)


@dataclass
class FolderEntry:
    path: str
    depth: int


@dataclass
class RepoStats:
    total_files: int = 0
    total_folders: int = 0
    language_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class RepoStructure:
    repo_name: str
    root_path: str
    files: List[FileEntry] = field(default_factory=list)
    folders: List[FolderEntry] = field(default_factory=list)
    stats: RepoStats = field(default_factory=RepoStats)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DependencyEdge:
    source: str
    target: str
    type: str = "import"
    language: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "from": self.source,
            "to": self.target,
            "type": self.type,
            "language": self.language,
            "confidence": self.confidence,
        }


@dataclass
class DependencyGraphStats:
    total_edges: int = 0
    unique_nodes: int = 0


@dataclass
class DependencyGraph:
    nodes: List[str] = field(default_factory=list)
    edges: List[DependencyEdge] = field(default_factory=list)
    stats: DependencyGraphStats = field(default_factory=DependencyGraphStats)

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "edges": [e.to_dict() for e in self.edges],
            "stats": asdict(self.stats),
        }


# --- Phase 2-B: Graph Model ---

@dataclass
class GraphNode:
    id: str
    role: str = ""
    importance_score: float = 0.0
    is_entrypoint: bool = False


@dataclass
class FanInOut:
    fan_in: int = 0
    fan_out: int = 0


@dataclass
class GraphAnalysisStats:
    total_nodes: int = 0
    total_edges: int = 0
    isolated_nodes: List[str] = field(default_factory=list)
    entrypoint_reachability: Dict[str, List[str]] = field(default_factory=dict)
    fan_stats: Dict[str, FanInOut] = field(default_factory=dict)


@dataclass
class GraphModel:
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[DependencyEdge] = field(default_factory=list)
    adjacency_list: Dict[str, List[str]] = field(default_factory=dict)
    reverse_adjacency_list: Dict[str, List[str]] = field(default_factory=dict)
    stats: GraphAnalysisStats = field(default_factory=GraphAnalysisStats)

    def to_dict(self) -> dict:
        fan_dict = {
            k: asdict(v) for k, v in self.stats.fan_stats.items()
        }
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "adjacency_list": self.adjacency_list,
            "reverse_adjacency_list": self.reverse_adjacency_list,
            "stats": {
                "total_nodes": self.stats.total_nodes,
                "total_edges": self.stats.total_edges,
                "isolated_nodes": self.stats.isolated_nodes,
                "entrypoint_reachability": self.stats.entrypoint_reachability,
                "fan_stats": fan_dict,
            },
        }


# --- Phase 2.5: Graph Interpretation ---

@dataclass
class InterpretedNode:
    id: str
    role: str = ""
    importance_score: float = 0.0
    is_entrypoint: bool = False
    criticality_score: float = 0.0
    system_role: str = ""
    impact_level: str = ""


@dataclass
class InterpretedEdge:
    source: str
    target: str
    type: str = "import"
    language: str = ""
    confidence: float = 1.0
    dependency_type: str = ""

    def to_dict(self) -> dict:
        return {
            "from": self.source,
            "to": self.target,
            "type": self.type,
            "language": self.language,
            "confidence": self.confidence,
            "dependency_type": self.dependency_type,
        }


@dataclass
class InterpretedGraph:
    nodes: List[InterpretedNode] = field(default_factory=list)
    edges: List[InterpretedEdge] = field(default_factory=list)
    adjacency_list: Dict[str, List[str]] = field(default_factory=dict)
    reverse_adjacency_list: Dict[str, List[str]] = field(default_factory=dict)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "adjacency_list": self.adjacency_list,
            "reverse_adjacency_list": self.reverse_adjacency_list,
            "stats": self.stats,
        }


# --- Phase 3: System Intelligence ---

@dataclass
class Bottleneck:
    node_id: str
    bottleneck_type: str        # primary / orchestration / system_critical
    severity: str               # critical / high / medium
    reason: str
    fan_in: int = 0
    fan_out: int = 0


@dataclass
class ArchitectureLayers:
    entry_layer: List[str] = field(default_factory=list)
    orchestration_layer: List[str] = field(default_factory=list)
    core_layer: List[str] = field(default_factory=list)
    utility_layer: List[str] = field(default_factory=list)
    leaf_layer: List[str] = field(default_factory=list)


@dataclass
class CouplingMetrics:
    high_coupling_nodes: List[str] = field(default_factory=list)
    low_cohesion_nodes: List[str] = field(default_factory=list)
    avg_coupling_score: float = 0.0


@dataclass
class SystemHealth:
    overall_score: float = 0.0
    risk_level: str = "low"     # low / medium / high
    fragile_modules: List[str] = field(default_factory=list)
    refactor_candidates: List[str] = field(default_factory=list)


@dataclass
class SystemInsights:
    bottlenecks: List[Bottleneck] = field(default_factory=list)
    architecture_layers: ArchitectureLayers = field(default_factory=ArchitectureLayers)
    coupling_metrics: CouplingMetrics = field(default_factory=CouplingMetrics)
    system_health: SystemHealth = field(default_factory=SystemHealth)

    def to_dict(self) -> dict:
        return {
            "bottlenecks": [asdict(b) for b in self.bottlenecks],
            "architecture_layers": asdict(self.architecture_layers),
            "coupling_metrics": asdict(self.coupling_metrics),
            "system_health": asdict(self.system_health),
        }


# --- Phase 4: Task Coupling ---

@dataclass
class TaskStep:
    step_id: int
    description: str
    suggested_skills: List[str] = field(default_factory=list)
    dependency_nodes: List[str] = field(default_factory=list)


@dataclass
class AnalysisTask:
    task_id: str = ""
    title: str = ""
    type: str = ""                # refactor / cleanup / decouple / optimize / stabilize
    priority: str = ""            # P0 / P1 / P2
    target_nodes: List[str] = field(default_factory=list)
    impact_score: float = 0.0
    risk_level: str = "low"       # low / medium / high
    reason: str = ""
    steps: List[TaskStep] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    global_task_id: str = ""      # RA::<repo>::<task_id> cross-system identity overlay
    skill_id: str = ""           # resolved skill identifier from SkillSystem v4
    skill_input: dict = field(default_factory=dict)   # prepared input schema
    skill_output: dict = field(default_factory=dict)  # binding/execution result


@dataclass
class TaskPlanSummary:
    total_tasks: int = 0
    high_priority_tasks: int = 0
    risk_distribution: dict = field(default_factory=dict)


@dataclass
class TaskPlan:
    tasks: List[AnalysisTask] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)
    summary: TaskPlanSummary = field(default_factory=TaskPlanSummary)

    def to_dict(self) -> dict:
        return {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "global_task_id": t.global_task_id,
                    "title": t.title,
                    "type": t.type,
                    "priority": t.priority,
                    "target_nodes": t.target_nodes,
                    "impact_score": t.impact_score,
                    "risk_level": t.risk_level,
                    "reason": t.reason,
                    "steps": [asdict(s) for s in t.steps],
                    "depends_on": t.depends_on,
                    "skill_id": t.skill_id,
                    "skill_input": t.skill_input,
                    "skill_output": t.skill_output,
                }
                for t in self.tasks
            ],
            "execution_order": self.execution_order,
            "summary": asdict(self.summary),
        }
