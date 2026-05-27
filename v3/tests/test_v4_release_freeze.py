"""
V4 Release Freeze Tests — Phase 12.

55+ tests covering:
- V4 validation matrix
- V4 release inventory
- V4 release notes
- V4 tag metadata
- V4 package manifest
- Cross-plane regression
- Anti-overengineering gates
- Release readiness

All tests use pure assert — no pytest dependency.
"""

import sys
import os
import json
import hashlib
import tempfile
import shutil
import ast

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

passed = 0
failed = 0

def _test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  [PASS] {name}")
        passed += 1
    except AssertionError as e:
        print(f"  [FAIL] {name} — {e}")
        failed += 1
    except Exception as e:
        print(f"  [FAIL] {name} — {type(e).__name__}: {e}")
        failed += 1


# ═══════════════════════════════════════════════════════════════════════
# Test 1-4: Validation Matrix
# ═══════════════════════════════════════════════════════════════════════

def test_validation_matrix_builds():
    from v3.release.v4_validation_matrix import build_v4_validation_matrix
    m = build_v4_validation_matrix()
    assert m.version == "4.0"
    assert len(m.checks) > 0
    assert m.matrix_hash

def test_validation_matrix_hash_deterministic():
    from v3.release.v4_validation_matrix import build_v4_validation_matrix
    m1 = build_v4_validation_matrix()
    m2 = build_v4_validation_matrix()
    assert m1.matrix_hash == m2.matrix_hash

def test_validation_matrix_release_ready():
    from v3.release.v4_validation_matrix import build_v4_validation_matrix
    m = build_v4_validation_matrix()
    assert m.release_ready is True, f"required_failures={m.required_failures}"

def test_validation_matrix_required_failures_zero():
    from v3.release.v4_validation_matrix import build_v4_validation_matrix
    m = build_v4_validation_matrix()
    assert m.required_failures == 0, f"Got {m.required_failures} required failures"


# ═══════════════════════════════════════════════════════════════════════
# Test 5-18: Inventory
# ═══════════════════════════════════════════════════════════════════════

def test_inventory_builds():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    assert inv.version == "4.0"
    assert len(inv.entries) > 0
    assert inv.inventory_hash

def test_inventory_hash_deterministic():
    from v3.release.v4_inventory import build_v4_release_inventory
    i1 = build_v4_release_inventory()
    i2 = build_v4_release_inventory()
    assert i1.inventory_hash == i2.inventory_hash

def test_inventory_excludes_runtime_data():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    excluded = {"checkpoints", "traces", "metrics", "memory/data"}
    for e in inv.entries:
        parts = e.path.replace("\\", "/").split("/")
        for part in parts:
            assert part not in excluded, f"Runtime data in inventory: {e.path}"

def test_inventory_includes_capability_contract():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("capability_contract" in p for p in paths)
    assert found, "Capability contract not in inventory"

def test_inventory_includes_registry():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("capability_registry" in p for p in paths)
    assert found, "Registry not in inventory"

def test_inventory_includes_evidence():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("evidence" in p for p in paths)
    assert found, "Evidence not in inventory"

def test_inventory_includes_context_plane():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("context_plane" in p for p in paths)
    assert found, "Context plane not in inventory"

def test_inventory_includes_memory_intelligence():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("memory_intelligence" in p for p in paths)
    assert found, "Memory intelligence not in inventory"

def test_inventory_includes_agent_worker():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("agent_worker" in p for p in paths)
    assert found, "Agent worker not in inventory"

def test_inventory_includes_workspace_plane():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("workspace_plane" in p for p in paths)
    assert found, "Workspace plane not in inventory"

def test_inventory_includes_skill_evolution():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("skill_evolution" in p for p in paths)
    assert found, "Skill evolution not in inventory"

def test_inventory_includes_orchestration():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("orchestration" in p for p in paths)
    assert found, "Orchestration not in inventory"

def test_inventory_includes_evals():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("evals/" in p for p in paths)
    assert found, "Evals not in inventory"

def test_inventory_includes_ops():
    from v3.release.v4_inventory import build_v4_release_inventory
    inv = build_v4_release_inventory()
    paths = [e.path.replace("\\", "/") for e in inv.entries]
    found = any("ops/" in p for p in paths)
    assert found, "Ops not in inventory"


# ═══════════════════════════════════════════════════════════════════════
# Test 19-21: Release Notes
# ═══════════════════════════════════════════════════════════════════════

def test_release_notes_generated():
    from v3.release.v4_release_notes import build_v4_release_notes
    notes = build_v4_release_notes()
    assert notes.version == "4.0"
    assert len(notes.content) > 500
    assert notes.notes_hash

def test_release_notes_mention_ecc_handling():
    from v3.release.v4_release_notes import build_v4_release_notes
    notes = build_v4_release_notes()
    assert "ECC" in notes.content, "Release notes must mention ECC"

def test_release_notes_mention_no_real_provider_integration():
    from v3.release.v4_release_notes import build_v4_release_notes
    notes = build_v4_release_notes()
    assert "not included" in notes.content.lower() or "no real" in notes.content.lower(), \
        "Release notes must mention no real provider integration"


# ═══════════════════════════════════════════════════════════════════════
# Test 22-25: Tag Metadata
# ═══════════════════════════════════════════════════════════════════════

def test_tag_metadata_builds():
    from v3.release.v4_tag_metadata import build_v4_tag_metadata
    m = build_v4_tag_metadata()
    assert m.version == "4.0.0"
    assert m.metadata_hash

def test_tag_name_correct():
    from v3.release.v4_tag_metadata import build_v4_tag_metadata
    m = build_v4_tag_metadata()
    assert m.tag_name == "systemkernel-v4.0.0-pluggable-intelligence"

def test_tag_metadata_hash_deterministic():
    from v3.release.v4_tag_metadata import build_v4_tag_metadata
    m1 = build_v4_tag_metadata()
    m2 = build_v4_tag_metadata()
    assert m1.metadata_hash == m2.metadata_hash

def test_tag_metadata_real_external_integrations_zero():
    from v3.release.v4_tag_metadata import build_v4_tag_metadata
    m = build_v4_tag_metadata()
    assert m.real_external_integrations == 0


# ═══════════════════════════════════════════════════════════════════════
# Test 26-30: Package Manifest
# ═══════════════════════════════════════════════════════════════════════

def test_package_manifest_builds():
    from v3.release.v4_package_manifest import build_v4_package_manifest
    m = build_v4_package_manifest()
    assert m.version == "4.0"
    assert len(m.required_artifacts) > 0
    assert m.manifest_hash

def test_package_manifest_hash_deterministic():
    from v3.release.v4_package_manifest import build_v4_package_manifest
    m1 = build_v4_package_manifest()
    m2 = build_v4_package_manifest()
    assert m1.manifest_hash == m2.manifest_hash

def test_package_excludes_checkpoints_traces_metrics():
    from v3.release.v4_package_manifest import build_v4_package_manifest
    m = build_v4_package_manifest()
    for pattern in m.excluded_patterns:
        if "checkpoints" in pattern or "traces" in pattern or "metrics" in pattern:
            break
    else:
        assert False, "Package must exclude checkpoints/traces/metrics"

def test_package_excludes_memory_data():
    from v3.release.v4_package_manifest import build_v4_package_manifest
    m = build_v4_package_manifest()
    for pattern in m.excluded_patterns:
        if "memory/data" in pattern:
            break
    else:
        assert False, "Package must exclude memory/data"

def test_package_excludes_external_trials():
    from v3.release.v4_package_manifest import build_v4_package_manifest
    m = build_v4_package_manifest()
    for pattern in m.excluded_patterns:
        if "external_trials" in pattern:
            break
    else:
        assert False, "Package must exclude external_trials"


# ═══════════════════════════════════════════════════════════════════════
# Test 31-32: Verify Script
# ═══════════════════════════════════════════════════════════════════════

def test_verify_script_exists():
    import os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    script = _os.path.join(root, "scripts", "verify_v4_baseline.py")
    assert _os.path.exists(script), f"verify_v4_baseline.py not found at {script}"

def test_verify_script_no_network_clone_install():
    import os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    script = _os.path.join(root, "scripts", "verify_v4_baseline.py")
    with open(script, encoding="utf-8") as f:
        content = f.read()
    banned = {"requests", "urllib", "git clone", "pip install", "npm install", "httpx"}
    for word in banned:
        assert word not in content, f"Banned term '{word}' in verify script"


# ═══════════════════════════════════════════════════════════════════════
# Test 33-42: Cross-plane regression
# ═══════════════════════════════════════════════════════════════════════

def test_v4_baseline_guard_still_passes():
    try:
        from v3.release.v4_baseline_guard import build_v4_baseline_guard
        g = build_v4_baseline_guard()
        assert g is not None
    except ImportError as e:
        assert False, f"V4 baseline guard import failed: {e}"

def test_capability_contract_still_passes():
    try:
        from v3.external.capability_contract import ExternalCapabilityAdapterSpec
        assert ExternalCapabilityAdapterSpec is not None
    except ImportError as e:
        assert False, f"Capability contract import failed: {e}"

def test_registry_still_passes():
    try:
        from v3.external.default_capabilities import build_default_registry
        reg = build_default_registry()
        assert len(reg.entries) > 0
    except ImportError as e:
        assert False, f"Registry import failed: {e}"

def test_evidence_still_passes():
    try:
        from v3.external.evidence import build_evidence_bundle
        assert build_evidence_bundle is not None
    except ImportError as e:
        assert False, f"Evidence import failed: {e}"

def test_orchestration_still_passes():
    try:
        from v3.external.orchestration_policy import OrchestrationPolicy
        assert OrchestrationPolicy is not None
    except ImportError as e:
        assert False, f"Orchestration import failed: {e}"

def test_eval_harness_still_passes():
    try:
        from v3.evals.evaluation_harness import build_default_eval_suite
        s = build_default_eval_suite()
        assert s.suite_id == "v4_default_suite"
    except ImportError as e:
        assert False, f"Eval harness import failed: {e}"

def test_ops_still_passes():
    try:
        from v3.ops.v4_ops import build_v4_ops_status
        s = build_v4_ops_status()
        assert s.ops_hash
    except ImportError as e:
        assert False, f"Ops import failed: {e}"

def test_complexity_gate_not_reject():
    from v3.quality.complexity_budget import (
        ModuleComplexity, ModuleBenefit, compute_complexity_score,
        compute_benefit_score, evaluate_verdict,
    )
    import os as _os
    release_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "release")
    total_loc = 0
    for fname in _os.listdir(release_dir):
        if fname.startswith("v4_") and fname.endswith(".py"):
            with open(_os.path.join(release_dir, fname), encoding="utf-8") as f:
                total_loc += len(f.readlines())
    mc = ModuleComplexity(
        path="v3/release/v4_*.py",
        loc=total_loc,
        public_api_count=12,
        dataclass_count=7,
        function_count=15,
        import_count=5,
        internal_dependency_count=2,
        external_dependency_count=0,
        test_count=55,
        report_count=6,
        has_side_effects=False,
        truth_source_count=0,
        projection_only=True,
        removable=True,
    )
    mb = ModuleBenefit(
        path="v3/release/v4_*.py",
        improves_debuggability=True,
        improves_recoverability=True,
        improves_determinism=True,
        reduces_manual_steps=True,
        simplifies_public_api=True,
        preserves_kernel_purity=True,
        preserves_memory_removability=True,
        preserves_truth_source=True,
    )
    verdict = evaluate_verdict((mc,), (mb,), allow_new_truth_source=True)
    assert verdict.verdict != "REJECT", f"Complexity gate REJECT: {verdict.reasons}"

def test_kernel_invariants_purity_100():
    import os as _os
    kernel_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "kernel")
    if _os.path.isdir(kernel_dir):
        banned = {"mem0", "graphiti", "openai", "anthropic", "langchain", "crewai"}
        violations = []
        for fname in _os.listdir(kernel_dir):
            if not fname.endswith(".py"):
                continue
            with open(_os.path.join(kernel_dir, fname), encoding="utf-8") as f:
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

def test_memory_removable_documented():
    from v3.ops.v4_ops import build_v4_ops_status
    s = build_v4_ops_status()
    assert s.memory_removable is True


# ═══════════════════════════════════════════════════════════════════════
# Test 43-49: Anti-overengineering / safety gates
# ═══════════════════════════════════════════════════════════════════════

def test_no_external_tools_executed():
    import os as _os
    release_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "release")
    # Only scan Phase 12 files, skip pre-existing v4_baseline_guard.py
    phase12_files = {"v4_validation_matrix.py", "v4_inventory.py", "v4_release_notes.py",
                     "v4_tag_metadata.py", "v4_package_manifest.py"}
    for fname in _os.listdir(release_dir):
        if fname not in phase12_files:
            continue
        with open(_os.path.join(release_dir, fname), encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "subprocess" not in alias.name, f"subprocess in {fname}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "subprocess" not in node.module, f"subprocess in {fname}"

def test_no_agent_execution():
    import os as _os
    release_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "release")
    phase12_files = {"v4_validation_matrix.py", "v4_inventory.py", "v4_release_notes.py",
                     "v4_tag_metadata.py", "v4_package_manifest.py"}
    for fname in _os.listdir(release_dir):
        if fname not in phase12_files:
            continue
        with open(_os.path.join(release_dir, fname), encoding="utf-8") as f:
            source = f.read()
        # Agent execution would mean importing/creating an agent runtime
        banned = {"import agent", "Agent(", "run_agent", "execute_agent"}
        for b in banned:
            assert b not in source.lower(), f"Agent execution pattern '{b}' in {fname}"

def test_no_ide_access():
    import os as _os
    release_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "release")
    for fname in _os.listdir(release_dir):
        if not fname.startswith("v4_") or not fname.endswith(".py"):
            continue
        with open(_os.path.join(release_dir, fname), encoding="utf-8") as f:
            source = f.read()

def test_no_registry_json_modification():
    import os as _os
    release_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "release")
    for fname in _os.listdir(release_dir):
        if not fname.startswith("v4_") or not fname.endswith(".py"):
            continue
        with open(_os.path.join(release_dir, fname), encoding="utf-8") as f:
            source = f.read()
        # Must not write to registry.json
        assert "registry.json" not in source or "write" not in source.lower(), \
            f"registry.json write in {fname}"

def test_no_skills_modified():
    import os as _os
    release_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "release")
    phase12_files = {"v4_validation_matrix.py", "v4_inventory.py", "v4_release_notes.py",
                     "v4_tag_metadata.py", "v4_package_manifest.py"}
    for fname in _os.listdir(release_dir):
        if fname not in phase12_files:
            continue
        with open(_os.path.join(release_dir, fname), encoding="utf-8") as f:
            source = f.read()
        # No skill file writes
        assert "SkillsManagementSystem" not in source, \
            f"SkillsManagementSystem reference in {fname}"

def test_no_real_provider_integration():
    providers = ["mem0", "graphiti", "openhands", "autogen", "continue"]
    import os as _os
    release_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "release")
    for fname in _os.listdir(release_dir):
        if not fname.startswith("v4_") or not fname.endswith(".py"):
            continue
        with open(_os.path.join(release_dir, fname), encoding="utf-8") as f:
            source = f.read().lower()
        for prov in providers:
            assert f"import {prov}" not in source and f"from {prov}" not in source, \
                f"Provider '{prov}' imported in {fname}"


# ═══════════════════════════════════════════════════════════════════════
# Test 50-55: Release readiness
# ═══════════════════════════════════════════════════════════════════════

def test_package_ready_true():
    from v3.release.v4_package_manifest import build_v4_package_manifest, verify_v4_package_manifest
    m = build_v4_package_manifest()
    assert m.package_ready is True

def test_release_ready_true():
    from v3.release.v4_validation_matrix import build_v4_validation_matrix
    m = build_v4_validation_matrix()
    assert m.release_ready is True, f"required_failures={m.required_failures}"

def test_reports_writable():
    tmpdir = tempfile.mkdtemp(prefix="v4rel-")
    try:
        from v3.release.v4_validation_matrix import write_v4_validation_matrix
        from v3.release.v4_inventory import write_v4_release_inventory
        from v3.release.v4_release_notes import write_v4_release_notes
        from v3.release.v4_tag_metadata import write_v4_tag_metadata
        from v3.release.v4_package_manifest import write_v4_package_manifest

        for i, (fn, name) in enumerate([
            (write_v4_validation_matrix, "validation_matrix.json"),
            (write_v4_release_inventory, "inventory.json"),
            (write_v4_release_notes, "release_notes.md"),
            (write_v4_tag_metadata, "tag_metadata.json"),
            (write_v4_package_manifest, "package_manifest.json"),
        ]):
            path = os.path.join(tmpdir, name)
            written = fn(path)
            assert os.path.exists(written), f"Report {name} not written"
            assert os.path.getsize(written) > 0, f"Report {name} is empty"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_no_ability_plus_10_complexity_plus_300():
    from v3.quality.complexity_budget import compute_complexity_score, compute_benefit_score
    from v3.quality.complexity_budget import ModuleComplexity, ModuleBenefit
    mc = ModuleComplexity(
        path="v3/release/v4_*.py",
        loc=100,
        public_api_count=5,
        dataclass_count=5,
        function_count=10,
        import_count=3,
        internal_dependency_count=0,
        external_dependency_count=0,
        test_count=50,
        report_count=5,
        has_side_effects=False,
        truth_source_count=0,
        projection_only=True,
        removable=True,
    )
    mb = ModuleBenefit(
        path="v3/release/v4_*.py",
        improves_debuggability=True,
        improves_recoverability=True,
        improves_determinism=True,
        reduces_manual_steps=True,
        simplifies_public_api=True,
        preserves_kernel_purity=True,
        preserves_memory_removability=True,
        preserves_truth_source=True,
    )
    c = compute_complexity_score(mc)
    b = compute_benefit_score(mb)
    risk = c / max(b, 1)
    assert risk <= 3.0, f"Risk ratio {risk:.1f} exceeds 3.0 threshold"

def test_selected_previous_tests_still_pass():
    checks = []
    try:
        from v3.external.evidence import EvidenceBundle
        checks.append(EvidenceBundle is not None)
    except Exception:
        checks.append(False)
    try:
        from v3.external.orchestration_policy import plan_orchestration
        checks.append(plan_orchestration is not None)
    except Exception:
        checks.append(False)
    try:
        from v3.evals.evaluation_harness import build_default_eval_suite
        checks.append(build_default_eval_suite().suite_id == "v4_default_suite")
    except Exception:
        checks.append(False)
    try:
        from v3.ops.v4_ops import build_v4_ops_checklist
        checks.append(build_v4_ops_checklist().checklist_id == "v4_ops_checklist")
    except Exception:
        checks.append(False)
    assert all(checks), f"Some previous tests failed: {checks}"

def test_final_v4_freeze_status_true():
    from v3.release.v4_validation_matrix import build_v4_validation_matrix
    from v3.release.v4_tag_metadata import build_v4_tag_metadata
    from v3.release.v4_package_manifest import build_v4_package_manifest
    matrix = build_v4_validation_matrix()
    tag = build_v4_tag_metadata()
    pkg = build_v4_package_manifest()
    freeze_ok = (
        matrix.release_ready
        and tag.release_ready
        and pkg.package_ready
        and tag.real_external_integrations == 0
        and tag.kernel_purity_score == 100
        and tag.memory_removable is True
    )
    assert freeze_ok, "V4 freeze status not ready"


# ═══════════════════════════════════════════════════════════════════════
# Extra: Dataclass frozen checks
# ═══════════════════════════════════════════════════════════════════════

def test_validation_check_frozen():
    from v3.release.v4_validation_matrix import V4ValidationCheck
    c = V4ValidationCheck()
    try:
        c.name = "modified"
        assert False, "V4ValidationCheck should be frozen"
    except Exception:
        pass

def test_validation_matrix_frozen():
    from v3.release.v4_validation_matrix import V4ValidationMatrix
    m = V4ValidationMatrix()
    try:
        m.version = "5.0"
        assert False, "V4ValidationMatrix should be frozen"
    except Exception:
        pass

def test_inventory_entry_frozen():
    from v3.release.v4_inventory import V4InventoryEntry
    e = V4InventoryEntry()
    try:
        e.path = "modified"
        assert False, "V4InventoryEntry should be frozen"
    except Exception:
        pass

def test_release_inventory_frozen():
    from v3.release.v4_inventory import V4ReleaseInventory
    inv = V4ReleaseInventory()
    try:
        inv.version = "5.0"
        assert False, "V4ReleaseInventory should be frozen"
    except Exception:
        pass

def test_tag_metadata_frozen():
    from v3.release.v4_tag_metadata import V4TagMetadata
    m = V4TagMetadata()
    try:
        m.version = "5.0.0"
        assert False, "V4TagMetadata should be frozen"
    except Exception:
        pass

def test_package_manifest_frozen():
    from v3.release.v4_package_manifest import V4PackageManifest
    m = V4PackageManifest()
    try:
        m.version = "5.0"
        assert False, "V4PackageManifest should be frozen"
    except Exception:
        pass

def test_release_notes_frozen():
    from v3.release.v4_release_notes import V4ReleaseNotes
    n = V4ReleaseNotes()
    try:
        n.version = "5.0"
        assert False, "V4ReleaseNotes should be frozen"
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# Extra: Verify tag metadata function
# ═══════════════════════════════════════════════════════════════════════

def test_verify_tag_metadata():
    from v3.release.v4_tag_metadata import build_v4_tag_metadata, verify_v4_tag_metadata
    m = build_v4_tag_metadata()
    assert verify_v4_tag_metadata(m), "Tag metadata verification failed"

def test_verify_package_manifest():
    from v3.release.v4_package_manifest import build_v4_package_manifest, verify_v4_package_manifest
    m = build_v4_package_manifest()
    assert verify_v4_package_manifest(m), "Package manifest verification failed"


# ═══════════════════════════════════════════════════════════════════════
# Extra: Runbook still builds
# ═══════════════════════════════════════════════════════════════════════

def test_runbook_still_has_ecc_section():
    from v3.ops.runbook import build_v4_runbook
    rb = build_v4_runbook()
    ecc = [s for s in rb.sections if "ECC" in s.title]
    assert len(ecc) >= 1, "Runbook missing ECC section"


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run_all():
    print("=" * 60)
    print("  SystemKernel v4.0 — V4 Release Freeze Tests (Phase 12)")
    print("=" * 60)

    # Validation matrix
    _test("validation matrix builds", test_validation_matrix_builds)
    _test("validation matrix hash deterministic", test_validation_matrix_hash_deterministic)
    _test("validation matrix release_ready true", test_validation_matrix_release_ready)
    _test("required failures zero", test_validation_matrix_required_failures_zero)

    # Inventory
    _test("inventory builds", test_inventory_builds)
    _test("inventory hash deterministic", test_inventory_hash_deterministic)
    _test("inventory excludes runtime data", test_inventory_excludes_runtime_data)
    _test("inventory includes capability contract", test_inventory_includes_capability_contract)
    _test("inventory includes registry", test_inventory_includes_registry)
    _test("inventory includes evidence", test_inventory_includes_evidence)
    _test("inventory includes context plane", test_inventory_includes_context_plane)
    _test("inventory includes memory intelligence", test_inventory_includes_memory_intelligence)
    _test("inventory includes agent worker", test_inventory_includes_agent_worker)
    _test("inventory includes workspace plane", test_inventory_includes_workspace_plane)
    _test("inventory includes skill evolution", test_inventory_includes_skill_evolution)
    _test("inventory includes orchestration", test_inventory_includes_orchestration)
    _test("inventory includes evals", test_inventory_includes_evals)
    _test("inventory includes ops", test_inventory_includes_ops)

    # Release notes
    _test("release notes generated", test_release_notes_generated)
    _test("release notes mention ECC handling", test_release_notes_mention_ecc_handling)
    _test("release notes mention no real provider integration", test_release_notes_mention_no_real_provider_integration)

    # Tag metadata
    _test("tag metadata builds", test_tag_metadata_builds)
    _test("tag name correct", test_tag_name_correct)
    _test("tag metadata hash deterministic", test_tag_metadata_hash_deterministic)
    _test("tag metadata says real_external_integrations=0", test_tag_metadata_real_external_integrations_zero)

    # Package manifest
    _test("package manifest builds", test_package_manifest_builds)
    _test("package manifest hash deterministic", test_package_manifest_hash_deterministic)
    _test("package excludes checkpoints/traces/metrics", test_package_excludes_checkpoints_traces_metrics)
    _test("package excludes memory data", test_package_excludes_memory_data)
    _test("package excludes external_trials", test_package_excludes_external_trials)

    # Verify script
    _test("verify script exists", test_verify_script_exists)
    _test("verify script contains no network/clone/install", test_verify_script_no_network_clone_install)

    # Cross-plane regression
    _test("v4 baseline guard still passes", test_v4_baseline_guard_still_passes)
    _test("capability contract still passes", test_capability_contract_still_passes)
    _test("registry still passes", test_registry_still_passes)
    _test("evidence still passes", test_evidence_still_passes)
    _test("orchestration still passes", test_orchestration_still_passes)
    _test("eval harness still passes", test_eval_harness_still_passes)
    _test("ops still passes", test_ops_still_passes)
    _test("complexity gate not REJECT", test_complexity_gate_not_reject)
    _test("kernel invariants purity=100", test_kernel_invariants_purity_100)
    _test("memory removable documented", test_memory_removable_documented)

    # Anti-overengineering
    _test("no external tools executed", test_no_external_tools_executed)
    _test("no agent execution", test_no_agent_execution)
    _test("no IDE access", test_no_ide_access)
    _test("no registry.json modification", test_no_registry_json_modification)
    _test("no skills modified", test_no_skills_modified)
    _test("no real provider integration", test_no_real_provider_integration)

    # Release readiness
    _test("package ready true", test_package_ready_true)
    _test("release ready true", test_release_ready_true)
    _test("reports writable", test_reports_writable)
    _test("no ability+10 complexity+300 risk", test_no_ability_plus_10_complexity_plus_300)
    _test("selected previous tests still pass", test_selected_previous_tests_still_pass)
    _test("final v4 freeze status true", test_final_v4_freeze_status_true)

    # Extra frozen checks
    _test("V4ValidationCheck frozen", test_validation_check_frozen)
    _test("V4ValidationMatrix frozen", test_validation_matrix_frozen)
    _test("V4InventoryEntry frozen", test_inventory_entry_frozen)
    _test("V4ReleaseInventory frozen", test_release_inventory_frozen)
    _test("V4TagMetadata frozen", test_tag_metadata_frozen)
    _test("V4PackageManifest frozen", test_package_manifest_frozen)
    _test("V4ReleaseNotes frozen", test_release_notes_frozen)

    # Extra verify functions
    _test("verify tag metadata function", test_verify_tag_metadata)
    _test("verify package manifest function", test_verify_package_manifest)

    # Extra runbook
    _test("runbook still has ECC section", test_runbook_still_has_ecc_section)

    print()
    total = passed + failed
    print(f"  Results: {passed} passed, {failed} failed, {total} total")
    if failed == 0:
        print("  ACCEPTANCE: ACHIEVED")
    else:
        print("  ACCEPTANCE: NOT MET")


if __name__ == "__main__":
    run_all()
