"""
Observability Graph — Deterministic runtime graph projection from event streams.

Phase 4C: Projects an immutable event stream into a structured RuntimeGraph
with nodes, edges, and a deterministic graph_hash. Pure functional — no side
effects, no file I/O, no LLM. Reconstructable from events alone.

Events are the source of truth. Checkpoints are snapshot nodes only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional, Tuple

from v3.kernel.events import ExecutionEvent, EventType, json_dumps_stable


# ═══════════════════════════════════════════════════════════════════════
# Node Types
# ═══════════════════════════════════════════════════════════════════════

class NodeType:
    EXECUTION = "execution"
    STAGE = "stage"
    CHECKPOINT = "checkpoint"
    FORK = "fork"
    ERROR = "error"
    RETRY = "retry"

    ALL = {EXECUTION, STAGE, CHECKPOINT, FORK, ERROR, RETRY}


# ═══════════════════════════════════════════════════════════════════════
# Edge Types
# ═══════════════════════════════════════════════════════════════════════

class EdgeType:
    NEXT = "next"
    CONTAINS = "contains"
    FAILED_AT = "failed_at"
    RETRIED_BY = "retried_by"
    FORKED_FROM = "forked_from"
    CHECKPOINTED_AT = "checkpointed_at"

    ALL = {NEXT, CONTAINS, FAILED_AT, RETRIED_BY, FORKED_FROM, CHECKPOINTED_AT}


# ═══════════════════════════════════════════════════════════════════════
# RuntimeNode
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuntimeNode:
    """A single node in the runtime observability graph."""

    node_id: str
    node_type: str
    label: str
    sequence_start: int
    sequence_end: int
    status: str = "ok"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "sequence_start": self.sequence_start,
            "sequence_end": self.sequence_end,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


# ═══════════════════════════════════════════════════════════════════════
# RuntimeEdge
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuntimeEdge:
    """A directed edge between two RuntimeNodes."""

    source: str
    target: str
    edge_type: str
    sequence: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "sequence": self.sequence,
            "metadata": dict(self.metadata),
        }


# ═══════════════════════════════════════════════════════════════════════
# RuntimeGraph
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuntimeGraph:
    """Deterministic projection of an event stream into a graph.

    Built entirely from events. No file I/O, no LLM, no side effects.
    graph_hash is computed deterministically from node/edge content.
    """

    execution_id: str
    nodes: Tuple[RuntimeNode, ...]
    edges: Tuple[RuntimeEdge, ...]
    stage_order: Tuple[str, ...]
    event_count: int
    failure_count: int
    retry_count: int
    checkpoint_count: int
    fork_count: int
    duration_ms: int
    graph_hash: str

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "stage_order": list(self.stage_order),
            "event_count": self.event_count,
            "failure_count": self.failure_count,
            "retry_count": self.retry_count,
            "checkpoint_count": self.checkpoint_count,
            "fork_count": self.fork_count,
            "duration_ms": self.duration_ms,
            "graph_hash": self.graph_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Graph Builder — pure function: events → RuntimeGraph
# ═══════════════════════════════════════════════════════════════════════

def build_graph(events: Tuple[ExecutionEvent, ...]) -> RuntimeGraph:
    """Build a RuntimeGraph from an ordered tuple of ExecutionEvents.

    Pure function. Deterministic. Same events → same graph.
    """
    if not events:
        return RuntimeGraph(
            execution_id="",
            nodes=(),
            edges=(),
            stage_order=(),
            event_count=0,
            failure_count=0,
            retry_count=0,
            checkpoint_count=0,
            fork_count=0,
            duration_ms=0,
            graph_hash=_empty_graph_hash(),
        )

    eid = events[0].execution_id
    nodes: list[RuntimeNode] = []
    edges: list[RuntimeEdge] = []

    execution_node_id = f"exec-{eid[:8]}"
    nodes.append(RuntimeNode(
        node_id=execution_node_id,
        node_type=NodeType.EXECUTION,
        label=f"Execution {eid[:12]}",
        sequence_start=0,
        sequence_end=len(events) - 1,
    ))

    failure_count = 0
    retry_count = 0
    checkpoint_count = 0
    fork_count = 0
    stage_order: list[str] = []
    duration_ms = 0
    edge_seq = 0

    last_stage_node_id: Optional[str] = None
    last_node_id = execution_node_id

    for i, event in enumerate(events):
        etype = event.event_type
        payload = event.payload

        if etype == EventType.EXECUTION_STARTED:
            edges.append(RuntimeEdge(
                source=execution_node_id,
                target=execution_node_id,
                edge_type=EdgeType.NEXT,
                sequence=edge_seq,
                metadata={"event_type": etype},
            ))
            edge_seq += 1
            if "stage_order" in payload:
                stage_order = list(payload["stage_order"])

        elif etype == EventType.STAGE_STARTED:
            stage_name = payload.get("stage_name", "unknown")
            node_id = f"stage-{stage_name}-{eid[:8]}"
            nodes.append(RuntimeNode(
                node_id=node_id,
                node_type=NodeType.STAGE,
                label=stage_name,
                sequence_start=i,
                sequence_end=i,
            ))
            edges.append(RuntimeEdge(
                source=execution_node_id,
                target=node_id,
                edge_type=EdgeType.CONTAINS,
                sequence=edge_seq,
            ))
            edge_seq += 1
            if last_stage_node_id:
                edges.append(RuntimeEdge(
                    source=last_stage_node_id,
                    target=node_id,
                    edge_type=EdgeType.NEXT,
                    sequence=edge_seq,
                ))
                edge_seq += 1
            last_stage_node_id = node_id
            last_node_id = node_id

        elif etype == EventType.STAGE_COMPLETED:
            stage_name = payload.get("stage_name", "unknown")
            stage_dur = payload.get("duration_ms", 0)
            duration_ms += stage_dur
            # Update the corresponding stage node's end sequence
            for j, node in enumerate(nodes):
                if node.label == stage_name and node.node_type == NodeType.STAGE:
                    nodes[j] = RuntimeNode(
                        node_id=node.node_id,
                        node_type=node.node_type,
                        label=node.label,
                        sequence_start=node.sequence_start,
                        sequence_end=i,
                        status="ok",
                        metadata={"duration_ms": stage_dur},
                    )
                    break

        elif etype == EventType.STAGE_FAILED:
            stage_name = payload.get("stage_name", "unknown")
            error_msg = payload.get("error", "")
            failure_count += 1
            node_id = f"error-{stage_name}-{eid[:8]}"
            nodes.append(RuntimeNode(
                node_id=node_id,
                node_type=NodeType.ERROR,
                label=f"Failed: {stage_name}",
                sequence_start=i,
                sequence_end=i,
                status="failed",
                metadata={"stage_name": stage_name, "error": error_msg},
            ))
            # Edge from last stage node to error
            if last_stage_node_id:
                edges.append(RuntimeEdge(
                    source=last_stage_node_id,
                    target=node_id,
                    edge_type=EdgeType.FAILED_AT,
                    sequence=edge_seq,
                ))
                edge_seq += 1
            edges.append(RuntimeEdge(
                source=execution_node_id,
                target=node_id,
                edge_type=EdgeType.CONTAINS,
                sequence=edge_seq,
            ))
            edge_seq += 1
            last_node_id = node_id

        elif etype == EventType.RETRY_INCREMENTED:
            retry_count += 1
            node_id = f"retry-{retry_count}-{eid[:8]}"
            nodes.append(RuntimeNode(
                node_id=node_id,
                node_type=NodeType.RETRY,
                label=f"Retry #{retry_count}",
                sequence_start=i,
                sequence_end=i,
                metadata={"retry_number": retry_count},
            ))
            if last_node_id:
                edges.append(RuntimeEdge(
                    source=last_node_id,
                    target=node_id,
                    edge_type=EdgeType.RETRIED_BY,
                    sequence=edge_seq,
                ))
                edge_seq += 1
            last_node_id = node_id

        elif etype == EventType.FORK_CREATED:
            fork_count += 1
            original_eid = payload.get("original_execution_id", "")
            node_id = f"fork-{fork_count}-{eid[:8]}"
            nodes.append(RuntimeNode(
                node_id=node_id,
                node_type=NodeType.FORK,
                label=f"Fork from {original_eid[:12]}",
                sequence_start=i,
                sequence_end=i,
                metadata={
                    "original_execution_id": original_eid,
                    "forked_at_sequence": payload.get("forked_at_sequence", 0),
                },
            ))
            edges.append(RuntimeEdge(
                source=execution_node_id,
                target=node_id,
                edge_type=EdgeType.FORKED_FROM,
                sequence=edge_seq,
            ))
            edge_seq += 1
            last_node_id = node_id

        elif etype in (EventType.EVENT_RECORDED, EventType.REPLAY_STARTED, EventType.REPLAY_COMPLETED):
            # Checkpoint-related events → checkpoint node
            checkpoint_count += 1
            node_id = f"checkpoint-{checkpoint_count}-{eid[:8]}"
            nodes.append(RuntimeNode(
                node_id=node_id,
                node_type=NodeType.CHECKPOINT,
                label=f"Snapshot #{checkpoint_count}",
                sequence_start=i,
                sequence_end=i,
                status="snapshot",
                metadata={"event_type": etype, "is_truth_source": False},
            ))
            if last_node_id:
                edges.append(RuntimeEdge(
                    source=last_node_id,
                    target=node_id,
                    edge_type=EdgeType.CHECKPOINTED_AT,
                    sequence=edge_seq,
                ))
                edge_seq += 1
            last_node_id = node_id

        elif etype in (EventType.EXECUTION_COMPLETED, EventType.EXECUTION_FAILED, EventType.EXECUTION_CRASHED):
            # Terminal event — update duration only
            # failure_count is already incremented by STAGE_FAILED handler
            dur = payload.get("duration_ms", 0)
            if dur > 0:
                duration_ms = dur

    # Compute total duration from event timestamps if not set by payloads
    if duration_ms == 0 and len(events) >= 2:
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(events[0].timestamp)
            t1 = datetime.fromisoformat(events[-1].timestamp)
            duration_ms = int((t1 - t0).total_seconds() * 1000)
        except Exception:
            pass

    # Build sorted stage_order from observed stage events
    observed_order: list[str] = []
    seen = set()
    for event in events:
        sn = event.payload.get("stage_name", "")
        if sn and sn not in seen and event.event_type == EventType.STAGE_COMPLETED:
            observed_order.append(sn)
            seen.add(sn)

    final_stage_order = tuple(stage_order) if stage_order else tuple(observed_order)

    graph = RuntimeGraph(
        execution_id=eid,
        nodes=tuple(nodes),
        edges=tuple(edges),
        stage_order=final_stage_order,
        event_count=len(events),
        failure_count=failure_count,
        retry_count=retry_count,
        checkpoint_count=checkpoint_count,
        fork_count=fork_count,
        duration_ms=max(0, duration_ms),
        graph_hash="",
    )

    gh = _compute_graph_hash(graph)
    return RuntimeGraph(
        execution_id=graph.execution_id,
        nodes=graph.nodes,
        edges=graph.edges,
        stage_order=graph.stage_order,
        event_count=graph.event_count,
        failure_count=graph.failure_count,
        retry_count=graph.retry_count,
        checkpoint_count=graph.checkpoint_count,
        fork_count=graph.fork_count,
        duration_ms=graph.duration_ms,
        graph_hash=gh,
    )


# ═══════════════════════════════════════════════════════════════════════
# Graph Hash
# ═══════════════════════════════════════════════════════════════════════

def _compute_graph_hash(graph: RuntimeGraph) -> str:
    """Deterministic SHA-256 hash of graph structure."""
    parts = [
        graph.execution_id,
        "|".join(f"{n.node_id}:{n.node_type}:{n.label}:{n.sequence_start}:{n.sequence_end}:{n.status}" for n in graph.nodes),
        "|".join(f"{e.source}->{e.target}:{e.edge_type}:{e.sequence}" for e in graph.edges),
        "|".join(graph.stage_order),
        str(graph.event_count),
        str(graph.failure_count),
        str(graph.retry_count),
        str(graph.checkpoint_count),
        str(graph.fork_count),
        str(graph.duration_ms),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _empty_graph_hash() -> str:
    return hashlib.sha256(b"empty-graph").hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Query helpers
# ═══════════════════════════════════════════════════════════════════════

def get_nodes_by_type(graph: RuntimeGraph, node_type: str) -> Tuple[RuntimeNode, ...]:
    """Return all nodes of a given type."""
    return tuple(n for n in graph.nodes if n.node_type == node_type)


def get_edges_by_type(graph: RuntimeGraph, edge_type: str) -> Tuple[RuntimeEdge, ...]:
    """Return all edges of a given type."""
    return tuple(e for e in graph.edges if e.edge_type == edge_type)


def get_error_nodes(graph: RuntimeGraph) -> Tuple[RuntimeNode, ...]:
    """Return all error nodes."""
    return get_nodes_by_type(graph, NodeType.ERROR)


def is_deterministic(graph: RuntimeGraph) -> bool:
    """Check if graph is deterministic: no errors, no retries, no forks."""
    return (
        graph.failure_count == 0
        and graph.retry_count == 0
        and graph.fork_count == 0
    )
