"""
SystemKernel v4.0 — Baseline Verification Script.

Runs all test suites and reports pass/fail status.
Standard library only. No network. No clone. No install. No external tools.

Usage:
    python scripts/verify_v4_baseline.py

Returns 0 if all tests pass, 1 if any fail.
"""

import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable

TEST_SUITES = [
    ("Kernel Invariants", "v3/tests/test_kernel_invariants.py"),
    ("V4 Baseline Guard", "v3/tests/test_v4_baseline_guard.py"),
    ("Capability Contract", "v3/tests/test_capability_contract.py"),
    ("Capability Registry", "v3/tests/test_capability_registry.py"),
    ("External Evidence", "v3/tests/test_external_evidence.py"),
    ("Orchestration Policy", "v3/tests/test_orchestration_policy.py"),
    ("Evaluation Harness", "v3/tests/test_evaluation_harness.py"),
    ("Productization Ops", "v3/tests/test_v4_productization_ops.py"),
    ("V4 Release Freeze", "v3/tests/test_v4_release_freeze.py"),
    ("Complexity Budget", "v3/tests/test_complexity_budget.py"),
]


def run_one(name, rel_path):
    full = os.path.join(ROOT, rel_path)
    if not os.path.exists(full):
        return (name, "SKIP", "file not found")
    try:
        result = subprocess.run(
            [PYTHON, full],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ROOT,
        )
        if result.returncode == 0:
            return (name, "PASS", "")
        else:
            # Extract last meaningful line for error
            lines = [l for l in result.stdout.split("\n") + result.stderr.split("\n") if l.strip()]
            error = lines[-1] if lines else f"exit code {result.returncode}"
            return (name, "FAIL", error[:120])
    except subprocess.TimeoutExpired:
        return (name, "FAIL", "timeout (>300s)")
    except Exception as e:
        return (name, "FAIL", str(e)[:120])


def main():
    print("=" * 60)
    print("  SystemKernel v4.0 — Baseline Verification")
    print("=" * 60)
    print()

    results = []
    for name, path in TEST_SUITES:
        name, status, detail = run_one(name, path)
        results.append((name, status, detail))
        if status == "PASS":
            print(f"  [PASS] {name}")
        elif status == "SKIP":
            print(f"  [SKIP] {name} — {detail}")
        else:
            print(f"  [FAIL] {name} — {detail}")

    print()
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    skipped = sum(1 for _, s, _ in results if s == "SKIP")
    total = len(results)

    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped, {total} total")

    if failed > 0:
        print()
        print("  VERIFICATION: FAILED")
        return 1
    else:
        print()
        print("  VERIFICATION: PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
