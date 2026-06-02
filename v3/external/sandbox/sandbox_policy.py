"""
Sandbox Policy — Permission matrix for sandbox execution.

Defines what a sandbox command is allowed to do. Every sandbox execution
is governed by exactly one SandboxPolicy. Predefined policies follow the
principle of least privilege: defaults deny everything.

Inspired by earthly/earthly permission grading:
  - RUN --network=none    → allow_network = False
  - RUN --no-cache        → deterministic execution
  - RUN --mount-type=cache → cache strategy

Stdlib only. No external dependencies. No LLM.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Risk Levels
# ═══════════════════════════════════════════════════════════════════════

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

ALL_RISK_LEVELS = (RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_CRITICAL)


# ═══════════════════════════════════════════════════════════════════════
# Sandbox Policy
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SandboxPolicy:
    """Immutable permission matrix for a sandbox execution.

    All permissions default to DENY. Each execution must explicitly
    opt into the permissions it needs via a predefined or custom policy.

    require_evidence_wrap is ALWAYS True: sandbox output is evidence,
    never truth.
    """

    policy_id: str = ""
    allow_network: bool = False
    allow_file_write: bool = False
    allowed_paths: Tuple[str, ...] = ()       # blank = deny all writes
    allow_subprocess: bool = False
    max_timeout_seconds: int = 300
    max_memory_mb: int = 512
    require_evidence_wrap: bool = True         # ALWAYS True — enforced
    description: str = ""
    risk_level: str = RISK_LOW
    policy_hash: str = ""

    def __post_init__(self):
        # require_evidence_wrap is always True — invariant
        if not self.require_evidence_wrap:
            object.__setattr__(self, "require_evidence_wrap", True)

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "allow_network": self.allow_network,
            "allow_file_write": self.allow_file_write,
            "allowed_paths": list(self.allowed_paths),
            "allow_subprocess": self.allow_subprocess,
            "max_timeout_seconds": self.max_timeout_seconds,
            "max_memory_mb": self.max_memory_mb,
            "require_evidence_wrap": self.require_evidence_wrap,
            "description": self.description,
            "risk_level": self.risk_level,
            "policy_hash": self.policy_hash,
        }

    def validate_command(self, command: str) -> Tuple[bool, str]:
        """Pre-flight check: does this policy allow the command?

        Checks:
          - Empty command → reject
          - Network keywords (curl, wget, http://, https://) → check allow_network
          - File write keywords (>, >>, tee, dd) → check allow_file_write
          - Path whitelist: if allow_file_write and allowed_paths non-empty,
            command must reference an allowed path
        """
        cmd = command.strip()
        if not cmd:
            return False, "Empty command"

        # Network detection
        _NETWORK_KEYWORDS = ("curl ", "wget ", "http://", "https://", "fetch ", "nc ")
        for kw in _NETWORK_KEYWORDS:
            if kw in cmd:
                if not self.allow_network:
                    return False, f"Network access denied by policy '{self.policy_id}': command contains '{kw}'"
                break

        # File write detection
        _WRITE_KEYWORDS = (" > ", ">> ", "tee ", "dd ")
        has_write = any(kw in cmd for kw in _WRITE_KEYWORDS)
        if has_write:
            if not self.allow_file_write:
                return False, f"File write denied by policy '{self.policy_id}'"
            # Check path whitelist
            if self.allowed_paths:
                path_ok = any(
                    p in cmd for p in self.allowed_paths
                )
                if not path_ok:
                    return False, (
                        f"Write path not in allowed_paths for policy "
                        f"'{self.policy_id}': {self.allowed_paths}"
                    )

        return True, "OK"

    def allows_path(self, path: str) -> bool:
        """Check if a path is in the allowed_paths whitelist."""
        if not self.allowed_paths:
            return False  # blank whitelist = deny all
        return path in self.allowed_paths


# ═══════════════════════════════════════════════════════════════════════
# Hash Helpers
# ═══════════════════════════════════════════════════════════════════════

def _compute_policy_hash(policy: SandboxPolicy) -> str:
    data = policy.to_dict()
    data.pop("policy_hash", None)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Predefined Policies
# ═══════════════════════════════════════════════════════════════════════

def policy_strict() -> SandboxPolicy:
    """Maximum isolation. All permissions denied.

    Use for: executing untrusted or unknown code where safety is paramount.
    Network OFF, file writes OFF, subprocess OFF.
    """
    p = SandboxPolicy(
        policy_id="strict",
        allow_network=False,
        allow_file_write=False,
        allowed_paths=(),
        allow_subprocess=False,
        max_timeout_seconds=60,
        max_memory_mb=256,
        require_evidence_wrap=True,
        description="Maximum isolation — all permissions denied. For untrusted code.",
        risk_level=RISK_LOW,
    )
    object.__setattr__(p, "policy_hash", _compute_policy_hash(p))
    return p


def policy_isolated_build() -> SandboxPolicy:
    """Isolated build sandbox. File writes allowed only in /tmp/build/.

    Use for: dagger/earthly-style containerized builds, compiling code,
    running test suites in isolation.

    Network OFF (build deps should be pre-fetched).
    File writes ON (limited to /tmp/build/).
    Subprocess ON (build tools need it).
    """
    p = SandboxPolicy(
        policy_id="isolated_build",
        allow_network=False,
        allow_file_write=True,
        allowed_paths=("/tmp/build/",),
        allow_subprocess=True,
        max_timeout_seconds=600,
        max_memory_mb=1024,
        require_evidence_wrap=True,
        description="Isolated build — file writes in /tmp/build/, no network. For dagger/earthly builds.",
        risk_level=RISK_MEDIUM,
    )
    object.__setattr__(p, "policy_hash", _compute_policy_hash(p))
    return p


def policy_network_readonly() -> SandboxPolicy:
    """Network GET allowed, no file writes.

    Use for: web scraping tools (crawl4ai, jina-reader, scrapling),
    API fetch operations, package index queries.

    Network ON (GET only, enforced at adapter level).
    File writes OFF.
    Subprocess ON (scrapers may need it).
    """
    p = SandboxPolicy(
        policy_id="network_readonly",
        allow_network=True,
        allow_file_write=False,
        allowed_paths=(),
        allow_subprocess=True,
        max_timeout_seconds=120,
        max_memory_mb=512,
        require_evidence_wrap=True,
        description="Network read-only — GET requests allowed, no file writes. For web scraping tools.",
        risk_level=RISK_MEDIUM,
    )
    object.__setattr__(p, "policy_hash", _compute_policy_hash(p))
    return p


# ═══════════════════════════════════════════════════════════════════════
# Policy Registry
# ═══════════════════════════════════════════════════════════════════════

ALL_PRESET_POLICIES = {
    "strict": policy_strict,
    "isolated_build": policy_isolated_build,
    "network_readonly": policy_network_readonly,
}


def get_policy(policy_id: str) -> Optional[SandboxPolicy]:
    """Look up a preset policy by ID. Returns None if not found."""
    builder = ALL_PRESET_POLICIES.get(policy_id)
    if builder is None:
        return None
    return builder()
