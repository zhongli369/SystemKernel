"""Global Task ID: deterministic cross-system identity overlay.

Internal identity:  TASK-B001  (RepoAnalyzer internal)
External identity:  RA::RepoAnalyzer::TASK-B001

This is NOT a new ID system — it is a naming overlay only.
No behavioral changes. No structural changes.
"""


def build_global_task_id(repo_name: str, task_id: str) -> str:
    """Map internal task_id to cross-system global_task_id.

    Example:
        build_global_task_id("RepoAnalyzer", "TASK-B001")
        → "RA::RepoAnalyzer::TASK-B001"
    """
    return f"RA::{repo_name}::{task_id}"


def parse_global_task_id(global_id: str) -> dict:
    """Parse a global task ID back into its components.

    Example:
        parse_global_task_id("RA::RepoAnalyzer::TASK-B001")
        → {"system": "RA", "repo": "RepoAnalyzer", "task_id": "TASK-B001"}
    """
    parts = global_id.split("::")
    return {
        "system": parts[0],
        "repo": parts[1],
        "task_id": parts[2],
    }
