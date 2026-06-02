"""
Sandbox Snapshot — Filesystem snapshot/rollback for worktree sandboxes.

Pure stdlib: shutil.copytree for snapshots, shutil.rmtree for cleanup.
No Docker, no ZFS, no LVM. Filesystem-level only.

Snapshots are stored in .sandbox_snapshots/ relative to the worktree.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class SnapshotManager:
    """Manage filesystem snapshots for sandbox worktrees.

    Snapshots are full directory copies using shutil.copytree.
    Suitable for small-to-medium worktrees (<1GB). Not suitable
    for production container-level checkpointing.
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.path.join(
                os.path.dirname(__file__), ".sandbox_snapshots"
            )
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self, path: str) -> str:
        """Create a snapshot of the given directory.

        Returns the snapshot_id.
        """
        snapshot_id = str(uuid.uuid4())[:16]
        dest = self._base_dir / snapshot_id
        try:
            shutil.copytree(path, str(dest), symlinks=False,
                           ignore_dangling_symlinks=True)
        except (OSError, shutil.Error) as e:
            raise OSError(f"Snapshot failed: {e}") from e
        # Write metadata
        meta = {
            "snapshot_id": snapshot_id,
            "source_path": str(path),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = self._base_dir / f"{snapshot_id}.meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        return snapshot_id

    def rollback(self, path: str, snapshot_id: str) -> bool:
        """Restore a directory from a snapshot.

        Removes current contents first, then copies snapshot back.
        Returns True on success.
        """
        snap_dir = self._base_dir / snapshot_id
        if not snap_dir.exists():
            return False
        target = Path(path)
        # Remove current contents
        if target.exists():
            try:
                shutil.rmtree(str(target), ignore_errors=True)
            except OSError:
                return False
        # Restore from snapshot
        try:
            shutil.copytree(str(snap_dir), str(target), symlinks=False)
            return True
        except (OSError, shutil.Error):
            return False

    def list_snapshots(self) -> list[dict]:
        """List all snapshots with metadata."""
        snapshots = []
        for meta_file in sorted(self._base_dir.glob("*.meta.json")):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    snapshots.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
        return snapshots

    def prune(self, max_age_hours: int = 24) -> int:
        """Remove snapshots older than max_age_hours. Returns count pruned."""
        now = time.time()
        cutoff = now - (max_age_hours * 3600)
        pruned = 0
        for meta_file in list(self._base_dir.glob("*.meta.json")):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                created = datetime.fromisoformat(
                    meta["created_at"]
                ).timestamp()
                if created < cutoff:
                    snap_id = meta["snapshot_id"]
                    snap_dir = self._base_dir / snap_id
                    if snap_dir.exists():
                        shutil.rmtree(str(snap_dir), ignore_errors=True)
                    meta_file.unlink(missing_ok=True)
                    pruned += 1
            except (json.JSONDecodeError, OSError, KeyError, ValueError):
                pass
        return pruned
