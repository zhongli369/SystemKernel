"""
Workspace Context Provider Profiles — Phase 7.

Defines disabled/blocked profiles for future IDE/workspace context
providers (Continue.dev, Cline, Roo Code, VS Code) and one allowed
mock provider for deterministic testing.

Profiles are DESCRIPTIONS, not integrations. No provider imports,
executes, or connects to IDE APIs.

All profiles: truth_source=False, removable=True.

Default policy blocks all real workspace providers. Only
deterministic_mock passes the gate under default policy.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


def _compute_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Profile Status Cache
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceProfileStatus:
    """Cached status of a workspace provider profile under a given policy."""
    provider_id: str = ""
    allowed: bool = False
    reason: str = ""
    status_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "status_hash": self.status_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Provider Profile Builders
# ═══════════════════════════════════════════════════════════════════════

def _build_provider(
    provider_id: str,
    name: str,
    provider_type: str,
    requires_ide_api: bool = False,
    requires_file_watch: bool = False,
    can_read_files: bool = False,
    can_write_files: bool = False,
    can_execute_terminal: bool = False,
    external_service_required: bool = False,
    description: str = "",
) -> "WorkspaceProvider":
    """Build a deterministic workspace provider with hash."""
    from v3.external.workspace_context import (
        WorkspaceProvider,
        _compute_hash as ws_hash,
    )

    provider = WorkspaceProvider(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        capability_type="ide",
        execution_mode="inspect_only",
        requires_ide_api=requires_ide_api,
        requires_file_watch=requires_file_watch,
        can_read_files=can_read_files,
        can_write_files=can_write_files,
        can_execute_terminal=can_execute_terminal,
        external_service_required=external_service_required,
        truth_source=False,
        removable=True,
        description=description,
    )
    object.__setattr__(provider, "provider_hash", ws_hash(provider))
    return provider


# ═══════════════════════════════════════════════════════════════════════
# Continue.dev Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def continue_workspace_profile() -> "WorkspaceProvider":
    """Continue.dev workspace context provider profile.

    BLOCKED by default policy:
    - requires_ide_api=True  →  blocked (allow_ide_api=False)
    - can_read_files=True  →  allowed (allow_file_read=True, metadata only)
    - can_write_files=True  →  blocked (allow_file_write=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — Continue.dev is not integrated.
    """
    return _build_provider(
        provider_id="continue_workspace_context",
        name="Continue.dev Workspace Context",
        provider_type="continue_like",
        requires_ide_api=True,
        requires_file_watch=False,
        can_read_files=True,
        can_write_files=True,
        can_execute_terminal=False,
        external_service_required=True,
        description=(
            "External workspace context provider using Continue.dev. "
            "Requires IDE API and external service. "
            "Can read and write files. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Cline Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def cline_workspace_profile() -> "WorkspaceProvider":
    """Cline workspace context provider profile.

    BLOCKED by default policy:
    - requires_ide_api=True  →  blocked (allow_ide_api=False)
    - can_read_files=True  →  allowed (allow_file_read=True)
    - can_write_files=True  →  blocked (allow_file_write=False)
    - can_execute_terminal=True  →  blocked (allow_terminal_execution=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — Cline is not integrated.
    """
    return _build_provider(
        provider_id="cline_workspace_context",
        name="Cline Workspace Context",
        provider_type="cline_like",
        requires_ide_api=True,
        requires_file_watch=False,
        can_read_files=True,
        can_write_files=True,
        can_execute_terminal=True,
        external_service_required=True,
        description=(
            "External workspace context provider using Cline. "
            "Requires IDE API, can execute terminal, and external service. "
            "Can read and write files. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Roo Code Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def roo_workspace_profile() -> "WorkspaceProvider":
    """Roo Code workspace context provider profile.

    BLOCKED by default policy:
    - requires_ide_api=True  →  blocked (allow_ide_api=False)
    - can_read_files=True  →  allowed (allow_file_read=True)
    - can_write_files=True  →  blocked (allow_file_write=False)
    - can_execute_terminal=True  →  blocked (allow_terminal_execution=False)
    - external_service_required=True  →  blocked (allow_external_services=False)

    This is a PLACEHOLDER profile — Roo Code is not integrated.
    """
    return _build_provider(
        provider_id="roo_workspace_context",
        name="Roo Code Workspace Context",
        provider_type="roo_like",
        requires_ide_api=True,
        requires_file_watch=False,
        can_read_files=True,
        can_write_files=True,
        can_execute_terminal=True,
        external_service_required=True,
        description=(
            "External workspace context provider using Roo Code. "
            "Requires IDE API, can execute terminal, and external service. "
            "Can read and write files. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# VS Code Profile (BLOCKED by default)
# ═══════════════════════════════════════════════════════════════════════

def vscode_workspace_profile() -> "WorkspaceProvider":
    """VS Code workspace context provider profile.

    BLOCKED by default policy:
    - requires_ide_api=True  →  blocked (allow_ide_api=False)
    - requires_file_watch=True  →  blocked (allow_file_watch=False)
    - can_write_files=True  →  blocked (allow_file_write=False)
    - can_execute_terminal=True  →  blocked (allow_terminal_execution=False)

    VS Code extension API does not require external service by default,
    but file watching and terminal are capabilities that need gate.

    This is a PLACEHOLDER profile — VS Code extension API is not integrated.
    """
    return _build_provider(
        provider_id="vscode_workspace_context",
        name="VS Code Workspace Context",
        provider_type="vscode_like",
        requires_ide_api=True,
        requires_file_watch=True,
        can_read_files=True,
        can_write_files=True,
        can_execute_terminal=True,
        external_service_required=False,
        description=(
            "External workspace context provider using VS Code API. "
            "Requires IDE API and file watching. "
            "Can read and write files, execute terminal. "
            "BLOCKED by default policy. NOT integrated."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Deterministic Mock Profile (ALLOWED by default)
# ═══════════════════════════════════════════════════════════════════════

def deterministic_mock_workspace_profile() -> "WorkspaceProvider":
    """Deterministic mock workspace context provider profile.

    ALLOWED by default policy:
    - requires_ide_api=False  →  passes
    - requires_file_watch=False  →  passes
    - can_read_files=True  →  passes
    - can_write_files=False  →  passes
    - can_execute_terminal=False  →  passes
    - external_service_required=False  →  passes

    Used for testing the workspace context plane. Always deterministic.
    """
    return _build_provider(
        provider_id="deterministic_mock_workspace",
        name="Deterministic Mock Workspace Context",
        provider_type="deterministic_mock",
        requires_ide_api=False,
        requires_file_watch=False,
        can_read_files=True,
        can_write_files=False,
        can_execute_terminal=False,
        external_service_required=False,
        description=(
            "Deterministic mock workspace context provider. "
            "Produces synthetic workspace snapshots from fixture input. "
            "Used for testing the workspace context plane. "
            "Always deterministic — same input → same output. "
            "ALLOWED by default policy."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Profile Registry
# ═══════════════════════════════════════════════════════════════════════

def get_all_profiles() -> Tuple["WorkspaceProvider", ...]:
    """Return all registered workspace provider profiles.

    Sorted by provider_id for determinism.
    """
    profiles = (
        continue_workspace_profile(),
        cline_workspace_profile(),
        roo_workspace_profile(),
        vscode_workspace_profile(),
        deterministic_mock_workspace_profile(),
    )
    return tuple(sorted(profiles, key=lambda p: p.provider_id))


def get_profile(provider_id: str) -> Optional["WorkspaceProvider"]:
    """Get a single provider profile by ID. Returns None if not found."""
    for p in get_all_profiles():
        if p.provider_id == provider_id:
            return p
    return None


def evaluate_all_profiles(policy) -> Tuple[WorkspaceProfileStatus, ...]:
    """Evaluate all workspace profiles against a policy.

    Returns tuple of WorkspaceProfileStatus, sorted by provider_id.
    """
    from v3.external.workspace_context_policy import validate_provider_against_policy

    results = []
    for p in get_all_profiles():
        allowed, reason = validate_provider_against_policy(p, policy)
        status = WorkspaceProfileStatus(
            provider_id=p.provider_id,
            allowed=allowed,
            reason=reason if not allowed else "OK",
        )
        object.__setattr__(status, "status_hash", _compute_hash(status.to_dict()))
        results.append(status)

    return tuple(sorted(results, key=lambda s: s.provider_id))
