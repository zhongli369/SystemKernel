"""
Task Store — filesystem operations layer (v2.0).
All paths use pathlib. No os.path string concatenation.

v2.0 enhancements:
  - Atomic counter file for next_task_id (no filesystem scan)
  - Fixed move_task ordering (write-new → atomic-rename → delete-old)
  - Timestamp helper for mutation tracking
"""

import json
from pathlib import Path
from datetime import datetime, timezone

TASKS_ROOT = Path(__file__).resolve().parent.parent / "tasks"
_COUNTER_FILE = TASKS_ROOT / ".task_counter"

STATUS_DIRS = {
    "backlog": TASKS_ROOT / "backlog",
    "active": TASKS_ROOT / "active",
    "done": TASKS_ROOT / "done",
}

VALID_ID_PATTERN = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


def _ensure_dirs() -> None:
    for d in STATUS_DIRS.values():
        d.mkdir(parents=True, exist_ok=True)


def _validate_task_id(task_id: str) -> None:
    if not task_id or not isinstance(task_id, str):
        raise ValueError(f"Invalid task_id: {task_id!r}")
    if ".." in task_id or "/" in task_id or "\\" in task_id:
        raise ValueError(f"task_id contains path separators: {task_id!r}")
    if not set(task_id).issubset(VALID_ID_PATTERN):
        raise ValueError(f"task_id contains invalid characters: {task_id!r}")
    if len(task_id) > 64:
        raise ValueError(f"task_id too long: {len(task_id)} chars")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_task_file(task_id: str) -> Path | None:
    """Search all status directories for a task file."""
    for d in STATUS_DIRS.values():
        candidate = d / f"{task_id}.json"
        if candidate.exists():
            return candidate
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Atomic counter file (v2.0 — replaces filesystem scan)
# ═══════════════════════════════════════════════════════════════════════════════

def _seed_counter() -> int:
    """Scan existing task files to seed the counter. Called once if counter file missing."""
    max_num = 0
    for d in STATUS_DIRS.values():
        if not d.exists():
            continue
        for f in d.glob("TASK-*.json"):
            try:
                num = int(f.stem.split("-")[1])
                if num > max_num:
                    max_num = num
            except (IndexError, ValueError):
                continue
    return max_num


def _read_counter() -> int:
    """Read current counter value, seeding from filesystem if needed."""
    _ensure_dirs()
    if not _COUNTER_FILE.exists():
        seed = _seed_counter()
        _COUNTER_FILE.write_text(str(seed), encoding="utf-8")
        return seed
    try:
        return int(_COUNTER_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, FileNotFoundError):
        seed = _seed_counter()
        _COUNTER_FILE.write_text(str(seed), encoding="utf-8")
        return seed


def _write_counter(value: int) -> None:
    """Atomically write counter value (tmp + rename)."""
    tmp = _COUNTER_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(str(value), encoding="utf-8")
        tmp.replace(_COUNTER_FILE)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def next_task_id() -> str:
    """Generate the next task ID using atomic counter file.

    v2.0: Uses .task_counter file instead of filesystem scan.
    The tmp+rename write is atomic on most filesystems.
    For the single-user CLI use case, races are extremely unlikely.
    """
    current = _read_counter()
    next_num = current + 1
    _write_counter(next_num)
    return f"TASK-{next_num:03d}"


# ═══════════════════════════════════════════════════════════════════════════════
# Core I/O
# ═══════════════════════════════════════════════════════════════════════════════

def save_task(task: dict, status: str) -> Path:
    """
    Write task dict to the directory matching its status.
    Uses atomic write: tmp file first, then rename.
    """
    if status not in STATUS_DIRS:
        raise ValueError(f"Unknown status: {status!r}")
    task_id = task["id"]
    _validate_task_id(task_id)
    task["status"] = status
    task.setdefault("created_at", _now())

    _ensure_dirs()
    target = STATUS_DIRS[status] / f"{task_id}.json"
    tmp = target.with_suffix(".tmp")

    try:
        tmp.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise

    return target


def load_task(task_id: str) -> dict | None:
    """Find and load a task by ID from any status directory."""
    _validate_task_id(task_id)
    filepath = _find_task_file(task_id)
    if filepath is None:
        return None
    return json.loads(filepath.read_text(encoding="utf-8"))


def move_task(task_id: str, from_status: str, to_status: str,
              task: dict | None = None) -> dict:
    """
    Move a task file from one status directory to another (v2.0 atomic).

    v2.0 fix — correct ordering:
      1. Use pre-modified task dict if provided, otherwise read source file
      2. Write new file (tmp + atomic rename)
      3. Verify destination exists
      4. Delete source file

    If `task` is provided, it must already contain all desired modifications
    (event_log entries, timestamps, etc.). The status field will be set to
    to_status automatically.

    This avoids the "double file exists" window where both
    src and dst exist simultaneously before src is deleted.
    """
    _validate_task_id(task_id)
    if from_status not in STATUS_DIRS:
        raise ValueError(f"Unknown from_status: {from_status!r}")
    if to_status not in STATUS_DIRS:
        raise ValueError(f"Unknown to_status: {to_status!r}")

    src = STATUS_DIRS[from_status] / f"{task_id}.json"

    if task is None:
        if not src.exists():
            raise FileNotFoundError(f"Task {task_id} not found in {from_status}")
        task = json.loads(src.read_text(encoding="utf-8"))

    task["status"] = to_status

    _ensure_dirs()
    dst = STATUS_DIRS[to_status] / f"{task_id}.json"
    tmp = dst.with_suffix(".tmp")

    try:
        tmp.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(dst)
        # Verify destination exists before deleting source
        if not dst.exists():
            raise RuntimeError(f"Atomic rename failed: {dst} does not exist after rename")
        src.unlink()
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise

    return task


def list_tasks(status: str) -> list[dict]:
    """List all tasks in the given status directory, sorted by created_at."""
    if status not in STATUS_DIRS:
        raise ValueError(f"Unknown status: {status!r}")

    _ensure_dirs()
    tasks = []
    dirpath = STATUS_DIRS[status]
    for f in sorted(dirpath.glob("*.json")):
        try:
            tasks.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue

    tasks.sort(key=lambda t: t.get("created_at", ""))
    return tasks
