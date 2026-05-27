"""
Capability Registry Tests — Phase 2.

31 tests for the unified capability registry.
Stdlib only.
"""

import ast
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable

from v3.external.capability_contract import (
    CapabilityType,
    CapabilityRiskLevel,
    ExternalCapabilityAdapterSpec,
)
from v3.external.capability_registry import (
    CapabilityRegistryEntry,
    CapabilityRegistry,
    build_registry,
    validate_registry,
    get_entry,
    list_by_type,
    list_enabled,
    list_requires_approval,
    list_by_lifecycle,
    list_high_risk,
    disable_entry,
    enable_entry,
    write_registry,
    load_registry,
)
from v3.external.capability_lifecycle import (
    STATE_APPROVED,
    STATE_DISABLED,
    STATE_PROPOSED,
    STATE_REGISTERED,
)
from v3.external.default_capabilities import build_default_registry


def _run_module(module_path, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    result = subprocess.run(
        [PYTHON, module_path] + list(args),
        capture_output=True, text=True, timeout=30,
        cwd=ROOT, env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _make_test_entry(adapter_id, enabled=True, lifecycle=STATE_APPROVED,
                     cap_type=CapabilityType.tool.value, risk=CapabilityRiskLevel.low.value):
    spec = ExternalCapabilityAdapterSpec(
        adapter_id=adapter_id,
        name=adapter_id.replace("_", " ").title(),
        capability_type=cap_type,
        forbidden_actions=("no_network",),
        risk_level=risk,
    )
    entry = CapabilityRegistryEntry(
        adapter_id=adapter_id,
        spec=spec,
        lifecycle_state=lifecycle,
        enabled=enabled,
        maturity="stable",
    )
    object.__setattr__(entry, "entry_hash", f"hash-{adapter_id}")
    return entry


class TestCapabilityRegistry(unittest.TestCase):

    # ── Test 1: registry entry frozen ───────────────────────────────────

    def test_01_entry_frozen(self):
        entry = _make_test_entry("test-adapter")
        with self.assertRaises(Exception):
            entry.enabled = False

    # ── Test 2: registry frozen ─────────────────────────────────────────

    def test_02_registry_frozen(self):
        e1 = _make_test_entry("a")
        e2 = _make_test_entry("b")
        reg = build_registry((e1, e2))
        with self.assertRaises(Exception):
            reg.enabled_count = 99

    # ── Test 3: registry hash deterministic ─────────────────────────────

    def test_03_hash_deterministic(self):
        e1 = _make_test_entry("a")
        e2 = _make_test_entry("b")
        reg1 = build_registry((e1, e2))
        reg2 = build_registry((e1, e2))
        self.assertEqual(reg1.registry_hash, reg2.registry_hash)

    # ── Test 4: entries sorted by adapter_id ────────────────────────────

    def test_04_entries_sorted(self):
        e_c = _make_test_entry("c")
        e_a = _make_test_entry("a")
        e_b = _make_test_entry("b")
        reg = build_registry((e_c, e_a, e_b))
        ids = [e.adapter_id for e in reg.entries]
        self.assertEqual(ids, ["a", "b", "c"])

    # ── Test 5: duplicate adapter_id invalid ────────────────────────────

    def test_05_duplicate_invalid(self):
        e1 = _make_test_entry("same-id")
        e2 = _make_test_entry("same-id")
        with self.assertRaises(ValueError):
            build_registry((e1, e2))

    # ── Test 6: get_entry works ─────────────────────────────────────────

    def test_06_get_entry(self):
        e1 = _make_test_entry("target")
        reg = build_registry((e1,))
        entry = get_entry(reg, "target")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.adapter_id, "target")
        self.assertIsNone(get_entry(reg, "nonexistent"))

    # ── Test 7: list_by_type works ──────────────────────────────────────

    def test_07_list_by_type(self):
        e1 = _make_test_entry("ctx1", cap_type=CapabilityType.context.value)
        e2 = _make_test_entry("mem1", cap_type=CapabilityType.memory.value)
        e3 = _make_test_entry("ctx2", cap_type=CapabilityType.context.value)
        reg = build_registry((e1, e2, e3))
        ctx = list_by_type(reg, CapabilityType.context.value)
        self.assertEqual(len(ctx), 2)
        mem = list_by_type(reg, CapabilityType.memory.value)
        self.assertEqual(len(mem), 1)

    # ── Test 8: list_enabled works ──────────────────────────────────────

    def test_08_list_enabled(self):
        e1 = _make_test_entry("a", enabled=True)
        e2 = _make_test_entry("b", enabled=False)
        reg = build_registry((e1, e2))
        enabled = list_enabled(reg)
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0].adapter_id, "a")

    # ── Test 9: list_requires_approval works ────────────────────────────

    def test_09_list_requires_approval(self):
        e1 = _make_test_entry("a")
        e2 = CapabilityRegistryEntry(
            adapter_id="b",
            spec=e1.spec,
            lifecycle_state=STATE_APPROVED,
            enabled=True,
            approval_required=False,
        )
        reg = build_registry((e1, e2))
        needs = list_requires_approval(reg)
        self.assertEqual(len(needs), 1)
        self.assertEqual(needs[0].adapter_id, "a")

    # ── Test 10: list_by_lifecycle works ─────────────────────────────────

    def test_10_list_by_lifecycle(self):
        e1 = _make_test_entry("a", lifecycle=STATE_APPROVED)
        e2 = _make_test_entry("b", lifecycle=STATE_DISABLED)
        reg = build_registry((e1, e2))
        approved = list_by_lifecycle(reg, STATE_APPROVED)
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0].adapter_id, "a")

    # ── Test 11: disable_entry returns new registry ─────────────────────

    def test_11_disable_entry(self):
        e1 = _make_test_entry("a", enabled=True)
        reg = build_registry((e1,))
        reg2 = disable_entry(reg, "a", "test reason")
        self.assertIsNot(reg, reg2)
        self.assertNotEqual(reg.registry_hash, reg2.registry_hash)
        entry = get_entry(reg2, "a")
        self.assertFalse(entry.enabled)
        self.assertEqual(entry.lifecycle_state, STATE_DISABLED)

    # ── Test 12: enable_entry returns new registry ──────────────────────

    def test_12_enable_entry(self):
        e1 = _make_test_entry("a", enabled=False, lifecycle=STATE_DISABLED)
        reg = build_registry((e1,))
        reg2 = enable_entry(reg, "a", "test reason")
        self.assertIsNot(reg, reg2)
        entry = get_entry(reg2, "a")
        self.assertTrue(entry.enabled)

    # ── Test 13: disabled entries counted ───────────────────────────────

    def test_13_disabled_counted(self):
        e1 = _make_test_entry("a", enabled=True)
        e2 = _make_test_entry("b", enabled=False)
        reg = build_registry((e1, e2))
        self.assertEqual(reg.disabled_count, 1)

    # ── Test 14: approved entries counted ───────────────────────────────

    def test_14_approved_counted(self):
        e1 = _make_test_entry("a", lifecycle=STATE_APPROVED)
        e2 = _make_test_entry("b", lifecycle=STATE_REGISTERED)
        reg = build_registry((e1, e2))
        self.assertEqual(reg.approved_count, 1)

    # ── Test 15: high risk entries counted ──────────────────────────────

    def test_15_high_risk_counted(self):
        e1 = _make_test_entry("a", risk=CapabilityRiskLevel.high.value)
        e2 = _make_test_entry("b", risk=CapabilityRiskLevel.low.value)
        reg = build_registry((e1, e2))
        self.assertEqual(reg.high_risk_count, 1)

    # ── Test 16: critical risk disabled unless approved ─────────────────

    def test_16_critical_risk_requires_approval(self):
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="critical-test",
            name="Critical Test",
            capability_type=CapabilityType.tool.value,
            risk_level=CapabilityRiskLevel.critical.value,
            execution_modes=("disabled",),
            forbidden_actions=("no_network",),
        )
        entry = CapabilityRegistryEntry(
            adapter_id="critical-test",
            spec=spec,
            lifecycle_state=STATE_PROPOSED,
            enabled=True,  # enabled but not approved — should fail validation
        )
        object.__setattr__(entry, "entry_hash", "test-hash")
        reg = build_registry((entry,))
        valid, errors = validate_registry(reg)
        self.assertFalse(valid)
        self.assertTrue(any("critical" in e.lower() for e in errors))

    # ── Test 17: explicit_execute requires approval ─────────────────────

    def test_17_explicit_execute_needs_approval(self):
        spec = ExternalCapabilityAdapterSpec(
            adapter_id="exec-test",
            name="Exec Test",
            capability_type=CapabilityType.tool.value,
            forbidden_actions=("no_network",),
            execution_modes=("explicit_execute",),
        )
        entry = CapabilityRegistryEntry(
            adapter_id="exec-test",
            spec=spec,
            lifecycle_state=STATE_APPROVED,
            enabled=True,
            execution_mode_default="explicit_execute",
            approval_required=False,  # should fail
        )
        object.__setattr__(entry, "entry_hash", "test-hash")
        reg = build_registry((entry,))
        valid, errors = validate_registry(reg)
        self.assertFalse(valid)
        self.assertTrue(any("approval" in e.lower() for e in errors))

    # ── Test 18: default registry builds ────────────────────────────────

    def test_18_default_registry_builds(self):
        registry = build_default_registry()
        self.assertIsNotNone(registry)
        self.assertGreater(len(registry.entries), 0)
        self.assertNotEqual(registry.registry_hash, "")

    # ── Test 19: repomix registered as context ──────────────────────────

    def test_19_repomix_context(self):
        registry = build_default_registry()
        entry = get_entry(registry, "repomix_context_pack")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.spec.capability_type, CapabilityType.context.value)
        self.assertTrue(entry.enabled)
        self.assertEqual(entry.lifecycle_state, STATE_APPROVED)

    # ── Test 20: ccusage registered as usage ────────────────────────────

    def test_20_ccusage_usage(self):
        registry = build_default_registry()
        entry = get_entry(registry, "ccusage_usage_report")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.spec.capability_type, CapabilityType.usage.value)
        self.assertTrue(entry.enabled)
        self.assertEqual(entry.lifecycle_state, STATE_APPROVED)

    # ── Test 21: anthropic skills disabled/deferred ─────────────────────

    def test_21_anthropic_skills_deferred(self):
        registry = build_default_registry()
        entry = get_entry(registry, "anthropic_skills_format_reference")
        self.assertIsNotNone(entry)
        self.assertFalse(entry.enabled)
        self.assertEqual(entry.lifecycle_state, STATE_REGISTERED)

    # ── Test 22: future placeholders disabled ───────────────────────────

    def test_22_placeholders_disabled(self):
        registry = build_default_registry()
        placeholders = [
            "mem0_memory_intelligence",
            "graphiti_temporal_kg",
            "openhands_agent_worker",
            "autogen_multi_agent",
            "continue_workspace_context",
            "swe_agent_worker",
            "letta_memory_agent",
        ]
        for pid in placeholders:
            entry = get_entry(registry, pid)
            self.assertIsNotNone(entry, f"Missing placeholder: {pid}")
            self.assertFalse(entry.enabled, f"Placeholder {pid} should be disabled")
            self.assertEqual(entry.lifecycle_state, STATE_DISABLED,
                             f"Placeholder {pid} should be disabled state")

    # ── Test 23: registry write/load deterministic ──────────────────────

    def test_23_write_load_roundtrip(self):
        registry = build_default_registry()
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            path = write_registry(registry, f.name)

        try:
            loaded = load_registry(path)
            self.assertEqual(registry.registry_hash, loaded.registry_hash)
            self.assertEqual(len(registry.entries), len(loaded.entries))
            for orig, loaded_entry in zip(registry.entries, loaded.entries):
                self.assertEqual(orig.adapter_id, loaded_entry.adapter_id)
                self.assertEqual(orig.enabled, loaded_entry.enabled)
        finally:
            os.unlink(path)

    # ── Test 24: CLI capability list works ──────────────────────────────

    def test_24_cli_list(self):
        cli = os.path.join(V3_ROOT, "cli", "systemkernel.py")
        rc, stdout, stderr = _run_module(cli, "capability", "list")
        self.assertEqual(rc, 0, f"CLI capability list failed:\n{stderr[:1000]}")
        self.assertIn("repomix_context_pack", stdout)
        self.assertIn("ccusage_usage_report", stdout)

    # ── Test 25: CLI capability summary works ───────────────────────────

    def test_25_cli_summary(self):
        cli = os.path.join(V3_ROOT, "cli", "systemkernel.py")
        rc, stdout, stderr = _run_module(cli, "capability", "summary")
        self.assertEqual(rc, 0, f"CLI capability summary failed:\n{stderr[:1000]}")
        self.assertIn("Total entries", stdout)
        self.assertIn("Enabled", stdout)
        self.assertIn("Disabled", stdout)

    # ── Test 26: CLI capability show works ──────────────────────────────

    def test_26_cli_show(self):
        cli = os.path.join(V3_ROOT, "cli", "systemkernel.py")
        rc, stdout, stderr = _run_module(
            cli, "capability", "show", "repomix_context_pack"
        )
        self.assertEqual(rc, 0, f"CLI capability show failed:\n{stderr[:1000]}")
        self.assertIn("repomix_context_pack", stdout)
        self.assertIn("context", stdout.lower())

    # ── Test 27: no external tools executed ─────────────────────────────

    def test_27_no_external_execution(self):
        """Registry operations must not execute external tools."""
        phase2_files = [
            os.path.join(EXTERNAL_DIR, "capability_registry.py"),
            os.path.join(EXTERNAL_DIR, "default_capabilities.py"),
        ]
        for fpath in phase2_files:
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            self.assertNotIn("subprocess.run", source,
                             f"{os.path.basename(fpath)} should not execute subprocesses")
            self.assertNotIn("npx ", source)

    # ── Test 28: no LLM/vector/agent framework imports ──────────────────

    def test_28_no_banned_imports(self):
        BANNED = {"openai", "anthropic", "langchain", "crewai", "autogen",
                  "mem0", "graphiti", "chromadb", "qdrant", "milvus"}
        phase2_files = ["capability_registry.py", "default_capabilities.py"]
        for fname in phase2_files:
            fpath = os.path.join(EXTERNAL_DIR, fname)
            with open(fpath, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0].lower()
                        self.assertNotIn(root, BANNED,
                                         f"{fname} imports banned: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root = node.module.split(".")[0].lower()
                        self.assertNotIn(root, BANNED,
                                         f"{fname} imports banned: {node.module}")

    # ── Test 29: count summaries correct ────────────────────────────────

    def test_29_counts_correct(self):
        registry = build_default_registry()
        self.assertEqual(registry.enabled_count + registry.disabled_count,
                         len(registry.entries))
        self.assertEqual(registry.enabled_count, 2)  # repomix + ccusage
        self.assertEqual(registry.disabled_count, 8)  # anthropic + 7 placeholders


class TestPhase2Regression(unittest.TestCase):

    def test_v4_baseline_guard_passes(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_v4_baseline_guard.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Baseline guard failed:\n{result.stderr[:1000]}")

    def test_kernel_invariants_passes(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_kernel_invariants.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Kernel invariants failed:\n{result.stderr[:1000]}")
        self.assertIn("purity_score == 100", result.stdout)


if __name__ == "__main__":
    unittest.main()
