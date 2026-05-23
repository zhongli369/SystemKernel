"""
ExecutionLoop — Deterministic Verification Gate (v2.0 — Phase 2 industrial)

Flow: execute skill → verify (lint → typecheck → test) → report → optional retry → stop.

THIS IS A MECHANICAL QUALITY GATE, not an agent or executor.

Key guarantees:
  - Fixed pipeline: lint → typecheck → test → report (ALWAYS in this order)
  - Max 2 attempts (initial + 1 correction based on error log only)
  - No AI decisions, no dynamic pipeline, no conditional execution
  - Subprocess isolation per check (timeout, filesystem scope)
  - Standardized JSON report output
  - Deterministic: same input → same check sequence every time
"""

from dataclasses import dataclass, field, asdict
import subprocess
import sys
import time
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# Data types (frozen — no runtime state mutation)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ResolvedCapability:
    """Capability resolved BEFORE the loop. Immutable for entire loop duration."""
    skill_id: str
    confidence: float = 1.0


@dataclass(frozen=True)
class ExecutionRequest:
    """Input to the execution loop."""
    capability: ResolvedCapability
    target: str                     # file path or description of what changed
    verification: tuple[str, ...]   # check names ("lint", "typecheck", "test") or shell commands


@dataclass(frozen=True)
class ExecutionResult:
    """Output of the execution loop. Ephemeral — caller decides persistence."""
    success: bool
    corrected: bool
    verification_passed: bool
    attempt: int                    # 1 or 2
    correction_remaining: bool      # True if one more correction allowed
    summary: str                    # human-readable

    def json_report(self) -> dict:
        """Standardized JSON execution report (Phase 2 industrial)."""
        return {
            "task_id": "",
            "skill_id": "",
            "attempts": self.attempt,
            "lint": "",
            "typecheck": "",
            "tests": "",
            "duration_ms": 0,
            "error_summary": "",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Sandbox configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SandboxConfig:
    """Isolation parameters for verification checks.

    LIGHTWEIGHT — subprocess isolation only. No containers, no VMs.
    """
    timeout_per_check: int = 300   # seconds per individual check (5 min)
    timeout_total: int = 600       # seconds for all checks combined (10 min)
    filesystem_scope: str = "."    # cwd for subprocess invocation
    max_output_bytes: int = 50_000 # truncate output beyond this


# ═══════════════════════════════════════════════════════════════════════════════
# Fixed verification pipeline — ALWAYS lint → typecheck → test → report
# ═══════════════════════════════════════════════════════════════════════════════

# Named checks map (deterministic, no dynamic resolution)
_NAMED_CHECKS: dict[str, list[str]] = {
    "lint":      ["ruff", "check", "."],
    "typecheck": ["mypy", "."],
    "test":      ["pytest", "-q", "--tb=short"],
}

# Fixed execution order — the ONLY order, always
_FIXED_PIPELINE = ("lint", "typecheck", "test")


@dataclass
class CheckResult:
    """Result of a single verification check."""
    check_name: str
    passed: bool
    output: str
    duration_ms: int
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Single check runner — subprocess isolation
# ═══════════════════════════════════════════════════════════════════════════════

def _run_one_check(
    check: str,
    cwd: str = ".",
    timeout: int = 300,
    max_output: int = 50_000,
) -> CheckResult:
    """Run a single verification check in isolated subprocess.

    Pure I/O function. No side effects beyond subprocess execution.

    Args:
        check: Named check ("lint", "typecheck", "test") or raw shell command.
        cwd: Working directory for the subprocess.
        timeout: Seconds before SIGTERM.
        max_output: Maximum output bytes before truncation.

    Returns:
        CheckResult with passed/fail, output, timing.
    """
    if check in _NAMED_CHECKS:
        cmd = _NAMED_CHECKS[check]
    else:
        cmd = check.split()

    start = time.monotonic()
    result = CheckResult(
        check_name=check,
        passed=False,
        output="",
        duration_ms=0,
    )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        result.duration_ms = elapsed
        result.passed = proc.returncode == 0
        output = (proc.stdout + "\n" + proc.stderr).strip()
        result.output = output[:max_output] if len(output) > max_output else output
        if len(output) > max_output:
            result.output += f"\n[TRUNCATED at {max_output} bytes]"

    except FileNotFoundError:
        result.duration_ms = int((time.monotonic() - start) * 1000)
        result.output = f"Command not found: {cmd[0]}"
        result.error = result.output

    except subprocess.TimeoutExpired:
        result.duration_ms = int((time.monotonic() - start) * 1000)
        result.output = f"Check timed out after {timeout}s: {' '.join(cmd)}"
        result.error = result.output

    except Exception as exc:
        result.duration_ms = int((time.monotonic() - start) * 1000)
        result.output = f"Check error: {exc}"
        result.error = result.output

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Fixed pipeline runner — lint → typecheck → test → report (ALWAYS)
# ═══════════════════════════════════════════════════════════════════════════════

def _run_fixed_pipeline(
    verification: tuple[str, ...],
    cwd: str,
    sandbox: SandboxConfig,
) -> Tuple[bool, list[CheckResult], int]:
    """Run ALL checks in FIXED order. Stops at first failure.

    The order is ALWAYS lint → typecheck → test → [custom].
    Named checks are ordered. Custom checks run after named checks.
    No dynamic ordering. No conditional execution.

    Returns:
        (all_passed: bool, results: list[CheckResult], total_duration_ms: int)
    """
    results: list[CheckResult] = []
    all_passed = True
    total_start = time.monotonic()

    # Partition: named checks in fixed order, then custom checks
    named_checks = [c for c in _FIXED_PIPELINE if c in verification]
    custom_checks = [c for c in verification if c not in _NAMED_CHECKS]

    # Run named checks in FIXED order
    for check in named_checks:
        elapsed = int((time.monotonic() - total_start) * 1000)
        if elapsed > sandbox.timeout_total * 1000:
            results.append(CheckResult(
                check_name=check,
                passed=False,
                output="Total timeout exceeded — pipeline halted",
                error="timeout",
            ))
            all_passed = False
            break

        result = _run_one_check(check, cwd=cwd, timeout=sandbox.timeout_per_check)
        results.append(result)

        if not result.passed:
            all_passed = False
            break  # Stop at first failure — fix that first

    # Run custom checks only if named checks all passed
    if all_passed:
        for check in custom_checks:
            elapsed = int((time.monotonic() - total_start) * 1000)
            if elapsed > sandbox.timeout_total * 1000:
                results.append(CheckResult(
                    check_name=check,
                    passed=False,
                    output="Total timeout exceeded — pipeline halted",
                    error="timeout",
                ))
                all_passed = False
                break

            result = _run_one_check(check, cwd=cwd, timeout=sandbox.timeout_per_check)
            results.append(result)

            if not result.passed:
                all_passed = False
                break

    total_duration = int((time.monotonic() - total_start) * 1000)
    return all_passed, results, total_duration


# ═══════════════════════════════════════════════════════════════════════════════
# Standardized JSON report builder
# ═══════════════════════════════════════════════════════════════════════════════

def _build_json_report(
    task_id: str,
    skill_id: str,
    attempt: int,
    results: list[CheckResult],
    total_duration_ms: int,
) -> dict:
    """Build the standardized execution report (Phase 2 industrial).

    Output schema:
    {
        "task_id": str,
        "skill_id": str,
        "attempts": int,
        "lint": "pass|fail|skipped",
        "typecheck": "pass|fail|skipped",
        "tests": "pass|fail|skipped",
        "duration_ms": int,
        "error_summary": str
    }
    """
    report = {
        "task_id": task_id,
        "skill_id": skill_id,
        "attempts": attempt,
        "lint": "skipped",
        "typecheck": "skipped",
        "tests": "skipped",
        "duration_ms": total_duration_ms,
        "error_summary": "",
    }

    error_messages: list[str] = []

    for r in results:
        status = "pass" if r.passed else "fail"
        if r.check_name in report:
            report[r.check_name] = status
        else:
            # Custom check — add as extra field
            report[f"check_{r.check_name}"] = status

        if not r.passed:
            error_messages.append(f"[{r.check_name}] {r.output[:200]}")

    if error_messages:
        report["error_summary"] = "\n".join(error_messages)

    return report


# ═══════════════════════════════════════════════════════════════════════════════
# Public API — single entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run(
    request: ExecutionRequest,
    *,
    correction_attempted: bool = False,
    cwd: str = ".",
    sandbox: Optional[SandboxConfig] = None,
) -> ExecutionResult:
    """Run the bounded execution verification loop.

    FIXED PIPELINE: lint → typecheck → test → [custom] → report.
    Always this order. No dynamic reordering. No conditional execution.

    Call sequence:
        1. run(request)                          → first verification
        2. If result.correction_remaining:
           caller applies ONE correction
           (Correction MUST be based on error log output — no AI decisions)
        3. run(request, correction_attempted=True) → final verification
        4. Stop — no further corrections allowed.

    Args:
        request: ExecutionRequest with capability, target, and verification checks.
        correction_attempted: Set True when calling after a correction was applied.
        cwd: Working directory for running checks.
        sandbox: Optional SandboxConfig for isolation parameters.

    Returns:
        ExecutionResult — ephemeral. Caller decides whether to persist summary.
    """
    if sandbox is None:
        sandbox = SandboxConfig()

    skill_id = request.capability.skill_id
    target = request.target

    # Handle edge case: no verification checks configured
    if not request.verification:
        return ExecutionResult(
            success=False,
            corrected=correction_attempted,
            verification_passed=False,
            attempt=2 if correction_attempted else 1,
            correction_remaining=False,
            summary=(
                f"VERIFICATION FAILED — no verification checks configured.\n"
                f"Target: {target}\n"
                f"Skill: {skill_id}\n"
                f"Attempt: {'2/2 (max)' if correction_attempted else '1/2'}"
            ),
        )

    attempt = 2 if correction_attempted else 1

    # ── Observability: record execution span (non-invasive) ────────────
    import uuid as _uuid
    _exec_trace_id = str(_uuid.uuid4())
    _exec_span_id = ""
    try:
        from Observability.trace import record_span as _record_span
        _exec_span_obj = _record_span(
            stage="execution",
            data={
                "target": target,
                "verification": list(request.verification),
                "attempt": attempt,
            },
            trace_id=_exec_trace_id,
        )
        _exec_span_id = _exec_span_obj.span_id
    except Exception:
        pass

    _exec_start = time.monotonic()

    # Run the FIXED pipeline
    passed, results, total_duration = _run_fixed_pipeline(
        request.verification, cwd, sandbox
    )

    _exec_elapsed_ms = (time.monotonic() - _exec_start) * 1000

    # Build JSON report (Phase 2 industrial)
    json_rpt = _build_json_report("", skill_id, attempt, results, total_duration)

    # Build human-readable summary
    header = "VERIFICATION PASSED" if passed else "VERIFICATION FAILED"
    correction_note = " (after correction)" if correction_attempted else ""

    summary_lines = [
        f"{header}{correction_note}.",
        f"Target: {target}",
        f"Skill: {skill_id} (confidence: {request.capability.confidence:.2f})",
        f"Attempt: {attempt}/2 (max)",
        f"Pipeline: {' → '.join(request.verification)}",
        f"Duration: {total_duration}ms",
        "",
    ]

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        summary_lines.append(f"[{status}] {r.check_name} ({r.duration_ms}ms)")
        if r.output:
            truncated = r.output[:200] + "..." if len(r.output) > 200 else r.output
            summary_lines.append(f"  {truncated}")

    # JSON report embedded in summary
    import json
    summary_lines.append("")
    summary_lines.append("--- JSON Report ---")
    summary_lines.append(json.dumps(json_rpt, indent=2, ensure_ascii=False))

    # Correction remaining only if first attempt failed and no correction yet
    correction_remaining = (not passed and not correction_attempted)

    # ── Observability: record validation span + metrics (non-invasive)
    try:
        from Observability.trace import record_span as _record_span
        from Observability.metrics import record_metric as _record_metric

        _record_span(
            stage="validation",
            data={
                "verification_passed": passed,
                "lint": json_rpt.get("lint", "skipped"),
                "typecheck": json_rpt.get("typecheck", "skipped"),
                "tests": json_rpt.get("tests", "skipped"),
                "duration_ms": total_duration,
            },
            trace_id=_exec_trace_id,
            parent_span_id=_exec_span_id,
        )
        _record_metric("execution_latency_ms", _exec_elapsed_ms,
                       tags={"skill": skill_id, "attempt": str(attempt)},
                       trace_id=_exec_trace_id)
        _record_metric("validation_passed", 1 if passed else 0,
                       tags={"skill": skill_id},
                       trace_id=_exec_trace_id)
        if correction_attempted:
            _record_metric("retry", 1,
                           tags={"skill": skill_id},
                           trace_id=_exec_trace_id)
    except Exception:
        pass

    return ExecutionResult(
        success=passed,
        corrected=correction_attempted,
        verification_passed=passed,
        attempt=attempt,
        correction_remaining=correction_remaining,
        summary="\n".join(summary_lines),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Structured report extractor (for callers that want machine-readable output)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_report(result: ExecutionResult) -> dict:
    """Extract the JSON report from an ExecutionResult's summary.

    Parses the embedded JSON report block from the summary string.
    Callers that need structured data can use this instead of parsing summary.
    """
    lines = result.summary.split("\n")
    in_json = False
    json_lines = []
    for line in lines:
        if line.strip() == "--- JSON Report ---":
            in_json = True
            continue
        if in_json:
            json_lines.append(line)

    if json_lines:
        import json
        try:
            return json.loads("\n".join(json_lines))
        except json.JSONDecodeError:
            pass

    return result.json_report()


# ═══════════════════════════════════════════════════════════════════════════════
# Optional: persist summary to TaskSystem
# ═══════════════════════════════════════════════════════════════════════════════

def write_summary_to_task(
    result: ExecutionResult,
    task_id: str,
    task_system_path: str = "../TaskSystem",
) -> bool:
    """Write the execution result summary to a TaskSystem task's context_log.

    OPTIONAL. Caller decides whether to persist. The execution loop itself
    has no opinion on persistence.

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
