"""Detect system bottlenecks: primary, orchestration, and system-critical nodes."""

from typing import Dict, List

from core.model import Bottleneck, FanInOut


def detect_bottlenecks(
    nodes: list,
    fan_stats: Dict[str, FanInOut],
    adjacency: Dict[str, List[str]],
) -> List[Bottleneck]:
    """Detect bottleneck nodes in the system.

    Bottleneck types:
      - primary: high fan-in + high criticality → depended on by many
      - orchestration: high fan-out → depends on many (coupling risk)
      - system_critical: entrypoint + high dependency load
    """
    bottlenecks: List[Bottleneck] = []

    # Build lookup
    criticality_map: Dict[str, float] = {}
    system_role_map: Dict[str, str] = {}
    impact_map: Dict[str, str] = {}
    for n in nodes:
        criticality_map[n["id"]] = n.get("criticality_score", 0.0)
        system_role_map[n["id"]] = n.get("system_role", "")
        impact_map[n["id"]] = n.get("impact_level", "")

    for n in nodes:
        nid = n["id"]
        fan = fan_stats.get(nid)
        if fan is None:
            continue

        criticality = criticality_map.get(nid, 0.0)
        system_role = system_role_map.get(nid, "")
        impact = impact_map.get(nid, "")

        # Primary bottleneck: high fan-in + shared_core + high/medium criticality
        if fan.fan_in >= 4 and system_role == "shared_core":
            severity = "critical" if criticality >= 0.7 else "high"
            bottlenecks.append(Bottleneck(
                node_id=nid,
                bottleneck_type="primary",
                severity=severity,
                reason=f"Shared core with {fan.fan_in} dependents; failure impacts many modules",
                fan_in=fan.fan_in,
                fan_out=fan.fan_out,
            ))

        # Orchestration bottleneck: high fan-out + orchestrator role
        elif fan.fan_out >= 4 and system_role == "orchestrator":
            bottlenecks.append(Bottleneck(
                node_id=nid,
                bottleneck_type="orchestration",
                severity="high",
                reason=f"Orchestrator depends on {fan.fan_out} modules; high coupling risk",
                fan_in=fan.fan_in,
                fan_out=fan.fan_out,
            ))

        # System critical: entrypoint or system_entry with heavy dependency load
        elif system_role == "system_entry" and fan.fan_out >= 3:
            bottlenecks.append(Bottleneck(
                node_id=nid,
                bottleneck_type="system_critical",
                severity="high" if impact == "high" else "medium",
                reason=f"System entry point with {fan.fan_out} direct dependencies; failure blocks entire system",
                fan_in=fan.fan_in,
                fan_out=fan.fan_out,
            ))

        # Medium severity: any node with fan_in >= 6 that isn't already caught
        elif fan.fan_in >= 6:
            bottlenecks.append(Bottleneck(
                node_id=nid,
                bottleneck_type="primary",
                severity="medium",
                reason=f"High fan-in ({fan.fan_in} dependents); consider interface abstraction",
                fan_in=fan.fan_in,
                fan_out=fan.fan_out,
            ))

    bottlenecks.sort(key=lambda b: {"critical": 0, "high": 1, "medium": 2}[b.severity])
    return bottlenecks
