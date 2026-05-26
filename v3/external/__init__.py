"""
External Tool Adapters — Safe wrappers for tools outside the kernel boundary.

These are NOT kernel modules. They are developer tools that wrap external
processes (e.g., npx repomix) with safety gates. No external tool is ever
imported as a Python dependency.

Rule: truth_source is ALWAYS False for context pack outputs.
"""

from v3.external.context_pack import (
    ContextPackAdapter,
    ContextPackConfig,
    ContextPackResult,
)
from v3.external.usage_report import (
    UsageReportAdapter,
    UsageReportConfig,
    UsageDayRecord,
    UsageReportSummary,
)

__all__ = [
    "ContextPackAdapter",
    "ContextPackConfig",
    "ContextPackResult",
    "UsageReportAdapter",
    "UsageReportConfig",
    "UsageDayRecord",
    "UsageReportSummary",
]
