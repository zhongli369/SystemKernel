"""
L1 Sandbox Execution Environment — Phase 14c-2.

Sandbox abstraction layer for deterministic, policy-governed code execution.
Defines provider contracts, permission policies, and adapter interfaces for
external sandbox backends (Dagger, Earthly, Git Worktree).

All sandbox results are EvidenceRecord-wrapped with truth_source=False.
No container runtime is implemented here — only CLI-based adapters.
No LLM execution in sandbox — strictly for deterministic code.
"""

from v3.external.sandbox.sandbox_provider import (
    SandboxProvider,
    SandboxEnv,
    SandboxHandle,
    SandboxResult,
)

from v3.external.sandbox.sandbox_policy import (
    SandboxPolicy,
    policy_strict,
    policy_isolated_build,
    policy_network_readonly,
)

from v3.external.sandbox.sandbox_adapter import (
    DaggerSandboxAdapter,
    EarthlySandboxAdapter,
    WorktreeSandboxAdapter,
    execute_sandbox,
)
