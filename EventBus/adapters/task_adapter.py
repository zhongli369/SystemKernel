"""
task_adapter.py — Event → TaskSystem Bridge (v1.0)

The ONLY connection point between EventBus and TaskSystem.

Pure translation layer:
  RoutingDecision → TaskSystem function call

NO logic beyond field mapping.
NO skill routing (TaskSystem does NOT route skills here).
NO content analysis.
NO LLM calls.
"""

from typing import Optional
from EventBus.event_router import RoutingDecision


# ═══════════════════════════════════════════════════════════════════════════════
# Translation table: RoutingDecision.action → TaskSystem function
# ═══════════════════════════════════════════════════════════════════════════════

def dispatch(decision: RoutingDecision) -> Optional[str]:
    """Translate a RoutingDecision into a TaskSystem operation.

    The ONLY function that calls TaskSystem from EventBus.
    Pure translation — no logic, no routing, no AI.

    Args:
        decision: RoutingDecision from event_router.route().

    Returns:
        Task ID string if a task was created/modified, None otherwise.

    Raises:
        ImportError: If TaskSystem is not importable (will happen if
                     workspace root is not on sys.path).
    """
    if decision.action == "skip":
        return None

    # Lazy import — TaskSystem is a sibling workspace, not a package dependency
    try:
        from TaskSystem.core.task_manager import create_task, start_task, complete_task
    except ImportError:
        # Bootstrap: ensure workspace root is importable
        import sys
        from pathlib import Path
        workspace_root = str(Path(__file__).resolve().parent.parent)
        if workspace_root not in sys.path:
            sys.path.insert(0, workspace_root)
        from TaskSystem.core.task_manager import create_task, start_task, complete_task

    task_id = None

    if decision.action == "create_task":
        # Create task with title and priority from routing decision
        task = create_task(decision.title)

        # Set priority if not default
        if decision.priority != "P1":
            try:
                from TaskSystem.core.task_manager import set_priority
                set_priority(task["id"], decision.priority)
            except ImportError:
                pass

        # Add metadata as context log entry
        try:
            from TaskSystem.core.task_manager import add_context_log
            metadata_str = (
                f"EventBus | source={decision.metadata.get('source', '?')} | "
                f"event_type={decision.metadata.get('event_type', '?')} | "
                f"event_id={decision.event_id[:12]}..."
            )
            add_context_log(task["id"], metadata_str)
        except ImportError:
            pass

        task_id = task["id"]

    elif decision.action == "start_task":
        # Extract task_id from metadata if provided
        tid = decision.metadata.get("task_id")
        if tid:
            start_task(tid)
            task_id = tid

    elif decision.action == "complete_task":
        tid = decision.metadata.get("task_id")
        if tid:
            complete_task(tid)
            task_id = tid

    return task_id
