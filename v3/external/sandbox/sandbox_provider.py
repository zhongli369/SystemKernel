"""
Sandbox Provider — Abstract interface for sandbox execution backends.

Defines the contract all sandbox providers must fulfill.
Providers execute deterministic code in isolated environments;
results are Evidence-wrapped, never treated as truth.

Inspired by:
  - dagger/dagger: Container-as-function declarative API semantics
  - earthly/earthly: Permission-graded execution matrix
  - OpenHands/OpenHands: Sandbox lifecycle state machine

Stdlib only. No external dependencies. No LLM.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Sandbox Lifecycle State Machine
# ═══════════════════════════════════════════════════════════════════════

SANDBOX_CREATED = "created"
SANDBOX_RUNNING = "running"
SANDBOX_PAUSED = "paused"
SANDBOX_DESTROYED = "destroyed"

ALL_SANDBOX_STATES = (SANDBOX_CREATED, SANDBOX_RUNNING, SANDBOX_PAUSED, SANDBOX_DESTROYED)

# Legal state transitions: created → running → paused → running → destroyed
VALID_TRANSITIONS = {
    SANDBOX_CREATED: (SANDBOX_RUNNING, SANDBOX_DESTROYED),
    SANDBOX_RUNNING: (SANDBOX_PAUSED, SANDBOX_DESTROYED),
    SANDBOX_PAUSED: (SANDBOX_RUNNING, SANDBOX_DESTROYED),
    SANDBOX_DESTROYED: (),
}


def is_valid_transition(from_state: str, to_state: str) -> bool:
    return to_state in VALID_TRANSITIONS.get(from_state, ())


# ═══════════════════════════════════════════════════════════════════════
# Sandbox Environment
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SandboxEnv:
    """Immutable sandbox environment definition.

    Container-as-function semantics: each SandboxEnv describes a
    self-contained execution context. Creating a modified copy returns
    a new SandboxEnv (immutability via dataclass replace).
    """

    image: Optional[str] = None        # container mode: Docker image
    worktree_path: Optional[str] = None  # worktree mode: git worktree path
    env_vars: Tuple[Tuple[str, str], ...] = ()  # (key, value) pairs
    memory_limit_mb: int = 512
    cpu_limit: float = 1.0
    env_id: str = ""

    def with_env(self, key: str, value: str) -> "SandboxEnv":
        """Return a new SandboxEnv with an added environment variable."""
        new_vars = tuple(v for v in self.env_vars if v[0] != key) + ((key, value),)
        return SandboxEnv(
            image=self.image,
            worktree_path=self.worktree_path,
            env_vars=new_vars,
            memory_limit_mb=self.memory_limit_mb,
            cpu_limit=self.cpu_limit,
            env_id=self.env_id,
        )

    def with_image(self, image: str) -> "SandboxEnv":
        """Container-as-function: return new SandboxEnv with image set."""
        return SandboxEnv(
            image=image,
            worktree_path=self.worktree_path,
            env_vars=self.env_vars,
            memory_limit_mb=self.memory_limit_mb,
            cpu_limit=self.cpu_limit,
            env_id=self.env_id,
        )

    def to_dict(self) -> dict:
        return {
            "image": self.image,
            "worktree_path": self.worktree_path,
            "env_vars": [list(v) for v in self.env_vars],
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_limit": self.cpu_limit,
            "env_id": self.env_id,
        }


# ═══════════════════════════════════════════════════════════════════════
# Sandbox Handle
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SandboxHandle:
    """Opaque handle to a running sandbox instance.

    Returned by SandboxProvider.create(). Must be passed to execute()
    and eventually to destroy().
    """

    handle_id: str = ""
    provider_id: str = ""
    backend: str = ""          # "container", "worktree", "process"
    created_at: float = 0.0    # time.time() when created
    state: str = SANDBOX_CREATED

    def to_dict(self) -> dict:
        return {
            "handle_id": self.handle_id,
            "provider_id": self.provider_id,
            "backend": self.backend,
            "created_at": self.created_at,
            "state": self.state,
        }


# ═══════════════════════════════════════════════════════════════════════
# Sandbox Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SandboxResult:
    """Deterministic result of a single sandbox command execution.

    All sandbox output is EVIDENCE, never TRUTH. The evidence_hash
    enables deterministic verification that the same command in the
    same sandbox produces the same output.
    """

    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0
    handle_id: str = ""
    evidence_hash: str = ""   # sha256(handle_id + command + stdout + exit_code)[:16]

    @staticmethod
    def compute_evidence_hash(handle_id: str, command: str, stdout: str, exit_code: int) -> str:
        payload = f"{handle_id}:{command}:{stdout}:{exit_code}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout[:1000],
            "stderr": self.stderr[:1000],
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "handle_id": self.handle_id,
            "evidence_hash": self.evidence_hash,
        }

    @classmethod
    def failed(cls, handle_id: str = "", reason: str = "") -> "SandboxResult":
        return cls(
            stdout="",
            stderr=reason,
            exit_code=1,
            handle_id=handle_id,
        )


# ═══════════════════════════════════════════════════════════════════════
# Sandbox Provider — Abstract Base
# ═══════════════════════════════════════════════════════════════════════

class SandboxProvider(ABC):
    """Abstract sandbox backend contract.

    Each provider implements three operations:
      create(env)   → SandboxHandle    — allocate sandbox
      execute(h, c) → SandboxResult    — run command in sandbox
      destroy(h)    → None             — release resources

    Backends: "container" (Dagger/Earthly), "worktree" (git), "process" (subprocess)
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        ...

    @property
    @abstractmethod
    def supported_backends(self) -> Tuple[str, ...]:
        ...

    @abstractmethod
    def create(self, env: SandboxEnv) -> SandboxHandle:
        """Allocate and prepare a sandbox. Returns a handle."""
        ...

    @abstractmethod
    def execute(
        self,
        handle: SandboxHandle,
        command: str,
        timeout: int = 300,
    ) -> SandboxResult:
        """Run a command inside the sandbox. Returns stdout/stderr/exit_code."""
        ...

    @abstractmethod
    def destroy(self, handle: SandboxHandle) -> None:
        """Release sandbox resources. Idempotent — safe to call on already-destroyed."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider_id={self.provider_id!r})"
