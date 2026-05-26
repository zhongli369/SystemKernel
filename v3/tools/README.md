# Tools/

External tool adapters. All synchronous. All LLM-free.

## Adapters

| Adapter | Protocol | External |
|---------|----------|----------|
| `repomix_adapter.py` | npx subprocess | repomix |
| `mcp_adapter.py` | MCP protocol | any MCP server |
| `shell_adapter.py` | subprocess.run | any CLI |

## Contract

```python
class ToolAdapter(ABC):
    def invoke(self, invocation: ToolInvocation) -> ToolResult: ...
    def health_check(self) -> bool: ...
```
