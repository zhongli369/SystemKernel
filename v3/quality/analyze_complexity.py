"""
Complexity Analyzer — Deterministic AST-based complexity measurement.

Scans v3/kernel/, v3/memory/, v3/tests/, v3/exports/ and produces
ModuleComplexity objects for every Python file found.

Zero LLM. Pure AST analysis. All metrics are deterministic.
"""

from __future__ import annotations

import ast
import os
import re
from typing import Tuple, Optional, Dict, List

from v3.quality.complexity_budget import ModuleComplexity, compute_complexity_score


# ═══════════════════════════════════════════════════════════════════════
# AST analysis helpers
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
        if stripped.startswith('"""') or stripped.startswith("'''"):
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if stripped.startswith("#"):
            continue
        count += 1
    return count


def _parse_file(filepath: str) -> Optional[ast.AST]:
    """Parse a Python file, returning AST or None on syntax error."""
    if not os.path.exists(filepath):
        return None
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _count_public_functions(tree: ast.AST) -> int:
    """Count public functions and dunder methods."""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                count += 1
            elif node.name.startswith("__") and node.name.endswith("__"):
                count += 1
    return count


def _count_all_functions(tree: ast.AST) -> int:
    """Count all function definitions including private."""
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))


def _count_dataclasses(tree: ast.AST) -> int:
    """Count @dataclass-decorated classes."""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
                    count += 1
                    break
                if isinstance(decorator, ast.Attribute) and decorator.attr == "dataclass":
                    count += 1
                    break
                if isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name) and decorator.func.id == "dataclass":
                        count += 1
                        break
                    if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "dataclass":
                        count += 1
                        break
    return count


def _count_imports(tree: ast.AST) -> int:
    """Count import statements."""
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, (ast.Import, ast.ImportFrom)))


def _extract_imports(tree: ast.AST) -> Tuple[List[str], List[str]]:
    """Extract internal and external import module paths.

    Returns:
        (internal_modules, external_modules) — internal = within v3/
    """
    internal = []
    external = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.module.startswith("v3."):
                internal.append(node.module)
            elif not node.module.startswith("__") and "." in node.module:
                external.append(node.module)
            elif node.module in ("sys", "os", "json", "hashlib", "uuid",
                                 "datetime", "time", "dataclasses", "typing",
                                 "abc", "collections", "functools", "itertools",
                                 "pathlib", "re", "math", "textwrap", "copy",
                                 "tempfile", "shutil", "subprocess", "io",
                                 "ast", "enum", "logging", "traceback"):
                pass  # stdlib — not counted as external
            else:
                external.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith("v3."):
                    internal.append(name)
                elif name.split(".")[0] in (
                    "sys", "os", "json", "hashlib", "uuid", "datetime", "time",
                    "dataclasses", "typing", "abc", "collections", "functools",
                    "itertools", "pathlib", "re", "math", "textwrap", "copy",
                    "tempfile", "shutil", "subprocess", "io", "ast", "enum",
                    "logging", "traceback",
                ):
                    pass  # stdlib
                else:
                    external.append(name)
    return (internal, external)


def _has_side_effects(tree: ast.AST) -> bool:
    """Check if module performs I/O or modifies global state."""
    io_calls = {"open", "print", "write", "read", "json.dump", "json.load",
                "os.remove", "os.rename", "os.mkdir", "os.makedirs",
                "shutil.rmtree", "shutil.copy", "subprocess.run",
                "subprocess.call", "subprocess.Popen"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in io_calls:
                return True
            if isinstance(node.func, ast.Attribute):
                full = _resolve_attr_path(node.func)
                if full in io_calls:
                    return True
    return False


def _resolve_attr_path(node: ast.Attribute) -> str:
    """Resolve an ast.Attribute chain to a dotted string."""
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _count_truth_sources(tree: ast.AST) -> int:
    """Count truth-source markers in the module.

    A "truth source" is a module that creates NEW authoritative data
    (not derived from events or upstream sources). Detects:
      - Classes with "SourceOfTruth" in name (explicit marker)
      - Docstrings claiming "source of truth" for the module
      - Classes that define new EventType enums (origin patterns)

    Does NOT count: ExecutionTruthSnapshot, TruthDiff, TruthLinkedRecallRuntime
    (these operate ON truth, not AS truth).
    """
    count = 0
    # Check docstring for explicit truth-source claim.
    # "Events are the source of truth" → references events, not self.
    # "This module is the source of truth" → self-claim. Only count self-claims.
    doc = ast.get_docstring(tree)
    if doc:
        doc_lower = doc.lower()
        if "source of truth" in doc_lower:
            # If doc mentions events/event-log/execution-events as the source,
            # it's referencing the event system, not claiming self as source.
            if re.search(r'events?\s+(is|are|remain)', doc_lower):
                pass
            elif "event log" in doc_lower and "source of truth" in doc_lower:
                pass
            elif "this module" in doc_lower and "source of truth" in doc_lower:
                count += 1

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Only "SourceOfTruth" — not TruthSnapshot, TruthDiff, TruthLinked*
            if "SourceOfTruth" in node.name:
                count += 1
    return count


def _is_projection_only(tree: ast.AST, filepath: str) -> bool:
    """Check if module outputs are projections of external data.

    A module is projection-only if:
      - It has no truth-source classes
      - It imports from known source-of-truth modules
      - Its docstring mentions "projection"
    """
    # Check docstring for projection marker
    doc = ast.get_docstring(tree)
    if doc and "projection" in doc.lower():
        return True
    # If it has truth sources, it's not projection-only
    if _count_truth_sources(tree) > 0:
        return False
    # kernel/ files with events or truth_model are source of truth
    if "truth_model" in filepath or "events.py" in filepath:
        return False
    return True


def _is_removable(filepath: str) -> bool:
    """Check if module is in a removable directory (memory/ or exports/)."""
    normalized = filepath.replace("\\", "/")
    return normalized.startswith("memory/") or normalized.startswith("exports/")


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def analyze_module(
    filepath: str,
    base_dir: str = "",
) -> Optional[ModuleComplexity]:
    """Analyze a single Python module and return its complexity metrics.

    Args:
        filepath: Absolute or relative path to the .py file
        base_dir: Base directory for computing relative paths

    Returns:
        ModuleComplexity or None if file can't be parsed.
    """
    if not filepath.endswith(".py"):
        return None
    if not os.path.exists(filepath):
        return None

    tree = _parse_file(filepath)
    if tree is None:
        return None

    rel_path = filepath
    if base_dir:
        rel_path = os.path.relpath(filepath, base_dir).replace("\\", "/")

    loc = _count_loc(filepath)
    public_api = _count_public_functions(tree)
    dataclasses = _count_dataclasses(tree)
    functions = _count_all_functions(tree)
    imports = _count_imports(tree)
    internal_deps, external_deps = _extract_imports(tree)
    side_effects = _has_side_effects(tree)
    truth_sources = _count_truth_sources(tree)
    projection = _is_projection_only(tree, rel_path)
    removable = _is_removable(rel_path)

    module = ModuleComplexity(
        path=rel_path,
        loc=loc,
        public_api_count=public_api,
        dataclass_count=dataclasses,
        function_count=functions,
        import_count=imports,
        internal_dependency_count=len(set(internal_deps)),
        external_dependency_count=len(set(external_deps)),
        test_count=0,  # Filled later by count_tests_for_module
        report_count=0,  # Filled later by count_reports_for_module
        has_side_effects=side_effects,
        truth_source_count=truth_sources,
        projection_only=projection,
        removable=removable,
    )
    return ModuleComplexity(
        path=module.path,
        loc=module.loc,
        public_api_count=module.public_api_count,
        dataclass_count=module.dataclass_count,
        function_count=module.function_count,
        import_count=module.import_count,
        internal_dependency_count=module.internal_dependency_count,
        external_dependency_count=module.external_dependency_count,
        test_count=module.test_count,
        report_count=module.report_count,
        has_side_effects=module.has_side_effects,
        truth_source_count=module.truth_source_count,
        projection_only=module.projection_only,
        removable=module.removable,
        complexity_score=compute_complexity_score(module),
    )


def analyze_directory(
    directory: str,
    *,
    recursive: bool = True,
    exclude_init: bool = True,
) -> Tuple[ModuleComplexity, ...]:
    """Analyze all Python modules in a directory.

    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories
        exclude_init: Exclude __init__.py files

    Returns:
        Tuple of ModuleComplexity objects, sorted by path.
    """
    results = []

    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ and hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for fname in sorted(files):
            if not fname.endswith(".py"):
                continue
            if exclude_init and fname == "__init__.py":
                continue

            full_path = os.path.join(root, fname)
            module = analyze_module(full_path, base_dir=directory)
            if module is not None:
                results.append(module)

        if not recursive:
            break

    return tuple(results)


def count_tests_for_module(
    module_path: str,
    tests_dir: str,
) -> int:
    """Count test functions in the test file matching a module.

    Maps patterns like:
      kernel/execution_engine.py → test_execution_engine.py or test_kernel_*.py
      memory/runtime.py → test_memory_runtime*.py
    """
    basename = os.path.basename(module_path).replace(".py", "")
    if not os.path.isdir(tests_dir):
        return 0

    count = 0
    for fname in os.listdir(tests_dir):
        if not fname.endswith(".py"):
            continue
        if basename in fname or fname.replace("test_", "").startswith(basename):
            fpath = os.path.join(tests_dir, fname)
            tree = _parse_file(fpath)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_"):
                        count += 1
    return count


def count_reports_for_module(
    module_path: str,
    exports_dir: str,
) -> int:
    """Count export report files matching a module.

    Maps patterns like:
      kernel/execution_engine.py → execution_*.md, execution_*.json
      memory/runtime.py → memory_runtime_*.md, memory_*.json
    """
    basename = os.path.basename(module_path).replace(".py", "")
    # Extract a search key: e.g., "memory_compaction" from "compaction.py"
    search_terms = [basename]

    # Add directory-prefixed variation
    dir_part = os.path.dirname(module_path).replace("\\", "/").split("/")[-1]
    if dir_part:
        search_terms.append(f"{dir_part}_{basename}")

    if not os.path.isdir(exports_dir):
        return 0

    count = 0
    for fname in os.listdir(exports_dir):
        fname_lower = fname.lower()
        for term in search_terms:
            if term.lower() in fname_lower:
                count += 1
                break
    return count


# ═══════════════════════════════════════════════════════════════════════
# ComplexityAnalyzer class
# ═══════════════════════════════════════════════════════════════════════

class ComplexityAnalyzer:
    """Deterministic AST-based complexity analyzer.

    Usage:
        analyzer = ComplexityAnalyzer(v3_root="/path/to/v3")
        complexities = analyzer.analyze_all()
        report = analyzer.generate_report()
    """

    def __init__(self, v3_root: str):
        self._v3_root = v3_root
        self._kernel_dir = os.path.join(v3_root, "kernel")
        self._memory_dir = os.path.join(v3_root, "memory")
        self._tests_dir = os.path.join(v3_root, "tests")
        self._exports_dir = os.path.join(v3_root, "exports")
        self._quality_dir = os.path.join(v3_root, "quality")

    def analyze_all(self) -> Tuple[ModuleComplexity, ...]:
        """Analyze all source directories and return complexity metrics."""
        all_modules = []

        # Analyze kernel/
        if os.path.isdir(self._kernel_dir):
            all_modules.extend(analyze_directory(self._kernel_dir))

        # Analyze memory/
        if os.path.isdir(self._memory_dir):
            all_modules.extend(analyze_directory(self._memory_dir))

        # Analyze quality/ (self-analysis)
        if os.path.isdir(self._quality_dir):
            all_modules.extend(analyze_directory(self._quality_dir))

        # Enrich with test and report counts
        enriched = []
        for m in all_modules:
            test_count = count_tests_for_module(m.path, self._tests_dir)
            report_count = count_reports_for_module(m.path, self._exports_dir)
            enriched.append(ModuleComplexity(
                path=m.path,
                loc=m.loc,
                public_api_count=m.public_api_count,
                dataclass_count=m.dataclass_count,
                function_count=m.function_count,
                import_count=m.import_count,
                internal_dependency_count=m.internal_dependency_count,
                external_dependency_count=m.external_dependency_count,
                test_count=test_count,
                report_count=report_count,
                has_side_effects=m.has_side_effects,
                truth_source_count=m.truth_source_count,
                projection_only=m.projection_only,
                removable=m.removable,
                complexity_score=compute_complexity_score(m),
            ))

        return tuple(enriched)

    def generate_report(self) -> dict:
        """Generate a full complexity analysis report."""
        modules = self.analyze_all()

        total_loc = sum(m.loc for m in modules)
        total_complexity = sum(m.complexity_score for m in modules)
        total_tests = sum(m.test_count for m in modules)
        total_reports = sum(m.report_count for m in modules)
        modules_with_side_effects = [m.path for m in modules if m.has_side_effects]
        truth_source_modules = [m.path for m in modules if m.truth_source_count > 0]
        projection_modules = [m.path for m in modules if m.projection_only]
        removable_modules = [m.path for m in modules if m.removable]

        return {
            "summary": {
                "total_modules": len(modules),
                "total_loc": total_loc,
                "total_complexity_score": round(total_complexity, 2),
                "total_tests": total_tests,
                "total_reports": total_reports,
                "avg_loc_per_module": round(total_loc / max(len(modules), 1), 1),
            },
            "risk_factors": {
                "modules_with_side_effects": modules_with_side_effects,
                "truth_source_modules": truth_source_modules,
            },
            "safety_factors": {
                "projection_only_modules": len(projection_modules),
                "removable_modules": len(removable_modules),
            },
            "modules": [m.to_dict() for m in modules],
        }
