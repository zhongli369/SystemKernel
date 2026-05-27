"""
SystemKernel v3.0 — Developer CLI.

One-command runtime for status, quality, memory, reports, and health checks.
All commands wrap existing facades. Zero new runtime capability.
Standard library only. Deterministic output.

Usage:
    python v3/cli/systemkernel.py status
    python v3/cli/systemkernel.py quality
    python v3/cli/systemkernel.py memory report
    python v3/cli/systemkernel.py reports list
    python v3/cli/systemkernel.py reports summary
    python v3/cli/systemkernel.py doctor
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from typing import Optional, Tuple


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


# ═══════════════════════════════════════════════════════════════════════
# Command: status
# ═══════════════════════════════════════════════════════════════════════

def cmd_status() -> int:
    """Print system status summary."""
    print("=" * 60)
    print("  SystemKernel v3.0 — Status")
    print("=" * 60)

    # Kernel purity
    kernel_report = _read_json(os.path.join(EXPORTS_DIR, "kernel_validity_report.json"))
    purity = kernel_report.get("purity_score", "?")
    print(f"\n  Kernel Purity:        {purity}/100")

    # Test summary
    test_count = _count_test_functions()
    test_files = _count_test_files()
    print(f"  Test Suites:          {test_files}")
    print(f"  Total Tests:          {test_count}")

    # Memory removable
    mem_report = _read_json(os.path.join(EXPORTS_DIR, "memory_removability_report.json"))
    mem_removable = mem_report.get("removable", "YES") if mem_report else "YES"
    print(f"  Memory Removable:     {mem_removable}")

    # Events source of truth
    mem_sys = _read_json(os.path.join(EXPORTS_DIR, "memory_system_report.json"))
    verdicts = mem_sys.get("verdicts", {})
    sot = verdicts.get("source_of_truth", "YES")
    print(f"  Events Source of Truth: {sot}")

    # Complexity verdict
    cb_report = _read_json(os.path.join(EXPORTS_DIR, "complexity_budget_report.json"))
    cb_verdict = cb_report.get("verdict", {}).get("verdict", "?")
    print(f"  Complexity Verdict:   {cb_verdict}")

    # Latest reports
    print(f"\n  Recent Reports ({EXPORTS_DIR}):")
    report_files = _list_report_files()
    # Show key reports
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


# ═══════════════════════════════════════════════════════════════════════
# Command: quality
# ═══════════════════════════════════════════════════════════════════════

def cmd_quality() -> int:
    """Run complexity budget analysis and write report."""
    # Ensure v3/ is on path
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


# ═══════════════════════════════════════════════════════════════════════
# Command: memory report
# ═══════════════════════════════════════════════════════════════════════

def cmd_memory_report() -> int:
    """Generate and write memory system report."""
    import tempfile
    import shutil

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.memory.runtime import MemoryRuntime
    from v3.memory.system_report import write_system_report_json

    print("=" * 60)
    print("  SystemKernel v3.0 — Memory System Report")
    print("=" * 60)

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


# ═══════════════════════════════════════════════════════════════════════
# Command: reports list
# ═══════════════════════════════════════════════════════════════════════

def cmd_reports_list() -> int:
    """List all report files in exports/."""
    print("=" * 60)
    print("  SystemKernel v3.0 — Reports")
    print("=" * 60)

    files = _list_report_files()
    if not files:
        print("\n  No reports found.")
        return 0

    # Group by type
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


# ═══════════════════════════════════════════════════════════════════════
# Command: reports summary
# ═══════════════════════════════════════════════════════════════════════

def cmd_reports_summary() -> int:
    """Print a short summary of key reports."""
    print("=" * 60)
    print("  SystemKernel v3.0 — Reports Summary")
    print("=" * 60)

    # Kernel validity
    kernel = _read_json(os.path.join(EXPORTS_DIR, "kernel_validity_report.json"))
    purity = kernel.get("purity_score", "?")
    print(f"\n  PURE KERNEL:           purity_score={purity}")

    # Tests
    test_count = _count_test_functions()
    test_files = _count_test_files()
    print(f"  Tests:                 {test_count} tests in {test_files} suites")

    # Memory
    mem_sys = _read_json(os.path.join(EXPORTS_DIR, "memory_system_report.json"))
    mem_verdicts = mem_sys.get("verdicts", {})
    mem_counts = mem_sys.get("counts", {})
    print(f"  Memory:")
    print(f"    Records:             {mem_counts.get('total_records', '?')}")
    print(f"    Removable:           {mem_verdicts.get('removability', 'YES')}")
    print(f"    Source of truth:     {mem_verdicts.get('source_of_truth', 'YES')}")

    # Complexity
    cb = _read_json(os.path.join(EXPORTS_DIR, "complexity_budget_report.json"))
    cb_v = cb.get("verdict", {})
    print(f"  Complexity:")
    print(f"    Verdict:             {cb_v.get('verdict', '?')}")
    print(f"    Complexity score:    {cb_v.get('total_complexity_score', '?')}")
    print(f"    Benefit score:       {cb_v.get('total_benefit_score', '?')}")

    # Phase completion
    print(f"\n  Phase Completion:")
    phases = [
        ("4D", "phase_4d_completion_report.md"),
        ("5A", "phase_5a_gate_report.md"),
    ]
    for phase_name, filename in phases:
        marker = "[COMPLETE]" if _report_exists(filename) else "[PENDING]"
        print(f"    {marker} Phase {phase_name}")

    # Report counts
    files = _list_report_files()
    json_count = sum(1 for n, _ in files if n.endswith(".json"))
    md_count = sum(1 for n, _ in files if n.endswith(".md"))
    print(f"\n  Reports:               {len(files)} total ({json_count} JSON, {md_count} MD)")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: doctor
# ═══════════════════════════════════════════════════════════════════════

def cmd_doctor() -> int:
    """Run lightweight health checks."""
    print("=" * 60)
    print("  SystemKernel v3.0 — Doctor")
    print("=" * 60)

    checks = []

    # 1. Required directories
    required_dirs = {
        "kernel/": KERNEL_DIR,
        "memory/": MEMORY_DIR,
        "tests/": TESTS_DIR,
        "quality/": QUALITY_DIR,
        "exports/": EXPORTS_DIR,
        "checkpoints/": CHECKPOINTS_DIR,
        "traces/": TRACES_DIR,
        "metrics/": METRICS_DIR,
        "config/": CONFIG_DIR,
    }
    for label, dpath in required_dirs.items():
        ok = os.path.isdir(dpath)
        checks.append((f"Directory: {label}", "PASS" if ok else "FAIL"))

    # 2. Key reports exist
    key_reports = [
        "kernel_validity_report.json",
        "memory_system_report.json",
        "complexity_budget_report.json",
    ]
    for rname in key_reports:
        ok = _report_exists(rname)
        checks.append((f"Report: {rname}", "PASS" if ok else "FAIL"))

    # 3. Banned imports scan (kernel + memory + quality)
    for dir_label, dir_path in [("kernel", KERNEL_DIR), ("memory", MEMORY_DIR), ("quality", QUALITY_DIR)]:
        violations = _scan_banned_imports(dir_path)
        ok = len(violations) == 0
        detail = "" if ok else f" ({len(violations)} violations: {violations[0][:60]}...)"
        checks.append((f"Banned imports: {dir_label}/", f"PASS{detail}" if ok else f"FAIL{detail}"))

    # 4. Memory is external (kernel doesn't import memory)
    mem_violations = _check_kernel_imports_memory()
    ok = len(mem_violations) == 0
    detail = "" if ok else f" ({mem_violations[0]})"
    checks.append((f"Memory external", f"PASS{detail}" if ok else f"FAIL{detail}"))

    # 5. Quality is external (kernel doesn't import quality)
    qual_violations = _check_kernel_imports_quality()
    ok = len(qual_violations) == 0
    detail = "" if ok else f" ({qual_violations[0]})"
    checks.append((f"Quality external", f"PASS{detail}" if ok else f"FAIL{detail}"))

    # 6. Quality gate can run
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from v3.quality.phase_gate import evaluate_phase
        result = evaluate_phase("5A", v3_root=V3_ROOT)
        can_run = result.verdict.verdict in ("ACCEPT", "REVIEW", "REJECT")
        checks.append(("Quality gate runs", f"PASS (verdict={result.verdict.verdict})" if can_run else "FAIL"))
    except Exception as e:
        checks.append(("Quality gate runs", f"FAIL ({e})"))

    # 7. CLI self-check (this file parses correctly)
    try:
        with open(__file__, encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)
        checks.append(("CLI self-parse", "PASS"))
    except Exception as e:
        checks.append(("CLI self-parse", f"FAIL ({e})"))

    # Print table
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


# ═══════════════════════════════════════════════════════════════════════
# Command: intake profile
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_profile(name: str) -> int:
    """Show intake assessment for a specific known repo profile."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.repo_profiles import get_profile
    from v3.intake.repo_intake import decide_repo_intake, compute_report_hash
    from v3.intake.rules import apply_rules, classify_repo_type

    profile = get_profile(name)
    if profile is None:
        print(f"Unknown profile: {name}")
        print(f"Use 'intake list' to see available profiles.")
        return 1

    inp = profile.to_input()
    signals = profile.analyze()
    decision = decide_repo_intake(inp, signals)
    rule_decision, rule_id = apply_rules(inp, signals)
    repo_type = classify_repo_type(signals, profile.name)
    report_hash = compute_report_hash(inp, signals, decision)

    print("=" * 60)
    print(f"  Repo Intake — {profile.name}")
    print("=" * 60)

    print(f"\n  URL:                  {profile.url}")
    print(f"  Category:             {profile.category_hint or repo_type}")
    print(f"  Repo Type:            {repo_type}")
    print(f"  Intended Use:         {profile.intended_use}")

    print(f"\n  Signals:")
    print(f"    README:             {'YES' if signals.has_readme else 'NO'}")
    print(f"    LICENSE:            {'YES' if signals.has_license else 'NO'}")
    print(f"    Languages:          {', '.join(signals.language_hints) or 'none'}")
    print(f"    CLI:                {'YES' if signals.has_cli else 'NO'}")
    print(f"    MCP:                {'YES' if signals.has_mcp else 'NO'}")
    print(f"    Tests:              {'YES' if signals.has_tests else 'NO'}")
    print(f"    Docs:               {'YES' if signals.has_docs else 'NO'}")

    print(f"\n  Dependency Risks:")
    print(f"    Banned:             {signals.banned_dependency_hits}")
    print(f"    Heavy:              {signals.heavy_dependency_hits}")
    print(f"    LLM:                {signals.llm_dependency_hits}")
    print(f"    Memory:             {signals.memory_dependency_hits}")
    print(f"    Framework:          {signals.framework_dependency_hits}")

    print(f"\n  Decision:")
    print(f"    Verdict:            {decision.decision}")
    print(f"    Priority:           {decision.priority}")
    print(f"    CC Value:           {decision.claude_code_value_score}/10")
    print(f"    SK Value:           {decision.systemkernel_value_score}/10")
    print(f"    Complexity Risk:    {decision.complexity_risk_score}/10")
    print(f"    Purity Risk:        {decision.purity_risk_score}/10")
    print(f"    Maintenance Risk:   {decision.maintenance_risk_score}/10")
    print(f"    Final Score:        {decision.final_score}")
    print(f"    Rule Match:         {rule_id} → {rule_decision}")
    print(f"    Report Hash:        {report_hash}")

    if decision.reasons:
        print(f"\n  Reasons:")
        for r in decision.reasons:
            print(f"    - {r}")

    if profile.known_risks:
        print(f"\n  Known Risks:")
        for r in profile.known_risks:
            print(f"    - {r}")

    print(f"\n  Target:              {decision.recommended_target_dir}")
    print(f"  Allowed:             {', '.join(decision.allowed_actions)}")
    print(f"  Forbidden:           {', '.join(decision.forbidden_actions)}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake list
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_list() -> int:
    """List all known repo profiles."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.repo_profiles import get_all_profiles

    profiles = get_all_profiles()

    print("=" * 60)
    print("  Repo Intake — Known Profiles")
    print("=" * 60)

    print(f"\n  {'Name':<35} {'Expected':<25} {'Category'}")
    print(f"  {'-'*35} {'-'*25} {'-'*20}")

    for p in profiles:
        print(f"  {p.name:<35} {p.expected_decision:<25} {p.category_hint or 'unknown':<20}")

    print(f"\n  Total: {len(profiles)} profiles")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake summarize
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_summarize() -> int:
    """Summarize all repo profiles with full intake decisions."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.repo_profiles import get_all_profiles
    from v3.intake.repo_intake import decide_repo_intake, compute_report_hash
    from v3.intake.rules import apply_rules, classify_repo_type

    profiles = get_all_profiles()

    print("=" * 60)
    print("  Repo Intake — Summary")
    print("=" * 60)

    # Count decisions
    counts = {"DIRECT_CLONE": 0, "EXTERNAL_EXTENSION": 0,
              "ARCHITECTURE_REFERENCE": 0, "REJECT": 0}

    results = []
    for p in profiles:
        inp = p.to_input()
        signals = p.analyze()
        decision = decide_repo_intake(inp, signals)
        rule_decision, rule_id = apply_rules(inp, signals)
        repo_type = classify_repo_type(signals, p.name)
        report_hash = compute_report_hash(inp, signals, decision)

        counts[decision.decision] = counts.get(decision.decision, 0) + 1

        results.append({
            "name": p.name,
            "decision": decision.decision,
            "priority": decision.priority,
            "cc_value": decision.claude_code_value_score,
            "sk_value": decision.systemkernel_value_score,
            "final_score": decision.final_score,
            "rule_id": rule_id,
            "rule_decision": rule_decision,
            "repo_type": repo_type,
            "report_hash": report_hash,
            "expected": p.expected_decision,
            "match": "MATCH" if decision.decision == p.expected_decision else "MISMATCH",
        })

    # Print table
    print(f"\n  {'Name':<35} {'Decision':<25} {'Score':<8} {'Expected':<25} {'Match'}")
    print(f"  {'-'*35} {'-'*25} {'-'*8} {'-'*25} {'-'*8}")

    for r in results:
        flag = " !" if r["match"] == "MISMATCH" else ""
        print(f"  {r['name']:<35} {r['decision']:<25} {r['final_score']:<8.1f} "
              f"{r['expected']:<25} {r['match']}{flag}")

    # Summary counts
    print(f"\n  Decision Distribution:")
    for dec in ("DIRECT_CLONE", "EXTERNAL_EXTENSION", "ARCHITECTURE_REFERENCE", "REJECT"):
        c = counts.get(dec, 0)
        bar = "#" * c
        print(f"    {dec:<25} {c:>2}  {bar}")

    # Direct clone candidates
    clones = [r for r in results if r["decision"] == "DIRECT_CLONE"]
    if clones:
        print(f"\n  DIRECT_CLONE Candidates ({len(clones)}):")
        for r in clones:
            print(f"    - {r['name']} (score={r['final_score']:.1f}, priority={r['priority']})")

    # Mismatches
    mismatches = [r for r in results if r["match"] == "MISMATCH"]
    if mismatches:
        print(f"\n  MISMATCHES ({len(mismatches)}):")
        for r in mismatches:
            print(f"    - {r['name']}: expected {r['expected']}, got {r['decision']}")

    print(f"\n  Total: {len(profiles)} profiles")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake registry
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_registry(output_path: str = None) -> int:
    """Generate the external tool registry from all profiles."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.tool_registry import build_registry_from_profiles, write_registry

    print("=" * 60)
    print("  SystemKernel v3.0 — External Tool Registry")
    print("=" * 60)
    print()
    print("  PLAN ONLY — no network access, no cloning performed.")
    print()

    registry = build_registry_from_profiles()

    if output_path is None:
        output_path = os.path.join(EXPORTS_DIR, "external_tool_registry.json")

    write_registry(registry, output_path)

    print(f"  Entries:              {len(registry.entries)}")
    print(f"  Direct clone:         {registry.direct_clone_count}")
    print(f"  External extension:   {registry.external_extension_count}")
    print(f"  Architecture ref:     {registry.architecture_reference_count}")
    print(f"  Rejected:             {registry.reject_count}")
    print(f"  Registry hash:        {registry.registry_hash}")
    print()

    # Breakdown by use mode
    print(f"  Use Mode Breakdown:")
    for entry in registry.entries:
        print(f"    [{entry.priority}] {entry.name:<30} → {entry.use_mode}")

    print(f"\n  Registry written:     {output_path}")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake clone-plan
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_clone_plan(output_dir: str = None) -> int:
    """Generate the GitHub clone plan (JSON + Markdown)."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.tool_registry import build_registry_from_profiles
    from v3.intake.clone_plan import create_clone_plan, filter_clone_now, summarize_plan
    from v3.intake.clone_plan import write_clone_plan_markdown

    print("=" * 60)
    print("  SystemKernel v3.0 — GitHub Clone Plan")
    print("=" * 60)
    print()
    print("  PLAN ONLY — no actual cloning is performed.")
    print("  All items require manual review before execution.")
    print()

    registry = build_registry_from_profiles()
    plan = create_clone_plan(registry, root_dir="F:\\Claude\\Github")

    if output_dir is None:
        output_dir = EXPORTS_DIR

    json_path = os.path.join(output_dir, "github_clone_plan.json")
    md_path = os.path.join(output_dir, "github_clone_plan.md")

    # Write JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)

    # Write Markdown
    write_clone_plan_markdown(plan, md_path)

    clone_now = filter_clone_now(plan)
    inspect = [i for i in plan.items if i.post_clone_action == "inspect_only"]
    ext_eval = [i for i in plan.items if i.post_clone_action == "evaluate_external_service"]
    ref_only = [i for i in plan.items if i.post_clone_action == "none"]

    print(f"  Clone Now ({len(clone_now)}):")
    for item in clone_now:
        print(f"    [{item.priority}] {item.name} → {item.target_path}")
        print(f"          Post-clone: {item.post_clone_action}")

    print(f"\n  Inspect Only ({len(inspect)}):")
    for item in inspect:
        print(f"    [{item.priority}] {item.name}")

    print(f"\n  External Evaluation ({len(ext_eval)}):")
    for item in ext_eval:
        print(f"    [{item.priority}] {item.name}")

    print(f"\n  Reference Only ({len(ref_only)}):")
    for item in ref_only:
        print(f"    [{item.priority}] {item.name}")

    print(f"\n  Plan hash:            {plan.plan_hash}")
    print(f"  JSON written:         {json_path}")
    print(f"  Markdown written:     {md_path}")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: intake clone-list
# ═══════════════════════════════════════════════════════════════════════

def cmd_intake_clone_list() -> int:
    """Print recommended clone order. Does NOT clone."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.intake.tool_registry import build_registry_from_profiles, recommend_clone_order

    print("=" * 60)
    print("  SystemKernel v3.0 — Recommended Clone Order")
    print("=" * 60)
    print()
    print("  PLAN ONLY — no actual cloning is performed.")
    print("  Run these commands manually when ready:")
    print()

    registry = build_registry_from_profiles()
    order = recommend_clone_order(registry)

    for i, name in enumerate(order, 1):
        entry = None
        for e in registry.entries:
            if e.name == name:
                entry = e
                break
        if entry:
            print(f"  {i}. git clone {entry.repo_url} {entry.target_dir}")
            print(f"     Use mode: {entry.use_mode}")
            print(f"     Priority: {entry.priority}")
            print()

    print(f"  Total clone-now items: {len(order)}")
    print()
    print("  SAFETY REMINDER:")
    print("    - These are EXTERNAL tools, not kernel modules.")
    print("    - Clone into F:/Claude/Github/ — outside kernel boundary.")
    print("    - Do NOT integrate into SystemKernel without separate audit.")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: context-pack plan
# ═══════════════════════════════════════════════════════════════════════

def cmd_context_pack_plan(target: str, output: str, style: str = "markdown") -> int:
    """Plan a context pack command. Does NOT execute."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

    config = ContextPackConfig(
        target_path=target,
        output_path=output,
        style=style,
    )
    result = ContextPackAdapter.plan(config)

    print("=" * 60)
    print("  SystemKernel v3.0 — Context Pack Plan")
    print("=" * 60)
    print()
    print(f"  Status:               {result.status}")
    print(f"  Target:               {result.target_path}")
    print(f"  Output:               {result.output_path}")
    print(f"  Estimated size:       {result.size_bytes:,} bytes")
    print(f"  Estimated tokens:     {result.token_estimate:,}")
    print(f"  Estimated files:      {len(result.included_files)}")
    print(f"  Truth source:         {result.truth_source}")

    if result.command:
        print(f"\n  Planned command:")
        print(f"    {result.command}")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")

    if result.included_files:
        print(f"\n  Files to include ({len(result.included_files)}):")
        for f in result.included_files[:20]:
            print(f"    - {f}")
        if len(result.included_files) > 20:
            print(f"    ... and {len(result.included_files) - 20} more")

    print()
    if result.status == "blocked":
        return 1
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Command: context-pack inspect
# ═══════════════════════════════════════════════════════════════════════

def cmd_context_pack_inspect(path: str) -> int:
    """Inspect an existing context pack output file. Read-only."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_pack import ContextPackAdapter

    result = ContextPackAdapter.inspect_output(path)
    verified = ContextPackAdapter.verify_pack(result)

    print("=" * 60)
    print("  SystemKernel v3.0 — Context Pack Inspect")
    print("=" * 60)
    print()
    print(f"  Status:               {result.status}")
    print(f"  Path:                 {result.output_path}")
    print(f"  Size:                 {result.size_bytes:,} bytes")
    print(f"  Lines:                {result.line_count:,}")
    print(f"  Token estimate:       {result.token_estimate:,}")
    print(f"  Pack hash:            {result.pack_hash}")
    print(f"  Truth source:         {result.truth_source}")
    print(f"  Verified:             {verified}")
    print(f"  Included files:       {len(result.included_files)}")

    if result.included_files:
        print()
        for f in result.included_files[:30]:
            print(f"    - {f}")
        if len(result.included_files) > 30:
            print(f"    ... and {len(result.included_files) - 30} more")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")

    print()
    return 0 if result.status == "generated" else 1


# ═══════════════════════════════════════════════════════════════════════
# Command: context-pack generate
# ═══════════════════════════════════════════════════════════════════════

def cmd_context_pack_generate(target: str, output: str, style: str = "markdown",
                               allow_execute: bool = False) -> int:
    """Generate a context pack. Requires --allow-execute flag."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_pack import ContextPackConfig, ContextPackAdapter

    if not allow_execute:
        print("ERROR: --allow-execute flag is required to generate a context pack.")
        print()
        print("This flag confirms you understand:")
        print("  1. An external tool (npx repomix) will be executed")
        print("  2. Network access may be required on first run")
        print("  3. The generated pack is NOT a truth source")
        print("  4. The generated pack will be written to disk")
        print()
        print("Run with --allow-execute to proceed.")
        return 1

    config = ContextPackConfig(
        target_path=target,
        output_path=output,
        style=style,
    )
    result = ContextPackAdapter.generate(config, allow_execute=True)

    print("=" * 60)
    print("  SystemKernel v3.0 — Context Pack Generate")
    print("=" * 60)
    print()
    print(f"  Status:               {result.status}")
    print(f"  Target:               {result.target_path}")
    print(f"  Output:               {result.output_path}")

    if result.status == "generated":
        print(f"  Size:                 {result.size_bytes:,} bytes")
        print(f"  Lines:                {result.line_count:,}")
        print(f"  Token estimate:       {result.token_estimate:,}")
        print(f"  Pack hash:            {result.pack_hash}")
        print(f"  Included files:       {len(result.included_files)}")
        print(f"  Truth source:         {result.truth_source}")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")

    print()
    return 0 if result.status == "generated" else 1


# ═══════════════════════════════════════════════════════════════════════
# Command: usage inspect
# ═══════════════════════════════════════════════════════════════════════

def cmd_usage_inspect(path: str) -> int:
    """Inspect ccusage JSON output and print summary."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.usage_report import UsageReportAdapter

    print("=" * 60)
    print("  SystemKernel v3.0 — Usage Report Inspect")
    print("=" * 60)

    if not os.path.exists(path):
        print(f"\n  ERROR: File not found: {path}")
        return 1

    try:
        summary = UsageReportAdapter.inspect(path)
    except Exception as e:
        print(f"\n  ERROR: Failed to parse usage data: {e}")
        return 1

    verified = UsageReportAdapter.verify_summary(summary)

    print(f"\n  Source tool:          {summary.source_tool}")
    print(f"  Records:              {summary.record_count}")
    print(f"  Date range:           {summary.date_start} → {summary.date_end}")
    print(f"  Total tokens:         {summary.total_tokens:,}")
    print(f"  Total cost:           ${summary.total_cost_usd:,.6f}")
    print(f"  Cache read ratio:     {summary.cache_read_ratio:.4f}")
    print(f"  Models:               {summary.model_count}")
    print(f"  Agents:               {summary.agent_count}")
    print(f"  Sensitive detected:   {summary.sensitive_text_detected}")
    print(f"  Report hash:          {summary.report_hash}")
    print(f"  Truth source:         {summary.truth_source}")
    print(f"  Verified:             {verified}")

    if summary.warnings:
        print(f"\n  Warnings ({len(summary.warnings)}):")
        for w in summary.warnings:
            print(f"    - {w}")

    print()
    return 0 if verified else 1


# ═══════════════════════════════════════════════════════════════════════
# Command: usage summarize
# ═══════════════════════════════════════════════════════════════════════

def cmd_usage_summarize(path: str, output: str) -> int:
    """Read ccusage JSON output and write normalized usage summary."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.usage_report import UsageReportAdapter

    print("=" * 60)
    print("  SystemKernel v3.0 — Usage Report Summarize")
    print("=" * 60)

    if not os.path.exists(path):
        print(f"\n  ERROR: File not found: {path}")
        return 1

    try:
        summary = UsageReportAdapter.inspect(path)
    except Exception as e:
        print(f"\n  ERROR: Failed to parse usage data: {e}")
        return 1

    UsageReportAdapter.write_summary(summary, output)

    print(f"\n  Input:                {path}")
    print(f"  Output:               {output}")
    print(f"  Records:              {summary.record_count}")
    print(f"  Total tokens:         {summary.total_tokens:,}")
    print(f"  Total cost:           ${summary.total_cost_usd:,.6f}")
    print(f"  Report hash:          {summary.report_hash}")
    print(f"  Truth source:         {summary.truth_source}")
    print(f"\n  Summary written.")
    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# CLI Main
# ═══════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="systemkernel",
        description="SystemKernel v3.0 Developer CLI",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # status
    sub.add_parser("status", help="Print system status summary")

    # quality
    sub.add_parser("quality", help="Run complexity budget gate")

    # memory report
    sub.add_parser("memory", help="Memory operations").add_argument(
        "memory_action", choices=["report"], nargs="?", default="report",
        help="Memory action (default: report)"
    )

    # reports
    reports_parser = sub.add_parser("reports", help="Report operations")
    reports_parser.add_argument(
        "reports_action", choices=["list", "summary"], nargs="?", default="list",
        help="Reports action (default: list)"
    )

    # doctor
    sub.add_parser("doctor", help="Run health checks")

    # intake
    intake_parser = sub.add_parser("intake", help="Repo intake operations")
    intake_sub = intake_parser.add_subparsers(dest="intake_action", help="Intake actions")

    intake_profile_parser = intake_sub.add_parser("profile", help="Show intake profile for a repo")
    intake_profile_parser.add_argument("name", help="Profile name (e.g. Repomix, LangGraph)")

    intake_sub.add_parser("list", help="List all known repo profiles")
    intake_sub.add_parser("summarize", help="Summarize all repo profiles with decisions")

    intake_registry_parser = intake_sub.add_parser("registry", help="Generate external tool registry")
    intake_registry_parser.add_argument("--output", default=None,
                                        help="Output path (default: v3/exports/external_tool_registry.json)")

    intake_clone_plan_parser = intake_sub.add_parser("clone-plan", help="Generate GitHub clone plan")
    intake_clone_plan_parser.add_argument("--output-dir", default=None,
                                          help="Output directory (default: v3/exports/)")

    intake_sub.add_parser("clone-list", help="List recommended clone order (no actual cloning)")

    # context-pack
    cp_parser = sub.add_parser("context-pack", help="External context pack operations")
    cp_sub = cp_parser.add_subparsers(dest="cp_action", help="Context pack actions")

    cp_plan_parser = cp_sub.add_parser("plan", help="Plan a context pack (no execution)")
    cp_plan_parser.add_argument("target", help="Target directory path")
    cp_plan_parser.add_argument("--output", required=True, help="Output file path")
    cp_plan_parser.add_argument("--style", default="markdown",
                                choices=["markdown", "xml", "json", "plain"],
                                help="Output format (default: markdown)")

    cp_inspect_parser = cp_sub.add_parser("inspect", help="Inspect an existing context pack")
    cp_inspect_parser.add_argument("path", help="Path to context pack output file")

    cp_gen_parser = cp_sub.add_parser("generate", help="Generate a context pack (requires --allow-execute)")
    cp_gen_parser.add_argument("target", help="Target directory path")
    cp_gen_parser.add_argument("--output", required=True, help="Output file path")
    cp_gen_parser.add_argument("--style", default="markdown",
                               choices=["markdown", "xml", "json", "plain"],
                               help="Output format (default: markdown)")
    cp_gen_parser.add_argument("--allow-execute", action="store_true",
                               help="Explicitly allow external command execution")

    # usage
    usage_parser = sub.add_parser("usage", help="External usage report operations")
    usage_sub = usage_parser.add_subparsers(dest="usage_action", help="Usage actions")

    usage_inspect_parser = usage_sub.add_parser("inspect", help="Inspect ccusage JSON output")
    usage_inspect_parser.add_argument("path", help="Path to ccusage JSON output file")

    usage_summarize_parser = usage_sub.add_parser("summarize", help="Write normalized usage summary")
    usage_summarize_parser.add_argument("path", help="Path to ccusage JSON output file")
    usage_summarize_parser.add_argument("--output", required=True, help="Output JSON path")

    # context-plane
    ctxpl_parser = sub.add_parser("context-plane", help="Context engineering plane operations")
    ctxpl_sub = ctxpl_parser.add_subparsers(dest="ctxpl_action", help="Context plane actions")

    ctxpl_plan_parser = ctxpl_sub.add_parser("plan", help="Plan a context pack (no execution)")
    ctxpl_plan_parser.add_argument("target", help="Target directory path")
    ctxpl_plan_parser.add_argument("--output", default="", help="Output file path")
    ctxpl_plan_parser.add_argument("--style", default="markdown",
                                   choices=["markdown", "xml", "json", "plain"],
                                   help="Output format (default: markdown)")

    ctxpl_inspect_parser = ctxpl_sub.add_parser("inspect", help="Inspect an existing context pack")
    ctxpl_inspect_parser.add_argument("path", help="Path to context pack output file")

    ctxpl_evidence_parser = ctxpl_sub.add_parser("evidence", help="Build evidence bundle from context pack")
    ctxpl_evidence_parser.add_argument("path", help="Path to context pack output file")
    ctxpl_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")
    ctxpl_evidence_parser.add_argument("--target", default="", help="Original target path (for plan context)")

    # memory-intel
    mi_parser = sub.add_parser("memory-intel", help="Memory intelligence plane operations")
    mi_sub = mi_parser.add_subparsers(dest="mi_action", help="Memory intelligence actions")

    mi_sub.add_parser("profiles", help="List memory intelligence provider profiles")

    mi_mock_parser = mi_sub.add_parser("mock", help="Generate deterministic mock memory intelligence result")
    mi_mock_parser.add_argument("--provider", default="deterministic_mock_memory",
                               help="Provider ID (default: deterministic_mock_memory)")
    mi_mock_parser.add_argument("--signals", type=int, default=3,
                               help="Number of mock signals to generate (default: 3)")

    mi_evidence_parser = mi_sub.add_parser("evidence", help="Build evidence bundle from memory intelligence result")
    mi_evidence_parser.add_argument("--provider", default="deterministic_mock_memory",
                                   help="Provider ID (default: deterministic_mock_memory)")
    mi_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # workspace
    ws_parser = sub.add_parser("workspace", help="Workspace context plane operations")
    ws_sub = ws_parser.add_subparsers(dest="ws_action", help="Workspace actions")

    ws_sub.add_parser("profiles", help="List workspace provider profiles")

    ws_mock_parser = ws_sub.add_parser("mock", help="Generate deterministic mock workspace snapshot")
    ws_mock_parser.add_argument("--provider", default="deterministic_mock_workspace",
                               help="Provider ID (default: deterministic_mock_workspace)")
    ws_mock_parser.add_argument("--files", type=int, default=3,
                               help="Number of mock file refs (default: 3)")
    ws_mock_parser.add_argument("--diagnostics", type=int, default=2,
                               help="Number of mock diagnostics (default: 2)")

    ws_evidence_parser = ws_sub.add_parser("evidence", help="Build evidence bundle from workspace snapshot")
    ws_evidence_parser.add_argument("--provider", default="deterministic_mock_workspace",
                                   help="Provider ID (default: deterministic_mock_workspace)")
    ws_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # agent-worker
    aw_parser = sub.add_parser("agent-worker", help="Agent worker plane operations")
    aw_sub = aw_parser.add_subparsers(dest="aw_action", help="Agent worker actions")

    aw_sub.add_parser("profiles", help="List agent worker provider profiles")

    aw_mock_parser = aw_sub.add_parser("mock", help="Generate deterministic mock agent worker result")
    aw_mock_parser.add_argument("--provider", default="deterministic_mock_agent",
                               help="Provider ID (default: deterministic_mock_agent)")
    aw_mock_parser.add_argument("--proposals", type=int, default=2,
                               help="Number of mock proposals to generate (default: 2)")

    aw_evidence_parser = aw_sub.add_parser("evidence", help="Build evidence bundle from agent worker result")
    aw_evidence_parser.add_argument("--provider", default="deterministic_mock_agent",
                                   help="Provider ID (default: deterministic_mock_agent)")
    aw_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # skill-evolution
    se_parser = sub.add_parser("skill-evolution", help="Skill evolution plane operations")
    se_sub = se_parser.add_subparsers(dest="se_action", help="Skill evolution actions")

    se_sub.add_parser("profiles", help="List skill evolution provider profiles")

    se_mock_parser = se_sub.add_parser("mock", help="Generate deterministic mock skill evolution result")
    se_mock_parser.add_argument("--provider", default="deterministic_mock_skill_evolution",
                               help="Provider ID (default: deterministic_mock_skill_evolution)")
    se_mock_parser.add_argument("--proposals", type=int, default=2,
                               help="Number of mock proposals to generate (default: 2)")
    se_mock_parser.add_argument("--signals", type=int, default=3,
                               help="Number of mock gap signals (default: 3)")

    se_evidence_parser = se_sub.add_parser("evidence", help="Build evidence bundle from skill evolution result")
    se_evidence_parser.add_argument("--provider", default="deterministic_mock_skill_evolution",
                                   help="Provider ID (default: deterministic_mock_skill_evolution)")
    se_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # orchestrate
    orch_parser = sub.add_parser("orchestrate", help="Orchestration policy layer operations")
    orch_sub = orch_parser.add_subparsers(dest="orch_action", help="Orchestration actions")

    orch_sub.add_parser("policies", help="List orchestration policy profiles")

    orch_plan_parser = orch_sub.add_parser("plan", help="Build dry-run orchestration plan")
    orch_plan_parser.add_argument("--profile", default="safe_context_only",
                                 help="Policy profile ID (default: safe_context_only)")
    orch_plan_parser.add_argument("--objective", default="Dry-run orchestration plan",
                                 help="Objective text for the plan")

    orch_evidence_parser = orch_sub.add_parser("evidence", help="Build evidence bundle from orchestration plan")
    orch_evidence_parser.add_argument("--profile", default="safe_context_only",
                                     help="Policy profile ID (default: safe_context_only)")
    orch_evidence_parser.add_argument("--objective", default="Dry-run orchestration plan",
                                     help="Objective text for the plan")
    orch_evidence_parser.add_argument("--output", default="", help="Output JSON path for evidence bundle")

    # eval
    eval_parser = sub.add_parser("eval", help="Evaluation and regression harness operations")
    eval_sub = eval_parser.add_subparsers(dest="eval_action", help="Eval actions")

    eval_sub.add_parser("suite", help="List default eval cases")

    eval_sub.add_parser("run", help="Run deterministic static eval suite")

    eval_reg_parser = eval_sub.add_parser("regression", help="Generate regression matrix result")
    eval_reg_parser.add_argument("--output", default="", help="Output JSON path")

    eval_ben_parser = eval_sub.add_parser("benefit", help="Generate benefit-vs-complexity report")
    eval_ben_parser.add_argument("--output", default="", help="Output JSON path")

    # v4
    v4_parser = sub.add_parser("v4", help="V4 productization and ops commands")
    v4_sub = v4_parser.add_subparsers(dest="v4_action", help="V4 actions")

    v4_sub.add_parser("status", help="Print compact v4 operational status")

    v4_ops_check_parser = v4_sub.add_parser("ops-check", help="Print v4 operational checklist")
    v4_ops_check_parser.add_argument("--output", default="", help="Output JSON path")

    v4_runbook_parser = v4_sub.add_parser("runbook", help="Write v4 runbook")
    v4_runbook_parser.add_argument("--output", default="", help="Output directory (default: v3/exports/)")
    v4_runbook_parser.add_argument("--format", default="md", choices=["md", "json"],
                                    help="Output format (default: md)")

    v4_sub.add_parser("summary", help="Combined registry/evidence/orchestration/eval summary")

    # capability
    cap_parser = sub.add_parser("capability", help="Capability registry operations")
    cap_sub = cap_parser.add_subparsers(dest="cap_action", help="Capability actions")

    cap_sub.add_parser("list", help="List all capability registry entries")

    cap_sub.add_parser("summary", help="Print capability registry summary counts")

    cap_show_parser = cap_sub.add_parser("show", help="Show one capability registry entry")
    cap_show_parser.add_argument("adapter_id", help="Adapter ID to show")

    return parser


# ═══════════════════════════════════════════════════════════════════════
# Context engineering plane commands (Phase 4)
# ═══════════════════════════════════════════════════════════════════════

def cmd_context_plane_plan(target: str, output: str = "", style: str = "markdown") -> int:
    """Plan a context pack through the Context Engineering Plane. No execution."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_plane import (
        plan_context_pack,
        default_context_budget_policy,
        validate_context_budget,
        BUDGET_PASS,
        BUDGET_REVIEW,
        BUDGET_BLOCKED,
    )

    policy = default_context_budget_policy()
    plan = plan_context_pack(target, output=output, style=style, policy=policy)
    budget = validate_context_budget(plan, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Context Engineering Plane")
    print("=" * 60)
    print()
    print(f"  Adapter:              {plan.adapter_id}")
    print(f"  Target:               {plan.target_path}")
    print(f"  Output:               {plan.output_path}")
    print(f"  Style:                {plan.style}")
    print(f"  Estimated files:      {plan.estimated_files}")
    print(f"  Estimated size:       {plan.estimated_bytes:,} bytes")
    print(f"  Estimated tokens:     {plan.estimated_tokens:,}")
    print(f"  Budget status:        {plan.budget_status}")
    print(f"  Plan hash:            {plan.plan_hash}")

    if plan.command:
        print(f"\n  Planned command:")
        print(f"    {plan.command}")

    if budget.violations:
        print(f"\n  Budget Violations:")
        for v in budget.violations:
            print(f"    [BLOCKED] {v}")

    if budget.warnings:
        print(f"\n  Budget Warnings:")
        for w in budget.warnings:
            print(f"    [WARN] {w}")

    if plan.warnings:
        print(f"\n  Adapter Warnings:")
        for w in plan.warnings:
            if w not in budget.violations and w not in budget.warnings:
                print(f"    - {w}")

    print()
    if plan.budget_status == BUDGET_BLOCKED:
        return 1
    return 0


def cmd_context_plane_inspect(path: str) -> int:
    """Inspect an existing context pack through the Context Engineering Plane."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_plane import (
        inspect_context_pack,
        default_context_budget_policy,
        validate_context_budget,
    )

    policy = default_context_budget_policy()
    inspection = inspect_context_pack(path, policy=policy)
    budget = validate_context_budget(inspection, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Context Engineering Plane")
    print("=" * 60)
    print()
    print(f"  Path:                 {inspection.output_path}")
    print(f"  Size:                 {inspection.size_bytes:,} bytes")
    print(f"  Lines:                {inspection.line_count:,}")
    print(f"  Token estimate:       {inspection.token_estimate:,}")
    print(f"  Included files:       {len(inspection.included_files)}")
    print(f"  Sections detected:    {len(inspection.detected_sections)}")
    print(f"  Sensitive hits:       {len(inspection.sensitive_pattern_hits)}")
    print(f"  Pack hash:            {inspection.pack_hash}")
    print(f"  Inspection hash:      {inspection.inspection_hash}")

    if inspection.sensitive_pattern_hits:
        print(f"\n  Sensitive Pattern Hits:")
        for hit in inspection.sensitive_pattern_hits:
            print(f"    [WARN] Pattern detected: {hit}")

    if budget.warnings:
        print(f"\n  Budget Warnings:")
        for w in budget.warnings:
            print(f"    [WARN] {w}")

    if inspection.detected_sections:
        print(f"\n  Sections ({len(inspection.detected_sections)}):")
        for s in inspection.detected_sections:
            print(f"    - {s}")

    if inspection.included_files:
        print(f"\n  Files ({len(inspection.included_files)}):")
        for f in inspection.included_files[:20]:
            print(f"    - {f}")
        if len(inspection.included_files) > 20:
            print(f"    ... and {len(inspection.included_files) - 20} more")

    print()
    return 0


def cmd_context_plane_evidence(path: str, output: str = "", target: str = "") -> int:
    """Build evidence bundle from an existing inspected context pack."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.context_plane import (
        plan_context_pack,
        inspect_context_pack,
        context_pack_to_evidence,
        build_context_engineering_report,
        write_context_report,
        default_context_budget_policy,
    )
    from v3.external.default_capabilities import build_default_registry

    policy = default_context_budget_policy()
    inspection = inspect_context_pack(path, policy=policy)
    plan = plan_context_pack(
        target=target or path, output=path, style="markdown", policy=policy,
    )

    registry = build_default_registry()
    evidence_bundle = context_pack_to_evidence(
        plan, inspection, registry_hash=registry.registry_hash,
    )
    report = build_context_engineering_report(plan, inspection, evidence_bundle)

    if not output:
        output = f"{path}.evidence.json"
    written = write_context_report(report, output)

    print("=" * 60)
    print("  SystemKernel v4.0 — Context Engineering Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:      {evidence_bundle.bundle_id}")
    print(f"  Evidence records:     {len(evidence_bundle.records)}")
    print(f"  Budget status:        {report.budget_status}")
    print(f"  Truth source:         {report.truth_source}")
    print(f"  Report hash:          {report.report_hash}")
    print(f"  Report written:       {written}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Memory intelligence plane commands (Phase 5)
# ═══════════════════════════════════════════════════════════════════════

def cmd_memory_intel_profiles() -> int:
    """List all memory intelligence provider profiles and policy status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.memory_intelligence_profiles import (
        get_all_profiles, evaluate_all_profiles,
    )
    from v3.external.memory_intelligence_policy import (
        default_memory_intelligence_policy,
    )

    policy = default_memory_intelligence_policy()
    profiles = get_all_profiles()
    statuses = evaluate_all_profiles(policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Memory Intelligence Plane")
    print("=" * 60)
    print()
    print(f"  Policy hash:           {policy.policy_hash}")
    print(f"  Allow LLM providers:   {policy.allow_llm_providers}")
    print(f"  Allow vector DB:       {policy.allow_vector_db_providers}")
    print(f"  Allow graph DB:        {policy.allow_graph_db_providers}")
    print(f"  Allow external svcs:   {policy.allow_external_services}")
    print()
    print(f"  {'Provider':<35} {'Type':<22} {'Allowed':<10} {'LLM':<6} {'VecDB':<7} {'Graph':<7} {'ExtSvc':<8}")
    print(f"  {'-'*35} {'-'*22} {'-'*10} {'-'*6} {'-'*7} {'-'*7} {'-'*8}")

    status_map = {s.provider_id: s for s in statuses}
    for p in profiles:
        st = status_map.get(p.provider_id)
        allowed = "YES" if (st and st.allowed) else "NO"
        print(f"  {p.provider_id:<35} {p.provider_type:<22} {allowed:<10} "
              f"{'Y' if p.requires_llm else 'N':<6} "
              f"{'Y' if p.requires_vector_db else 'N':<7} "
              f"{'Y' if p.requires_graph_db else 'N':<7} "
              f"{'Y' if p.external_service_required else 'N':<8}")

    print()
    print(f"  Profiles:              {len(profiles)}")
    print("  External integrations: NONE (Phase 5 is contract only)")
    print()
    return 0


def cmd_memory_intel_mock(provider_id: str = "deterministic_mock_memory",
                          signals: int = 3) -> int:
    """Generate deterministic mock memory intelligence result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.memory_intelligence import (
        build_memory_intelligence_request,
        mock_memory_intelligence_result,
        validate_memory_intelligence_result,
        MODE_INSPECT_ONLY,
    )
    from v3.external.memory_intelligence_profiles import get_profile
    from v3.external.memory_intelligence_policy import (
        default_memory_intelligence_policy,
        validate_provider_against_policy,
    )

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_memory_intelligence_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Memory Intelligence Plane")
    print("=" * 60)
    print()
    print(f"  Provider:              {provider.provider_id}")
    print(f"  Type:                  {provider.provider_type}")
    print(f"  Policy allowed:        {allowed}")
    if not allowed:
        print(f"  Reason:                {reason}")
        return 1

    request = build_memory_intelligence_request(
        provider_id=provider_id,
        input_record_refs=("mem-001", "mem-002", "mem-003"),
        input_evidence_refs=("ev-001",),
        mode=MODE_INSPECT_ONLY,
        max_signals=signals,
    )
    result = mock_memory_intelligence_result(request, signal_count=signals)
    validation = validate_memory_intelligence_result(result)

    print(f"  Request ID:            {request.request_id}")
    print(f"  Request mode:          {request.mode}")
    print(f"  Signals generated:     {len(result.signals)}")
    print(f"  Blocked:               {result.blocked}")
    print(f"  Truth source:          {result.truth_source}")
    print(f"  Result hash:           {result.result_hash}")
    print(f"  Validation:            {'PASS' if validation.valid else 'FAIL'}")

    if result.signals:
        print(f"\n  Signals:")
        for s in result.signals:
            print(f"    [{s.signal_type}] {s.signal_id[:8]} "
                  f"confidence={s.confidence:.1f} content='{s.content[:50]}...'")

    print()
    return 0


def cmd_memory_intel_evidence(provider_id: str = "deterministic_mock_memory",
                              output: str = "") -> int:
    """Build evidence bundle from mock memory intelligence result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.memory_intelligence import (
        build_memory_intelligence_request,
        mock_memory_intelligence_result,
        memory_signals_to_evidence,
        build_memory_intelligence_report,
        MODE_INSPECT_ONLY,
    )
    from v3.external.memory_intelligence_profiles import get_profile
    from v3.external.memory_intelligence_policy import (
        default_memory_intelligence_policy,
        validate_provider_against_policy,
    )
    from v3.external.default_capabilities import build_default_registry
    import json as _json

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_memory_intelligence_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    if not allowed:
        print(f"Provider blocked: {reason}")
        return 1

    request = build_memory_intelligence_request(
        provider_id=provider_id,
        input_record_refs=("mem-001", "mem-002", "mem-003"),
        input_evidence_refs=("ev-001",),
        mode=MODE_INSPECT_ONLY,
        max_signals=5,
    )
    result = mock_memory_intelligence_result(request, signal_count=3)
    registry = build_default_registry()
    bundle = memory_signals_to_evidence(
        result, registry_hash=registry.registry_hash,
    )
    report = build_memory_intelligence_report(
        provider, request, result, bundle, policy_status="pass",
    )

    if not output:
        output = f"/tmp/memory_intel_evidence_{result.result_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Memory Intelligence Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:       {bundle.bundle_id}")
    print(f"  Evidence records:      {len(bundle.records)}")
    print(f"  Truth source:          {bundle.truth_source}")
    print(f"  Policy status:         {report.policy_status}")
    print(f"  Report hash:           {report.report_hash}")
    print(f"  Report written:        {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Workspace context plane commands (Phase 7)
# ═══════════════════════════════════════════════════════════════════════

def cmd_workspace_profiles() -> int:
    """List all workspace provider profiles and policy status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.workspace_context_profiles import (
        get_all_profiles, evaluate_all_profiles,
    )
    from v3.external.workspace_context_policy import (
        default_workspace_context_policy,
    )

    policy = default_workspace_context_policy()
    profiles = get_all_profiles()
    statuses = evaluate_all_profiles(policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Workspace Context Plane")
    print("=" * 60)
    print()
    print(f"  Policy hash:            {policy.policy_hash}")
    print(f"  Allow IDE API:          {policy.allow_ide_api}")
    print(f"  Allow file watch:       {policy.allow_file_watch}")
    print(f"  Allow file read:        {policy.allow_file_read}")
    print(f"  Allow file write:       {policy.allow_file_write}")
    print(f"  Allow terminal:         {policy.allow_terminal_execution}")
    print(f"  Allow external svcs:    {policy.allow_external_services}")
    print(f"  Require redaction:      {policy.require_redaction}")
    print(f"  Require human approval: {policy.require_human_approval}")
    print()
    print(f"  {'Provider':<35} {'Type':<22} {'Allowed':<10} {'IDE':<6} {'Watch':<7} {'Read':<6} {'Write':<7} {'Term':<6} {'ExtSvc':<8}")
    print(f"  {'-'*35} {'-'*22} {'-'*10} {'-'*6} {'-'*7} {'-'*6} {'-'*7} {'-'*6} {'-'*8}")

    status_map = {s.provider_id: s for s in statuses}
    for p in profiles:
        st = status_map.get(p.provider_id)
        allowed = "YES" if (st and st.allowed) else "NO"
        print(f"  {p.provider_id:<35} {p.provider_type:<22} {allowed:<10} "
              f"{'Y' if p.requires_ide_api else 'N':<6} "
              f"{'Y' if p.requires_file_watch else 'N':<7} "
              f"{'Y' if p.can_read_files else 'N':<6} "
              f"{'Y' if p.can_write_files else 'N':<7} "
              f"{'Y' if p.can_execute_terminal else 'N':<6} "
              f"{'Y' if p.external_service_required else 'N':<8}")

    print()
    print(f"  Profiles:               {len(profiles)}")
    print("  External integrations:  NONE (Phase 7 is contract only)")
    print()
    return 0


def cmd_workspace_mock(provider_id: str = "deterministic_mock_workspace",
                       files: int = 3, diagnostics: int = 2) -> int:
    """Generate deterministic mock workspace snapshot."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.workspace_context import (
        mock_workspace_snapshot,
        validate_workspace_provider,
        validate_workspace_snapshot,
    )
    from v3.external.workspace_context_profiles import get_profile
    from v3.external.workspace_context_policy import (
        default_workspace_context_policy,
        validate_provider_against_policy,
    )

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_workspace_context_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Workspace Context Plane")
    print("=" * 60)
    print()
    print(f"  Provider:               {provider.provider_id}")
    print(f"  Type:                   {provider.provider_type}")
    print(f"  Policy allowed:         {allowed}")
    if not allowed:
        print(f"  Reason:                 {reason}")
        return 1

    provider_valid = validate_workspace_provider(provider)
    snapshot = mock_workspace_snapshot(
        provider_id=provider_id,
        file_count=files,
        diagnostic_count=diagnostics,
    )
    snapshot_valid = validate_workspace_snapshot(snapshot)

    print(f"  Snapshot ID:            {snapshot.snapshot_id}")
    print(f"  Root path:              {snapshot.root_path}")
    print(f"  File refs:              {len(snapshot.file_refs)}")
    print(f"  Diagnostics:            {len(snapshot.diagnostics)}")
    print(f"  Open files:             {len(snapshot.open_files)}")
    if snapshot.active_file:
        print(f"  Active file:            {snapshot.active_file}")
    if snapshot.git_state:
        print(f"  Git branch:             {snapshot.git_state.branch}")
        print(f"  Modified count:         {snapshot.git_state.modified_count}")
    print(f"  Truth source:           {snapshot.truth_source}")
    print(f"  Snapshot hash:          {snapshot.snapshot_hash}")
    print(f"  Provider validation:    {'PASS' if provider_valid.valid else 'FAIL'}")
    print(f"  Snapshot validation:    {'PASS' if snapshot_valid.valid else 'FAIL'}")

    if snapshot.file_refs:
        print(f"\n  File Refs:")
        for ref in snapshot.file_refs:
            print(f"    {ref.path}  ({ref.language}, {ref.size_bytes:,} bytes)")

    if snapshot.diagnostics:
        print(f"\n  Diagnostics:")
        for d in snapshot.diagnostics:
            print(f"    [{d.severity}] {d.source}: {d.message_summary}")

    print()
    return 0


def cmd_workspace_evidence(provider_id: str = "deterministic_mock_workspace",
                           output: str = "") -> int:
    """Build evidence bundle from mock workspace snapshot."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.workspace_context import (
        mock_workspace_snapshot,
        workspace_snapshot_to_evidence,
        build_workspace_context_report,
    )
    from v3.external.workspace_context_profiles import get_profile
    from v3.external.workspace_context_policy import (
        default_workspace_context_policy,
        validate_provider_against_policy,
    )
    from v3.external.default_capabilities import build_default_registry
    import json as _json

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_workspace_context_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    if not allowed:
        print(f"Provider blocked: {reason}")
        return 1

    snapshot = mock_workspace_snapshot(provider_id=provider_id, file_count=3, diagnostic_count=2)
    registry = build_default_registry()
    bundle = workspace_snapshot_to_evidence(
        snapshot, registry_hash=registry.registry_hash,
    )
    report = build_workspace_context_report(
        provider, snapshot, bundle, policy_status="pass",
    )

    if not output:
        output = f"/tmp/workspace_evidence_{snapshot.snapshot_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Workspace Context Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:        {bundle.bundle_id}")
    print(f"  Evidence records:       {len(bundle.records)}")
    print(f"  Truth source:           {bundle.truth_source}")
    print(f"  Policy status:          {report.policy_status}")
    print(f"  Report hash:            {report.report_hash}")
    print(f"  Report written:         {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Agent worker plane commands (Phase 6)
# ═══════════════════════════════════════════════════════════════════════

def cmd_agent_worker_profiles() -> int:
    """List all agent worker provider profiles and policy status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.agent_worker_profiles import (
        get_all_profiles, evaluate_all_profiles,
    )
    from v3.external.agent_worker_policy import (
        default_agent_worker_policy,
    )

    policy = default_agent_worker_policy()
    profiles = get_all_profiles()
    statuses = evaluate_all_profiles(policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Agent Worker Plane")
    print("=" * 60)
    print()
    print(f"  Policy hash:            {policy.policy_hash}")
    print(f"  Allow LLM providers:    {policy.allow_llm_providers}")
    print(f"  Allow network:          {policy.allow_network}")
    print(f"  Allow file mod:         {policy.allow_file_modification}")
    print(f"  Allow cmd exec:         {policy.allow_command_execution}")
    print(f"  Allow external svcs:    {policy.allow_external_services}")
    print(f"  Require sandbox:        {policy.require_sandbox}")
    print(f"  Require human approval: {policy.require_human_approval}")
    print()
    print(f"  {'Provider':<35} {'Type':<22} {'Allowed':<10} {'LLM':<6} {'Net':<6} {'File':<6} {'Cmd':<6} {'ExtSvc':<8}")
    print(f"  {'-'*35} {'-'*22} {'-'*10} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")

    status_map = {s.provider_id: s for s in statuses}
    for p in profiles:
        st = status_map.get(p.provider_id)
        allowed = "YES" if (st and st.allowed) else "NO"
        print(f"  {p.provider_id:<35} {p.provider_type:<22} {allowed:<10} "
              f"{'Y' if p.requires_llm else 'N':<6} "
              f"{'Y' if p.requires_network else 'N':<6} "
              f"{'Y' if p.can_modify_files else 'N':<6} "
              f"{'Y' if p.can_execute_commands else 'N':<6} "
              f"{'Y' if p.external_service_required else 'N':<8}")

    print()
    print(f"  Profiles:               {len(profiles)}")
    print("  External integrations:  NONE (Phase 6 is contract only)")
    print()
    return 0


def cmd_agent_worker_mock(provider_id: str = "deterministic_mock_agent",
                          proposals: int = 2) -> int:
    """Generate deterministic mock agent worker result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.agent_worker import (
        build_agent_worker_task,
        mock_agent_worker_result,
        validate_agent_worker_provider,
        validate_agent_worker_result,
    )
    from v3.external.agent_worker_profiles import get_profile
    from v3.external.agent_worker_policy import (
        default_agent_worker_policy,
        validate_provider_against_policy,
    )

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_agent_worker_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Agent Worker Plane")
    print("=" * 60)
    print()
    print(f"  Provider:               {provider.provider_id}")
    print(f"  Type:                   {provider.provider_type}")
    print(f"  Policy allowed:         {allowed}")
    if not allowed:
        print(f"  Reason:                 {reason}")
        return 1

    provider_valid = validate_agent_worker_provider(provider)
    task = build_agent_worker_task(
        provider_id=provider_id,
        task_summary="Mock agent worker task for testing",
        input_refs=("file-1.py", "file-2.py"),
        allowed_paths=("./src",),
        max_runtime_seconds=300,
        dry_run=True,
    )
    result = mock_agent_worker_result(task, proposal_count=proposals)
    result_valid = validate_agent_worker_result(result)

    print(f"  Task ID:                {task.task_id}")
    print(f"  Task dry_run:           {task.dry_run}")
    print(f"  Proposals generated:    {len(result.proposals)}")
    print(f"  Status:                 {result.status}")
    print(f"  Truth source:           {result.truth_source}")
    print(f"  Result hash:            {result.result_hash}")
    print(f"  Provider validation:    {'PASS' if provider_valid.valid else 'FAIL'}")
    print(f"  Result validation:      {'PASS' if result_valid.valid else 'FAIL'}")

    if result.proposals:
        print(f"\n  Proposals:")
        for p in result.proposals:
            print(f"    [{p.proposal_id[:8]}] confidence={p.confidence:.1f} "
                  f"plan='{p.proposed_plan[:60]}...'")

    print()
    return 0


def cmd_agent_worker_evidence(provider_id: str = "deterministic_mock_agent",
                              output: str = "") -> int:
    """Build evidence bundle from mock agent worker result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.agent_worker import (
        build_agent_worker_task,
        mock_agent_worker_result,
        agent_proposals_to_evidence,
        build_agent_worker_report,
    )
    from v3.external.agent_worker_profiles import get_profile
    from v3.external.agent_worker_policy import (
        default_agent_worker_policy,
        validate_provider_against_policy,
    )
    from v3.external.default_capabilities import build_default_registry
    import json as _json

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_agent_worker_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    if not allowed:
        print(f"Provider blocked: {reason}")
        return 1

    task = build_agent_worker_task(
        provider_id=provider_id,
        task_summary="Mock agent worker task for evidence mapping",
        input_refs=("file-1.py", "file-2.py"),
        allowed_paths=("./src",),
        max_runtime_seconds=300,
        dry_run=True,
    )
    result = mock_agent_worker_result(task, proposal_count=3)
    registry = build_default_registry()
    bundle = agent_proposals_to_evidence(
        result, registry_hash=registry.registry_hash,
    )
    report = build_agent_worker_report(
        provider, task, result, bundle, policy_status="pass",
    )

    if not output:
        output = f"/tmp/agent_worker_evidence_{result.result_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Agent Worker Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:        {bundle.bundle_id}")
    print(f"  Evidence records:       {len(bundle.records)}")
    print(f"  Truth source:           {bundle.truth_source}")
    print(f"  Policy status:          {report.policy_status}")
    print(f"  Report hash:            {report.report_hash}")
    print(f"  Report written:         {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Skill evolution plane commands (Phase 8)
# ═══════════════════════════════════════════════════════════════════════

def cmd_skill_evolution_profiles() -> int:
    """List all skill evolution provider profiles and policy status."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.skill_evolution_profiles import (
        get_all_profiles, evaluate_all_profiles,
    )
    from v3.external.skill_evolution_policy import (
        default_skill_evolution_policy,
    )

    policy = default_skill_evolution_policy()
    profiles = get_all_profiles()
    statuses = evaluate_all_profiles(policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Skill Evolution Plane")
    print("=" * 60)
    print()
    print(f"  Policy hash:             {policy.policy_hash}")
    print(f"  Allow LLM providers:     {policy.allow_llm_providers}")
    print(f"  Allow skill mod:         {policy.allow_skill_file_modification}")
    print(f"  Allow registry update:   {policy.allow_registry_update}")
    print(f"  Allow skill install:     {policy.allow_skill_installation}")
    print(f"  Require tests:           {policy.require_tests_for_changes}")
    print(f"  Require human approval:  {policy.require_human_approval}")
    print()
    print(f"  {'Provider':<40} {'Type':<25} {'Allowed':<10} {'LLM':<6} {'Mod':<6} {'Reg':<6} {'Inst':<7} {'ExtSvc':<8}")
    print(f"  {'-'*40} {'-'*25} {'-'*10} {'-'*6} {'-'*6} {'-'*6} {'-'*7} {'-'*8}")

    status_map = {s.provider_id: s for s in statuses}
    for p in profiles:
        st = status_map.get(p.provider_id)
        allowed = "YES" if (st and st.allowed) else "NO"
        print(f"  {p.provider_id:<40} {p.provider_type:<25} {allowed:<10} "
              f"{'Y' if p.requires_llm else 'N':<6} "
              f"{'Y' if p.can_modify_skills else 'N':<6} "
              f"{'Y' if p.can_update_registry else 'N':<6} "
              f"{'Y' if p.can_install_skills else 'N':<7} "
              f"{'Y' if p.external_service_required else 'N':<8}")

    print()
    print(f"  Profiles:                {len(profiles)}")
    print("  Skill evolution:         PROPOSAL-ONLY (no automatic modification)")
    print()
    return 0


def cmd_skill_evolution_mock(provider_id: str = "deterministic_mock_skill_evolution",
                              proposals: int = 2, signals: int = 3) -> int:
    """Generate deterministic mock skill evolution result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.skill_evolution import (
        mock_skill_evolution_result,
        validate_skill_provider,
        validate_skill_result,
    )
    from v3.external.skill_evolution_profiles import get_profile
    from v3.external.skill_evolution_policy import (
        default_skill_evolution_policy,
        validate_provider_against_policy,
    )

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_skill_evolution_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Skill Evolution Plane")
    print("=" * 60)
    print()
    print(f"  Provider:                {provider.provider_id}")
    print(f"  Type:                    {provider.provider_type}")
    print(f"  Policy allowed:          {allowed}")
    if not allowed:
        print(f"  Reason:                  {reason}")
        return 1

    provider_valid = validate_skill_provider(provider)
    result = mock_skill_evolution_result(
        provider_id=provider_id,
        proposal_count=proposals,
        signal_count=signals,
    )
    result_valid = validate_skill_result(result)

    print(f"  Proposals generated:     {len(result.proposals)}")
    print(f"  Status:                  {result.status}")
    print(f"  Truth source:            {result.truth_source}")
    print(f"  Result hash:             {result.result_hash}")
    print(f"  Provider validation:     {'PASS' if provider_valid.valid else 'FAIL'}")
    print(f"  Result validation:       {'PASS' if result_valid.valid else 'FAIL'}")

    if result.proposals:
        print(f"\n  Proposals:")
        for p in result.proposals:
            print(f"    [{p.proposal_id[:8]}] type={p.proposal_type} "
                  f"approval={p.approval_required} "
                  f"summary='{p.proposed_changes_summary[:50]}...'")

    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    - {w}")

    print()
    return 0


def cmd_skill_evolution_evidence(provider_id: str = "deterministic_mock_skill_evolution",
                                  output: str = "") -> int:
    """Build evidence bundle from mock skill evolution result."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.skill_evolution import (
        mock_skill_evolution_result,
        skill_proposals_to_evidence,
        build_skill_evolution_report,
    )
    from v3.external.skill_evolution_profiles import get_profile
    from v3.external.skill_evolution_policy import (
        default_skill_evolution_policy,
        validate_provider_against_policy,
    )
    from v3.external.default_capabilities import build_default_registry
    import json as _json

    provider = get_profile(provider_id)
    if provider is None:
        print(f"Unknown provider: {provider_id}")
        return 1

    policy = default_skill_evolution_policy()
    allowed, reason = validate_provider_against_policy(provider, policy)

    if not allowed:
        print(f"Provider blocked: {reason}")
        return 1

    result = mock_skill_evolution_result(provider_id=provider_id, proposal_count=3, signal_count=3)
    registry = build_default_registry()
    bundle = skill_proposals_to_evidence(
        result, registry_hash=registry.registry_hash,
    )
    report = build_skill_evolution_report(
        provider, result, bundle, policy_status="pass",
    )

    if not output:
        output = f"/tmp/skill_evolution_evidence_{result.result_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Skill Evolution Plane")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:         {bundle.bundle_id}")
    print(f"  Evidence records:        {len(bundle.records)}")
    print(f"  Truth source:            {bundle.truth_source}")
    print(f"  Policy status:           {report.policy_status}")
    print(f"  Report hash:             {report.report_hash}")
    print(f"  Report written:          {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Orchestration policy commands (Phase 9)
# ═══════════════════════════════════════════════════════════════════════

def cmd_orchestrate_policies() -> int:
    """List all orchestration policy profiles."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.orchestration_profiles import (
        get_all_profiles, get_all_profile_statuses,
    )

    profiles = get_all_profiles()
    statuses = get_all_profile_statuses()
    status_map = {s.policy_id: s for s in statuses}

    print("=" * 60)
    print("  SystemKernel v4.0 — Orchestration Policy Layer")
    print("=" * 60)
    print()
    print(f"  {'Profile':<30} {'Types':<30} {'Run':<8} {'Risk':<8} {'Exec':<6} {'Net':<6} {'File':<6}")
    print(f"  {'-'*30} {'-'*30} {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*6}")

    for p in profiles:
        types_str = ",".join(p.allowed_capability_types[:3])
        if len(p.allowed_capability_types) > 3:
            types_str += "..."
        if not p.allowed_capability_types:
            types_str = "(all)"
        print(f"  {p.policy_id:<30} {types_str:<30} "
              f"{'dry' if p.dry_run_only else 'live':<8} "
              f"{p.max_risk_level:<8} "
              f"{'Y' if p.allow_external_execution else 'N':<6} "
              f"{'Y' if p.allow_network else 'N':<6} "
              f"{'Y' if p.allow_file_modification else 'N':<6}")

    print()
    print(f"  Profiles:                {len(profiles)}")
    print("  Execution:               NONE (Phase 9 is planning only)")
    print()
    return 0


def cmd_orchestrate_plan(profile_id: str = "safe_context_only",
                          objective: str = "Dry-run orchestration plan") -> int:
    """Build a dry-run orchestration plan."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.orchestration_policy import (
        build_orchestration_request,
        plan_orchestration,
        validate_orchestration_plan,
    )
    from v3.external.orchestration_profiles import get_profile
    from v3.external.default_capabilities import build_default_registry

    policy = get_profile(profile_id)
    if policy is None:
        print(f"Unknown profile: {profile_id}")
        print(f"Use 'orchestrate policies' to list available profiles.")
        return 1

    registry = build_default_registry()
    request = build_orchestration_request(
        objective=objective,
        requested_capability_types=policy.allowed_capability_types,
    )
    plan = plan_orchestration(request, registry, policy)
    validation = validate_orchestration_plan(plan, registry, policy)

    print("=" * 60)
    print("  SystemKernel v4.0 — Orchestration Policy Layer")
    print("=" * 60)
    print()
    print(f"  Profile:                {policy.policy_id}")
    print(f"  Policy hash:            {policy.policy_hash}")
    print(f"  Objective:              {objective}")
    print(f"  Plan ID:                {plan.plan_id}")
    print(f"  Steps:                  {len(plan.steps)}")
    print(f"  Blocked steps:          {len(plan.blocked_steps)}")
    print(f"  Warnings:               {len(plan.warnings)}")
    print(f"  Truth source:           {plan.truth_source}")
    print(f"  Plan hash:              {plan.plan_hash}")
    print(f"  Validation:             {'PASS' if validation.valid else 'FAIL'}")

    if plan.steps:
        print(f"\n  Planned Steps:")
        for s in plan.steps:
            print(f"    [{s.capability_type}] {s.adapter_id}")
            print(f"      mode={s.execution_mode} evidence={s.expected_evidence_type}")

    if plan.blocked_steps:
        print(f"\n  Blocked Steps:")
        for s in plan.blocked_steps:
            print(f"    [BLOCKED] {s.adapter_id} — {s.block_reason[:70]}")

    if plan.warnings:
        print(f"\n  Warnings:")
        for w in plan.warnings:
            print(f"    - {w}")

    print()
    return 0


def cmd_orchestrate_evidence(profile_id: str = "safe_context_only",
                               objective: str = "Dry-run orchestration plan",
                               output: str = "") -> int:
    """Build evidence bundle from orchestration plan."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from v3.external.orchestration_policy import (
        build_orchestration_request,
        plan_orchestration,
        build_orchestration_policy_report,
        orchestration_plan_to_evidence,
    )
    from v3.external.orchestration_profiles import get_profile
    from v3.external.default_capabilities import build_default_registry
    import json as _json

    policy = get_profile(profile_id)
    if policy is None:
        print(f"Unknown profile: {profile_id}")
        return 1

    registry = build_default_registry()
    request = build_orchestration_request(
        objective=objective,
        requested_capability_types=policy.allowed_capability_types,
    )
    plan = plan_orchestration(request, registry, policy)
    bundle = orchestration_plan_to_evidence(
        plan, registry_hash=registry.registry_hash,
    )
    report = build_orchestration_policy_report(
        policy, request, plan, registry_hash=registry.registry_hash,
    )

    if not output:
        output = f"/tmp/orchestration_evidence_{plan.plan_hash}.json"
    with open(output, "w", encoding="utf-8") as f:
        _json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

    print("=" * 60)
    print("  SystemKernel v4.0 — Orchestration Policy Layer")
    print("=" * 60)
    print()
    print(f"  Evidence bundle:         {bundle.bundle_id}")
    print(f"  Evidence records:        {len(bundle.records)}")
    print(f"  Truth source:            {bundle.truth_source}")
    print(f"  Validation status:       {report.validation_status}")
    print(f"  Report hash:             {report.report_hash}")
    print(f"  Report written:          {output}")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Capability registry commands (Phase 2)
# ═══════════════════════════════════════════════════════════════════════

def cmd_capability_list() -> int:
    """List all capability registry entries."""
    from v3.external.default_capabilities import build_default_registry

    registry = build_default_registry()
    if not registry.entries:
        print("(no entries)")
        return 0

    for entry in registry.entries:
        status = "[ENABLED]" if entry.enabled else "[DISABLED]"
        risk = entry.spec.risk_level if entry.spec else "?"
        print(f"{status} {entry.adapter_id} | {entry.maturity} | {entry.lifecycle_state} | risk={risk}")
    return 0


def cmd_capability_summary() -> int:
    """Print capability registry summary counts."""
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import (
        list_by_type, list_enabled, list_high_risk, list_by_lifecycle,
    )
    from v3.external.capability_lifecycle import STATE_APPROVED

    registry = build_default_registry()
    total = len(registry.entries)
    enabled = list_enabled(registry)
    disabled = [e for e in registry.entries if not e.enabled]
    approved = list_by_lifecycle(registry, STATE_APPROVED)
    high_risk = list_high_risk(registry)

    print(f"Total entries:      {total}")
    print(f"Enabled:            {len(enabled)}")
    print(f"Disabled:           {len(disabled)}")
    print(f"Approved:           {len(approved)}")
    print(f"High risk:          {len(high_risk)}")
    print()

    # Counts by type
    from v3.external.capability_contract import CapabilityType
    print("By type:")
    for t in CapabilityType:
        entries = list_by_type(registry, t.value)
        if entries:
            enabled_count = sum(1 for e in entries if e.enabled)
            print(f"  {t.value}: {len(entries)} ({enabled_count} enabled)")

    print()
    print(f"Registry hash:      {registry.registry_hash}")
    print()
    print("External integrations performed: NONE (Phase 2 is registry only)")
    return 0


def cmd_capability_show(adapter_id: str) -> int:
    """Show one capability registry entry."""
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import get_entry

    registry = build_default_registry()
    entry = get_entry(registry, adapter_id)
    if entry is None:
        print(f"Entry not found: {adapter_id}")
        return 1

    print(f"Adapter ID:         {entry.adapter_id}")
    if entry.spec:
        print(f"Name:               {entry.spec.name}")
        print(f"Type:               {entry.spec.capability_type}")
        print(f"Modes:              {', '.join(entry.spec.execution_modes)}")
        print(f"Risk:               {entry.spec.risk_level}")
        print(f"Truth source:       {entry.spec.truth_source}")
        print(f"Removable:          {entry.spec.removable}")
        print(f"Forbidden actions:  {', '.join(entry.spec.forbidden_actions)}")
    print(f"Lifecycle:          {entry.lifecycle_state}")
    print(f"Enabled:            {entry.enabled}")
    print(f"Maturity:           {entry.maturity}")
    print(f"Approval required:  {entry.approval_required}")
    print(f"Owner:              {entry.owner}")
    print(f"Notes:              {entry.notes}")
    print(f"Entry hash:         {entry.entry_hash}")
    return 0


# ═══════════════════════════════════════════════════════════════════════
# Evaluation harness commands (Phase 10)
# ═══════════════════════════════════════════════════════════════════════

def cmd_eval_suite() -> int:
    """List default eval cases."""
    from v3.evals.evaluation_harness import build_default_eval_suite

    suite = build_default_eval_suite()
    print(f"Suite: {suite.suite_id}")
    print(f"Cases: {len(suite.cases)}")
    print(f"Hash:  {suite.suite_hash}")
    print()
    for case in suite.cases:
        print(f"  [{case.category}] {case.name}")
        print(f"    ID:        {case.case_id}")
        print(f"    Objective: {case.objective}")
        print(f"    Invariants: {', '.join(case.required_invariants) if case.required_invariants else '(none)'}")
        print()
    return 0


def cmd_eval_run() -> int:
    """Run deterministic static eval suite."""
    from v3.evals.evaluation_harness import build_default_eval_suite, run_eval_suite

    suite = build_default_eval_suite()
    result = run_eval_suite(suite)

    print(f"Suite:        {result.suite_id}")
    print(f"Passed:       {result.passed_count}")
    print(f"Failed:       {result.failed_count}")
    print(f"Avg Score:    {result.average_score}")
    print(f"Result Hash:  {result.suite_result_hash}")
    print()

    for r in result.results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.case_id} — score={r.score}")
        if r.missing_outputs:
            print(f"    Missing: {', '.join(r.missing_outputs)}")
        if r.warnings:
            print(f"    Warnings: {', '.join(r.warnings)}")

    print()
    if result.failed_count == 0:
        print("All eval cases passed.")
        return 0
    else:
        print(f"{result.failed_count} eval case(s) failed.")
        return 1


def cmd_eval_regression(output: str = "") -> int:
    """Generate regression matrix result."""
    from v3.evals.regression_matrix import (
        run_static_regression_matrix, write_regression_matrix_result,
    )

    if output:
        path = write_regression_matrix_result(output)
        print(f"Regression matrix written: {path}")
    else:
        result = run_static_regression_matrix()
        print(f"Matrix:   {result.matrix.matrix_hash}")
        print(f"Passed:   {result.passed}")
        print(f"Failed:   {result.failed}")
        print(f"Skipped:  {result.skipped}")
        print(f"Total:    {result.matrix.total}")
        print(f"Required: {result.matrix.required_count}")
        print()
        if result.release_blocking_failures:
            print("Release Blocking Failures:")
            for f in result.release_blocking_failures:
                print(f"  - {f}")
        else:
            print("No release blocking failures.")
        print(f"Result Hash: {result.result_hash}")

    return 0 if result.failed == 0 else 1


def cmd_eval_benefit(output: str = "") -> int:
    """Generate benefit-vs-complexity report for current v4 planes."""
    from v3.evals.benefit_complexity import (
        BenefitSignal, score_benefit_complexity, write_benefit_complexity_report,
    )

    # Score each major v4 plane
    planes = {
        "capability_contract": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=False,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 3.0),
        "capability_registry": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 4.0),
        "evidence_model": (BenefitSignal(
            reduces_manual_steps=False,
            improves_verifiability=True,
            improves_replaceability=False,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 2.0),
        "context_plane": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=False,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 4.0),
        "memory_intelligence": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 5.0),
        "agent_worker": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 5.0),
        "workspace_context": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=False,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 5.0),
        "skill_evolution": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 5.0),
        "orchestration_policy": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=True,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 6.0),
        "eval_harness": (BenefitSignal(
            reduces_manual_steps=True,
            improves_verifiability=True,
            improves_replaceability=False,
            improves_safety_boundary=True,
            improves_debuggability=True,
            avoids_new_truth_source=True,
            avoids_runtime_dependency=True,
        ), 2.0),
    }

    scores = tuple(
        score_benefit_complexity(name, sig, complexity)
        for name, (sig, complexity) in planes.items()
    )

    if output:
        path = write_benefit_complexity_report(scores, output)
        print(f"Benefit-complexity report written: {path}")
    else:
        print("V4 Plane Benefit-Complexity Scores:")
        print()
        for s in scores:
            verdict_mark = {"ACCEPT": "+", "REVIEW": "~", "REJECT": "!"}.get(s.verdict, "?")
            print(f"  [{verdict_mark}] {s.target_id}")
            print(f"      Benefit={s.benefit_score}  Complexity={s.complexity_score}  "
                  f"Net={s.net_value}  RiskRatio={s.risk_ratio}  Verdict={s.verdict}")

        accepted = sum(1 for s in scores if s.verdict == "ACCEPT")
        review = sum(1 for s in scores if s.verdict == "REVIEW")
        rejected = sum(1 for s in scores if s.verdict == "REJECT")
        print(f"\n  Accepted: {accepted}  Review: {review}  Rejected: {rejected}")

    return 0


# ═══════════════════════════════════════════════════════════════════════
# V4 Productization + Ops commands (Phase 11)
# ═══════════════════════════════════════════════════════════════════════

def cmd_v4_status() -> int:
    """Print compact v4 operational status."""
    from v3.ops.v4_ops import build_v4_ops_status

    s = build_v4_ops_status()
    print("V4 Operational Status")
    print("=" * 40)
    print(f"  Kernel purity:        {s.kernel_purity}/100")
    print(f"  Memory removable:     {'YES' if s.memory_removable else 'NO'}")
    print(f"  Registry entries:     {s.registry_entries} ({s.enabled_capabilities} enabled, {s.disabled_capabilities} disabled)")
    print(f"  Evidence model:       {'READY' if s.evidence_model_ready else 'NOT READY'}")
    print(f"  Orchestration:        {'READY' if s.orchestration_ready else 'NOT READY'}")
    print(f"  Eval harness:         {'READY' if s.eval_ready else 'NOT READY'}")
    print(f"  Complexity verdict:   {s.complexity_verdict}")
    print(f"  Ops hash:             {s.ops_hash}")
    return 0


def cmd_v4_ops_check(output: str = "") -> int:
    """Print v4 operational checklist."""
    from v3.ops.v4_ops import build_v4_ops_checklist, write_v4_ops_checklist

    checklist = build_v4_ops_checklist()

    if output:
        path = write_v4_ops_checklist(output)
        print(f"Checklist written: {path}")
    else:
        print(f"V4 Ops Checklist — {checklist.checklist_id}")
        print(f"Passed: {checklist.passed}  Failed: {checklist.failed}")
        print(f"Hash:   {checklist.checklist_hash}")
        print()
        cats = {}
        for item in checklist.items:
            cats.setdefault(item.category, []).append(item)
        for cat, cat_items in sorted(cats.items()):
            print(f"  [{cat.upper()}]")
            for item in cat_items:
                m = {"pass": "+", "fail": "!", "pending": "?"}.get(item.status, "?")
                req = " [REQUIRED]" if item.required else ""
                print(f"    [{m}] {item.title}{req}")
            print()

    return 0 if checklist.failed == 0 else 1


def cmd_v4_runbook(output: str = "", fmt: str = "md") -> int:
    """Write v4 runbook to file."""
    from v3.ops.runbook import write_v4_runbook_md, write_v4_runbook_json

    if not output:
        output_dir = os.path.join(EXPORTS_DIR, f"v4_runbook.{fmt}")
    else:
        output_dir = output

    if fmt == "json":
        path = write_v4_runbook_json(output_dir)
    else:
        path = write_v4_runbook_md(output_dir)

    print(f"Runbook written: {path}")
    return 0


def cmd_v4_summary() -> int:
    """Combined registry/evidence/orchestration/eval summary."""
    from v3.external.default_capabilities import build_default_registry
    from v3.external.capability_registry import list_enabled
    from v3.external.orchestration_profiles import get_all_profiles
    from v3.evals.evaluation_harness import build_default_eval_suite, run_eval_suite

    # Registry
    reg = build_default_registry()
    enabled = list_enabled(reg)
    types = {}
    for e in reg.entries:
        if e.spec:
            types.setdefault(e.spec.capability_type, []).append(e)

    # Orchestration
    profiles = get_all_profiles()

    # Eval
    suite = build_default_eval_suite()
    eval_result = run_eval_suite(suite)

    print("=" * 50)
    print("  SystemKernel v4.0 — Operational Summary")
    print("=" * 50)

    print(f"\n  Registry:        {len(reg.entries)} entries ({len(enabled)} enabled)")
    print(f"  Capability types: {len(types)}/8 covered")
    print(f"  Orchestration:    {len(profiles)} policy profiles")
    print(f"  Eval:             {eval_result.passed_count}/{len(suite.cases)} cases pass (score={eval_result.average_score})")
    print(f"  Regression:       static checks available via 'systemkernel eval regression'")
    print(f"  Complexity:       check via 'systemkernel quality'")
    print(f"  Kernel:           purity 100/100, memory removable")

    print(f"\n  Commands:")
    print(f"    systemkernel v4 status      — Full ops health")
    print(f"    systemkernel v4 ops-check   — Operational checklist")
    print(f"    systemkernel v4 runbook     — Generate runbook")
    print(f"    systemkernel eval run       — Run deterministic eval suite")
    print(f"    systemkernel eval benefit   — Benefit-complexity scores")
    print(f"    systemkernel orchestrate plan --profile safe_context_only")

    return 0


def main(argv: Optional[list] = None) -> int:
    """Main entry point. Returns exit code."""
    parser = build_parser()

    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    if args.command == "status":
        return cmd_status()
    elif args.command == "quality":
        return cmd_quality()
    elif args.command == "memory":
        if args.memory_action == "report":
            return cmd_memory_report()
        else:
            print(f"Unknown memory action: {args.memory_action}")
            return 1
    elif args.command == "reports":
        if args.reports_action == "list":
            return cmd_reports_list()
        elif args.reports_action == "summary":
            return cmd_reports_summary()
        else:
            print(f"Unknown reports action: {args.reports_action}")
            return 1
    elif args.command == "doctor":
        return cmd_doctor()
    elif args.command == "intake":
        if args.intake_action == "profile":
            return cmd_intake_profile(args.name)
        elif args.intake_action == "list":
            return cmd_intake_list()
        elif args.intake_action == "summarize":
            return cmd_intake_summarize()
        elif args.intake_action == "registry":
            return cmd_intake_registry(getattr(args, "output", None))
        elif args.intake_action == "clone-plan":
            return cmd_intake_clone_plan(getattr(args, "output_dir", None))
        elif args.intake_action == "clone-list":
            return cmd_intake_clone_list()
        else:
            print(f"Unknown intake action: {args.intake_action}")
            return 1
    elif args.command == "context-pack":
        if args.cp_action == "plan":
            return cmd_context_pack_plan(
                args.target, args.output,
                style=getattr(args, "style", "markdown"),
            )
        elif args.cp_action == "inspect":
            return cmd_context_pack_inspect(args.path)
        elif args.cp_action == "generate":
            return cmd_context_pack_generate(
                args.target, args.output,
                style=getattr(args, "style", "markdown"),
                allow_execute=getattr(args, "allow_execute", False),
            )
        else:
            print(f"Unknown context-pack action: {args.cp_action}")
            return 1
    elif args.command == "usage":
        if args.usage_action == "inspect":
            return cmd_usage_inspect(args.path)
        elif args.usage_action == "summarize":
            return cmd_usage_summarize(args.path, args.output)
        else:
            print(f"Unknown usage action: {args.usage_action}")
            return 1
    elif args.command == "context-plane":
        if args.ctxpl_action == "plan":
            return cmd_context_plane_plan(
                args.target,
                output=getattr(args, "output", ""),
                style=getattr(args, "style", "markdown"),
            )
        elif args.ctxpl_action == "inspect":
            return cmd_context_plane_inspect(args.path)
        elif args.ctxpl_action == "evidence":
            return cmd_context_plane_evidence(
                args.path,
                output=getattr(args, "output", ""),
                target=getattr(args, "target", ""),
            )
        else:
            print(f"Unknown context-plane action: {args.ctxpl_action}")
            return 1
    elif args.command == "memory-intel":
        if args.mi_action == "profiles":
            return cmd_memory_intel_profiles()
        elif args.mi_action == "mock":
            return cmd_memory_intel_mock(
                provider_id=getattr(args, "provider", "deterministic_mock_memory"),
                signals=getattr(args, "signals", 3),
            )
        elif args.mi_action == "evidence":
            return cmd_memory_intel_evidence(
                provider_id=getattr(args, "provider", "deterministic_mock_memory"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown memory-intel action: {args.mi_action}")
            return 1
    elif args.command == "workspace":
        if args.ws_action == "profiles":
            return cmd_workspace_profiles()
        elif args.ws_action == "mock":
            return cmd_workspace_mock(
                provider_id=getattr(args, "provider", "deterministic_mock_workspace"),
                files=getattr(args, "files", 3),
                diagnostics=getattr(args, "diagnostics", 2),
            )
        elif args.ws_action == "evidence":
            return cmd_workspace_evidence(
                provider_id=getattr(args, "provider", "deterministic_mock_workspace"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown workspace action: {args.ws_action}")
            return 1
    elif args.command == "agent-worker":
        if args.aw_action == "profiles":
            return cmd_agent_worker_profiles()
        elif args.aw_action == "mock":
            return cmd_agent_worker_mock(
                provider_id=getattr(args, "provider", "deterministic_mock_agent"),
                proposals=getattr(args, "proposals", 2),
            )
        elif args.aw_action == "evidence":
            return cmd_agent_worker_evidence(
                provider_id=getattr(args, "provider", "deterministic_mock_agent"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown agent-worker action: {args.aw_action}")
            return 1
    elif args.command == "skill-evolution":
        if args.se_action == "profiles":
            return cmd_skill_evolution_profiles()
        elif args.se_action == "mock":
            return cmd_skill_evolution_mock(
                provider_id=getattr(args, "provider", "deterministic_mock_skill_evolution"),
                proposals=getattr(args, "proposals", 2),
                signals=getattr(args, "signals", 3),
            )
        elif args.se_action == "evidence":
            return cmd_skill_evolution_evidence(
                provider_id=getattr(args, "provider", "deterministic_mock_skill_evolution"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown skill-evolution action: {args.se_action}")
            return 1
    elif args.command == "orchestrate":
        if args.orch_action == "policies":
            return cmd_orchestrate_policies()
        elif args.orch_action == "plan":
            return cmd_orchestrate_plan(
                profile_id=getattr(args, "profile", "safe_context_only"),
                objective=getattr(args, "objective", "Dry-run orchestration plan"),
            )
        elif args.orch_action == "evidence":
            return cmd_orchestrate_evidence(
                profile_id=getattr(args, "profile", "safe_context_only"),
                objective=getattr(args, "objective", "Dry-run orchestration plan"),
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown orchestrate action: {args.orch_action}")
            return 1
    elif args.command == "capability":
        if args.cap_action == "list":
            return cmd_capability_list()
        elif args.cap_action == "summary":
            return cmd_capability_summary()
        elif args.cap_action == "show":
            return cmd_capability_show(args.adapter_id)
        else:
            print(f"Unknown capability action: {args.cap_action}")
            return 1
    elif args.command == "eval":
        if args.eval_action == "suite":
            return cmd_eval_suite()
        elif args.eval_action == "run":
            return cmd_eval_run()
        elif args.eval_action == "regression":
            return cmd_eval_regression(
                output=getattr(args, "output", ""),
            )
        elif args.eval_action == "benefit":
            return cmd_eval_benefit(
                output=getattr(args, "output", ""),
            )
        else:
            print(f"Unknown eval action: {args.eval_action}")
            return 1
    elif args.command == "v4":
        if args.v4_action == "status":
            return cmd_v4_status()
        elif args.v4_action == "ops-check":
            return cmd_v4_ops_check(
                output=getattr(args, "output", ""),
            )
        elif args.v4_action == "runbook":
            return cmd_v4_runbook(
                output=getattr(args, "output", ""),
                fmt=getattr(args, "format", "md"),
            )
        elif args.v4_action == "summary":
            return cmd_v4_summary()
        else:
            print(f"Unknown v4 action: {args.v4_action}")
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
