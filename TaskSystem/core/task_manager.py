"""
Task Manager — business logic layer (v2.0).
Only calls task_store, never touches filesystem directly.

v2.0 enhancements:
  - State transition validation (validate_transition)
  - New fields: updated_at, started_at, completed_at, event_log
  - Step execution: add_step, done_step, list_steps
  - SkillSystem v4 integration (no local keyword matching)
  - Mutation history with event_log
  - Enhanced query: has_step, step_status filters
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from core.task_store import save_task, load_task, move_task, list_tasks, next_task_id

# Ensure SkillsManagementSystem is importable from sibling workspace
_WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

try:
    from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest
except ImportError:
    resolve = None
    CapabilityRequest = None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ═══════════════════════════════════════════════════════════════════════════════
# State transition validation (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════

_VALID_TRANSITIONS = {
    ("backlog", "active"): True,
    ("active", "done"): True,
    # Allow re-activation from done (edge case: reopen completed task)
    ("done", "active"): True,
}


def validate_transition(old_status: str, new_status: str) -> bool:
    """Check if a status transition is valid.

    Allowed transitions:
      backlog → active  (start)
      active  → done    (complete)
      done    → active  (reopen)

    Returns True if valid, False otherwise.
    """
    return _VALID_TRANSITIONS.get((old_status, new_status), False)


# ═══════════════════════════════════════════════════════════════════════════════
# Event log helper (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════

def _append_event(task: dict, action: str) -> None:
    """Append a timestamped event to task.event_log and touch updated_at."""
    task.setdefault("event_log", [])
    task["event_log"].append(f"{_now()} | {action}")
    task["updated_at"] = _now()


def _touch(task: dict) -> None:
    """Update the updated_at timestamp on a task."""
    task["updated_at"] = _now()


# ═══════════════════════════════════════════════════════════════════════════════
# Skill suggestion — delegates to SkillSystem v4 (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════

def suggest_skills_for_step(step_content: str) -> list[str]:
    """Suggest skill names for a step via unified Adapter.

    Delegates to SkillsManagementSystem.core.adapter.resolve().
    No local keyword matching — all routing logic lives in SkillSystem.

    Returns list of skill names (top match + alternatives).
    """
    if not step_content:
        return []

    try:
        if resolve is None:
            return []
        binding = resolve(CapabilityRequest(intent="", context=step_content))
        if not binding.skill_id:
            return []

        skills: list[str] = [binding.skill_id]
        for alt in binding.alternatives:
            if alt and alt not in skills:
                skills.append(alt)
        return skills
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Task CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def create_task(title: str) -> dict:
    """Create a new task with auto-generated ID, placed in backlog."""
    task_id = next_task_id()
    now = _now()
    task = {
        "id": task_id,
        "title": title,
        "status": "backlog",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "steps": [],
        "notes": "",
        "context_log": [],
        "event_log": [f"{now} | CREATE_TASK"],
        "current_focus": "",
        "tags": [],
        "priority": "P1",
    }
    save_task(task, "backlog")
    return task


def start_task(task_id: str) -> dict:
    """Move a task from backlog to active. Sets started_at on first activation."""
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    current_status = task["status"]
    new_status = "active"

    if current_status == "active":
        raise ValueError(f"Task {task_id} is already active")

    if not validate_transition(current_status, new_status):
        hint = ""
        if current_status == "done":
            hint = " — task was already completed, use start to reopen"
        else:
            hint = f" — unexpected status '{current_status}'"
        raise ValueError(
            f"Cannot transition '{current_status}' → '{new_status}' "
            f"for task {task_id}{hint}"
        )

    # Set started_at only on first activation (preserve original start time)
    if task.get("started_at") is None:
        task["started_at"] = _now()

    _append_event(task, "START_TASK")

    if current_status == new_status:
        save_task(task, current_status)
        return task

    return move_task(task_id, current_status, new_status, task=task)


def complete_task(task_id: str) -> dict:
    """Move a task from active to done. Sets completed_at."""
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    current_status = task["status"]
    new_status = "done"

    if current_status == "done":
        raise ValueError(f"Task {task_id} is already done")
    if current_status == "backlog":
        raise ValueError(f"Task {task_id} is still in backlog — start it first")

    if not validate_transition(current_status, new_status):
        raise ValueError(
            f"Cannot transition '{current_status}' → '{new_status}' "
            f"for task {task_id} — unexpected state"
        )

    task["completed_at"] = _now()
    _append_event(task, "COMPLETE_TASK")

    return move_task(task_id, current_status, new_status, task=task)


# ═══════════════════════════════════════════════════════════════════════════════
# Context & focus
# ═══════════════════════════════════════════════════════════════════════════════

def add_context_log(task_id: str, message: str) -> dict:
    """Append a timestamped entry to task.context_log."""
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    entry = f"{_now()} | {message}"
    task.setdefault("context_log", [])
    task["context_log"].append(entry)
    _append_event(task, f"LOG: {message[:80]}")
    save_task(task, task["status"])
    return task


def set_current_focus(task_id: str, focus: str) -> dict:
    """Set task.current_focus to mark the current execution point."""
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    task["current_focus"] = focus
    _append_event(task, f"FOCUS: {focus[:80]}")
    save_task(task, task["status"])
    return task


# ═══════════════════════════════════════════════════════════════════════════════
# Step operations (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════

def _step_by_id(steps: list, step_id: int) -> dict | None:
    """Find a step dict by its id field. Returns None if not found or steps are strings."""
    for s in steps:
        if isinstance(s, dict) and s.get("id") == step_id:
            return s
    return None


def _next_step_id(steps: list) -> int:
    """Find the next available step id."""
    max_id = 0
    for s in steps:
        if isinstance(s, dict):
            sid = s.get("id", 0)
            if isinstance(sid, int) and sid > max_id:
                max_id = sid
    return max_id + 1


def add_step(task_id: str, content: str) -> dict:
    """Add a new step to a task.

    v2.0: Steps are always object form with full metadata.
    """
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    step_id = _next_step_id(task.get("steps", []))
    now = _now()

    step = {
        "id": step_id,
        "content": content,
        "status": "todo",
        "created_at": now,
        "completed_at": None,
        "suggested_skills": [],
        "selected_skill": None,
    }

    # Auto-suggest skills from SkillSystem v4
    suggestions = suggest_skills_for_step(content)
    if suggestions:
        step["suggested_skills"] = suggestions

    task.setdefault("steps", [])
    task["steps"].append(step)
    _append_event(task, f"ADD_STEP:{step_id}")
    save_task(task, task["status"])
    return task


def done_step(task_id: str, step_id: int) -> dict:
    """Mark a step as done.

    v2.0: todo → done only. Does not support undo.
    """
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    step = _step_by_id(task.get("steps", []), step_id)
    if step is None:
        raise LookupError(f"Step {step_id} not found in task {task_id}")

    if step.get("status") == "done":
        raise ValueError(f"Step {step_id} is already done")

    step["status"] = "done"
    step["completed_at"] = _now()
    _append_event(task, f"DONE_STEP:{step_id}")
    save_task(task, task["status"])
    return task


def list_steps(task_id: str) -> list[dict]:
    """List all steps for a task."""
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    return task.get("steps", [])


# ═══════════════════════════════════════════════════════════════════════════════
# History & traceability (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════

def get_history(task_id: str) -> dict:
    """Return task event_log and derived status timeline.

    Returns dict with:
      - event_log: raw event entries
      - timeline: derived status transitions with timestamps
    """
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    event_log = task.get("event_log", [])

    # Derive status timeline from event_log
    timeline: list[dict] = []
    timeline.append({
        "timestamp": task.get("created_at", "?"),
        "status": "backlog",
        "event": "CREATE_TASK",
    })

    for entry in event_log:
        ts = entry[:20] if len(entry) >= 20 else entry
        if "START_TASK" in entry:
            timeline.append({"timestamp": ts, "status": "active", "event": "START_TASK"})
        elif "COMPLETE_TASK" in entry:
            timeline.append({"timestamp": ts, "status": "done", "event": "COMPLETE_TASK"})

    # Current status
    timeline.append({
        "timestamp": task.get("updated_at", "?"),
        "status": task.get("status", "?"),
        "event": "(current)",
    })

    return {
        "task_id": task_id,
        "title": task.get("title", ""),
        "event_log": event_log,
        "timeline": timeline,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Skill binding
# ═══════════════════════════════════════════════════════════════════════════════

def bind_skill(task_id: str, step_id: int, skill_name: str) -> dict:
    """Bind a skill to a specific step within a task."""
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    steps = task.get("steps", [])
    step = _step_by_id(steps, step_id)
    if step is None:
        raise LookupError(f"Step {step_id} not found in task {task_id}")

    step["selected_skill"] = skill_name
    _append_event(task, f"BIND_SKILL:{step_id}:{skill_name}")
    save_task(task, task["status"])
    return task


# ═══════════════════════════════════════════════════════════════════════════════
# Tags & priority
# ═══════════════════════════════════════════════════════════════════════════════

def set_tag(task_id: str, tags: list[str]) -> dict:
    """Set tags for a task (replaces existing tags)."""
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    task["tags"] = tags
    _append_event(task, f"TAG: {', '.join(tags) if tags else '(none)'}")
    save_task(task, task["status"])
    return task


def set_priority(task_id: str, priority: str) -> dict:
    """Set priority for a task. Valid: P0, P1, P2."""
    if priority not in ("P0", "P1", "P2"):
        raise ValueError(f"Invalid priority: {priority!r}. Must be P0, P1, or P2.")

    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    task["priority"] = priority
    _append_event(task, f"PRIORITY: {priority}")
    save_task(task, task["status"])
    return task


# ═══════════════════════════════════════════════════════════════════════════════
# Display helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _step_text(s) -> str:
    """Extract display text from a step, whether string or dict."""
    if isinstance(s, dict):
        return s.get("content", "").strip()
    return s.lstrip("✔ ").strip()


def _step_is_done(s) -> bool:
    """Check if a step is marked done."""
    if isinstance(s, dict):
        return s.get("status") == "done"
    return s.startswith("✔ ")


def _step_is_doing(s, focus: str) -> bool:
    """Check if a step is currently in focus."""
    text = _step_text(s)
    return bool(focus and focus in text)


def task_show(task_id: str) -> str:
    """Return a structured, human-readable view of a task (v2.0)."""
    task = load_task(task_id)
    if task is None:
        raise LookupError(f"Task {task_id} not found")

    lines = []
    sep = "---------------------------------"
    focus = task.get("current_focus", "")

    # Header
    tags = task.get("tags") or []
    priority = task.get("priority", "P1")
    started = task.get("started_at") or "-"
    completed = task.get("completed_at") or "-"

    lines.append(sep)
    lines.append(f"TASK ID:    {task['id']}")
    lines.append(f"TITLE:      {task['title']}")
    lines.append(f"STATUS:     {task['status']}")
    lines.append(f"PRIORITY:   {priority}")
    lines.append(f"TAGS:       {', '.join(tags) if tags else '(none)'}")
    lines.append(f"CREATED:    {task.get('created_at', '-')}")
    lines.append(f"STARTED:    {started}")
    lines.append(f"COMPLETED:  {completed}")
    lines.append(f"UPDATED:    {task.get('updated_at', '-')}")
    lines.append(sep)

    # Current focus
    lines.append("")
    lines.append("CURRENT FOCUS:")
    lines.append(f"  -> {focus}" if focus else "  (not set)")

    # Steps
    steps = task.get("steps", [])
    lines.append("")
    if not steps:
        lines.append("STEPS:")
        lines.append("  (none)")
    elif isinstance(steps[0], str):
        # Phase 2 compat — plain string steps
        lines.append("STEPS:")
        for s in steps:
            text = s.lstrip("✔ ").strip()
            if s.startswith("✔ "):
                lines.append(f"  [ok] {text}")
            elif _step_is_doing(s, focus):
                lines.append(f"  [>>] {text}")
            else:
                lines.append(f"  [  ] {text}")
    else:
        # v2.0 — object steps with full metadata
        lines.append("STEP BREAKDOWN:")
        lines.append(sep)
        for s in steps:
            sid = s.get("id", "?")
            content = s.get("content", "")
            status = s.get("status", "todo")
            suggested = s.get("suggested_skills", [])
            selected = s.get("selected_skill")
            step_created = s.get("created_at", "-")
            step_done = s.get("completed_at")

            # Status icon
            if status == "done":
                icon = "[ok]"
            elif _step_is_doing(s, focus):
                icon = "[>>]"
            else:
                icon = "[  ]"

            done_info = f" done={step_done}" if step_done else ""
            lines.append(f"{icon} STEP-{sid}: {content} ({status}; created={step_created}{done_info})")
            if suggested:
                lines.append(f"    suggested: {', '.join(suggested)}")
            if selected:
                lines.append(f"    selected: {selected}")
            else:
                lines.append(f"    selected: none")
            lines.append("")

    # Event log (last 5 entries)
    event_log = task.get("event_log", [])
    lines.append("EVENT LOG (recent):")
    if not event_log:
        lines.append("  (empty)")
    else:
        for entry in event_log[-5:]:
            lines.append(f"  - {entry}")

    # Context log
    lines.append("")
    lines.append("CONTEXT LOG:")
    c_log = task.get("context_log", [])
    if not c_log:
        lines.append("  (empty)")
    else:
        for entry in c_log:
            lines.append(f"  - {entry}")

    # Next suggestion
    lines.append("")
    lines.append("NEXT SUGGESTION:")
    if task["status"] == "done":
        lines.append("  -> Task is complete. No further action.")
    elif not steps:
        lines.append("  -> Add steps, then run: cli.py start {task_id}")
    elif task["status"] == "backlog":
        lines.append("  -> Task is in backlog. Run: cli.py start {task_id}")
    elif focus:
        found = False
        for i, s in enumerate(steps):
            if _step_is_doing(s, focus):
                found = True
                if i + 1 < len(steps):
                    next_text = _step_text(steps[i + 1])
                    lines.append(f"  -> Continue with: {next_text}")
                else:
                    lines.append("  -> All steps addressed. Run: cli.py done {task_id}")
                break
        if not found:
            lines.append("  -> Current focus not in steps. Update focus or add steps.")
    else:
        lines.append("  -> Set current_focus to mark your position.")

    lines.append(sep)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Querying (v2.0 enhanced)
# ═══════════════════════════════════════════════════════════════════════════════

def _all_tasks() -> list[dict]:
    """Collect all tasks from all status directories."""
    tasks: list[dict] = []
    for status in ("backlog", "active", "done"):
        tasks.extend(list_tasks(status))
    return tasks


def query_tasks(status: str | None = None,
                tag: str | None = None,
                priority: str | None = None,
                has_step: bool | None = None,
                step_status: str | None = None) -> list[dict]:
    """Filter tasks by status, tag, priority, step presence, and step status.

    v2.0: Added has_step and step_status filters.
    Scans task files directly — O(n tasks), no index.
    """
    tasks = _all_tasks()

    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if tag:
        tasks = [t for t in tasks if tag in (t.get("tags") or [])]
    if priority:
        tasks = [t for t in tasks if t.get("priority") == priority]
    if has_step is True:
        tasks = [t for t in tasks if len(t.get("steps", [])) > 0]
    elif has_step is False:
        tasks = [t for t in tasks if len(t.get("steps", [])) == 0]
    if step_status:
        tasks = [t for t in tasks if any(
            isinstance(s, dict) and s.get("status") == step_status
            for s in t.get("steps", [])
        )]

    return tasks


def _sort_key(task: dict) -> tuple[int, int, str]:
    """Sort key: priority (P0 first) → status (active first) → created_at (new first)."""
    p_order = {"P0": 0, "P1": 1, "P2": 2}
    s_order = {"active": 0, "backlog": 1, "done": 2}

    p_val = p_order.get(task.get("priority", "P1"), 1)
    s_val = s_order.get(task.get("status", "backlog"), 1)
    created = task.get("created_at", "")

    return (p_val, s_val, created)


def list_tasks_enhanced() -> list[dict]:
    """Return all tasks sorted by priority → status → created_at."""
    tasks = _all_tasks()
    tasks.sort(key=_sort_key)
    return tasks


def list_tasks_by_status(status: str) -> list[dict]:
    """List tasks in the given status."""
    if status not in ("backlog", "active", "done"):
        raise ValueError(f"Unknown status: {status!r}")
    return list_tasks(status)
