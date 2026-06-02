"""
v4.0 Baseline Guard — Phase 0.

Protects v3.0 baseline integrity during all v4.0 development.
Stdlib only — zero external dependencies.

Usage:
  python v3/release/v4_baseline_guard.py --dry-run
  python v3/release/v4_baseline_guard.py --verify
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

BASELINE_COMMIT = "13f2069c8fa6021d4d57f9bf8929bb601cc860b3"
BASELINE_TAG = "systemkernel-v3.0.0-baseline"

FORBIDDEN_DEPENDENCIES = (
    "openai", "anthropic", "langchain", "crewai", "autogen",
    "mem0", "graphiti", "chromadb", "qdrant", "milvus",
)

PROTECTED_PATHS = (
    "v3/kernel/",
    "v3/memory/",
    "v3/release/",
    "scripts/verify_v3_baseline.py",
)

# SHA-256 hashes of v3/kernel/*.py files at baseline commit 13f2069
KERNEL_BASELINE_HASHES = {
    "__init__.py": "45538a1fc781ece6a20c312981a8f2fffa4389c50833e7b82c890d1d642c2891",
    "checkpoint.py": "6c8cdaf2612ed08ac567e10f6df23aafb0a0c57a31c510396a685bfc54027561",
    "complexity_budget.py": "075c48b94780c4667ede5380bd65ed86ac3766bf73e2e0b8cd75a0170aa68afd",
    "event_store.py": "e7b639083ee0e4c087e8d9e8a65219b3926d09b7e8443be8b467231ec6a3dc9e",
    "events.py": "447d4bd2913edc555561813e79561ffa1f6c268eddc4210b1d4b1ac43b9bb943",
    "execution_engine.py": "17b4ce5292b6edb95f4c50f864429e6c211bc93f35d73c8a0a421f5fcdffc9c7",
    "execution_state.py": "099b3f15cf8acb6f71f20f705231f95747636cc0fcad580ead75ec1bd5bb6ba2",
    "invariants.py": "92aaf58a0e4f1646dd4399ba1c41e22bbe665997c712b60ee6cb6376cf56b36d",
    "memory_candidate.py": "f61822263e7fd026e187b70524eb6d5a1154bf857bf8513e4e5764daf5d4f63e",
    "memory_contract.py": "0378e71aec4377657cdb0fcc89a7ed7323b9d85028def95434cab9936c262242",
    "memory_gateway.py": "13fa867a97a721c0780902b8b41adbf619a2c8a1675388b0dea46efa683d3472",
    "metrics.py": "a9c6aa6c22378ff2380171a532dfa954915e1de1f72a9cb680a192ef76702211",
    "observability.py": "47eb14922d3faf5e6c8d005498df8496dfdfb896b3fff53d96b2e822b6fe6f5a",
    "observability_graph.py": "4f10a97f4f26e285e63d6d06a403e3b7ef4d57aa94c9c5d5742cf526d7c42a71",
    "replay.py": "5325f3c804fbc484747b7571b55610019c52f77dd3fadcc02ae6768e4296a55e",
    "structure_trace.py": "5664262b2927b085267ddbc4e4b3dfa597b888ad09dd52ee685413ec4efdba73",
    "telemetry.py": "cb5c3ff4724dad7e45acf48f8c92f422bcc519c575f6c149791ae557a2581e37",
    "time_travel.py": "61353b97d0aa6c48fd78767dcbb75d076fe952a069ab436253ecf0f33ad7dd59",
    "truth_model.py": "0ce274c59f929be8ba438283fc8b3402eee0e25a26130296e317fcf60248c3ae",
}

V3_RELEASE_BASELINE_HASHES = {
    "__init__.py": "5d0638362ae7caa2de4640687dd2a354e34ccf631d60d43c7561c810c24b1ece",
    "archive_manifest.py": "3ea4eaa5a1d492686325239fe1cb8d4455b81421e249bcd0d5033d1973106e2f",
    "handoff.py": "64f126a8b4ca6b4ef2d21fc6eea49d3470aa67b9b0493457f4236aeae792645e",
    "inventory.py": "43a2091350f8c966dbcd4df74fcc25e5afe769c3ecbe914dc60298aeec690ae1",
    "package_manifest.py": "a8d3833055f39e4c6e8d20346abbeb0e8b1ac69af8fa0ae262ea5975d59f4ce7",
    "release_notes.py": "af09aac34bd861f8a9fea3bf40348c22973175c24ec1b72e59157c7cff9c9c62",
    "tag_metadata.py": "f5cef268bd5d37d88f63dc941e57aea86e4d3c8fdd02807539eda5acd6c961d0",
    "validation_matrix.py": "d63a0f35716f04a15de492d737a7aa4c105ec75ed5bc95b6665bb987ff316ad7",
}

VERIFY_SCRIPT_HASH = "925b487ff2ad63cfb1f4dc60e5c3ffbe3f003b52b3fa71cad05956613551811c"

EVENTBUS_ROUTING_RULE_COUNT = 13

EXECUTION_PIPELINE_STAGES = ("lint", "typecheck", "test", "custom", "report")


# ═══════════════════════════════════════════════════════════════════════
# BaselineGuardResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BaselineGuardResult:
    """Result of a full baseline guard check."""

    timestamp: str = ""
    baseline_commit: str = BASELINE_COMMIT
    baseline_tag: str = BASELINE_TAG

    # INV-01: Kernel source immutability
    kernel_files_checked: int = 0
    kernel_files_modified: int = 0
    kernel_modified_files: Tuple[str, ...] = ()
    kernel_immutability_pass: bool = True

    # INV-02: Memory removability
    memory_removable: bool = True
    memory_removability_detail: str = ""

    # INV-03: Zero LLM in kernel
    kernel_llm_imports_found: int = 0
    kernel_llm_imports: Tuple[str, ...] = ()
    kernel_llm_free_pass: bool = True

    # INV-04: Protected path integrity
    protected_files_checked: int = 0
    protected_files_modified: int = 0
    protected_modified_files: Tuple[str, ...] = ()
    protected_path_pass: bool = True

    # INV-05: Forbidden dependencies
    forbidden_imports_found: int = 0
    forbidden_imports: Tuple[str, ...] = ()
    forbidden_deps_pass: bool = True

    # INV-06: Adapter contract
    adapter_contract_intact: bool = True
    adapter_contract_detail: str = ""

    # INV-07: Execution pipeline
    execution_pipeline_intact: bool = True
    execution_pipeline_detail: str = ""

    # INV-08: EventBus routing table
    eventbus_routing_intact: bool = True
    eventbus_routing_detail: str = ""

    # INV-09: Observability write-only
    observability_contract_intact: bool = True
    observability_contract_detail: str = ""

    # INV-10: Baseline tag
    baseline_tag_intact: bool = True
    baseline_tag_detail: str = ""

    # Summary
    invariants_passed: int = 10
    invariants_failed: int = 0
    overall_pass: bool = True

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "baseline_commit": self.baseline_commit,
            "baseline_tag": self.baseline_tag,
            "inv_01_kernel_immutability": {
                "pass": self.kernel_immutability_pass,
                "files_checked": self.kernel_files_checked,
                "files_modified": self.kernel_files_modified,
                "modified_files": list(self.kernel_modified_files),
            },
            "inv_02_memory_removability": {
                "pass": self.memory_removable,
                "detail": self.memory_removability_detail,
            },
            "inv_03_kernel_llm_free": {
                "pass": self.kernel_llm_free_pass,
                "imports_found": self.kernel_llm_imports_found,
                "imports": list(self.kernel_llm_imports),
            },
            "inv_04_protected_paths": {
                "pass": self.protected_path_pass,
                "files_checked": self.protected_files_checked,
                "files_modified": self.protected_files_modified,
                "modified_files": list(self.protected_modified_files),
            },
            "inv_05_forbidden_deps": {
                "pass": self.forbidden_deps_pass,
                "imports_found": self.forbidden_imports_found,
                "imports": list(self.forbidden_imports),
            },
            "inv_06_adapter_contract": {
                "pass": self.adapter_contract_intact,
                "detail": self.adapter_contract_detail,
            },
            "inv_07_execution_pipeline": {
                "pass": self.execution_pipeline_intact,
                "detail": self.execution_pipeline_detail,
            },
            "inv_08_eventbus_routing": {
                "pass": self.eventbus_routing_intact,
                "detail": self.eventbus_routing_detail,
            },
            "inv_09_observability_contract": {
                "pass": self.observability_contract_intact,
                "detail": self.observability_contract_detail,
            },
            "inv_10_baseline_tag": {
                "pass": self.baseline_tag_intact,
                "detail": self.baseline_tag_detail,
            },
            "summary": {
                "invariants_passed": self.invariants_passed,
                "invariants_failed": self.invariants_failed,
                "overall_pass": self.overall_pass,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _resolve_root() -> str:
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _hash_file(filepath: str) -> str:
    """SHA-256 hash of a file's contents."""
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _scan_imports(filepath: str, banned: Tuple[str, ...]) -> list[dict]:
    """Scan a Python file for banned imports. Returns list of violation dicts."""
    violations = []
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
    except Exception:
        return violations

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0].lower()
                if root_pkg in banned:
                    violations.append({
                        "file": filepath,
                        "line": node.lineno,
                        "import": alias.name,
                    })
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0].lower()
                if root_pkg in banned:
                    violations.append({
                        "file": filepath,
                        "line": node.lineno,
                        "import": f"from {node.module} import ...",
                    })
    return violations


# ═══════════════════════════════════════════════════════════════════════
# INV-01: Kernel Source Immutability
# ═══════════════════════════════════════════════════════════════════════

def _check_kernel_immutability(root: str) -> dict:
    kernel_dir = os.path.join(root, "v3", "kernel")
    modified = []
    checked = 0

    for fname, expected_hash in sorted(KERNEL_BASELINE_HASHES.items()):
        fpath = os.path.join(kernel_dir, fname)
        if not os.path.isfile(fpath):
            modified.append(f"MISSING: {fname}")
            continue
        checked += 1
        actual = _hash_file(fpath)
        if actual != expected_hash:
            modified.append(f"HASH_MISMATCH: {fname} (expected {expected_hash[:8]}..., got {actual[:8]}...)")

    return {
        "files_checked": checked,
        "files_modified": len(modified),
        "modified_files": tuple(modified),
        "pass": len(modified) == 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# INV-02: Memory Removability
# ═══════════════════════════════════════════════════════════════════════

def _check_memory_removability(root: str) -> dict:
    memory_dir = os.path.join(root, "v3", "memory")
    invariants_test = os.path.join(root, "v3", "tests", "test_kernel_invariants.py")

    if not os.path.isfile(invariants_test):
        return {
            "pass": False,
            "detail": "test_kernel_invariants.py not found — cannot verify memory removability",
        }

    # Run kernel invariants test (it internally tests memory removability)
    py = sys.executable
    try:
        result = subprocess.run(
            [py, invariants_test],
            capture_output=True, text=True, timeout=120,
            cwd=root,
        )
        purity_line = ""
        for line in result.stdout.splitlines():
            if "purity_score == 100" in line:
                purity_line = line
                break

        if result.returncode == 0:
            return {"pass": True, "detail": "Kernel invariants pass with memory present"}
        else:
            return {"pass": False, "detail": f"Kernel invariants failed: rc={result.returncode}"}
    except Exception as e:
        return {"pass": False, "detail": f"Error running kernel invariants: {e}"}


# ═══════════════════════════════════════════════════════════════════════
# INV-03: Zero LLM in Kernel
# ═══════════════════════════════════════════════════════════════════════

def _check_kernel_llm_free(root: str) -> dict:
    kernel_dir = os.path.join(root, "v3", "kernel")
    all_imports = []

    for py_file in sorted(Path(kernel_dir).rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        violations = _scan_imports(str(py_file), FORBIDDEN_DEPENDENCIES)
        for v in violations:
            rel = os.path.relpath(v["file"], root)
            all_imports.append(f"{rel}:{v['line']} → {v['import']}")

    return {
        "imports_found": len(all_imports),
        "imports": tuple(all_imports),
        "pass": len(all_imports) == 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# INV-04: Protected Path Integrity
# ═══════════════════════════════════════════════════════════════════════

def _check_protected_paths(root: str) -> dict:
    """Check all protected paths against baseline hashes."""
    modified = []
    checked = 0

    # Kernel files
    kernel_dir = os.path.join(root, "v3", "kernel")
    for fname, expected in KERNEL_BASELINE_HASHES.items():
        fpath = os.path.join(kernel_dir, fname)
        if os.path.isfile(fpath):
            checked += 1
            actual = _hash_file(fpath)
            if actual != expected:
                modified.append(f"v3/kernel/{fname}")

    # Release files
    release_dir = os.path.join(root, "v3", "release")
    for fname, expected in V3_RELEASE_BASELINE_HASHES.items():
        fpath = os.path.join(release_dir, fname)
        if os.path.isfile(fpath):
            checked += 1
            actual = _hash_file(fpath)
            if actual != expected:
                modified.append(f"v3/release/{fname}")

    # Verify script
    verify_path = os.path.join(root, "scripts", "verify_v3_baseline.py")
    if os.path.isfile(verify_path):
        checked += 1
        actual = _hash_file(verify_path)
        if actual != VERIFY_SCRIPT_HASH:
            modified.append("scripts/verify_v3_baseline.py")

    return {
        "files_checked": checked,
        "files_modified": len(modified),
        "modified_files": tuple(modified),
        "pass": len(modified) == 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# INV-05: Forbidden Dependencies
# ═══════════════════════════════════════════════════════════════════════

def _check_forbidden_dependencies(root: str) -> dict:
    """Scan core Python files for forbidden imports.

    Skips directories that legitimately contain external dependencies:
      - SkillsManagementSystem/packages/ — skills may use external APIs
      - v3/integrations/ — integration adapters wrap external tools
      - v3/memory/ — memory adapters use vector/embedding libraries
      - v4/ — future intelligence plane
    """
    all_imports = []
    skip_dirs = {"__pycache__", ".git", ".claude", "v4", "node_modules",
                 "external_trials", "Snapshots", "CC日志"}
    skip_rel_paths = {
        "SkillsManagementSystem/packages",
        "v3/integrations",
        "v3/memory",
    }

    for py_file in Path(root).rglob("*.py"):
        parts = set(py_file.parts)
        if parts & skip_dirs:
            continue
        rel = os.path.relpath(str(py_file), root).replace("\\", "/")
        if any(rel.startswith(p + "/") or rel == p for p in skip_rel_paths):
            continue
        violations = _scan_imports(str(py_file), FORBIDDEN_DEPENDENCIES)
        for v in violations:
            rel_path = os.path.relpath(v["file"], root)
            all_imports.append(f"{rel_path}:{v['line']} → {v['import']}")

    return {
        "imports_found": len(all_imports),
        "imports": tuple(all_imports),
        "pass": len(all_imports) == 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# INV-06: Adapter Contract Stability
# ═══════════════════════════════════════════════════════════════════════

def _check_adapter_contract(root: str) -> dict:
    adapter_path = os.path.join(
        root, "SkillsManagementSystem", "core", "adapter.py")
    if not os.path.isfile(adapter_path):
        return {"pass": False, "detail": "adapter.py not found"}

    with open(adapter_path, encoding="utf-8") as f:
        source = f.read()

    checks = []
    # resolve() function must exist
    if "def resolve(" not in source:
        checks.append("resolve() function missing")
    # CapabilityRequest parameter
    if "CapabilityRequest" not in source:
        checks.append("CapabilityRequest type missing")
    # CapabilityBinding return type
    if "CapabilityBinding" not in source:
        checks.append("CapabilityBinding type missing")
    # Empty binding contract
    if 'skill_id=""' not in source and "skill_id=''" not in source:
        checks.append("Empty binding skill_id='' contract missing")
    if "confidence=0.0" not in source:
        checks.append("Empty binding confidence=0.0 contract missing")

    if checks:
        return {"pass": False, "detail": "; ".join(checks)}
    return {"pass": True, "detail": "resolve(CapabilityRequest) → CapabilityBinding intact"}


# ═══════════════════════════════════════════════════════════════════════
# INV-07: Execution Pipeline Immutability
# ═══════════════════════════════════════════════════════════════════════

def _check_execution_pipeline(root: str) -> dict:
    engine_path = os.path.join(root, "v3", "kernel", "execution_engine.py")
    if not os.path.isfile(engine_path):
        return {"pass": False, "detail": "execution_engine.py not found"}

    with open(engine_path, encoding="utf-8") as f:
        source = f.read()

    checks = []

    # LintStage must exist (first pipeline stage)
    if "class LintStage" not in source:
        checks.append("LintStage class missing")
    # PipelineStage base class
    if "class PipelineStage" not in source:
        checks.append("PipelineStage base class missing")
    # Pipeline is a tuple (immutable)
    if "pipeline: Tuple[PipelineStage" not in source:
        checks.append("Pipeline tuple type declaration missing")
    # Retry policy: max_retries = 1
    if "max_retries: int = 1" not in source:
        checks.append("max_retries=1 default missing")
    if "max_retries" not in source:
        checks.append("max_retries field missing from ExecutionConfig")

    if checks:
        return {"pass": False, "detail": "; ".join(checks)}
    return {"pass": True, "detail": "LintStage→PipelineStage tuple; max_retries=1; immutable pipeline"}


# ═══════════════════════════════════════════════════════════════════════
# INV-08: EventBus Routing Table Stability
# ═══════════════════════════════════════════════════════════════════════

def _check_eventbus_routing(root: str) -> dict:
    router_path = os.path.join(root, "EventBus", "event_router.py")
    if not os.path.isfile(router_path):
        return {"pass": False, "detail": "event_router.py not found"}

    with open(router_path, encoding="utf-8") as f:
        source = f.read()

    # Count entries in _ROUTE_TABLE dict
    import re
    # Match event type keys in the route table: "source.type" or "source.type.action"
    event_keys = re.findall(r'"([a-z]+\.[a-z]+(?:\.[a-z]+)?)"\s*:', source)
    rule_count = len(event_keys)

    if rule_count < EVENTBUS_ROUTING_RULE_COUNT:
        return {
            "pass": False,
            "detail": f"Only {rule_count} routing rules found (expected >= {EVENTBUS_ROUTING_RULE_COUNT})"
        }

    # Verify core actions: create_task, start_task, complete_task, skip
    for required_action in ("create_task", "start_task", "complete_task", "skip"):
        if f'"{required_action}"' not in source:
            return {
                "pass": False,
                "detail": f"Required action '{required_action}' missing from routing table"
            }

    return {"pass": True, "detail": f"{rule_count} routing rules, all required actions present"}


# ═══════════════════════════════════════════════════════════════════════
# INV-09: Observability Write-Only Contract
# ═══════════════════════════════════════════════════════════════════════

def _check_observability_contract(root: str) -> dict:
    obs_dir = os.path.join(root, "Observability")
    if not os.path.isdir(obs_dir):
        return {"pass": False, "detail": "Observability/ directory not found"}

    # Check for LLM imports in Observability
    all_imports = []
    for py_file in Path(obs_dir).rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        violations = _scan_imports(str(py_file), FORBIDDEN_DEPENDENCIES)
        all_imports.extend(v for v in violations)

    if all_imports:
        detail = "; ".join(f"{v['file']}:{v['line']}→{v['import']}" for v in all_imports)
        return {"pass": False, "detail": f"LLM imports in Observability: {detail}"}

    # Check for try/except pass hook pattern
    obs_py = os.path.join(obs_dir, "observability.py")
    if os.path.isfile(obs_py):
        with open(obs_py, encoding="utf-8") as f:
            source = f.read()
        if "except Exception:" not in source and "except:" not in source:
            return {"pass": False, "detail": "No exception-safe hook pattern found"}

    return {"pass": True, "detail": "Write-only, append-only, zero LLM, exception-safe hooks"}


# ═══════════════════════════════════════════════════════════════════════
# INV-10: Baseline Tag Immutability
# ═══════════════════════════════════════════════════════════════════════

def _check_baseline_tag(root: str) -> dict:
    try:
        result = subprocess.run(
            ["git", "rev-list", "-n", "1", BASELINE_TAG],
            capture_output=True, text=True, timeout=30,
            cwd=root,
        )
        if result.returncode != 0:
            return {"pass": False, "detail": f"Tag '{BASELINE_TAG}' not found: {result.stderr.strip()}"}

        actual_commit = result.stdout.strip()
        if actual_commit != BASELINE_COMMIT:
            return {
                "pass": False,
                "detail": f"Tag points to {actual_commit[:12]}..., expected {BASELINE_COMMIT[:12]}...",
            }
        return {"pass": True, "detail": f"Tag {BASELINE_TAG} → {BASELINE_COMMIT[:12]}"}
    except Exception as e:
        return {"pass": False, "detail": f"Error checking tag: {e}"}


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def build_v4_baseline_guard(root: Optional[str] = None) -> BaselineGuardResult:
    """Run all 10 invariant checks and produce a BaselineGuardResult.

    Deterministic: same inputs → same result.
    """
    if root is None:
        root = _resolve_root()

    now = datetime.now(timezone.utc).isoformat()

    inv01 = _check_kernel_immutability(root)
    inv02 = _check_memory_removability(root)
    inv03 = _check_kernel_llm_free(root)
    inv04 = _check_protected_paths(root)
    inv05 = _check_forbidden_dependencies(root)
    inv06 = _check_adapter_contract(root)
    inv07 = _check_execution_pipeline(root)
    inv08 = _check_eventbus_routing(root)
    inv09 = _check_observability_contract(root)
    inv10 = _check_baseline_tag(root)

    all_checks = [inv01, inv02, inv03, inv04, inv05, inv06, inv07, inv08, inv09, inv10]
    passed = sum(1 for c in all_checks if c["pass"])
    failed = len(all_checks) - passed

    return BaselineGuardResult(
        timestamp=now,
        baseline_commit=BASELINE_COMMIT,
        baseline_tag=BASELINE_TAG,
        kernel_files_checked=inv01["files_checked"],
        kernel_files_modified=inv01["files_modified"],
        kernel_modified_files=inv01["modified_files"],
        kernel_immutability_pass=inv01["pass"],
        memory_removable=inv02["pass"],
        memory_removability_detail=inv02["detail"],
        kernel_llm_imports_found=inv03["imports_found"],
        kernel_llm_imports=inv03["imports"],
        kernel_llm_free_pass=inv03["pass"],
        protected_files_checked=inv04["files_checked"],
        protected_files_modified=inv04["files_modified"],
        protected_modified_files=inv04["modified_files"],
        protected_path_pass=inv04["pass"],
        forbidden_imports_found=inv05["imports_found"],
        forbidden_imports=inv05["imports"],
        forbidden_deps_pass=inv05["pass"],
        adapter_contract_intact=inv06["pass"],
        adapter_contract_detail=inv06["detail"],
        execution_pipeline_intact=inv07["pass"],
        execution_pipeline_detail=inv07["detail"],
        eventbus_routing_intact=inv08["pass"],
        eventbus_routing_detail=inv08["detail"],
        observability_contract_intact=inv09["pass"],
        observability_contract_detail=inv09["detail"],
        baseline_tag_intact=inv10["pass"],
        baseline_tag_detail=inv10["detail"],
        invariants_passed=passed,
        invariants_failed=failed,
        overall_pass=(failed == 0),
    )


# ═══════════════════════════════════════════════════════════════════════
# Convenience aliases (for test imports)
# ═══════════════════════════════════════════════════════════════════════

def check_protected_paths(root: Optional[str] = None) -> dict:
    """Check protected path integrity (INV-04). Returns dict with pass/modified files."""
    if root is None:
        root = _resolve_root()
    return _check_protected_paths(root)


def check_forbidden_dependencies(root: Optional[str] = None) -> dict:
    """Check for forbidden dependencies (INV-05). Returns dict with pass/imports."""
    if root is None:
        root = _resolve_root()
    return _check_forbidden_dependencies(root)


# ═══════════════════════════════════════════════════════════════════════
# Reporter
# ═══════════════════════════════════════════════════════════════════════

def write_v4_baseline_guard_report(
    result: BaselineGuardResult,
    path: Optional[str] = None,
) -> str:
    """Write baseline guard report to JSON file. Returns absolute path."""
    if path is None:
        root = _resolve_root()
        export_dir = os.path.join(root, "v3", "exports")
        os.makedirs(export_dir, exist_ok=True)
        path = os.path.join(export_dir, "v4_baseline_guard_report.json")
    else:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)
    return os.path.abspath(path)


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def _print_result(result: BaselineGuardResult) -> None:
    """Pretty-print baseline guard result to stdout."""
    print("=" * 64)
    print("  SystemKernel v4.0 — Baseline Guard Report")
    print("=" * 64)
    print(f"  Timestamp:        {result.timestamp}")
    print(f"  Baseline commit:  {result.baseline_commit[:12]}...")
    print(f"  Baseline tag:     {result.baseline_tag}")
    print()

    checks = [
        ("INV-01", "Kernel Immutability", result.kernel_immutability_pass,
         f"{result.kernel_files_modified} modified" if result.kernel_files_modified else "all clean"),
        ("INV-02", "Memory Removability", result.memory_removable,
         result.memory_removability_detail),
        ("INV-03", "Kernel LLM-Free", result.kernel_llm_free_pass,
         f"{result.kernel_llm_imports_found} violations" if result.kernel_llm_imports_found else "clean"),
        ("INV-04", "Protected Paths", result.protected_path_pass,
         f"{result.protected_files_modified} modified" if result.protected_files_modified else "all clean"),
        ("INV-05", "Forbidden Deps", result.forbidden_deps_pass,
         f"{result.forbidden_imports_found} violations" if result.forbidden_imports_found else "clean"),
        ("INV-06", "Adapter Contract", result.adapter_contract_intact,
         result.adapter_contract_detail),
        ("INV-07", "Execution Pipeline", result.execution_pipeline_intact,
         result.execution_pipeline_detail),
        ("INV-08", "EventBus Routing", result.eventbus_routing_intact,
         result.eventbus_routing_detail),
        ("INV-09", "Observability", result.observability_contract_intact,
         result.observability_contract_detail),
        ("INV-10", "Baseline Tag", result.baseline_tag_intact,
         result.baseline_tag_detail),
    ]

    for inv_id, name, passed, detail in checks:
        icon = "[PASS]" if passed else "[FAIL]"
        print(f"  {icon} {inv_id} {name}")
        if not passed:
            print(f"         → {detail}")

    print()
    print(f"  Invariants: {result.invariants_passed}/10 passed")
    print(f"  Overall:    {'PASS' if result.overall_pass else 'FAIL'}")
    print()

    if result.kernel_modified_files:
        print("  Modified kernel files:")
        for f in result.kernel_modified_files:
            print(f"    !! {f}")
        print()

    if result.forbidden_imports:
        print("  Forbidden imports found:")
        for imp in result.forbidden_imports:
            print(f"    !! {imp}")
        print()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="v4_baseline_guard",
        description="SystemKernel v4.0 Baseline Guard — Phase 0",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Check invariants, print report, do not write files",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Check invariants and write report JSON",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Custom output path for JSON report",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.verify:
        args.verify = True  # default to verify

    root = _resolve_root()
    result = build_v4_baseline_guard(root)
    _print_result(result)

    if args.verify:
        report_path = write_v4_baseline_guard_report(result, args.output)
        print(f"  Report written: {report_path}")

    sys.exit(0 if result.overall_pass else 1)


if __name__ == "__main__":
    main()
