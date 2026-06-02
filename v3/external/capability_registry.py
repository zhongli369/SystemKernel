"""
Capability Registry — Phase 2.

Unified read-only registry for all external capability adapters.
Standardizes listing, querying, auditing, and lifecycle gating.

Uses Phase 1 contract types. All updates return new frozen registries.
Stdlib only. No external dependencies. No external tool execution.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

from v3.external.capability_contract import (
    CapabilityRiskLevel,
    CapabilityType,
    ExternalCapabilityAdapterSpec,
    compute_stable_hash,
)
from v3.external.capability_lifecycle import (
    STATE_APPROVED,
    STATE_DISABLED,
    CapabilityLifecycleRecord,
)


# ═══════════════════════════════════════════════════════════════════════
# Registry Entry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityRegistryEntry:
    """One entry in the capability registry.

    Wraps an ExternalCapabilityAdapterSpec with lifecycle state,
    enablement, maturity, and ownership metadata.
    """
    adapter_id: str = ""
    spec: Optional[ExternalCapabilityAdapterSpec] = None
    lifecycle_state: str = "proposed"
    enabled: bool = False
    maturity: str = "experimental"   # experimental | stable | deprecated
    execution_mode_default: str = "dry_run"
    approval_required: bool = True
    owner: str = ""
    notes: str = ""
    entry_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "spec": self.spec.to_dict() if self.spec else None,
            "lifecycle_state": self.lifecycle_state,
            "enabled": self.enabled,
            "maturity": self.maturity,
            "execution_mode_default": self.execution_mode_default,
            "approval_required": self.approval_required,
            "owner": self.owner,
            "notes": self.notes,
            "entry_hash": self.entry_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityRegistry:
    """Immutable registry of all external capability adapters.

    Entries are sorted deterministically by adapter_id.
    All mutation functions return NEW registries.
    """
    entries: Tuple[CapabilityRegistryEntry, ...] = ()
    registry_hash: str = ""
    enabled_count: int = 0
    disabled_count: int = 0
    approved_count: int = 0
    high_risk_count: int = 0

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "registry_hash": self.registry_hash,
            "enabled_count": self.enabled_count,
            "disabled_count": self.disabled_count,
            "approved_count": self.approved_count,
            "high_risk_count": self.high_risk_count,
        }


# ═══════════════════════════════════════════════════════════════════════
# Builders
# ═══════════════════════════════════════════════════════════════════════

def _compute_counts(entries: Tuple[CapabilityRegistryEntry, ...]) -> dict:
    """Compute aggregate counts for a set of entries."""
    enabled = sum(1 for e in entries if e.enabled)
    disabled = sum(1 for e in entries if not e.enabled)
    approved = sum(1 for e in entries if e.lifecycle_state == STATE_APPROVED)
    high_risk = sum(
        1 for e in entries
        if e.spec and e.spec.risk_level == CapabilityRiskLevel.high.value
    )
    return {
        "enabled_count": enabled,
        "disabled_count": disabled,
        "approved_count": approved,
        "high_risk_count": high_risk,
    }


def build_registry(
    entries: Tuple[CapabilityRegistryEntry, ...],
) -> CapabilityRegistry:
    """Build an immutable registry from a set of entries.

    Entries are sorted deterministically by adapter_id.
    Raises ValueError on duplicate adapter_ids.
    """
    # Check for duplicates
    seen = set()
    for entry in entries:
        if entry.adapter_id in seen:
            raise ValueError(f"Duplicate adapter_id: {entry.adapter_id}")
        seen.add(entry.adapter_id)

    # Sort deterministically
    sorted_entries = tuple(sorted(entries, key=lambda e: e.adapter_id))

    counts = _compute_counts(sorted_entries)

    # Compute registry hash
    hash_input = json.dumps(
        [e.entry_hash for e in sorted_entries],
        sort_keys=True, ensure_ascii=False,
    )
    registry_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return CapabilityRegistry(
        entries=sorted_entries,
        registry_hash=registry_hash,
        **counts,
    )


# ═══════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════

def validate_registry(registry: CapabilityRegistry) -> Tuple[bool, Tuple[str, ...]]:
    """Validate a registry against contract rules.

    Returns (valid, errors).
    """
    errors = []

    # Check for duplicates
    ids = [e.adapter_id for e in registry.entries]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate adapter_ids in registry")

    # Check sort order
    if list(ids) != sorted(ids):
        errors.append("Entries not sorted by adapter_id")

    for entry in registry.entries:
        if not entry.adapter_id or not entry.adapter_id.strip():
            errors.append(f"Entry with empty adapter_id: {entry.entry_hash}")

        # Critical risk must be disabled unless approved
        if entry.spec and entry.spec.risk_level == CapabilityRiskLevel.critical.value:
            if entry.enabled and entry.lifecycle_state != STATE_APPROVED:
                errors.append(
                    f"Critical risk adapter '{entry.adapter_id}' is enabled "
                    f"but not approved (state: {entry.lifecycle_state})"
                )

        # explicit_execute requires approval
        if entry.spec and entry.execution_mode_default == "explicit_execute":
            if not entry.approval_required:
                errors.append(
                    f"Adapter '{entry.adapter_id}' has explicit_execute default "
                    f"but approval_required is False"
                )

    return len(errors) == 0, tuple(errors)


# ═══════════════════════════════════════════════════════════════════════
# Queries
# ═══════════════════════════════════════════════════════════════════════

def get_entry(
    registry: CapabilityRegistry,
    adapter_id: str,
) -> Optional[CapabilityRegistryEntry]:
    """Get a registry entry by adapter_id. Returns None if not found."""
    for entry in registry.entries:
        if entry.adapter_id == adapter_id:
            return entry
    return None


def list_by_type(
    registry: CapabilityRegistry,
    capability_type: str,
) -> Tuple[CapabilityRegistryEntry, ...]:
    """List all entries of a given capability type."""
    return tuple(
        e for e in registry.entries
        if e.spec and e.spec.capability_type == capability_type
    )


def list_enabled(
    registry: CapabilityRegistry,
) -> Tuple[CapabilityRegistryEntry, ...]:
    """List all enabled entries."""
    return tuple(e for e in registry.entries if e.enabled)


def list_requires_approval(
    registry: CapabilityRegistry,
) -> Tuple[CapabilityRegistryEntry, ...]:
    """List all entries that require approval for execution."""
    return tuple(e for e in registry.entries if e.approval_required)


def list_by_lifecycle(
    registry: CapabilityRegistry,
    state: str,
) -> Tuple[CapabilityRegistryEntry, ...]:
    """List all entries in a given lifecycle state."""
    return tuple(e for e in registry.entries if e.lifecycle_state == state)


def list_high_risk(
    registry: CapabilityRegistry,
) -> Tuple[CapabilityRegistryEntry, ...]:
    """List all high-risk entries."""
    return tuple(
        e for e in registry.entries
        if e.spec and e.spec.risk_level in (
            CapabilityRiskLevel.high.value,
            CapabilityRiskLevel.critical.value,
        )
    )


# ═══════════════════════════════════════════════════════════════════════
# Phase 16c: CapabilitySelector — Context-aware selection
# ═══════════════════════════════════════════════════════════════════════

TASK_TYPES = (
    "code_generation",
    "context_gathering",
    "security_scan",
    "memory_query",
    "cost_analysis",
    "execution_orchestration",
    # L2 Tool Interface task types (Phase 16c)
    "code",
    "review",
    "research",
    "build",
    "security",
)

# Task → relevant capability types (deterministic mapping)
TASK_CAPABILITY_MAP = {
    "code_generation":          ("context", "agent", "tool"),
    "context_gathering":        ("context", "tool", "usage"),
    "security_scan":            ("tool", "eval", "quality"),
    "memory_query":             ("memory", "agent"),
    "cost_analysis":            ("usage", "tool"),
    "execution_orchestration":  ("agent", "tool", "eval"),
    # L2 Tool Interface: high-level task categories (cline-inspired)
    "code":                     ("context", "skill", "tool"),
    "review":                   ("context", "quality", "tool"),
    "research":                 ("context", "direction", "tool"),
    "build":                    ("context", "tool", "agent", "sandbox"),
    "security":                 ("tool", "eval", "quality"),
}

# Safety baseline per capability type (0-1, deterministic)
SAFETY_BASELINE = {
    "context": 0.8,
    "memory": 0.6,
    "agent": 0.4,
    "ide": 0.5,
    "eval": 0.7,
    "skill": 0.9,
    "usage": 0.9,
    "tool": 0.5,
    "direction": 0.8,
    "quality": 0.8,
    "sandbox": 0.6,
    "lifecycle": 0.9,
    "observability": 0.9,
}

# Estimated cost per capability type (USD baseline)
COST_ESTIMATE = {
    "context": 0.01,
    "memory": 0.05,
    "agent": 0.10,
    "ide": 0.02,
    "eval": 0.01,
    "skill": 0.005,
    "usage": 0.005,
    "tool": 0.02,
    "direction": 0.01,
    "quality": 0.01,
    "sandbox": 0.03,
    "lifecycle": 0.005,
    "observability": 0.005,
}


@dataclass(frozen=True)
class TaskContext:
    """Immutable task description for capability selection."""
    task_type: str = "code_generation"
    risk_level: str = "low"
    network_allowed: bool = False
    file_write_allowed: bool = False
    estimated_duration_s: int = 60

    def __post_init__(self):
        if self.task_type not in TASK_TYPES:
            raise ValueError(f"Unknown task_type: {self.task_type}. Must be one of {TASK_TYPES}")

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "risk_level": self.risk_level,
            "network_allowed": self.network_allowed,
            "file_write_allowed": self.file_write_allowed,
            "estimated_duration_s": self.estimated_duration_s,
        }


@dataclass(frozen=True)
class CapabilityScore:
    """Scored capability result from selection."""
    capability_id: str = ""
    capability_type: str = ""
    relevance: float = 0.0
    safety: float = 0.0
    cost_estimate: float = 0.0
    composite_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "capability_type": self.capability_type,
            "relevance": round(self.relevance, 4),
            "safety": round(self.safety, 4),
            "cost_estimate": round(self.cost_estimate, 6),
            "composite_score": round(self.composite_score, 4),
        }


class CapabilitySelector:
    """Deterministic capability selector.

    Filters by task type, scores by relevance+safety+cost, ranks top-N.
    No LLM. No probabilistic selection. Same input → same output.
    """

    @staticmethod
    def select(
        registry: CapabilityRegistry,
        task: TaskContext,
        top_n: int = 5,
    ) -> Tuple[CapabilityScore, ...]:
        """Select top-N capabilities for a given task context.

        Pipeline:
          1. Filter: enabled + task_type match
          2. Score: relevance*0.5 + safety*0.3 + (1-cost/max_cost)*0.2
          3. Sort: composite_score descending
          4. Take top-N
        """
        relevant_types = TASK_CAPABILITY_MAP.get(task.task_type, ("tool",))
        candidates = []

        for entry in registry.entries:
            if not entry.enabled:
                continue
            if not entry.spec:
                continue
            ctype = entry.spec.capability_type
            if ctype not in relevant_types:
                continue
            # Network/filter constraints
            if task.network_allowed is False and getattr(entry.spec, "requires_network", False):
                continue

            candidates.append(entry)

        if not candidates:
            return ()

        return CapabilitySelector._score_and_rank(candidates, top_n)

    @staticmethod
    def _score_and_rank(
        candidates: list[CapabilityRegistryEntry],
        top_n: int,
    ) -> Tuple[CapabilityScore, ...]:
        scores = []
        max_cost = max(
            (COST_ESTIMATE.get(e.spec.capability_type if e.spec else "tool", 0.02)
             for e in candidates),
            default=0.01,
        )

        for entry in candidates:
            ctype = entry.spec.capability_type if entry.spec else "tool"
            relevance = 0.8 if ctype in TASK_CAPABILITY_MAP.get("code_generation", ()) else 0.5
            safety = SAFETY_BASELINE.get(ctype, 0.5)

            # Adjust safety for risk level
            if entry.spec and entry.spec.risk_level == "high":
                safety *= 0.7
            elif entry.spec and entry.spec.risk_level == "critical":
                safety *= 0.3
            if entry.maturity == "stable":
                safety *= 1.1
            elif entry.maturity == "experimental":
                safety *= 0.9

            cost = COST_ESTIMATE.get(ctype, 0.02)
            cost_factor = 1.0 - (cost / max(max_cost, 0.001))
            cost_factor = max(0.0, min(1.0, cost_factor))

            composite = relevance * 0.5 + safety * 0.3 + cost_factor * 0.2
            composite = max(0.0, min(1.0, composite))

            scores.append(CapabilityScore(
                capability_id=entry.adapter_id,
                capability_type=ctype,
                relevance=relevance,
                safety=round(safety, 4),
                cost_estimate=cost,
                composite_score=round(composite, 4),
            ))

        scores.sort(key=lambda s: s.composite_score, reverse=True)
        return tuple(scores[:top_n])


# ═══════════════════════════════════════════════════════════════════════
# Phase 16c: CapabilityDedup — Duplicate detection
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DuplicateGroup:
    """A group of capabilities that appear to be duplicates."""
    reason: str = ""               # "same_command", "type_overlap", "same_provider"
    entries: Tuple[str, ...] = ()  # adapter_ids
    recommended_action: str = ""   # "review", "keep_higher_safety", "keep_newer"

    def to_dict(self) -> dict:
        return {
            "reason": self.reason,
            "entries": list(self.entries),
            "recommended_action": self.recommended_action,
        }


class CapabilityDedup:
    """Detect duplicate or overlapping capabilities.

    Rules:
      1. Same command → definite duplicate
      2. Same capability_type + provider_id → same provider, different entries
      3. Same capability_type + overlapping functions → suspicious
    """

    @staticmethod
    def find_duplicates(
        registry: CapabilityRegistry,
    ) -> Tuple[DuplicateGroup, ...]:
        groups = []

        # Rule 1: Same capability_type + overlapping adapter_id prefix
        prefix_map: dict[str, list[str]] = {}
        for entry in registry.entries:
            if entry.spec:
                # Extract provider prefix from adapter_id (e.g. "repomix_context_pack" → "repomix")
                parts = entry.adapter_id.split("_")
                prefix = parts[0] if parts else entry.adapter_id
                key = f"{entry.spec.capability_type}:{prefix}"
                if key not in prefix_map:
                    prefix_map[key] = []
                prefix_map[key].append(entry.adapter_id)
        for key, ids in prefix_map.items():
            if len(ids) > 1:
                groups.append(DuplicateGroup(
                    reason="type_overlap",
                    entries=tuple(sorted(ids)),
                    recommended_action="review",
                ))

        # Rule 2: Same name prefix (different entries from same provider)
        name_map: dict[str, list[str]] = {}
        for entry in registry.entries:
            prefix = entry.adapter_id.split("_")[0] if "_" in entry.adapter_id else entry.adapter_id
            if prefix not in name_map:
                name_map[prefix] = []
            name_map[prefix].append(entry.adapter_id)
        for prefix, ids in name_map.items():
            if len(ids) > 1:
                groups.append(DuplicateGroup(
                    reason="same_provider",
                    entries=tuple(sorted(ids)),
                    recommended_action="keep_higher_safety",
                ))

        return tuple(groups)

    @staticmethod
    def dedup_strategy(group: DuplicateGroup, registry: CapabilityRegistry) -> str:
        """Determine which entry to keep from a duplicate group.

        Returns the recommended adapter_id to keep.
        """
        entries = [get_entry(registry, aid) for aid in group.entries]
        entries = [e for e in entries if e is not None]
        if not entries:
            return ""

        if group.recommended_action == "keep_higher_safety":
            best = max(entries, key=lambda e: (
                e.enabled,
                e.maturity == "stable",
                SAFETY_BASELINE.get(e.spec.capability_type if e.spec else "tool", 0.5),
            ))
            return best.adapter_id

        if group.recommended_action == "keep_newer":
            best = max(entries, key=lambda e: (
                e.enabled,
                e.maturity == "stable",
            ))
            return best.adapter_id

        # Default: keep first enabled, then first stable
        for e in entries:
            if e.enabled:
                return e.adapter_id
        return entries[0].adapter_id


# ═══════════════════════════════════════════════════════════════════════
# Phase 16c: CapabilityConflict — Conflict detection
# ═══════════════════════════════════════════════════════════════════════

# Priority ordering for conflict resolution
CONFLICT_PRIORITY = {
    "governance": 0,
    "context": 1,
    "memory": 2,
    "agent": 3,
    "voice": 4,
    "tool": 5,
    "sandbox": 6,
    "lifecycle": 7,
    "observability": 8,
    "eval": 9,
    "skill": 10,
    "usage": 11,
    "quality": 12,
    "direction": 13,
    "ide": 14,
}


@dataclass(frozen=True)
class Conflict:
    """A detected conflict between two capabilities."""
    capability_a: str = ""
    capability_b: str = ""
    conflict_type: str = ""        # "resource", "permission", "output_slot"
    description: str = ""
    resolution: str = ""           # recommended resolution

    def to_dict(self) -> dict:
        return {
            "capability_a": self.capability_a,
            "capability_b": self.capability_b,
            "conflict_type": self.conflict_type,
            "description": self.description,
            "resolution": self.resolution,
        }


class CapabilityConflict:
    """Detect conflicts between enabled capabilities.

    Rules:
      1. Resource conflict: both need same port/temp dir/file lock
      2. Permission conflict: contradictory network/file requirements
      3. Output slot conflict: same capability_type, different providers
    """

    @staticmethod
    def detect(registry: CapabilityRegistry) -> Tuple[Conflict, ...]:
        conflicts = []
        enabled = [e for e in registry.entries if e.enabled and e.spec]

        for i, a in enumerate(enabled):
            for b in enabled[i + 1:]:
                # Permission conflict: contradictory network requirements
                if (getattr(a.spec, "requires_network", False) !=
                        getattr(b.spec, "requires_network", False)):
                    if a.spec.capability_type == b.spec.capability_type:
                        conflicts.append(Conflict(
                            capability_a=a.adapter_id,
                            capability_b=b.adapter_id,
                            conflict_type="permission",
                            description=f"Network requirements differ for same type "
                                        f"({a.spec.capability_type})",
                            resolution=CapabilityConflict._resolve(a, b),
                        ))

                # Output slot conflict: same type + different adapter sources
                if a.spec.capability_type == b.spec.capability_type:
                    a_provider = a.adapter_id.split("_")[0] if "_" in a.adapter_id else a.adapter_id
                    b_provider = b.adapter_id.split("_")[0] if "_" in b.adapter_id else b.adapter_id
                    if a_provider != b_provider:
                        conflicts.append(Conflict(
                            capability_a=a.adapter_id,
                            capability_b=b.adapter_id,
                            conflict_type="output_slot",
                            description=f"Same capability type ({a.spec.capability_type}) "
                                        f"with different providers",
                            resolution=CapabilityConflict._resolve(a, b),
                        ))

        return tuple(conflicts)

    @staticmethod
    def _resolve(
        a: CapabilityRegistryEntry,
        b: CapabilityRegistryEntry,
    ) -> str:
        """Resolve a conflict by priority + safety.

        Lower priority number wins. Tiebreak: higher safety score.
        """
        type_a = a.spec.capability_type if a.spec else "tool"
        type_b = b.spec.capability_type if b.spec else "tool"
        pri_a = CONFLICT_PRIORITY.get(type_a, 99)
        pri_b = CONFLICT_PRIORITY.get(type_b, 99)

        if pri_a < pri_b:
            return f"Prefer {a.adapter_id} (higher priority: {type_a} < {type_b})"
        elif pri_b < pri_a:
            return f"Prefer {b.adapter_id} (higher priority: {type_b} < {type_a})"
        else:
            safety_a = SAFETY_BASELINE.get(type_a, 0.5)
            safety_b = SAFETY_BASELINE.get(type_b, 0.5)
            if safety_a >= safety_b:
                return f"Prefer {a.adapter_id} (same priority, higher safety)"
            else:
                return f"Prefer {b.adapter_id} (same priority, higher safety)"


# ═══════════════════════════════════════════════════════════════════════
# Mutations (return NEW registry)
# ═══════════════════════════════════════════════════════════════════════

def _replace_entry(
    registry: CapabilityRegistry,
    adapter_id: str,
    new_entry: CapabilityRegistryEntry,
) -> CapabilityRegistry:
    """Replace one entry in the registry, returning a new registry."""
    new_entries_list = []
    for e in registry.entries:
        if e.adapter_id == adapter_id:
            new_entries_list.append(new_entry)
        else:
            new_entries_list.append(e)
    return build_registry(tuple(new_entries_list))


def disable_entry(
    registry: CapabilityRegistry,
    adapter_id: str,
    reason: str = "",
) -> CapabilityRegistry:
    """Disable an entry. Returns new registry. Raises KeyError if not found."""
    entry = get_entry(registry, adapter_id)
    if entry is None:
        raise KeyError(f"Entry not found: {adapter_id}")

    new_entry = CapabilityRegistryEntry(
        adapter_id=entry.adapter_id,
        spec=entry.spec,
        lifecycle_state=STATE_DISABLED,
        enabled=False,
        maturity=entry.maturity,
        execution_mode_default="disabled",
        approval_required=True,
        owner=entry.owner,
        notes=f"Disabled: {reason}" if reason else "Disabled",
    )
    object.__setattr__(new_entry, "entry_hash",
                       compute_stable_hash({"adapter_id": adapter_id, "state": "disabled"}))
    return _replace_entry(registry, adapter_id, new_entry)


def enable_entry(
    registry: CapabilityRegistry,
    adapter_id: str,
    reason: str = "",
) -> CapabilityRegistry:
    """Enable an entry. Returns new registry. Raises KeyError if not found."""
    entry = get_entry(registry, adapter_id)
    if entry is None:
        raise KeyError(f"Entry not found: {adapter_id}")

    new_entry = CapabilityRegistryEntry(
        adapter_id=entry.adapter_id,
        spec=entry.spec,
        lifecycle_state=entry.lifecycle_state,
        enabled=True,
        maturity=entry.maturity,
        execution_mode_default=entry.execution_mode_default,
        approval_required=entry.approval_required,
        owner=entry.owner,
        notes=f"Enabled: {reason}" if reason else entry.notes,
    )
    object.__setattr__(new_entry, "entry_hash",
                       compute_stable_hash({"adapter_id": adapter_id, "state": "enabled"}))
    return _replace_entry(registry, adapter_id, new_entry)


# ═══════════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════════

def write_registry(registry: CapabilityRegistry, path: str) -> str:
    """Write registry to JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)
    return os.path.abspath(path)


def load_registry(path: str) -> CapabilityRegistry:
    """Load registry from JSON file. Returns CapabilityRegistry."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    entries = []
    for e_data in data.get("entries", []):
        spec_data = e_data.get("spec")
        spec = ExternalCapabilityAdapterSpec(**spec_data) if spec_data else None
        entry = CapabilityRegistryEntry(
            adapter_id=e_data.get("adapter_id", ""),
            spec=spec,
            lifecycle_state=e_data.get("lifecycle_state", "proposed"),
            enabled=e_data.get("enabled", False),
            maturity=e_data.get("maturity", "experimental"),
            execution_mode_default=e_data.get("execution_mode_default", "dry_run"),
            approval_required=e_data.get("approval_required", True),
            owner=e_data.get("owner", ""),
            notes=e_data.get("notes", ""),
            entry_hash=e_data.get("entry_hash", ""),
        )
        entries.append(entry)

    return CapabilityRegistry(
        entries=tuple(entries),
        registry_hash=data.get("registry_hash", ""),
        enabled_count=data.get("enabled_count", 0),
        disabled_count=data.get("disabled_count", 0),
        approved_count=data.get("approved_count", 0),
        high_risk_count=data.get("high_risk_count", 0),
    )
