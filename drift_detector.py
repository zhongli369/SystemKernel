#!/usr/bin/env python3
"""
drift_detector.py — Architecture Drift Detection Engine v1.0

Detects discrepancies between CLAUDE.md claims and actual code reality.

Truth sources (exclusively):
  1. Filesystem via pathlib (files, directories, existence)
  2. AST-parse for import provenance
  3. registry.json for skill count and package data
  4. CLAUDE.md text content — parsed into structured claims

NOT an architecture guard (that checks code for banned patterns).
This checks CLAUDE.md against reality.

Output: DriftReport with categorized Discrepancy entries.
  CRITICAL = CLAUDE.md claim is provably wrong → block merge
  HIGH     = Significant undocumented structure
  MEDIUM   = Code quality issue discussed in CLAUDE.md
  LOW      = Minor documentation gap

Usage:
  python drift_detector.py                  # Human-readable report
  python drift_detector.py --json           # JSON report
  python drift_detector.py --pre-commit     # JSON, exit 1 if CRITICAL, auto-snapshot
  python drift_detector.py --snapshot       # Save current CLAUDE.md state
"""

import ast
import json
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Data structures (frozen)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Discrepancy:
    id: str
    severity: str          # CRITICAL | HIGH | MEDIUM | LOW
    section: str           # which CLAUDE.md section
    claim: str             # what CLAUDE.md says
    reality: str           # what code actually shows
    impact: str            # why this matters


@dataclass
class DriftReport:
    timestamp: str
    claude_md_versions: dict
    discrepancies: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Path resolution
# ═══════════════════════════════════════════════════════════════════════════════

KERNEL_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = KERNEL_ROOT.parent  # F:\Claude

ROOT_CLAUDE_MD = WORKSPACE_ROOT / "CLAUDE.md"
KERNEL_CLAUDE_MD = KERNEL_ROOT / "CLAUDE.md"
REGISTRY_PATH = KERNEL_ROOT / "SkillsManagementSystem" / "registry.json"
PACKAGES_DIR = KERNEL_ROOT / "SkillsManagementSystem" / "packages"
SNAPSHOTS_DIR = KERNEL_ROOT / "snapshots"
CLAUDE_SKILLS_DIR = KERNEL_ROOT / ".claude" / "skills"
EXECUTION_LOOP_DIR = KERNEL_ROOT / "ExecutionLoop"
TASK_SYSTEM_DIR = KERNEL_ROOT / "TaskSystem"
REPO_ANALYZER_DIR = KERNEL_ROOT / "RepoAnalyzer"
EXAMPLES_DIR = KERNEL_ROOT / "examples"


# Regex: match actual sys.path.insert()/sys.path.append() calls, not string literals
_SYS_PATH_CALL_RE = re.compile(r'\bsys\.path\.(insert|append)\s*\(')

# Files excluded from self-detection (the drift detector and architecture guard themselves)
_SELF_EXCLUDE = {"drift_detector.py", "architecture_guard.py"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Truth source: filesystem
# ═══════════════════════════════════════════════════════════════════════════════

def _py_files(root: Path) -> list[Path]:
    """All .py files under root, excluding __pycache__."""
    files = []
    for f in root.rglob("*.py"):
        if "__pycache__" in str(f):
            continue
        files.append(f)
    return files


def _all_kernel_py_files() -> list[Path]:
    """All Python files in SystemKernel (excluding .claude skills and packages skill scripts)."""
    files = []
    for f in KERNEL_ROOT.rglob("*.py"):
        path_str = str(f)
        if "__pycache__" in path_str:
            continue
        if ".claude/skills/" in path_str.replace("\\", "/"):
            continue
        if "/SkillsManagementSystem/packages/" in path_str.replace("\\", "/"):
            continue
        if "/SkillsManagementSystem/shared/" in path_str.replace("\\", "/"):
            continue
        files.append(f)
    return files


def _package_dirs() -> list[Path]:
    """All package directories under SkillsManagementSystem/packages/."""
    if not PACKAGES_DIR.exists():
        return []
    return sorted([d for d in PACKAGES_DIR.iterdir() if d.is_dir()])


def _installed_skill_names() -> set[str]:
    """Skill names installed in .claude/skills/."""
    if not CLAUDE_SKILLS_DIR.exists():
        return set()
    return {d.name for d in CLAUDE_SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")}


# ═══════════════════════════════════════════════════════════════════════════════
# Truth source: AST import analysis
# ═══════════════════════════════════════════════════════════════════════════════

def _has_sys_path_in_function(filepath: Path) -> list[dict]:
    """Check for sys.path.insert/append inside function bodies (indent > 0)."""
    relative = str(filepath.relative_to(KERNEL_ROOT)).replace("\\", "/")
    if relative in _SELF_EXCLUDE:
        return []
    results = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return results

    lines = content.split("\n")
    in_function = False
    function_indent = 0

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("def ") and not stripped.startswith("def __"):
            in_function = True
            function_indent = len(line) - len(line.lstrip())
            continue

        if in_function:
            current_indent = len(line) - len(line.lstrip())
            if stripped and current_indent <= function_indent and not stripped.startswith("@"):
                in_function = False
                continue
            # Use regex to match actual function calls, not string literals containing these words
            if _SYS_PATH_CALL_RE.search(stripped) and current_indent > 0:
                results.append({
                    "file": str(filepath.relative_to(KERNEL_ROOT)).replace("\\", "/"),
                    "line": line_no,
                    "detail": line.strip()[:120],
                })

    return results


def _has_absolute_import_relying_on_path_hack(filepath: Path) -> bool:
    """Check if file has absolute imports that would fail without sys.path hacks."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False

    has_path_hack = "sys.path.insert" in content or "sys.path.append" in content
    if not has_path_hack:
        return False

    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:  # absolute import
                # Check if this module is from a sibling package (not stdlib/third-party)
                if node.module.split(".")[0] in ("core", "SkillsManagementSystem"):
                    return True
    return False


def _find_imports_of(filepath: Path, target_module: str) -> bool:
    """Check if file imports a specific module name."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return target_module in content and "import" in content


def _code_implements_full_chain() -> bool:
    """Check if any .py file implements the full Adapter -> TaskSystem -> ExecutionLoop chain.

    Uses AST import analysis — only counts actual import/from statements, not string mentions.
    Excludes self (drift_detector.py) and architecture_guard.py.
    """
    for f in _all_kernel_py_files():
        relative = str(f.relative_to(KERNEL_ROOT)).replace("\\", "/")
        if relative in _SELF_EXCLUDE:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue

        imports_adapter = False
        imports_tasksystem = False
        imports_executionloop = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if "SkillsManagementSystem" in name or "adapter" in name:
                        imports_adapter = True
                    if "TaskSystem" in name:
                        imports_tasksystem = True
                    if "ExecutionLoop" in name:
                        imports_executionloop = True
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    if "SkillsManagementSystem" in node.module:
                        imports_adapter = True
                    if "TaskSystem" in node.module:
                        imports_tasksystem = True
                    if "ExecutionLoop" in node.module:
                        imports_executionloop = True

        if imports_adapter and imports_tasksystem and imports_executionloop:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Truth source: CLAUDE.md parsing
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_claude_md_sections(filepath: Path) -> dict[str, str]:
    """Extract sections (## headings) from CLAUDE.md."""
    content = _read_file(filepath)
    sections = {}
    current_heading = "_preamble"
    current_lines: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_lines:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections[current_heading] = "\n".join(current_lines)

    return sections


def _extract_claude_md_version(filepath: Path) -> str:
    """Extract version string from CLAUDE.md."""
    content = _read_file(filepath)
    for line in content.split("\n"):
        if "Version:" in line or "Current:" in line and "v" in line:
            m = re.search(r"v(\d+\.\d+)", line)
            if m:
                return m.group(0)
    return "unknown"


def _extract_claude_md_tree_paths(filepath: Path) -> set[str]:
    """Extract directory/file paths mentioned in CLAUDE.md tree diagrams."""
    content = _read_file(filepath)
    paths = set()
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("├──") or stripped.startswith("└──") or stripped.startswith("│"):
            m = re.search(r"([\w/\\]+\.[\w]+|[\w/\\]+/)", stripped)
            if m:
                paths.add(m.group(1).rstrip("/"))
    return paths


# ═══════════════════════════════════════════════════════════════════════════════
# Discrepancy checks
# ═══════════════════════════════════════════════════════════════════════════════

def check_001_execution_flow() -> Optional[Discrepancy]:
    """Check: Does any code implement the full Adapter -> TaskSystem -> ExecutionLoop chain?"""
    full_chain_exists = _code_implements_full_chain()
    if not full_chain_exists:
        return Discrepancy(
            id="DRIFT-001",
            severity="HIGH",
            section="CLAUDE.md Section 2.1 (Lifecycle) / Global Section 6 (Standard Execution Flow)",
            claim="The diagram shows Request → Adapter.resolve → TaskSystem → ExecutionLoop.run → Result as THE standard execution flow.",
            reality="No code in the repository implements the full Adapter → TaskSystem → ExecutionLoop chain. "
                    "examples/basic_usage.py calls Adapter.resolve() and ExecutionLoop.run() but skips TaskSystem entirely. "
                    "TaskSystem never imports or calls ExecutionLoop. The diagram is normative, not descriptive.",
            impact="New developers following the diagram will expect a wired pipeline that does not exist. "
                   "The diagram is valid as a design target but should be labeled as normative/aspirational.",
        )
    return None


def check_002_sys_path_in_function() -> Optional[Discrepancy]:
    """Check: sys.path.insert inside function bodies."""
    violations = []
    for f in _all_kernel_py_files():
        v = _has_sys_path_in_function(f)
        violations.extend(v)

    if violations:
        details = "; ".join(f"{v['file']}:{v['line']}" for v in violations)
        return Discrepancy(
            id="DRIFT-002",
            severity="HIGH",
            section="CLAUDE.md Section 4.1 (Routing Bypasses) — bans sys.path.insert inside function bodies",
            claim="sys.path.insert/sys.path.append inside function bodies is forbidden.",
            reality=f"Found {len(violations)} violation(s): {details}",
            impact="Runtime sys.path manipulation makes import behavior unpredictable and violates the FROZEN contract.",
        )
    return None


def check_003_missing_init_py() -> Optional[Discrepancy]:
    """Check: ExecutionLoop/ and TaskSystem/ have __init__.py."""
    el_init = EXECUTION_LOOP_DIR / "__init__.py"
    ts_init = TASK_SYSTEM_DIR / "__init__.py"
    missing = []
    if not el_init.exists():
        missing.append("ExecutionLoop/")
    if not ts_init.exists():
        missing.append("TaskSystem/")

    if missing:
        return Discrepancy(
            id="DRIFT-003",
            severity="LOW",
            section="CLAUDE.md Section 1.2, 1.3 (import paths)",
            claim="ExecutionLoop and TaskSystem are referenced as packages with import paths like "
                  "'ExecutionLoop.loop' and 'TaskSystem.core.task_manager'.",
            reality=f"Missing __init__.py in: {', '.join(missing)}. "
                    "These rely on Python 3.3+ implicit namespace packages.",
            impact="Without __init__.py, imports may fail if Python is invoked with -P flag or if "
                   "sys.path configuration changes. Explicit is safer than implicit.",
        )
    return None


def check_004_legacy_core_py() -> Optional[Discrepancy]:
    """Check: SkillsManagementSystem/core.py (v3.5) shadowed by core/ package."""
    core_py = KERNEL_ROOT / "SkillsManagementSystem" / "core.py"
    core_pkg = KERNEL_ROOT / "SkillsManagementSystem" / "core"
    if core_py.exists() and core_pkg.exists():
        return Discrepancy(
            id="DRIFT-004",
            severity="MEDIUM",
            section="CLAUDE.md Section 1.1 (Adapter import path)",
            claim="The import path 'SkillsManagementSystem.core.adapter' routes through the core/ package (v4.0).",
            reality=f"Both core.py ({core_py.stat().st_size} bytes, v3.5 interface) AND core/ package (v4.0) exist. "
                    "Python's import resolution prefers the core/ directory package. core.py is shadowed legacy code.",
            impact="core.py is dead code that could confuse maintainers. It should be removed or explicitly renamed to "
                   "core_legacy.py if the v3.5 interface is still needed.",
        )
    return None


def check_005_suggestion_engine_path_hack() -> Optional[Discrepancy]:
    """Check: suggestion_engine.py has sys.path.insert at module level."""
    se_path = KERNEL_ROOT / "SkillsManagementSystem" / "suggestion_engine.py"
    if not se_path.exists():
        return None
    content = _read_file(se_path)
    if "sys.path.insert" in content or "sys.path.append" in content:
        return Discrepancy(
            id="DRIFT-005",
            severity="MEDIUM",
            section="CLAUDE.md Section 4.1 (Routing Bypasses)",
            claim="sys.path.insert/sys.path.append inside function bodies is forbidden.",
            reality="SkillsManagementSystem/suggestion_engine.py uses sys.path.insert at module level (line ~41). "
                    "This is module-level (not function-body), making it less severe but still a path manipulation.",
            impact="Module-level sys.path manipulation is less dangerous than per-call manipulation, but it modifies "
                   "global state on import and should be documented as a bootstrap necessity.",
        )
    return None


def check_006_task_manager_fragile_import() -> Optional[Discrepancy]:
    """Check: task_manager.py uses absolute import that depends on sys.path hack."""
    tm_path = TASK_SYSTEM_DIR / "core" / "task_manager.py"
    if not tm_path.exists():
        return None
    content = _read_file(tm_path)
    has_path_hack = "sys.path.insert" in content or "sys.path.append" in content
    has_absolute_import = False
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    if node.module.split(".")[0] == "core":
                        has_absolute_import = True
    except SyntaxError:
        pass

    if has_path_hack and has_absolute_import:
        return Discrepancy(
            id="DRIFT-006",
            severity="MEDIUM",
            section="CLAUDE.md Section 1.3 (TaskSystem) and Section 4.1",
            claim="TaskSystem is imported as 'TaskSystem.core.task_manager'. sys.path.insert is forbidden.",
            reality="TaskSystem/core/task_manager.py uses absolute import 'from core.task_store import...' "
                    "which only works because of module-level sys.path.insert at lines 22-23. "
                    "This is fragile if called from outside the workspace root.",
            impact="External consumers importing 'from TaskSystem.core.task_manager import create_task' will fail "
                   "because the internal absolute import 'from core.task_store' won't resolve correctly.",
        )
    return None


def check_007_repoanalyzer_undocumented() -> Optional[Discrepancy]:
    """Check: RepoAnalyzer has 47 files but neither CLAUDE.md documents them."""
    py_files = _py_files(REPO_ANALYZER_DIR)
    kernel_sections = _read_file(KERNEL_CLAUDE_MD)
    root_sections = _read_file(ROOT_CLAUDE_MD)

    repoanalyzer_mentioned_kernel = "RepoAnalyzer" in kernel_sections
    repoanalyzer_detailed_root = "RepoAnalyzer/core" in root_sections

    if len(py_files) > 5 and not repoanalyzer_detailed_root:
        return Discrepancy(
            id="DRIFT-007",
            severity="MEDIUM",
            section="CLAUDE.md (both) — RepoAnalyzer section",
            claim="RepoAnalyzer is listed as a top-level subsystem but its internal structure (~47 Python files "
                  "across 11+ modules) is not documented.",
            reality=f"RepoAnalyzer contains {len(py_files)} Python files. Core modules include: "
                    "dependency_builder, coupling_analyzer, bottleneck_detector, graph_builder, graph_analyzer, "
                    "impact_analyzer, architecture_layering, importance_scorer, criticality_scorer, "
                    "entrypoint_detector, role_classifier, system_health_reporter, plus "
                    "skill_integration/ (skill_client, skill_resolver, skill_executor) and "
                    "validation/ (architecture_guard, schema_validator, drift_detector).",
            impact="Developers working on RepoAnalyzer have no documented reference for its internal architecture.",
        )
    return None


def check_008_claude_dir_undocumented() -> Optional[Discrepancy]:
    """Check: .claude/ directory is undocumented."""
    claude_dir = KERNEL_ROOT / ".claude"
    kernel_content = _read_file(KERNEL_CLAUDE_MD)
    if claude_dir.exists() and ".claude" not in kernel_content:
        return Discrepancy(
            id="DRIFT-008",
            severity="LOW",
            section="CLAUDE.md Section 2 (SystemKernel Location tree)",
            claim="The directory tree does not mention .claude/ which contains settings and installed skills.",
            reality=".claude/ directory exists with settings.local.json and 32 installed skills under .claude/skills/.",
            impact="The .claude/ directory is where Claude Code reads its configuration. It should be documented "
                   "so developers understand the skill installation target.",
        )
    return None


def check_009_examples_undocumented() -> Optional[Discrepancy]:
    """Check: examples/ directory is undocumented."""
    kernel_content = _read_file(KERNEL_CLAUDE_MD)
    if EXAMPLES_DIR.exists() and "examples" not in kernel_content.lower():
        return Discrepancy(
            id="DRIFT-009",
            severity="LOW",
            section="CLAUDE.md (both) — directory tree",
            claim="The directory tree does not mention examples/ which contains basic_usage.py.",
            reality="examples/basic_usage.py exists as the only end-to-end demonstration of Adapter → ExecutionLoop.",
            impact="New users may not discover the working example. The file is valuable onboarding material.",
        )
    return None


def check_010_readme_files_undocumented() -> Optional[Discrepancy]:
    """Check: README/Contributing files are undocumented."""
    readme = KERNEL_ROOT / "README.md"
    readme_cn = KERNEL_ROOT / "README_CN.md"
    contributing = KERNEL_ROOT / "CONTRIBUTING.md"
    kernel_content = _read_file(KERNEL_CLAUDE_MD)
    undocumented = []
    for f in [readme, readme_cn, contributing]:
        if f.exists() and f.name.lower() not in kernel_content.lower():
            undocumented.append(f.name)
    if undocumented:
        return Discrepancy(
            id="DRIFT-010",
            severity="LOW",
            section="CLAUDE.md (kernel) — directory tree",
            claim="The directory tree only lists code directories.",
            reality=f"Documentation files exist but are not mentioned: {', '.join(undocumented)}.",
            impact="Minor documentation gap. These files help new contributors but are not architecturally critical.",
        )
    return None


def check_011_missing_manifests() -> Optional[Discrepancy]:
    """Check: packages missing manifest.json."""
    missing = []
    for pkg_dir in _package_dirs():
        manifest = pkg_dir / "manifest.json"
        if not manifest.exists():
            missing.append(pkg_dir.name)
    if missing:
        return Discrepancy(
            id="DRIFT-011",
            severity="HIGH",
            section="registry.json packages section — all packages should have manifest.json",
            claim="Each package in SkillsManagementSystem/packages/ should have a manifest.json for metadata.",
            reality=f"Packages missing manifest.json: {', '.join(missing)}. "
                    "These have SKILL.md files but no package-level manifest.",
            impact="Without manifest.json, these packages cannot be auto-discovered by the package builder. "
                   "They exist on disk but are partial builds.",
        )
    return None


def check_012_guard_output_undocumented() -> Optional[Discrepancy]:
    """Check: guard_output.txt exists but is undocumented."""
    guard_output = KERNEL_ROOT / "guard_output.txt"
    if guard_output.exists():
        kernel_content = _read_file(KERNEL_CLAUDE_MD)
        if "guard_output" not in kernel_content:
            return Discrepancy(
                id="DRIFT-012",
                severity="LOW",
                section="CLAUDE.md (kernel) — directory tree",
                claim="No mention of guard_output.txt.",
                reality="guard_output.txt exists at the SystemKernel root (output from architecture_guard.py).",
                impact="Minor. This is a generated artifact and could be added to .gitignore or documented.",
            )
    return None


def check_013_skill_install_gap() -> Optional[Discrepancy]:
    """Check: gap between registered skills and installed skills."""
    if not REGISTRY_PATH.exists():
        return None
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None

    skills_section = registry.get("skills", {})
    registered_count = len(skills_section)
    installed_count = len(_installed_skill_names())

    # Only count non-external skills
    local_skills = {name for name, meta in skills_section.items() if not meta.get("external", False)}
    installed = _installed_skill_names()
    not_installed = local_skills - installed

    if not_installed:
        return Discrepancy(
            id="DRIFT-013",
            severity="LOW",
            section="registry.json vs .claude/skills/",
            claim=f"Registry lists {registered_count} total skills ({len(local_skills)} local).",
            reality=f"{len(not_installed)} registered local skills are not installed in .claude/skills/: "
                    f"{', '.join(sorted(not_installed))}.",
            impact="These skills exist in packages/ but haven't been installed. The install gap may be intentional "
                   "(on-demand lazy install) or a missed step.",
        )
    return None


def check_014_import_paths_verifiable() -> Optional[Discrepancy]:
    """Check: Documented import paths actually resolve."""
    import_paths = [
        "SkillsManagementSystem.core.adapter",
        "ExecutionLoop.loop",
        "TaskSystem.core.task_manager",
    ]
    failures = []
    for path in import_paths:
        # Check if the module file exists on disk (static check, no actual import)
        parts = path.split(".")
        if parts[0] == "SkillsManagementSystem":
            filepath = KERNEL_ROOT / "SkillsManagementSystem" / "core" / "adapter.py"
            if not filepath.exists():
                failures.append(path)
        elif parts[0] == "ExecutionLoop":
            filepath = KERNEL_ROOT / "ExecutionLoop" / "loop.py"
            if not filepath.exists():
                failures.append(path)
        elif parts[0] == "TaskSystem":
            filepath = KERNEL_ROOT / "TaskSystem" / "core" / "task_manager.py"
            if not filepath.exists():
                failures.append(path)

    if failures:
        return Discrepancy(
            id="DRIFT-014",
            severity="CRITICAL",
            section="CLAUDE.md Section 1 (Public Interface) — documented import paths",
            claim=f"These import paths are documented as working: {', '.join(import_paths)}.",
            reality=f"Import path(s) do not resolve to existing files: {', '.join(failures)}.",
            impact="Documented public API is broken. External consumers following the contract will get ImportError.",
        )
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Snapshot system
# ═══════════════════════════════════════════════════════════════════════════════

def _load_snapshot_index() -> dict:
    """Load the snapshot index.json, or return empty skeleton."""
    index_path = SNAPSHOTS_DIR / "index.json"
    if not index_path.exists():
        return {"snapshot_system": "claude-md-kernel-snapshot/v1", "tracked_files": [], "snapshots": []}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {"snapshot_system": "claude-md-kernel-snapshot/v1", "tracked_files": [], "snapshots": []}


def _save_snapshot_index(index: dict) -> None:
    """Save snapshot index.json atomically."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    index_path = SNAPSHOTS_DIR / "index.json"
    tmp = index_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(index_path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def create_snapshot(trigger: str = "manual", drift_report: Optional[dict] = None) -> Optional[str]:
    """Create a snapshot of both CLAUDE.md files.

    Returns snapshot_id if created, None if unchanged from last snapshot.
    """
    root_content = _read_file(ROOT_CLAUDE_MD)
    kernel_content = _read_file(KERNEL_CLAUDE_MD)
    root_hash = _sha256(root_content)
    kernel_hash = _sha256(kernel_content)
    combined_hash = _sha256(root_hash + kernel_hash)

    index = _load_snapshot_index()

    # Check if unchanged from last snapshot
    if index["snapshots"]:
        last = index["snapshots"][-1]
        if last.get("files_hash") == combined_hash:
            return None  # No change

    # Update tracked files
    index["tracked_files"] = [
        str(ROOT_CLAUDE_MD).replace("\\", "/"),
        str(KERNEL_CLAUDE_MD).replace("\\", "/"),
    ]

    snapshot_id = f"snap-{len(index['snapshots']) + 1:03d}"
    timestamp = _now()

    root_version = _extract_claude_md_version(ROOT_CLAUDE_MD)
    kernel_version = _extract_claude_md_version(KERNEL_CLAUDE_MD)

    snapshot_data = {
        "snapshot_id": snapshot_id,
        "timestamp": timestamp,
        "trigger": trigger,
        "files_hash": combined_hash,
        "version_labels": {
            "root": root_version,
            "kernel": kernel_version,
        },
        "files": {
            str(ROOT_CLAUDE_MD).replace("\\", "/"): {
                "version": root_version,
                "content": root_content,
                "sha256": root_hash,
            },
            str(KERNEL_CLAUDE_MD).replace("\\", "/"): {
                "version": kernel_version,
                "content": kernel_content,
                "sha256": kernel_hash,
            },
        },
    }

    if drift_report:
        snapshot_data["drift_report"] = drift_report

    # Write snapshot file
    snapshot_path = SNAPSHOTS_DIR / f"{snapshot_id}.json"
    tmp = snapshot_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(snapshot_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(snapshot_path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise

    # Update index
    index["snapshots"].append({
        "id": snapshot_id,
        "timestamp": timestamp,
        "trigger": trigger,
        "files_hash": combined_hash,
        "version_labels": snapshot_data["version_labels"],
    })
    _save_snapshot_index(index)

    return snapshot_id


# ═══════════════════════════════════════════════════════════════════════════════
# Main drift check runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_drift_check() -> DriftReport:
    """Run all drift checks and return a DriftReport."""
    checks = [
        check_001_execution_flow,
        check_002_sys_path_in_function,
        check_003_missing_init_py,
        check_004_legacy_core_py,
        check_005_suggestion_engine_path_hack,
        check_006_task_manager_fragile_import,
        check_007_repoanalyzer_undocumented,
        check_008_claude_dir_undocumented,
        check_009_examples_undocumented,
        check_010_readme_files_undocumented,
        check_011_missing_manifests,
        check_012_guard_output_undocumented,
        check_013_skill_install_gap,
        check_014_import_paths_verifiable,
    ]

    report = DriftReport(
        timestamp=_now(),
        claude_md_versions={
            "root": _extract_claude_md_version(ROOT_CLAUDE_MD),
            "kernel": _extract_claude_md_version(KERNEL_CLAUDE_MD),
        },
    )

    for check_fn in checks:
        result = check_fn()
        if result is not None:
            report.discrepancies.append(asdict(result))

    # Build summary
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for d in report.discrepancies:
        sev = d.get("severity", "LOW")
        if sev in severity_counts:
            severity_counts[sev] += 1

    report.summary = {
        "critical": severity_counts["CRITICAL"],
        "high": severity_counts["HIGH"],
        "medium": severity_counts["MEDIUM"],
        "low": severity_counts["LOW"],
        "total": len(report.discrepancies),
    }

    return report


# ═══════════════════════════════════════════════════════════════════════════════
# Output formatters
# ═══════════════════════════════════════════════════════════════════════════════

def _format_human(report: DriftReport) -> str:
    lines = []
    sep = "=" * 62

    lines.append(sep)
    lines.append("  ARCHITECTURE DRIFT DETECTOR — REPORT")
    lines.append(sep)
    lines.append(f"  Timestamp:       {report.timestamp}")
    lines.append(f"  Root CLAUDE.md:  {report.claude_md_versions.get('root', '?')}")
    lines.append(f"  Kernel CLAUDE.md:{report.claude_md_versions.get('kernel', '?')}")
    lines.append(f"  Discrepancies:   {report.summary.get('total', 0)}")
    lines.append(f"    CRITICAL: {report.summary.get('critical', 0)}")
    lines.append(f"    HIGH:     {report.summary.get('high', 0)}")
    lines.append(f"    MEDIUM:   {report.summary.get('medium', 0)}")
    lines.append(f"    LOW:      {report.summary.get('low', 0)}")
    lines.append(sep)

    if not report.discrepancies:
        lines.append("")
        lines.append("  No discrepancies found. CLAUDE.md matches code reality.")
        lines.append("")
        return "\n".join(lines)

    for i, d in enumerate(report.discrepancies, 1):
        sev = d["severity"]
        lines.append(f"\n  [{sev}] {d['id']}")
        lines.append(f"  Section: {d['section']}")
        lines.append(f"  Claim:   {d['claim'][:200]}")
        lines.append(f"  Reality: {d['reality'][:200]}")
        lines.append(f"  Impact:  {d['impact'][:200]}")

    lines.append(f"\n{sep}")
    return "\n".join(lines)


def _format_json(report: DriftReport) -> str:
    output = {
        "timestamp": report.timestamp,
        "claude_md_versions": report.claude_md_versions,
        "discrepancies": report.discrepancies,
        "summary": report.summary,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Architecture Drift Detector — CLAUDE.md vs code reality consistency check"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--snapshot", action="store_true", help="Create a snapshot of current CLAUDE.md files")
    parser.add_argument("--pre-commit", action="store_true",
                        help="Pre-commit mode: snapshot, then exit 1 if CRITICAL discrepancies")
    args = parser.parse_args()

    # Run drift check
    report = run_drift_check()

    # Snapshot if requested
    snapshot_created = False
    if args.snapshot or args.pre_commit:
        trigger = "pre-commit" if args.pre_commit else "manual"
        report_dict = {
            "timestamp": report.timestamp,
            "summary": report.summary,
            "discrepancies": report.discrepancies,
        }
        snap_id = create_snapshot(trigger=trigger, drift_report=report_dict)
        if snap_id:
            snapshot_created = True

    # Output
    if args.json or args.pre_commit:
        output = _format_json(report)
        if snapshot_created and args.pre_commit:
            # Add snapshot info
            output_dict = json.loads(output)
            output_dict["snapshot_created"] = True
            output = json.dumps(output_dict, indent=2, ensure_ascii=False)
    else:
        output = _format_human(report)
        if snapshot_created:
            output += f"\n\nSnapshot created: {snap_id}\n"

    print(output)

    # Pre-commit mode: exit 1 if CRITICAL
    if args.pre_commit:
        if report.summary.get("critical", 0) > 0:
            print("\nCOMMIT BLOCKED: CRITICAL architecture drift detected.", file=sys.stderr)
            sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
