"""Generate system health report: overall score, risk level, fragile modules, refactor candidates."""

from typing import Dict, List

from core.model import SystemHealth, FanInOut


def generate_health_report(
    nodes: list,
    bottlenecks: list,
    coupling_metrics,
) -> SystemHealth:
    """Compute system health metrics and generate a structured report.

    overall_score aggregates:
      - avg_criticality (higher is better — well-structured code)
      - bottleneck_penalty (fewer bottlenecks is better)
      - coupling_penalty (lower coupling is better)
      - isolation_penalty (isolated nodes are bad)
    """
    n = len(nodes) if nodes else 1

    # 1. Average criticality contribution
    avg_criticality = sum(nn.get("criticality_score", 0.0) for nn in nodes) / n

    # 2. Bottleneck penalty (scaled by project size)
    critical_bottlenecks = sum(1 for b in bottlenecks if b.severity == "critical")
    high_bottlenecks = sum(1 for b in bottlenecks if b.severity == "high")
    # Normalize: fewer nodes → higher per-bottleneck weight
    nodes_per_bottleneck = max(n, 1) / max(critical_bottlenecks + high_bottlenecks, 1)
    scale = max(0.4, min(1.0, 1.0 / max(nodes_per_bottleneck / 10, 0.5)))

    bottleneck_penalty = 0.0
    if critical_bottlenecks > 0:
        bottleneck_penalty += min(critical_bottlenecks * 0.15 * scale, 0.4)
    if high_bottlenecks > 0:
        bottleneck_penalty += min(high_bottlenecks * 0.06 * scale, 0.25)

    # 3. Coupling penalty
    coupling_penalty = min(coupling_metrics.avg_coupling_score * 0.3, 0.3)

    # 4. Isolation penalty
    isolated_count = sum(1 for nn in nodes if nn.get("system_role") == "isolated")
    isolation_penalty = min(isolated_count / max(n, 1) * 0.2, 0.2)

    # Overall health score (1.0 = perfect, 0.0 = terrible)
    overall = 1.0 - bottleneck_penalty - coupling_penalty - isolation_penalty
    overall = max(0.0, min(overall, 1.0))

    # Risk level
    if overall >= 0.75:
        risk = "low"
    elif overall >= 0.45:
        risk = "medium"
    else:
        risk = "high"

    # Fragile modules: low impact but isolated, or high coupling + low criticality
    fragile = []
    for nn in nodes:
        nid = nn["id"]
        sys_role = nn.get("system_role", "")
        impact = nn.get("impact_level", "")

        if sys_role == "isolated":
            fragile.append(nid)
        elif impact == "low" and nid in coupling_metrics.high_coupling_nodes:
            fragile.append(nid)

    # Refactor candidates: high-coupling nodes with medium+ impact
    refactor = []
    for nn in nodes:
        nid = nn["id"]
        impact = nn.get("impact_level", "")
        if impact in ("high", "medium") and nid in coupling_metrics.high_coupling_nodes:
            refactor.append(nid)

    refactor.sort(key=lambda nid: -next(
        (nn.get("criticality_score", 0.0) for nn in nodes if nn["id"] == nid), 0.0
    ))

    return SystemHealth(
        overall_score=round(overall, 3),
        risk_level=risk,
        fragile_modules=sorted(fragile),
        refactor_candidates=refactor,
    )
