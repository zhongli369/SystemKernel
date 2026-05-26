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

    return parser


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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
