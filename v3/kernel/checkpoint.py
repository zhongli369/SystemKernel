"""
Checkpoint — Append-only JSONL checkpoint persistence for deterministic execution.

Phase 4B: Checkpoints are optimization snapshots only.
The event log (events.py) is the authoritative source of truth.
ExecutionState is a pure projection of the event stream.

Enhances the v2 checkpoint system with:
  - execution_id keying (replaces thread_id)
  - pipeline_hash, stage_order, truth_fingerprint, invariant_status
  - lifecycle_snapshot from ExecutionState
  - CrashMarker for crash recovery
  - Append-only guarantee (never truncates, never overwrites)

Zero LLM. Zero external dependencies beyond stdlib.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Checkpoint
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Checkpoint:
    """Point-in-time execution snapshot.

    Written after each successful pipeline stage and once at completion.
    Links form a parent chain for deterministic replay.
    """

    checkpoint_id: str
    execution_id: str
    stage: str
    stage_index: int = 0
    state_snapshot: dict = field(default_factory=dict)
    lifecycle_snapshot: dict = field(default_factory=dict)
    pipeline_hash: str = ""
    stage_order: Tuple[str, ...] = ()
    truth_fingerprint: str = ""
    invariant_status: str = "UNKNOWN"
    timestamp: str = ""
    parent_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "execution_id": self.execution_id,
            "stage": self.stage,
            "stage_index": self.stage_index,
            "state_snapshot": self.state_snapshot,
            "lifecycle_snapshot": self.lifecycle_snapshot,
            "pipeline_hash": self.pipeline_hash,
            "stage_order": list(self.stage_order),
            "truth_fingerprint": self.truth_fingerprint,
            "invariant_status": self.invariant_status,
            "timestamp": self.timestamp,
            "parent_id": self.parent_id,
        }


# ═══════════════════════════════════════════════════════════════════════
# CheckpointStore — abstract
# ═══════════════════════════════════════════════════════════════════════

class CheckpointStore:
    """Abstract checkpoint persistence.

    Subclass and implement the storage methods.
    """

    def save_checkpoint(self, cp: Checkpoint) -> None:
        raise NotImplementedError

    def load_latest(self, execution_id: str) -> Optional[Checkpoint]:
        raise NotImplementedError

    def load(self, execution_id: str, checkpoint_id: str) -> Optional[Checkpoint]:
        raise NotImplementedError

    def list(self, execution_id: str, limit: int = 100) -> list[Checkpoint]:
        raise NotImplementedError

    def replay(self, execution_id: str) -> list[Checkpoint]:
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════
# FileCheckpointStore — append-only JSONL
# ═══════════════════════════════════════════════════════════════════════

class FileCheckpointStore(CheckpointStore):
    """Append-only JSONL checkpoint storage.

    Guarantees:
      - All writes use open(path, "a") — never truncates, never overwrites
      - File naming: {safe_execution_id}.jsonl
      - Each line is a complete, parseable JSON object
      - Order is preserved: first line = first checkpoint, last = latest
    """

    def __init__(self, path: str = "./v3/checkpoints/"):
        self._path = path
        os.makedirs(path, exist_ok=True)

    def _file(self, execution_id: str) -> str:
        safe_id = execution_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self._path, f"{safe_id}.jsonl")

    def _list_execution_files(self) -> list[str]:
        result = []
        try:
            for fname in os.listdir(self._path):
                if fname.endswith(".jsonl"):
                    result.append(os.path.join(self._path, fname))
        except OSError:
            pass
        return result

    # ── Write (append-only) ────────────────────────────────────────────

    def save_checkpoint(self, cp: Checkpoint) -> None:
        """Append checkpoint to JSONL file. NEVER truncates."""
        record = cp.to_dict()
        with open(self._file(cp.execution_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ── Read ───────────────────────────────────────────────────────────

    def load_latest(self, execution_id: str) -> Optional[Checkpoint]:
        """Load most recent checkpoint for an execution. O(1) via last-line read."""
        fpath = self._file(execution_id)
        if not os.path.exists(fpath):
            return None
        try:
            with open(fpath, encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return None
            return self._parse_record(json.loads(lines[-1].strip()))
        except (OSError, json.JSONDecodeError):
            return None

    def load(self, execution_id: str, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a specific checkpoint by ID."""
        fpath = self._file(execution_id)
        if not os.path.exists(fpath):
            return None
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line.strip())
                    if record.get("checkpoint_id") == checkpoint_id:
                        return self._parse_record(record)
        except (OSError, json.JSONDecodeError):
            pass
        return None

    def list(self, execution_id: str, limit: int = 100) -> list[Checkpoint]:
        """List all checkpoints for an execution, most recent first."""
        fpath = self._file(execution_id)
        if not os.path.exists(fpath):
            return []
        checkpoints = []
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    checkpoints.append(self._parse_record(json.loads(line.strip())))
        except (OSError, json.JSONDecodeError):
            pass
        return checkpoints[-limit:]

    def replay(self, execution_id: str) -> list[Checkpoint]:
        """Return checkpoints in chronological order for replay."""
        return self.list(execution_id, limit=10000)

    # ── Parse ──────────────────────────────────────────────────────────

    def _parse_record(self, record: dict) -> Checkpoint:
        return Checkpoint(
            checkpoint_id=record.get("checkpoint_id", ""),
            execution_id=record.get("execution_id", ""),
            stage=record.get("stage", ""),
            stage_index=record.get("stage_index", 0),
            state_snapshot=record.get("state_snapshot", {}),
            lifecycle_snapshot=record.get("lifecycle_snapshot", {}),
            pipeline_hash=record.get("pipeline_hash", ""),
            stage_order=tuple(record.get("stage_order", [])),
            truth_fingerprint=record.get("truth_fingerprint", ""),
            invariant_status=record.get("invariant_status", "UNKNOWN"),
            timestamp=record.get("timestamp", ""),
            parent_id=record.get("parent_id"),
        )


# ═══════════════════════════════════════════════════════════════════════
# CrashMarker — crash recovery marker
# ═══════════════════════════════════════════════════════════════════════

class CrashMarker:
    """Static helper for crash detection and recovery.

    Before each stage, a .crash file is written with the current execution
    context. After successful checkpointing, it is cleared.

    If a crash marker exists on the next run(), the engine can detect it
    and resume from the last good checkpoint.
    """

    DIR = "./v3/checkpoints/"

    @staticmethod
    def _path(execution_id: str) -> str:
        safe_id = execution_id.replace("/", "_").replace("\\", "_")
        return os.path.join(CrashMarker.DIR, f"{safe_id}.crash")

    @staticmethod
    def write(execution_id: str, stage: str, stage_index: int) -> None:
        """Write crash marker before stage execution."""
        os.makedirs(CrashMarker.DIR, exist_ok=True)
        marker = {
            "execution_id": execution_id,
            "stage": stage,
            "stage_index": stage_index,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(CrashMarker._path(execution_id), "w", encoding="utf-8") as f:
                json.dump(marker, f, ensure_ascii=False)
        except OSError:
            pass

    @staticmethod
    def read(execution_id: str) -> Optional[dict]:
        """Read crash marker if it exists. Returns None if absent."""
        fpath = CrashMarker._path(execution_id)
        if not os.path.exists(fpath):
            return None
        try:
            with open(fpath, encoding="utf-8") as f:
                return json.loads(f.read().strip())
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def exists(execution_id: str) -> bool:
        """Check if a crash marker is present."""
        return os.path.exists(CrashMarker._path(execution_id))

    @staticmethod
    def clear(execution_id: str) -> None:
        """Remove crash marker after successful stage completion."""
        fpath = CrashMarker._path(execution_id)
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════

def compute_truth_fingerprint(truth: dict) -> str:
    """Deterministic fingerprint of a truth snapshot for checkpoint embedding."""
    import hashlib
    parts = [
        truth.get("pipeline_hash", ""),
        "|".join(truth.get("stage_order", [])),
        truth.get("invariant_status", "UNKNOWN"),
        str(truth.get("invariant_violations", 0)),
    ]
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]
