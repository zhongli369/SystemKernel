"""
ToolAdapter — Unified external tool invocation protocol.

All tool adapters implement this abstract base.
ZERO LLM dependency. Sync execution only.
Event-driven notifications via EventBus (optional).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolInvocation:
    """Input to a tool adapter."""
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    cwd: str = "."
    timeout_s: int = 300


@dataclass(frozen=True)
class ToolResult:
    """Output from a tool adapter."""
    tool_name: str
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: int = 0
    truncated: bool = False


class ToolAdapter(ABC):
    """Unified tool invocation protocol.

    Design:
      - All tools look the same from ExecutionEngine perspective
      - Sync execution (no async for kernel tools — deterministic)
      - ZERO LLM in tool invocation
      - health_check() verifies tool availability

    Subclass and implement:
      - invoke(ToolInvocation) -> ToolResult
      - health_check() -> bool
      - tool_name -> str (property)
    """

    @abstractmethod
    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        """Execute the tool. Must be sync and deterministic."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Verify the tool is available and functional."""
        ...

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Unique tool identifier."""
        ...


# ═══════════════════════════════════════════════════════════════════════
# Built-in: Shell Adapter (wraps subprocess.run)
# ═══════════════════════════════════════════════════════════════════════

class ShellAdapter(ToolAdapter):
    """Adapter for arbitrary shell commands via subprocess.run."""

    tool_name = "shell"

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        import subprocess
        import time

        cmd = invocation.args.get("cmd", [])
        if isinstance(cmd, str):
            cmd = cmd.split()

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=invocation.timeout_s,
                cwd=invocation.cwd,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            output = proc.stdout + "\n" + proc.stderr
            truncated = len(output) > 50000
            return ToolResult(
                tool_name="shell",
                success=proc.returncode == 0,
                stdout=proc.stdout[:50000],
                stderr=proc.stderr[:50000],
                exit_code=proc.returncode,
                duration_ms=elapsed,
                truncated=truncated,
            )
        except FileNotFoundError:
            return ToolResult(
                tool_name="shell", success=False,
                stderr=f"Command not found: {cmd[0] if cmd else '?'}",
                exit_code=127,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="shell", success=False,
                stderr=f"Timeout after {invocation.timeout_s}s",
                exit_code=124,
                duration_ms=invocation.timeout_s * 1000,
            )

    def health_check(self) -> bool:
        import subprocess
        try:
            subprocess.run(["echo", "ok"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False
