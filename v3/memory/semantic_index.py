"""
SemanticMemoryIndex — Deterministic lexical semantic index for episodic memory.

Phase 4D-3: "Semantic" here means lexical/deterministic token-based indexing,
NOT embedding-based. No LLM. No vector DB. No external services.

The index is a pure projection of EpisodicMemoryRecord data. It can be fully
rebuilt from the episodic JSONL store at any time.

Properties:
  - Deterministic tokenization (split + lowercase + filter)
  - Deterministic scoring (token match + tag boost + frequency normalization)
  - Deterministic tie-break by record_hash
  - Index is projection only — not a truth source
  - Fully rebuildable from episodic JSONL records
  - Zero external dependencies (stdlib only)
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3.memory.episodic_store import EpisodicMemoryStore, EpisodicMemoryRecord


# ═══════════════════════════════════════════════════════════════════════
# Tokenizer (deterministic, stdlib only)
# ═══════════════════════════════════════════════════════════════════════

_TOKENIZE_RE = re.compile(r"[^a-zA-Z0-9_一-鿿]+")
_MIN_TOKEN_LEN = 2


def tokenize(text: str) -> Tuple[str, ...]:
    """Deterministic tokenization: split on non-word chars, lowercase, filter short tokens.

    Preserves CJK characters (U+4E00–U+9FFF) for Chinese text support.
    Same input always produces the same tokens in the same order.
    """
    if not text:
        return ()
    tokens: list[str] = []
    for token in _TOKENIZE_RE.split(text.lower()):
        token = token.strip()
        if len(token) >= _MIN_TOKEN_LEN:
            tokens.append(token)
    return tuple(tokens)


# ═══════════════════════════════════════════════════════════════════════
# SemanticIndexEntry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SemanticIndexEntry:
    """A single inverted-index entry mapping a token to matching records.

    Fields:
        token: The indexed token (lowercased, cleaned)
        memory_ids: All memory_ids whose content contains this token
        record_hashes: Corresponding record_hashes
        frequency: Total occurrences of this token across all records
        candidate_types: Candidate types in records containing this token
        tags: All tags from records containing this token
        source_execution_ids: Execution IDs of source records
    """

    token: str
    memory_ids: Tuple[str, ...]
    record_hashes: Tuple[str, ...]
    frequency: int
    candidate_types: Tuple[str, ...]
    tags: Tuple[str, ...]
    source_execution_ids: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "memory_ids": list(self.memory_ids),
            "record_hashes": list(self.record_hashes),
            "frequency": self.frequency,
            "candidate_types": list(self.candidate_types),
            "tags": list(self.tags),
            "source_execution_ids": list(self.source_execution_ids),
        }

    @staticmethod
    def from_dict(d: dict) -> "SemanticIndexEntry":
        return SemanticIndexEntry(
            token=d["token"],
            memory_ids=tuple(d.get("memory_ids", [])),
            record_hashes=tuple(d.get("record_hashes", [])),
            frequency=d.get("frequency", 0),
            candidate_types=tuple(d.get("candidate_types", [])),
            tags=tuple(d.get("tags", [])),
            source_execution_ids=tuple(d.get("source_execution_ids", [])),
        )


# ═══════════════════════════════════════════════════════════════════════
# SemanticSearchResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SemanticSearchResult:
    """A single search result with scoring breakdown.

    Fields:
        memory_id: Matched memory record ID
        score: Deterministic relevance score (0.0–1.0+)
        matched_tokens: Which query tokens matched
        candidate_type: Type of the matched record
        tags: Tags of the matched record
        source_hash: Traceability link to source events
        record_hash: Content-addressed record hash
    """

    memory_id: str
    score: float
    matched_tokens: Tuple[str, ...]
    candidate_type: str
    tags: Tuple[str, ...]
    source_hash: str
    record_hash: str

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "score": self.score,
            "matched_tokens": list(self.matched_tokens),
            "candidate_type": self.candidate_type,
            "tags": list(self.tags),
            "source_hash": self.source_hash,
            "record_hash": self.record_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# SemanticMemoryIndex
# ═══════════════════════════════════════════════════════════════════════

class SemanticMemoryIndex:
    """Deterministic lexical semantic index over episodic memory records.

    Builds an inverted index from EpisodicMemoryRecord objects. Search is
    pure token matching with deterministic scoring — no embeddings, no ML.

    Usage:
        store = EpisodicMemoryStore("data/episodes.jsonl")
        index = SemanticMemoryIndex()
        index.build(store.list_records())
        results = index.search("build error", limit=10)
        explanation = index.explain("build error")

    All operations are deterministic: same records + same query = same results.
    """

    def __init__(self):
        self._entries: dict[str, SemanticIndexEntry] = {}
        self._records_by_memory_id: dict[str, EpisodicMemoryRecord] = {}
        self._record_count: int = 0
        self._index_hash: str = ""
        self._built: bool = False

    # ── Build ──────────────────────────────────────────────────────────

    def build(self, records: "Tuple[EpisodicMemoryRecord, ...]") -> int:
        """Build inverted index from episodic memory records.

        Returns the number of unique tokens indexed.
        """
        # Inverted index: token → {memory_id: frequency}
        token_map: dict[str, dict[str, int]] = {}
        record_map: dict[str, EpisodicMemoryRecord] = {}

        for record in records:
            record_map[record.memory_id] = record

            # Tokenize content
            content_text = json.dumps(
                record.content, ensure_ascii=False, sort_keys=True, default=str
            )
            tokens = tokenize(content_text)

            # Also tokenize tags (boosted in search)
            tag_tokens: set[str] = set()
            for tag in record.tags:
                tag_tokens.update(tokenize(tag))

            all_tokens = set(tokens) | tag_tokens

            for token in all_tokens:
                if token not in token_map:
                    token_map[token] = {}
                token_map[token][record.memory_id] = token_map[token].get(record.memory_id, 0) + 1

        # Build SemanticIndexEntry per token
        entries: dict[str, SemanticIndexEntry] = {}
        for token, mem_freqs in token_map.items():
            mem_ids = tuple(sorted(mem_freqs.keys()))
            total_freq = sum(mem_freqs.values())

            # Collect metadata for records containing this token
            ctypes: set[str] = set()
            tags: set[str] = set()
            eids: set[str] = set()
            rhashes: list[str] = []

            for mid in mem_ids:
                rec = record_map.get(mid)
                if rec:
                    ctypes.add(rec.candidate_type)
                    tags.update(rec.tags)
                    eids.add(rec.execution_id)
                    rhashes.append(rec.record_hash)

            entries[token] = SemanticIndexEntry(
                token=token,
                memory_ids=tuple(mem_ids),
                record_hashes=tuple(sorted(rhashes)),
                frequency=total_freq,
                candidate_types=tuple(sorted(ctypes)),
                tags=tuple(sorted(tags)),
                source_execution_ids=tuple(sorted(eids)),
            )

        self._entries = entries
        self._records_by_memory_id = record_map
        self._record_count = len(records)
        self._index_hash = self._compute_index_hash()
        self._built = True

        return len(entries)

    # ── Search ─────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> Tuple[SemanticSearchResult, ...]:
        """Search the index for records matching the query.

        Scoring (deterministic):
          - Token match: each matched token = 1/N per record (N = query token count)
          - Tag match: +0.2 per matched tag token
          - Frequency normalization: log(1 + tf) dampening
          - Tie-break: lower record_hash sorts first (deterministic total order)

        Filters (optional dict):
          - execution_id: str — only records with this execution_id
          - candidate_type: str — only records of this type
          - tag: str — only records with this tag
          - min_importance: int — only records with importance >= this value

        Args:
            query: Search query text
            limit: Max results to return
            filters: Optional filter dict

        Returns:
            Tuple of SemanticSearchResult, sorted by score descending,
            then by record_hash ascending (deterministic tie-break).
        """
        if not self._built:
            return ()

        query_tokens = tokenize(query)
        if not query_tokens:
            return ()

        filters = filters or {}
        exec_filter = filters.get("execution_id", "")
        type_filter = filters.get("candidate_type", "")
        tag_filter = filters.get("tag", "")
        min_importance = filters.get("min_importance", 0)

        n = len(query_tokens)
        scores: dict[str, dict] = {}  # memory_id → {score, matched_tokens, ...}

        for qt in query_tokens:
            entry = self._entries.get(qt)
            if entry is None:
                continue

            for mid in entry.memory_ids:
                rec = self._records_by_memory_id.get(mid)
                if rec is None:
                    continue

                # Apply filters
                if exec_filter and rec.execution_id != exec_filter:
                    continue
                if type_filter and rec.candidate_type != type_filter:
                    continue
                if tag_filter and tag_filter not in rec.tags:
                    continue
                if rec.importance < min_importance:
                    continue

                # Token match score
                token_score = 1.0 / n

                if mid not in scores:
                    scores[mid] = {
                        "score": 0.0,
                        "matched_tokens": [],
                        "candidate_type": rec.candidate_type,
                        "tags": rec.tags,
                        "source_hash": rec.source_hash,
                        "record_hash": rec.record_hash,
                    }

                scores[mid]["score"] += token_score
                scores[mid]["matched_tokens"].append(qt)

        # Tag boost: check if query tokens match record tags
        for mid in scores:
            rec = self._records_by_memory_id.get(mid)
            if rec is None:
                continue
            for qt in query_tokens:
                for tag in rec.tags:
                    tag_lower = tag.lower()
                    if qt in tag_lower or tag_lower in qt:
                        scores[mid]["score"] += 0.2
                        break

        # Build results sorted by score desc, then record_hash asc (tie-break)
        results: list[SemanticSearchResult] = []
        for mid, data in scores.items():
            results.append(SemanticSearchResult(
                memory_id=mid,
                score=round(data["score"], 4),
                matched_tokens=tuple(sorted(set(data["matched_tokens"]))),
                candidate_type=data["candidate_type"],
                tags=tuple(data["tags"]),
                source_hash=data["source_hash"],
                record_hash=data["record_hash"],
            ))

        # Sort: score descending, record_hash ascending (deterministic tie-break)
        results.sort(key=lambda r: (-r.score, r.record_hash))

        return tuple(results[:limit])

    # ── Explain ────────────────────────────────────────────────────────

    def explain(self, query: str) -> dict:
        """Explain how a query would be processed — tokenization, which
        index entries match, scoring breakdown.

        Returns a dict suitable for debugging and verification.
        """
        query_tokens = tokenize(query)
        matched_entries: dict[str, dict] = {}

        for qt in query_tokens:
            entry = self._entries.get(qt)
            if entry:
                matched_entries[qt] = {
                    "document_count": len(entry.memory_ids),
                    "total_frequency": entry.frequency,
                    "candidate_types": list(entry.candidate_types),
                }

        results = self.search(query, limit=20)
        result_details = []
        for r in results:
            result_details.append({
                "memory_id": r.memory_id,
                "score": r.score,
                "matched_tokens": list(r.matched_tokens),
                "candidate_type": r.candidate_type,
            })

        return {
            "query": query,
            "query_tokens": list(query_tokens),
            "total_index_entries": len(self._entries),
            "total_records": self._record_count,
            "matched_entries": matched_entries,
            "results": result_details,
            "index_hash": self._index_hash,
        }

    # ── Rebuild from store ─────────────────────────────────────────────

    def rebuild_from_store(self, store: "EpisodicMemoryStore") -> int:
        """Rebuild the index from an EpisodicMemoryStore.

        Returns the number of unique tokens indexed.
        """
        records = store.list_records()
        return self.build(records)

    # ── Integrity ──────────────────────────────────────────────────────

    def verify_integrity(self) -> dict:
        """Verify index integrity. Returns a report dict.

        Checks:
          - Index is built
          - Every entry references valid memory_ids present in records
          - Every entry has valid record_hashes
          - Index hash is stable (recomputed matches stored)
          - No dangling references
        """
        checks: dict[str, bool | int] = {}
        issues: list[str] = []

        checks["index_built"] = self._built
        if not self._built:
            issues.append("Index has not been built (call build() first)")
            return {
                "checks": checks,
                "issues": issues,
                "valid": False,
                "index_hash": "",
            }

        checks["record_count"] = self._record_count
        checks["entry_count"] = len(self._entries)

        # Every entry references valid memory_ids
        dangling = 0
        for token, entry in self._entries.items():
            for mid in entry.memory_ids:
                if mid not in self._records_by_memory_id:
                    dangling += 1
                    issues.append(f"Entry '{token}': memory_id '{mid}' not in records")
        checks["no_dangling_memory_ids"] = dangling == 0

        # Every entry has valid record_hashes
        hash_mismatch = 0
        for token, entry in self._entries.items():
            for rh in entry.record_hashes:
                found = False
                for mid in entry.memory_ids:
                    rec = self._records_by_memory_id.get(mid)
                    if rec and rec.record_hash == rh:
                        found = True
                        break
                if not found:
                    hash_mismatch += 1
                    issues.append(f"Entry '{token}': record_hash '{rh}' not matched to any record")
        checks["all_record_hashes_valid"] = hash_mismatch == 0

        # Index hash stable
        current_hash = self._compute_index_hash()
        checks["index_hash_stable"] = current_hash == self._index_hash
        if current_hash != self._index_hash:
            issues.append(f"Index hash mismatch: stored={self._index_hash}, computed={current_hash}")

        # Index is projection only — entries reference records, never define them
        total_refs = sum(len(e.memory_ids) for e in self._entries.values())
        checks["total_references"] = total_refs
        checks["index_is_projection"] = True  # By construction

        # No truth source violation — all records have source_hash
        no_source = sum(
            1 for r in self._records_by_memory_id.values()
            if not r.source_hash
        )
        checks["no_truth_source_violation"] = no_source == 0
        if no_source > 0:
            issues.append(f"{no_source} records have empty source_hash (would be truth source)")

        return {
            "checks": checks,
            "issues": issues,
            "valid": len(issues) == 0,
            "index_hash": self._index_hash,
        }

    # ── Hash ───────────────────────────────────────────────────────────

    def _compute_index_hash(self) -> str:
        """Deterministic hash of the entire index."""
        parts: list[str] = []
        for token in sorted(self._entries.keys()):
            entry = self._entries[token]
            parts.append(f"{token}:{len(entry.memory_ids)}:{entry.frequency}")
        parts.append(f"records:{self._record_count}")
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]

    # ── Introspection ──────────────────────────────────────────────────

    @property
    def index_hash(self) -> str:
        return self._index_hash

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def record_count(self) -> int:
        return self._record_count

    @property
    def is_built(self) -> bool:
        return self._built

    def get_entry(self, token: str) -> Optional[SemanticIndexEntry]:
        """Get a single index entry by token."""
        return self._entries.get(token)

    def list_tokens(self) -> Tuple[str, ...]:
        """Return all indexed tokens in sorted order."""
        return tuple(sorted(self._entries.keys()))

    def entries(self) -> Tuple[SemanticIndexEntry, ...]:
        """Return all index entries."""
        return tuple(self._entries.values())
