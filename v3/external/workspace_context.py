"""
Workspace Context Plane — Phase 7.

Defines contracts for external IDE/workspace context providers
(Continue.dev, Cline, Roo Code, VS Code) WITHOUT integrating them.
Workspace providers supply context evidence only — read-only snapshots,
diagnostics summaries, open-file metadata, and git state summaries.

They do NOT control execution, mutate kernel truth, write files,
or execute terminal commands.

All snapshots are EVIDENCE, never TRUTH. All real providers are
disabled/blocked by default policy.

Stdlib only. No LLM. No IDE APIs. No file watching. No terminal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Provider Types
# ═══════════════════════════════════════════════════════════════════════

PROVIDER_TYPE_CONTINUE_LIKE = "continue_like"
PROVIDER_TYPE_CLINE_LIKE = "cline_like"
PROVIDER_TYPE_ROO_LIKE = "roo_like"
PROVIDER_TYPE_VSCODE_LIKE = "vscode_like"
PROVIDER_TYPE_DETERMINISTIC_MOCK = "deterministic_mock"
PROVIDER_TYPE_GENERIC = "generic"

ALL_PROVIDER_TYPES = (
    PROVIDER_TYPE_CONTINUE_LIKE,
    PROVIDER_TYPE_CLINE_LIKE,
    PROVIDER_TYPE_ROO_LIKE,
    PROVIDER_TYPE_VSCODE_LIKE,
    PROVIDER_TYPE_DETERMINISTIC_MOCK,
    PROVIDER_TYPE_GENERIC,
)

# ═══════════════════════════════════════════════════════════════════════
# Diagnostic Severities
# ═══════════════════════════════════════════════════════════════════════

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

ALL_SEVERITIES = (SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_ERROR)


# ═══════════════════════════════════════════════════════════════════════
# Workspace Provider
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceProvider:
    """Description of an external workspace context provider.

    This is a CONTRACT, not an integration. Providers describe what they
    require and what they can do. They do not execute within the kernel.

    truth_source is ALWAYS False. removable is ALWAYS True.
    """
    provider_id: str = ""
    name: str = ""
    provider_type: str = PROVIDER_TYPE_GENERIC
    capability_type: str = "ide"
    execution_mode: str = "inspect_only"
    requires_ide_api: bool = False
    requires_file_watch: bool = False
    can_read_files: bool = False
    can_write_files: bool = False
    can_execute_terminal: bool = False
    external_service_required: bool = False
    truth_source: bool = False
    removable: bool = True
    description: str = ""
    provider_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "provider_type": self.provider_type,
            "capability_type": self.capability_type,
            "execution_mode": self.execution_mode,
            "requires_ide_api": self.requires_ide_api,
            "requires_file_watch": self.requires_file_watch,
            "can_read_files": self.can_read_files,
            "can_write_files": self.can_write_files,
            "can_execute_terminal": self.can_execute_terminal,
            "external_service_required": self.external_service_required,
            "truth_source": self.truth_source,
            "removable": self.removable,
            "description": self.description,
            "provider_hash": self.provider_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Workspace File Ref
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceFileRef:
    """Metadata reference to a workspace file.

    Contains path, language, size, and content hash only.
    Does NOT store file content. included/redacted flags
    indicate whether the file is part of the snapshot context.
    """
    path: str = ""
    language: str = ""
    size_bytes: int = 0
    content_hash: str = ""
    included: bool = True
    redacted: bool = False
    ref_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "content_hash": self.content_hash,
            "included": self.included,
            "redacted": self.redacted,
            "ref_hash": self.ref_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Workspace Diagnostic
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceDiagnostic:
    """A diagnostic message from a workspace provider.

    Summaries only — no full diagnostic content. Diagnostics are
    evidence, not truth. Severity: info | warning | error.
    """
    diagnostic_id: str = ""
    path: str = ""
    severity: str = SEVERITY_INFO
    source: str = ""
    message_summary: str = ""
    line: int = 0
    diagnostic_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "diagnostic_id": self.diagnostic_id,
            "path": self.path,
            "severity": self.severity,
            "source": self.source,
            "message_summary": self.message_summary,
            "line": self.line,
            "diagnostic_hash": self.diagnostic_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Workspace Git State
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceGitState:
    """A read-only summary of git state in the workspace.

    Contains branch, HEAD commit, and counts only. Does NOT
    contain file contents or diffs.
    """
    branch: str = ""
    head_commit: str = ""
    modified_count: int = 0
    untracked_count: int = 0
    staged_count: int = 0
    git_state_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "branch": self.branch,
            "head_commit": self.head_commit,
            "modified_count": self.modified_count,
            "untracked_count": self.untracked_count,
            "staged_count": self.staged_count,
            "git_state_hash": self.git_state_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Workspace Snapshot
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceSnapshot:
    """A read-only snapshot of workspace context.

    Contains file refs (metadata only), diagnostics summaries,
    git state, and open file metadata. No file content. No
    terminal output. No mutations.

    truth_source is ALWAYS False.
    """
    snapshot_id: str = ""
    provider_id: str = ""
    root_path: str = ""
    file_refs: Tuple[WorkspaceFileRef, ...] = ()
    diagnostics: Tuple[WorkspaceDiagnostic, ...] = ()
    git_state: Optional[WorkspaceGitState] = None
    open_files: Tuple[str, ...] = ()
    active_file: str = ""
    risk_flags: Tuple[str, ...] = ()
    truth_source: bool = False
    snapshot_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "provider_id": self.provider_id,
            "root_path": self.root_path,
            "file_refs": [f.to_dict() for f in self.file_refs],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "git_state": self.git_state.to_dict() if self.git_state else None,
            "open_files": list(self.open_files),
            "active_file": self.active_file,
            "risk_flags": list(self.risk_flags),
            "truth_source": self.truth_source,
            "snapshot_hash": self.snapshot_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Workspace Context Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceContextReport:
    """Full report combining provider, snapshot, and evidence."""
    provider: Optional[WorkspaceProvider] = None
    snapshot: Optional[WorkspaceSnapshot] = None
    evidence_bundle_id: str = ""
    policy_status: str = "unknown"
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider.to_dict() if self.provider else None,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "evidence_bundle_id": self.evidence_bundle_id,
            "policy_status": self.policy_status,
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Validation Results
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkspaceValidationResult:
    """Result of validating a workspace context object."""
    valid: bool = True
    target_id: str = ""
    violations: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "target_id": self.target_id,
            "violations": list(self.violations),
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash Helpers
# ═══════════════════════════════════════════════════════════════════════

def _compute_hash(obj) -> str:
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        for key in ("provider_hash", "ref_hash", "diagnostic_hash",
                     "git_state_hash", "snapshot_hash", "report_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Builders
# ═══════════════════════════════════════════════════════════════════════

def make_workspace_file_ref(
    path: str,
    language: str = "",
    size_bytes: int = 0,
    content_hash: str = "",
    included: bool = True,
    redacted: bool = False,
) -> WorkspaceFileRef:
    """Build a deterministic WorkspaceFileRef."""
    ref = WorkspaceFileRef(
        path=path,
        language=language,
        size_bytes=size_bytes,
        content_hash=content_hash or hashlib.sha256(path.encode("utf-8")).hexdigest()[:16],
        included=included,
        redacted=redacted,
    )
    object.__setattr__(ref, "ref_hash", _compute_hash(ref))
    return ref


def make_workspace_diagnostic(
    path: str,
    severity: str = SEVERITY_INFO,
    source: str = "",
    message_summary: str = "",
    line: int = 0,
) -> WorkspaceDiagnostic:
    """Build a deterministic WorkspaceDiagnostic."""
    id_input = f"{path}:{severity}:{source}:{message_summary}:{line}"
    diagnostic_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]
    d = WorkspaceDiagnostic(
        diagnostic_id=diagnostic_id,
        path=path,
        severity=severity,
        source=source,
        message_summary=message_summary,
        line=line,
    )
    object.__setattr__(d, "diagnostic_hash", _compute_hash(d))
    return d


def make_workspace_git_state(
    branch: str = "",
    head_commit: str = "",
    modified_count: int = 0,
    untracked_count: int = 0,
    staged_count: int = 0,
) -> WorkspaceGitState:
    """Build a deterministic WorkspaceGitState."""
    gs = WorkspaceGitState(
        branch=branch,
        head_commit=head_commit,
        modified_count=modified_count,
        untracked_count=untracked_count,
        staged_count=staged_count,
    )
    object.__setattr__(gs, "git_state_hash", _compute_hash(gs))
    return gs


def make_workspace_snapshot(
    provider_id: str,
    root_path: str = "",
    file_refs: Tuple[WorkspaceFileRef, ...] = (),
    diagnostics: Tuple[WorkspaceDiagnostic, ...] = (),
    git_state: Optional[WorkspaceGitState] = None,
    open_files: Tuple[str, ...] = (),
    active_file: str = "",
    risk_flags: Tuple[str, ...] = (),
) -> WorkspaceSnapshot:
    """Build a deterministic WorkspaceSnapshot.

    snapshot_id = hash(provider_id + root_path + sorted file refs).
    All refs/diagnostics sorted deterministically.
    """
    ref_paths = sorted(ref.path for ref in file_refs)
    id_input = f"{provider_id}:{root_path}:{':'.join(ref_paths)}"
    snapshot_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()[:16]

    snapshot = WorkspaceSnapshot(
        snapshot_id=snapshot_id,
        provider_id=provider_id,
        root_path=root_path,
        file_refs=tuple(sorted(file_refs, key=lambda f: f.path)),
        diagnostics=tuple(sorted(diagnostics, key=lambda d: (d.path, d.severity, d.line))),
        git_state=git_state,
        open_files=tuple(sorted(open_files)),
        active_file=active_file,
        risk_flags=risk_flags,
        truth_source=False,
    )
    object.__setattr__(snapshot, "snapshot_hash", _compute_hash(snapshot))
    return snapshot


# ═══════════════════════════════════════════════════════════════════════
# Mock Workspace Snapshot
# ═══════════════════════════════════════════════════════════════════════

def mock_workspace_snapshot(
    provider_id: str = "deterministic_mock_workspace",
    file_count: int = 3,
    diagnostic_count: int = 2,
) -> WorkspaceSnapshot:
    """Generate a deterministic mock workspace snapshot.

    Produces synthetic file refs, diagnostics, and git state from
    fixture-like input. No real IDE API, file watch, or terminal.

    Always deterministic — same input → same snapshot.
    """
    _lang_to_ext = {"python": "py", "markdown": "md", "json": "json", "yaml": "yml", "typescript": "ts"}
    languages = ("python", "markdown", "json", "yaml", "typescript")
    file_refs = []
    for i in range(min(file_count, 10)):
        lang = languages[i % len(languages)]
        ext = _lang_to_ext.get(lang, lang)
        if lang == "markdown":
            path = f"docs/doc_{i}.md"
        elif lang == "json":
            path = f"config/settings_{i}.json"
        else:
            path = f"src/module_{i}.{ext}"
        ref = make_workspace_file_ref(
            path=path,
            language=lang,
            size_bytes=(i + 1) * 1024,
            included=True,
            redacted=False,
        )
        file_refs.append(ref)

    diag_severities = (SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_ERROR)
    diag_sources = ("ruff", "mypy", "eslint")
    diagnostics = []
    for i in range(min(diagnostic_count, 8)):
        ref = file_refs[i % len(file_refs)]
        d = make_workspace_diagnostic(
            path=ref.path,
            severity=diag_severities[i % 3],
            source=diag_sources[i % 3],
            message_summary=f"Mock diagnostic {i + 1} for {ref.path}",
            line=10 + i * 5,
        )
        diagnostics.append(d)

    git_state = make_workspace_git_state(
        branch="master",
        head_commit="a1b2c3d4e5f6a7b8"[:16],
        modified_count=file_count,
        untracked_count=0,
        staged_count=0,
    )

    open_files = tuple(ref.path for ref in file_refs[:2])
    active_file = file_refs[0].path if file_refs else ""

    return make_workspace_snapshot(
        provider_id=provider_id,
        root_path="/mock/workspace",
        file_refs=tuple(file_refs),
        diagnostics=tuple(diagnostics),
        git_state=git_state,
        open_files=open_files,
        active_file=active_file,
        risk_flags=("mock",),
    )


# ═══════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════

def validate_workspace_provider(
    provider: WorkspaceProvider,
) -> WorkspaceValidationResult:
    """Validate a provider against contract rules."""
    violations = []
    if provider.truth_source is not False:
        violations.append(f"Provider {provider.provider_id}: truth_source must be False")
    if provider.removable is not True:
        violations.append(f"Provider {provider.provider_id}: removable must be True")
    if provider.provider_type not in ALL_PROVIDER_TYPES:
        violations.append(f"Unknown provider_type: {provider.provider_type}")
    if not provider.provider_id:
        violations.append("provider_id is empty")
    return WorkspaceValidationResult(
        valid=len(violations) == 0,
        target_id=provider.provider_id,
        violations=tuple(violations),
    )


def validate_workspace_snapshot(
    snapshot: WorkspaceSnapshot,
) -> WorkspaceValidationResult:
    """Validate a snapshot against contract rules."""
    violations = []
    if snapshot.truth_source is not False:
        violations.append(f"Snapshot {snapshot.snapshot_id}: truth_source must be False")
    if not snapshot.snapshot_id:
        violations.append("snapshot_id is empty")
    if not snapshot.provider_id:
        violations.append("provider_id is empty")
    # Check file refs are sorted
    paths = [f.path for f in snapshot.file_refs]
    if paths != sorted(paths):
        violations.append("file_refs must be sorted by path")
    # Check diagnostics are sorted
    diag_keys = [(d.path, d.severity, d.line) for d in snapshot.diagnostics]
    if diag_keys != sorted(diag_keys):
        violations.append("diagnostics must be sorted by (path, severity, line)")
    # Check open files are sorted
    if list(snapshot.open_files) != sorted(snapshot.open_files):
        violations.append("open_files must be sorted")
    return WorkspaceValidationResult(
        valid=len(violations) == 0,
        target_id=snapshot.snapshot_id,
        violations=tuple(violations),
    )


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping
# ═══════════════════════════════════════════════════════════════════════

def workspace_snapshot_to_evidence(
    snapshot: WorkspaceSnapshot,
    registry_hash: str = "",
    adapter_spec_hash: str = "",
):
    """Convert a workspace snapshot into an EvidenceBundle.

    File refs, diagnostics, and git state each become one
    aggregate EvidenceRecord. All records have truth_source=False.
    """
    from v3.external.evidence import (
        EVIDENCE_TYPE_IDE_CONTEXT,
        TRUST_LOW,
        make_evidence_record,
        build_evidence_bundle,
    )

    records = []

    # File refs as one aggregate record
    if snapshot.file_refs:
        file_data = {
            "count": len(snapshot.file_refs),
            "files": [
                {
                    "path": f.path,
                    "language": f.language,
                    "size_bytes": f.size_bytes,
                    "content_hash": f.content_hash,
                }
                for f in snapshot.file_refs
            ],
        }
        records.append(make_evidence_record(
            adapter_id=snapshot.provider_id,
            evidence_type=EVIDENCE_TYPE_IDE_CONTEXT,
            capability_type="ide",
            input_data={"snapshot_id": snapshot.snapshot_id, "root_path": snapshot.root_path},
            output_data={"file_refs": file_data},
            payload_summary=f"workspace file refs: {len(snapshot.file_refs)} files",
            payload_ref="",
            source_uri=f"provider://{snapshot.provider_id}",
            collected_by="systemkernel",
            collection_mode="inspect_only",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            risk_flags=snapshot.risk_flags,
            source_trust_level=TRUST_LOW,
        ))

    # Diagnostics as one aggregate record
    if snapshot.diagnostics:
        diag_data = {
            "count": len(snapshot.diagnostics),
            "by_severity": {
                sev: sum(1 for d in snapshot.diagnostics if d.severity == sev)
                for sev in ALL_SEVERITIES
            },
            "diagnostics": [
                {
                    "diagnostic_id": d.diagnostic_id,
                    "path": d.path,
                    "severity": d.severity,
                    "source": d.source,
                    "message_summary": d.message_summary,
                    "line": d.line,
                }
                for d in snapshot.diagnostics
            ],
        }
        records.append(make_evidence_record(
            adapter_id=snapshot.provider_id,
            evidence_type=EVIDENCE_TYPE_IDE_CONTEXT,
            capability_type="ide",
            input_data={"snapshot_id": snapshot.snapshot_id},
            output_data={"diagnostics": diag_data},
            payload_summary=f"workspace diagnostics: {len(snapshot.diagnostics)} items",
            payload_ref="",
            source_uri=f"provider://{snapshot.provider_id}",
            collected_by="systemkernel",
            collection_mode="inspect_only",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            risk_flags=snapshot.risk_flags,
            source_trust_level=TRUST_LOW,
        ))

    # Git state as one record
    if snapshot.git_state:
        gs = snapshot.git_state
        records.append(make_evidence_record(
            adapter_id=snapshot.provider_id,
            evidence_type=EVIDENCE_TYPE_IDE_CONTEXT,
            capability_type="ide",
            input_data={"snapshot_id": snapshot.snapshot_id},
            output_data={
                "git_state": {
                    "branch": gs.branch,
                    "head_commit": gs.head_commit,
                    "modified_count": gs.modified_count,
                    "untracked_count": gs.untracked_count,
                    "staged_count": gs.staged_count,
                }
            },
            payload_summary=f"git state: branch={gs.branch}, modified={gs.modified_count}",
            payload_ref="",
            source_uri=f"provider://{snapshot.provider_id}",
            collected_by="systemkernel",
            collection_mode="inspect_only",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            risk_flags=snapshot.risk_flags,
            source_trust_level=TRUST_LOW,
        ))

    # Fallback empty record
    if not records:
        records.append(make_evidence_record(
            adapter_id=snapshot.provider_id,
            evidence_type=EVIDENCE_TYPE_IDE_CONTEXT,
            capability_type="ide",
            input_data={"snapshot_id": snapshot.snapshot_id},
            output_data={"status": "empty snapshot"},
            payload_summary="workspace snapshot: empty (no data)",
            payload_ref="",
            source_uri=f"provider://{snapshot.provider_id}",
            collected_by="systemkernel",
            collection_mode="inspect_only",
            adapter_spec_hash=adapter_spec_hash,
            registry_hash=registry_hash,
            source_trust_level=TRUST_LOW,
        ))

    return build_evidence_bundle(tuple(records), bundle_type="workspace_context")


# ═══════════════════════════════════════════════════════════════════════
# Report Builder
# ═══════════════════════════════════════════════════════════════════════

def build_workspace_context_report(
    provider: WorkspaceProvider,
    snapshot: WorkspaceSnapshot,
    evidence_bundle,
    policy_status: str = "unknown",
) -> WorkspaceContextReport:
    """Build a full workspace context report."""
    report = WorkspaceContextReport(
        provider=provider,
        snapshot=snapshot,
        evidence_bundle_id=evidence_bundle.bundle_id if hasattr(evidence_bundle, "bundle_id") else "",
        policy_status=policy_status,
    )
    object.__setattr__(report, "report_hash", _compute_hash(report))
    return report
