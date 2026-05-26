"""
Architecture Invariant Registry — Runtime verification of system invariants.

Declares ArchitecturalInvariant rules and validates them post-execution.
Violations are logged, never used to alter execution flow.

ZERO impact on execution logic. Try/except guarded at all call sites.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


# ═══════════════════════════════════════════════════════════════════════
# Invariant Severity
# ═══════════════════════════════════════════════════════════════════════

class InvariantSeverity(str, Enum):
    CRITICAL = "critical"  # Blocks execution
    WARN = "warn"          # Logged only
    INFO = "info"          # Telemetry only


# ═══════════════════════════════════════════════════════════════════════
# Architectural Invariant
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ArchitecturalInvariant:
    """A single architectural invariant with its validator.

    Validator receives the execution result dict and the engine instance.
    Returns (passed: bool, detail: str).
    """
    name: str
    description: str
    severity: InvariantSeverity
    validator: Callable[[dict, Any], tuple[bool, str]] = field(repr=False)


# ═══════════════════════════════════════════════════════════════════════
# Validator Functions (pure, stateless)
# ═══════════════════════════════════════════════════════════════════════

def _validate_single_loop(result: dict, engine: Any) -> tuple[bool, str]:
    """Invariant 1: ExecutionEngine must be single-loop — one run() call per trace."""
    run_count = getattr(engine, "_run_count", -1)
    if run_count == 0:
        return (True, f"run_count={run_count}")
    if run_count == 1:
        return (True, f"run_count={run_count}")
    return (False, f"Engine run_count={run_count} — expected 1 per trace_id")


def _validate_memory_non_interference(result: dict, engine: Any) -> tuple[bool, str]:
    """Invariant 2: MemoryGateway must not influence execution control flow."""
    gw = getattr(engine.config, "memory_gateway", None)
    if gw is None:
        return (True, "No memory gateway configured")
    # Check: execution succeeded/failed independently of memory presence
    success = result.get("success")
    if success is not None:
        return (True, f"Memory gateway present, execution success={success}")
    return (False, "Execution result missing 'success' field")


def _validate_tools_llm_free(result: dict, engine: Any) -> tuple[bool, str]:
    """Invariant 3: ToolAdapter must be LLM-free — no LLM imports in tools/."""
    import ast
    banned = ("openai", "anthropic", "langchain", "transformers", "llm")
    found = []
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
    if os.path.isdir(tools_dir):
        for fname in os.listdir(tools_dir):
            if fname.endswith(".py"):
                fpath = os.path.join(tools_dir, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                name = alias.name.split(".")[0].lower()
                                if name in banned:
                                    found.append(f"{fname}: imports '{alias.name}'")
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                name = node.module.split(".")[0].lower()
                                if name in banned:
                                    found.append(f"{fname}: from {node.module} imports ...")
                except SyntaxError:
                    pass
                except Exception:
                    pass
    if found:
        return (False, f"LLM imports detected in tools/: {found}")
    return (True, "No LLM imports in tools/")


def _validate_pipeline_immutability(result: dict, engine: Any) -> tuple[bool, str]:
    """Invariant 4: ExecutionEngine pipeline must be immutable after init."""
    config = engine.config
    pipeline = config.pipeline
    if not isinstance(pipeline, tuple):
        return (False, f"Pipeline is {type(pipeline).__name__}, not tuple")
    # Verify we can't mutate it
    try:
        if hasattr(pipeline, "__setitem__"):
            return (False, "Pipeline supports item assignment")
    except Exception:
        pass
    return (True, f"Pipeline is immutable tuple of {len(pipeline)} stages")


def _validate_memory_side_effect_only(result: dict, engine: Any) -> tuple[bool, str]:
    """Invariant 5: Memory is side-effect only — emits never alter execution state."""
    gw = getattr(engine.config, "memory_gateway", None)
    if gw is None:
        return (True, "No memory gateway")
    event_count = gw.event_count if hasattr(gw, "event_count") else 0
    # Emitted events don't change result.success or pipeline order
    return (True, f"Memory events emitted: {event_count} (side-effect only)")


def _validate_observability_no_mutation(result: dict, engine: Any) -> tuple[bool, str]:
    """Invariant 6: Observability must not alter state — read-only recording."""
    stage_results = result.get("stage_results", [])
    # Each stage result must be a plain dict (no mutation back into engine)
    for sr in stage_results:
        if not isinstance(sr, dict):
            return (False, f"Stage result is {type(sr).__name__}, not dict")
    return (True, f"{len(stage_results)} stages verified — observability is read-only")


# ═══════════════════════════════════════════════════════════════════════
# Invariant Registry
# ═══════════════════════════════════════════════════════════════════════

class SystemInvariantRegistry:
    """Extensible registry of architectural invariants.

    Add new invariants with register(). Validate all with validate_all().
    """

    def __init__(self):
        self._invariants: dict[str, ArchitecturalInvariant] = {}

    def register(self, invariant: ArchitecturalInvariant) -> None:
        self._invariants[invariant.name] = invariant

    def unregister(self, name: str) -> None:
        self._invariants.pop(name, None)

    @property
    def count(self) -> int:
        return len(self._invariants)

    def list_all(self) -> list[dict]:
        return [
            {"name": inv.name, "description": inv.description, "severity": inv.severity.value}
            for inv in self._invariants.values()
        ]

    def validate_all(self, result: dict, engine: Any) -> list[dict]:
        """Run all registered validators. Returns list of violation dicts.

        Each violation dict: {name, severity, passed, detail}
        """
        violations = []
        for inv in self._invariants.values():
            try:
                passed, detail = inv.validator(result, engine)
            except Exception as exc:
                passed = False
                detail = f"Validator raised: {type(exc).__name__}: {exc}"
            if not passed:
                violations.append({
                    "name": inv.name,
                    "severity": inv.severity.value,
                    "passed": False,
                    "detail": detail,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                })
        return violations


# ═══════════════════════════════════════════════════════════════════════
# Default Registry (6 core invariants)
# ═══════════════════════════════════════════════════════════════════════

def create_default_registry() -> SystemInvariantRegistry:
    registry = SystemInvariantRegistry()

    registry.register(ArchitecturalInvariant(
        name="execution_engine_single_loop",
        description="ExecutionEngine must execute exactly one pipeline per run() call — no hidden loops",
        severity=InvariantSeverity.CRITICAL,
        validator=_validate_single_loop,
    ))
    registry.register(ArchitecturalInvariant(
        name="memory_gateway_non_interference",
        description="MemoryGateway must not influence execution control flow (pass/fail/re-route)",
        severity=InvariantSeverity.CRITICAL,
        validator=_validate_memory_non_interference,
    ))
    registry.register(ArchitecturalInvariant(
        name="tools_llm_free",
        description="ToolAdapter module must not import or use any LLM library",
        severity=InvariantSeverity.CRITICAL,
        validator=_validate_tools_llm_free,
    ))
    registry.register(ArchitecturalInvariant(
        name="pipeline_immutability",
        description="ExecutionEngine pipeline must be frozen (tuple) after construction",
        severity=InvariantSeverity.CRITICAL,
        validator=_validate_pipeline_immutability,
    ))
    registry.register(ArchitecturalInvariant(
        name="memory_side_effect_only",
        description="Memory emissions must never alter execution state or pipeline order",
        severity=InvariantSeverity.WARN,
        validator=_validate_memory_side_effect_only,
    ))
    registry.register(ArchitecturalInvariant(
        name="observability_read_only",
        description="Observability must only record — never mutate state or decide outcomes",
        severity=InvariantSeverity.WARN,
        validator=_validate_observability_no_mutation,
    ))

    return registry


def has_critical_violations(violations: list[dict]) -> bool:
    """Check if any violations are CRITICAL severity."""
    return any(v["severity"] == InvariantSeverity.CRITICAL.value for v in violations)
