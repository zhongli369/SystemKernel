"""Infer dependency_type for edges based on source and target system roles."""

from typing import Dict


def infer_dependency_type(
    source_role: str,
    target_role: str,
    source_system_role: str,
    target_system_role: str,
) -> str:
    """Infer the semantic meaning of a dependency edge.

    Returns one of:
      - orchestration_dependency: entrypoint/system_entry → anything
      - data_dependency: business_core/service → data_layer/model
      - control_flow_dependency: interface/controller → service/business_core
      - shared_dependency: anything → utility/support_module
      - config_dependency: anything → config/infrastructure
      - core_dependency: internal core module → core module
      - leaf_dependency: leaf → leaf or support
      - generic_dependency: fallback
    """
    # Entrypoint → anything = orchestration
    if source_role in ("entrypoint",) or source_system_role in ("system_entry",):
        return "orchestration_dependency"

    # Anything → config/infrastructure = config_dependency
    if target_role in ("config",) or target_system_role in ("infrastructure",):
        return "config_dependency"

    # Service/business_core → data_layer/model = data_dependency
    if source_role in ("service", "interface") or source_system_role in ("business_core",):
        if target_role in ("data",) or target_system_role in ("data_layer",):
            return "data_dependency"

    # Interface/controller → service = control_flow
    if source_role in ("interface",) or source_system_role in ("business_core",):
        if target_role in ("service",) or target_system_role in ("business_core",):
            return "control_flow_dependency"

    # Anything → utility/support = shared_dependency
    if target_role in ("utility",) or target_system_role in ("support_module",):
        return "shared_dependency"

    # Internal core → core
    if source_system_role in ("shared_core", "orchestrator", "business_core", "data_layer"):
        if target_system_role in ("shared_core", "orchestrator", "business_core", "data_layer"):
            return "core_dependency"

    # Leaf → leaf or support
    if source_system_role in ("leaf_module",):
        return "leaf_dependency"

    return "generic_dependency"


def infer_all_edge_types(
    edges: list,
    node_system_roles: Dict[str, str],
    node_roles: Dict[str, str],
) -> list:
    """Assign dependency_type to every edge.

    Args:
        edges: list of DependencyEdge objects
        node_system_roles: node_id → system_role
        node_roles: node_id → file_role

    Returns a list of (source, target, dependency_type).
    """
    result = []
    for edge in edges:
        src_role = node_roles.get(edge.source, "")
        tgt_role = node_roles.get(edge.target, "")
        src_sys = node_system_roles.get(edge.source, "")
        tgt_sys = node_system_roles.get(edge.target, "")

        dep_type = infer_dependency_type(src_role, tgt_role, src_sys, tgt_sys)
        result.append((edge.source, edge.target, dep_type))
    return result
