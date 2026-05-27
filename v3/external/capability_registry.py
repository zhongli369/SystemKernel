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
