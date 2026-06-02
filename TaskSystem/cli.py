"""
Task System CLI — command-line interface (v2.0).

Existing (13 commands, preserved):
  python cli.py new "title"
  python cli.py start TASK-001
  python cli.py done TASK-001
  python cli.py list backlog|active|done
  python cli.py show TASK-001
  python cli.py log TASK-001 "message"
  python cli.py focus TASK-001 "focus text"
  python cli.py suggest TASK-001 STEP-1
  python cli.py bind TASK-001 STEP-1 repo-analyzer
  python cli.py tag TASK-001 backend api
  python cli.py priority TASK-001 P0
  python cli.py query --status active
  python cli.py listx

New (v2.0):
  python cli.py add-step TASK-001 "content"
  python cli.py done-step TASK-001 1
  python cli.py list-steps TASK-001
  python cli.py history TASK-001
  python cli.py query --has-step  (or --no-step, --step-status todo)
"""

import argparse
import sys
from pathlib import Path

# Ensure core/ is importable from the TaskSystem root
_sys_root = Path(__file__).resolve().parent
if str(_sys_root) not in sys.path:
    sys.path.insert(0, str(_sys_root))

from TaskSystem.core.task_manager import (
    create_task, start_task, complete_task, list_tasks_by_status,
    add_context_log, set_current_focus, task_show,
    suggest_skills_for_step, bind_skill, load_task,
    set_tag, set_priority, query_tasks, list_tasks_enhanced,
    add_step, done_step, list_steps, get_history,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Existing commands (v1.0 — preserved)
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_new(args: argparse.Namespace) -> None:
    task = create_task(args.title)
    print(f"[created] {task['id']}  {task['title']}")


def cmd_start(args: argparse.Namespace) -> None:
    try:
        task = start_task(args.task_id)
        print(f"[started] {task['id']}  {task['title']}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_done(args: argparse.Namespace) -> None:
    try:
        task = complete_task(args.task_id)
        print(f"[done] {task['id']}  {task['title']}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    tasks = list_tasks_by_status(args.status)
    if not tasks:
        print(f"(empty)")
        return
    for t in tasks:
        print(f"[{t['status']}] {t['id']}  {t['title']}")


def cmd_show(args: argparse.Namespace) -> None:
    try:
        output = task_show(args.task_id)
        print(output)
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_log(args: argparse.Namespace) -> None:
    try:
        add_context_log(args.task_id, args.message)
        print(f"[logged] {args.task_id}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_focus(args: argparse.Namespace) -> None:
    try:
        task = set_current_focus(args.task_id, args.focus)
        print(f"[focus] {task['id']}  ->  {task['current_focus']}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)


def _parse_step_ref(step_ref: str) -> int:
    """Parse 'STEP-1' or '1' to integer step id."""
    raw = step_ref.upper().replace("STEP-", "").replace("STEP", "")
    if not raw.isdigit():
        raise ValueError(f"Invalid step reference: {step_ref!r}")
    return int(raw)


def cmd_suggest(args: argparse.Namespace) -> None:
    """Suggest skills for a task step using SkillSystem v4."""
    try:
        step_id = _parse_step_ref(args.step_ref)
        task = load_task(args.task_id)
        if task is None:
            print(f"Error: Task {args.task_id} not found")
            sys.exit(1)

        steps = task.get("steps", [])
        step = None
        for s in steps:
            if isinstance(s, dict) and s.get("id") == step_id:
                step = s
                break

        if step is None:
            print(f"Error: STEP-{step_id} not found in task {args.task_id}")
            sys.exit(1)

        content = step.get("content", "")
        skills = suggest_skills_for_step(content)
        if skills:
            print(f"Suggested skills for STEP-{step_id} ({content}):")
            for sk in skills:
                print(f"  - {sk}")
        else:
            print(f"No skill suggestions for STEP-{step_id} ({content})")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_bind(args: argparse.Namespace) -> None:
    try:
        step_id = _parse_step_ref(args.step_ref)
        task = bind_skill(args.task_id, step_id, args.skill)
        print(f"[bind] {task['id']} STEP-{step_id}  ->  {args.skill}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_tag(args: argparse.Namespace) -> None:
    try:
        task = set_tag(args.task_id, args.tags)
        tags_str = ", ".join(task["tags"]) if task["tags"] else "(none)"
        print(f"[tag] {task['id']}  {tags_str}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_priority(args: argparse.Namespace) -> None:
    try:
        task = set_priority(args.task_id, args.priority)
        print(f"[priority] {task['id']}  ->  {task['priority']}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_query(args: argparse.Namespace) -> None:
    """Query tasks by metadata. v2.0: added --has-step, --no-step, --step-status."""
    has_step = None
    if getattr(args, 'has_step', False):
        has_step = True
    elif getattr(args, 'no_step', False):
        has_step = False

    results = query_tasks(
        status=args.status,
        tag=args.tag,
        priority=args.priority,
        has_step=has_step,
        step_status=args.step_status,
    )
    if not results:
        print("(no matches)")
        return
    for t in results:
        tags = ", ".join(t.get("tags") or []) or "-"
        pri = t.get("priority", "P1")
        step_count = len(t.get("steps", []))
        print(f"[{t['status']}] {t['id']} | {t['title']} | {pri} | steps={step_count} | [{tags}]")


def cmd_listx(args: argparse.Namespace) -> None:
    tasks = list_tasks_enhanced()
    if not tasks:
        print("(no tasks)")
        return
    for t in tasks:
        tags = ", ".join(t.get("tags") or []) or "-"
        pri = t.get("priority", "P1")
        print(f"{t['id']} | {t['title']} | {t['status']} | {pri} | [{tags}]")


# ═══════════════════════════════════════════════════════════════════════════════
# New commands (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_add_step(args: argparse.Namespace) -> None:
    """Add a step to a task."""
    try:
        task = add_step(args.task_id, args.content)
        steps = task.get("steps", [])
        new_step = steps[-1] if steps else None
        sid = new_step.get("id", "?") if new_step else "?"
        print(f"[add-step] {task['id']} STEP-{sid}  {args.content}")
        if new_step and new_step.get("suggested_skills"):
            print(f"  suggested skills: {', '.join(new_step['suggested_skills'])}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_done_step(args: argparse.Namespace) -> None:
    """Mark a step as done."""
    try:
        step_id = _parse_step_ref(args.step_ref)
        task = done_step(args.task_id, step_id)
        print(f"[done-step] {task['id']} STEP-{step_id}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_list_steps(args: argparse.Namespace) -> None:
    """List all steps for a task."""
    try:
        steps = list_steps(args.task_id)
        if not steps:
            print("(no steps)")
            return
        for s in steps:
            if isinstance(s, dict):
                sid = s.get("id", "?")
                content = s.get("content", "")
                status = s.get("status", "todo")
                selected = s.get("selected_skill")
                icon = "[ok]" if status == "done" else "[  ]"
                skill_info = f" -> {selected}" if selected else ""
                print(f"{icon} STEP-{sid}: {content} ({status}){skill_info}")
            else:
                print(f"  - {s}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_history(args: argparse.Namespace) -> None:
    """Show task event log and status timeline."""
    try:
        info = get_history(args.task_id)
        print(f"Task: {info['task_id']} — {info['title']}")
        print()
        print("Status Timeline:")
        print("-----------------")
        for entry in info["timeline"]:
            print(f"  {entry['timestamp']}  [{entry['status']}]  {entry['event']}")
        print()
        print("Full Event Log:")
        print("---------------")
        if not info["event_log"]:
            print("  (empty)")
        else:
            for entry in info["event_log"]:
                print(f"  {entry}")
    except LookupError as e:
        print(f"Error: {e}")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(prog="task", description="Task System CLI v2.0")
    sub = parser.add_subparsers(dest="command", required=True)

    # ── Existing commands ────────────────────────────────────────────────

    p_new = sub.add_parser("new", help="Create a new task")
    p_new.add_argument("title", type=str, help="Task title")
    p_new.set_defaults(func=cmd_new)

    p_start = sub.add_parser("start", help="Start a task (backlog -> active)")
    p_start.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_start.set_defaults(func=cmd_start)

    p_done = sub.add_parser("done", help="Complete a task (active -> done)")
    p_done.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_done.set_defaults(func=cmd_done)

    p_list = sub.add_parser("list", help="List tasks by status")
    p_list.add_argument("status", type=str, choices=["backlog", "active", "done"],
                        help="Status to list")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Show task details and context")
    p_show.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_show.set_defaults(func=cmd_show)

    p_log = sub.add_parser("log", help="Append a context log entry to a task")
    p_log.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_log.add_argument("message", type=str, help="Log message")
    p_log.set_defaults(func=cmd_log)

    p_focus = sub.add_parser("focus", help="Set the current focus of a task")
    p_focus.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_focus.add_argument("focus", type=str, help="Current focus description")
    p_focus.set_defaults(func=cmd_focus)

    p_suggest = sub.add_parser("suggest", help="Suggest skills for a task step (SkillSystem v4)")
    p_suggest.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_suggest.add_argument("step_ref", type=str, help="Step reference (e.g. STEP-1)")
    p_suggest.set_defaults(func=cmd_suggest)

    p_bind = sub.add_parser("bind", help="Bind a skill to a task step")
    p_bind.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_bind.add_argument("step_ref", type=str, help="Step reference (e.g. STEP-1)")
    p_bind.add_argument("skill", type=str, help="Skill name to bind")
    p_bind.set_defaults(func=cmd_bind)

    p_tag = sub.add_parser("tag", help="Set tags for a task")
    p_tag.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_tag.add_argument("tags", type=str, nargs="+", help="Tags to set (space-separated)")
    p_tag.set_defaults(func=cmd_tag)

    p_priority = sub.add_parser("priority", help="Set priority for a task")
    p_priority.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_priority.add_argument("priority", type=str, choices=["P0", "P1", "P2"],
                            help="Priority level")
    p_priority.set_defaults(func=cmd_priority)

    p_query = sub.add_parser("query", help="Query tasks by metadata")
    p_query.add_argument("--status", type=str, choices=["backlog", "active", "done"],
                         default=None, help="Filter by status")
    p_query.add_argument("--tag", type=str, default=None, help="Filter by tag")
    p_query.add_argument("--priority", type=str, choices=["P0", "P1", "P2"],
                         default=None, help="Filter by priority")
    p_query.add_argument("--has-step", action="store_true", default=False,
                         help="Filter tasks that have steps")
    p_query.add_argument("--no-step", action="store_true", default=False,
                         help="Filter tasks that have no steps")
    p_query.add_argument("--step-status", type=str, choices=["todo", "done"],
                         default=None, help="Filter tasks with steps in given status")
    p_query.set_defaults(func=cmd_query)

    p_listx = sub.add_parser("listx", help="List all tasks with metadata, sorted")
    p_listx.set_defaults(func=cmd_listx)

    # ── New v2.0 commands ─────────────────────────────────────────────────

    p_add_step = sub.add_parser("add-step", help="Add a step to a task")
    p_add_step.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_add_step.add_argument("content", type=str, help="Step content description")
    p_add_step.set_defaults(func=cmd_add_step)

    p_done_step = sub.add_parser("done-step", help="Mark a step as done")
    p_done_step.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_done_step.add_argument("step_ref", type=str, help="Step reference (e.g. 1 or STEP-1)")
    p_done_step.set_defaults(func=cmd_done_step)

    p_list_steps = sub.add_parser("list-steps", help="List all steps for a task")
    p_list_steps.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_list_steps.set_defaults(func=cmd_list_steps)

    p_history = sub.add_parser("history", help="Show task event log and status timeline")
    p_history.add_argument("task_id", type=str, help="Task ID (e.g. TASK-001)")
    p_history.set_defaults(func=cmd_history)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
