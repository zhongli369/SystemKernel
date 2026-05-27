"""
Agent Worker Policy — Phase 6.

Defines policies governing which agent worker providers are allowed
to operate and what types of tasks/proposals they may produce.

Default policy is maximally conservative:
- No LLM-based providers
- No network access
- No file modification
- No command execution
- Sandbox required
- Human approval required for any execution
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
# Agent Worker Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentWorkerPolicy:
    """Policy governing agent worker provider operations.

    The policy defines which capabilities external agent worker
    providers may use and what constraints apply to tasks and results.

    Default: blocks everything except deterministic mock providers.
    All real agent workers require human approval.
    """
    allow_llm_providers: bool = False
    allow_network: bool = False
    allow_file_modification: bool = False
    allow_command_execution: bool = False
    allow_external_services: bool = False
    require_sandbox: bool = True
    require_human_approval: bool = True
    max_runtime_seconds: int = 300
    max_proposals: int = 10
    allowed_paths: Tuple[str, ...] = ()
    forbidden_paths: Tuple[str, ...] = ()
    policy_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "allow_llm_providers": self.allow_llm_providers,
            "allow_network": self.allow_network,
            "allow_file_modification": self.allow_file_modification,
            "allow_command_execution": self.allow_command_execution,
            "allow_external_services": self.allow_external_services,
            "require_sandbox": self.require_sandbox,
            "require_human_approval": self.require_human_approval,
            "max_runtime_seconds": self.max_runtime_seconds,
            "max_proposals": self.max_proposals,
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "policy_hash": self.policy_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Default Policy
# ═══════════════════════════════════════════════════════════════════════

def default_agent_worker_policy() -> AgentWorkerPolicy:
    """Return the default agent worker policy.

    Blocks all LLM, network, file modification, command execution,
    and external service providers. Only deterministic_mock providers
    pass by default.

    require_sandbox=True and require_human_approval=True are the
    mandatory gates for any future real agent worker trial.
    """
    policy = AgentWorkerPolicy(
        allow_llm_providers=False,
        allow_network=False,
        allow_file_modification=False,
        allow_command_execution=False,
        allow_external_services=False,
        require_sandbox=True,
        require_human_approval=True,
        max_runtime_seconds=300,
        max_proposals=10,
        allowed_paths=(),
        forbidden_paths=(),
    )

    policy_hash = hashlib.sha256(
        json.dumps(policy.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    object.__setattr__(policy, "policy_hash", policy_hash)
    return policy


# ═══════════════════════════════════════════════════════════════════════
# Policy Validation
# ═══════════════════════════════════════════════════════════════════════

def block_provider_reason(provider, policy: AgentWorkerPolicy) -> str:
    """Return the reason a provider is blocked, or empty string if allowed.

    Used by the gate: if this returns non-empty, the provider is blocked.
    """
    from v3.external.agent_worker import (
        PROVIDER_TYPE_DETERMINISTIC_MOCK,
    )

    # Deterministic mock always allowed
    if provider.provider_type == PROVIDER_TYPE_DETERMINISTIC_MOCK:
        return ""

    if provider.requires_llm and not policy.allow_llm_providers:
        return f"Provider '{provider.provider_id}' requires LLM, blocked by policy (allow_llm_providers=False)"

    if provider.requires_network and not policy.allow_network:
        return f"Provider '{provider.provider_id}' requires network, blocked by policy (allow_network=False)"

    if provider.can_modify_files and not policy.allow_file_modification:
        return f"Provider '{provider.provider_id}' can modify files, blocked by policy (allow_file_modification=False)"

    if provider.can_execute_commands and not policy.allow_command_execution:
        return f"Provider '{provider.provider_id}' can execute commands, blocked by policy (allow_command_execution=False)"

    if provider.external_service_required and not policy.allow_external_services:
        return f"Provider '{provider.provider_id}' requires external service, blocked by policy (allow_external_services=False)"

    return ""


def validate_provider_against_policy(
    provider,
    policy: AgentWorkerPolicy,
) -> Tuple[bool, str]:
    """Validate an AgentWorkerProvider against the policy.

    Returns (allowed, reason).
    """
    reason = block_provider_reason(provider, policy)
    if reason:
        return False, reason
    return True, "OK"


def validate_task_against_policy(
    task,
    policy: AgentWorkerPolicy,
) -> Tuple[bool, str]:
    """Validate an AgentWorkerTask against the policy.

    Returns (valid, reason).
    Checks: allowed_paths, forbidden_paths, max_runtime_seconds,
    dry_run enforcement, human approval.
    """
    from v3.external.agent_worker import AgentWorkerTask

    if not isinstance(task, AgentWorkerTask):
        return False, f"Expected AgentWorkerTask, got {type(task).__name__}"

    # dry_run must always be True unless human approval is explicitly given
    if not task.dry_run and policy.require_human_approval:
        return False, (
            f"Task '{task.task_id}': dry_run=False requires explicit "
            f"human approval (require_human_approval=True)"
        )

    # Check runtime
    if task.max_runtime_seconds > policy.max_runtime_seconds:
        return False, (
            f"Task '{task.task_id}': max_runtime_seconds "
            f"({task.max_runtime_seconds}) exceeds policy limit "
            f"({policy.max_runtime_seconds})"
        )

    # Check forbidden paths — if task allowed_paths overlap with policy forbidden_paths
    if policy.forbidden_paths:
        for ap in task.allowed_paths:
            for fp in policy.forbidden_paths:
                if ap.startswith(fp.rstrip("/")) or fp.startswith(ap.rstrip("/")):
                    return False, (
                        f"Task '{task.task_id}': allowed_path '{ap}' "
                        f"conflicts with forbidden_path '{fp}'"
                    )

    # Check allowed_paths — if policy has an allowlist, task paths must be within it
    if policy.allowed_paths:
        for ap in task.allowed_paths:
            ok = any(
                ap.startswith(p.rstrip("/")) or p.startswith(ap.rstrip("/"))
                for p in policy.allowed_paths
            )
            if not ok:
                return False, (
                    f"Task '{task.task_id}': allowed_path '{ap}' "
                    f"is outside policy allowed_paths"
                )

    return True, "OK"


def validate_result_against_policy(
    result,
    policy: AgentWorkerPolicy,
) -> Tuple[bool, str]:
    """Validate an AgentWorkerResult against the policy.

    Returns (valid, reason).
    Checks: max_proposals, blocked results, truth_source.
    """
    from v3.external.agent_worker import AgentWorkerResult, STATUS_BLOCKED

    if not isinstance(result, AgentWorkerResult):
        return False, f"Expected AgentWorkerResult, got {type(result).__name__}"

    # Blocked results are valid — just empty
    if result.status == STATUS_BLOCKED:
        return True, "OK"

    # Check max proposals
    if len(result.proposals) > policy.max_proposals:
        return False, (
            f"Result has {len(result.proposals)} proposals, "
            f"max is {policy.max_proposals}"
        )

    return True, "OK"


# ═══════════════════════════════════════════════════════════════════════
# Policy Evaluation
# ═══════════════════════════════════════════════════════════════════════

def evaluate_task_policy(
    task,
    provider,
    policy: AgentWorkerPolicy,
) -> Tuple[bool, str]:
    """Full evaluation of a task against policy, including provider check.

    Returns (allowed, reason). Checks provider first, then task.
    """
    provider_ok, reason = validate_provider_against_policy(provider, policy)
    if not provider_ok:
        return False, reason

    task_ok, reason = validate_task_against_policy(task, policy)
    if not task_ok:
        return False, reason

    return True, "OK"
