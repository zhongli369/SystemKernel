"""
External Tool Registry Tests — Phase 5E.

Tests for:
  - ExternalToolEntry, ExternalToolRegistry
  - ClonePlanItem, ClonePlan
  - build_registry_from_profiles()
  - create_clone_plan()
  - CLI intake registry, clone-plan, clone-list
  - Safety invariants (no network, no git, no kernel modification)
  - Regression (existing tests still pass)
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")
CLI_PATH = os.path.join(V3_ROOT, "cli", "systemkernel.py")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, CLI_PATH] + list(args),
        capture_output=True, text=True, cwd=V3_ROOT,
    )


# ═══════════════════════════════════════════════════════════════════════
# Test 1: registry builds from profiles
# ═══════════════════════════════════════════════════════════════════════

def test_registry_builds_from_profiles():
    """Registry builds successfully from all 14 profiles."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    assert len(registry.entries) == 14, f"Expected 14 entries, got {len(registry.entries)}"
    assert registry.registry_hash, "Registry hash must not be empty"
    assert len(registry.registry_hash) == 16, "Registry hash must be 16 chars"


# ═══════════════════════════════════════════════════════════════════════
# Test 2: registry hash deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_registry_hash_deterministic():
    """Registry hash is deterministic across builds."""
    from v3.intake.tool_registry import build_registry_from_profiles

    hashes = set()
    for _ in range(5):
        registry = build_registry_from_profiles()
        hashes.add(registry.registry_hash)
    assert len(hashes) == 1, f"Registry hash not deterministic: {hashes}"


# ═══════════════════════════════════════════════════════════════════════
# Test 3: clone plan hash deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_clone_plan_hash_deterministic():
    """Clone plan hash is deterministic across builds."""
    from v3.intake.tool_registry import build_registry_from_profiles
    from v3.intake.clone_plan import create_clone_plan

    hashes = set()
    for _ in range(5):
        registry = build_registry_from_profiles()
        plan = create_clone_plan(registry)
        hashes.add(plan.plan_hash)
    assert len(hashes) == 1, f"Clone plan hash not deterministic: {hashes}"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: target paths use F:\Claude\Github
# ═══════════════════════════════════════════════════════════════════════

def test_target_paths_use_claude_github():
    """Clone-now target paths use F:/Claude/Github/."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    for entry in registry.entries:
        if entry.is_clone_now:
            assert "F:/Claude/Github" in entry.target_dir or "F:\\Claude\\Github" in entry.target_dir, \
                f"{entry.name}: target_dir '{entry.target_dir}' not in F:/Claude/Github"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Repomix use_mode direct_tool
# ═══════════════════════════════════════════════════════════════════════

def test_repomix_use_mode_direct_tool():
    """Repomix has use_mode direct_tool."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    repomix = None
    for e in registry.entries:
        if e.name == "Repomix":
            repomix = e
            break
    assert repomix is not None, "Repomix not found in registry"
    assert repomix.use_mode == "direct_tool", f"Expected direct_tool, got {repomix.use_mode}"
    assert repomix.is_clone_now, "Repomix should be clone_now"


# ═══════════════════════════════════════════════════════════════════════
# Test 6: ccusage use_mode direct_tool
# ═══════════════════════════════════════════════════════════════════════

def test_ccusage_use_mode_direct_tool():
    """ccusage has use_mode direct_tool."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    ccusage = None
    for e in registry.entries:
        if e.name == "ccusage":
            ccusage = e
            break
    assert ccusage is not None, "ccusage not found in registry"
    assert ccusage.use_mode == "direct_tool", f"Expected direct_tool, got {ccusage.use_mode}"
    assert ccusage.is_clone_now, "ccusage should be clone_now"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Anthropic Skills use_mode format_reference
# ═══════════════════════════════════════════════════════════════════════

def test_anthropic_skills_use_mode_format_reference():
    """Anthropic Skills has use_mode format_reference."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    ask = None
    for e in registry.entries:
        if e.name == "Anthropic Skills":
            ask = e
            break
    assert ask is not None, "Anthropic Skills not found in registry"
    assert ask.use_mode == "format_reference", f"Expected format_reference, got {ask.use_mode}"
    assert ask.is_clone_now, "Anthropic Skills should be clone_now (format ref)"


# ═══════════════════════════════════════════════════════════════════════
# Test 8: LangGraph use_mode architecture_reference
# ═══════════════════════════════════════════════════════════════════════

def test_langgraph_use_mode_architecture_reference():
    """LangGraph has use_mode architecture_reference."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    lg = None
    for e in registry.entries:
        if e.name == "LangGraph":
            lg = e
            break
    assert lg is not None, "LangGraph not found in registry"
    assert lg.use_mode == "architecture_reference", \
        f"Expected architecture_reference, got {lg.use_mode}"
    assert lg.is_reference_only, "LangGraph should be reference_only"


# ═══════════════════════════════════════════════════════════════════════
# Test 9: CrewAI use_mode architecture_reference
# ═══════════════════════════════════════════════════════════════════════

def test_crewai_use_mode_architecture_reference():
    """CrewAI has use_mode architecture_reference."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    crew = None
    for e in registry.entries:
        if e.name == "CrewAI":
            crew = e
            break
    assert crew is not None, "CrewAI not found in registry"
    assert crew.use_mode == "architecture_reference", \
        f"Expected architecture_reference, got {crew.use_mode}"


# ═══════════════════════════════════════════════════════════════════════
# Test 10: mem0 use_mode external_service
# ═══════════════════════════════════════════════════════════════════════

def test_mem0_use_mode_external_service():
    """mem0 has use_mode external_service."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    mem0 = None
    for e in registry.entries:
        if e.name == "mem0":
            mem0 = e
            break
    assert mem0 is not None, "mem0 not found in registry"
    assert mem0.use_mode == "external_service", \
        f"Expected external_service, got {mem0.use_mode}"
    assert mem0.is_external_eval, "mem0 should be external_eval"


# ═══════════════════════════════════════════════════════════════════════
# Test 11: Graphiti use_mode external_service
# ═══════════════════════════════════════════════════════════════════════

def test_graphiti_use_mode_external_service():
    """Graphiti has use_mode external_service."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    g = None
    for e in registry.entries:
        if e.name == "Graphiti":
            g = e
            break
    assert g is not None, "Graphiti not found in registry"
    assert g.use_mode == "external_service", \
        f"Expected external_service, got {g.use_mode}"


# ═══════════════════════════════════════════════════════════════════════
# Test 12: AppFlowy clone_now false (inspect_only)
# ═══════════════════════════════════════════════════════════════════════

def test_appflowy_not_clone_now():
    """AppFlowy is inspect_only despite DIRECT_CLONE decision."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    af = None
    for e in registry.entries:
        if e.name == "AppFlowy":
            af = e
            break
    assert af is not None, "AppFlowy not found in registry"
    assert af.decision == "DIRECT_CLONE", "AppFlowy baseline decision must be DIRECT_CLONE"
    assert af.use_mode == "source_reference", \
        f"Expected source_reference (inspect_only), got {af.use_mode}"
    assert not af.is_clone_now, "AppFlowy should NOT be clone_now despite DIRECT_CLONE"
    assert af.is_inspect_only, "AppFlowy should be inspect_only"


# ═══════════════════════════════════════════════════════════════════════
# Test 13: JupyterLab clone_now false (inspect_only)
# ═══════════════════════════════════════════════════════════════════════

def test_jupyterlab_not_clone_now():
    """JupyterLab is inspect_only despite DIRECT_CLONE decision."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    jl = None
    for e in registry.entries:
        if e.name == "JupyterLab":
            jl = e
            break
    assert jl is not None, "JupyterLab not found in registry"
    assert jl.decision == "DIRECT_CLONE", "JupyterLab baseline decision must be DIRECT_CLONE"
    assert jl.use_mode == "source_reference", \
        f"Expected source_reference (inspect_only), got {jl.use_mode}"
    assert not jl.is_clone_now, "JupyterLab should NOT be clone_now despite DIRECT_CLONE"
    assert jl.is_inspect_only, "JupyterLab should be inspect_only"


# ═══════════════════════════════════════════════════════════════════════
# Test 14: forbidden actions include do_not_integrate_into_kernel
# ═══════════════════════════════════════════════════════════════════════

def test_forbidden_actions_include_no_integration():
    """All entries with kernel_risk > 0 have do_not_integrate_into_kernel."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    for entry in registry.entries:
        assert "do_not_integrate_into_kernel" in entry.forbidden_actions, \
            f"{entry.name}: missing do_not_integrate_into_kernel in forbidden actions"
        assert "do_not_modify_kernel_boundary" in entry.forbidden_actions, \
            f"{entry.name}: missing do_not_modify_kernel_boundary in forbidden actions"


# ═══════════════════════════════════════════════════════════════════════
# Test 15: clone-list CLI does not clone
# ═══════════════════════════════════════════════════════════════════════

def test_clone_list_does_not_clone():
    """clone-list CLI command prints plan only, no git commands executed."""
    # Check that the CLI code does not import subprocess to run git
    cli_source = open(CLI_PATH, encoding="utf-8").read()

    # cmd_intake_clone_list must not call subprocess.run or os.system for git
    tree = ast.parse(cli_source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in ("system",), \
                    "clone-list should not call os.system()"
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    combo = f"{node.func.value.id}.{node.func.attr}"
                    assert combo not in ("subprocess.run", "subprocess.call", "os.system"), \
                        f"clone-list should not call {combo}"

    # Also verify by running the command
    result = _run_cli("intake", "clone-list")
    output = result.stdout + result.stderr
    assert "PLAN ONLY" in output, "clone-list must state PLAN ONLY"
    assert "git clone" in output.lower(), "clone-list should show git clone commands for reference"


# ═══════════════════════════════════════════════════════════════════════
# Test 16: clone-plan CLI writes reports
# ═══════════════════════════════════════════════════════════════════════

def test_clone_plan_cli_writes_reports():
    """clone-plan CLI writes both JSON and Markdown reports."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _run_cli("intake", "clone-plan", "--output-dir", tmpdir)

        json_path = os.path.join(tmpdir, "github_clone_plan.json")
        md_path = os.path.join(tmpdir, "github_clone_plan.md")

        assert os.path.exists(json_path), f"JSON not written: {json_path}"
        assert os.path.exists(md_path), f"Markdown not written: {md_path}"

        # Validate JSON structure
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "root_dir" in data
        assert "items" in data
        assert "plan_hash" in data
        assert "safety_notes" in data
        assert len(data["items"]) == 14

        # Validate Markdown content
        with open(md_path, encoding="utf-8") as f:
            md_content = f.read()
        assert "# SystemKernel" in md_content
        assert "Clone Plan" in md_content
        assert "PLAN ONLY" in md_content


# ═══════════════════════════════════════════════════════════════════════
# Test 17: registry CLI writes report
# ═══════════════════════════════════════════════════════════════════════

def test_registry_cli_writes_report():
    """registry CLI writes a valid JSON report."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "registry.json")
        result = _run_cli("intake", "registry", "--output", out_path)

        assert os.path.exists(out_path), f"Registry not written: {out_path}"

        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "entries" in data
        assert "registry_hash" in data
        assert "counts" in data
        assert len(data["entries"]) == 14


# ═══════════════════════════════════════════════════════════════════════
# Test 18: no network calls
# ═══════════════════════════════════════════════════════════════════════

def test_no_network_calls():
    """tool_registry.py and clone_plan.py make zero network calls."""
    import v3.intake.tool_registry as tr
    import v3.intake.clone_plan as cp

    for mod in (tr, cp):
        source = open(mod.__file__, encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in ("urllib", "requests", "httpx", "socket",
                                              "http.client", "aiohttp"), \
                        f"{mod.__file__}: imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0] not in (
                        "urllib", "requests", "httpx", "socket", "aiohttp"), \
                        f"{mod.__file__}: imports {node.module}"


# ═══════════════════════════════════════════════════════════════════════
# Test 19: no git commands
# ═══════════════════════════════════════════════════════════════════════

def test_no_git_commands():
    """tool_registry.py and clone_plan.py never invoke git."""
    import v3.intake.tool_registry as tr
    import v3.intake.clone_plan as cp

    for mod in (tr, cp):
        source = open(mod.__file__, encoding="utf-8").read()
        # No subprocess git calls
        assert "subprocess" not in source, \
            f"{mod.__file__}: should not import subprocess"
        # No os.system git calls
        assert "os.system" not in source, \
            f"{mod.__file__}: should not call os.system"
        assert "git clone" not in source.lower() or '"git clone"' in source.lower(), \
            f"{mod.__file__}: should not invoke git clone (only reference in strings)"


# ═══════════════════════════════════════════════════════════════════════
# Test 20: complexity gate not REJECT
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_gate_not_reject():
    """Complexity gate must not be REJECT after Phase 5E additions."""
    from v3.quality.phase_gate import evaluate_phase

    result = evaluate_phase("5E", v3_root=V3_ROOT)
    assert not result.verdict.is_rejected, \
        f"Complexity gate REJECTED: {result.verdict.reasons}"


# ═══════════════════════════════════════════════════════════════════════
# Test 21: existing repo intake tests still pass (via import check)
# ═══════════════════════════════════════════════════════════════════════

def test_repo_intake_imports_still_work():
    """All repo_intake functions still import correctly."""
    from v3.intake.repo_intake import (
        RepoIntakeInput, RepoSignals, RepoIntakeDecision, RepoIntakeReport,
        analyze_repo_snapshot, decide_repo_intake, compute_report_hash, write_report,
    )
    from v3.intake.rules import apply_rules, classify_repo_type, get_rules_table
    from v3.intake.repo_profiles import get_all_profiles, get_profile, list_profiles

    # Verify basic functionality still works
    profiles = get_all_profiles()
    assert len(profiles) == 14

    p = get_profile("Repomix")
    assert p is not None
    inp = p.to_input()
    signals = p.analyze()
    decision = decide_repo_intake(inp, signals)
    assert decision.decision == "DIRECT_CLONE"


# ═══════════════════════════════════════════════════════════════════════
# Test 22: kernel invariants still purity=100
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_invariants_import_chain():
    """Kernel boundary is not violated by new intake modules."""
    # intake/ modules must not import from kernel/
    import v3.intake.tool_registry as tr
    import v3.intake.clone_plan as cp

    for mod in (tr, cp):
        source = open(mod.__file__, encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("v3.kernel"), \
                        f"{mod.__file__}: imports from kernel: {node.module}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("v3.kernel"), \
                        f"{mod.__file__}: imports from kernel: {alias.name}"


# ═══════════════════════════════════════════════════════════════════════
# Test 23: ExternalToolEntry serialization
# ═══════════════════════════════════════════════════════════════════════

def test_entry_to_dict():
    """ExternalToolEntry.to_dict() produces complete dict."""
    from v3.intake.tool_registry import ExternalToolEntry

    entry = ExternalToolEntry(
        name="TestTool",
        repo_url="https://github.com/test/tool",
        decision="DIRECT_CLONE",
        priority="A",
        target_dir="F:/Claude/Github/test-tool",
        use_mode="direct_tool",
        allowed_actions=("clone_to_github", "run_locally_as_tool"),
        forbidden_actions=("do_not_integrate_into_kernel",),
        systemkernel_touchpoints=("cli_invocation",),
        claude_code_value=8.5,
        kernel_risk=1.0,
        notes="Test entry",
    )

    d = entry.to_dict()
    assert d["name"] == "TestTool"
    assert d["use_mode"] == "direct_tool"
    assert d["claude_code_value"] == 8.5
    assert "do_not_integrate_into_kernel" in d["forbidden_actions"]


# ═══════════════════════════════════════════════════════════════════════
# Test 24: ClonePlanItem serialization
# ═══════════════════════════════════════════════════════════════════════

def test_clone_plan_item_to_dict():
    """ClonePlanItem.to_dict() produces complete dict."""
    from v3.intake.clone_plan import ClonePlanItem

    item = ClonePlanItem(
        name="TestTool",
        repo_url="https://github.com/test/tool",
        target_path="F:/Claude/Github/test-tool",
        priority="A",
        clone_now=True,
        reason="Test reason",
        post_clone_action="run_cli_help",
        forbidden_post_clone_actions=("do_not_integrate_into_kernel",),
    )

    d = item.to_dict()
    assert d["name"] == "TestTool"
    assert d["clone_now"] is True
    assert d["post_clone_action"] == "run_cli_help"


# ═══════════════════════════════════════════════════════════════════════
# Test 25: filter_clone_now works
# ═══════════════════════════════════════════════════════════════════════

def test_filter_clone_now():
    """filter_clone_now returns only clone_now=True items."""
    from v3.intake.tool_registry import build_registry_from_profiles
    from v3.intake.clone_plan import create_clone_plan, filter_clone_now

    registry = build_registry_from_profiles()
    plan = create_clone_plan(registry)
    clone_now = filter_clone_now(plan)

    assert len(clone_now) > 0, "Should have at least one clone-now item"
    for item in clone_now:
        assert item.clone_now is True, f"{item.name}: clone_now must be True"
        assert item.target_path, f"{item.name}: must have target_path"


# ═══════════════════════════════════════════════════════════════════════
# Test 26: summarize_plan returns string
# ═══════════════════════════════════════════════════════════════════════

def test_summarize_plan():
    """summarize_plan returns a readable string."""
    from v3.intake.tool_registry import build_registry_from_profiles
    from v3.intake.clone_plan import create_clone_plan, summarize_plan

    registry = build_registry_from_profiles()
    plan = create_clone_plan(registry)
    summary = summarize_plan(plan)

    assert isinstance(summary, str)
    assert len(summary) > 100
    assert "Clone Plan Summary" in summary
    assert "F:/Claude/Github" in summary or "F:\\Claude\\Github" in summary


# ═══════════════════════════════════════════════════════════════════════
# Test 27: recommend_clone_order returns sorted list
# ═══════════════════════════════════════════════════════════════════════

def test_recommend_clone_order():
    """recommend_clone_order returns priority-sorted list."""
    from v3.intake.tool_registry import build_registry_from_profiles, recommend_clone_order

    registry = build_registry_from_profiles()
    order = recommend_clone_order(registry)

    assert len(order) > 0, "Should have at least one recommended clone"
    # First items should be highest priority
    assert isinstance(order, list)
    # Repomix and ccusage should be in the list
    clone_now_names = [e.name for e in registry.entries if e.is_clone_now]
    assert order == clone_now_names, \
        f"Clone order should include all clone-now entries in priority order"


# ═══════════════════════════════════════════════════════════════════════
# Test 28: ExternalToolRegistry to_dict and to_json
# ═══════════════════════════════════════════════════════════════════════

def test_registry_to_dict_and_json():
    """ExternalToolRegistry.to_dict() and to_json() work."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    d = registry.to_dict()
    assert "entries" in d
    assert "registry_hash" in d
    assert "counts" in d
    assert d["counts"]["total"] == 14

    j = registry.to_json()
    assert isinstance(j, str)
    parsed = json.loads(j)
    assert parsed["registry_hash"] == registry.registry_hash


# ═══════════════════════════════════════════════════════════════════════
# Test 29: ClonePlan to_dict and to_json
# ═══════════════════════════════════════════════════════════════════════

def test_clone_plan_to_dict_and_json():
    """ClonePlan.to_dict() and to_json() work."""
    from v3.intake.tool_registry import build_registry_from_profiles
    from v3.intake.clone_plan import create_clone_plan

    registry = build_registry_from_profiles()
    plan = create_clone_plan(registry)

    d = plan.to_dict()
    assert "root_dir" in d
    assert "items" in d
    assert "plan_hash" in d
    assert "safety_notes" in d
    assert d["summary"]["total"] == 14

    j = plan.to_json()
    assert isinstance(j, str)
    parsed = json.loads(j)
    assert parsed["plan_hash"] == plan.plan_hash


# ═══════════════════════════════════════════════════════════════════════
# Test 30: All entries have valid use_mode
# ═══════════════════════════════════════════════════════════════════════

def test_all_entries_have_valid_use_mode():
    """All registry entries have a valid use_mode."""
    from v3.intake.tool_registry import USE_MODES, build_registry_from_profiles

    registry = build_registry_from_profiles()
    for entry in registry.entries:
        assert entry.use_mode in USE_MODES, \
            f"{entry.name}: invalid use_mode '{entry.use_mode}'"


# ═══════════════════════════════════════════════════════════════════════
# Test 31: SuperClaude is inspect_only
# ═══════════════════════════════════════════════════════════════════════

def test_superclaude_inspect_only():
    """SuperClaude is inspect_only despite DIRECT_CLONE."""
    from v3.intake.tool_registry import build_registry_from_profiles

    registry = build_registry_from_profiles()
    sc = None
    for e in registry.entries:
        if e.name == "SuperClaude":
            sc = e
            break
    assert sc is not None, "SuperClaude not found in registry"
    assert sc.decision == "DIRECT_CLONE"
    assert sc.use_mode == "source_reference", \
        f"Expected source_reference, got {sc.use_mode}"
    assert sc.is_inspect_only, "SuperClaude should be inspect_only"


# ═══════════════════════════════════════════════════════════════════════
# Test 32: write_registry writes valid JSON
# ═══════════════════════════════════════════════════════════════════════

def test_write_registry_writes_valid_json():
    """write_registry produces readable, valid JSON."""
    from v3.intake.tool_registry import build_registry_from_profiles, write_registry

    registry = build_registry_from_profiles()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_registry.json")
        result_path = write_registry(registry, path)
        assert os.path.exists(result_path)

        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["registry_hash"] == registry.registry_hash
        assert len(data["entries"]) == 14


# ═══════════════════════════════════════════════════════════════════════
# Test 33: write_clone_plan writes valid JSON
# ═══════════════════════════════════════════════════════════════════════

def test_write_clone_plan_writes_valid_json():
    """write_clone_plan produces readable, valid JSON."""
    from v3.intake.tool_registry import build_registry_from_profiles, write_clone_plan

    registry = build_registry_from_profiles()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_clone_plan.json")
        result_path = write_clone_plan(registry, path)
        assert os.path.exists(result_path)

        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "root_dir" in data
        assert "plan_hash" in data
        assert len(data["items"]) == 14


# ═══════════════════════════════════════════════════════════════════════
# Bonus: CLI help shows new intake commands
# ═══════════════════════════════════════════════════════════════════════

def test_cli_help_shows_new_intake_commands():
    """CLI help shows registry, clone-plan, clone-list."""
    result = _run_cli("intake", "--help")
    output = result.stdout + result.stderr
    assert "registry" in output, "CLI help missing 'registry'"
    assert "clone-plan" in output, "CLI help missing 'clone-plan'"
    assert "clone-list" in output, "CLI help missing 'clone-list'"


# ═══════════════════════════════════════════════════════════════════════
# Bonus: No LLM/vector imports in new modules
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_imports_in_new_modules():
    """tool_registry.py and clone_plan.py have no banned imports."""
    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow",
    }

    import v3.intake.tool_registry as tr
    import v3.intake.clone_plan as cp

    for mod in (tr, cp):
        source = open(mod.__file__, encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in banned, \
                        f"{mod.__file__}: imports banned {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0] not in banned, \
                        f"{mod.__file__}: imports banned {node.module}"


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    """Run all external tool registry tests."""
    tests = [
        test_registry_builds_from_profiles,
        test_registry_hash_deterministic,
        test_clone_plan_hash_deterministic,
        test_target_paths_use_claude_github,
        test_repomix_use_mode_direct_tool,
        test_ccusage_use_mode_direct_tool,
        test_anthropic_skills_use_mode_format_reference,
        test_langgraph_use_mode_architecture_reference,
        test_crewai_use_mode_architecture_reference,
        test_mem0_use_mode_external_service,
        test_graphiti_use_mode_external_service,
        test_appflowy_not_clone_now,
        test_jupyterlab_not_clone_now,
        test_forbidden_actions_include_no_integration,
        test_clone_list_does_not_clone,
        test_clone_plan_cli_writes_reports,
        test_registry_cli_writes_report,
        test_no_network_calls,
        test_no_git_commands,
        test_complexity_gate_not_reject,
        test_repo_intake_imports_still_work,
        test_kernel_invariants_import_chain,
        test_entry_to_dict,
        test_clone_plan_item_to_dict,
        test_filter_clone_now,
        test_summarize_plan,
        test_recommend_clone_order,
        test_registry_to_dict_and_json,
        test_clone_plan_to_dict_and_json,
        test_all_entries_have_valid_use_mode,
        test_superclaude_inspect_only,
        test_write_registry_writes_valid_json,
        test_write_clone_plan_writes_valid_json,
        test_cli_help_shows_new_intake_commands,
        test_no_banned_imports_in_new_modules,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS  {test.__name__}")
        except Exception as e:
            failed += 1
            errors.append((test.__name__, str(e)))
            print(f"  FAIL  {test.__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{passed + failed} passed")

    if errors:
        print(f"\n  Failures:")
        for name, msg in errors:
            print(f"    {name}: {msg}")

    print(f"{'='*60}")
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all()
    if failed > 0:
        print(f"\n{paused}/{passed + failed} tests passed — SOME FAILED")
        sys.exit(1)
    else:
        print(f"\nAll {passed}/{passed + failed} tests passed.")
