"""
SystemKernel CLI — shared path resolution and utility helpers.

Standard library only. No external imports.
Used by all CLI command modules.
"""
from __future__ import annotations

import ast
import json
import os


# ═══════════════════════════════════════════════════════════════════════
# Path resolution
# ═══════════════════════════════════════════════════════════════════════

def _resolve_root() -> str:
    """Resolve the SystemKernel root directory (F:/Claude/SystemKernel)."""
    cli_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(cli_dir))


def _resolve_v3_root() -> str:
    """Resolve the v3/ directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = _resolve_root()
V3_ROOT = _resolve_v3_root()
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")
KERNEL_DIR = os.path.join(V3_ROOT, "kernel")
MEMORY_DIR = os.path.join(V3_ROOT, "memory")
TESTS_DIR = os.path.join(V3_ROOT, "tests")
QUALITY_DIR = os.path.join(V3_ROOT, "quality")
CHECKPOINTS_DIR = os.path.join(V3_ROOT, "checkpoints")
TRACES_DIR = os.path.join(V3_ROOT, "traces")
METRICS_DIR = os.path.join(V3_ROOT, "metrics")
CONFIG_DIR = os.path.join(V3_ROOT, "config")


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _read_json(path: str) -> dict:
    """Read a JSON file, returning empty dict on failure."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _count_test_functions() -> int:
    """Count test_ functions across all test files."""
    total = 0
    if not os.path.isdir(TESTS_DIR):
        return 0
    for fname in sorted(os.listdir(TESTS_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = os.path.join(TESTS_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_"):
                        total += 1
        except (SyntaxError, OSError):
            pass
    return total


def _count_test_files() -> int:
    """Count test files in tests/."""
    if not os.path.isdir(TESTS_DIR):
        return 0
    return sum(1 for f in os.listdir(TESTS_DIR)
               if f.endswith(".py") and not f.startswith("_"))


def _scan_banned_imports(directory: str) -> list:
    """Scan Python files in a directory for banned LLM/vector imports."""
    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "sklearn", "scipy",
    }
    violations = []
    if not os.path.isdir(directory):
        return violations
    for root_dir, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    source = f.read()
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            name = alias.name.split(".")[0]
                            if name in banned:
                                violations.append(f"{os.path.relpath(fpath, ROOT)}: imports {name}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            name = node.module.split(".")[0]
                            if name in banned:
                                violations.append(f"{os.path.relpath(fpath, ROOT)}: imports {name}")
            except (SyntaxError, OSError):
                pass
    return violations


def _check_kernel_imports_memory() -> list:
    """Check if any kernel file imports from v3.memory (boundary violation)."""
    violations = []
    if not os.path.isdir(KERNEL_DIR):
        return violations
    allowed = {"memory_contract.py", "memory_candidate.py", "memory_gateway.py"}
    for fname in os.listdir(KERNEL_DIR):
        if not fname.endswith(".py"):
            continue
        if fname in allowed:
            continue
        fpath = os.path.join(KERNEL_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "v3.memory" in node.module:
                        violations.append(f"{fname} imports {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "v3.memory" in alias.name:
                            violations.append(f"{fname} imports {alias.name}")
        except (SyntaxError, OSError):
            pass
    return violations


def _check_kernel_imports_quality() -> list:
    """Check if any kernel file imports from v3.quality (boundary violation)."""
    violations = []
    if not os.path.isdir(KERNEL_DIR):
        return violations
    for fname in os.listdir(KERNEL_DIR):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(KERNEL_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "v3.quality" in node.module:
                        violations.append(f"{fname} imports {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "v3.quality" in alias.name:
                            violations.append(f"{fname} imports {alias.name}")
        except (SyntaxError, OSError):
            pass
    return violations


def _report_exists(basename: str) -> bool:
    """Check if a report file exists in exports/."""
    return os.path.exists(os.path.join(EXPORTS_DIR, basename))


def _list_report_files() -> list:
    """List report files in exports/."""
    if not os.path.isdir(EXPORTS_DIR):
        return []
    files = []
    for fname in sorted(os.listdir(EXPORTS_DIR)):
        fpath = os.path.join(EXPORTS_DIR, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            files.append((fname, size))
    return files
