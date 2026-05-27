"""
SystemKernel CLI — core commands: status, quality, memory, reports, doctor.

Extracted from systemkernel.py during Phase 13D CLI Surface Compression.
All behavior preserved. No new capability added.
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile
import shutil

from v3.cli._helpers import (
    ROOT, V3_ROOT, EXPORTS_DIR, KERNEL_DIR, MEMORY_DIR,
    TESTS_DIR, QUALITY_DIR, CHECKPOINTS_DIR, TRACES_DIR,
    METRICS_DIR, CONFIG_DIR,
    _read_json, _count_test_functions, _count_test_files,
    _scan_banned_imports, _check_kernel_imports_memory,
    _check_kernel_imports_quality, _report_exists, _list_report_files,
)


def cmd_status() -> int:
    """Print system status summary."""
    print("=" * 60)
    print("  SystemKernel v3.0 — Status")
    print("=" * 60)

    kernel_report = _read_json(os.path.join(EXPORTS_DIR, "kernel_validity_report.json"))
    purity = kernel_report.get("purity_score", "?")
    print(f"\n  Kernel Purity:        {purity}/100")

    test_count = _count_test_functions()
    test_files = _count_test_files()
    print(f"  Test Suites:          {test_files}")
    print(f"  Total Tests:          {test_count}")

    mem_report = _read_json(os.path.join(EXPORTS_DIR, "memory_removability_report.json"))
    mem_removable = mem_report.get("removable", "YES") if mem_report else "YES"
    print(f"  Memory Removable:     {mem_removable}")

    mem_sys = _read_json(os.path.join(EXPORTS_DIR, "memory_system_report.json"))
    verdicts = mem_sys.get("verdicts", {})
    sot = verdicts.get("source_of_truth", "YES")
    print(f"  Events Source of Truth: {sot}")

    cb_report = _read_json(os.path.join(EXPORTS_DIR, "complexity_budget_report.json"))
    cb_verdict = cb_report.get("verdict", {}).get("verdict", "?")
    print(f"  Complexity Verdict:   {cb_verdict}")

    print(f"\n  Recent Reports ({EXPORTS_DIR}):")
    report_files = _list_report_files()
    key_reports = [
        "kernel_validity_report.json",
        "memory_system_report.json",
        "memory_removability_report.json",
        "complexity_budget_report.json",
        "phase_5a_gate_report.md",
        "phase_4d_completion_report.md",
    ]
    for name in key_reports:
        marker = "  [EXISTS]" if _report_exists(name) else "  [MISSING]"
        print(f"    {marker}  {name}")

    print()
    return 0


def cmd_quality() -> int:
    """Run complexity budget analysis and write report."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from v3.quality.phase_gate import evaluate_phase, write_complexity_report

    print("=" * 60)
    print("  SystemKernel v3.0 — Complexity Gate")
    print("=" * 60)

    result = evaluate_phase("5A", v3_root=V3_ROOT)
    report_path = os.path.join(EXPORTS_DIR, "complexity_budget_report.json")
    write_complexity_report(result, report_path)

    print(f"\n  Modules analyzed:     {len(result.module_complexities)}")
    print(f"  Complexity score:     {result.verdict.total_complexity_score}")
    print(f"  Benefit score:        {result.verdict.total_benefit_score}")
    print(f"  Net value:            {result.verdict.net_value_score}")
    print(f"  Risk ratio:           {result.verdict.risk_ratio}")
    print(f"  Verdict:              {result.verdict.verdict}")
    print(f"  Reasons:              {'; '.join(result.verdict.reasons)}")
    print(f"\n  Report written:       {report_path}")

    if result.verdict.is_rejected:
        print("\n  GATE REJECTED — fix complexity issues before proceeding.")
        return 2
    elif result.verdict.is_review:
        print("\n  GATE REVIEW — complexity exceeds benefit threshold. Review recommended.")
        return 0
    else:
        print("\n  GATE ACCEPTED — complexity is within budget.")
        return 0


def cmd_memory_report() -> int:
    """Generate and write memory system report."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    print("=" * 60)
    print("  SystemKernel v3.0 — Memory System Report")
    print("=" * 60)

    try:
        from v3.memory.runtime import MemoryRuntime
        from v3.memory.system_report import write_system_report_json
    except ImportError:
        print("\n  Memory runtime not available (memory module removed/restructured).")
        print("  This is expected when v3/memory/ is deleted per v4 removable-memory design.")
        return 0

    tmpdir = tempfile.mkdtemp(prefix="cli-mem-")
    try:
        store_path = os.path.join(tmpdir, "episodes.jsonl")
        runtime = MemoryRuntime.from_paths(
            store_path=store_path, enable_index=False, enable_compaction=False,
        )
        report_path = os.path.join(EXPORTS_DIR, "memory_system_report.json")
        write_system_report_json(runtime.store, report_path)
        report = _read_json(report_path)
        counts = report.get("counts", {})
        verdicts = report.get("verdicts", {})

        print(f"\n  Total records:        {counts.get('total_records', 0)}")
        print(f"  Index entries:        {counts.get('total_indexed_entries', 0)}")
        print(f"  Compacted:            {counts.get('total_compacted_records', 0)}")
        print(f"  Removability:         {verdicts.get('removability', 'YES')}")
        print(f"  Projection only:      {verdicts.get('projection_only', 'YES')}")
        print(f"  Source of truth:      {verdicts.get('source_of_truth', 'YES')}")
        print(f"  Report hash:          {report.get('report_hash', '')}")
        print(f"\n  Report written:       {report_path}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return 0


def cmd_reports_list() -> int:
    """List all report files in exports/."""
    print("=" * 60)
    print("  SystemKernel v3.0 — Reports")
    print("=" * 60)
    files = _list_report_files()
    if not files:
        print("\n  No reports found.")
        return 0

    json_files = [(n, s) for n, s in files if n.endswith(".json")]
    md_files = [(n, s) for n, s in files if n.endswith(".md")]
    other_files = [(n, s) for n, s in files if not n.endswith((".json", ".md"))]

    if json_files:
        print(f"\n  JSON Reports ({len(json_files)}):")
        for name, size in json_files:
            print(f"    {name}  ({size:,} bytes)")
    if md_files:
        print(f"\n  Markdown Reports ({len(md_files)}):")
        for name, size in md_files:
            print(f"    {name}  ({size:,} bytes)")
    if other_files:
        print(f"\n  Other ({len(other_files)}):")
        for name, size in other_files:
            print(f"    {name}  ({size:,} bytes)")

    print(f"\n  Total: {len(files)} report files")
    return 0


def cmd_reports_summary() -> int:
    """Print a short summary of key reports."""
    print("=" * 60)
    print("  SystemKernel v3.0 — Reports Summary")
    print("=" * 60)

    kernel = _read_json(os.path.join(EXPORTS_DIR, "kernel_validity_report.json"))
    purity = kernel.get("purity_score", "?")
    print(f"\n  PURE KERNEL:           purity_score={purity}")

    test_count = _count_test_functions()
    test_files = _count_test_files()
    print(f"  Tests:                 {test_count} tests in {test_files} suites")

    mem_sys = _read_json(os.path.join(EXPORTS_DIR, "memory_system_report.json"))
    mem_verdicts = mem_sys.get("verdicts", {})
    mem_counts = mem_sys.get("counts", {})
    print(f"  Memory:")
    print(f"    Records:             {mem_counts.get('total_records', '?')}")
    print(f"    Removable:           {mem_verdicts.get('removability', 'YES')}")
    print(f"    Source of truth:     {mem_verdicts.get('source_of_truth', 'YES')}")

    cb = _read_json(os.path.join(EXPORTS_DIR, "complexity_budget_report.json"))
    cb_v = cb.get("verdict", {})
    print(f"  Complexity:")
    print(f"    Verdict:             {cb_v.get('verdict', '?')}")
    print(f"    Complexity score:    {cb_v.get('total_complexity_score', '?')}")
    print(f"    Benefit score:       {cb_v.get('total_benefit_score', '?')}")

    print(f"\n  Phase Completion:")
    phases = [("4D", "phase_4d_completion_report.md"), ("5A", "phase_5a_gate_report.md")]
    for phase_name, filename in phases:
        marker = "[COMPLETE]" if _report_exists(filename) else "[PENDING]"
        print(f"    {marker} Phase {phase_name}")

    files = _list_report_files()
    json_count = sum(1 for n, _ in files if n.endswith(".json"))
    md_count = sum(1 for n, _ in files if n.endswith(".md"))
    print(f"\n  Reports:               {len(files)} total ({json_count} JSON, {md_count} MD)")
    print()
    return 0


def cmd_doctor() -> int:
    """Run lightweight health checks."""
    print("=" * 60)
    print("  SystemKernel v3.0 — Doctor")
    print("=" * 60)

    checks = []

    required_dirs = {
        "kernel/": KERNEL_DIR, "memory/": MEMORY_DIR,
        "tests/": TESTS_DIR, "quality/": QUALITY_DIR,
        "exports/": EXPORTS_DIR, "checkpoints/": CHECKPOINTS_DIR,
        "traces/": TRACES_DIR, "metrics/": METRICS_DIR,
        "config/": CONFIG_DIR,
    }
    for label, dpath in required_dirs.items():
        ok = os.path.isdir(dpath)
        checks.append((f"Directory: {label}", "PASS" if ok else "FAIL"))

    key_reports = [
        "kernel_validity_report.json",
        "memory_system_report.json",
        "complexity_budget_report.json",
    ]
    for rname in key_reports:
        ok = _report_exists(rname)
        checks.append((f"Report: {rname}", "PASS" if ok else "FAIL"))

    for dir_label, dir_path in [("kernel", KERNEL_DIR), ("memory", MEMORY_DIR), ("quality", QUALITY_DIR)]:
        violations = _scan_banned_imports(dir_path)
        ok = len(violations) == 0
        detail = "" if ok else f" ({len(violations)} violations: {violations[0][:60]}...)"
        checks.append((f"Banned imports: {dir_label}/", f"PASS{detail}" if ok else f"FAIL{detail}"))

    mem_violations = _check_kernel_imports_memory()
    ok = len(mem_violations) == 0
    detail = "" if ok else f" ({mem_violations[0]})"
    checks.append((f"Memory external", f"PASS{detail}" if ok else f"FAIL{detail}"))

    qual_violations = _check_kernel_imports_quality()
    ok = len(qual_violations) == 0
    detail = "" if ok else f" ({qual_violations[0]})"
    checks.append((f"Quality external", f"PASS{detail}" if ok else f"FAIL{detail}"))

    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from v3.quality.phase_gate import evaluate_phase
        result = evaluate_phase("5A", v3_root=V3_ROOT)
        can_run = result.verdict.verdict in ("ACCEPT", "REVIEW", "REJECT")
        checks.append(("Quality gate runs", f"PASS (verdict={result.verdict.verdict})" if can_run else "FAIL"))
    except Exception as e:
        checks.append(("Quality gate runs", f"FAIL ({e})"))

    try:
        with open(__file__, encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)
        checks.append(("CLI self-parse", "PASS"))
    except Exception as e:
        checks.append(("CLI self-parse", f"FAIL ({e})"))

    print(f"\n  {'Check':<40} {'Result'}")
    print(f"  {'-'*40} {'-'*20}")
    passed = 0
    failed = 0
    for name, result in checks:
        status = "[PASS]" if result.startswith("PASS") else "[FAIL]"
        if status == "[PASS]":
            passed += 1
        else:
            failed += 1
        print(f"  {name:<40} {result}")

    print(f"\n  Results: {passed} passed, {failed} failed, {len(checks)} total")
    print(f"  HEALTH: {'OK' if failed == 0 else 'ISSUES FOUND'}")
    return 0 if failed == 0 else 1
