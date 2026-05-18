"""Upgrade file-level role to system-level role based on connectivity and metadata."""

from typing import Dict

from core.model import FanInOut

# Threshold for "high connectivity"
HIGH_FAN_IN = 4
HIGH_FAN_OUT = 4
LOW_CONNECTIVITY = 1  # total (fan_in + fan_out) ≤ this = low


def classify_system_role(
    node_id: str,
    file_role: str,
    is_entrypoint: bool,
    fan_stats: Dict[str, FanInOut],
    isolated_nodes: list,
) -> str:
    """Classify the system-level role of a node.

    System roles:
      - system_entry: entry point to the system
      - shared_core: heavily depended upon by many others
      - orchestrator: depends on many others, coordinates
      - business_core: core service/logic
      - data_layer: models, schemas, entities
      - infrastructure: configuration and settings
      - support_module: utilities and helpers
      - leaf_module: low-connectivity leaf
      - isolated: no connections at all
    """
    if node_id in (isolated_nodes or []):
        return "isolated"

    fan = fan_stats.get(node_id)
    fan_in = fan.fan_in if fan else 0
    fan_out = fan.fan_out if fan else 0
    total = fan_in + fan_out

    # Entrypoint → system_entry
    if is_entrypoint or file_role == "entrypoint":
        return "system_entry"

    # High fan-in → shared_core (many depend on this)
    if fan_in >= HIGH_FAN_IN:
        return "shared_core"

    # High fan-out → orchestrator (this depends on many)
    if fan_out >= HIGH_FAN_OUT:
        return "orchestrator"

    # Low total connectivity → leaf_module
    if total <= LOW_CONNECTIVITY:
        return "leaf_module"

    # Role-based mappings
    role_map = {
        "service": "business_core",
        "interface": "business_core",
        "data": "data_layer",
        "model": "data_layer",
        "config": "infrastructure",
        "script": "support_module",
        "component": "business_core",
        "utility": "support_module",
        "test": "support_module",
        "docs": "leaf_module",
        "asset": "leaf_module",
    }
    return role_map.get(file_role, "support_module")
