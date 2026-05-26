"""
SystemKernel v3.0 — Tool Adapters.

External tool wrappers. ZERO LLM. Pure subprocess/API adapters.

Protocol:
  ToolAdapter.invoke(ToolInvocation) → ToolResult

Adapters:
  - repomix:  code compression via Tree-sitter AST
  - mcp:      generic MCP protocol tools
  - shell:    subprocess command execution
"""

from v3.tools.tool_adapter_base import ToolAdapter, ToolInvocation, ToolResult

__all__ = [
    "ToolAdapter",
    "ToolInvocation",
    "ToolResult",
]
