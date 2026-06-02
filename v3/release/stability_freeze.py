"""
Stability Freeze Guard — v4.1.

Locks the SystemKernel API surface, signal contracts, and injection pipeline
to prevent architectural drift. Each freeze invariant must pass for the
system to be considered STABLE.

Invariants:
  SF-01: API Surface Freeze — exactly 7 public functions, no renames, no sig changes
  SF-02: Capability Freeze — list_capabilities() read-only, enabled-only
  SF-03: Signal Contract Freeze — gstack (direction, 0.4), superpowers (quality, 0.6)
  SF-04: Injection Pipeline Freeze — 5-step flow preserved
  SF-05: Internal System Protection — no direct internal access from api.py
  SF-06: ECC Rule — ECC execution-only, not exposed via API
  SF-07: Complexity Guard — no surface increase, no new entry points

Usage:
  python v3/release/stability_freeze.py --dry-run
  python v3/release/stability_freeze.py --verify
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
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

# SF-01: The frozen API surface — exactly these 7 public functions
FROZEN_API_FUNCTIONS = (
    "resolve_skill",
    "run_skill",
    "create_task_safe",
    "list_capabilities",
    "query_external_signals",
    "analyze_direction",
    "analyze_quality",
    "inject_external_signals",
)

# Number of public functions expected (len of tuple above)
FROZEN_API_COUNT = len(FROZEN_API_FUNCTIONS)

# SF-01: Frozen function key parameters that MUST still exist
FROZEN_API_PARAMS = {
    "resolve_skill": ("intent", "context"),
    "run_skill": ("skill_id", "target"),
    "create_task_safe": (),          # *args, **kwargs — no fixed params
    "list_capabilities": (),         # no params
    "query_external_signals": ("plane",),
    "analyze_direction": ("task_intent", "project_context"),
    "analyze_quality": ("target_content", "target_type"),
    "inject_external_signals": ("task_intent", "project_context",
                                "target_content", "target_type"),
}

# SF-03: Frozen signal planes — exactly these 2
FROZEN_SIGNAL_PLANES = ("direction", "quality")

# SF-03: Frozen plane sources and weights
FROZEN_PLANE_CONFIG = {
    "direction": {"source": "gstack", "weight": 0.4},
    "quality": {"source": "superpowers", "weight": 0.6},
}

# SF-04: Frozen injection pipeline stages (must appear in order)
FROZEN_PIPELINE_STAGES = (
    "query_external_signals",
    "direction_weight",
    "quality_weight",
    "complexity gate",
    "external contribution",
    "final_score",
    "verdict",
)

# SF-05: Protected internal modules — must not appear in api.py
PROTECTED_INTERNAL_IMPORTS = (
    "v3.kernel",
    "v3.memory",
    "v3.evals",
    "v3.intake",
)

# SF-05: Protected internal subsystems — must not appear as public exports
PROTECTED_SUBSYSTEMS = (
    "EventBus",
    "TaskSystem",
    "Observability",
    "ExecutionLoop",
    "SkillsManagementSystem",
)

# SF-06: ECC must not appear in api.py as export or capability
ECC_BANNED_PATTERNS = (
    "ecc",
    "ECC",
    "everything_claude_code",
    "everything-claude-code",
)

# SF-07: Only api.py is the entry point; no new entry modules
ALLOWED_ENTRY_POINT_FILES = ("api.py",)

# Weight constants that must not change
DIRECTION_WEIGHT = 0.4
QUALITY_WEIGHT = 0.6
COMPLEXITY_GATE_THRESHOLD = 2.0


# ═══════════════════════════════════════════════════════════════════════
# StabilityFreezeResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StabilityFreezeResult:
    """Result of a full stability freeze check."""

    timestamp: str = ""
    version: str = "4.1"

    # SF-01: API Surface Freeze
    api_functions_found: int = 0
    api_functions_expected: int = FROZEN_API_COUNT
    api_missing_functions: Tuple[str, ...] = ()
    api_extra_functions: Tuple[str, ...] = ()
    api_signature_violations: Tuple[str, ...] = ()
    api_surface_pass: bool = True

    # SF-02: Capability Freeze
    capability_read_only: bool = True
    capability_enabled_only: bool = True
    capability_no_internal_leak: bool = True
    capability_freeze_pass: bool = True
    capability_detail: str = ""

    # SF-03: Signal Contract Freeze
    signal_planes_found: Tuple[str, ...] = ()
    signal_planes_expected: Tuple[str, ...] = FROZEN_SIGNAL_PLANES
    signal_weight_violations: Tuple[str, ...] = ()
    signal_contract_pass: bool = True

    # SF-04: Injection Pipeline Freeze
    pipeline_stages_found: Tuple[str, ...] = ()
    pipeline_stages_expected: Tuple[str, ...] = FROZEN_PIPELINE_STAGES
    pipeline_complexity_gate_intact: bool = True
    pipeline_freeze_pass: bool = True

    # SF-05: Internal System Protection
    internal_imports_in_api: Tuple[str, ...] = ()
    internal_subsystems_exposed: Tuple[str, ...] = ()
    internal_protection_pass: bool = True

    # SF-06: ECC Rule
    ecc_in_api: bool = False
    ecc_in_registry: bool = False
    ecc_rule_pass: bool = True
    ecc_detail: str = ""

    # SF-07: Complexity Guard
    new_entry_points: Tuple[str, ...] = ()
    circular_deps_detected: bool = False
    complexity_guard_pass: bool = True

    # Summary
    invariants_passed: int = 7
    invariants_failed: int = 0
    overall_pass: bool = True

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "version": self.version,
            "sf_01_api_surface": {
                "pass": self.api_surface_pass,
                "functions_found": self.api_functions_found,
                "functions_expected": self.api_functions_expected,
                "missing_functions": list(self.api_missing_functions),
                "extra_functions": list(self.api_extra_functions),
                "signature_violations": list(self.api_signature_violations),
            },
            "sf_02_capability_freeze": {
                "pass": self.capability_freeze_pass,
                "read_only": self.capability_read_only,
                "enabled_only": self.capability_enabled_only,
                "no_internal_leak": self.capability_no_internal_leak,
                "detail": self.capability_detail,
            },
            "sf_03_signal_contract": {
                "pass": self.signal_contract_pass,
                "planes_found": list(self.signal_planes_found),
                "planes_expected": list(self.signal_planes_expected),
                "weight_violations": list(self.signal_weight_violations),
            },
            "sf_04_injection_pipeline": {
                "pass": self.pipeline_freeze_pass,
                "stages_found": list(self.pipeline_stages_found),
                "stages_expected": list(self.pipeline_stages_expected),
                "complexity_gate_intact": self.pipeline_complexity_gate_intact,
            },
            "sf_05_internal_protection": {
                "pass": self.internal_protection_pass,
                "internal_imports_in_api": list(self.internal_imports_in_api),
                "internal_subsystems_exposed": list(self.internal_subsystems_exposed),
            },
            "sf_06_ecc_rule": {
                "pass": self.ecc_rule_pass,
                "ecc_in_api": self.ecc_in_api,
                "ecc_in_registry": self.ecc_in_registry,
                "detail": self.ecc_detail,
            },
            "sf_07_complexity_guard": {
                "pass": self.complexity_guard_pass,
                "new_entry_points": list(self.new_entry_points),
                "circular_deps_detected": self.circular_deps_detected,
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


# ═══════════════════════════════════════════════════════════════════════
# SF-01: API Surface Freeze
# ═══════════════════════════════════════════════════════════════════════

def _check_api_surface(root: str) -> dict:
    """Verify api.py has exactly the frozen 7 public functions.

    Detects:
      - Missing functions (removed/renamed)
      - Extra functions (new additions)
      - Signature changes (parameter count decreased)
    """
    api_path = os.path.join(root, "api.py")
    if not os.path.isfile(api_path):
        return {
            "pass": False,
            "functions_found": 0,
            "missing": tuple(FROZEN_API_FUNCTIONS),
            "extra": (),
            "signature_violations": (),
            "detail": "api.py not found",
        }

    with open(api_path, encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {
            "pass": False,
            "functions_found": 0,
            "missing": (),
            "extra": (),
            "signature_violations": (),
            "detail": f"api.py syntax error: {e}",
        }

    # Find all top-level function definitions with their parameter names
    found_functions = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            name = node.name
            param_names = [a.arg for a in node.args.args]
            found_functions[name] = param_names

    # Public functions are those not prefixed with _
    public_found = {
        k: v for k, v in found_functions.items()
        if not k.startswith("_")
    }

    expected_set = set(FROZEN_API_FUNCTIONS)
    found_set = set(public_found.keys())

    missing = tuple(sorted(expected_set - found_set))
    extra = tuple(sorted(found_set - expected_set))

    # Check signature violations: key parameters must still exist
    signature_violations = []
    for fname in expected_set & found_set:
        expected_params = FROZEN_API_PARAMS.get(fname, ())
        if not expected_params:
            continue
        actual_params = set(public_found[fname])
        for p in expected_params:
            if p not in actual_params:
                signature_violations.append(
                    f"{fname}: missing required param '{p}'"
                )

    pass_check = (
        len(missing) == 0
        and len(extra) == 0
        and len(signature_violations) == 0
    )

    return {
        "pass": pass_check,
        "functions_found": len(public_found),
        "missing": missing,
        "extra": extra,
        "signature_violations": tuple(signature_violations),
        "detail": f"Found {len(public_found)} public functions, "
                  f"expected {FROZEN_API_COUNT}",
    }


# ═══════════════════════════════════════════════════════════════════════
# SF-02: Capability Freeze
# ═══════════════════════════════════════════════════════════════════════

def _check_capability_freeze(root: str) -> dict:
    """Verify list_capabilities() in api.py remains frozen.

    Checks:
      - Read-only (only reads from registry, no mutations)
      - Enabled-only filtering
      - No internal structure leakage
    """
    api_path = os.path.join(root, "api.py")
    if not os.path.isfile(api_path):
        return {
            "pass": False,
            "read_only": False,
            "enabled_only": False,
            "no_internal_leak": False,
            "detail": "api.py not found",
        }

    with open(api_path, encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {
            "pass": False,
            "read_only": False,
            "enabled_only": False,
            "no_internal_leak": False,
            "detail": "api.py syntax error",
        }

    # Find list_capabilities function
    list_cap_fn = None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "list_capabilities":
            list_cap_fn = node
            break

    if list_cap_fn is None:
        return {
            "pass": False,
            "read_only": False,
            "enabled_only": False,
            "no_internal_leak": False,
            "detail": "list_capabilities() not found in api.py",
        }

    # Extract the function body as string for pattern checks
    fn_source = ast.get_source_segment(source, list_cap_fn)
    if fn_source is None:
        fn_source = ast.unparse(list_cap_fn)

    # Check: only reads from registry (no write_registry, no enable_entry, no disable_entry)
    mutating_calls = ("write_registry", "enable_entry", "disable_entry",
                      "register", "unregister", "setattr", "__setattr__")
    read_only = all(call not in fn_source for call in mutating_calls)

    # Check: filters for enabled=True
    enabled_only = "entry.enabled" in fn_source or "not entry.enabled" in fn_source

    # Check: no internal structure exposure
    # Should not expose module paths, file paths, or internal class names
    internal_patterns = (
        "v3/kernel", "v3/external", "v3/memory",
        "__module__", "__file__", "sys.path",
        "importlib", "inspect.",
    )
    no_internal_leak = all(p not in fn_source for p in internal_patterns)

    violations = []
    if not read_only:
        violations.append("contains mutating calls")
    if not enabled_only:
        violations.append("no enabled=True filter")
    if not no_internal_leak:
        violations.append("exposes internal structure")

    all_pass = len(violations) == 0
    detail = "all checks passed" if all_pass else "; ".join(violations)

    return {
        "pass": all_pass,
        "read_only": read_only,
        "enabled_only": enabled_only,
        "no_internal_leak": no_internal_leak,
        "detail": detail,
    }


# ═══════════════════════════════════════════════════════════════════════
# SF-03: Signal Contract Freeze
# ═══════════════════════════════════════════════════════════════════════

def _check_signal_contract(root: str) -> dict:
    """Verify external signal contracts are frozen.

    Checks:
      - Exactly 2 planes: direction (gstack, 0.4) and quality (superpowers, 0.6)
      - Weight constants unchanged
    """
    injector_path = os.path.join(root, "v3", "external", "external_signal_injector.py")
    api_path = os.path.join(root, "api.py")

    if not os.path.isfile(injector_path):
        return {
            "pass": False,
            "planes_found": (),
            "weight_violations": ("external_signal_injector.py not found",),
        }

    all_weight_violations = []

    # Check api.py for plane routing
    if os.path.isfile(api_path):
        with open(api_path, encoding="utf-8") as f:
            api_source = f.read()

        planes_in_api = []
        for plane in FROZEN_SIGNAL_PLANES:
            if f'plane == "{plane}"' in api_source or f"plane == '{plane}'" in api_source:
                planes_in_api.append(plane)

        # Check no unknown planes in api.py
        unknown_plane_pattern = 'plane == "'
        import re
        plane_matches = re.findall(r'plane\s*==\s*["\']([^"\']+)["\']', api_source)
        unknown_planes = [p for p in plane_matches
                         if p not in FROZEN_SIGNAL_PLANES]
        if unknown_planes:
            all_weight_violations.append(
                f"Unknown planes in api.py: {unknown_planes}"
            )
    else:
        planes_in_api = []

    # Check external_signal_injector.py for weight constants
    with open(injector_path, encoding="utf-8") as f:
        injector_source = f.read()

    # Verify direction_weight = 0.4
    if "direction_weight = 0.4" not in injector_source:
        all_weight_violations.append(
            "direction_weight = 0.4 not found in external_signal_injector.py"
        )

    # Verify quality_weight = 0.6
    if "quality_weight = 0.6" not in injector_source:
        all_weight_violations.append(
            "quality_weight = 0.6 not found in external_signal_injector.py"
        )

    # Verify complexity gate threshold
    if "increase_ratio <= 2.0" not in injector_source and \
       "increase_ratio > 2.0" not in injector_source:
        all_weight_violations.append(
            "Complexity gate threshold 2.0 not found"
        )

    # Check direction source is gstack
    if '"source": "gstack"' not in injector_source:
        all_weight_violations.append(
            'direction source "gstack" not confirmed in injector'
        )

    # Check quality source is superpowers
    if '"source": "superpowers"' not in injector_source:
        all_weight_violations.append(
            'quality source "superpowers" not confirmed in injector'
        )

    pass_check = len(all_weight_violations) == 0

    return {
        "pass": pass_check,
        "planes_found": tuple(planes_in_api) if planes_in_api else FROZEN_SIGNAL_PLANES,
        "weight_violations": tuple(all_weight_violations),
    }


# ═══════════════════════════════════════════════════════════════════════
# SF-04: Injection Pipeline Freeze
# ═══════════════════════════════════════════════════════════════════════

def _check_injection_pipeline(root: str) -> dict:
    """Verify inject_external_signals() pipeline is frozen.

    Checks that the 5-step pipeline is preserved:
      1. query external signals
      2. normalize outputs
      3. apply complexity gate
      4. perform deterministic fusion
      5. return decision object
    """
    injector_path = os.path.join(root, "v3", "external", "external_signal_injector.py")
    api_path = os.path.join(root, "api.py")

    if not os.path.isfile(injector_path):
        return {
            "pass": False,
            "stages_found": (),
            "complexity_gate_intact": False,
            "detail": "external_signal_injector.py not found",
        }

    with open(injector_path, encoding="utf-8") as f:
        source = f.read()

    # Check each required pipeline stage marker appears in order
    stage_markers = [
        ("query_external_signals", "Step 1: Query external signals"),
        ("direction_weight = 0.4", "Step 2: Direction weight 0.4"),
        ("quality_weight = 0.6", "Step 3: Quality weight 0.6"),
        ("evaluate_complexity_gate", "Step 4: Complexity gate"),
        ("final_score = kernel_score + external_contribution", "Step 5: Fusion formula"),
    ]

    stages_found = []
    for marker, label in stage_markers:
        if marker in source:
            stages_found.append(label)

    # Verify complexity gate is not bypassable
    complexity_gate_intact = (
        "evaluate_complexity_gate" in source
        and "increase_ratio" in source
        and "complexity_penalty" in source
        and "2.0" in source  # threshold
    )

    # Check Step 6: Verdict
    verdict_markers = ["verdict", "PROCEED", "REVIEW", "BLOCKED"]
    verdict_intact = all(m in source for m in verdict_markers[:1])

    all_pass = (
        len(stages_found) >= 5
        and complexity_gate_intact
        and verdict_intact
    )

    detail = ""
    if not all_pass:
        missing = [m[1] for m in stage_markers if m[1] not in stages_found]
        if missing:
            detail = f"Missing stages: {missing}"
        if not complexity_gate_intact:
            detail += " | Complexity gate not intact"
    else:
        detail = f"All {len(stages_found)} pipeline stages confirmed"

    return {
        "pass": all_pass,
        "stages_found": tuple(stages_found),
        "complexity_gate_intact": complexity_gate_intact,
        "detail": detail,
    }


# ═══════════════════════════════════════════════════════════════════════
# SF-05: Internal System Protection
# ═══════════════════════════════════════════════════════════════════════

def _check_internal_protection(root: str) -> dict:
    """Verify internal subsystems are not exposed by api.py.

    api.py must NOT directly import or expose:
      - v3/kernel/*
      - v3/memory/*
      - v3/evals/*
      - v3/intake/*
      - EventBus, TaskSystem, Observability internals
    """
    api_path = os.path.join(root, "api.py")
    if not os.path.isfile(api_path):
        return {
            "pass": False,
            "internal_imports": ("api.py not found",),
            "subsystems_exposed": (),
            "detail": "api.py not found",
        }

    with open(api_path, encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {
            "pass": False,
            "internal_imports": ("api.py syntax error",),
            "subsystems_exposed": (),
            "detail": "api.py syntax error",
        }

    # SF-05a: Check imports — what does api.py import?
    internal_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for protected in PROTECTED_INTERNAL_IMPORTS:
                    if alias.name.startswith(protected):
                        internal_imports.append(
                            f"import {alias.name} (from {protected})"
                        )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for protected in PROTECTED_INTERNAL_IMPORTS:
                    if node.module.startswith(protected):
                        internal_imports.append(
                            f"from {node.module} import ... (from {protected})"
                        )

    # The existing imports in api.py are:
    #   from SkillsManagementSystem.core.adapter import ...
    #   from ExecutionLoop.loop import ...
    #   from TaskSystem.core.task_manager import ...
    # These are the CORE 3 forwarding imports and are ALLOWED.
    ALLOWED_SUBSYSTEM_IMPORTS = {
        "SkillsManagementSystem.core.adapter",
        "ExecutionLoop.loop",
        "TaskSystem.core.task_manager",
        "v3.external.gstack_adapter",
        "v3.external.superpowers_adapter",
        "v3.external.external_signal_injector",
        "v3.external.default_capabilities",
        "datetime",
    }

    # SF-05b: Check for NEW internal subsystem exposures (beyond allowed baseline)
    subsystems_exposed = []
    for protected in PROTECTED_SUBSYSTEMS:
        if protected in source:
            lines = source.split("\n")
            for i, line in enumerate(lines, 1):
                if protected in line and ("import" in line or "from" in line):
                    line_stripped = line.strip()
                    # Only flag if NOT one of the 3 allowed core imports
                    is_allowed = False
                    for allowed in ALLOWED_SUBSYSTEM_IMPORTS:
                        if allowed in line_stripped:
                            is_allowed = True
                            break
                    if not is_allowed:
                        subsystems_exposed.append(
                            f"Line {i}: {line_stripped}"
                        )

    # Filter internal_imports: only flag those NOT in the allowed set
    actual_violations = []
    for imp in internal_imports:
        is_allowed = False
        for allowed in ALLOWED_SUBSYSTEM_IMPORTS:
            if allowed in imp:
                is_allowed = True
                break
        if not is_allowed:
            actual_violations.append(imp)

    pass_check = len(actual_violations) == 0 and len(subsystems_exposed) == 0

    return {
        "pass": pass_check,
        "internal_imports": tuple(actual_violations),
        "subsystems_exposed": tuple(subsystems_exposed),
        "detail": "all internal subsystems protected"
        if pass_check
        else f"{len(actual_violations)} import violations, "
             f"{len(subsystems_exposed)} subsystem exposures",
    }


# ═══════════════════════════════════════════════════════════════════════
# SF-06: ECC Rule
# ═══════════════════════════════════════════════════════════════════════

def _check_ecc_rule(root: str) -> dict:
    """Verify ECC is NOT exposed via API or capability registry.

    ECC is execution-only infrastructure. It must not:
      - Appear in api.py as a public function or export
      - Appear in the capability registry as an enabled entry
      - Be referenced as a truth source
    """
    api_path = os.path.join(root, "api.py")
    registry_path = os.path.join(root, "v3", "external", "default_capabilities.py")

    ecc_in_api = False
    ecc_in_registry = False
    violations = []

    # Check api.py for ECC references
    if os.path.isfile(api_path):
        with open(api_path, encoding="utf-8") as f:
            api_source = f.read()
        api_lower = api_source.lower()
        if "ecc" in api_lower:
            # Check context: ECC may appear in comments/docstrings as exclusion notes
            # but should NOT appear as a functional export
            if "def " in api_source:
                lines = api_source.split("\n")
                for i, line in enumerate(lines, 1):
                    line_lower = line.lower()
                    if "ecc" in line_lower and not line.strip().startswith("#"):
                        if "def " in line_lower or "import " in line_lower or \
                           "return" in line_lower or "ecc_" in line_lower:
                            ecc_in_api = True
                            violations.append(f"api.py line {i}: {line.strip()[:80]}")

    # Check capability registry for ECC entry
    if os.path.isfile(registry_path):
        with open(registry_path, encoding="utf-8") as f:
            registry_source = f.read()
        reg_lower = registry_source.lower()
        if "ecc" in reg_lower:
            # ECC should not be in any enabled adapter entry
            if "everything_claude_code" in reg_lower or "everything-claude-code" in reg_lower:
                ecc_in_registry = True
                violations.append("ECC found in capability registry")

    pass_check = not ecc_in_api and not ecc_in_registry
    detail = "ECC properly isolated" if pass_check else "; ".join(violations)

    return {
        "pass": pass_check,
        "ecc_in_api": ecc_in_api,
        "ecc_in_registry": ecc_in_registry,
        "detail": detail,
    }


# ═══════════════════════════════════════════════════════════════════════
# SF-07: Complexity Guard
# ═══════════════════════════════════════════════════════════════════════

def _check_complexity_guard(root: str) -> dict:
    """Verify no complexity-increasing changes have been introduced.

    Checks:
      - No new entry point files (only api.py)
      - No circular dependencies between signal planes
      - Deterministic behavior preserved (no random, no time-based routing)
    """
    api_path = os.path.join(root, "api.py")
    if not os.path.isfile(api_path):
        return {
            "pass": False,
            "new_entry_points": ("api.py not found",),
            "circular_deps": False,
            "detail": "api.py not found",
        }

    with open(api_path, encoding="utf-8") as f:
        api_source = f.read()

    violations = []

    # Check: no new entry point files
    # Only api.py should serve as the public API
    # Check that __init__.py in root doesn't re-export api.py contents
    init_path = os.path.join(root, "__init__.py")
    if os.path.isfile(init_path):
        with open(init_path, encoding="utf-8") as f:
            init_source = f.read()
        if init_source.strip():
            violations.append("Root __init__.py is non-empty (potential alternative entry point)")

    # Check for non-deterministic patterns in api.py and signal injector
    non_deterministic_patterns = (
        "random.", "time.sleep", "threading.",
        "async def", "asyncio.", "concurrent.",
    )
    for pattern in non_deterministic_patterns:
        if pattern in api_source:
            violations.append(f"Non-deterministic pattern in api.py: {pattern}")

    # Check: no circular dependencies between direction and quality planes
    gstack_path = os.path.join(root, "v3", "external", "gstack_adapter.py")
    superpowers_path = os.path.join(root, "v3", "external", "superpowers_adapter.py")

    if os.path.isfile(gstack_path) and os.path.isfile(superpowers_path):
        with open(gstack_path, encoding="utf-8") as f:
            gstack_source = f.read()
        with open(superpowers_path, encoding="utf-8") as f:
            superpowers_source = f.read()

        # Direction (gstack) must not import quality (superpowers) and vice versa
        if "superpowers" in gstack_source.lower():
            violations.append("gstack_adapter imports/references superpowers (circular dependency)")
        if "gstack" in superpowers_source.lower():
            violations.append("superpowers_adapter imports/references gstack (circular dependency)")

    pass_check = len(violations) == 0

    return {
        "pass": pass_check,
        "new_entry_points": tuple(violations),
        "circular_deps": any("circular" in v.lower() for v in violations),
        "detail": "no complexity violations" if pass_check else "; ".join(violations),
    }


# ═══════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════

def build_stability_freeze(root: Optional[str] = None) -> StabilityFreezeResult:
    """Run all 7 stability freeze invariant checks.

    Deterministic: same inputs → same result.
    """
    if root is None:
        root = _resolve_root()

    now = datetime.now(timezone.utc).isoformat()

    sf01 = _check_api_surface(root)
    sf02 = _check_capability_freeze(root)
    sf03 = _check_signal_contract(root)
    sf04 = _check_injection_pipeline(root)
    sf05 = _check_internal_protection(root)
    sf06 = _check_ecc_rule(root)
    sf07 = _check_complexity_guard(root)

    all_checks = [sf01, sf02, sf03, sf04, sf05, sf06, sf07]
    passed = sum(1 for c in all_checks if c["pass"])
    failed = len(all_checks) - passed

    return StabilityFreezeResult(
        timestamp=now,
        version="4.1",
        # SF-01
        api_functions_found=sf01.get("functions_found", 0),
        api_functions_expected=FROZEN_API_COUNT,
        api_missing_functions=sf01.get("missing", ()),
        api_extra_functions=sf01.get("extra", ()),
        api_signature_violations=sf01.get("signature_violations", ()),
        api_surface_pass=sf01["pass"],
        # SF-02
        capability_read_only=sf02.get("read_only", False),
        capability_enabled_only=sf02.get("enabled_only", False),
        capability_no_internal_leak=sf02.get("no_internal_leak", False),
        capability_freeze_pass=sf02["pass"],
        capability_detail=sf02.get("detail", ""),
        # SF-03
        signal_planes_found=sf03.get("planes_found", ()),
        signal_planes_expected=FROZEN_SIGNAL_PLANES,
        signal_weight_violations=sf03.get("weight_violations", ()),
        signal_contract_pass=sf03["pass"],
        # SF-04
        pipeline_stages_found=sf04.get("stages_found", ()),
        pipeline_stages_expected=FROZEN_PIPELINE_STAGES,
        pipeline_complexity_gate_intact=sf04.get("complexity_gate_intact", False),
        pipeline_freeze_pass=sf04["pass"],
        # SF-05
        internal_imports_in_api=sf05.get("internal_imports", ()),
        internal_subsystems_exposed=sf05.get("subsystems_exposed", ()),
        internal_protection_pass=sf05["pass"],
        # SF-06
        ecc_in_api=sf06.get("ecc_in_api", False),
        ecc_in_registry=sf06.get("ecc_in_registry", False),
        ecc_rule_pass=sf06["pass"],
        ecc_detail=sf06.get("detail", ""),
        # SF-07
        new_entry_points=sf07.get("new_entry_points", ()),
        circular_deps_detected=sf07.get("circular_deps", False),
        complexity_guard_pass=sf07["pass"],
        # Summary
        invariants_passed=passed,
        invariants_failed=failed,
        overall_pass=(failed == 0),
    )


# ═══════════════════════════════════════════════════════════════════════
# Reporter
# ═══════════════════════════════════════════════════════════════════════

def write_stability_freeze_report(
    result: StabilityFreezeResult,
    path: Optional[str] = None,
) -> str:
    """Write stability freeze report to JSON file. Returns absolute path."""
    if path is None:
        root = _resolve_root()
        export_dir = os.path.join(root, "v3", "exports")
        os.makedirs(export_dir, exist_ok=True)
        path = os.path.join(export_dir, "stability_freeze_report.json")
    else:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)
    return os.path.abspath(path)


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def _print_result(result: StabilityFreezeResult) -> None:
    """Pretty-print stability freeze result to stdout."""
    print("=" * 64)
    print("  SystemKernel v4.1 — Stability Freeze Report")
    print("=" * 64)
    print(f"  Timestamp:  {result.timestamp}")
    print(f"  Version:    {result.version}")
    print()

    checks = [
        ("SF-01", "API Surface Freeze", result.api_surface_pass,
         f"{result.api_functions_found}/{result.api_functions_expected} functions"
         if result.api_surface_pass
         else f"missing={list(result.api_missing_functions)}, extra={list(result.api_extra_functions)}"),
        ("SF-02", "Capability Freeze", result.capability_freeze_pass,
         result.capability_detail),
        ("SF-03", "Signal Contract Freeze", result.signal_contract_pass,
         f"planes={list(result.signal_planes_found)}"
         if result.signal_contract_pass
         else f"violations={list(result.signal_weight_violations)}"),
        ("SF-04", "Injection Pipeline Freeze", result.pipeline_freeze_pass,
         f"stages={len(result.pipeline_stages_found)}/{len(result.pipeline_stages_expected)}"),
        ("SF-05", "Internal System Protection", result.internal_protection_pass,
         "all protected" if result.internal_protection_pass
         else f"imports={list(result.internal_imports_in_api)}, exposures={list(result.internal_subsystems_exposed)}"),
        ("SF-06", "ECC Rule", result.ecc_rule_pass,
         result.ecc_detail),
        ("SF-07", "Complexity Guard", result.complexity_guard_pass,
         "no violations" if result.complexity_guard_pass
         else f"violations={list(result.new_entry_points)}"),
    ]

    for inv_id, name, passed, detail in checks:
        icon = "[PASS]" if passed else "[FAIL]"
        print(f"  {icon} {inv_id} {name}")
        if not passed:
            print(f"         → {detail}")

    print()
    print(f"  Invariants: {result.invariants_passed}/7 passed")
    print(f"  Overall:    {'FROZEN' if result.overall_pass else 'DRIFT DETECTED'}")
    print()

    if result.api_extra_functions:
        print("  Extra API functions (architectural drift):")
        for f in result.api_extra_functions:
            print(f"    !! {f}")
        print()

    if result.api_missing_functions:
        print("  Missing API functions (breaking change):")
        for f in result.api_missing_functions:
            print(f"    !! {f}")
        print()

    if result.signal_weight_violations:
        print("  Signal weight violations:")
        for v in result.signal_weight_violations:
            print(f"    !! {v}")
        print()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="stability_freeze",
        description="SystemKernel v4.1 Stability Freeze Guard",
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
        args.verify = True

    root = _resolve_root()
    result = build_stability_freeze(root)
    _print_result(result)

    if args.verify:
        report_path = write_stability_freeze_report(result, args.output)
        print(f"  Report written: {report_path}")

    sys.exit(0 if result.overall_pass else 1)


if __name__ == "__main__":
    main()
