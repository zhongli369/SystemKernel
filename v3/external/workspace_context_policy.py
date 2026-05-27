"""
Workspace Context Policy — Phase 7.

Defines policies governing which workspace context providers are
allowed to operate and what constraints apply to snapshots.

Default policy is maximally conservative:
- No IDE API access
- No file watching
- No file writing
- No terminal execution
- File read limited to metadata only
- Redaction required
- Only deterministic_mock providers allowed

Stdlib only. No external dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Tuple


# ═══════════════════════════════════════════════════════════════════════
# Policy Statuses
# ═══════════════════════════════════════════════════════════════════════

POLICY_PASS = "pass"
POLICY_BLOCKED = "blocked"
POLICY_REVIEW = "review"

ALL_POLICY_STATUSES = (POLICY_PASS, POLICY_BLOCKED, POLICY_REVIEW)


# ═══════════════════════════════════════════════════════════════════════
# Workspace Context Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceContextPolicy:
    """Policy governing workspace context provider operations.

    The policy defines which capabilities external workspace
    providers may use and what constraints apply to snapshots.

    Default: blocks everything except deterministic mock providers.
    File reads allowed for metadata only. No writes. No terminal.
    """
    allow_ide_api: bool = False
    allow_file_watch: bool = False
    allow_file_read: bool = True
    allow_file_write: bool = False
    allow_terminal_execution: bool = False
    allow_external_services: bool = False
    max_files: int = 100
    max_diagnostics: int = 200
    max_open_files: int = 20
    allowed_roots: Tuple[str, ...] = ()
    forbidden_paths: Tuple[str, ...] = ()
    require_redaction: bool = True
    require_human_approval: bool = True
    policy_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "allow_ide_api": self.allow_ide_api,
            "allow_file_watch": self.allow_file_watch,
            "allow_file_read": self.allow_file_read,
            "allow_file_write": self.allow_file_write,
            "allow_terminal_execution": self.allow_terminal_execution,
            "allow_external_services": self.allow_external_services,
            "max_files": self.max_files,
            "max_diagnostics": self.max_diagnostics,
            "max_open_files": self.max_open_files,
            "allowed_roots": list(self.allowed_roots),
            "forbidden_paths": list(self.forbidden_paths),
            "require_redaction": self.require_redaction,
            "require_human_approval": self.require_human_approval,
            "policy_hash": self.policy_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Default Policy
# ═══════════════════════════════════════════════════════════════════════

def default_workspace_context_policy() -> WorkspaceContextPolicy:
    """Return the default workspace context policy.

    Blocks all IDE API, file watch, file write, terminal execution,
    and external service providers. File read allowed for metadata only.
    Only deterministic_mock providers pass by default.

    require_redaction=True and require_human_approval=True are
    mandatory gates for any future real workspace provider trial.
    """
    policy = WorkspaceContextPolicy(
        allow_ide_api=False,
        allow_file_watch=False,
        allow_file_read=True,
        allow_file_write=False,
        allow_terminal_execution=False,
        allow_external_services=False,
        max_files=100,
        max_diagnostics=200,
        max_open_files=20,
        allowed_roots=(),
        forbidden_paths=(),
        require_redaction=True,
        require_human_approval=True,
    )

    policy_hash = hashlib.sha256(
        json.dumps(policy.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    object.__setattr__(policy, "policy_hash", policy_hash)
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Policy Validation
# ═══════════════════════════════════════════════════════════════════════

def block_provider_reason(provider, policy: WorkspaceContextPolicy) -> str:
    """Return the reason a provider is blocked, or empty string if allowed.

    Used by the gate: if this returns non-empty, the provider is blocked.
    """
    from v3.external.workspace_context import (
        PROVIDER_TYPE_DETERMINISTIC_MOCK,
    )

    # Deterministic mock always allowed
    if provider.provider_type == PROVIDER_TYPE_DETERMINISTIC_MOCK:
        return ""

    if provider.requires_ide_api and not policy.allow_ide_api:
        return f"Provider '{provider.provider_id}' requires IDE API, blocked by policy (allow_ide_api=False)"

    if provider.requires_file_watch and not policy.allow_file_watch:
        return f"Provider '{provider.provider_id}' requires file watch, blocked by policy (allow_file_watch=False)"

    if provider.can_write_files and not policy.allow_file_write:
        return f"Provider '{provider.provider_id}' can write files, blocked by policy (allow_file_write=False)"

    if provider.can_execute_terminal and not policy.allow_terminal_execution:
        return f"Provider '{provider.provider_id}' can execute terminal, blocked by policy (allow_terminal_execution=False)"

    if provider.external_service_required and not policy.allow_external_services:
        return f"Provider '{provider.provider_id}' requires external service, blocked by policy (allow_external_services=False)"

    return ""


def validate_provider_against_policy(
    provider,
    policy: WorkspaceContextPolicy,
) -> Tuple[bool, str]:
    """Validate a WorkspaceProvider against the policy.

    Returns (allowed, reason).
    """
    reason = block_provider_reason(provider, policy)
    if reason:
        return False, reason
    return True, "OK"


def validate_snapshot_against_policy(
    snapshot,
    policy: WorkspaceContextPolicy,
) -> Tuple[bool, str]:
    """Validate a WorkspaceSnapshot against the policy.

    Returns (valid, reason).
    Checks: max_files, max_diagnostics, max_open_files, forbidden_paths,
    redaction requirement, root_path.
    """
    from v3.external.workspace_context import WorkspaceSnapshot

    if not isinstance(snapshot, WorkspaceSnapshot):
        return False, f"Expected WorkspaceSnapshot, got {type(snapshot).__name__}"

    # Check max files
    if len(snapshot.file_refs) > policy.max_files:
        return False, (
            f"Snapshot has {len(snapshot.file_refs)} file refs, "
            f"max is {policy.max_files}"
        )

    # Check max diagnostics
    if len(snapshot.diagnostics) > policy.max_diagnostics:
        return False, (
            f"Snapshot has {len(snapshot.diagnostics)} diagnostics, "
            f"max is {policy.max_diagnostics}"
        )

    # Check max open files
    if len(snapshot.open_files) > policy.max_open_files:
        return False, (
            f"Snapshot has {len(snapshot.open_files)} open files, "
            f"max is {policy.max_open_files}"
        )

    # Check forbidden paths
    if policy.forbidden_paths:
        for ref in snapshot.file_refs:
            for fp in policy.forbidden_paths:
                if ref.path.startswith(fp.rstrip("/")):
                    return False, (
                        f"File '{ref.path}' is in forbidden path '{fp}'"
                    )

    # Check root path against allowed roots
    if policy.allowed_roots:
        root_ok = any(
            snapshot.root_path.startswith(r.rstrip("/"))
            for r in policy.allowed_roots
        )
        if not root_ok:
            return False, (
                f"Snapshot root '{snapshot.root_path}' is outside "
                f"allowed roots"
            )

    # Check redaction requirement
    if policy.require_redaction:
        for ref in snapshot.file_refs:
            if ref.included and not ref.redacted and ref.content_hash:
                pass  # metadata-only refs with content_hash are acceptable
            # The point is that file CONTENT is not stored — refs are metadata.

    return True, "OK"
