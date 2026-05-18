"""Classify nodes into architecture layers for system structure understanding."""

from typing import Dict, List
from collections import defaultdict

from core.model import ArchitectureLayers

# Mapping from system_role → architecture layer
ROLE_TO_LAYER: Dict[str, str] = {
    "system_entry": "entry",
    "orchestrator": "orchestration",
    "shared_core": "core",
    "business_core": "core",
    "data_layer": "core",
    "support_module": "utility",
    "infrastructure": "utility",
    "leaf_module": "leaf",
    "isolated": "leaf",
}


def classify_layers(nodes: list) -> ArchitectureLayers:
    """Classify nodes into architecture layers based on system_role."""
    layers: Dict[str, List[str]] = defaultdict(list)

    for n in nodes:
        system_role = n.get("system_role", "")
        layer = ROLE_TO_LAYER.get(system_role, "leaf")
        layers[layer].append(n["id"])

    # Sort nodes within each layer by criticality (descending)
    crit_lookup = {n["id"]: n.get("criticality_score", 0.0) for n in nodes}
    for layer in layers:
        layers[layer].sort(key=lambda nid: -crit_lookup.get(nid, 0.0))

    return ArchitectureLayers(
        entry_layer=layers.get("entry", []),
        orchestration_layer=layers.get("orchestration", []),
        core_layer=layers.get("core", []),
        utility_layer=layers.get("utility", []),
        leaf_layer=layers.get("leaf", []),
    )
