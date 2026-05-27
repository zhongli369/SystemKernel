"""
Context Engineering Plane — Phase 4.

Formalizes the Repomix context-pack adapter into a Context Engineering
Plane component using:
- Phase 1 Capability Adapter Contract
- Phase 2 Intelligence Plane Registry
- Phase 3 External Evidence Model

Every context pack output is EVIDENCE, never TRUTH.

Planning never executes. Inspection only reads existing files.
Budget policy enforces size/token/file limits before any tool runs.

Stdlib only. No external dependencies. No Repomix execution in tests.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Sensitive Patterns
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_SENSITIVE_PATTERNS: Tuple[str, ...] = (
    "API_KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PRIVATE_KEY",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN PGP PRIVATE KEY BLOCK-----",
    "AUTH_TOKEN",
    "ACCESS_KEY",
    "SECRET_KEY",
)

DEFAULT_EXCLUDED_PATHS: Tuple[str, ...] = (
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".eggs",
    "*.pyc",
)


# ═══════════════════════════════════════════════════════════════════════
# Context Budget Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ContextBudgetPolicy:
    """Budget constraints for context pack generation.

    Enforced before any external tool execution. Oversized or risky
    targets are blocked or flagged for review.
    """
    max_files: int = 500
    max_bytes: int = 10_000_000
    max_tokens: int = 200_000
    allowed_styles: Tuple[str, ...] = ("markdown", "xml", "json", "plain")
    default_style: str = "markdown"
    sensitive_patterns: Tuple[str, ...] = DEFAULT_SENSITIVE_PATTERNS
    excluded_paths: Tuple[str, ...] = DEFAULT_EXCLUDED_PATHS
    require_subdir_target: bool = True
    allow_repo_root: bool = False
    policy_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "max_files": self.max_files,
            "max_bytes": self.max_bytes,
            "max_tokens": self.max_tokens,
            "allowed_styles": list(self.allowed_styles),
            "default_style": self.default_style,
            "sensitive_patterns": list(self.sensitive_patterns),
            "excluded_paths": list(self.excluded_paths),
            "require_subdir_target": self.require_subdir_target,
            "allow_repo_root": self.allow_repo_root,
            "policy_hash": self.policy_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Budget Status
# ═══════════════════════════════════════════════════════════════════════

BUDGET_PASS = "pass"
BUDGET_REVIEW = "review"
BUDGET_BLOCKED = "blocked"
ALL_BUDGET_STATUSES = (BUDGET_PASS, BUDGET_REVIEW, BUDGET_BLOCKED)


# ═══════════════════════════════════════════════════════════════════════
# Budget Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BudgetValidationResult:
    """Result of validating a plan or inspection against budget policy."""
    status: str = BUDGET_PASS  # pass | review | blocked
    violations: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    result_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "violations": list(self.violations),
            "warnings": list(self.warnings),
            "result_hash": self.result_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Context Pack Plan
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ContextPackPlan:
    """A planned context pack operation. Never executes a command.

    Contains the deterministic command string, budget estimates, and
    budget status. The plan is EVIDENCE, not truth.
    """
    adapter_id: str = "repomix_context_pack"
    target_path: str = ""
    output_path: str = ""
    style: str = "markdown"
    command: str = ""
    estimated_files: int = 0
    estimated_bytes: int = 0
    estimated_tokens: int = 0
    budget_status: str = BUDGET_PASS
    warnings: Tuple[str, ...] = ()
    plan_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "target_path": self.target_path,
            "output_path": self.output_path,
            "style": self.style,
            "command": self.command,
            "estimated_files": self.estimated_files,
            "estimated_bytes": self.estimated_bytes,
            "estimated_tokens": self.estimated_tokens,
            "budget_status": self.budget_status,
            "warnings": list(self.warnings),
            "plan_hash": self.plan_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Context Pack Inspection
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ContextPackInspection:
    """Inspection of an existing context pack output file. Read-only.

    Reports size, structure, sensitive pattern hits, and a deterministic
    pack hash. The inspection is EVIDENCE, not truth.
    """
    output_path: str = ""
    size_bytes: int = 0
    line_count: int = 0
    token_estimate: int = 0
    detected_sections: Tuple[str, ...] = ()
    sensitive_pattern_hits: Tuple[str, ...] = ()
    included_files: Tuple[str, ...] = ()
    pack_hash: str = ""
    inspection_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "output_path": self.output_path,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "token_estimate": self.token_estimate,
            "detected_sections": list(self.detected_sections),
            "sensitive_pattern_hits": list(self.sensitive_pattern_hits),
            "included_files": list(self.included_files),
            "pack_hash": self.pack_hash,
            "inspection_hash": self.inspection_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Context Engineering Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ContextEngineeringReport:
    """Full context engineering report — plan + inspection + evidence.

    Combines the plan, inspection, and evidence bundle into one report.
    truth_source is ALWAYS False.
    """
    adapter_id: str = "repomix_context_pack"
    plan: Optional[ContextPackPlan] = None
    inspection: Optional[ContextPackInspection] = None
    evidence_bundle_id: str = ""
    budget_status: str = BUDGET_PASS
    truth_source: bool = False
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "adapter_id": self.adapter_id,
            "plan": self.plan.to_dict() if self.plan else None,
            "inspection": self.inspection.to_dict() if self.inspection else None,
            "evidence_bundle_id": self.evidence_bundle_id,
            "budget_status": self.budget_status,
            "truth_source": self.truth_source,
            "report_hash": self.report_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Hash Helpers
# ═══════════════════════════════════════════════════════════════════════

def _compute_hash(obj) -> str:
    """Deterministic SHA-256 hash for context plane objects."""
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        for key in ("plan_hash", "inspection_hash", "report_hash",
                     "policy_hash", "result_hash"):
            data.pop(key, None)
    elif isinstance(obj, dict):
        data = obj
    else:
        data = str(obj)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _resolve_root() -> str:
    external_dir = os.path.dirname(os.path.abspath(__file__))
    v3_dir = os.path.dirname(external_dir)
    return os.path.dirname(v3_dir)


def _resolve_absolute(target: str) -> str:
    if os.path.isabs(target):
        return os.path.normpath(target)
    root = _resolve_root()
    return os.path.normpath(os.path.join(root, target))


def _is_repo_root(target: str) -> bool:
    root = _resolve_root()
    v3_root = os.path.join(root, "v3")
    abs_target = _resolve_absolute(target)
    return abs_target == os.path.normpath(root) or abs_target == os.path.normpath(v3_root)


# ═══════════════════════════════════════════════════════════════════════
# Default Policy
# ═══════════════════════════════════════════════════════════════════════

def default_context_budget_policy() -> ContextBudgetPolicy:
    """Return the default context budget policy.

    - 500 files max, 10MB max, 200K tokens max
    - Markdown/xml/json/plain styles allowed
    - Repo root blocked by default (require_subdir_target=True)
    - Sensitive pattern detection active
    """
    policy = ContextBudgetPolicy()
    object.__setattr__(policy, "policy_hash", _compute_hash(policy))
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Budget Validation
# ═══════════════════════════════════════════════════════════════════════

def validate_context_budget(
    plan_or_inspection,
    policy: ContextBudgetPolicy,
) -> BudgetValidationResult:
    """Validate a ContextPackPlan or ContextPackInspection against budget policy.

    Returns a BudgetValidationResult with status and any violations/warnings.
    """
    violations = []
    warnings = []

    if isinstance(plan_or_inspection, ContextPackPlan):
        obj = plan_or_inspection
        est_files = obj.estimated_files
        est_bytes = obj.estimated_bytes
        est_tokens = obj.estimated_tokens

        # Style check (plan only)
        if obj.style not in policy.allowed_styles:
            violations.append(
                f"Unsupported style '{obj.style}'. Allowed: {policy.allowed_styles}"
            )

        # Repo root check (plan only)
        if policy.require_subdir_target and not policy.allow_repo_root:
            if _is_repo_root(obj.target_path):
                violations.append(
                    "REPO_ROOT_BLOCKED: target is the repository root. "
                    "Specify a subdirectory or set allow_repo_root=True."
                )

    elif isinstance(plan_or_inspection, ContextPackInspection):
        obj = plan_or_inspection
        est_files = len(obj.included_files)
        est_bytes = obj.size_bytes
        est_tokens = obj.token_estimate
    else:
        return BudgetValidationResult(
            status=BUDGET_BLOCKED,
            violations=(f"Unknown type: {type(plan_or_inspection).__name__}",),
        )

    # File count check
    if est_files > policy.max_files:
        violations.append(
            f"File count {est_files} exceeds max {policy.max_files}"
        )
    elif est_files > policy.max_files * 0.8:
        warnings.append(
            f"File count {est_files} near max {policy.max_files} (80% threshold)"
        )

    # Byte size check
    if est_bytes > policy.max_bytes:
        violations.append(
            f"Estimated size {est_bytes:,} bytes exceeds max {policy.max_bytes:,}"
        )
    elif est_bytes > policy.max_bytes * 0.8:
        warnings.append(
            f"Estimated size {est_bytes:,} bytes near max {policy.max_bytes:,} (80% threshold)"
        )

    # Token estimate check
    if est_tokens > policy.max_tokens:
        violations.append(
            f"Token estimate {est_tokens:,} exceeds max {policy.max_tokens:,}"
        )
    elif est_tokens > policy.max_tokens * 0.8:
        warnings.append(
            f"Token estimate {est_tokens:,} near max {policy.max_tokens:,} (80% threshold)"
        )

    # Determine status
    if violations:
        status = BUDGET_BLOCKED
    elif warnings:
        status = BUDGET_REVIEW
    else:
        status = BUDGET_PASS

    result = BudgetValidationResult(
        status=status,
        violations=tuple(violations),
        warnings=tuple(warnings),
    )
    object.__setattr__(result, "result_hash", _compute_hash(result))
    return result


# ═══════════════════════════════════════════════════════════════════════
# Planning
# ═══════════════════════════════════════════════════════════════════════

def plan_context_pack(
    target: str,
    output: str = "",
    style: str = "markdown",
    policy: Optional[ContextBudgetPolicy] = None,
) -> ContextPackPlan:
    """Plan a context pack operation. NEVER executes a command.

    Uses the existing context_pack adapter to estimate size/files/tokens,
    then validates against the budget policy.
    """
    from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

    if policy is None:
        policy = default_context_budget_policy()

    if not output:
        output = f"{target.rstrip('/').rstrip('\\')}.ctx.md"

    if style not in policy.allowed_styles:
        plan = ContextPackPlan(
            adapter_id="repomix_context_pack",
            target_path=target,
            output_path=output,
            style=style,
            command="",
            budget_status=BUDGET_BLOCKED,
            warnings=(f"Unsupported style '{style}'. Allowed: {policy.allowed_styles}",),
        )
        object.__setattr__(plan, "plan_hash", _compute_hash(plan))
        return plan

    config = ContextPackConfig(
        target_path=target,
        output_path=output,
        style=style,
        max_bytes=policy.max_bytes,
        max_tokens=policy.max_tokens,
        allow_repo_root=policy.allow_repo_root,
    )
    adapter_result = ContextPackAdapter.plan(config)

    estimated_files = len(adapter_result.included_files)
    estimated_bytes = adapter_result.size_bytes
    estimated_tokens = adapter_result.token_estimate

    plan = ContextPackPlan(
        adapter_id="repomix_context_pack",
        target_path=target,
        output_path=output,
        style=style,
        command=adapter_result.command if adapter_result.status == "planned" else "",
        estimated_files=estimated_files,
        estimated_bytes=estimated_bytes,
        estimated_tokens=estimated_tokens,
        budget_status=BUDGET_PASS,
        warnings=adapter_result.warnings,
    )

    # Validate against budget
    budget = validate_context_budget(plan, policy)
    object.__setattr__(plan, "budget_status", budget.status)

    if budget.violations:
        all_warnings = list(plan.warnings) + list(budget.violations)
        object.__setattr__(plan, "warnings", tuple(all_warnings))
    elif budget.warnings:
        all_warnings = list(plan.warnings) + list(budget.warnings)
        object.__setattr__(plan, "warnings", tuple(all_warnings))

    object.__setattr__(plan, "plan_hash", _compute_hash(plan))
    return plan


# ═══════════════════════════════════════════════════════════════════════
# Inspection
# ═══════════════════════════════════════════════════════════════════════

def inspect_context_pack(
    path: str,
    policy: Optional[ContextBudgetPolicy] = None,
) -> ContextPackInspection:
    """Inspect an existing context pack output file. Read-only.

    Reads the file, extracts metadata, checks for sensitive patterns,
    and computes a deterministic inspection hash.
    """
    from v3.external.context_pack import ContextPackAdapter

    if policy is None:
        policy = default_context_budget_policy()

    abs_path = _resolve_absolute(path)

    if not os.path.exists(abs_path):
        return ContextPackInspection(
            output_path=path,
            inspection_hash=_compute_hash({"path": path, "status": "not_found"}),
        )

    adapter_result = ContextPackAdapter.inspect_output(path)

    # Read file content for sensitive pattern scan
    sensitive_hits = []
    sections = []
    try:
        with open(abs_path, encoding="utf-8") as f:
            content = f.read()

        for pattern in policy.sensitive_patterns:
            if pattern in content:
                # Report which pattern matched, not the value
                sensitive_hits.append(pattern)

        # Detect sections (## markers in markdown)
        for line in content.split("\n"):
            if line.startswith("## ") and not line.startswith("## File:"):
                sections.append(line[3:].strip())
    except (OSError, UnicodeDecodeError):
        pass

    inspection = ContextPackInspection(
        output_path=path,
        size_bytes=adapter_result.size_bytes,
        line_count=adapter_result.line_count,
        token_estimate=adapter_result.token_estimate,
        detected_sections=tuple(sections),
        sensitive_pattern_hits=tuple(sensitive_hits),
        included_files=adapter_result.included_files,
        pack_hash=adapter_result.pack_hash,
    )
    object.__setattr__(inspection, "inspection_hash", _compute_hash(inspection))
    return inspection


# ═══════════════════════════════════════════════════════════════════════
# Evidence Mapping
# ═══════════════════════════════════════════════════════════════════════

def context_pack_to_evidence(
    plan: ContextPackPlan,
    inspection: ContextPackInspection,
    registry_hash: str = "",
    adapter_spec_hash: str = "",
):
    """Convert a context pack plan + inspection into an EvidenceBundle.

    The bundle contains two evidence records (plan + inspection).
    Both records have truth_source=False.
    """
    from v3.external.evidence import (
        EVIDENCE_TYPE_CONTEXT_PACK,
        TRUST_MEDIUM,
        EvidenceBundle,
        make_evidence_record,
        build_evidence_bundle,
    )

    plan_record = make_evidence_record(
        adapter_id=plan.adapter_id,
        evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
        capability_type="context",
        input_data={"target": plan.target_path, "output": plan.output_path, "style": plan.style},
        output_data={
            "command": plan.command,
            "estimated_files": plan.estimated_files,
            "estimated_bytes": plan.estimated_bytes,
            "estimated_tokens": plan.estimated_tokens,
            "budget_status": plan.budget_status,
        },
        payload_summary=f"plan: {plan.target_path} → {plan.output_path} ({plan.estimated_files} files, {plan.estimated_bytes:,} bytes)",
        payload_ref=plan.output_path,
        source_uri=plan.target_path,
        collected_by="systemkernel",
        collection_mode="inspect_only",
        adapter_spec_hash=adapter_spec_hash,
        registry_hash=registry_hash,
        confidence=0.95,
        source_trust_level=TRUST_MEDIUM,
    )

    inspection_record = make_evidence_record(
        adapter_id=plan.adapter_id,
        evidence_type=EVIDENCE_TYPE_CONTEXT_PACK,
        capability_type="context",
        input_data={"path": inspection.output_path},
        output_data={
            "size_bytes": inspection.size_bytes,
            "line_count": inspection.line_count,
            "token_estimate": inspection.token_estimate,
            "sections": list(inspection.detected_sections),
            "sensitive_hits": list(inspection.sensitive_pattern_hits),
            "pack_hash": inspection.pack_hash,
        },
        payload_summary=f"inspect: {inspection.output_path} ({inspection.size_bytes:,} bytes, {inspection.line_count} lines)",
        payload_ref=inspection.output_path,
        source_uri=inspection.output_path,
        collected_by="systemkernel",
        collection_mode="inspect_only",
        adapter_spec_hash=adapter_spec_hash,
        registry_hash=registry_hash,
        risk_flags=_sensitive_to_risk_flags(inspection.sensitive_pattern_hits),
        confidence=0.95,
        source_trust_level=TRUST_MEDIUM,
    )

    return build_evidence_bundle((plan_record, inspection_record), bundle_type="context_pack")


def _sensitive_to_risk_flags(sensitive_hits: Tuple[str, ...]) -> Tuple[str, ...]:
    """Map sensitive pattern hits to evidence risk flags."""
    if not sensitive_hits:
        return ()
    from v3.external.evidence_policy import RISK_FLAG_UNVERIFIED
    return (RISK_FLAG_UNVERIFIED,)


# ═══════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════

def build_context_engineering_report(
    plan: ContextPackPlan,
    inspection: ContextPackInspection,
    evidence_bundle,
) -> ContextEngineeringReport:
    """Build a full context engineering report from plan + inspection + evidence.

    truth_source is ALWAYS False.
    """
    budget_status = BUDGET_PASS
    if plan.budget_status == BUDGET_BLOCKED:
        budget_status = BUDGET_BLOCKED
    elif plan.budget_status == BUDGET_REVIEW or inspection.sensitive_pattern_hits:
        budget_status = BUDGET_REVIEW

    report = ContextEngineeringReport(
        adapter_id=plan.adapter_id,
        plan=plan,
        inspection=inspection,
        evidence_bundle_id=evidence_bundle.bundle_id,
        budget_status=budget_status,
        truth_source=False,
    )
    object.__setattr__(report, "report_hash", _compute_hash(report))
    return report


def write_context_report(report: ContextEngineeringReport, path: str) -> str:
    """Write a context engineering report to a JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)
    return os.path.abspath(path)


# ═══════════════════════════════════════════════════════════════════════
# Compatibility: ContextPackResult → ContextPackPlan
# ═══════════════════════════════════════════════════════════════════════

def plan_from_context_pack_result(
    result,  # ContextPackResult
    policy: Optional[ContextBudgetPolicy] = None,
) -> ContextPackPlan:
    """Convert an existing ContextPackResult (Phase 7C) into a ContextPackPlan.

    This is a compatibility bridge — new code should use plan_context_pack()
    directly.
    """
    if policy is None:
        policy = default_context_budget_policy()

    budget_status = BUDGET_PASS
    if result.status == "blocked":
        budget_status = BUDGET_BLOCKED
    elif result.warnings:
        budget_status = BUDGET_REVIEW

    plan = ContextPackPlan(
        adapter_id="repomix_context_pack",
        target_path=result.target_path,
        output_path=result.output_path,
        style="markdown",
        command=result.command,
        estimated_files=len(result.included_files),
        estimated_bytes=result.size_bytes,
        estimated_tokens=result.token_estimate,
        budget_status=budget_status,
        warnings=result.warnings,
    )
    object.__setattr__(plan, "plan_hash", _compute_hash(plan))
    return plan
