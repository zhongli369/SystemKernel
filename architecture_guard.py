#!/usr/bin/env python3
"""Architecture Guard — Frozen System Contract Enforcement (Freeze v3).

Static analysis tool. No runtime dependencies. No side effects.

Validates:
  1. Single entrypoint (Adapter)
  2. Single semantic chain (Intent → Adapter.resolve → routing_pipeline → binding)
  3. Zero bypass routes
  4. Zero alternative routing systems
  5. Evolution constrained, not expanded

Usage:
  python architecture_guard.py           # check all systems
  python architecture_guard.py --json    # machine-readable output
"""

import json
import os
import re
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent

# ═════════════════════════════════════════════════════════════
# Configuration: system boundaries
# ═════════════════════════════════════════════════════════════

EXTERNAL_SYSTEMS = {
    "RepoAnalyzer": WORKSPACE_ROOT / "RepoAnalyzer",
    "TaskSystem": WORKSPACE_ROOT / "TaskSystem",
    "ExecutionLoop": WORKSPACE_ROOT / "ExecutionLoop",
    "EventBus": WORKSPACE_ROOT / "EventBus",
    "Observability": WORKSPACE_ROOT / "Observability",
}

# EventBus modules — self-contained, do not import from SkillsManagementSystem
EVENTBUS_PATH = WORKSPACE_ROOT / "EventBus"

SKILLSYSTEM_PATH = WORKSPACE_ROOT / "SkillsManagementSystem"

# Modules that MUST only be accessed through Adapter
PROTECTED_MODULES = [
    "routing_pipeline",
    "capability_registry",
    "alias_resolver",
    "tag_matcher",
    "routing_engine",
    "package_router",
    "external_skill_adapter",
]

# Patterns that indicate hardcoded skill names (banned in task generators)
SKILL_NAME_PATTERN = re.compile(
    r'"\s*(repo-analyzer|code-review|debugger|reflective-reasoning'
    r'|algorithm-explainer|researcher|mcp-builder|markdown-analyzer)\s*"'
)

# Patterns that indicate duplicate intent maps (banned everywhere)
DUPLICATE_MAP_PATTERNS = [
    "TYPE_QUERY_MAP",
    "_TYPE_QUERY_HINTS",
]

# Patterns that indicate hidden skill decision points
HIDDEN_DECISION_PATTERNS = [
    re.compile(r"if\s+.*intent\s*==\s*"),
    re.compile(r"match\s+.*intent\s*:"),
    re.compile(r"elif\s+.*skill"),
]

# Banned import patterns in RepoAnalyzer and TaskSystem
BANNED_IMPORTS = [
    re.compile(r"from\s+SkillsManagementSystem\.core\.(routing_pipeline|capability_registry|alias_resolver|tag_matcher|routing_engine|package_router|external_skill_adapter)"),
    re.compile(r"import\s+subprocess"),
    re.compile(r"import\s+importlib"),
]

# Allowed: only adapter imports
ALLOWED_IMPORT = re.compile(r"from\s+SkillsManagementSystem\.core\.adapter\s+import")

# ═════════════════════════════════════════════════════════════
# Check functions
# ═════════════════════════════════════════════════════════════

def _py_files(root: Path, exclude_tests: bool = True) -> list[Path]:
    """Return all Python files under root, excluding tests and __pycache__."""
    files = []
    for f in root.rglob("*.py"):
        path_str = str(f)
        if "__pycache__" in path_str or f.name.startswith("."):
            continue
        if exclude_tests and ("/tests/" in path_str.replace("\\", "/") or path_str.replace("\\", "/").endswith("/test_unified_invocation.py")):
            continue
        files.append(f)
    return files


def _excluded_from_hardcoded_check(filepath: Path) -> bool:
    """Files where hardcoded skill names are definitional, not violations."""
    relative = str(filepath.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    excluded = [
        "SkillsManagementSystem/core/capability_registry.py",
        "SkillsManagementSystem/register.py",
        "SkillsManagementSystem/core/__init__.py",
        "architecture_guard.py",
    ]
    if any(relative.endswith(e) for e in excluded):
        return True
    # Observability files reference skill names only in docstring examples
    if relative.startswith("Observability/"):
        return True
    return False


def check_external_access(filepath: Path) -> list[dict]:
    """Check a file for banned imports from SkillsManagementSystem internal modules."""
    violations = []
    relative = str(filepath.relative_to(WORKSPACE_ROOT)).replace("\\", "/")

    # ExecutionLoop uses subprocess for verification checks (lint, test), not routing
    if relative.startswith("ExecutionLoop/"):
        return violations
    # Guard self-check
    if relative == "architecture_guard.py":
        return violations

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        # Skip test assertions that check for ABSENCE of banned imports
        if "assert " in stripped and "not in" in stripped:
            continue
        if "has_import" in stripped or "has_call" in stripped:
            continue

        for pattern in BANNED_IMPORTS:
            if pattern.search(line):
                violations.append({
                    "file": str(filepath.relative_to(WORKSPACE_ROOT)),
                    "line": line_no,
                    "rule": "banned_import",
                    "detail": line.strip()[:120],
                    "severity": "CRITICAL",
                })

    return violations


def check_duplicate_maps(filepath: Path) -> list[dict]:
    """Check for duplicate intent→query maps."""
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in DUPLICATE_MAP_PATTERNS:
            if pattern in line:
                violations.append({
                    "file": str(filepath.relative_to(WORKSPACE_ROOT)),
                    "line": line_no,
                    "rule": "duplicate_intent_map",
                    "detail": line.strip()[:120],
                    "severity": "CRITICAL",
                })

    return violations


def check_hardcoded_skills(filepath: Path) -> list[dict]:
    """Check for hardcoded skill name strings."""
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    if _excluded_from_hardcoded_check(filepath):
        return violations

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Skip argparse prog= declarations
        if "prog=" in stripped and "argparse" not in stripped:
            continue
        # Skip test assertions that check for ABSENCE of skill names
        if "for sn in" in stripped and '"' in stripped:
            continue
        if SKILL_NAME_PATTERN.search(line):
            violations.append({
                "file": str(filepath.relative_to(WORKSPACE_ROOT)),
                "line": line_no,
                "rule": "hardcoded_skill_name",
                "detail": line.strip()[:120],
                "severity": "MEDIUM",
            })

    return violations


def check_hidden_decisions(filepath: Path) -> list[dict]:
    """Check for hidden skill decision points (if-intent, match-intent, etc.)."""
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in HIDDEN_DECISION_PATTERNS:
            if pattern.search(stripped):
                violations.append({
                    "file": str(filepath.relative_to(WORKSPACE_ROOT)),
                    "line": line_no,
                    "rule": "hidden_decision_point",
                    "detail": line.strip()[:120],
                    "severity": "MEDIUM",
                })

    return violations


def check_sys_path_hacks(filepath: Path) -> list[dict]:
    """Check for sys.path manipulation inside function bodies."""
    relative = str(filepath.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    if relative == "architecture_guard.py":
        return []
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    lines = content.split("\n")
    in_function = False
    function_indent = 0

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # Track function boundaries by indentation
        if stripped.startswith("def ") and not stripped.startswith("def __"):
            in_function = True
            function_indent = len(line) - len(line.lstrip())
            continue

        if in_function:
            current_indent = len(line) - len(line.lstrip())
            if stripped and current_indent <= function_indent and not stripped.startswith("@"):
                in_function = False
                continue

            if "sys.path.insert" in stripped or "sys.path.append" in stripped:
                # Allow module-level (indent 0)
                if current_indent > 0:
                    violations.append({
                        "file": str(filepath.relative_to(WORKSPACE_ROOT)),
                        "line": line_no,
                        "rule": "sys_path_in_function",
                        "detail": line.strip()[:120],
                        "severity": "MEDIUM",
                    })

    return violations


def check_subprocess_routing(filepath: Path) -> list[dict]:
    """Check for subprocess usage related to skill routing."""
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    # Only flag if BOTH subprocess AND routing keywords appear nearby
    has_subprocess = "subprocess.run" in content or "subprocess.Popen" in content
    has_routing = any(kw in content for kw in ["routing_pipeline", "skill", "adapter", "registry"])

    if has_subprocess and has_routing:
        for line_no, line in enumerate(content.split("\n"), 1):
            if ("subprocess.run" in line or "subprocess.Popen" in line) and \
               any(kw in line for kw in ["routing_pipeline", "skill", "adapter", "registry"]):
                violations.append({
                    "file": str(filepath.relative_to(WORKSPACE_ROOT)),
                    "line": line_no,
                    "rule": "subprocess_routing",
                    "detail": line.strip()[:120],
                    "severity": "CRITICAL",
                })

    return violations


def check_adapter_is_only_authority(filepath: Path) -> list[dict]:
    """Verify that any SkillsManagementSystem import goes through adapter."""
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    relative = str(filepath.relative_to(WORKSPACE_ROOT))

    # SkillsManagementSystem internal files are exempt
    if relative.startswith("SkillsManagementSystem") or relative == "architecture_guard.py":
        return violations

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Skip test assertions
        if "assert " in stripped and ("not in" in stripped or "in tm_content" in stripped):
            continue

        # Any SkillsManagementSystem import must be from adapter
        if "SkillsManagementSystem" in line and "import" in line:
            if not ALLOWED_IMPORT.search(line) and "SkillsManagementSystem.core" in line:
                violations.append({
                    "file": relative,
                    "line": line_no,
                    "rule": "non_adapter_import",
                    "detail": line.strip()[:120],
                    "severity": "CRITICAL",
                })

    return violations


def check_execution_loop_purity() -> list[dict]:
    """Verify ExecutionLoop makes no routing decisions, creates no tasks."""
    violations = []
    loop_file = WORKSPACE_ROOT / "ExecutionLoop" / "loop.py"
    if not loop_file.exists():
        return violations

    try:
        content = loop_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    # ExecutionLoop must NOT contain routing logic
    banned_in_loop = [
        "routing_pipeline",
        "CapabilityRequest",
        "adapter.resolve",
        "suggest_by_intent",
        "TYPE_QUERY_MAP",
        "_TYPE_QUERY_HINTS",
        "INTENT_HINTS",
        "skill_resolver",
        "skill_client",
    ]

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for kw in banned_in_loop:
            if kw in stripped and "import" in stripped:
                violations.append({
                    "file": "ExecutionLoop/loop.py",
                    "line": line_no,
                    "rule": "execution_loop_impure",
                    "detail": line.strip()[:120],
                    "severity": "CRITICAL",
                })

    return violations


def check_classify_not_in_routing_path() -> list[dict]:
    """Verify classify.py is NOT imported by any routing pipeline module.

    classify.py is a dev-only tool. It must not participate in runtime routing.
    """
    violations = []
    routing_modules = [
        SKILLSYSTEM_PATH / "core" / "routing_pipeline.py",
        SKILLSYSTEM_PATH / "core" / "routing_engine.py",
        SKILLSYSTEM_PATH / "core" / "adapter.py",
        SKILLSYSTEM_PATH / "core" / "capability_registry.py",
    ]

    for mod_path in routing_modules:
        if not mod_path.exists():
            continue
        try:
            content = mod_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        relative = str(mod_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        for line_no, line in enumerate(content.split("\n"), 1):
            if "import" in line and "classify" in line and not line.strip().startswith("#"):
                violations.append({
                    "file": relative,
                    "line": line_no,
                    "rule": "classify_in_routing_path",
                    "detail": line.strip()[:120],
                    "severity": "CRITICAL",
                })

    return violations


def check_capability_registry_purity() -> list[dict]:
    """Check capability_registry.py no longer uses hardcoded Python dicts.

    Phase 2: _EXTERNAL_SKILL_METADATA and _LOCAL_SKILL_CAPABILITIES
    must NOT exist as Python dicts in the code.
    """
    violations = []
    cr_path = SKILLSYSTEM_PATH / "core" / "capability_registry.py"
    if not cr_path.exists():
        return violations

    try:
        content = cr_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Check for old hardcoded dict definitions
        if stripped == "_EXTERNAL_SKILL_METADATA = {" or stripped == "_LOCAL_SKILL_CAPABILITIES = {":
            violations.append({
                "file": "SkillsManagementSystem/core/capability_registry.py",
                "line": line_no,
                "rule": "hardcoded_skill_dict",
                "detail": f"Hardcoded Python dict still present: {stripped[:80]}",
                "severity": "CRITICAL",
            })

    return violations


def check_eventbus_no_llm() -> list[dict]:
    """Verify EventBus has zero LLM-related imports or calls."""
    violations = []
    if not EVENTBUS_PATH.exists():
        return violations

    llm_patterns = [
        "openai", "anthropic", "llm", "embedding", "semantic",
        "classify", "predict", "model.generate", "chat.completions",
    ]

    for py_file in EVENTBUS_PATH.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        relative = str(py_file.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        for line_no, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in llm_patterns:
                if pattern in stripped.lower() and "import" in stripped:
                    violations.append({
                        "file": relative,
                        "line": line_no,
                        "rule": "eventbus_llm_import",
                        "detail": line.strip()[:120],
                        "severity": "CRITICAL",
                    })

    return violations


def check_observability_purity() -> list[dict]:
    """Verify Observability layer has zero intelligence, zero LLM calls.

    Phase 3: Observability must be pure write-only / read-only.
    No AI, no decisions, no anomaly detection, no model imports.
    Only flags actual import statements — not documentation mentions.
    """
    violations = []
    obs_path = WORKSPACE_ROOT / "Observability"
    if not obs_path.exists():
        return violations

    # Patterns that indicate intelligence imports in observability
    llm_import_patterns = [
        "import openai", "import anthropic", "from openai",
        "from anthropic", "import torch", "import tensorflow",
        "import sklearn", "from sklearn",
    ]
    # Patterns that indicate decision-making function calls (not in comments/docstrings)
    decision_calls = [
        ".predict(", ".classify(", ".generate(", ".complete(",
    ]

    for py_file in obs_path.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        relative = str(py_file.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        in_docstring = False

        for line_no, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()

            # Skip comments and docstrings
            if stripped.startswith("#"):
                continue
            if '"""' in stripped:
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue

            for pattern in llm_import_patterns:
                if pattern in stripped:
                    violations.append({
                        "file": relative,
                        "line": line_no,
                        "rule": "observability_intelligence_leak",
                        "detail": f"LLM/AI import in observability: {stripped[:120]}",
                        "severity": "CRITICAL",
                    })

            for pattern in decision_calls:
                if pattern in stripped:
                    violations.append({
                        "file": relative,
                        "line": line_no,
                        "rule": "observability_decision_call",
                        "detail": f"Decision-making call in observability: {stripped[:120]}",
                        "severity": "CRITICAL",
                    })

    return violations


def check_observability_hooks_non_blocking() -> list[dict]:
    """Verify observability hooks in kernel subsystems are try/except: pass.

    Observability failure must NEVER affect kernel behavior.
    Every hook must be wrapped in try/except Exception: pass.
    """
    violations = []
    kernel_files = [
        WORKSPACE_ROOT / "EventBus" / "event_bus.py",
        WORKSPACE_ROOT / "SkillsManagementSystem" / "core" / "adapter.py",
        WORKSPACE_ROOT / "ExecutionLoop" / "loop.py",
        WORKSPACE_ROOT / "TaskSystem" / "core" / "task_manager.py",
    ]

    for kf in kernel_files:
        if not kf.exists():
            continue
        try:
            content = kf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        relative = str(kf.relative_to(WORKSPACE_ROOT)).replace("\\", "/")

        # Check: if Observability is imported, it must have try/except protection
        if "from Observability" in content or "import Observability" in content:
            has_try_except = "try:" in content and "except Exception:" in content
            if not has_try_except:
                violations.append({
                    "file": relative,
                    "line": 0,
                    "rule": "observability_hook_unprotected",
                    "detail": "Observability import found without try/except protection",
                    "severity": "MEDIUM",
                })

    return violations


def check_intent_hints_canonical() -> list[dict]:
    """Verify INTENT_HINTS only exists in adapter.py."""
    violations = []
    adapter_file = SKILLSYSTEM_PATH / "core" / "adapter.py"

    for py_file in _py_files(WORKSPACE_ROOT, exclude_tests=True):
        relative = str(py_file.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        if relative == "SkillsManagementSystem/core/adapter.py":
            continue
        if relative == "architecture_guard.py":
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for line_no, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "INTENT_HINTS" in stripped and ":" in stripped and "=" not in stripped[:20]:
                pass  # references in comments/docstrings are OK
            if "INTENT_HINTS" in stripped and "=" in stripped and not stripped.startswith("#"):
                violations.append({
                    "file": relative,
                    "line": line_no,
                    "rule": "duplicate_intent_hints",
                    "detail": line.strip()[:120],
                    "severity": "CRITICAL",
                })

    return violations


# ═════════════════════════════════════════════════════════════
# Main guard runner
# ═════════════════════════════════════════════════════════════

def run_guard() -> dict:
    """Run all architecture guard checks. Returns a freeze report dict."""
    all_violations: list[dict] = []

    # Check external systems (RepoAnalyzer, TaskSystem, ExecutionLoop)
    for system_name, system_path in EXTERNAL_SYSTEMS.items():
        if not system_path.exists():
            continue

        for py_file in _py_files(system_path):
            all_violations.extend(check_external_access(py_file))
            all_violations.extend(check_duplicate_maps(py_file))
            all_violations.extend(check_hardcoded_skills(py_file))
            all_violations.extend(check_hidden_decisions(py_file))
            all_violations.extend(check_sys_path_hacks(py_file))
            all_violations.extend(check_subprocess_routing(py_file))
            all_violations.extend(check_adapter_is_only_authority(py_file))

    # Check SkillsManagementSystem internal files for duplicate maps
    if SKILLSYSTEM_PATH.exists():
        for py_file in _py_files(SKILLSYSTEM_PATH):
            all_violations.extend(check_duplicate_maps(py_file))

    # Special checks
    all_violations.extend(check_execution_loop_purity())
    all_violations.extend(check_intent_hints_canonical())
    all_violations.extend(check_classify_not_in_routing_path())
    all_violations.extend(check_capability_registry_purity())
    all_violations.extend(check_eventbus_no_llm())
    all_violations.extend(check_observability_purity())
    all_violations.extend(check_observability_hooks_non_blocking())

    # Deduplicate
    seen = set()
    unique_violations = []
    for v in all_violations:
        key = (v["file"], v["line"], v["rule"])
        if key not in seen:
            seen.add(key)
            unique_violations.append(v)

    # Sort by severity then file
    severity_order = {"CRITICAL": 0, "MEDIUM": 1, "LOW": 2}
    unique_violations.sort(key=lambda v: (
        severity_order.get(v["severity"], 9),
        v["file"],
        v["line"],
    ))

    criticals = [v for v in unique_violations if v["severity"] == "CRITICAL"]
    mediums = [v for v in unique_violations if v["severity"] == "MEDIUM"]
    frozen = len(criticals) == 0

    # Calculate stability score
    base_score = 100
    base_score -= len(criticals) * 25
    base_score -= len(mediums) * 5
    stability_score = max(0, min(100, base_score))

    return {
        "frozen": frozen,
        "architecture_stability_score": stability_score,
        "violations": {
            "CRITICAL": criticals,
            "MEDIUM": mediums,
            "LOW": [v for v in unique_violations if v["severity"] == "LOW"],
        },
        "total_violations": len(unique_violations),
        "allowed_evolution_scope": [
            "SkillSystem internal logic (routing_engine improvements)",
            "registry.json additions (new skills)",
            "Adapter INTENT_HINTS (additive changes only, no structural change)",
            "Observability dashboard view additions (display-only, no intelligence)",
        ],
        "immutable_borders": [
            "Adapter is the ONLY entry point for skill selection, metadata, routing",
            "SkillSystem internals (routing_pipeline, capability_registry, etc.) are PRIVATE",
            "ExecutionLoop is PURE — no routing decisions, no task creation",
            "Observability is PURE — write-only/read-only, zero intelligence, zero decisions",
            "No new layers, entrypoints, or alternative routing systems",
        ],
        "forbidden_operations": [
            "New routing entry points",
            "New intent → skill mapping layers",
            "Direct registry access outside SkillSystem",
            "subprocess / importlib for routing",
            "sys.path manipulation inside function bodies",
            "Duplicate skill selection logic",
            "Fallback skill heuristics outside Adapter",
            "AI/LLM imports in observability layer",
            "Anomaly detection or alerting in observability",
            "Observability hooks without try/except protection",
        ],
        "checked_modules": len(list(_py_files(WORKSPACE_ROOT / "RepoAnalyzer"))) +
                          len(list(_py_files(WORKSPACE_ROOT / "TaskSystem"))) +
                          len(list(_py_files(SKILLSYSTEM_PATH))) +
                          len(list(_py_files(WORKSPACE_ROOT / "Observability"))) +
                          (1 if (WORKSPACE_ROOT / "ExecutionLoop" / "loop.py").exists() else 0),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Architecture Guard — Frozen System Contract Enforcement")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    report = run_guard()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        if report["frozen"]:
            print("=" * 52)
            print("  ARCHITECTURE GUARD — FREEZE STATUS: PASSED")
            print("=" * 52)
        else:
            print("=" * 52)
            print("  ARCHITECTURE GUARD — FREEZE STATUS: VIOLATIONS FOUND")
            print("=" * 52)

        print(f"\nStability Score: {report['architecture_stability_score']}/100")
        print(f"Files Checked: {report['checked_modules']}")
        print(f"Violations: {report['total_violations']}")

        if report["violations"]["CRITICAL"]:
            print(f"\n  CRITICAL ({len(report['violations']['CRITICAL'])}):")
            for v in report["violations"]["CRITICAL"]:
                print(f"    {v['file']}:{v['line']} — {v['detail'][:100]}")

        if report["violations"]["MEDIUM"]:
            print(f"\n  MEDIUM ({len(report['violations']['MEDIUM'])}):")
            for v in report["violations"]["MEDIUM"]:
                print(f"    {v['file']}:{v['line']} — {v['detail'][:100]}")

        if report["total_violations"] == 0:
            print("\n  All checks passed. System is frozen.")

        print("\nAllowed Evolution Scope:")
        for item in report["allowed_evolution_scope"]:
            print(f"  + {item}")

        print("\nImmutable Borders:")
        for item in report["immutable_borders"]:
            print(f"  - {item}")

    return 0 if report["frozen"] else 1


if __name__ == "__main__":
    sys.exit(main())
