"""Classify node impact_level (low / medium / high) from criticality_score."""


def compute_impact_level(
    criticality_score: float,
    is_entrypoint: bool,
    is_isolated: bool,
) -> str:
    """Determine impact level for a node.

    Rules:
      - isolated → low
      - entrypoint → at least medium
      - criticality > 0.7 → high
      - criticality 0.4–0.7 → medium
      - criticality < 0.4 → low
    """
    if is_isolated:
        return "low"

    if is_entrypoint and criticality_score < 0.4:
        return "medium"

    if criticality_score > 0.7:
        return "high"
    elif criticality_score >= 0.4:
        return "medium"
    else:
        return "low"
