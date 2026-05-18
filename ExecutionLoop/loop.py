"""
Execution Loop — Minimal Verification Harness (v1.0)

Flow: resolve once → execute → verify → optional single correction → verify → stop.

NOT an agent, executor, orchestrator, or workflow engine.
A deterministic verification gate with one bounded retry.
"""

from dataclasses import dataclass
import subprocess
import sys
from typing import Optional, Tuple


# ═══════════ Data types (frozen — no runtime state) ═══════════

@dataclass(frozen=True)
class ResolvedCapability:
    """Capability resolved BEFORE the loop. Immutable for entire loop duration."""
    skill_id: str
    confidence: float = 1.0


@dataclass(frozen=True)
class ExecutionRequest:
    """Input to the execution loop."""
    capability: ResolvedCapability
    target: str                     # modified file path or description
    verification: tuple[str, ...]   # check names ("lint") or shell commands


@dataclass(frozen=True)
class ExecutionResult:
    """Output of the execution loop. Ephemeral — caller decides persistence."""
    success: bool
    corrected: bool
    verification_passed: bool
    attempt: int                    # 1 or 2
    correction_remaining: bool      # True if one more correction allowed
    summary: str


# ═══════════ Named verification checks (deterministic only) ═══════════

_NAMED_CHECKS: dict[str, list[str]] = {
    "lint":      ["ruff", "check", "."],
    "typecheck": ["mypy", "."],
    "test":      ["pytest", "-q", "--tb=short"],
}


# ═══════════ Internal: single check runner ═══════════

def _run_one_check(check: str, cwd: str, timeout: int = 120) -> Tuple[bool, str]:
    """Run a single check. Named check or raw shell command.

    Returns (passed: bool, output: str).
    """
    if check in _NAMED_CHECKS:
        cmd = _NAMED_CHECKS[check]
    else:
        cmd = check.split()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        passed = result.returncode == 0
        output = (result.stdout + result.stderr).strip()
        return passed, output or "(no output)"
    except FileNotFoundError:
        return False, f"check not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"check timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as exc:
        return False, f"check error: {exc}"


# ═══════════ Internal: all checks runner ═══════════

def _run_all_checks(verification: tuple[str, ...], cwd: str) -> Tuple[bool, str]:
    """Run all checks sequentially. Stops at first failure for efficiency.

    Returns (all_passed: bool, combined_output: str).
    """
    all_passed = True
    lines: list[str] = []

    for check in verification:
        passed, output = _run_one_check(check, cwd)
        status = "PASS" if passed else "FAIL"
        # Truncate per-check output to keep summary bounded
        truncated = output[:300] + "..." if len(output) > 300 else output
        lines.append(f"[{status}] {check}")
        if truncated:
            lines.append(f"  {truncated}")
        if not passed:
            all_passed = False
            break  # stop at first failure — fix that first

    return all_passed, "\n".join(lines)


# ═══════════ Public API — single entry point ═══════════

def run(
    request: ExecutionRequest,
    *,
    correction_attempted: bool = False,
    cwd: str = ".",
) -> ExecutionResult:
    """Run the bounded execution verification loop.

    Call sequence:
        1. run(request)                          → first verification
        2. If result.correction_remaining:
           caller applies ONE correction
        3. run(request, correction_attempted=True) → final verification
        4. Stop — no further corrections allowed.

    Args:
        request: ExecutionRequest with capability, target, and verification checks.
        correction_attempted: Set True when calling after a correction was applied.
        cwd: Working directory for running checks.

    Returns:
        ExecutionResult — ephemeral. Caller decides whether to persist summary.
    """
    if correction_attempted and not request.verification:
        return ExecutionResult(
            success=False,
            corrected=True,
            verification_passed=False,
            attempt=2,
            correction_remaining=False,
            summary=(
                f"CORRECTION APPLIED — no verification checks configured.\n"
                f"Target: {request.target}\n"
                f"Capability: {request.capability.skill_id}\n"
                f"Attempt: 2/2 (max)"
            ),
        )

    attempt = 2 if correction_attempted else 1
    passed, output = _run_all_checks(request.verification, cwd)

    # Build summary
    header = "VERIFICATION PASSED" if passed else "VERIFICATION FAILED"
    correction_note = ""
    if correction_attempted:
        correction_note = " (after correction)"

    summary_lines = [
        f"{header}{correction_note}.",
        f"Target: {request.target}",
        f"Capability: {request.capability.skill_id} "
        f"(confidence: {request.capability.confidence:.2f})",
        f"Attempt: {attempt}/2 (max)",
        f"Checks: {', '.join(request.verification)}",
        "",
        output,
    ]

    # Correction remaining only if first attempt failed and no correction yet
    correction_remaining = (not passed and not correction_attempted)

    return ExecutionResult(
        success=passed,
        corrected=correction_attempted,
        verification_passed=passed,
        attempt=attempt,
        correction_remaining=correction_remaining,
        summary="\n".join(summary_lines),
    )


# ═══════════ Optional: persist summary to TaskSystem ═══════════

def write_summary_to_task(
    result: ExecutionResult,
    task_id: str,
    task_system_path: str = "../TaskSystem",
) -> bool:
    """Write the execution result summary to a TaskSystem task's context_log.

    This is OPTIONAL. The caller may choose to persist the summary or discard it.
    The execution loop itself has no opinion on persistence.

    Returns True if written successfully, False otherwise.
    """
    try:
        import sys as _sys
        from pathlib import Path

        ts_path = Path(__file__).resolve().parent / task_system_path
        ts_core = str(ts_path / "core")
        if ts_core not in _sys.path:
            _sys.path.insert(0, ts_core)

        from task_manager import add_context_log

        message = (
            f"EXECUTION_LOOP | success={result.success} | "
            f"corrected={result.corrected} | attempt={result.attempt}"
        )
        add_context_log(task_id, message)
        return True
    except Exception:
        return False
