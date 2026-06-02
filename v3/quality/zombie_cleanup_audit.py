"""
Zombie Code & Stale Version Cleanup — Audit Tool.

Phase 1 only: audit, no cleanup. Scans for zombie code, stale tests,
docs drift, stale reports, and duplicate content.

Stdlib only. AST/static grep only. No source mutation. Deterministic ordering.
Protected paths never marked safe_to_auto_fix.

Usage:
    python v3/quality/zombie_cleanup_audit.py
    python v3/quality/zombie_cleanup_audit.py --json-output v3/exports/zombie_cleanup_audit.json
    python v3/quality/zombie_cleanup_audit.py --md-output v3/exports/zombie_cleanup_audit.md
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

# ═══════════════════════════════════════════════════════════════════════
# Frozen dataclasses
# ═══════════════════════════════════════════════════════════════════════

CATEGORY_ZOMBIE_CODE = "zombie_code"
CATEGORY_STALE_VERSION = "stale_version"
CATEGORY_STALE_TEST = "stale_test"
CATEGORY_DOCS_DRIFT = "docs_drift"
CATEGORY_STALE_REPORT = "stale_report"
CATEGORY_DUPLICATE_HELPER = "duplicate_helper"
CATEGORY_HUMAN_REVIEW = "human_review"

CONFIDENCE_LOW = "low"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_HIGH = "high"

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

ACTION_KEEP = "keep"
ACTION_REMOVE = "remove"
ACTION_UPDATE = "update"
ACTION_CONSOLIDATE = "consolidate"
ACTION_HUMAN_REVIEW = "human_review"


@dataclass(frozen=True)
class ZombieFinding:
    finding_id: str
    category: str
    path: str
    symbol: str
    evidence: str
    confidence: str
    risk: str
    recommended_action: str
    safe_to_auto_fix: bool
    finding_hash: str = ""

    def __post_init__(self):
        if not self.finding_hash:
            canonical = json.dumps(
                {
                    "category": self.category,
                    "path": self.path,
                    "symbol": self.symbol,
                    "evidence": self.evidence[:200],
                },
                sort_keys=True,
                ensure_ascii=False,
            )
            h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
            object.__setattr__(self, "finding_hash", h)

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "category": self.category,
            "path": self.path,
            "symbol": self.symbol,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "risk": self.risk,
            "recommended_action": self.recommended_action,
            "safe_to_auto_fix": self.safe_to_auto_fix,
            "finding_hash": self.finding_hash,
        }


@dataclass(frozen=True)
class ZombieCleanupAudit:
    scanned_files: int
    findings: Tuple[ZombieFinding, ...]
    safe_remove_count: int
    safe_update_count: int
    human_review_count: int
    protected_count: int
    audit_hash: str = ""

    def __post_init__(self):
        if not self.audit_hash:
            data = {
                "scanned_files": self.scanned_files,
                "finding_ids": sorted(f.finding_id for f in self.findings),
                "safe_remove_count": self.safe_remove_count,
                "safe_update_count": self.safe_update_count,
                "human_review_count": self.human_review_count,
                "protected_count": self.protected_count,
            }
            canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
            h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
            object.__setattr__(self, "audit_hash", h)

    def to_dict(self) -> dict:
        return {
            "scanned_files": self.scanned_files,
            "findings": [f.to_dict() for f in self.findings],
            "safe_remove_count": self.safe_remove_count,
            "safe_update_count": self.safe_update_count,
            "human_review_count": self.human_review_count,
            "protected_count": self.protected_count,
            "audit_hash": self.audit_hash,
        }


# ═══════════════════════════════════════════════════════════════════════
# Protected paths
# ═══════════════════════════════════════════════════════════════════════

PROTECTED_DIRS: FrozenSet[str] = frozenset({
    "v3/kernel",
    "v3/kernel/",
    "v3/checkpoints",
    "v3/traces",
    "v3/metrics",
    "v3/memory/data",
    ".git",
    "node_modules",
    "external_trials",
})

PROTECTED_FILES: FrozenSet[str] = frozenset({
    "api.py",
    "v3/release/archive_manifest.py",
    "v3/release/inventory.py",
    "v3/release/package_manifest.py",
    "v3/release/release_notes.py",
    "v3/release/tag_metadata.py",
    "v3/release/stability_freeze.py",
    "v3/release/validation_matrix.py",
    "v3/release/handoff.py",
    "v3/release/v4_inventory.py",
    "v3/release/v4_package_manifest.py",
    "v3/release/v4_release_notes.py",
    "v3/release/v4_tag_metadata.py",
    "v3/release/v4_validation_matrix.py",
    "v3/release/v4_baseline_guard.py",
    "scripts/verify_v3_baseline.py",
    "scripts/verify_v4_baseline.py",
    "v3/quality/complexity_budget.py",
    "v3/quality/phase_gate.py",
    "v3/quality/v4_simplification_audit.py",
    "v3/quality/analyze_complexity.py",
    "CLAUDE.md",
    "CORE_FREEZE_v1.md",
    "README.md",
})

SCAN_DIRS: Tuple[str, ...] = (
    "v3/external",
    "v3/evals",
    "v3/ops",
    "v3/release",
    "v3/quality",
    "v3/cli",
    "v3/tests",
    "docs",
    "Docs",
    "tools",
    "scripts",
    "v3/exports",
    "v3/memory",
    "v3/integrations",
    "v3/intake",
    "v3/packages",
    "v3/tools",
)

NON_SCAN_EXTS: FrozenSet[str] = frozenset({".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe"})


def _resolve_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _is_protected(rel_path: str) -> bool:
    """Check if a path is in protected directories or files."""
    norm = rel_path.replace("\\", "/")
    for d in PROTECTED_DIRS:
        if norm.startswith(d):
            return True
    for f in PROTECTED_FILES:
        if norm == f or norm.endswith("/" + f):
            return True
    return False


def _rel_path(abs_path: Path, root: Path) -> str:
    try:
        return str(abs_path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(abs_path).replace("\\", "/")


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# Scan functions
# ═══════════════════════════════════════════════════════════════════════


def _find_python_files(root: Path, dirs: Tuple[str, ...]) -> List[Path]:
    """Find all .py files in given directories."""
    files = []
    for d in dirs:
        dpath = root / d
        if not dpath.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(dpath):
            dirnames[:] = [dn for dn in dirnames if dn != "__pycache__"]
            for fn in filenames:
                if fn.endswith(".py"):
                    files.append(Path(dirpath) / fn)
                elif fn.endswith(".pyc"):
                    files.append(Path(dirpath) / fn)
    return sorted(files)


def _find_all_files(root: Path, dirs: Tuple[str, ...], exts: FrozenSet[str] = frozenset()) -> List[Path]:
    """Find all files in given directories, filtering extensions."""
    files = []
    for d in dirs:
        dpath = root / d
        if not dpath.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(dpath):
            dirnames[:] = [dn for dn in dirnames if dn not in ("__pycache__", ".git", "node_modules")]
            for fn in filenames:
                if exts and os.path.splitext(fn)[1] not in exts:
                    continue
                files.append(Path(dirpath) / fn)
    return sorted(files)


def _extract_imports(filepath: Path) -> Set[str]:
    """Extract all imported module names from a Python file."""
    imports = set()
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except (SyntaxError, UnicodeDecodeError):
        pass
    return imports


def _extract_definitions(filepath: Path) -> Dict[str, Set[str]]:
    """Extract functions and classes defined in a Python file.
    Returns {"functions": {...}, "classes": {...}, "private_functions": {...}}."""
    result = {"functions": set(), "classes": set(), "private_functions": set()}
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                result["functions"].add(node.name)
                if node.name.startswith("_") and not node.name.startswith("__"):
                    result["private_functions"].add(node.name)
            elif isinstance(node, ast.ClassDef):
                result["classes"].add(node.name)
                if node.name.startswith("_") and not node.name.startswith("__"):
                    result["private_functions"].add(node.name)
    except (SyntaxError, UnicodeDecodeError):
        pass
    return result


def _read_file(filepath: Path) -> Optional[str]:
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


# ── 1. Zombie Code Scan ──────────────────────────────────────────────


def scan_for_zombie_code(root: Path) -> List[ZombieFinding]:
    """Scan for unreferenced code, stale modules, and zombie helpers."""
    findings = []
    fid = 0

    # 1a. Check v3/main.py — Phase 2 demo, stale version info
    main_py = root / "v3" / "main.py"
    if main_py.exists():
        content = _read_file(main_py)
        if content and "Phase 2" in content and "Phase 3" in content:
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_STALE_VERSION,
                path="v3/main.py",
                symbol="main()",
                evidence="v3/main.py still references 'Phase 2' and 'Next: Phase 3' but codebase is v4.1. "
                         "This is a demo entry point from v3.0 early development.",
                confidence=CONFIDENCE_HIGH,
                risk=RISK_LOW,
                recommended_action=ACTION_HUMAN_REVIEW,
                safe_to_auto_fix=False,
            ))

    # 1b. Check for __pycache__ directories (build artifacts in source control)
    pycache_dirs = []
    for dirpath, dirnames, _ in os.walk(root / "v3"):
        if "__pycache__" in dirnames:
            pycache_dirs.append(str(Path(dirpath) / "__pycache__"))
    if pycache_dirs:
        fid += 1
        findings.append(ZombieFinding(
            finding_id=f"ZC-{fid:03d}",
            category=CATEGORY_ZOMBIE_CODE,
            path="v3/**/__pycache__/",
            symbol="__pycache__",
            evidence=f"{len(pycache_dirs)} __pycache__ directories found in v3/ source tree. "
                     f"These are build artifacts that should be gitignored, not committed.",
            confidence=CONFIDENCE_HIGH,
            risk=RISK_LOW,
            recommended_action=ACTION_REMOVE,
            safe_to_auto_fix=False,  # Requires .gitignore check
        ))

    # 1c. tools/generate_phase_6b_reports.py — one-shot script, not referenced
    tools_dir = root / "tools"
    gen6b = tools_dir / "generate_phase_6b_reports.py"
    if gen6b.exists():
        content = _read_file(gen6b)
        # Check if referenced from anywhere
        ref_count = 0
        for pyf in _find_python_files(root, ("v3", "scripts", "tools")):
            if pyf == gen6b:
                continue
            fc = _read_file(pyf)
            if fc and "generate_phase_6b_reports" in fc:
                ref_count += 1
        if ref_count == 0:
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_ZOMBIE_CODE,
                path="tools/generate_phase_6b_reports.py",
                symbol="generate_phase_6b_reports",
                evidence="One-shot Phase 6B report generator. Not imported or referenced by any other file. "
                         "Phase 6B is complete; this tool is no longer needed.",
                confidence=CONFIDENCE_HIGH,
                risk=RISK_LOW,
                recommended_action=ACTION_REMOVE,
                safe_to_auto_fix=False,  # User should confirm
            ))

    # 1d. tools/bootstrap_claude_projects.ps1 — one-shot bootstrap
    bs_ps1 = tools_dir / "bootstrap_claude_projects.ps1"
    if bs_ps1.exists():
        content = _read_file(bs_ps1)
        ref_count = 0
        for pyf in _find_python_files(root, ("v3",)):
            fc = _read_file(pyf)
            if fc and "bootstrap_claude_projects" in fc:
                ref_count += 1
        if ref_count == 0:
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_ZOMBIE_CODE,
                path="tools/bootstrap_claude_projects.ps1",
                symbol="bootstrap_claude_projects.ps1",
                evidence="One-shot PowerShell bootstrap script for global CLAUDE.md injection. "
                         "Not referenced by any Python code. Bootstrap phase is complete.",
                confidence=CONFIDENCE_MEDIUM,
                risk=RISK_LOW,
                recommended_action=ACTION_HUMAN_REVIEW,
                safe_to_auto_fix=False,
            ))

    # 1e. v3/exports/generate_*_reports.py — report generators in wrong location
    export_generators = [
        "v3/exports/generate_4d6_reports.py",
        "v3/exports/generate_compaction_reports.py",
    ]
    for gen_path in export_generators:
        gen_file = root / gen_path
        if gen_file.exists():
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_ZOMBIE_CODE,
                path=gen_path,
                symbol=gen_file.stem,
                evidence="Report generator script stored inside v3/exports/ instead of tools/ or scripts/. "
                         "These are one-shot generators, not runtime data exports.",
                confidence=CONFIDENCE_HIGH,
                risk=RISK_LOW,
                recommended_action=ACTION_REMOVE,
                safe_to_auto_fix=False,
            ))

    # 1f. Check for Python files that import from non-existent v3_* modules
    # (Skip the audit tool itself and any protected paths)
    _self_path = str(Path(__file__).resolve())
    for pyf in _find_python_files(root, ("v3",)):
        if str(pyf.resolve()) == _self_path:
            continue
        content = _read_file(pyf)
        if not content:
            continue
        if "v3_release" in content or "v3.release.v3_" in content:
            rel = _rel_path(pyf, root)
            if _is_protected(rel):
                continue
            # Only flag if it's a v3_* pattern that's actually a stale reference
            # (not just any "v3_release" string)
            has_stale_import = False
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and ("v3_release" in node.module or "v3_validation" in node.module):
                            has_stale_import = True
                            break
            except SyntaxError:
                pass
            if not has_stale_import:
                continue
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_ZOMBIE_CODE,
                path=rel,
                symbol="v3_* import",
                evidence="Imports reference v3_* modules that no longer exist "
                         "(e.g., v3_release_notes, v3_inventory, v3_validation_matrix).",
                confidence=CONFIDENCE_MEDIUM,
                risk=RISK_LOW,
                recommended_action=ACTION_UPDATE,
                safe_to_auto_fix=False,
            ))

    return findings


# ── 2. Stale Version Scan ────────────────────────────────────────────


def scan_for_stale_versions(root: Path) -> List[ZombieFinding]:
    """Scan for old version remnants and stale references."""
    findings = []
    fid = 100

    # 2a. archive_manifest.py references 9 non-existent phase reports
    archive_manifest = root / "v3" / "release" / "archive_manifest.py"
    if archive_manifest.exists():
        content = _read_file(archive_manifest)
        if content:
            stale_refs = [
                "phase_4d_completion_report.md",
                "phase_5a_gate_report.md",
                "phase_5b_cli_report.md",
                "phase_5c_examples_report.md",
                "phase_5d_repo_intake_report.md",
                "phase_5e_external_registry_report.md",
                "phase_5f_release_freeze_report.md",
                "systemkernel_v3_release_notes.md",
            ]
            missing = []
            exports_dir = root / "v3" / "exports"
            for ref in stale_refs:
                if not (exports_dir / ref).exists():
                    missing.append(ref)
            if missing:
                fid += 1
                findings.append(ZombieFinding(
                    finding_id=f"ZC-{fid:03d}",
                    category=CATEGORY_STALE_VERSION,
                    path="v3/release/archive_manifest.py",
                    symbol="ArchiveManifest.included_reports",
                    evidence=f"archive_manifest.py references {len(missing)} non-existent phase reports: "
                             f"{', '.join(missing[:4])}... "
                             f"These are v3.0-era reports that no longer exist.",
                    confidence=CONFIDENCE_HIGH,
                    risk=RISK_LOW,
                    recommended_action=ACTION_UPDATE,
                    safe_to_auto_fix=False,
                ))

    # 2b. v3/release/v4_inventory.py _BUILD_BLACKLIST references non-existent v3_*.py files
    inventory = root / "v3" / "release" / "v4_inventory.py"
    if inventory.exists():
        content = _read_file(inventory)
        if content and "_BUILD_BLACKLIST" in content:
            blacklisted = [
                "v3/release/v3_validation_matrix.py",
                "v3/release/v3_inventory.py",
                "v3/release/v3_release_notes.py",
                "v3/release/v3_tag_metadata.py",
                "v3/release/v3_package_manifest.py",
                "v3/release/v3_baseline_guard.py",
            ]
            missing = []
            for bl in blacklisted:
                if not (root / bl).exists():
                    missing.append(bl)
            if len(missing) == len(blacklisted):
                fid += 1
                findings.append(ZombieFinding(
                    finding_id=f"ZC-{fid:03d}",
                    category=CATEGORY_STALE_VERSION,
                    path="v3/release/v4_inventory.py",
                    symbol="_BUILD_BLACKLIST",
                    evidence=f"v4_inventory.py blacklists 6 v3_*.py files, but none exist on disk. "
                             f"The blacklist is a dead code remnant from v3→v4 migration.",
                    confidence=CONFIDENCE_HIGH,
                    risk=RISK_LOW,
                    recommended_action=ACTION_UPDATE,
                    safe_to_auto_fix=False,
                ))

    # 2c. Check for v3/release/__pycache__ — committed build artifacts
    pycache = root / "v3" / "release" / "__pycache__"
    if pycache.exists():
        pyc_count = len(list(pycache.glob("*.pyc")))
        if pyc_count > 0:
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_STALE_VERSION,
                path="v3/release/__pycache__/",
                symbol="*.pyc",
                evidence=f"{pyc_count} compiled .pyc files committed in v3/release/__pycache__/. "
                         f"These are build artifacts that should be cleaned and gitignored.",
                confidence=CONFIDENCE_HIGH,
                risk=RISK_LOW,
                recommended_action=ACTION_REMOVE,
                safe_to_auto_fix=False,  # Needs gitignore verification
            ))

    # 2d. Check for old v3.0 references in cli docstrings
    cli_main = root / "v3" / "cli" / "systemkernel.py"
    if cli_main.exists():
        content = _read_file(cli_main)
        if content:
            v3_refs = []
            for line in content.split("\n"):
                if "v3.0" in line and "SystemKernel" in line:
                    v3_refs.append(line.strip())
            if v3_refs:
                fid += 1
                findings.append(ZombieFinding(
                    finding_id=f"ZC-{fid:03d}",
                    category=CATEGORY_STALE_VERSION,
                    path="v3/cli/systemkernel.py",
                    symbol="build_parser() docstring",
                    evidence=f"CLI parser docstring says 'SystemKernel v3.0 Developer CLI' "
                             f"but current version is v4.1.",
                    confidence=CONFIDENCE_HIGH,
                    risk=RISK_LOW,
                    recommended_action=ACTION_UPDATE,
                    safe_to_auto_fix=False,
                ))

    return findings


# ── 3. Stale Tests Scan ──────────────────────────────────────────────


def scan_for_stale_tests(root: Path) -> List[ZombieFinding]:
    """Scan for skipped tests, dead references, and stale fixtures."""
    findings = []
    fid = 200

    tests_dir = root / "v3" / "tests"

    # 3a. Check for test files referencing non-existent modules
    # Build set of known modules (both files and packages)
    known_modules = set()
    for pyf in _find_python_files(root, SCAN_DIRS):
        rel = _rel_path(pyf, root)
        # Add as file module: v3/tests/test_x.py → v3.tests.test_x
        known_modules.add(rel.replace("/", ".").replace(".py", ""))
        # Also add parent as package if __init__.py
        parent_dir = pyf.parent
        init_file = parent_dir / "__init__.py"
        if init_file.exists():
            pkg_path = _rel_path(init_file, root).replace("/", ".").replace(".py", "")
            known_modules.add(pkg_path.rstrip(".__init__"))

    # Also add packages with __init__.py explicitly
    for d in SCAN_DIRS:
        dpath = root / d
        if not dpath.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(dpath):
            dirnames[:] = [dn for dn in dirnames if dn != "__pycache__"]
            if "__init__.py" in filenames:
                rel = _rel_path(Path(dirpath), root)
                known_modules.add(rel.replace("/", "."))

    for test_file in sorted(tests_dir.glob("test_*.py")):
        content = _read_file(test_file)
        if not content:
            continue

        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        test_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    test_imports.add(node.module)

        for imp in test_imports:
            # Convert import path to file path
            imp_path = imp.replace(".", "/") + ".py"
            imp_pkg_path = imp.replace(".", "/") + "/__init__.py"
            if imp.startswith("v3") and imp_path not in known_modules and imp not in known_modules:
                # Check if it's a kernel module (protected)
                if "v3/kernel" in imp_path or "v3/memory" in imp_path:
                    continue
                # Check if the file or package actually exists
                full_path = root / imp_path
                full_pkg_path = root / imp_pkg_path
                if not full_path.exists() and not full_pkg_path.exists():
                    rel = _rel_path(test_file, root)
                    fid += 1
                    findings.append(ZombieFinding(
                        finding_id=f"ZC-{fid:03d}",
                        category=CATEGORY_STALE_TEST,
                        path=rel,
                        symbol=imp,
                        evidence=f"Imports non-existent module: {imp} (neither {imp_path} nor {imp_pkg_path} found)",
                        confidence=CONFIDENCE_HIGH,
                        risk=RISK_MEDIUM,
                        recommended_action=ACTION_HUMAN_REVIEW,
                        safe_to_auto_fix=False,
                    ))

    # 3b. Check for permanently skipped tests
    for test_file in sorted(tests_dir.glob("test_*.py")):
        content = _read_file(test_file)
        if not content:
            continue
        rel = _rel_path(test_file, root)

        if "unittest.skip" in content and "pytest.mark.skip" not in content:
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_STALE_TEST,
                path=rel,
                symbol="unittest.skip",
                evidence="Contains unittest.skip — check if skip reason is still valid.",
                confidence=CONFIDENCE_LOW,
                risk=RISK_LOW,
                recommended_action=ACTION_HUMAN_REVIEW,
                safe_to_auto_fix=False,
            ))

    # 3c. Check for test files that reference blacklisted v3_ release modules
    for test_file in sorted(tests_dir.glob("test_*.py")):
        content = _read_file(test_file)
        if not content:
            continue
        rel = _rel_path(test_file, root)
        if "v3_release_notes" in content or "v3_baseline_guard" in content:
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_STALE_TEST,
                path=rel,
                symbol="v3_release_* reference",
                evidence="References v3.0-era release module names that are blacklisted in v4_inventory.py.",
                confidence=CONFIDENCE_MEDIUM,
                risk=RISK_LOW,
                recommended_action=ACTION_HUMAN_REVIEW,
                safe_to_auto_fix=False,
            ))

    return findings


# ── 4. Docs Drift Scan ────────────────────────────────────────────────


def scan_for_docs_drift(root: Path) -> List[ZombieFinding]:
    """Scan for documentation duplicates, stale commands, and drift."""
    findings = []
    fid = 300

    # 4a. docs/ vs Docs/ — case-sensitivity aware duplicate check
    docs_dir = root / "docs"
    docs_cap_dir = root / "Docs"
    if docs_dir.exists() and docs_cap_dir.exists():
        # Check if they resolve to the same physical directory (case-insensitive FS)
        try:
            same_physical_dir = docs_dir.resolve() == docs_cap_dir.resolve()
        except Exception:
            same_physical_dir = False

        if same_physical_dir:
            # Windows/macOS: docs/ and Docs/ are the same directory.
            # Not a real duplicate — flag as path inconsistency instead.
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_DOCS_DRIFT,
                path="docs/",
                symbol="Case-insensitive filesystem detected",
                evidence="docs/ and Docs/ resolve to the same physical directory on this "
                         "case-insensitive filesystem. Git tracks them as docs/ but "
                         "v4_inventory.py references Docs/. On Linux CI this would be "
                         "a real path mismatch. Consider normalizing to one case.",
                confidence=CONFIDENCE_HIGH,
                risk=RISK_MEDIUM,
                recommended_action=ACTION_HUMAN_REVIEW,
                safe_to_auto_fix=False,
            ))
        else:
            # Case-sensitive FS: real duplicates
            duplicate_count = 0
            duplicate_files = []
            for f in docs_dir.glob("*.md"):
                counterpart = docs_cap_dir / f.name
                if counterpart.exists():
                    c1 = _read_file(f)
                    c2 = _read_file(counterpart)
                    if c1 is not None and c2 is not None and c1 == c2:
                        duplicate_count += 1
                        duplicate_files.append(f.name)

            if duplicate_count > 0:
                inv_content = _read_file(root / "v3" / "release" / "v4_inventory.py")
                inventory_refs_docs_cap = inv_content and '"Docs"' in inv_content

                fid += 1
                findings.append(ZombieFinding(
                    finding_id=f"ZC-{fid:03d}",
                    category=CATEGORY_DOCS_DRIFT,
                    path="docs/ (vs Docs/)",
                    symbol="Duplicate docs directories",
                    evidence=f"{duplicate_count} byte-identical .md files in both docs/ and Docs/. "
                             f"v4_inventory.py references 'Docs/' (capital D), "
                             f"making docs/ (lowercase) a stale duplicate. "
                             f"Duplicates: {', '.join(duplicate_files[:5])}...",
                    confidence=CONFIDENCE_HIGH,
                    risk=RISK_LOW,
                    recommended_action=ACTION_REMOVE,
                    safe_to_auto_fix=False,
                ))

    # 4b. Check CLAUDE.md for commands that reference stale paths
    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        content = _read_file(claude_md)
        if content:
            # Check for stale references to v3_* or phase_
            stale_refs = []
            if "v3.0" in content:
                stale_refs.append("v3.0 (current is v4.1)")
            if stale_refs:
                fid += 1
                findings.append(ZombieFinding(
                    finding_id=f"ZC-{fid:03d}",
                    category=CATEGORY_DOCS_DRIFT,
                    path="CLAUDE.md",
                    symbol="Version references",
                    evidence=f"CLAUDE.md contains stale version references: {', '.join(stale_refs)}",
                    confidence=CONFIDENCE_MEDIUM,
                    risk=RISK_LOW,
                    recommended_action=ACTION_HUMAN_REVIEW,
                    safe_to_auto_fix=False,
                ))

    # 4c. Check README for commands that might not exist
    readme = root / "README.md"
    if readme.exists():
        content = _read_file(readme)
        if content:
            issues = []
            if "v3.0" in content and "v4.1" not in content:
                issues.append("References v3.0 but not v4.1")
            if issues:
                fid += 1
                findings.append(ZombieFinding(
                    finding_id=f"ZC-{fid:03d}",
                    category=CATEGORY_DOCS_DRIFT,
                    path="README.md",
                    symbol="Version info",
                    evidence="; ".join(issues),
                    confidence=CONFIDENCE_MEDIUM,
                    risk=RISK_LOW,
                    recommended_action=ACTION_HUMAN_REVIEW,
                    safe_to_auto_fix=False,
                ))

    # 4d. Check for Docs/ vs CLAUDE.md ECC description conflicts
    ecc_docs = root / "Docs" / "ECC_POSITIONING.md"
    claude_ecc = None
    if claude_md.exists():
        claude_content = _read_file(claude_md)
        if claude_content and "ECC" in claude_content:
            claude_ecc = claude_content
    if ecc_docs.exists() and claude_ecc:
        ecc_content = _read_file(ecc_docs)
        # Basic check: both describe ECC, ensure no contradictions
        if ecc_content and "execution-only" in claude_ecc and "execution-only" in ecc_content:
            pass  # Both consistent
        elif ecc_content and claude_ecc:
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_DOCS_DRIFT,
                path="Docs/ECC_POSITIONING.md vs CLAUDE.md",
                symbol="ECC positioning",
                evidence="ECC description may differ between Docs/ECC_POSITIONING.md and CLAUDE.md. "
                         "Verify both agree ECC is execution-only infrastructure.",
                confidence=CONFIDENCE_LOW,
                risk=RISK_MEDIUM,
                recommended_action=ACTION_HUMAN_REVIEW,
                safe_to_auto_fix=False,
            ))

    return findings


# ── 5. Stale Reports Scan ────────────────────────────────────────────


def scan_for_stale_reports(root: Path) -> List[ZombieFinding]:
    """Scan for stale export reports and runtime data in wrong locations."""
    findings = []
    fid = 400

    exports_dir = root / "v3" / "exports"

    # 5a. Phase-specific reports that are intermediate build artifacts
    phase_patterns = [
        "phase_6_agent_worker_report.md",
        "phase_6a_packaging_report.md",
        "phase_6b_archive_report.md",
        "phase_7_external_tools_summary.md",
        "phase_7_workspace_plane_report.md",
        "phase_7c_context_pack_report.md",
        "phase_7e_usage_adapter_report.md",
        "phase_8_skill_evolution_report.md",
        "phase_9_5_complexity_sanity.json",
        "phase_9_5_complexity_sanity_report.md",
        "phase_9_orchestration_policy_report.md",
        "phase_10_evaluation_harness_report.md",
        "phase_11_productization_ops_report.md",
        "phase_12_v4_release_freeze_report.md",
        "phase_13a_ecc_intake_report.md",
        "phase_13c_simplification_audit_report.md",
        "phase_13d_cli_compression_closure_report.md",
        "phase_13d_cli_compression_report.md",
        "phase_14a_provider_trial_selection_report.md",
        "phase_14b_repomix_evidence.json",
        "phase_14b_repomix_trial_report.md",
        "phase_14b_repomix_trial_summary.json",
    ]

    existing_phase_reports = []
    for pattern in phase_patterns:
        if (exports_dir / pattern).exists():
            existing_phase_reports.append(pattern)

    if existing_phase_reports:
        fid += 1
        findings.append(ZombieFinding(
            finding_id=f"ZC-{fid:03d}",
            category=CATEGORY_STALE_REPORT,
            path="v3/exports/phase_*",
            symbol="Phase build reports",
            evidence=f"{len(existing_phase_reports)} phase-specific reports exist. "
                     f"These are intermediate build artifacts from completed phases. "
                     f"Some may be kept as release inventory evidence; others are stale. "
                     f"Examples: {', '.join(existing_phase_reports[:4])}...",
            confidence=CONFIDENCE_MEDIUM,
            risk=RISK_LOW,
            recommended_action=ACTION_HUMAN_REVIEW,
            safe_to_auto_fix=False,
        ))

    # 5b. Duplicate report pairs (JSON + MD for same topic)
    duplicate_pairs = [
        ("ecc_positioning_report.json", "ecc_positioning_report.md"),
        ("ecc_global_enablement_report.md", "ecc_global_enablement_summary.json"),
        ("provider_trial_selection.json", "provider_trial_selection_report.md"),
        ("v4_simplification_audit.json", "v4_simplification_audit.md"),
        ("intelligence_plane_registry.json", "intelligence_plane_registry_report.md"),
        ("context_pack_adapter_report.json", "context_pack_adapter_architecture.md"),
    ]
    dup_found = []
    for json_f, md_f in duplicate_pairs:
        if (exports_dir / json_f).exists() and (exports_dir / md_f).exists():
            dup_found.append(f"{json_f} + {md_f}")

    if dup_found:
        fid += 1
        findings.append(ZombieFinding(
            finding_id=f"ZC-{fid:03d}",
            category=CATEGORY_STALE_REPORT,
            path="v3/exports/",
            symbol="Duplicate JSON+MD reports",
            evidence=f"{len(dup_found)} report topic(s) have both JSON and MD versions. "
                     f"May be intentional (machine + human readable) or stale duplication. "
                     f"Pairs: {', '.join(dup_found[:3])}...",
            confidence=CONFIDENCE_MEDIUM,
            risk=RISK_LOW,
            recommended_action=ACTION_HUMAN_REVIEW,
            safe_to_auto_fix=False,
        ))

    # 5c. Check for runtime data files in exports (misplaced)
    runtime_indicators = ["usage_sample.jsonl"]
    for ri in runtime_indicators:
        fpath = exports_dir / ri
        if fpath.exists():
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_STALE_REPORT,
                path=f"v3/exports/{ri}",
                symbol=ri,
                evidence="Runtime data file found in v3/exports/. Should be in runtime data path "
                         "(v3/traces/ or v3/metrics/), not exports.",
                confidence=CONFIDENCE_MEDIUM,
                risk=RISK_LOW,
                recommended_action=ACTION_HUMAN_REVIEW,
                safe_to_auto_fix=False,
            ))

    # 5d. checkpoints/*.crash files — stale crash artifacts
    checkpoints_dir = root / "v3" / "checkpoints"
    if checkpoints_dir.exists():
        crash_files = list(checkpoints_dir.glob("*.crash"))
        if crash_files:
            fid += 1
            findings.append(ZombieFinding(
                finding_id=f"ZC-{fid:03d}",
                category=CATEGORY_STALE_REPORT,
                path="v3/checkpoints/*.crash",
                symbol="*.crash",
                evidence=f"{len(crash_files)} .crash checkpoint files found. "
                         f"These are crash artifacts from testing/debugging, not needed for release.",
                confidence=CONFIDENCE_HIGH,
                risk=RISK_LOW,
                recommended_action=ACTION_REMOVE,
                safe_to_auto_fix=False,  # Protected path area, check first
            ))

    return findings


# ── 6. Build Audit ───────────────────────────────────────────────────


def build_zombie_cleanup_audit() -> ZombieCleanupAudit:
    """Build the complete zombie cleanup audit."""
    root = _resolve_root()

    all_findings: List[ZombieFinding] = []

    scanners = [
        ("zombie_code", scan_for_zombie_code),
        ("stale_version", scan_for_stale_versions),
        ("stale_test", scan_for_stale_tests),
        ("docs_drift", scan_for_docs_drift),
        ("stale_report", scan_for_stale_reports),
    ]

    scanned_files = 0
    for py_file in _find_python_files(root, SCAN_DIRS):
        scanned_files += 1

    for scan_name, scan_fn in scanners:
        try:
            findings = scan_fn(root)
            all_findings.extend(findings)
        except Exception as e:
            all_findings.append(ZombieFinding(
                finding_id=f"ERR-{scan_name}",
                category=CATEGORY_HUMAN_REVIEW,
                path="",
                symbol=scan_name,
                evidence=f"Scanner {scan_name} raised: {e}",
                confidence=CONFIDENCE_LOW,
                risk=RISK_LOW,
                recommended_action=ACTION_HUMAN_REVIEW,
                safe_to_auto_fix=False,
            ))

    # Sort by finding_id for deterministic output
    all_findings.sort(key=lambda f: f.finding_id)

    safe_remove = sum(1 for f in all_findings if f.recommended_action == ACTION_REMOVE and f.safe_to_auto_fix)
    safe_update = sum(1 for f in all_findings if f.recommended_action == ACTION_UPDATE and f.safe_to_auto_fix)
    human_review = sum(1 for f in all_findings if f.recommended_action == ACTION_HUMAN_REVIEW)
    protected = 0  # Counted separately

    return ZombieCleanupAudit(
        scanned_files=scanned_files,
        findings=tuple(all_findings),
        safe_remove_count=safe_remove,
        safe_update_count=safe_update,
        human_review_count=human_review,
        protected_count=protected,
    )


# ── 7. Output ─────────────────────────────────────────────────────────


def write_zombie_cleanup_audit_json(audit: ZombieCleanupAudit, path: str) -> str:
    """Write audit to JSON file."""
    out_path = Path(path)
    if not out_path.is_absolute():
        out_path = _resolve_root() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(audit.to_dict(), f, indent=2, ensure_ascii=False, default=str)
    return str(out_path)


def write_zombie_cleanup_audit_md(audit: ZombieCleanupAudit, path: str) -> str:
    """Write audit to Markdown report."""
    out_path = Path(path)
    if not out_path.is_absolute():
        out_path = _resolve_root() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Zombie Code & Stale Version Cleanup — Audit Report")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Audit Hash**: `{audit.audit_hash}`")
    lines.append(f"**Scanned Files**: {audit.scanned_files}")
    lines.append(f"**Total Findings**: {len(audit.findings)}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Category | Count |")
    lines.append(f"|----------|------:|")

    from collections import Counter
    cat_counts = Counter(f.category for f in audit.findings)
    for cat in [CATEGORY_ZOMBIE_CODE, CATEGORY_STALE_VERSION, CATEGORY_STALE_TEST,
                 CATEGORY_DOCS_DRIFT, CATEGORY_STALE_REPORT, CATEGORY_DUPLICATE_HELPER,
                 CATEGORY_HUMAN_REVIEW]:
        lines.append(f"| {cat} | {cat_counts.get(cat, 0)} |")

    lines.append("")
    lines.append(f"- **Safe Auto-Fix Candidates**: {audit.safe_remove_count} remove + {audit.safe_update_count} update")
    lines.append(f"- **Human Review Needed**: {audit.human_review_count}")
    lines.append("")

    # Group by recommendation
    for action_label, action in [
        ("Safe to Remove", ACTION_REMOVE),
        ("Needs Update", ACTION_UPDATE),
        ("Needs Human Review", ACTION_HUMAN_REVIEW),
        ("Keep / Protected", ACTION_KEEP),
    ]:
        group = [f for f in audit.findings if f.recommended_action == action]
        if not group:
            continue
        lines.append(f"## {action_label}")
        lines.append("")
        for f in group:
            safe_label = " [SAFE AUTO]" if f.safe_to_auto_fix else ""
            lines.append(f"### {f.finding_id}: {f.symbol}{safe_label}")
            lines.append("")
            lines.append(f"- **Category**: `{f.category}`")
            lines.append(f"- **Path**: `{f.path}`")
            lines.append(f"- **Confidence**: {f.confidence}")
            lines.append(f"- **Risk**: {f.risk}")
            lines.append(f"- **Evidence**: {f.evidence}")
            lines.append("")

    # Do Not Touch list
    lines.append("## Do Not Touch (Protected)")
    lines.append("")
    lines.append("The following paths are protected and MUST NOT be modified:")
    lines.append("")
    lines.append("| Path | Reason |")
    lines.append("|------|--------|")
    lines.append("| v3/kernel/ | Frozen deterministic core |")
    lines.append("| v3/memory/ runtime | Memory intelligence plane (removable) |")
    lines.append("| v3/release/ (v4_* files) | Release freeze artifacts |")
    lines.append("| v3/checkpoints/ | Runtime checkpoint data |")
    lines.append("| v3/traces/ | Runtime trace data |")
    lines.append("| v3/metrics/ | Runtime metric data |")
    lines.append("| scripts/verify_v*_baseline.py | Baseline verification scripts |")
    lines.append("| api.py | Public API surface (frozen) |")
    lines.append("")

    md = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return str(out_path)


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Zombie Code & Stale Version Cleanup Audit")
    parser.add_argument("--json-output", default="v3/exports/zombie_cleanup_audit.json",
                        help="Path for JSON audit output")
    parser.add_argument("--md-output", default="v3/exports/zombie_cleanup_audit.md",
                        help="Path for Markdown audit output")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output")
    parser.add_argument("--no-md", action="store_true", help="Skip Markdown output")
    args = parser.parse_args()

    print("=" * 60)
    print("  Zombie Code & Stale Version Cleanup — Audit")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    print("\n[1/3] Building audit...")
    audit = build_zombie_cleanup_audit()

    print(f"\n  Scanned files : {audit.scanned_files}")
    print(f"  Total findings: {len(audit.findings)}")
    print(f"  Safe remove   : {audit.safe_remove_count}")
    print(f"  Safe update   : {audit.safe_update_count}")
    print(f"  Human review  : {audit.human_review_count}")
    print(f"  Audit hash    : {audit.audit_hash}")

    if not args.no_json:
        print(f"\n[2/3] Writing JSON report...")
        json_path = write_zombie_cleanup_audit_json(audit, args.json_output)
        print(f"  {json_path}")

    if not args.no_md:
        print(f"\n[3/3] Writing Markdown report...")
        md_path = write_zombie_cleanup_audit_md(audit, args.md_output)
        print(f"  {md_path}")

    print(f"\n[OK] Audit complete.")
    if audit.safe_remove_count > 0:
        print(f"  {audit.safe_remove_count} items safe for auto-removal.")
    if audit.human_review_count > 0:
        print(f"  {audit.human_review_count} items need human review.")
    print(f"  Audit file: {args.json_output}")
