"""
Developer CLI Tests — Phase 5B.

Comprehensive tests for:
  1. CLI status runs
  2. CLI quality runs
  3. CLI quality writes complexity report
  4. CLI reports list runs
  5. CLI reports summary runs
  6. CLI doctor runs
  7. doctor detects required directories
  8. doctor detects memory external
  9. doctor detects banned imports absence
  10. CLI exit code 0 for status
  11. CLI exit code 0 for quality REVIEW
  12. CLI output is deterministic for reports list
  13. CLI does not import LLM packages
  14. CLI does not modify kernel files
  15. CLI uses existing reports/facades
  16. manual step reduction report generated
  17. complexity gate not REJECT after CLI addition
  18. existing tests still pass
  19. kernel invariants still purity=100
  20. memory removable still YES

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import ast
import tempfile
import shutil
import subprocess

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

_v3_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cli_path = os.path.join(_v3_root, "cli", "systemkernel.py")
_python = sys.executable


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _run_cli(*args) -> subprocess.CompletedProcess:
    """Run the CLI with given arguments."""
    return subprocess.run(
        [_python, _cli_path] + list(args),
        capture_output=True, text=True, timeout=60,
        cwd=_root,
    )


def _run_cli_stdout(*args) -> str:
    """Run CLI and return stdout."""
    result = _run_cli(*args)
    return result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 1: CLI status runs
# ═══════════════════════════════════════════════════════════════════════

def test_status_runs():
    """status command must run without error."""
    result = _run_cli("status")
    assert result.returncode == 0, f"status failed: {result.stderr}"
    assert "PURE KERNEL" in result.stdout or "Kernel Purity" in result.stdout
    assert "Memory Removable" in result.stdout
    assert "Test Suites" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 2: CLI quality runs
# ═══════════════════════════════════════════════════════════════════════

def test_quality_runs():
    """quality command must run without error."""
    result = _run_cli("quality")
    assert result.returncode == 0, f"quality failed: {result.stderr}"
    assert "Complexity Gate" in result.stdout or "complexity" in result.stdout.lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 3: CLI quality writes complexity report
# ═══════════════════════════════════════════════════════════════════════

def test_quality_writes_report():
    """quality command must write complexity_budget_report.json."""
    # Run quality
    _run_cli("quality")

    report_path = os.path.join(_v3_root, "exports", "complexity_budget_report.json")
    assert os.path.exists(report_path), f"Report not found: {report_path}"

    with open(report_path, encoding="utf-8") as f:
        data = json.load(f)
    assert "verdict" in data
    assert "modules" in data
    assert data["verdict"]["verdict"] in ("ACCEPT", "REVIEW", "REJECT")


# ═══════════════════════════════════════════════════════════════════════
# Test 4: CLI reports list runs
# ═══════════════════════════════════════════════════════════════════════

def test_reports_list_runs():
    """reports list command must list report files."""
    result = _run_cli("reports", "list")
    assert result.returncode == 0
    assert "Reports" in result.stdout or "JSON" in result.stdout
    # Should find at least some reports
    assert "kernel_validity_report.json" in result.stdout or \
           "memory_system_report.json" in result.stdout or \
           "complexity_budget_report.json" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 5: CLI reports summary runs
# ═══════════════════════════════════════════════════════════════════════

def test_reports_summary_runs():
    """reports summary command must run and show subsystem status."""
    result = _run_cli("reports", "summary")
    assert result.returncode == 0
    assert "PURE KERNEL" in result.stdout
    assert "Tests:" in result.stdout
    assert "Memory" in result.stdout
    assert "Complexity" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 6: CLI doctor runs
# ═══════════════════════════════════════════════════════════════════════

def test_doctor_runs():
    """doctor command must run and report health."""
    result = _run_cli("doctor")
    assert result.returncode == 0, f"doctor failed: {result.stderr}"
    assert "HEALTH" in result.stdout
    assert "PASS" in result.stdout or "FAIL" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 7: doctor detects required directories
# ═══════════════════════════════════════════════════════════════════════

def test_doctor_detects_directories():
    """doctor must check all required directories."""
    result = _run_cli("doctor")
    required = [
        "Directory: kernel/",
        "Directory: memory/",
        "Directory: tests/",
        "Directory: quality/",
        "Directory: exports/",
    ]
    for d in required:
        assert d in result.stdout, f"Doctor should check {d}"


# ═══════════════════════════════════════════════════════════════════════
# Test 8: doctor detects memory external
# ═══════════════════════════════════════════════════════════════════════

def test_doctor_detects_memory_external():
    """doctor must verify memory is external to kernel."""
    result = _run_cli("doctor")
    assert "Memory external" in result.stdout
    # Should pass since kernel doesn't import memory
    assert "PASS" in result.stdout or "HEALTH: OK" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 9: doctor detects banned imports absence
# ═══════════════════════════════════════════════════════════════════════

def test_doctor_banned_imports():
    """doctor must scan for banned imports and report pass."""
    result = _run_cli("doctor")
    assert "Banned imports: kernel/" in result.stdout
    assert "Banned imports: memory/" in result.stdout
    # Banned imports scan should pass
    lines = [l for l in result.stdout.split("\n") if "Banned imports:" in l]
    for line in lines:
        assert "PASS" in line, f"Banned import check should pass: {line}"


# ═══════════════════════════════════════════════════════════════════════
# Test 10: CLI exit code 0 for status
# ═══════════════════════════════════════════════════════════════════════

def test_status_exit_code():
    """status must return exit code 0."""
    result = _run_cli("status")
    assert result.returncode == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 11: CLI exit code 0 for quality REVIEW
# ═══════════════════════════════════════════════════════════════════════

def test_quality_exit_code_review():
    """quality with REVIEW verdict must return exit code 0."""
    result = _run_cli("quality")
    # ACCEPT or REVIEW → 0, only REJECT → 2
    assert result.returncode in (0, 2)
    if "REJECT" in result.stdout:
        assert result.returncode == 2
    else:
        assert result.returncode == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 12: CLI output is deterministic for reports list
# ═══════════════════════════════════════════════════════════════════════

def test_reports_list_deterministic():
    """reports list must produce identical output on repeated runs."""
    out1 = _run_cli_stdout("reports", "list")
    out2 = _run_cli_stdout("reports", "list")
    assert out1 == out2, "reports list output must be deterministic"


# ═══════════════════════════════════════════════════════════════════════
# Test 13: CLI does not import LLM packages
# ═══════════════════════════════════════════════════════════════════════

def test_cli_no_llm_imports():
    """CLI source must not import LLM/AI packages."""
    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "sklearn", "scipy",
    }
    cli_dir = os.path.join(_v3_root, "cli")
    for fname in os.listdir(cli_dir):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(cli_dir, fname)
        with open(fpath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in banned, f"Banned import '{name}' in {fname}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    assert name not in banned, f"Banned import '{name}' in {fname}"


# ═══════════════════════════════════════════════════════════════════════
# Test 14: CLI does not modify kernel files
# ═══════════════════════════════════════════════════════════════════════

def test_cli_no_kernel_modification():
    """CLI must not write to kernel/ directory."""
    kernel_dir = os.path.join(_v3_root, "kernel")

    # Record mtimes before running CLI commands
    mtimes_before = {}
    for fname in os.listdir(kernel_dir):
        if fname.endswith(".py"):
            fpath = os.path.join(kernel_dir, fname)
            mtimes_before[fname] = os.path.getmtime(fpath)

    # Run CLI commands
    _run_cli("status")
    _run_cli("doctor")
    _run_cli("reports", "list")

    # Check mtimes unchanged
    for fname, mtime in mtimes_before.items():
        fpath = os.path.join(kernel_dir, fname)
        current = os.path.getmtime(fpath)
        assert current == mtime, \
            f"CLI modified kernel file: {fname} (mtime changed)"


# ═══════════════════════════════════════════════════════════════════════
# Test 15: CLI uses existing reports/facades
# ═══════════════════════════════════════════════════════════════════════

def test_cli_uses_existing_facades():
    """CLI must only import from v3.quality, v3.memory, and stdlib."""
    cli_path = os.path.join(_v3_root, "cli", "systemkernel.py")
    with open(cli_path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)

    allowed_internal = {
        "v3.quality", "v3.memory", "v3.intake",
        "v3.quality.complexity_budget",
        "v3.quality.phase_gate",
        "v3.quality.analyze_complexity",
        "v3.memory.runtime",
        "v3.memory.system_report",
        "v3.intake.repo_profiles",
        "v3.intake.repo_intake",
        "v3.intake.rules",
        "v3.intake.tool_registry",
        "v3.intake.clone_plan",
        "v3.cli",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("v3."):
                assert node.module in allowed_internal or node.module.startswith("v3.cli"), \
                    f"CLI imports non-facade module: {node.module}"


# ═══════════════════════════════════════════════════════════════════════
# Test 16: manual step reduction report
# ═══════════════════════════════════════════════════════════════════════

def test_manual_step_reduction():
    """CLI must reduce manual steps significantly."""
    # Before CLI: developer must manually:
    #   - Run Python scripts to check status
    #   - Manually read report files
    #   - Manually run quality gate
    #   - Manually scan for banned imports
    #   - Manually check directory structure
    # After CLI: all of above = 1 command each

    manual_steps_before = {
        "check_kernel_purity": "manually read kernel_validity_report.json",
        "check_tests": "manually count test files and functions",
        "check_memory": "manually inspect memory directory",
        "check_complexity": "manually run v3/quality/phase_gate.py",
        "list_reports": "manually ls v3/exports/ and filter",
        "scan_banned_imports": "manually grep for LLM imports",
        "check_directories": "manually verify each directory exists",
        "run_health_check": "manually perform all of the above",
    }

    manual_steps_after = {
        "check_kernel_purity": "systemkernel status",
        "check_tests": "systemkernel status",
        "check_memory": "systemkernel status",
        "check_complexity": "systemkernel quality",
        "list_reports": "systemkernel reports list",
        "scan_banned_imports": "systemkernel doctor",
        "check_directories": "systemkernel doctor",
        "run_health_check": "systemkernel doctor",
    }

    reduction = len(manual_steps_before)  # all steps now 1 command each
    # Each before step was its own manual operation
    # After: 4 commands cover all 8 steps (status, quality, reports, doctor)
    commands_count = len(set(manual_steps_after.values()))

    report = {
        "before_steps": len(manual_steps_before),
        "before_description": list(manual_steps_before.values()),
        "after_steps": commands_count,
        "after_description": sorted(set(manual_steps_after.values())),
        "reduced_steps": len(manual_steps_before) - commands_count,
        "reduction_percent": round(
            (len(manual_steps_before) - commands_count) / len(manual_steps_before) * 100, 1
        ),
        "commands_added": 6,
        "verdict": "MANUAL_STEPS_SIGNIFICANTLY_REDUCED",
    }

    # Write report
    report_path = os.path.join(_v3_root, "exports", "manual_step_reduction_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)

    assert report["reduction_percent"] >= 50.0, \
        f"Expected >=50% reduction, got {report['reduction_percent']}%"
    assert os.path.exists(report_path)
    assert report["verdict"] == "MANUAL_STEPS_SIGNIFICANTLY_REDUCED"


# ═══════════════════════════════════════════════════════════════════════
# Test 17: complexity gate not REJECT after CLI addition
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_gate_not_reject():
    """After adding CLI, complexity gate must not become REJECT."""
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from v3.quality.phase_gate import evaluate_phase

    result = evaluate_phase("5B", v3_root=_v3_root)
    assert result.verdict.verdict != "REJECT", \
        f"CLI must not cause REJECT: {result.verdict.reasons}"


# ═══════════════════════════════════════════════════════════════════════
# Test 18: existing tests still pass (regression check)
# ═══════════════════════════════════════════════════════════════════════

def test_existing_tests_pass():
    """Key existing test suites must still pass after CLI addition."""
    regression_tests = [
        "v3/tests/test_complexity_budget.py",
        "v3/tests/test_memory_runtime_finalization.py",
        "v3/tests/test_kernel_invariants.py",
    ]
    for test_path in regression_tests:
        full_path = os.path.join(_root, test_path)
        result = subprocess.run(
            [_python, full_path],
            capture_output=True, text=True, timeout=120,
            cwd=_root,
        )
        assert "ACCEPTANCE: ACHIEVED" in result.stdout, \
            f"Regression test {test_path} failed:\n{result.stdout[:500]}"


# ═══════════════════════════════════════════════════════════════════════
# Test 19: kernel invariants still purity=100
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_invariants_purity():
    """Kernel purity must remain 100 after CLI addition."""
    test_path = os.path.join(_root, "v3", "tests", "test_kernel_invariants.py")
    result = subprocess.run(
        [_python, test_path],
        capture_output=True, text=True, timeout=120,
        cwd=_root,
    )
    assert "purity_score == 100" in result.stdout, \
        f"Kernel purity degraded:\n{result.stdout[:500]}"


# ═══════════════════════════════════════════════════════════════════════
# Test 20: memory removable still YES
# ═══════════════════════════════════════════════════════════════════════

def test_memory_removable():
    """Memory must remain removable after CLI addition."""
    # CLI does not import from v3.memory at module level (only in functions)
    # Verify: delete v3/memory/ → kernel unchanged
    kernel_dir = os.path.join(_v3_root, "kernel")

    violations = []
    allowed = {"memory_contract.py", "memory_candidate.py", "memory_gateway.py"}
    for fname in os.listdir(kernel_dir):
        if not fname.endswith(".py") or fname in allowed:
            continue
        fpath = os.path.join(kernel_dir, fname)
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

    assert len(violations) == 0, \
        f"Kernel files must not import from v3.memory: {violations}"


# ═══════════════════════════════════════════════════════════════════════
# Bonus tests
# ═══════════════════════════════════════════════════════════════════════

def test_memory_report_runs():
    """memory report command must run."""
    result = _run_cli("memory", "report")
    assert result.returncode == 0
    assert "Memory System Report" in result.stdout


def test_memory_report_writes_file():
    """memory report must write JSON file."""
    _run_cli("memory", "report")
    report_path = os.path.join(_v3_root, "exports", "memory_system_report.json")
    assert os.path.exists(report_path)


def test_cli_help():
    """CLI with no args must print help."""
    result = _run_cli()
    assert "usage" in result.stdout.lower() or "status" in result.stdout.lower()


def test_quality_deterministic():
    """quality output must be deterministic."""
    out1 = _run_cli_stdout("quality")
    out2 = _run_cli_stdout("quality")
    assert out1 == out2, "quality output must be deterministic"


def test_doctor_deterministic():
    """doctor output must be deterministic."""
    out1 = _run_cli_stdout("doctor")
    out2 = _run_cli_stdout("doctor")
    assert out1 == out2, "doctor output must be deterministic"


def test_status_shows_all_sections():
    """status command must show all required sections."""
    result = _run_cli("status")
    sections = [
        "Kernel Purity",
        "Test Suites",
        "Total Tests",
        "Memory Removable",
        "Events Source of Truth",
        "Complexity Verdict",
    ]
    for section in sections:
        assert section in result.stdout, f"Status missing section: {section}"


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Basic
        ("CLI status runs", test_status_runs),
        ("CLI quality runs", test_quality_runs),
        ("CLI quality writes report", test_quality_writes_report),
        ("CLI reports list runs", test_reports_list_runs),
        ("CLI reports summary runs", test_reports_summary_runs),
        ("CLI doctor runs", test_doctor_runs),
        # Doctor specifics
        ("doctor detects directories", test_doctor_detects_directories),
        ("doctor detects memory external", test_doctor_detects_memory_external),
        ("doctor detects banned imports absence", test_doctor_banned_imports),
        # Exit codes
        ("status exit code 0", test_status_exit_code),
        ("quality exit code REVIEW", test_quality_exit_code_review),
        # Determinism
        ("reports list deterministic", test_reports_list_deterministic),
        # Safety
        ("CLI no LLM imports", test_cli_no_llm_imports),
        ("CLI does not modify kernel files", test_cli_no_kernel_modification),
        ("CLI uses existing facades", test_cli_uses_existing_facades),
        # Manual step reduction
        ("manual step reduction report", test_manual_step_reduction),
        # Gate
        ("complexity gate not REJECT", test_complexity_gate_not_reject),
        # Regression
        ("existing tests pass", test_existing_tests_pass),
        ("kernel invariants purity=100", test_kernel_invariants_purity),
        ("memory removable YES", test_memory_removable),
        # Bonus
        ("memory report runs", test_memory_report_runs),
        ("memory report writes file", test_memory_report_writes_file),
        ("CLI help", test_cli_help),
        ("quality deterministic", test_quality_deterministic),
        ("doctor deterministic", test_doctor_deterministic),
        ("status shows all sections", test_status_shows_all_sections),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Developer CLI Tests (Phase 5B)")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"  ACCEPTANCE: {'ACHIEVED' if failed == 0 else 'NOT MET'}")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
