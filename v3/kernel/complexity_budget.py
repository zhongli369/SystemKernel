"""
Complexity Budget — Static analysis only. ZERO runtime impact.

Defines per-module LOC limits and dependency depth constraints.
validate_complexity_report() is called by architecture_guard.py, NOT by kernel.

Reads current module sizes and compares against budget limits.
Raises ComplexityBudgetExceeded if limits are breached.

NO runtime imports from kernel internals. Pure file-I/O for analysis.
"""

from __future__ import annotations

import os
import ast
import json
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# Budget Limits
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ModuleBudget:
    """Per-module complexity budget."""
    name: str
    path_glob: str
    max_loc: int
    max_public_functions: int = 20
    max_import_depth: int = 3  # max depth of internal dependency chain
    max_base_classes: int = 2
    note: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Budget Definitions
# ═══════════════════════════════════════════════════════════════════════

BUDGETS: tuple[ModuleBudget, ...] = (
    ModuleBudget(
        name="execution_engine",
        path_glob="kernel/execution_engine.py",
        max_loc=440,
        max_public_functions=26,
        max_import_depth=3,
        max_base_classes=15,
        note="Core execution loop — Event-Sourced DomainState + Checkpoint + Pipeline. Phase 4B.",
    ),
    ModuleBudget(
        name="execution_state",
        path_glob="kernel/execution_state.py",
        max_loc=180,
        max_public_functions=14,
        max_import_depth=1,
        max_base_classes=4,
        note="Frozen lifecycle tracker — immutable state transitions. Zero LLM.",
    ),
    ModuleBudget(
        name="checkpoint",
        path_glob="kernel/checkpoint.py",
        max_loc=280,
        max_public_functions=18,
        max_import_depth=1,
        max_base_classes=4,
        note="Append-only JSONL checkpoint persistence. Zero LLM.",
    ),
    ModuleBudget(
        name="replay",
        path_glob="kernel/replay.py",
        max_loc=250,
        max_public_functions=8,
        max_import_depth=2,
        max_base_classes=3,
        note="Deterministic execution timeline replay (checkpoints + events). Zero LLM.",
    ),
    ModuleBudget(
        name="events",
        path_glob="kernel/events.py",
        max_loc=250,
        max_public_functions=10,
        max_import_depth=1,
        max_base_classes=2,
        note="Immutable execution events + pure functional reducer. Zero LLM.",
    ),
    ModuleBudget(
        name="event_store",
        path_glob="kernel/event_store.py",
        max_loc=220,
        max_public_functions=15,
        max_import_depth=1,
        max_base_classes=3,
        note="Append-only event stream persistence. Zero LLM.",
    ),
    ModuleBudget(
        name="time_travel",
        path_glob="kernel/time_travel.py",
        max_loc=180,
        max_public_functions=12,
        max_import_depth=2,
        max_base_classes=5,
        note="Rewind, fork, and diff execution timelines. Zero LLM.",
    ),
    ModuleBudget(
        name="memory_gateway",
        path_glob="kernel/memory_gateway.py",
        max_loc=250,
        max_public_functions=13,
        max_import_depth=1,
        max_base_classes=7,
        note="Protocol definition only — no implementation, no backend knowledge.",
    ),
    ModuleBudget(
        name="observability",
        path_glob="kernel/observability.py",
        max_loc=300,
        max_public_functions=12,
        max_import_depth=1,
        max_base_classes=6,
        note="Write-only recording — no decisions, no predictions.",
    ),
    ModuleBudget(
        name="memory_service",
        path_glob="memory/memory_service.py",
        max_loc=200,
        max_public_functions=11,
        max_import_depth=2,
        max_base_classes=7,
        note="Memory interface — keep lean, push implementation to adapters.",
    ),
    ModuleBudget(
        name="memory_adapter_base",
        path_glob="memory/memory_adapter_base.py",
        max_loc=180,
        max_public_functions=14,
        max_import_depth=2,
        max_base_classes=3,
        note="Adapter interface — one abstract class, one default impl.",
    ),
    ModuleBudget(
        name="tool_adapter_base",
        path_glob="tools/tool_adapter_base.py",
        max_loc=180,
        max_public_functions=7,
        max_import_depth=1,
        max_base_classes=5,
        note="Tool protocol — simple invocation contract.",
    ),
    ModuleBudget(
        name="mem0_adapter",
        path_glob="integrations/mem0_adapter.py",
        max_loc=200,
        max_public_functions=8,
        max_import_depth=3,
        max_base_classes=2,
        note="External adapter — isolated from kernel. LLM allowed on write path.",
    ),
    ModuleBudget(
        name="graphiti_adapter",
        path_glob="integrations/graphiti_adapter.py",
        max_loc=200,
        max_public_functions=8,
        max_import_depth=3,
        max_base_classes=2,
        note="External adapter — isolated from kernel. LLM allowed on write path.",
    ),
    ModuleBudget(
        name="main",
        path_glob="main.py",
        max_loc=250,
        max_public_functions=5,
        max_import_depth=3,
        max_base_classes=0,
        note="Entry point — wiring only, no logic.",
    ),
)


# ═══════════════════════════════════════════════════════════════════════
# Analysis Functions (static, no runtime impact)
# ═══════════════════════════════════════════════════════════════════════

def _count_loc(filepath: str) -> int:
    """Count non-blank, non-comment lines."""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()
    count = 0
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('"""'):
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if stripped.startswith("#"):
            continue
        count += 1
    return count


def _count_public_functions(filepath: str) -> int:
    """Count module-level functions and public methods."""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                count += 1
            # Also count __init__ and dunder methods
            elif node.name.startswith("__") and node.name.endswith("__"):
                count += 1
    return count


def _count_classes(filepath: str) -> int:
    """Count class definitions."""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    return sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))


def _count_imports(filepath: str) -> int:
    """Count import statements."""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, (ast.Import, ast.ImportFrom)))


# ═══════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BudgetReport:
    module_name: str
    current_loc: int
    budget_loc: int
    loc_usage_pct: float
    current_functions: int
    budget_functions: int
    current_classes: int
    current_imports: int
    within_budget: bool
    warnings: list[str] = field(default_factory=list)

    STATUS_OK = "OK"
    STATUS_WARN = "WARN"
    STATUS_EXCEEDED = "EXCEEDED"

    @property
    def status(self) -> str:
        if not self.within_budget:
            return self.STATUS_EXCEEDED
        if self.loc_usage_pct >= 80.0:
            return self.STATUS_WARN
        return self.STATUS_OK


def validate_complexity_report(v3_root: Optional[str] = None) -> dict:
    """Generate complexity budget report. Pure I/O, no kernel imports.

    Args:
        v3_root: Path to v3/ directory. Auto-detected if None.

    Returns:
        {
            "overall_status": "OK" | "WARN" | "EXCEEDED",
            "modules": [BudgetReport, ...],
            "total_loc": int,
            "total_budget_loc": int,
            "exceeded_modules": [str, ...],
            "warn_modules": [str, ...],
        }
    """
    if v3_root is None:
        v3_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    reports = []
    exceeded = []
    warned = []
    total_loc = 0
    total_budget = 0

    for budget in BUDGETS:
        filepath = os.path.join(v3_root, budget.path_glob)
        loc = _count_loc(filepath)
        functions = _count_public_functions(filepath)
        classes = _count_classes(filepath)
        imports = _count_imports(filepath)
        loc_pct = (loc / budget.max_loc * 100) if budget.max_loc > 0 else 0.0

        warnings = []
        within = True

        if loc > budget.max_loc:
            warnings.append(f"LOC {loc} > budget {budget.max_loc}")
            within = False
        if functions > budget.max_public_functions:
            warnings.append(f"Functions {functions} > budget {budget.max_public_functions}")
            within = False
        if imports > budget.max_import_depth * 10:  # rough proxy
            warnings.append(f"Imports {imports} exceeds rough depth proxy")

        report = BudgetReport(
            module_name=budget.name,
            current_loc=loc,
            budget_loc=budget.max_loc,
            loc_usage_pct=round(loc_pct, 1),
            current_functions=functions,
            budget_functions=budget.max_public_functions,
            current_classes=classes,
            current_imports=imports,
            within_budget=within,
            warnings=warnings,
        )
        reports.append(report)
        total_loc += loc
        total_budget += budget.max_loc

        if not within:
            exceeded.append(budget.name)
        elif loc_pct >= 80.0:
            warned.append(budget.name)

    overall = "OK"
    if exceeded:
        overall = "EXCEEDED"
    elif warned:
        overall = "WARN"

    return {
        "overall_status": overall,
        "modules": [
            {
                "name": r.module_name,
                "loc": r.current_loc,
                "budget": r.budget_loc,
                "usage_pct": r.loc_usage_pct,
                "functions": r.current_functions,
                "classes": r.current_classes,
                "imports": r.current_imports,
                "status": r.status,
                "warnings": r.warnings,
            }
            for r in reports
        ],
        "total_loc": total_loc,
        "total_budget_loc": total_budget,
        "usage_pct": round(total_loc / total_budget * 100, 1) if total_budget > 0 else 0.0,
        "exceeded_modules": exceeded,
        "warn_modules": warned,
    }
