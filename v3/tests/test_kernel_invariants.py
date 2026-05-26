"""
Kernel Validity Stress Test — Phase 3.6.

6 HARD invariant tests proving SystemKernel is a deterministic execution
kernel, not a high-level orchestration framework.

Includes:
  - LLM boundary audit across all kernel files
  - Execution purity scoring (0–100)
  - Final kernel_validity_report.json generation
"""

import sys
import os
import json
import uuid
import hashlib
import shutil
import tempfile
import ast
from pathlib import Path

# Add SystemKernel root to path
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.kernel.execution_engine import (
    ExecutionEngine,
    DomainState,
    ExecutionConfig,
    StateField,
    MergeStrategy,
    RetryPolicy,
    NoopStage,
)
from v3.kernel.checkpoint import FileCheckpointStore
from v3.kernel.memory_gateway import MemoryGateway
from v3.kernel.truth_model import (
    ExecutionTruthSnapshot,
    capture_truth,
    write_truth,
    read_truths,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_domain_state(thread_id: str = "invariant-test") -> DomainState:
    return DomainState(
        schema=(
            StateField("thread_id", str, MergeStrategy.KEEP),
            StateField("target", str, MergeStrategy.REPLACE, default="."),
            StateField("task_id", str, MergeStrategy.KEEP),
            StateField("skill_id", str, MergeStrategy.KEEP),
            StateField("_last_stage", str, MergeStrategy.REPLACE),
            StateField("_last_result", dict, MergeStrategy.REPLACE),
        ),
        initial={
            "thread_id": thread_id,
            "target": ".",
            "task_id": f"task-{uuid.uuid4().hex[:8]}",
            "skill_id": "kernel-invariant-test",
        },
    )


def _make_engine(**kwargs) -> ExecutionEngine:
    defaults = {
        "pipeline": (
            NoopStage(name="stage_init", delay_s=0.001),
            NoopStage(name="stage_execute", delay_s=0.001),
            NoopStage(name="stage_verify", delay_s=0.001),
        ),
        "retry": RetryPolicy.ONCE,
        "max_retries": 1,
        "checkpoint_store": None,
        "thread_id": "invariant-test",
        "memory_gateway": None,
    }
    defaults.update(kwargs)
    return ExecutionEngine(ExecutionConfig(**defaults))


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Single Loop Invariant
# ═══════════════════════════════════════════════════════════════════════

def test_single_loop_invariant():
    """ExecutionEngine.run() must execute exactly ONE loop per call.
    No nested loops, no hidden re-execution, no recursive pipeline traversal.
    """
    engine = _make_engine()
    state = _make_domain_state()

    # Track how many times stages execute internally
    stage_hits = []

    class CountingStage(NoopStage):
        def run(self, st):
            stage_hits.append(self._name)
            return super().run(st)

    engine2 = _make_engine(pipeline=(
        CountingStage(name="A", delay_s=0.001),
        CountingStage(name="B", delay_s=0.001),
        CountingStage(name="C", delay_s=0.001),
    ))

    result = engine2.run(state)

    # Each stage must execute exactly once — no nested loops
    assert stage_hits == ["A", "B", "C"], \
        f"Stage execution order: {stage_hits} — expected ['A', 'B', 'C'] (single loop, no nesting)"

    # run_count must be exactly 1 after one call
    assert engine2.run_count == 1, \
        f"run_count={engine2.run_count}, expected 1 (no hidden re-execution)"

    # Result must contain exactly 3 stage results (one per stage, no extras)
    assert len(result["stage_results"]) == 3, \
        f"Expected 3 stage results, got {len(result['stage_results'])}"

    # Verify pipeline is a flat tuple (no nested iterables)
    assert isinstance(engine2.config.pipeline, tuple), \
        "Pipeline must be a flat tuple"


# ═══════════════════════════════════════════════════════════════════════
# Test 2: LLM Boundary Enforcement
# ═══════════════════════════════════════════════════════════════════════

def _scan_kernel_for_llm_imports(kernel_dir: str) -> list[dict]:
    """Scan all .py files in kernel_dir for banned LLM imports.

    Returns list of violation dicts: {file, line, import_name}
    """
    BANNED = {"mem0", "graphiti", "openai", "anthropic", "langchain", "crewai"}
    ALLOWED = {
        "typing", "dataclasses", "json", "hashlib", "time", "enum", "uuid",
        "os", "sys", "subprocess", "pathlib", "datetime", "ast",
        "__future__", "abc", "collections", "functools", "itertools",
    }
    violations = []

    for py_file in Path(kernel_dir).rglob("*.py"):
        # Skip __pycache__
        if "__pycache__" in str(py_file):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                source = f.read()
        except Exception:
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0].lower()
                    if root_pkg in BANNED:
                        violations.append({
                            "file": str(py_file.relative_to(kernel_dir)),
                            "line": node.lineno,
                            "import_name": alias.name,
                            "severity": "CRITICAL",
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0].lower()
                    if root_pkg in BANNED:
                        violations.append({
                            "file": str(py_file.relative_to(kernel_dir)),
                            "line": node.lineno,
                            "import_name": f"from {node.module} import ...",
                            "severity": "CRITICAL",
                        })

    return violations


def test_llm_boundary_enforcement():
    """kernel/ directory MUST NOT import any LLM-related module.
    memory adapters MAY import LLM, but kernel MUST NOT.
    """
    kernel_dir = os.path.join(_root, "v3", "kernel")
    violations = _scan_kernel_for_llm_imports(kernel_dir)

    if violations:
        detail = "\n".join(
            f"  {v['file']}:{v['line']} → {v['import_name']}"
            for v in violations
        )
        raise AssertionError(
            f"LLM imports detected in kernel/:\n{detail}"
        )

    # Also verify allowed-only imports check: kernel code must be minimal
    # (informational only — not a hard fail since kernel may legitimately
    #  import other stdlib modules)
    assert len(violations) == 0, f"{len(violations)} LLM boundary violations found"


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Memory Removability
# ═══════════════════════════════════════════════════════════════════════

def test_memory_removability():
    """System MUST run with memory_gateway=None.
    Execution result must remain identical (deterministic equality).
    """
    # Run WITHOUT memory
    engine_no_mem = _make_engine(memory_gateway=None)
    state1 = _make_domain_state("no-mem-test")
    result_no_mem = engine_no_mem.run(state1)

    assert result_no_mem["success"] is True
    assert result_no_mem["failed_stage"] is None

    # Run WITH memory
    gw = MemoryGateway()
    engine_with_mem = _make_engine(memory_gateway=gw, thread_id="with-mem-test")
    state2 = _make_domain_state("with-mem-test")
    result_with_mem = engine_with_mem.run(state2)

    assert result_with_mem["success"] is True

    # Structural comparison: same pipeline shape regardless of memory
    assert len(result_no_mem["stage_results"]) == len(result_with_mem["stage_results"]), \
        "Stage result count differs with/without memory"

    for r1, r2 in zip(result_no_mem["stage_results"], result_with_mem["stage_results"]):
        assert r1["stage_name"] == r2["stage_name"], \
            f"Stage name differs: {r1['stage_name']} vs {r2['stage_name']}"
        assert r1["passed"] == r2["passed"], \
            f"Stage pass status differs for {r1['stage_name']}"

    # Truth snapshots should match on structural properties
    truth_no_mem = result_no_mem.get("truth", {})
    truth_with_mem = result_with_mem.get("truth", {})

    assert truth_no_mem["pipeline_hash"] == truth_with_mem["pipeline_hash"], \
        "Pipeline hash differs with/without memory"
    assert truth_no_mem["stage_count"] == truth_with_mem["stage_count"], \
        "Stage count differs with/without memory"
    assert truth_no_mem["stage_order"] == truth_with_mem["stage_order"], \
        "Stage order differs with/without memory"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Execution Determinism (10 runs)
# ═══════════════════════════════════════════════════════════════════════

def _compute_execution_hash(truth: dict) -> str:
    """Deterministic hash of execution structural properties."""
    parts = [
        truth.get("pipeline_hash", ""),
        "|".join(truth.get("stage_order", [])),
        str(truth.get("stage_count", 0)),
        str(truth.get("engine_frozen", False)),
        str(truth.get("memory_backend_active", False)),
    ]
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]


def test_execution_determinism():
    """Run same pipeline 10 times. Assert identical execution_hash,
    stage order, and truth_snapshot fingerprint."""
    N = 10
    truths = []
    hashes = set()

    for i in range(N):
        engine = _make_engine(thread_id=f"det-{i}")
        state = _make_domain_state(f"det-{i}")
        result = engine.run(state)

        assert result["success"] is True, f"Run {i} failed"
        truth = result.get("truth", {})
        assert truth, f"Run {i} missing truth snapshot"

        truths.append(truth)
        hashes.add(_compute_execution_hash(truth))

    # Assert identical execution hashes
    assert len(hashes) == 1, \
        f"Expected 1 unique execution hash across {N} runs, got {len(hashes)}"

    # Assert identical stage order
    baseline_order = truths[0]["stage_order"]
    for i, t in enumerate(truths[1:], start=2):
        assert t["stage_order"] == baseline_order, \
            f"Run {i} stage order {t['stage_order']} != baseline {baseline_order}"

    # Assert identical fingerprint
    baseline_fp = truths[0].get("fingerprint") or ExecutionTruthSnapshot(**truths[0]).fingerprint()
    for i, t in enumerate(truths[1:], start=2):
        fp = t.get("fingerprint") or ExecutionTruthSnapshot(**t).fingerprint()
        assert fp == baseline_fp, \
            f"Run {i} fingerprint {fp} != baseline {baseline_fp}"

    # Assert identical pipeline_hash
    baseline_ph = truths[0]["pipeline_hash"]
    for i, t in enumerate(truths[1:], start=2):
        assert t["pipeline_hash"] == baseline_ph, \
            f"Run {i} pipeline_hash {t['pipeline_hash']} != baseline {baseline_ph}"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Truth Model Singularity
# ═══════════════════════════════════════════════════════════════════════

def test_truth_model_singularity():
    """Only ONE truth output exists per execution.
    Must not generate invariants.log.jsonl or structure_traces.jsonl.
    Only truth_snapshots.jsonl allowed as the single truth source.
    """
    # Check that the truth model only writes to truth_snapshots.jsonl
    import inspect

    from v3.kernel import truth_model as tm

    # Verify write_truth only writes to truth_snapshots.jsonl
    write_source = inspect.getsource(tm.write_truth)
    assert "truth_snapshots.jsonl" in write_source, \
        "write_truth must write to truth_snapshots.jsonl"
    assert "invariants.log.jsonl" not in write_source, \
        "write_truth must NOT write invariants.log.jsonl"
    assert "structure_traces.jsonl" not in write_source, \
        "write_truth must NOT write structure_traces.jsonl"

    # Verify structure_trace.py is pure delegation (no new write paths)
    st_path = os.path.join(_root, "v3", "kernel", "structure_trace.py")
    with open(st_path, encoding="utf-8") as f:
        st_source = f.read()
    assert "invariants.log" not in st_source, \
        "structure_trace.py must not reference invariants.log"
    assert "structure_traces.jsonl" not in st_source, \
        "structure_trace.py must not reference structure_traces.jsonl (deprecated)"
    # structure_trace.py must delegate everything to truth_model
    assert "from v3.kernel.truth_model import" in st_source, \
        "structure_trace.py must delegate to truth_model"

    # Run engine and verify truth appears in result
    engine = _make_engine(thread_id="singularity-test")
    state = _make_domain_state("singularity-test")
    result = engine.run(state)

    truth = result.get("truth")
    assert truth is not None, "Missing truth snapshot in result"

    # Verify truth has exactly one source of truth fields
    assert "trace_id" in truth
    assert "pipeline_hash" in truth
    assert "stage_order" in truth
    assert "invariant_violations" in truth

    # Ensure no duplicate systems writing to different files
    # (observability writes to trace.jsonl, metrics/*.jsonl — that's OK)
    # But invariants must not write their own JSONL separately
    inv_path = os.path.join(_root, "v3", "kernel", "invariants.py")
    with open(inv_path, encoding="utf-8") as f:
        inv_source = f.read()
    assert "jsonl" not in inv_source.lower() or "truth_snapshots" in inv_source.lower(), \
        "invariants.py must not write its own JSONL output files"


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Kernel Independence (memory folder removal)
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_independence():
    """Delete entire memory/ folder. System must still:
    execute, checkpoint, and generate truth snapshot.
    """
    memory_dir = os.path.join(_root, "v3", "memory")
    memory_backup = None
    temp_dir = None

    # Verify memory directory exists before we test
    if not os.path.isdir(memory_dir):
        # Already removed — kernel should still work
        pass
    else:
        # Move memory to temp location
        temp_dir = tempfile.mkdtemp(prefix="mem_backup_")
        memory_backup = os.path.join(temp_dir, "memory")
        shutil.move(memory_dir, memory_backup)

    try:
        # Ensure memory imports are purged from sys.modules
        mem_keys = [k for k in list(sys.modules.keys()) if "v3.memory" in k]
        for k in mem_keys:
            del sys.modules[k]

        # Now try to run the kernel — must succeed WITHOUT memory
        from v3.kernel.execution_engine import (
            ExecutionEngine, DomainState, ExecutionConfig,
            StateField, MergeStrategy, RetryPolicy, NoopStage,
        )

        engine = _make_engine(
            thread_id="no-memory-folder",
            memory_gateway=None,
        )
        state = _make_domain_state("no-memory-folder")
        result = engine.run(state)

        # Must execute successfully
        assert result["success"] is True, \
            "Kernel must execute successfully without memory/ folder"
        assert len(result["stage_results"]) == 3, \
            "All 3 pipeline stages must execute"

        # Must generate truth snapshot
        assert "truth" in result, \
            "Kernel must generate truth snapshot without memory/ folder"
        truth = result["truth"]
        assert truth["success"] is True
        assert truth["stage_count"] == 3

        # Must support checkpointing (checkpoint store is independent of memory)
        cp_store = FileCheckpointStore(os.path.join(_root, "v3", "checkpoints"))
        engine_cp = _make_engine(
            thread_id="no-memory-cp",
            memory_gateway=None,
            checkpoint_store=cp_store,
        )
        state_cp = _make_domain_state("no-memory-cp")
        result_cp = engine_cp.run(state_cp)
        assert result_cp["success"] is True

    finally:
        # Restore memory directory
        if memory_backup and os.path.isdir(memory_backup):
            shutil.move(memory_backup, memory_dir)
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Kernel Boundary Audit (STEP 2)
# ═══════════════════════════════════════════════════════════════════════

def audit_kernel_boundary(kernel_dir: str) -> dict:
    """Full scan of all .py files in kernel/ for boundary violations.

    Returns dict with violations list and pass/fail status.
    """
    BANNED = {"mem0", "graphiti", "openai", "anthropic", "langchain", "crewai"}
    violations = []
    files_scanned = []

    for py_file in sorted(Path(kernel_dir).rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        files_scanned.append(str(py_file.relative_to(kernel_dir)))

        try:
            with open(py_file, encoding="utf-8") as f:
                source = f.read()
        except Exception:
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0].lower()
                    if root_pkg in BANNED:
                        violations.append({
                            "file": str(py_file.relative_to(kernel_dir)),
                            "line": node.lineno,
                            "import_name": alias.name,
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0].lower()
                    if root_pkg in BANNED:
                        violations.append({
                            "file": str(py_file.relative_to(kernel_dir)),
                            "line": node.lineno,
                            "import_name": f"from {node.module} import ...",
                        })

    return {
        "files_scanned": files_scanned,
        "files_scanned_count": len(files_scanned),
        "violations": violations,
        "violation_count": len(violations),
        "passed": len(violations) == 0,
    }


def test_full_kernel_boundary_audit():
    """Comprehensive scan: all kernel/ files must be LLM-free."""
    kernel_dir = os.path.join(_root, "v3", "kernel")
    audit = audit_kernel_boundary(kernel_dir)

    if audit["violations"]:
        detail = "\n".join(
            f"  {v['file']}:{v['line']} → {v['import_name']}"
            for v in audit["violations"]
        )
        raise AssertionError(
            f"Kernel boundary violations found ({audit['violation_count']}):\n{detail}"
        )

    # Print audit status
    print(f"\n  Kernel Boundary Audit: {audit['files_scanned_count']} files scanned, 0 violations")


# ═══════════════════════════════════════════════════════════════════════
# Execution Purity Score (STEP 3)
# ═══════════════════════════════════════════════════════════════════════

def compute_execution_purity_score(
    single_loop: bool,
    memory_removable: bool,
    deterministic_output: bool,
    no_llm_in_kernel: bool,
    truth_singular: bool,
) -> tuple[int, str]:
    """Compute execution purity score (0–100) and verdict.

    Score rules:
      +20 if single-loop confirmed
      +20 if memory removable
      +20 if deterministic output
      +20 if no LLM imports in kernel
      +20 if truth_model is single-source

    Verdict:
      100 → PURE KERNEL
      80–99 → HYBRID SYSTEM
      <80 → FRAMEWORK (NOT KERNEL)
    """
    score = 0
    if single_loop:
        score += 20
    if memory_removable:
        score += 20
    if deterministic_output:
        score += 20
    if no_llm_in_kernel:
        score += 20
    if truth_singular:
        score += 20

    if score == 100:
        verdict = "PURE KERNEL"
    elif score >= 80:
        verdict = "HYBRID SYSTEM"
    else:
        verdict = "FRAMEWORK (NOT KERNEL)"

    return score, verdict


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    """Run all kernel invariant tests and generate final report."""
    tests = [
        ("single loop invariant", test_single_loop_invariant),
        ("LLM boundary enforcement", test_llm_boundary_enforcement),
        ("memory removability", test_memory_removability),
        ("execution determinism (10 runs)", test_execution_determinism),
        ("truth model singularity", test_truth_model_singularity),
        ("kernel independence (memory folder removal)", test_kernel_independence),
    ]

    # Run boundary audit separately (used by test_llm_boundary_enforcement
    # but also as standalone STEP 2 audit)
    kernel_dir = os.path.join(_root, "v3", "kernel")
    audit = audit_kernel_boundary(kernel_dir)

    print("=" * 60)
    print("  SystemKernel v3.0 -- Kernel Validity Stress Test (Phase 3.6)")
    print("=" * 60)

    passed = 0
    failed = 0
    results = {}

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
            results[name] = "PASS"
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
            results[name] = f"FAIL: {e}"
        except Exception as e:
            print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
            failed += 1
            results[name] = f"ERROR: {type(e).__name__}: {e}"

    # ── Boundary audit summary ──────────────────────────────────────
    print(f"\n  Kernel Boundary Audit:")
    print(f"    Files scanned: {audit['files_scanned_count']}")
    print(f"    Violations:    {audit['violation_count']}")
    for v in audit["violations"]:
        print(f"      !! {v['file']}:{v['line']} → {v['import_name']}")

    # ── Determine pass/fail for each dimension ───────────────────────
    single_loop_ok = results.get("single loop invariant") == "PASS"
    memory_removable_ok = results.get("memory removability") == "PASS"
    deterministic_ok = results.get("execution determinism (10 runs)") == "PASS"
    no_llm_ok = results.get("LLM boundary enforcement") == "PASS"
    truth_singular_ok = results.get("truth model singularity") == "PASS"

    # ── Compute purity score ────────────────────────────────────────
    purity_score, verdict = compute_execution_purity_score(
        single_loop=single_loop_ok,
        memory_removable=memory_removable_ok,
        deterministic_output=deterministic_ok,
        no_llm_in_kernel=no_llm_ok,
        truth_singular=truth_singular_ok,
    )

    print(f"\n{'-' * 60}")
    print(f"  Execution Purity Score: {purity_score}/100")
    print(f"  Breakdown:")
    print(f"    Single-loop confirmed:     {'[+]' if single_loop_ok else '[-]'} (+20)")
    print(f"    Memory removable:          {'[+]' if memory_removable_ok else '[-]'} (+20)")
    print(f"    Deterministic output:      {'[+]' if deterministic_ok else '[-]'} (+20)")
    print(f"    No LLM imports in kernel:  {'[+]' if no_llm_ok else '[-]'} (+20)")
    print(f"    Truth model single-source: {'[+]' if truth_singular_ok else '[-]'} (+20)")
    print(f"  Verdict: {verdict}")

    # ── Generate final report ────────────────────────────────────────
    report = {
        "report_type": "kernel_validity_report",
        "phase": "3.6",
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "purity_score": purity_score,
        "verdict": verdict,
        "invariant_results": {
            "single_loop": {
                "passed": single_loop_ok,
                "detail": results.get("single loop invariant", ""),
            },
            "llm_boundary": {
                "passed": no_llm_ok,
                "detail": results.get("LLM boundary enforcement", ""),
                "files_scanned": audit["files_scanned_count"],
                "violations_found": audit["violation_count"],
            },
            "memory_removability": {
                "passed": memory_removable_ok,
                "detail": results.get("memory removability", ""),
            },
            "execution_determinism": {
                "passed": deterministic_ok,
                "detail": results.get("execution determinism (10 runs)", ""),
                "runs": 10,
            },
            "truth_singularity": {
                "passed": truth_singular_ok,
                "detail": results.get("truth model singularity", ""),
            },
            "kernel_independence": {
                "passed": results.get("kernel independence (memory folder removal)") == "PASS",
                "detail": results.get("kernel independence (memory folder removal)", ""),
            },
        },
        "determinism_result": deterministic_ok,
        "memory_dependency_result": not memory_removable_ok,
        "llm_boundary_result": no_llm_ok,
        "final_verdict": verdict,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_total": len(tests),
    }

    # Write report
    export_dir = os.path.join(_root, "v3", "exports")
    os.makedirs(export_dir, exist_ok=True)
    report_path = os.path.join(export_dir, "kernel_validity_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  Report written: {os.path.abspath(report_path)}")
    print(f"\n  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"\n  ACCEPTANCE: {'ACHIEVED' if purity_score == 100 and failed == 0 else 'NOT MET'}")
    print(f"    - 6/6 tests pass:         {'[+]' if passed == 6 else '[-]'} ({passed}/6)")
    print(f"    - purity_score == 100:     {'[+]' if purity_score == 100 else '[-]'} ({purity_score})")
    print(f"    - memory fully removable:  {'[+]' if memory_removable_ok else '[-]'}")
    print(f"    - zero external AI deps:   {'[+]' if no_llm_ok else '[-]'}")
    print(f"    - identical with/without memory: {'[+]' if memory_removable_ok else '[-]'}")

    return failed == 0 and purity_score == 100


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
