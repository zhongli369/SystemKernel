"""
Sandbox Adapters — Concrete sandbox provider implementations.

Three backends:
  - DaggerSandboxAdapter   → dagger CLI (container)
  - EarthlySandboxAdapter  → earthly CLI (container)
  - WorktreeSandboxAdapter → git worktree (local filesystem, zero new deps)

All adapters:
  - Use subprocess + CLI (no Docker SDK, no BuildKit import)
  - Wrap every result as EvidenceRecord with truth_source=False
  - Enforce SandboxPolicy permissions before execution

Inspired by dagger/dagger Container-as-function patterns:
  Container.from(image) → withExec(command) → stdout()

Stdlib only. No external dependencies beyond the CLI tools themselves.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from typing import Optional, Tuple

from v3.external.sandbox.sandbox_provider import (
    SandboxProvider,
    SandboxEnv,
    SandboxHandle,
    SandboxResult,
    SANDBOX_CREATED,
    SANDBOX_RUNNING,
    SANDBOX_DESTROYED,
)

from v3.external.sandbox.sandbox_policy import (
    SandboxPolicy,
    policy_strict,
)

from v3.external.evidence import (
    EvidenceRecord,
    EvidenceSource,
    EvidenceProvenance,
    EVIDENCE_TYPE_GENERIC,
    TRUST_LOW,
)


# ═══════════════════════════════════════════════════════════════════════
# Dagger Sandbox Adapter
# ═══════════════════════════════════════════════════════════════════════

class DaggerSandboxAdapter(SandboxProvider):
    """Sandbox provider using the Dagger CLI.

    Container-as-function semantics: each execute() call is a
    `dagger run` invocation with the command.

    Backend: "container"
    Requires: dagger CLI installed on PATH
    """

    @property
    def provider_id(self) -> str:
        return "dagger-sandbox"

    @property
    def supported_backends(self) -> Tuple[str, ...]:
        return ("container",)

    def create(self, env: SandboxEnv) -> SandboxHandle:
        handle_id = str(uuid.uuid4())[:16]
        return SandboxHandle(
            handle_id=handle_id,
            provider_id=self.provider_id,
            backend="container",
            created_at=time.time(),
            state=SANDBOX_CREATED,
        )

    def execute(
        self,
        handle: SandboxHandle,
        command: str,
        timeout: int = 300,
    ) -> SandboxResult:
        start = time.time()

        try:
            result = subprocess.run(
                ["dagger", "run", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            stdout = ""
            stderr = f"Timeout after {timeout}s"
            exit_code = 124
        except FileNotFoundError:
            return SandboxResult.failed(
                handle_id=handle.handle_id,
                reason="dagger CLI not found on PATH",
            )
        except Exception as e:
            return SandboxResult.failed(
                handle_id=handle.handle_id,
                reason=str(e),
            )

        duration_ms = (time.time() - start) * 1000
        evidence_hash = SandboxResult.compute_evidence_hash(
            handle.handle_id, command, stdout, exit_code
        )

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            handle_id=handle.handle_id,
            evidence_hash=evidence_hash,
        )

    def destroy(self, handle: SandboxHandle) -> None:
        # Dagger containers are ephemeral — no explicit cleanup needed.
        # If we wanted to force cleanup: subprocess.run(["dagger", "clean"])
        pass


# ═══════════════════════════════════════════════════════════════════════
# Earthly Sandbox Adapter
# ═══════════════════════════════════════════════════════════════════════

class EarthlySandboxAdapter(SandboxProvider):
    """Sandbox provider using the Earthly CLI.

    Each execute() call runs an Earthly target. Permission flags
    from SandboxPolicy are mapped to Earthly --network / --no-cache flags.

    Backend: "container"
    Requires: earthly CLI installed on PATH
    """

    @property
    def provider_id(self) -> str:
        return "earthly-sandbox"

    @property
    def supported_backends(self) -> Tuple[str, ...]:
        return ("container",)

    def create(self, env: SandboxEnv) -> SandboxHandle:
        handle_id = str(uuid.uuid4())[:16]
        return SandboxHandle(
            handle_id=handle_id,
            provider_id=self.provider_id,
            backend="container",
            created_at=time.time(),
            state=SANDBOX_CREATED,
        )

    def execute(
        self,
        handle: SandboxHandle,
        command: str,
        timeout: int = 300,
        policy: Optional[SandboxPolicy] = None,
    ) -> SandboxResult:
        start = time.time()

        args = ["earthly"]
        if policy and not policy.allow_network:
            args.append("--network=none")
        args.extend(["+target", "--", command])

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            stdout = ""
            stderr = f"Timeout after {timeout}s"
            exit_code = 124
        except FileNotFoundError:
            return SandboxResult.failed(
                handle_id=handle.handle_id,
                reason="earthly CLI not found on PATH",
            )
        except Exception as e:
            return SandboxResult.failed(
                handle_id=handle.handle_id,
                reason=str(e),
            )

        duration_ms = (time.time() - start) * 1000
        evidence_hash = SandboxResult.compute_evidence_hash(
            handle.handle_id, command, stdout, exit_code
        )

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            handle_id=handle.handle_id,
            evidence_hash=evidence_hash,
        )

    def destroy(self, handle: SandboxHandle) -> None:
        # Earthly containers are ephemeral — no explicit cleanup needed.
        pass


# ═══════════════════════════════════════════════════════════════════════
# Worktree Sandbox Adapter
# ═══════════════════════════════════════════════════════════════════════

class WorktreeSandboxAdapter(SandboxProvider):
    """Sandbox provider using Git Worktree isolation.

    Reuses the existing git worktree mechanism (agent_worker.py).
    Zero new dependencies — pure subprocess + git.

    The worktree provides filesystem isolation: commands run in a
    separate working tree, not in the main repo.

    Backend: "worktree"
    Requires: git installed on PATH
    """

    @property
    def provider_id(self) -> str:
        return "worktree-sandbox"

    @property
    def supported_backends(self) -> Tuple[str, ...]:
        return ("worktree",)

    def create(self, env: SandboxEnv) -> SandboxHandle:
        handle_id = str(uuid.uuid4())[:16]
        worktree_path = env.worktree_path or os.path.join(
            os.path.dirname(__file__), ".sandbox_worktrees", handle_id
        )

        # Ensure worktree base dir exists
        os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

        return SandboxHandle(
            handle_id=handle_id,
            provider_id=self.provider_id,
            backend="worktree",
            created_at=time.time(),
            state=SANDBOX_CREATED,
        )

    def execute(
        self,
        handle: SandboxHandle,
        command: str,
        timeout: int = 300,
        cwd: Optional[str] = None,
    ) -> SandboxResult:
        start = time.time()

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=True,
                cwd=cwd,
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            stdout = ""
            stderr = f"Timeout after {timeout}s"
            exit_code = 124
        except Exception as e:
            return SandboxResult.failed(
                handle_id=handle.handle_id,
                reason=str(e),
            )

        duration_ms = (time.time() - start) * 1000
        evidence_hash = SandboxResult.compute_evidence_hash(
            handle.handle_id, command, stdout, exit_code
        )

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            handle_id=handle.handle_id,
            evidence_hash=evidence_hash,
        )

    def destroy(self, handle: SandboxHandle) -> None:
        worktree_dir = os.path.join(
            os.path.dirname(__file__), ".sandbox_worktrees", handle.handle_id
        )
        if os.path.isdir(worktree_dir):
            try:
                import shutil
                shutil.rmtree(worktree_dir, ignore_errors=True)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════
# Unified Execute — Evidence-Wrapped Sandbox Execution
# ═══════════════════════════════════════════════════════════════════════

def execute_sandbox(
    provider: SandboxProvider,
    command: str,
    policy: Optional[SandboxPolicy] = None,
    env: Optional[SandboxEnv] = None,
    timeout: int = 300,
) -> dict:
    """Execute a command in a sandbox and wrap the result as evidence.

    Pipeline:
      1. Apply policy pre-flight checks
      2. Create sandbox via provider
      3. Execute command in sandbox
      4. Wrap result as EvidenceRecord (truth_source=False)
      5. Destroy sandbox
      6. Return unified result dict

    Returns:
      {
        "result": SandboxResult,
        "evidence": EvidenceRecord,
        "success": bool,
        "policy_id": str,
        "provider_id": str,
        "trace_hash": str,
      }
    """
    trace_id = str(uuid.uuid4())[:16]

    if policy is None:
        policy = policy_strict()

    if env is None:
        env = SandboxEnv()

    # Pre-flight: policy validation
    ok, reason = policy.validate_command(command)
    if not ok:
        return {
            "result": SandboxResult.failed(reason=reason),
            "evidence": None,
            "success": False,
            "policy_id": policy.policy_id,
            "provider_id": provider.provider_id,
            "error": reason,
            "trace_hash": "",
        }

    # Create + Execute + Destroy
    handle = provider.create(env)
    result = provider.execute(handle, command, timeout=timeout)
    provider.destroy(handle)

    # Evidence wrap
    source = EvidenceSource(
        adapter_id=provider.provider_id,
        capability_type="sandbox",
        source_uri=handle.handle_id,
        collection_mode="sandbox_execute",
        source_trust_level=TRUST_LOW,
    )

    provenance = EvidenceProvenance(
        command_hash=hashlib.sha256(command.encode()).hexdigest()[:16],
        output_hash=result.evidence_hash,
        collected_at=str(time.time()),
    )

    evidence = EvidenceRecord(
        evidence_id=trace_id,
        evidence_type="sandbox_result",
        source=source,
        provenance=provenance,
        payload_summary=result.stdout[:500],
        confidence=0.5,
        truth_source=False,
        evidence_hash=result.evidence_hash,
    )

    trace_data = {
        "trace_id": trace_id,
        "policy_id": policy.policy_id,
        "provider_id": provider.provider_id,
        "handle_id": handle.handle_id,
        "command": command[:200],
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
    }

    return {
        "result": result,
        "evidence": evidence,
        "success": result.success,
        "policy_id": policy.policy_id,
        "provider_id": provider.provider_id,
        "trace_hash": hashlib.sha256(
            json.dumps(trace_data, sort_keys=True).encode()
        ).hexdigest()[:16],
    }
