"""
Tier Store — JSON file-based tiered memory storage.

Three-tier storage:
  L1 (WORKING)  — in-memory dict, never persisted, session-scoped
  L2 (EPISODIC) — ./v3/context_tiers/episodic/{execution_id}.jsonl, 7-day TTL
  L3 (SEMANTIC) — ./v3/context_tiers/semantic/entities.jsonl, permanent

All writes are append-only (open(path, "a") — never truncates).
expire() performs garbage collection on L2 files.
compact() promotes L2→L3 via compact_episodic_to_semantic().

Stdlib only. No external dependencies. No LLM.
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from v3.external.context_tiering.tier_policy import (
    MemoryTier,
    TierEntry,
    compact_episodic_to_semantic,
)


# ═══════════════════════════════════════════════════════════════════════
# Default storage root
# ═══════════════════════════════════════════════════════════════════════

def _default_storage_root() -> Path:
    """Compute the default storage root relative to this source file."""
    return Path(__file__).parent.parent.parent.parent / "v3" / "context_tiers"


# ═══════════════════════════════════════════════════════════════════════
# Tier Store (abstract)
# ═══════════════════════════════════════════════════════════════════════

class TierStore(ABC):
    """Abstract interface for tiered memory storage."""

    @abstractmethod
    def save(self, entry: TierEntry) -> None:
        """Persist a TierEntry to the appropriate tier."""

    @abstractmethod
    def load_by_execution(self, execution_id: str) -> Tuple[TierEntry, ...]:
        """Load all entries for a specific execution."""

    @abstractmethod
    def load_by_tier(self, tier: MemoryTier) -> Tuple[TierEntry, ...]:
        """Load all entries in a given tier."""

    @abstractmethod
    def expire(self) -> int:
        """Remove expired entries. Returns number of files cleaned up."""

    @abstractmethod
    def compact(self, window_days: int = 7, threshold: int = 3) -> int:
        """Promote L2 entities to L3. Returns number promoted."""


# ═══════════════════════════════════════════════════════════════════════
# File Tier Store
# ═══════════════════════════════════════════════════════════════════════

class FileTierStore(TierStore):
    """JSONL file-based implementation of TierStore.

    L1: in-memory dict (never persisted)
    L2: ./v3/context_tiers/episodic/{execution_id}.jsonl (append-only)
    L3: ./v3/context_tiers/semantic/entities.jsonl (append-only)
    """

    def __init__(self, storage_root: Optional[Path] = None,
                 auto_compact: bool = False, compact_threshold: int = 5,
                 ttl_episodic: int = 604800):
        root = storage_root or _default_storage_root()
        self._root = Path(root)
        self._episodic_dir = self._root / "episodic"
        self._semantic_dir = self._root / "semantic"
        self._l1_store: dict[str, TierEntry] = {}
        self.auto_compact = auto_compact
        self.compact_threshold = compact_threshold
        self.ttl_episodic = ttl_episodic
        # Simple metrics counters (stdlib, no external deps)
        self.metrics: dict[str, int] = {
            "writes_working": 0,
            "writes_episodic": 0,
            "writes_semantic": 0,
            "compaction_runs": 0,
            "compaction_promoted": 0,
            "expire_runs": 0,
            "expire_removed": 0,
        }

    # ── Path helpers ─────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        self._episodic_dir.mkdir(parents=True, exist_ok=True)
        self._semantic_dir.mkdir(parents=True, exist_ok=True)

    def _l2_path(self, execution_id: str) -> Path:
        safe_id = execution_id.replace("/", "_").replace("\\", "_")
        return self._episodic_dir / f"{safe_id}.jsonl"

    def _l3_path(self) -> Path:
        return self._semantic_dir / "entities.jsonl"

    # ── Write helpers (append-only) ──────────────────────────────────

    def _append_jsonl(self, path: Path, data: dict) -> None:
        """Append a single JSON line to a JSONL file. Never truncates."""
        self._ensure_dirs()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _read_jsonl(self, path: Path) -> list[dict]:
        """Read all JSON lines from a JSONL file. Returns empty list if
        file does not exist (graceful degradation)."""
        if not path.exists():
            return []
        entries: list[dict] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except (OSError, UnicodeDecodeError):
            return []
        return entries

    def _read_jsonl_entries(self, path: Path) -> list[TierEntry]:
        """Read all TierEntry objects from a JSONL file.

        Gracefully skips malformed entries (ValueError on invalid tier, etc.).
        """
        raw = self._read_jsonl(path)
        entries: list[TierEntry] = []
        for d in raw:
            try:
                entries.append(TierEntry.from_dict(d))
            except (ValueError, TypeError):
                continue
        return entries

    # ── Save ─────────────────────────────────────────────────────────

    def save(self, entry: TierEntry) -> None:
        """Persist a TierEntry to the appropriate tier.

        L1 (WORKING): stored in-memory only, never written to disk.
        L2 (EPISODIC): appended to execution-scoped JSONL file.
        L3 (SEMANTIC): appended to entities JSONL file.

        When auto_compact is enabled and an EPISODIC entry is saved,
        checks if the entity_key has accumulated enough entries in the
        current window to trigger compaction.
        """
        if entry.tier == MemoryTier.WORKING:
            self._l1_store[entry.entry_id] = entry
            self.metrics["writes_working"] += 1
        elif entry.tier == MemoryTier.EPISODIC:
            self._append_jsonl(self._l2_path(entry.execution_id), entry.to_dict())
            self.metrics["writes_episodic"] += 1
            # Auto-compact: check if entity_key has enough entries
            if self.auto_compact and entry.entity_key:
                self._maybe_auto_compact(entry.entity_key)
        elif entry.tier == MemoryTier.SEMANTIC:
            self._append_jsonl(self._l3_path(), entry.to_dict())
            self.metrics["writes_semantic"] += 1

    def _maybe_auto_compact(self, entity_key: str) -> None:
        """Check if entity_key meets threshold and trigger inline compaction."""
        if self.compact_threshold < 2:
            return
        # Count L2 entries for this entity_key in current window
        all_l2 = self.load_by_tier(MemoryTier.EPISODIC)
        count = sum(1 for e in all_l2 if e.entity_key == entity_key)
        if count >= self.compact_threshold:
            promoted = self.compact(window_days=7, threshold=self.compact_threshold)
            if promoted > 0:
                self.metrics["compaction_promoted"] += promoted

    # ── Load ─────────────────────────────────────────────────────────

    def load_by_execution(self, execution_id: str) -> Tuple[TierEntry, ...]:
        """Load all entries for a specific execution from L2 + L1.

        L1 entries matching the execution_id are included.
        L2 entries are read from the execution's JSONL file.
        Expired entries (ttl_expires_at in past) are filtered out.
        """
        results: list[TierEntry] = []

        # L1: filter in-memory entries
        for entry in self._l1_store.values():
            if entry.execution_id == execution_id:
                results.append(entry)

        # L2: read execution file
        l2_path = self._l2_path(execution_id)
        for entry in self._read_jsonl_entries(l2_path):
            if not _is_expired(entry):
                results.append(entry)

        return tuple(results)

    def load_by_tier(self, tier) -> Tuple[TierEntry, ...]:
        """Load all entries in a given tier.

        Accepts MemoryTier enum or string (e.g. "working", "episodic", "semantic").

        L1: from in-memory dict
        L2: all .jsonl files in episodic/ directory
        L3: entities.jsonl
        """
        if isinstance(tier, str):
            tier = MemoryTier(tier)
        if tier == MemoryTier.WORKING:
            return tuple(self._l1_store.values())

        if tier == MemoryTier.EPISODIC:
            results: list[TierEntry] = []
            try:
                for fpath in self._episodic_dir.glob("*.jsonl"):
                    for entry in self._read_jsonl_entries(fpath):
                        if not _is_expired(entry):
                            results.append(entry)
            except OSError:
                pass
            return tuple(results)

        if tier == MemoryTier.SEMANTIC:
            return tuple(self._read_jsonl_entries(self._l3_path()))

        return ()

    # ── Expire ───────────────────────────────────────────────────────

    def expire(self) -> int:
        """Remove L2 files where all entries are expired.

        For files with mixed (expired + valid) entries, rewrite the file
        keeping only valid entries. For files where all entries are expired,
        delete the file entirely.

        L1 entries past their TTL are also purged.

        Returns number of files removed.
        """
        removed = 0

        # Purge expired L1 entries only (not all)
        expired_l1 = [eid for eid, e in self._l1_store.items() if _is_expired(e)]
        for eid in expired_l1:
            del self._l1_store[eid]

        # Process L2 files
        try:
            for fpath in list(self._episodic_dir.glob("*.jsonl")):
                all_entries = self._read_jsonl_entries(fpath)
                valid = [e for e in all_entries if not _is_expired(e)]

                if not valid:
                    try:
                        os.remove(fpath)
                        removed += 1
                    except OSError:
                        pass
                elif len(valid) < len(all_entries):
                    # Rewrite with only valid entries (cleanup, not data write)
                    try:
                        with open(fpath, "w", encoding="utf-8") as f:
                            for e in valid:
                                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
                    except OSError:
                        pass
        except OSError:
            pass

        self.metrics["expire_runs"] += 1
        self.metrics["expire_removed"] += removed
        return removed

    # ── Compact ──────────────────────────────────────────────────────

    def compact(self, window_days: int = 7, threshold: int = 3) -> int:
        """Promote L2 entries to L3 via episodic-to-semantic compaction.

        Reads all L2 entries, runs compact_episodic_to_semantic(), appends
        promoted entries to L3, and removes the source L2 entries.

        This is the ONE case where file overwrite is correct — compaction
        is a deliberate state transition from L2 to L3.

        Returns number of entries promoted to L3.
        """
        all_l2 = list(self.load_by_tier(MemoryTier.EPISODIC))
        if not all_l2:
            return 0

        promoted = compact_episodic_to_semantic(
            tuple(all_l2),
            window_days=window_days,
            threshold=threshold,
        )

        if not promoted:
            return 0

        # Collect entity_keys that were promoted
        promoted_keys: set[str] = {e.entity_key for e in promoted}

        # Remove source L2 entries: find which execution files contain
        # entries with promoted entity_keys, and rewrite them without those entries
        self._remove_compacted_sources(promoted_keys)

        # Save promoted entries to L3
        for entry in promoted:
            self.save(entry)

        self.metrics["compaction_runs"] += 1
        self.metrics["compaction_promoted"] += len(promoted)
        return len(promoted)

    def _remove_compacted_sources(self, promoted_keys: set[str]) -> None:
        """Remove L2 entries whose entity_key was promoted to L3.

        For each L2 JSONL file, filter out entries with promoted entity_keys.
        If no entries remain, delete the file. Otherwise, overwrite with
        remaining entries.
        """
        try:
            for fpath in list(self._episodic_dir.glob("*.jsonl")):
                all_entries = self._read_jsonl_entries(fpath)
                remaining = [
                    e for e in all_entries
                    if e.entity_key not in promoted_keys
                ]
                if not remaining:
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
                elif len(remaining) < len(all_entries):
                    try:
                        with open(fpath, "w", encoding="utf-8") as f:
                            for e in remaining:
                                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
                    except OSError:
                        pass
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _is_expired(entry: TierEntry) -> bool:
    """Check if a TierEntry has passed its TTL.

    TTL 0 (WORKING): not expired (managed separately)
    TTL -1 (SEMANTIC): never expires
    TTL > 0: expired if current time > ttl_expires_at
    """
    if entry.ttl_expires_at < 0:
        return False   # SEMANTIC — permanent
    if entry.ttl_expires_at == 0:
        return False   # WORKING — session-scoped, managed by L1 purge
    return time.time() > entry.ttl_expires_at


# ═══════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════

def create_tier_store(path: Optional[str] = None) -> FileTierStore:
    """Create a FileTierStore at the given path.

    If path is None, uses the default: ./v3/context_tiers/ relative to
    the SystemKernel root.
    """
    storage_root = Path(path) if path else None
    return FileTierStore(storage_root=storage_root)
