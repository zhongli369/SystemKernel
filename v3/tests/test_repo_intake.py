"""
Repo Intake Tests — Phase 5D.

Comprehensive tests for:
  1. Synthetic CLI repo → DIRECT_CLONE
  2. LLM-heavy repo → EXTERNAL_EXTENSION
  3. No-license → maintenance risk penalty
  4. Docs-only → ARCHITECTURE_REFERENCE
  5. Banned dep → purity risk
  6. MCP signal → CC value boost
  7. Skill manifest → SK value boost
  8. Hash deterministic
  9. write_report round-trip
  10. All 14 profiles load
  11. All profiles produce valid decisions
  12-18. Specific expected decisions (7 repos)
  19-21. CLI intake commands
  22. No network access
  23. No banned imports in intake/
  24. Complexity gate not REJECT
  25. Rules match scoring engine
  26. Repo type classification
  27. Report hash stability
  28. Decision to_dict

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import ast
import subprocess
import tempfile

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

_v3_root = os.path.join(_root, "v3")
_python = sys.executable
_cli_path = os.path.join(_v3_root, "cli", "systemkernel.py")


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_input(name="test-repo", url="https://github.com/test/repo",
                path="", category="", intended="unknown") -> "RepoIntakeInput":
    from v3.intake.repo_intake import RepoIntakeInput
    return RepoIntakeInput(
        name=name, url=url, local_path=path,
        category_hint=category, intended_use=intended,
    )


def _make_signals(**kwargs) -> "RepoSignals":
    from v3.intake.repo_intake import RepoSignals
    defaults = {
        "has_readme": True, "has_license": True,
        "has_cli": True, "has_tests": True,
    }
    defaults.update(kwargs)
    return RepoSignals(**defaults)


def _decide(inp, signals) -> "RepoIntakeDecision":
    from v3.intake.repo_intake import decide_repo_intake
    return decide_repo_intake(inp, signals)


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Synthetic CLI repo → DIRECT_CLONE
# ═══════════════════════════════════════════════════════════════════════

def test_cli_repo_direct_clone():
    """A clean CLI tool with docs should be DIRECT_CLONE."""
    inp = _make_input(name="my-cli", intended="claude_code_enhancement")
    signals = _make_signals(
        has_readme=True, has_license=True, has_cli=True,
        has_tests=True, has_docs=True, has_examples=True,
    )
    decision = _decide(inp, signals)
    assert decision.decision == "DIRECT_CLONE", \
        f"Expected DIRECT_CLONE, got {decision.decision}"
    assert decision.priority in ("S", "A")
    assert decision.claude_code_value_score >= 7.0


# ═══════════════════════════════════════════════════════════════════════
# Test 2: LLM dep → EXTERNAL_EXTENSION
# ═══════════════════════════════════════════════════════════════════════

def test_llm_dep_external_extension():
    """Repos with LLM SDK deps should be EXTERNAL_EXTENSION."""
    inp = _make_input(name="llm-tool")
    signals = _make_signals(
        has_readme=True, has_license=True,
        llm_dependency_hits=1,
    )
    decision = _decide(inp, signals)
    assert decision.decision == "EXTERNAL_EXTENSION", \
        f"Expected EXTERNAL_EXTENSION, got {decision.decision}"


# ═══════════════════════════════════════════════════════════════════════
# Test 3: No-license → maintenance risk penalty
# ═══════════════════════════════════════════════════════════════════════

def test_no_license_penalty():
    """Missing license should increase maintenance risk."""
    inp = _make_input(name="no-license")
    signals_no_lic = _make_signals(has_license=False)
    signals_with_lic = _make_signals(has_license=True)

    d_no = _decide(inp, signals_no_lic)
    d_yes = _decide(inp, signals_with_lic)

    assert d_no.maintenance_risk_score > d_yes.maintenance_risk_score, \
        f"No-license risk ({d_no.maintenance_risk_score}) should exceed licensed risk ({d_yes.maintenance_risk_score})"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Docs-only repo → ARCHITECTURE_REFERENCE (no code signals)
# ═══════════════════════════════════════════════════════════════════════

def test_docs_only_architecture_reference():
    """A repo with only a README and no code should not be cloned."""
    inp = _make_input(name="awesome-list")
    signals = _make_signals(has_readme=True, has_license=False, has_cli=False,
                            has_tests=False, has_docs=False, has_examples=False)
    decision = _decide(inp, signals)
    # No license → can't be DIRECT_CLONE. No risky deps → not rejected.
    # Falls through to ARCHITECTURE_REFERENCE.
    assert decision.decision in ("ARCHITECTURE_REFERENCE", "REJECT"), \
        f"Expected ARCHITECTURE_REFERENCE or REJECT, got {decision.decision}"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Banned dep → purity risk
# ═══════════════════════════════════════════════════════════════════════

def test_banned_dep_purity_risk():
    """Banned dependencies should increase purity risk score."""
    inp = _make_input(name="banned-tool")
    clean = _make_signals()
    dirty = _make_signals(banned_dependency_hits=2)

    d_clean = _decide(inp, clean)
    d_dirty = _decide(inp, dirty)

    assert d_dirty.purity_risk_score > d_clean.purity_risk_score, \
        f"Banned deps should increase purity risk: {d_dirty.purity_risk_score} > {d_clean.purity_risk_score}"
    assert d_dirty.decision == "ARCHITECTURE_REFERENCE", \
        f"Banned deps should trigger ARCHITECTURE_REFERENCE, got {d_dirty.decision}"


# ═══════════════════════════════════════════════════════════════════════
# Test 6: MCP signal → CC value boost
# ═══════════════════════════════════════════════════════════════════════

def test_mcp_cc_value_boost():
    """MCP integration should boost Claude Code value."""
    inp = _make_input(name="mcp-server")
    # Use sparse signals so cc_value isn't already capped at 10
    without_mcp = _make_signals(has_readme=True, has_license=True, has_mcp=False,
                                has_cli=False, has_tests=False, has_docs=False,
                                has_examples=False)
    with_mcp = _make_signals(has_readme=True, has_license=True, has_mcp=True,
                             has_cli=False, has_tests=False, has_docs=False,
                             has_examples=False)

    d_no = _decide(inp, without_mcp)
    d_yes = _decide(inp, with_mcp)

    assert d_yes.claude_code_value_score > d_no.claude_code_value_score, \
        f"MCP should boost CC value: {d_yes.claude_code_value_score} > {d_no.claude_code_value_score}"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Skill manifest → SK value boost
# ═══════════════════════════════════════════════════════════════════════

def test_skill_manifest_value():
    """Skill manifest should boost SystemKernel value."""
    inp = _make_input(name="skill-tool")
    # Use sparse signals so values aren't already capped
    without_skill = _make_signals(has_readme=True, has_license=True,
                                  has_skill_manifest=False, has_cli=False,
                                  has_tests=False, has_docs=False, has_examples=False)
    with_skill = _make_signals(has_readme=True, has_license=True,
                               has_skill_manifest=True, has_cli=False,
                               has_tests=False, has_docs=False, has_examples=False)

    d_no = _decide(inp, without_skill)
    d_yes = _decide(inp, with_skill)

    assert d_yes.claude_code_value_score > d_no.claude_code_value_score, \
        f"Skill manifest should boost CC value: {d_yes.claude_code_value_score} > {d_no.claude_code_value_score}"


# ═══════════════════════════════════════════════════════════════════════
# Test 8: Hash deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_hash_deterministic():
    """Same input + signals + decision → same hash."""
    from v3.intake.repo_intake import compute_report_hash

    inp = _make_input("test")
    signals = _make_signals()
    decision = _decide(inp, signals)

    h1 = compute_report_hash(inp, signals, decision)
    h2 = compute_report_hash(inp, signals, decision)

    assert h1 == h2, f"Hash should be deterministic: {h1} != {h2}"
    assert len(h1) == 16, f"Hash should be 16 chars, got {len(h1)}: {h1}"


# ═══════════════════════════════════════════════════════════════════════
# Test 9: write_report round-trip
# ═══════════════════════════════════════════════════════════════════════

def test_write_report_roundtrip():
    """Write report → read back → verify content."""
    from v3.intake.repo_intake import (
        RepoIntakeReport, write_report, compute_report_hash,
    )

    inp = _make_input("roundtrip")
    signals = _make_signals()
    decision = _decide(inp, signals)
    rh = compute_report_hash(inp, signals, decision)
    report = RepoIntakeReport(input=inp, signals=signals,
                              decision=decision, report_hash=rh)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name

    try:
        written = write_report(report, tmp_path)
        assert os.path.exists(written)

        with open(written, encoding="utf-8") as f:
            data = json.load(f)
        assert data["input"]["name"] == "roundtrip"
        assert data["decision"]["decision"] == "DIRECT_CLONE"
        assert data["report_hash"] == rh
    finally:
        os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════
# Test 10: All 14 profiles load
# ═══════════════════════════════════════════════════════════════════════

def test_all_profiles_load():
    """All 14 pre-built profiles must be loadable."""
    from v3.intake.repo_profiles import get_all_profiles

    profiles = get_all_profiles()
    assert len(profiles) == 14, f"Expected 14 profiles, got {len(profiles)}"

    names = {p.name for p in profiles}
    expected_names = {
        "LangGraph", "CrewAI", "OpenAI Swarm", "Anthropic Skills",
        "mem0", "Graphiti", "Repomix", "ccusage", "Continue",
        "AppFlowy", "JupyterLab", "SuperClaude",
        "awesome-claude-code", "Awesome-Prompt-Engineering",
    }
    assert names == expected_names, f"Missing profiles: {expected_names - names}"


# ═══════════════════════════════════════════════════════════════════════
# Test 11: All profiles produce valid decisions
# ═══════════════════════════════════════════════════════════════════════

def test_all_profiles_produce_decisions():
    """Every profile must produce a valid decision matching its expected_decision."""
    from v3.intake.repo_profiles import get_all_profiles
    from v3.intake.repo_intake import decide_repo_intake, DECISIONS

    for p in get_all_profiles():
        inp = p.to_input()
        signals = p.analyze()
        decision = decide_repo_intake(inp, signals)

        assert decision.decision in DECISIONS, \
            f"{p.name}: invalid decision '{decision.decision}'"
        assert decision.decision == p.expected_decision, \
            f"{p.name}: expected {p.expected_decision}, got {decision.decision}"
        assert 0.0 <= decision.final_score <= 10.0, \
            f"{p.name}: score {decision.final_score} out of range"
        assert decision.priority in ("S", "A", "B", "C", "D"), \
            f"{p.name}: invalid priority '{decision.priority}'"


# ═══════════════════════════════════════════════════════════════════════
# Test 12-18: Specific expected decisions
# ═══════════════════════════════════════════════════════════════════════

def _assert_profile_decision(name, expected):
    from v3.intake.repo_profiles import get_profile
    from v3.intake.repo_intake import decide_repo_intake

    p = get_profile(name)
    assert p is not None, f"Profile not found: {name}"
    d = decide_repo_intake(p.to_input(), p.analyze())
    assert d.decision == expected, \
        f"{name}: expected {expected}, got {d.decision} (reasons: {d.reasons})"


def test_repomix_direct_clone():
    _assert_profile_decision("Repomix", "DIRECT_CLONE")


def test_ccusage_direct_clone():
    _assert_profile_decision("ccusage", "DIRECT_CLONE")


def test_langgraph_architecture_reference():
    _assert_profile_decision("LangGraph", "ARCHITECTURE_REFERENCE")


def test_crewai_architecture_reference():
    _assert_profile_decision("CrewAI", "ARCHITECTURE_REFERENCE")


def test_mem0_external_extension():
    _assert_profile_decision("mem0", "EXTERNAL_EXTENSION")


def test_graphiti_external_extension():
    _assert_profile_decision("Graphiti", "EXTERNAL_EXTENSION")


def test_anthropic_skills_direct_clone():
    _assert_profile_decision("Anthropic Skills", "DIRECT_CLONE")


# ═══════════════════════════════════════════════════════════════════════
# Test 19: CLI intake list
# ═══════════════════════════════════════════════════════════════════════

def test_cli_intake_list():
    """CLI intake list must exit 0 and show all 14 profiles."""
    result = subprocess.run(
        [_python, _cli_path, "intake", "list"],
        capture_output=True, text=True, timeout=60,
        cwd=_root,
    )
    assert result.returncode == 0, f"CLI intake list failed: {result.stderr[:300]}"
    assert "Total: 14 profiles" in result.stdout
    assert "Repomix" in result.stdout
    assert "LangGraph" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 20: CLI intake profile
# ═══════════════════════════════════════════════════════════════════════

def test_cli_intake_profile():
    """CLI intake profile <name> must show detailed assessment."""
    result = subprocess.run(
        [_python, _cli_path, "intake", "profile", "Repomix"],
        capture_output=True, text=True, timeout=60,
        cwd=_root,
    )
    assert result.returncode == 0
    assert "Repomix" in result.stdout
    assert "DIRECT_CLONE" in result.stdout
    assert "CC Value" in result.stdout
    assert "Purity Risk" in result.stdout


def test_cli_intake_profile_unknown():
    """CLI intake profile with unknown name must exit non-zero."""
    result = subprocess.run(
        [_python, _cli_path, "intake", "profile", "NonexistentRepo"],
        capture_output=True, text=True, timeout=60,
        cwd=_root,
    )
    assert result.returncode != 0
    assert "Unknown profile" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test 21: CLI intake summarize
# ═══════════════════════════════════════════════════════════════════════

def test_cli_intake_summarize():
    """CLI intake summarize must show all decisions and distribution."""
    result = subprocess.run(
        [_python, _cli_path, "intake", "summarize"],
        capture_output=True, text=True, timeout=60,
        cwd=_root,
    )
    assert result.returncode == 0
    assert "Decision Distribution" in result.stdout
    assert "DIRECT_CLONE Candidates" in result.stdout
    assert "Total: 14 profiles" in result.stdout
    # Should NOT have mismatches
    assert "MISMATCH" not in result.stdout, \
        f"Unexpected mismatches in summarize:\n{result.stdout}"


# ═══════════════════════════════════════════════════════════════════════
# Test 22: No network access in intake modules
# ═══════════════════════════════════════════════════════════════════════

def test_no_network_imports():
    """Intake modules must not import network libraries."""
    network_modules = {"urllib", "requests", "httpx", "aiohttp", "socket",
                       "http.client", "http.server", "smtplib", "ftplib"}
    intake_dir = os.path.join(_v3_root, "intake")
    violations = []
    for fname in os.listdir(intake_dir):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(intake_dir, fname)
        with open(fpath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in network_modules:
                        violations.append(f"{fname}: imports {name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    if name in network_modules:
                        violations.append(f"{fname}: imports {name}")

    assert len(violations) == 0, f"Network imports detected: {violations}"


# ═══════════════════════════════════════════════════════════════════════
# Test 23: No banned imports in intake/
# ═══════════════════════════════════════════════════════════════════════

def test_no_banned_imports_in_intake():
    """Intake modules must not import banned LLM/vector packages."""
    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "sklearn", "scipy",
    }
    intake_dir = os.path.join(_v3_root, "intake")
    violations = []
    for fname in os.listdir(intake_dir):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(intake_dir, fname)
        with open(fpath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in banned:
                        violations.append(f"{fname}: imports {name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split(".")[0]
                    if name in banned:
                        violations.append(f"{fname}: imports {name}")

    assert len(violations) == 0, f"Banned imports in intake/: {violations}"


# ═══════════════════════════════════════════════════════════════════════
# Test 24: Complexity gate not REJECT
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_gate_not_reject():
    """Complexity gate must not become REJECT after Phase 5D."""
    from v3.quality.phase_gate import evaluate_phase
    result = evaluate_phase("5D", v3_root=_v3_root)
    assert result.verdict.verdict != "REJECT", \
        f"Gate REJECTED: {result.verdict.reasons}"


# ═══════════════════════════════════════════════════════════════════════
# Test 25: Rules match scoring engine
# ═══════════════════════════════════════════════════════════════════════

def test_rules_match_scoring_engine():
    """Rule-based classification must match numeric scoring for all profiles."""
    from v3.intake.repo_profiles import get_all_profiles
    from v3.intake.repo_intake import decide_repo_intake
    from v3.intake.rules import apply_rules

    for p in get_all_profiles():
        inp = p.to_input()
        signals = p.analyze()
        scoring_decision = decide_repo_intake(inp, signals).decision
        rule_decision, rule_id = apply_rules(inp, signals)

        assert scoring_decision == rule_decision, \
            f"{p.name}: scoring={scoring_decision}, rules={rule_decision} (rule {rule_id})"


# ═══════════════════════════════════════════════════════════════════════
# Test 26: Repo type classification
# ═══════════════════════════════════════════════════════════════════════

def test_repo_type_classification():
    """classify_repo_type must correctly categorize repos."""
    from v3.intake.rules import classify_repo_type
    from v3.intake.repo_intake import RepoSignals

    # Agent runtime (framework deps)
    sig = RepoSignals(framework_dependency_hits=1)
    assert classify_repo_type(sig) == "agent_runtime"

    # Memory system (memory deps)
    sig = RepoSignals(memory_dependency_hits=1)
    assert classify_repo_type(sig) == "memory_system"

    # Claude Code extension (MCP)
    sig = RepoSignals(has_mcp=True)
    assert classify_repo_type(sig) == "claude_code_extension"

    # Skill system (skill manifest)
    sig = RepoSignals(has_skill_manifest=True)
    assert classify_repo_type(sig) == "skill_system"

    # Docs only
    sig = RepoSignals(has_readme=True, has_cli=False,
                      language_hints=(), dependency_files=())
    assert classify_repo_type(sig) == "docs_only"

    # Unknown
    sig = RepoSignals()
    assert classify_repo_type(sig) == "unknown"


# ═══════════════════════════════════════════════════════════════════════
# Test 27: Report hash changes with different inputs
# ═══════════════════════════════════════════════════════════════════════

def test_report_hash_uniqueness():
    """Different inputs should produce different hashes."""
    from v3.intake.repo_intake import compute_report_hash

    inp1 = _make_input("a")
    inp2 = _make_input("b")
    signals = _make_signals()
    d1 = _decide(inp1, signals)
    d2 = _decide(inp2, signals)

    h1 = compute_report_hash(inp1, signals, d1)
    h2 = compute_report_hash(inp2, signals, d2)

    assert h1 != h2, f"Different inputs should produce different hashes: {h1} == {h2}"


# ═══════════════════════════════════════════════════════════════════════
# Test 28: Decision to_dict completeness
# ═══════════════════════════════════════════════════════════════════════

def test_decision_to_dict():
    """RepoIntakeDecision.to_dict must include all fields."""
    from v3.intake.repo_intake import decide_repo_intake

    inp = _make_input("complete")
    signals = _make_signals()
    d = decide_repo_intake(inp, signals)
    dd = d.to_dict()

    required = [
        "decision", "priority", "claude_code_value_score",
        "systemkernel_value_score", "complexity_risk_score",
        "purity_risk_score", "maintenance_risk_score", "final_score",
        "reasons", "recommended_target_dir", "allowed_actions", "forbidden_actions",
    ]
    for key in required:
        assert key in dd, f"Missing key '{key}' in decision.to_dict()"


# ═══════════════════════════════════════════════════════════════════════
# Test 29: analyze_repo_snapshot with empty files
# ═══════════════════════════════════════════════════════════════════════

def test_analyze_empty_snapshot():
    """Empty snapshot should produce default signals."""
    from v3.intake.repo_intake import analyze_repo_snapshot

    signals = analyze_repo_snapshot("empty", "https://example.com", {})
    assert not signals.has_readme
    assert not signals.has_license
    assert signals.banned_dependency_hits == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 30: Framework dep → ARCHITECTURE_REFERENCE
# ═══════════════════════════════════════════════════════════════════════

def test_framework_dep_architecture_reference():
    """Framework dependency must trigger ARCHITECTURE_REFERENCE."""
    inp = _make_input(name="framework-tool")
    signals = _make_signals(
        has_readme=True, has_license=True,
        framework_dependency_hits=1,
    )
    decision = _decide(inp, signals)
    assert decision.decision == "ARCHITECTURE_REFERENCE", \
        f"Expected ARCHITECTURE_REFERENCE for framework dep, got {decision.decision}"


# ═══════════════════════════════════════════════════════════════════════
# Bonus tests
# ═══════════════════════════════════════════════════════════════════════

def test_intake_input_to_dict():
    """RepoIntakeInput.to_dict must be complete."""
    inp = _make_input("test-dict", "https://github.com/x/y", "/tmp/x", "tool", "claude_code_enhancement")
    d = inp.to_dict()
    assert d["name"] == "test-dict"
    assert d["url"] == "https://github.com/x/y"


def test_signals_to_dict():
    """RepoSignals.to_dict must be complete."""
    signals = _make_signals()
    d = signals.to_dict()
    assert "has_readme" in d
    assert "banned_dependency_hits" in d
    assert isinstance(d["language_hints"], list)


def test_decision_properties():
    """Decision boolean properties must work."""
    from v3.intake.repo_intake import (
        DECISION_DIRECT_CLONE, DECISION_EXTERNAL_EXTENSION,
        DECISION_ARCHITECTURE_REFERENCE, DECISION_REJECT,
        RepoIntakeDecision,
    )

    d = RepoIntakeDecision(decision=DECISION_DIRECT_CLONE)
    assert d.is_direct_clone
    assert not d.is_external
    assert not d.is_reference
    assert not d.is_rejected

    d2 = RepoIntakeDecision(decision=DECISION_REJECT)
    assert d2.is_rejected


def test_get_rules_table():
    """get_rules_table must return all 9 rules."""
    from v3.intake.rules import get_rules_table
    rules = get_rules_table()
    assert len(rules) == 9, f"Expected 9 rules, got {len(rules)}"
    assert all("rule_id" in r and "decision" in r for r in rules)


def test_cli_help_shows_intake():
    """CLI --help must show intake subcommand."""
    result = subprocess.run(
        [_python, _cli_path, "--help"],
        capture_output=True, text=True, timeout=60,
        cwd=_root,
    )
    assert result.returncode == 0
    assert "intake" in result.stdout


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    tests = [
        ("CLI repo → DIRECT_CLONE", test_cli_repo_direct_clone),
        ("LLM dep → EXTERNAL_EXTENSION", test_llm_dep_external_extension),
        ("No-license → maintenance penalty", test_no_license_penalty),
        ("Docs-only → ARCHITECTURE_REFERENCE", test_docs_only_architecture_reference),
        ("Banned dep → purity risk", test_banned_dep_purity_risk),
        ("MCP signal → CC value boost", test_mcp_cc_value_boost),
        ("Skill manifest → value boost", test_skill_manifest_value),
        ("Hash deterministic", test_hash_deterministic),
        ("write_report round-trip", test_write_report_roundtrip),
        ("All 14 profiles load", test_all_profiles_load),
        ("All profiles produce decisions", test_all_profiles_produce_decisions),
        ("Repomix → DIRECT_CLONE", test_repomix_direct_clone),
        ("ccusage → DIRECT_CLONE", test_ccusage_direct_clone),
        ("LangGraph → ARCHITECTURE_REFERENCE", test_langgraph_architecture_reference),
        ("CrewAI → ARCHITECTURE_REFERENCE", test_crewai_architecture_reference),
        ("mem0 → EXTERNAL_EXTENSION", test_mem0_external_extension),
        ("Graphiti → EXTERNAL_EXTENSION", test_graphiti_external_extension),
        ("Anthropic Skills → DIRECT_CLONE", test_anthropic_skills_direct_clone),
        ("CLI intake list", test_cli_intake_list),
        ("CLI intake profile", test_cli_intake_profile),
        ("CLI intake profile unknown", test_cli_intake_profile_unknown),
        ("CLI intake summarize", test_cli_intake_summarize),
        ("No network imports", test_no_network_imports),
        ("No banned imports in intake/", test_no_banned_imports_in_intake),
        ("Complexity gate not REJECT", test_complexity_gate_not_reject),
        ("Rules match scoring engine", test_rules_match_scoring_engine),
        ("Repo type classification", test_repo_type_classification),
        ("Report hash uniqueness", test_report_hash_uniqueness),
        ("Decision to_dict complete", test_decision_to_dict),
        ("Empty snapshot analysis", test_analyze_empty_snapshot),
        ("Framework dep → ARCHITECTURE_REFERENCE", test_framework_dep_architecture_reference),
        ("Input to_dict", test_intake_input_to_dict),
        ("Signals to_dict", test_signals_to_dict),
        ("Decision properties", test_decision_properties),
        ("get_rules_table", test_get_rules_table),
        ("CLI help shows intake", test_cli_help_shows_intake),
    ]

    print("=" * 60)
    print("  SystemKernel v3.0 — Repo Intake Tests (Phase 5D)")
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
