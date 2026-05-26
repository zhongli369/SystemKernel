"""
Golden Path Tests — Phase 5C.

Comprehensive tests for:
  1. golden path script exists
  2. golden path runs successfully
  3. output summary generated
  4. summary is deterministic across two runs
  5. event_count > 0
  6. graph_hash exists
  7. memory candidates generated
  8. recall results generated
  9. memory system report generated
  10. expected_summary matches current summary for stable fields
  11. CLI status works after golden path
  12. CLI reports summary works after golden path
  13. docs quickstart exists
  14. docs architecture overview exists
  15. no banned LLM imports in examples/docs
  16. complexity gate not REJECT
  17. existing kernel invariants still purity=100

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import ast
import subprocess

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

_v3_root = os.path.join(_root, "v3")
_python = sys.executable
_golden_path_script = os.path.join(_root, "examples", "golden_path", "run_golden_path.py")
_output_dir = os.path.join(_root, "examples", "golden_path", "output")


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _run_golden_path() -> subprocess.CompletedProcess:
    return subprocess.run(
        [_python, _golden_path_script],
        capture_output=True, text=True, timeout=120,
        cwd=_root,
    )


def _read_summary() -> dict:
    path = os.path.join(_output_dir, "golden_path_summary.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_expected() -> dict:
    path = os.path.join(_root, "examples", "golden_path", "expected_summary.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════
# Test 1: golden path script exists
# ═══════════════════════════════════════════════════════════════════════

def test_golden_path_script_exists():
    """run_golden_path.py must exist."""
    assert os.path.exists(_golden_path_script), \
        f"Golden path script not found: {_golden_path_script}"


# ═══════════════════════════════════════════════════════════════════════
# Test 2: golden path runs successfully
# ═══════════════════════════════════════════════════════════════════════

def test_golden_path_runs():
    """Golden path must complete without errors."""
    result = _run_golden_path()
    assert result.returncode == 0, \
        f"Golden path failed (exit {result.returncode}):\n{result.stderr[:500]}"
    assert "GOLDEN PATH COMPLETE" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 3: output summary generated
# ═══════════════════════════════════════════════════════════════════════

def test_output_summary_generated():
    """Golden path must produce golden_path_summary.json."""
    _run_golden_path()
    summary_path = os.path.join(_output_dir, "golden_path_summary.json")
    assert os.path.exists(summary_path), f"Summary not found: {summary_path}"

    summary = _read_summary()
    assert "golden_path_version" in summary
    assert "run_hash" in summary


# ═══════════════════════════════════════════════════════════════════════
# Test 4: summary is deterministic across two runs
# ═══════════════════════════════════════════════════════════════════════

def test_summary_deterministic():
    """Running golden path twice must produce identical summaries."""
    _run_golden_path()
    summary1 = _read_summary()

    _run_golden_path()
    summary2 = _read_summary()

    # Stable fields must match exactly
    stable_fields = [
        "event_count", "graph_hash", "candidates_count",
        "event_stream_fingerprint", "run_hash",
    ]
    for field in stable_fields:
        assert summary1[field] == summary2[field], \
            f"Field '{field}' not deterministic: {summary1[field]} != {summary2[field]}"

    # Memory sub-fields must also be stable
    mem1 = summary1["memory"]
    mem2 = summary2["memory"]
    for key in ("written_count", "runtime_hash", "recall_count", "report_hash"):
        assert mem1[key] == mem2[key], \
            f"Memory '{key}' not deterministic: {mem1[key]} != {mem2[key]}"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: event_count > 0
# ═══════════════════════════════════════════════════════════════════════

def test_event_count_positive():
    """Golden path must produce events."""
    _run_golden_path()
    summary = _read_summary()
    assert summary["event_count"] > 0
    assert summary["event_count"] == 13  # Known count for golden path


# ═══════════════════════════════════════════════════════════════════════
# Test 6: graph_hash exists
# ═══════════════════════════════════════════════════════════════════════

def test_graph_hash_exists():
    """Golden path must produce a graph_hash."""
    _run_golden_path()
    summary = _read_summary()
    assert len(summary["graph_hash"]) == 16
    assert summary["graph_hash"] == "a8e5b63f53a4d25e"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: memory candidates generated
# ═══════════════════════════════════════════════════════════════════════

def test_candidates_generated():
    """Golden path must project memory candidates."""
    _run_golden_path()
    summary = _read_summary()
    assert summary["candidates_count"] > 0
    assert summary["candidates_count"] == 8


# ═══════════════════════════════════════════════════════════════════════
# Test 8: recall results generated
# ═══════════════════════════════════════════════════════════════════════

def test_recall_results_generated():
    """Golden path must produce recall results."""
    _run_golden_path()
    summary = _read_summary()
    assert summary["memory"]["recall_count"] > 0


# ═══════════════════════════════════════════════════════════════════════
# Test 9: memory system report generated
# ═══════════════════════════════════════════════════════════════════════

def test_memory_report_generated():
    """Golden path must write memory_system_report.json."""
    _run_golden_path()
    report_path = os.path.join(_output_dir, "memory_system_report.json")
    assert os.path.exists(report_path), f"Memory report not found: {report_path}"

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    assert "verdicts" in report
    assert report["verdicts"]["removability"] == "YES"


# ═══════════════════════════════════════════════════════════════════════
# Test 10: expected_summary matches current summary for stable fields
# ═══════════════════════════════════════════════════════════════════════

def test_expected_summary_matches():
    """expected_summary.json must match current run for stable fields."""
    _run_golden_path()
    current = _read_summary()
    expected = _read_expected()

    stable_fields = [
        "event_count", "graph_hash", "candidates_count",
        "event_stream_fingerprint", "run_hash",
    ]
    for field in stable_fields:
        assert current[field] == expected[field], \
            f"Field '{field}' drifted: expected {expected[field]}, got {current[field]}"

    # Memory stability
    for key in ("written_count", "recall_count", "runtime_hash"):
        assert current["memory"][key] == expected["memory"][key], \
            f"Memory '{key}' drifted"


# ═══════════════════════════════════════════════════════════════════════
# Test 11: CLI status works after golden path
# ═══════════════════════════════════════════════════════════════════════

def test_cli_status_after_golden_path():
    """CLI status must work after running golden path."""
    _run_golden_path()
    cli_path = os.path.join(_v3_root, "cli", "systemkernel.py")
    result = subprocess.run(
        [_python, cli_path, "status"],
        capture_output=True, text=True, timeout=60,
        cwd=_root,
    )
    assert result.returncode == 0
    assert "Kernel Purity" in result.stdout
    assert "Memory Removable" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 12: CLI reports summary works after golden path
# ═══════════════════════════════════════════════════════════════════════

def test_cli_reports_summary_after_golden_path():
    """CLI reports summary must work after running golden path."""
    _run_golden_path()
    cli_path = os.path.join(_v3_root, "cli", "systemkernel.py")
    result = subprocess.run(
        [_python, cli_path, "reports", "summary"],
        capture_output=True, text=True, timeout=60,
        cwd=_root,
    )
    assert result.returncode == 0
    assert "PURE KERNEL" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 13: docs quickstart exists
# ═══════════════════════════════════════════════════════════════════════

def test_docs_quickstart_exists():
    """docs/QUICKSTART.md must exist."""
    path = os.path.join(_root, "docs", "QUICKSTART.md")
    assert os.path.exists(path), f"QUICKSTART.md not found: {path}"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "Quickstart" in content
    assert "systemkernel" in content.lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 14: docs architecture overview exists
# ═══════════════════════════════════════════════════════════════════════

def test_docs_architecture_exists():
    """docs/ARCHITECTURE_OVERVIEW.md must exist."""
    path = os.path.join(_root, "docs", "ARCHITECTURE_OVERVIEW.md")
    assert os.path.exists(path), f"ARCHITECTURE_OVERVIEW.md not found: {path}"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "SystemKernel" in content
    assert "Source of Truth" in content


# ═══════════════════════════════════════════════════════════════════════
# Test 15: no banned LLM imports in examples/docs
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_imports_in_examples():
    """Golden path and docs must not import banned LLM/AI packages."""
    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "sklearn", "scipy",
    }
    py_files = [
        os.path.join(_root, "examples", "golden_path", "run_golden_path.py"),
    ]
    for fpath in py_files:
        if not os.path.exists(fpath):
            continue
        with open(fpath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in banned, f"Banned import '{name}' in {os.path.basename(fpath)}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    assert name not in banned, f"Banned import '{name}' in {os.path.basename(fpath)}"


# ═══════════════════════════════════════════════════════════════════════
# Test 16: complexity gate not REJECT
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_gate_not_reject():
    """Complexity gate must not become REJECT."""
    from v3.quality.phase_gate import evaluate_phase
    result = evaluate_phase("golden-path", v3_root=_v3_root)
    assert result.verdict.verdict != "REJECT", \
        f"Gate REJECTED: {result.verdict.reasons}"


# ═══════════════════════════════════════════════════════════════════════
# Test 17: existing kernel invariants still purity=100
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_invariants_purity():
    """Kernel purity must remain 100."""
    test_path = os.path.join(_v3_root, "tests", "test_kernel_invariants.py")
    result = subprocess.run(
        [_python, test_path],
        capture_output=True, text=True, timeout=120,
        cwd=_root,
    )
    assert "purity_score == 100" in result.stdout, \
        f"Kernel purity degraded:\n{result.stdout[:500]}"


# ═══════════════════════════════════════════════════════════════════════
# Bonus tests
# ═══════════════════════════════════════════════════════════════════════

def test_golden_path_readme_exists():
    """examples/golden_path/README.md must exist."""
    path = os.path.join(_root, "examples", "golden_path", "README.md")
    assert os.path.exists(path), f"README.md not found: {path}"


def test_golden_path_memory_report_has_correct_verdicts():
    """Memory report must confirm removability, projection, truth source."""
    _run_golden_path()
    report_path = os.path.join(_output_dir, "memory_system_report.json")
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    verdicts = report["verdicts"]
    assert verdicts["removability"] == "YES"
    assert verdicts["projection_only"] == "YES"
    assert verdicts["source_of_truth"] == "YES"


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("golden path script exists", test_golden_path_script_exists),
        ("golden path runs successfully", test_golden_path_runs),
        ("output summary generated", test_output_summary_generated),
        ("summary is deterministic (2 runs)", test_summary_deterministic),
        ("event_count > 0", test_event_count_positive),
        ("graph_hash exists and stable", test_graph_hash_exists),
        ("memory candidates generated", test_candidates_generated),
        ("recall results generated", test_recall_results_generated),
        ("memory system report generated", test_memory_report_generated),
        ("expected summary matches current", test_expected_summary_matches),
        ("CLI status after golden path", test_cli_status_after_golden_path),
        ("CLI reports summary after golden path", test_cli_reports_summary_after_golden_path),
        ("docs QUICKSTART.md exists", test_docs_quickstart_exists),
        ("docs ARCHITECTURE_OVERVIEW.md exists", test_docs_architecture_exists),
        ("no banned LLM imports in examples", test_no_banned_imports_in_examples),
        ("complexity gate not REJECT", test_complexity_gate_not_reject),
        ("kernel invariants purity=100", test_kernel_invariants_purity),
        # Bonus
        ("golden path README exists", test_golden_path_readme_exists),
        ("memory report verdicts correct", test_golden_path_memory_report_has_correct_verdicts),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Golden Path Tests (Phase 5C)")
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
