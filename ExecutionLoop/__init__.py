"""ExecutionLoop — Deterministic verification gate (v2.0 Phase 2 industrial).

Fixed pipeline: lint → typecheck → test → report.
Max 2 attempts (initial + 1 correction based on error log only).
Zero AI decisions. Zero dynamic pipelines.
"""

from ExecutionLoop.loop import (
    run,
    extract_report,
    write_summary_to_task,
    ResolvedCapability,
    ExecutionRequest,
    ExecutionResult,
    SandboxConfig,
    CheckResult,
)

__all__ = [
    "run",
    "extract_report",
    "write_summary_to_task",
    "ResolvedCapability",
    "ExecutionRequest",
    "ExecutionResult",
    "SandboxConfig",
    "CheckResult",
]