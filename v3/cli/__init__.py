"""
SystemKernel v3.0 — Developer CLI package.

Provides one-command access to status, quality, memory, reports,
and health checks. All commands wrap existing facades.
"""

from v3.cli.systemkernel import (
    main, build_parser,
    cmd_status, cmd_quality, cmd_memory_report,
    cmd_reports_list, cmd_reports_summary, cmd_doctor,
)

__all__ = [
    "main",
    "build_parser",
    "cmd_status",
    "cmd_quality",
    "cmd_memory_report",
    "cmd_reports_list",
    "cmd_reports_summary",
    "cmd_doctor",
]
