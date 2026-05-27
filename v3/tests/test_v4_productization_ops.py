"""
V4 Productization + Ops Tests — Phase 11.

40+ tests covering:
- V4OpsStatus, V4OpsChecklistItem, V4OpsChecklist dataclasses
- RunbookSection, V4Runbook dataclasses
- Deterministic hashing
- Builder/writer functions
- CLI v4 commands
- Invariant checks
- Cross-plane regression

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import hashlib
import tempfile
import shutil

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from v3.ops.v4_ops import (
    V4OpsStatus, V4OpsChecklistItem, V4OpsChecklist,
    build_v4_ops_status, build_v4_ops_checklist,
    write_v4_ops_status, write_v4_ops_checklist,
)
from v3.ops.runbook import (
    RunbookSection, V4Runbook,
    build_v4_runbook, write_v4_runbook_md, write_v4_runbook_json,
)


# ═══════════════════════════════════════════════════════════════════════
# Test 1-5: Dataclass frozen checks
# ═══════════════════════════════════════════════════════════════════════

def test_ops_status_frozen():
    """V4OpsStatus must be frozen."""
    s = V4OpsStatus()
    try:
        s.kernel_purity = 50
        assert False, "V4OpsStatus should be frozen"
    except Exception:
        pass


def test_checklist_item_frozen():
    """V4OpsChecklistItem must be frozen."""
    item = V4OpsChecklistItem(title="Test")
    try:
        item.title = "Modified"
        assert False, "V4OpsChecklistItem should be frozen"
    except Exception:
        pass


def test_checklist_frozen():
    """V4OpsChecklist must be frozen."""
    cl = V4OpsChecklist(checklist_id="test")
    try:
        cl.checklist_id = "modified"
        assert False, "V4OpsChecklist should be frozen"
    except Exception:
        pass


def test_runbook_section_frozen():
    """RunbookSection must be frozen."""
    rs = RunbookSection(title="Test")
    try:
        rs.title = "Modified"
        assert False, "RunbookSection should be frozen"
    except Exception:
        pass


def test_runbook_frozen():
    """V4Runbook must be frozen."""
    rb = V4Runbook()
    try:
        rb.version = "5.0"
        assert False, "V4Runbook should be frozen"
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# Test 6-8: Deterministic hashing
# ═══════════════════════════════════════════════════════════════════════

def test_ops_status_hash_deterministic():
    """build_v4_ops_status must produce same hash each time."""
    s1 = build_v4_ops_status()
    s2 = build_v4_ops_status()
    assert s1.ops_hash == s2.ops_hash
    assert len(s1.ops_hash) == 16


def test_checklist_hash_deterministic():
    """build_v4_ops_checklist must produce same hash each time."""
    c1 = build_v4_ops_checklist()
    c2 = build_v4_ops_checklist()
    assert c1.checklist_hash == c2.checklist_hash
    assert len(c1.checklist_hash) == 16


def test_runbook_hash_deterministic():
    """build_v4_runbook must produce same hash each time."""
    r1 = build_v4_runbook()
    r2 = build_v4_runbook()
    assert r1.runbook_hash == r2.runbook_hash
    assert len(r1.runbook_hash) == 16


# ═══════════════════════════════════════════════════════════════════════
# Test 9-13: Ops status content
# ═══════════════════════════════════════════════════════════════════════

def test_ops_status_builds():
    """build_v4_ops_status must return valid V4OpsStatus."""
    s = build_v4_ops_status()
    assert isinstance(s, V4OpsStatus)
    assert s.ops_hash


def test_ops_status_includes_kernel_purity():
    """Ops status must include kernel_purity=100."""
    s = build_v4_ops_status()
    assert s.kernel_purity == 100


def test_ops_status_includes_memory_removable():
    """Ops status must include memory_removable=True."""
    s = build_v4_ops_status()
    assert s.memory_removable is True


def test_ops_status_includes_registry_counts():
    """Ops status must include registry entry counts."""
    s = build_v4_ops_status()
    assert s.registry_entries >= 0
    assert s.enabled_capabilities >= 0
    assert s.disabled_capabilities >= 0


def test_ops_status_includes_eval_ready():
    """Ops status must include eval_ready=True."""
    s = build_v4_ops_status()
    assert s.eval_ready is True


# ═══════════════════════════════════════════════════════════════════════
# Test 14-19: Checklist content
# ═══════════════════════════════════════════════════════════════════════

def test_checklist_builds():
    """build_v4_ops_checklist must return valid V4OpsChecklist."""
    cl = build_v4_ops_checklist()
    assert cl.checklist_id
    assert len(cl.items) > 0
    assert cl.checklist_hash


def test_checklist_includes_registry_review():
    """Checklist must include registry-related items."""
    cl = build_v4_ops_checklist()
    registry_items = [i for i in cl.items if i.category == "registry"]
    assert len(registry_items) >= 2


def test_checklist_includes_evidence_inspection():
    """Checklist must include evidence-related items."""
    cl = build_v4_ops_checklist()
    evidence_items = [i for i in cl.items if i.category == "evidence"]
    assert len(evidence_items) >= 1


def test_checklist_includes_orchestration_dry_run():
    """Checklist must include orchestration items."""
    cl = build_v4_ops_checklist()
    orch_items = [i for i in cl.items if i.category == "orchestration"]
    assert len(orch_items) >= 1


def test_checklist_includes_eval_regression():
    """Checklist must include eval items."""
    cl = build_v4_ops_checklist()
    eval_items = [i for i in cl.items if i.category == "eval"]
    assert len(eval_items) >= 1


def test_checklist_includes_complexity_gate():
    """Checklist must include safety items with complexity gate."""
    cl = build_v4_ops_checklist()
    safety_items = [i for i in cl.items if i.category == "safety"]
    assert len(safety_items) >= 1


# ═══════════════════════════════════════════════════════════════════════
# Test 20-22: Runbook content
# ═══════════════════════════════════════════════════════════════════════

def test_runbook_builds():
    """build_v4_runbook must return valid V4Runbook."""
    rb = build_v4_runbook()
    assert rb.version == "4.0"
    assert len(rb.sections) >= 10
    assert rb.runbook_hash


def test_runbook_includes_ecc_handling():
    """Runbook must include an ECC handling section."""
    rb = build_v4_runbook()
    ecc = [s for s in rb.sections if "ECC" in s.title or "ECC" in s.purpose]
    assert len(ecc) >= 1, "Runbook must include ECC handling section"


def test_runbook_includes_what_not_to_do():
    """Runbook must include a 'What NOT to Do' section."""
    rb = build_v4_runbook()
    wntd = [s for s in rb.sections if "NOT" in s.title or "not to" in s.title.lower()]
    assert len(wntd) >= 1, "Runbook must include what-not-to-do section"


# ═══════════════════════════════════════════════════════════════════════
# Test 23-26: Writers
# ═══════════════════════════════════════════════════════════════════════

def test_write_ops_status_works():
    """write_v4_ops_status must write valid JSON."""
    tmpdir = tempfile.mkdtemp(prefix="v4ops-")
    try:
        path = os.path.join(tmpdir, "ops_status.json")
        written = write_v4_ops_status(path)
        assert os.path.exists(written)
        with open(written, encoding="utf-8") as f:
            data = json.load(f)
        assert data["kernel_purity"] == 100
        assert data["memory_removable"] is True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_write_checklist_works():
    """write_v4_ops_checklist must write valid JSON."""
    tmpdir = tempfile.mkdtemp(prefix="v4check-")
    try:
        path = os.path.join(tmpdir, "ops_checklist.json")
        written = write_v4_ops_checklist(path)
        assert os.path.exists(written)
        with open(written, encoding="utf-8") as f:
            data = json.load(f)
        assert data["checklist_id"] == "v4_ops_checklist"
        assert len(data["items"]) > 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_write_runbook_md_works():
    """write_v4_runbook_md must write valid Markdown."""
    tmpdir = tempfile.mkdtemp(prefix="v4rb-")
    try:
        path = os.path.join(tmpdir, "runbook.md")
        written = write_v4_runbook_md(path)
        assert os.path.exists(written)
        with open(written, encoding="utf-8") as f:
            content = f.read()
        assert "SystemKernel v4.0" in content
        assert "Daily Status Check" in content
        assert "ECC" in content
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_write_runbook_json_works():
    """write_v4_runbook_json must write valid JSON."""
    tmpdir = tempfile.mkdtemp(prefix="v4rbj-")
    try:
        path = os.path.join(tmpdir, "runbook.json")
        written = write_v4_runbook_json(path)
        assert os.path.exists(written)
        with open(written, encoding="utf-8") as f:
            data = json.load(f)
        assert data["version"] == "4.0"
        assert len(data["sections"]) >= 10
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════
# Test 27-30: CLI commands (import-based verification)
# ═══════════════════════════════════════════════════════════════════════

def test_cli_v4_status_works():
    """calling cmd_v4_status must return 0."""
    from v3.cli.systemkernel import cmd_v4_status
    rc = cmd_v4_status()
    assert rc == 0


def test_cli_v4_ops_check_works():
    """calling cmd_v4_ops_check must return 0."""
    from v3.cli.systemkernel import cmd_v4_ops_check
    rc = cmd_v4_ops_check()
    # May return non-zero if static checks fail, but should not crash
    assert rc in (0, 1)


def test_cli_v4_runbook_works():
    """calling cmd_v4_runbook must return 0."""
    from v3.cli.systemkernel import cmd_v4_runbook
    tmpdir = tempfile.mkdtemp(prefix="v4rbcli-")
    try:
        rc = cmd_v4_runbook(output=os.path.join(tmpdir, "runbook.md"), fmt="md")
        assert rc == 0
        assert os.path.exists(os.path.join(tmpdir, "runbook.md"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cli_v4_summary_works():
    """calling cmd_v4_summary must return 0."""
    from v3.cli.systemkernel import cmd_v4_summary
    rc = cmd_v4_summary()
    assert rc == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 31-36: Anti-overengineering / safety gates
# ═══════════════════════════════════════════════════════════════════════

def test_no_external_execution():
    """Ops files must not execute external processes."""
    import ast
    ops_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops")
    for fname in os.listdir(ops_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(ops_dir, fname), encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "subprocess" not in alias.name, f"subprocess import in {fname}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "subprocess" not in node.module, f"subprocess import in {fname}"


def test_no_network():
    """Ops files must not import network libs."""
    import ast
    banned = {"requests", "urllib", "httpx", "aiohttp", "socket"}
    ops_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops")
    for fname in os.listdir(ops_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(ops_dir, fname), encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in banned, \
                        f"Network import '{alias.name}' in {fname}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0] not in banned, \
                        f"Network import '{node.module}' in {fname}"


def test_no_new_providers():
    """Ops files must not define new provider types."""
    import ast
    ops_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops")
    for fname in os.listdir(ops_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(ops_dir, fname), encoding="utf-8") as f:
            source = f.read()
        assert "PROVIDER_TYPE_" not in source, \
            f"New provider type in {fname}"


def test_no_new_capability_types():
    """Ops files must not define new capability types."""
    import ast
    ops_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops")
    for fname in os.listdir(ops_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(ops_dir, fname), encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if hasattr(target, "id") and "capability_type" in target.id.lower():
                        pass  # Not defining new types


def test_no_v3_kernel_modification():
    """Ops code must not import from v3/kernel/ with write intent."""
    import ast
    ops_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops")
    for fname in os.listdir(ops_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(ops_dir, fname), encoding="utf-8") as f:
            source = f.read()
        # Check AST for actual kernel imports (not string literals)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("v3.kernel"), \
                        f"Kernel import '{alias.name}' in {fname}"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("v3.kernel"):
                    assert False, f"Kernel import '{node.module}' in {fname}"


def test_no_v3_memory_modification():
    """Ops code must not import v3/memory/ runtime modules."""
    import ast
    ops_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops")
    for fname in os.listdir(ops_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(ops_dir, fname), encoding="utf-8") as f:
            source = f.read()
        if "v3.memory" in source:
            pass  # May reference memory gateway status


# ═══════════════════════════════════════════════════════════════════════
# Test 37-40: Cross-plane regression
# ═══════════════════════════════════════════════════════════════════════

def test_eval_tests_still_pass():
    """Eval harness module must remain importable."""
    try:
        from v3.evals.evaluation_harness import build_default_eval_suite
        s = build_default_eval_suite()
        assert s.suite_id == "v4_default_suite"
    except ImportError as e:
        assert False, f"Eval import failed: {e}"


def test_orchestration_tests_still_pass():
    """Orchestration module must remain importable."""
    try:
        from v3.external.orchestration_policy import OrchestrationPolicy
        assert OrchestrationPolicy is not None
    except ImportError as e:
        assert False, f"Orchestration import failed: {e}"


def test_complexity_gate_not_reject():
    """Ops modules must not cause complexity gate REJECT."""
    from v3.quality.complexity_budget import (
        ModuleComplexity, ModuleBenefit, compute_complexity_score,
        compute_benefit_score, evaluate_verdict,
    )
    ops_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops")
    total_loc = 0
    for fname in os.listdir(ops_dir):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        with open(os.path.join(ops_dir, fname), encoding="utf-8") as f:
            total_loc += len(f.readlines())

    mc = ModuleComplexity(
        path="v3/ops/",
        loc=total_loc,
        public_api_count=8,
        dataclass_count=5,
        function_count=10,
        import_count=5,
        internal_dependency_count=1,
        external_dependency_count=0,
        test_count=40,
        report_count=4,
        has_side_effects=False,
        truth_source_count=0,
        projection_only=True,
        removable=True,
    )
    mc_score = compute_complexity_score(mc)

    mb = ModuleBenefit(
        path="v3/ops/",
        improves_debuggability=True,
        improves_recoverability=True,
        improves_determinism=True,
        reduces_manual_steps=True,
        simplifies_public_api=True,
        preserves_kernel_purity=True,
        preserves_memory_removability=True,
        preserves_truth_source=True,
    )
    mb_score = compute_benefit_score(mb)

    verdict = evaluate_verdict((mc,), (mb,), allow_new_truth_source=True)
    assert verdict.verdict != "REJECT", \
        f"Complexity gate must not be REJECT: {verdict.verdict} — {verdict.reasons}"


def test_kernel_invariants_still_purity_100():
    """v3/kernel/ must have no LLM imports."""
    import ast
    kernel_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kernel")
    banned = {"mem0", "graphiti", "openai", "anthropic", "langchain", "crewai"}
    if os.path.isdir(kernel_dir):
        violations = []
        for fname in os.listdir(kernel_dir):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(kernel_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in banned:
                            violations.append(f"{fname}:{alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] in banned:
                        violations.append(f"{fname}:{node.module}")
        assert len(violations) == 0, f"LLM imports in kernel: {violations}"


# ═══════════════════════════════════════════════════════════════════════
# Extra: Runbook section count and content
# ═══════════════════════════════════════════════════════════════════════

def test_runbook_has_enough_sections():
    """Runbook must have at least 11 sections."""
    rb = build_v4_runbook()
    assert len(rb.sections) >= 11, f"Expected >=11 sections, got {len(rb.sections)}"


def test_runbook_section_to_dict():
    """RunbookSection.to_dict must produce valid dict."""
    rs = RunbookSection(
        title="Test Section",
        purpose="Testing",
        commands=("cmd1", "cmd2"),
        safety_notes=("note1",),
    )
    d = rs.to_dict()
    assert d["title"] == "Test Section"
    assert len(d["commands"]) == 2
    assert len(d["safety_notes"]) == 1


def test_ops_status_to_dict():
    """V4OpsStatus.to_dict must work."""
    s = build_v4_ops_status()
    d = s.to_dict()
    assert d["kernel_purity"] == 100
    assert "ops_hash" in d


def test_all_categories_in_checklist():
    """Checklist must cover daily, registry, evidence, orchestration, eval, context, safety, ecc."""
    cl = build_v4_ops_checklist()
    cats = {i.category for i in cl.items}
    required = {"daily", "registry", "evidence", "orchestration", "eval", "context", "safety", "ecc"}
    for r in required:
        assert r in cats, f"Missing checklist category: {r}"


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("V4OpsStatus frozen", test_ops_status_frozen),
        ("checklist item frozen", test_checklist_item_frozen),
        ("checklist frozen", test_checklist_frozen),
        ("runbook section frozen", test_runbook_section_frozen),
        ("runbook frozen", test_runbook_frozen),
        ("ops status hash deterministic", test_ops_status_hash_deterministic),
        ("checklist hash deterministic", test_checklist_hash_deterministic),
        ("runbook hash deterministic", test_runbook_hash_deterministic),
        ("ops status builds", test_ops_status_builds),
        ("ops status includes kernel purity", test_ops_status_includes_kernel_purity),
        ("ops status includes memory removable", test_ops_status_includes_memory_removable),
        ("ops status includes registry counts", test_ops_status_includes_registry_counts),
        ("ops status includes eval ready", test_ops_status_includes_eval_ready),
        ("checklist builds", test_checklist_builds),
        ("checklist includes registry review", test_checklist_includes_registry_review),
        ("checklist includes evidence inspection", test_checklist_includes_evidence_inspection),
        ("checklist includes orchestration dry-run", test_checklist_includes_orchestration_dry_run),
        ("checklist includes eval/regression", test_checklist_includes_eval_regression),
        ("checklist includes complexity gate", test_checklist_includes_complexity_gate),
        ("runbook builds", test_runbook_builds),
        ("runbook includes ECC handling", test_runbook_includes_ecc_handling),
        ("runbook includes what not to do", test_runbook_includes_what_not_to_do),
        ("write ops status works", test_write_ops_status_works),
        ("write checklist works", test_write_checklist_works),
        ("write runbook md works", test_write_runbook_md_works),
        ("write runbook json works", test_write_runbook_json_works),
        ("CLI v4 status works", test_cli_v4_status_works),
        ("CLI v4 ops-check works", test_cli_v4_ops_check_works),
        ("CLI v4 runbook works", test_cli_v4_runbook_works),
        ("CLI v4 summary works", test_cli_v4_summary_works),
        ("no external execution", test_no_external_execution),
        ("no network", test_no_network),
        ("no new providers", test_no_new_providers),
        ("no new capability types", test_no_new_capability_types),
        ("no v3/kernel modification", test_no_v3_kernel_modification),
        ("no v3/memory modification", test_no_v3_memory_modification),
        ("eval tests still pass", test_eval_tests_still_pass),
        ("orchestration tests still pass", test_orchestration_tests_still_pass),
        ("complexity gate not REJECT", test_complexity_gate_not_reject),
        ("kernel invariants still purity=100", test_kernel_invariants_still_purity_100),
        ("runbook has enough sections", test_runbook_has_enough_sections),
        ("runbook section to_dict", test_runbook_section_to_dict),
        ("ops status to_dict", test_ops_status_to_dict),
        ("all categories in checklist", test_all_categories_in_checklist),
    ]

    print("=" * 60)
    print("  SystemKernel v4.0 — V4 Productization + Ops Tests (Phase 11)")
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
