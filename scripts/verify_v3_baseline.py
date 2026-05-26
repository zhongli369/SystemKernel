"""
verify_v3_baseline.py — Single-script verification of SystemKernel v3.0 baseline.

Runs safe verification commands (no network, no clone, no install) and
prints a concise PASS/FAIL table. Returns nonzero on any failure.

Usage:
    python scripts/verify_v3_baseline.py

Requirements:
    Python 3.10+ standard library only. No additional package installation needed.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V3_ROOT = os.path.join(ROOT, "v3")


def _python() -> str:
    return sys.executable


def run_cmd(command: str, timeout: int = 120) -> tuple:
    """Run a command and return (returncode, stdout, stderr, duration_ms)."""
    start = time.time()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=ROOT,
        )
        duration_ms = int((time.time() - start) * 1000)
        return result.returncode, result.stdout, result.stderr, duration_ms
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start) * 1000)
        return -1, "", f"TIMEOUT after {timeout}s", duration_ms
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        return -1, "", str(e), duration_ms


def check_file_exists(relpath: str) -> tuple:
    """Check if a file exists."""
    fpath = os.path.join(ROOT, relpath)
    return os.path.exists(fpath), fpath


def check_export_json(relpath: str) -> tuple:
    """Check if an export JSON file exists and is valid JSON."""
    fpath = os.path.join(ROOT, relpath)
    if not os.path.exists(fpath):
        return False, f"{relpath}: not found"
    try:
        with open(fpath, encoding="utf-8") as f:
            json.load(f)
        return True, f"{relpath}: valid JSON"
    except (json.JSONDecodeError, OSError) as e:
        return False, f"{relpath}: {e}"


def main() -> int:
    print("=" * 64)
    print("  SystemKernel v3.0 — Baseline Verification")
    print("=" * 64)
    print()
    print(f"  Root:     {ROOT}")
    print(f"  Python:   {_python()}")
    print()

    results = []

    # ── Static file checks ──
    static_checks = [
        ("v3/main.py", "Main entry point"),
        ("v3/kernel/execution_engine.py", "Kernel: execution engine"),
        ("v3/kernel/events.py", "Kernel: events"),
        ("v3/kernel/checkpoint.py", "Kernel: checkpoint"),
        ("v3/kernel/observability.py", "Kernel: observability"),
        ("v3/kernel/invariants.py", "Kernel: invariants"),
        ("v3/memory/runtime.py", "Memory: runtime"),
        ("v3/memory/episodic_store.py", "Memory: episodic store"),
        ("v3/memory/semantic_index.py", "Memory: semantic index"),
        ("v3/memory/compaction.py", "Memory: compaction"),
        ("v3/quality/phase_gate.py", "Quality: phase gate"),
        ("v3/cli/systemkernel.py", "CLI: entry point"),
        ("v3/release/inventory.py", "Release: inventory"),
        ("v3/release/release_notes.py", "Release: release notes"),
        ("v3/release/validation_matrix.py", "Release: validation matrix"),
        ("v3/release/package_manifest.py", "Release: package manifest"),
        ("v3/release/handoff.py", "Release: handoff"),
        ("examples/golden_path/run_golden_path.py", "Golden path runner"),
        ("docs/OPERATIONS.md", "Operations documentation"),
        ("scripts/verify_v3_baseline.py", "Verification script (self)"),
    ]

    print("  ── Static File Checks ──")
    for relpath, desc in static_checks:
        ok, detail = check_file_exists(relpath)
        status = "PASS" if ok else "FAIL"
        results.append((f"File: {desc}", status, detail if not ok else relpath))
        print(f"    [{status}] {desc}")

    # ── Export JSON checks ──
    export_checks = [
        ("v3/exports/kernel_validity_report.json", "Kernel validity report"),
        ("v3/exports/memory_system_report.json", "Memory system report"),
        ("v3/exports/complexity_budget_report.json", "Complexity budget report"),
        ("v3/exports/release_inventory.json", "Release inventory"),
        ("v3/exports/release_validation_matrix.json", "Release validation matrix"),
        ("v3/exports/systemkernel_v3_release_notes.md", "Release notes"),
    ]

    print()
    print("  ── Export File Checks ──")
    for relpath, desc in export_checks:
        if relpath.endswith(".json"):
            ok, detail = check_export_json(relpath)
        else:
            ok = os.path.exists(os.path.join(ROOT, relpath))
            detail = relpath if ok else f"{relpath}: not found"
        status = "PASS" if ok else "FAIL"
        results.append((f"Export: {desc}", status, detail))
        print(f"    [{status}] {desc}")

    # ── Command execution checks ──
    commands = [
        ("Test: Kernel Invariants",
         f'"{_python()}" v3/tests/test_kernel_invariants.py',
         180),
        ("Test: Release Freeze",
         f'"{_python()}" v3/tests/test_release_freeze.py',
         180),
        ("CLI: Doctor",
         f'"{_python()}" v3/cli/systemkernel.py doctor',
         120),
        ("CLI: Reports Summary",
         f'"{_python()}" v3/cli/systemkernel.py reports summary',
         60),
        ("Golden Path",
         f'"{_python()}" examples/golden_path/run_golden_path.py',
         120),
    ]

    print()
    print("  ── Command Execution Checks ──")
    for name, cmd, timeout in commands:
        print(f"    Running: {name}...", end=" ", flush=True)
        rc, stdout, stderr, duration_ms = run_cmd(cmd, timeout=timeout)
        passed = rc == 0
        status = "PASS" if passed else "FAIL"
        detail = f"{duration_ms}ms"
        if not passed:
            # Extract last meaningful error line
            err_lines = [l for l in (stderr + stdout).split("\n") if l.strip()]
            detail = err_lines[-1][:100] if err_lines else f"exit={rc}"
        results.append((name, status, detail))
        print(f"[{status}] ({duration_ms}ms)")

    # ── Purity + Removability from reports ──
    print()
    print("  ── Invariant Checks ──")

    # Kernel purity
    kernel_path = os.path.join(ROOT, "v3", "exports", "kernel_validity_report.json")
    try:
        with open(kernel_path, encoding="utf-8") as f:
            kernel_data = json.load(f)
        purity = kernel_data.get("purity_score", 0)
        purity_ok = purity == 100
        results.append(("Kernel Purity 100/100", "PASS" if purity_ok else "FAIL",
                       f"purity_score={purity}"))
        print(f"    [{'PASS' if purity_ok else 'FAIL'}] Kernel Purity: {purity}/100")
    except Exception as e:
        results.append(("Kernel Purity 100/100", "FAIL", str(e)))
        print(f"    [FAIL] Kernel Purity: error reading report")

    # Memory removable
    mem_path = os.path.join(ROOT, "v3", "exports", "memory_system_report.json")
    try:
        with open(mem_path, encoding="utf-8") as f:
            mem_data = json.load(f)
        removable = mem_data.get("verdicts", {}).get("removability", "NO")
        removable_ok = removable == "YES"
        results.append(("Memory Removable", "PASS" if removable_ok else "FAIL",
                       f"removability={removable}"))
        print(f"    [{'PASS' if removable_ok else 'FAIL'}] Memory Removable: {removable}")
    except Exception as e:
        results.append(("Memory Removable", "FAIL", str(e)))
        print(f"    [FAIL] Memory Removable: error reading report")

    # Complexity gate
    cb_path = os.path.join(ROOT, "v3", "exports", "complexity_budget_report.json")
    try:
        with open(cb_path, encoding="utf-8") as f:
            cb_data = json.load(f)
        verdict = cb_data.get("verdict", {}).get("verdict", "UNKNOWN")
        cb_ok = verdict != "REJECT"
        results.append(("Complexity Gate Not REJECT", "PASS" if cb_ok else "FAIL",
                       f"verdict={verdict}"))
        print(f"    [{'PASS' if cb_ok else 'FAIL'}] Complexity Gate: {verdict}")
    except Exception as e:
        results.append(("Complexity Gate Not REJECT", "FAIL", str(e)))
        print(f"    [FAIL] Complexity Gate: error reading report")

    # Release ready
    release_path = os.path.join(ROOT, "v3", "exports", "release_validation_matrix.json")
    try:
        with open(release_path, encoding="utf-8") as f:
            release_data = json.load(f)
        rel_ready = release_data.get("release_ready", False)
        results.append(("Release Ready", "PASS" if rel_ready else "FAIL",
                       f"release_ready={rel_ready}"))
        print(f"    [{'PASS' if rel_ready else 'FAIL'}] Release Ready: {rel_ready}")
    except Exception as e:
        results.append(("Release Ready", "FAIL", str(e)))
        print(f"    [FAIL] Release Ready: error reading report")

    # ── Summary table ──
    print()
    print("=" * 64)
    print("  RESULTS")
    print("=" * 64)
    print()
    print(f"  {'Check':<42} {'Result':<10} {'Detail'}")
    print(f"  {'-'*42} {'-'*10} {'-'*30}")

    passed = 0
    failed = 0
    for name, status, detail in results:
        marker = "[PASS]" if status == "PASS" else "[FAIL]"
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        detail_short = detail[:60] if detail else ""
        print(f"  {name:<42} {marker:<10} {detail_short}")

    print()
    print(f"  Total:  {len(results)}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Verdict: {'PASS' if failed == 0 else 'FAIL'}")
    print()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
