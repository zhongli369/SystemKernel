"""
filewatch_source.py — File Watch Event Source (v1.0)

Watches filesystem for changes to whitelisted files and emits events.

PURELY an event emitter — no processing, no routing, no task creation.
Does NOT:
  - Read file contents for meaning
  - Classify the type of change
  - Decide whether the change is "important"
  - Call any LLM

Uses polling (simple, deterministic, no OS-specific watcher dependencies).
For production, replace with inotify/ReadDirectoryChangesW/FSEvents.
"""

import os
import time
from pathlib import Path
from typing import Optional, Callable


# ═══════════════════════════════════════════════════════════════════════════════
# Single event emission (for hook-based integration)
# ═══════════════════════════════════════════════════════════════════════════════

def listen(path: str, change_type: str) -> dict:
    """Emit a file watch event for a single file change.

    Args:
        path: Path to the changed file.
        change_type: "created" | "changed" | "deleted" | "modified"

    Returns:
        Raw event dict ready for EventBus.ingest().
    """
    from EventBus.event_schema import normalize_filewatch
    return normalize_filewatch(path, change_type)


# ═══════════════════════════════════════════════════════════════════════════════
# Polling watcher — simple, deterministic, no OS-specific deps
# ═══════════════════════════════════════════════════════════════════════════════

def watch(
    paths: list[str],
    callback: Callable[[dict], None],
    interval: float = 5.0,
    whitelist: Optional[set[str]] = None,
):
    """Poll a list of files/directories for changes and emit events.

    Deterministic polling — no inotify, no threading complexity.

    Args:
        paths: List of file or directory paths to watch.
        callback: Called with raw event dict for each change detected.
        interval: Polling interval in seconds (default 5.0).
        whitelist: Optional set of filenames to watch (uses FILEWATCH_WHITELIST if None).

    Note:
        This is a BLOCKING function. Run it in a dedicated thread/process.
        For production, replace with OS-native file watchers.
    """
    from EventBus.event_schema import FILEWATCH_WHITELIST

    if whitelist is None:
        whitelist = set(FILEWATCH_WHITELIST)

    # Expand directories to individual whitelisted files
    watch_files: dict[str, float] = {}  # path → last mtime

    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        if path.is_file():
            if path.name in whitelist:
                watch_files[str(path)] = os.path.getmtime(str(path))
        elif path.is_dir():
            for root, _, files in os.walk(str(path)):
                for f in files:
                    if f in whitelist:
                        full = os.path.join(root, f)
                        watch_files[full] = os.path.getmtime(full)

    # Polling loop
    while True:
        for filepath, last_mtime in list(watch_files.items()):
            try:
                current_mtime = os.path.getmtime(filepath)
            except OSError:
                # File deleted
                if last_mtime > 0:
                    callback(listen(filepath, "deleted"))
                    watch_files[filepath] = -1  # Mark as deleted
                continue

            if last_mtime < 0:
                # File was deleted, now recreated
                callback(listen(filepath, "created"))
                watch_files[filepath] = current_mtime
            elif current_mtime > last_mtime:
                callback(listen(filepath, "changed"))
                watch_files[filepath] = current_mtime

        time.sleep(interval)
