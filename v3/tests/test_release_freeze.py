"""
Release Freeze Tests — Phase 5F.

Tests for:
  - Validation matrix building and determinism
  - Project inventory building and determinism
  - Release notes generation
  - All subsystems present
  - Invariants maintained (no network, no clone, purity=100, memory removable)
  - Regression: existing test suites still pass
"""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile


# ═══════════════════════════════════════════════════════════════════════
# Path setup
# ═══════════════════════════════════════════════════════════════════════

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(V3_ROOT, "exports")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Validation matrix builds
# ═══════════════════════════════════════════════════════════════════════

def test_validation_matrix_builds():
    """Validation matrix builds successfully."""
    from v3.release.validation_matrix import build_validation_matrix

    matrix = build_validation_matrix()
    assert matrix.total > 0, "Matrix should have checks"
    assert matrix.total >= 38, f"Expected >=38 checks, got {matrix.total}"
    assert matrix.matrix_hash, "Matrix hash must not be empty"
    assert len(matrix.matrix_hash) == 16, "Matrix hash must be 16 chars"


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Validation matrix hash deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_validation_matrix_hash_deterministic():
    """Validation matrix hash is deterministic."""
    from v3.release.validation_matrix import build_validation_matrix

    hashes = set()
    for _ in range(5):
        matrix = build_validation_matrix()
        hashes.add(matrix.matrix_hash)
    assert len(hashes) == 1, f"Matrix hash not deterministic: {hashes}"


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Release inventory builds
# ═══════════════════════════════════════════════════════════════════════

def test_release_inventory_builds():
    """Release inventory builds with entries across all subsystems."""
    from v3.release.inventory import build_inventory

    inv = build_inventory()
    assert inv.release_version == "3.0.0"
    assert len(inv.entries) > 50, f"Expected >50 entries, got {len(inv.entries)}"
    assert inv.release_hash, "Inventory hash must not be empty"

    # Must have all required subsystems
    subsystems = set(e.subsystem for e in inv.entries)
    required = {"kernel", "memory", "quality", "intake", "cli", "tests", "exports"}
    missing = required - subsystems
    assert not missing, f"Missing subsystems: {missing}"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Inventory hash deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_hash_deterministic():
    """Inventory hash is deterministic."""
    from v3.release.inventory import build_inventory

    hashes = set()
    for _ in range(5):
        inv = build_inventory()
        hashes.add(inv.release_hash)
    assert len(hashes) == 1, f"Inventory hash not deterministic: {hashes}"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Release notes generated
# ═══════════════════════════════════════════════════════════════════════

def test_release_notes_generated():
    """Release notes are generated and contain key sections."""
    from v3.release.release_notes import generate_release_notes

    notes = generate_release_notes()
    assert isinstance(notes, str)
    assert len(notes) > 1000, "Release notes should be substantial"

    required_sections = [
        "What Is SystemKernel",
        "Completed Phases",
        "Major Capabilities",
        "What Is Intentionally NOT Included",
        "Safety Invariants",
        "Known Limitations",
        "Upgrade Policy",
    ]
    for section in required_sections:
        assert section in notes, f"Release notes missing section: {section}"


# ═══════════════════════════════════════════════════════════════════════
# Test 6: All required subsystems present in validation
# ═══════════════════════════════════════════════════════════════════════

def test_validation_all_subsystems_present():
    """Validation matrix covers all 10 subsystems."""
    from v3.release.validation_matrix import build_validation_matrix, VALIDATION_CATEGORIES

    matrix = build_validation_matrix()
    categories_found = set(c.category for c in matrix.checks)

    for cat in VALIDATION_CATEGORIES:
        assert cat in categories_found, f"Validation missing category: {cat}"


# ═══════════════════════════════════════════════════════════════════════
# Test 7: All required test suites listed in inventory
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_lists_test_suites():
    """Inventory lists all test suites."""
    from v3.release.inventory import build_inventory

    inv = build_inventory()
    test_entries = [e for e in inv.entries if e.kind == "test"]

    required_tests = [
        "test_kernel_invariants",
        "test_event_runtime",
        "test_checkpoint_runtime",
        "test_observability_graph",
        "test_memory_runtime_finalization",
        "test_complexity_budget",
        "test_golden_path",
        "test_repo_intake",
        "test_external_tool_registry",
        "test_developer_cli",
    ]
    test_paths = [e.path for e in test_entries]
    for req in required_tests:
        found = any(req in tp for tp in test_paths)
        assert found, f"Inventory missing test suite: {req}"


# ═══════════════════════════════════════════════════════════════════════
# Test 8: All required reports listed in inventory
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_lists_reports():
    """Inventory lists key export reports."""
    from v3.release.inventory import build_inventory

    inv = build_inventory()
    report_entries = [e for e in inv.entries if e.kind in ("report_json", "report_markdown")]

    required_reports = [
        "kernel_validity_report.json",
        "memory_system_report.json",
        "complexity_budget_report.json",
        "external_tool_registry.json",
        "github_clone_plan.json",
        "github_clone_plan.md",
    ]
    report_paths = [e.path for e in report_entries]
    for req in required_reports:
        found = any(req in rp for rp in report_paths)
        assert found, f"Inventory missing report: {req}"


# ═══════════════════════════════════════════════════════════════════════
# Test 9: CLI commands listed in inventory
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_lists_cli_commands():
    """Inventory lists CLI commands."""
    from v3.release.inventory import build_inventory

    inv = build_inventory()
    cli_entries = [e for e in inv.entries if e.kind == "cli_command"]

    required_commands = ["status", "quality", "doctor", "intake"]
    cli_names = [e.description for e in cli_entries]
    for req in required_commands:
        found = any(req in cn for cn in cli_names)
        assert found, f"Inventory missing CLI command: {req}"


# ═══════════════════════════════════════════════════════════════════════
# Test 10: Invariants listed in inventory
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_lists_invariants():
    """Inventory lists system invariants."""
    from v3.release.inventory import build_inventory

    inv = build_inventory()
    invariant_entries = [e for e in inv.entries if e.kind == "invariant"]

    # Should have at least a few invariants
    assert len(invariant_entries) > 0, "Inventory should list invariants"


# ═══════════════════════════════════════════════════════════════════════
# Test 11: External registry entries listed in inventory
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_lists_registry_entries():
    """Inventory lists external tool registry entries."""
    from v3.release.inventory import build_inventory

    inv = build_inventory()
    reg_entries = [e for e in inv.entries if e.subsystem == "external_registry"]

    assert len(reg_entries) == 14, \
        f"Expected 14 registry entries, got {len(reg_entries)}"


# ═══════════════════════════════════════════════════════════════════════
# Test 12: No release check introduces network
# ═══════════════════════════════════════════════════════════════════════

def test_release_no_network_imports():
    """Release modules have no network imports."""
    import v3.release.validation_matrix as vm
    import v3.release.inventory as inv
    import v3.release.release_notes as rn

    net_imports = {"urllib", "requests", "httpx", "socket", "aiohttp"}

    for mod in (vm, inv, rn):
        source = open(mod.__file__, encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in net_imports, \
                        f"{mod.__file__}: imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0] not in net_imports, \
                        f"{mod.__file__}: imports {node.module}"


# ═══════════════════════════════════════════════════════════════════════
# Test 13: No release check introduces clone
# ═══════════════════════════════════════════════════════════════════════

def test_release_no_git_commands():
    """Release modules do not invoke git."""
    import v3.release.validation_matrix as vm
    import v3.release.inventory as inv
    import v3.release.release_notes as rn

    for mod in (vm, inv, rn):
        source = open(mod.__file__, encoding="utf-8").read()
        assert "subprocess" not in source, \
            f"{mod.__file__}: should not import subprocess"
        assert "os.system" not in source, \
            f"{mod.__file__}: should not call os.system"


# ═══════════════════════════════════════════════════════════════════════
# Test 14: Complexity gate not REJECT
# ═══════════════════════════════════════════════════════════════════════

def test_complexity_gate_not_reject():
    """Complexity gate must not be REJECT after Phase 5F."""
    from v3.quality.phase_gate import evaluate_phase

    result = evaluate_phase("5F", v3_root=V3_ROOT)
    assert not result.verdict.is_rejected, \
        f"Complexity gate REJECTED: {result.verdict.reasons}"


# ═══════════════════════════════════════════════════════════════════════
# Test 15: Kernel purity remains 100
# ═══════════════════════════════════════════════════════════════════════

def test_kernel_purity_remains_100():
    """Kernel purity must remain 100/100."""
    kernel_report_path = os.path.join(EXPORTS_DIR, "kernel_validity_report.json")
    if os.path.exists(kernel_report_path):
        with open(kernel_report_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("purity_score", 0) == 100, \
            f"Kernel purity is {data.get('purity_score')}, expected 100"


# ═══════════════════════════════════════════════════════════════════════
# Test 16: Memory removable remains YES
# ═══════════════════════════════════════════════════════════════════════

def test_memory_removable_remains_yes():
    """Memory must remain removable."""
    mem_report_path = os.path.join(EXPORTS_DIR, "memory_system_report.json")
    if os.path.exists(mem_report_path):
        with open(mem_report_path, encoding="utf-8") as f:
            data = json.load(f)
        removable = data.get("verdicts", {}).get("removability", "NO")
        assert removable == "YES", f"Memory removable is {removable}, expected YES"


# ═══════════════════════════════════════════════════════════════════════
# Test 17: Golden path listed in validation
# ═══════════════════════════════════════════════════════════════════════

def test_validation_golden_path_checks():
    """Validation matrix has golden_path category checks."""
    from v3.release.validation_matrix import build_validation_matrix

    matrix = build_validation_matrix()
    gp_checks = [c for c in matrix.checks if c.category == "golden_path"]
    assert len(gp_checks) > 0, "Validation should have golden_path checks"


# ═══════════════════════════════════════════════════════════════════════
# Test 18: Repo intake listed in validation
# ═══════════════════════════════════════════════════════════════════════

def test_validation_repo_intake_checks():
    """Validation matrix has repo_intake category checks."""
    from v3.release.validation_matrix import build_validation_matrix

    matrix = build_validation_matrix()
    ri_checks = [c for c in matrix.checks if c.category == "repo_intake"]
    assert len(ri_checks) > 0, "Validation should have repo_intake checks"


# ═══════════════════════════════════════════════════════════════════════
# Test 19: release_ready is true
# ═══════════════════════════════════════════════════════════════════════

def test_release_ready_true():
    """Validation matrix reports release_ready=True."""
    from v3.release.validation_matrix import build_validation_matrix

    matrix = build_validation_matrix()
    assert matrix.release_ready, \
        f"release_ready is {matrix.release_ready}, failed={matrix.failed}/{matrix.total}"


# ═══════════════════════════════════════════════════════════════════════
# Test 20: Existing selected tests still pass (import validation)
# ═══════════════════════════════════════════════════════════════════════

def test_existing_modules_still_import():
    """Critical modules still import correctly."""
    # Kernel
    from v3.kernel.execution_engine import ExecutionEngine
    from v3.kernel.events import ExecutionEvent, make_event
    from v3.kernel.checkpoint import FileCheckpointStore
    from v3.kernel.truth_model import capture_truth
    from v3.kernel.memory_gateway import MemoryGateway

    # Memory
    from v3.memory.episodic_store import EpisodicMemoryStore
    from v3.memory.runtime import MemoryRuntime

    # Quality
    from v3.quality.phase_gate import evaluate_phase

    # Intake
    from v3.intake.repo_intake import decide_repo_intake
    from v3.intake.tool_registry import build_registry_from_profiles

    # Release
    from v3.release.validation_matrix import build_validation_matrix
    from v3.release.inventory import build_inventory
    from v3.release.release_notes import generate_release_notes

    assert True, "All critical modules import successfully"


# ═══════════════════════════════════════════════════════════════════════
# Test 21: Release notes are deterministic
# ═══════════════════════════════════════════════════════════════════════

def test_release_notes_deterministic():
    """Release notes are deterministic across generations."""
    from v3.release.release_notes import generate_release_notes

    notes_set = set()
    for _ in range(3):
        notes = generate_release_notes()
        notes_set.add(hash(notes))
    assert len(notes_set) == 1, "Release notes should be deterministic"


# ═══════════════════════════════════════════════════════════════════════
# Test 22: Validation matrix has all check IDs unique
# ═══════════════════════════════════════════════════════════════════════

def test_validation_check_ids_unique():
    """All validation check IDs are unique."""
    from v3.release.validation_matrix import build_validation_matrix

    matrix = build_validation_matrix()
    ids = [c.check_id for c in matrix.checks]
    assert len(ids) == len(set(ids)), f"Duplicate check IDs: {len(ids)} vs {len(set(ids))}"


# ═══════════════════════════════════════════════════════════════════════
# Test 23: Inventory includes release modules
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_includes_release_modules():
    """Inventory includes the new release/ modules."""
    from v3.release.inventory import build_inventory

    inv = build_inventory()
    release_entries = [e for e in inv.entries if e.subsystem == "release"]
    assert len(release_entries) >= 3, \
        f"Expected >=3 release modules, got {len(release_entries)}"


# ═══════════════════════════════════════════════════════════════════════
# Test 24: No banned LLM imports in release modules
# ═══════════════════════════════════════════════════════════════════════

def test_release_no_banned_imports():
    """Release modules have no banned LLM/vector imports."""
    banned = {
        "openai", "anthropic", "langchain", "llamaindex",
        "chromadb", "qdrant", "pinecone", "weaviate",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow",
    }

    import v3.release.validation_matrix as vm
    import v3.release.inventory as inv
    import v3.release.release_notes as rn

    for mod in (vm, inv, rn):
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
# Test 25: write_validation_matrix writes valid JSON
# ═══════════════════════════════════════════════════════════════════════

def test_write_validation_matrix():
    """write_validation_matrix produces valid JSON."""
    from v3.release.validation_matrix import build_validation_matrix, write_validation_matrix

    matrix = build_validation_matrix()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "validation_matrix.json")
        result_path = write_validation_matrix(matrix, path)
        assert os.path.exists(result_path)

        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["release_version"] == "3.0.0"
        assert data["matrix_hash"] == matrix.matrix_hash
        assert data["total"] == matrix.total


# ═══════════════════════════════════════════════════════════════════════
# Test 26: write_inventory writes valid JSON
# ═══════════════════════════════════════════════════════════════════════

def test_write_inventory():
    """write_inventory produces valid JSON."""
    from v3.release.inventory import build_inventory, write_inventory

    inv = build_inventory()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "inventory.json")
        result_path = write_inventory(inv, path)
        assert os.path.exists(result_path)

        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["release_version"] == "3.0.0"
        assert data["release_hash"] == inv.release_hash


# ═══════════════════════════════════════════════════════════════════════
# Test 27: write_release_notes writes markdown
# ═══════════════════════════════════════════════════════════════════════

def test_write_release_notes():
    """write_release_notes produces valid markdown."""
    from v3.release.release_notes import generate_release_notes, write_release_notes

    notes = generate_release_notes()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "release_notes.md")
        result_path = write_release_notes(notes, path)
        assert os.path.exists(result_path)

        with open(result_path, encoding="utf-8") as f:
            content = f.read()
        assert "# SystemKernel v3.0" in content
        assert "Release Notes" in content


# ═══════════════════════════════════════════════════════════════════════
# Bonus: Validation matrix to_dict and to_json
# ═══════════════════════════════════════════════════════════════════════

def test_validation_matrix_serialization():
    """ValidationMatrix.to_dict() and to_json() work."""
    from v3.release.validation_matrix import build_validation_matrix

    matrix = build_validation_matrix()
    d = matrix.to_dict()
    assert "release_version" in d
    assert "checks" in d
    assert "categories" in d

    j = matrix.to_json()
    parsed = json.loads(j)
    assert parsed["matrix_hash"] == matrix.matrix_hash


# ═══════════════════════════════════════════════════════════════════════
# Bonus: Inventory to_dict and to_json
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_serialization():
    """ProjectInventory.to_dict() and to_json() work."""
    from v3.release.inventory import build_inventory

    inv = build_inventory()
    d = inv.to_dict()
    assert "release_version" in d
    assert "entries" in d
    assert "summary" in d

    j = inv.to_json()
    parsed = json.loads(j)
    assert parsed["release_hash"] == inv.release_hash


# ═══════════════════════════════════════════════════════════════════════
# Bonus: Validation matrix passed count matches
# ═══════════════════════════════════════════════════════════════════════

def test_validation_passed_count():
    """Validation passed + failed == total."""
    from v3.release.validation_matrix import build_validation_matrix

    matrix = build_validation_matrix()
    assert matrix.passed + matrix.failed == matrix.total, \
        f"passed({matrix.passed}) + failed({matrix.failed}) != total({matrix.total})"


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    """Run all release freeze tests."""
    tests = [
        test_validation_matrix_builds,
        test_validation_matrix_hash_deterministic,
        test_release_inventory_builds,
        test_inventory_hash_deterministic,
        test_release_notes_generated,
        test_validation_all_subsystems_present,
        test_inventory_lists_test_suites,
        test_inventory_lists_reports,
        test_inventory_lists_cli_commands,
        test_inventory_lists_invariants,
        test_inventory_lists_registry_entries,
        test_release_no_network_imports,
        test_release_no_git_commands,
        test_complexity_gate_not_reject,
        test_kernel_purity_remains_100,
        test_memory_removable_remains_yes,
        test_validation_golden_path_checks,
        test_validation_repo_intake_checks,
        test_release_ready_true,
        test_existing_modules_still_import,
        test_release_notes_deterministic,
        test_validation_check_ids_unique,
        test_inventory_includes_release_modules,
        test_release_no_banned_imports,
        test_write_validation_matrix,
        test_write_inventory,
        test_write_release_notes,
        test_validation_matrix_serialization,
        test_inventory_serialization,
        test_validation_passed_count,
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
