"""Standardized output contract for all RepoAnalyzer pipeline phases.

Every pipeline output follows a uniform envelope:

    {
      "schema_version": "repoanalyzer.v1",
      "repo_id": "<repo name>",
      "phase": "<scan|enrich|graph|analyze|interpret|insights|plan>",
      "generated_at": "<ISO8601>",
      "data": { ... original output ... }
    }

Optional fields (not validated or enforced by the contract):
  - global_task_id: RA::<repo>::<task_id> cross-system identity overlay
  - skill_id: resolved SkillSystem v4 skill identifier
  - skill_input: prepared skill input schema
  - skill_output: skill binding/execution result

Architecture Constraint Layer:
  - REPOANALYZER_ARCHITECTURE_GUARD=soft|strict|off gates validation
  - Validation reports are read-only — they never modify pipeline data
  - Baseline for drift detection: .repoanalyzer_baseline.json

Usage:
    from core.output_contract import wrap_output, unwrap_output

    # Writing
    wrapped = wrap_output("MyRepo", "graph", graph_dict)
    json.dump(wrapped, f, ...)

    # Reading (handles old unwrapped files transparently)
    raw = json.load(f)
    data = unwrap_output(raw)
"""

from core.time_utils import current_utc_iso8601


def wrap_output(repo_id: str, phase: str, data: dict) -> dict:
    """Wrap pipeline output in the standard envelope contract.

    Args:
        repo_id: Repository name (from os.path.basename).
        phase: One of scan, enrich, graph, analyze, interpret, insights, plan.
        data: The original pipeline output dict.

    Returns:
        Envelope dict with schema_version, repo_id, phase, generated_at, data.
    """
    return {
        "schema_version": "repoanalyzer.v1",
        "repo_id": repo_id,
        "phase": phase,
        "generated_at": current_utc_iso8601(),
        "data": data,
    }


def unwrap_output(raw: dict) -> dict:
    """Extract data payload from a potentially wrapped output.

    Handles both wrapped (v1 contract) and unwrapped (legacy) formats:
      - If 'schema_version' and 'data' keys present → return raw['data']
      - Otherwise → return raw unchanged (old format)

    This ensures backward compatibility: old output files without the
    envelope are still readable without migration.
    """
    if isinstance(raw, dict) and "schema_version" in raw and "data" in raw:
        return raw["data"]
    return raw
