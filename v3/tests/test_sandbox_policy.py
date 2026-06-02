"""Sandbox Policy Tests — L1 Sandbox."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.external.sandbox.sandbox_policy import (
    SandboxPolicy, policy_strict, policy_isolated_build,
    policy_network_readonly, get_policy, ALL_PRESET_POLICIES,
    ALL_RISK_LEVELS,
)


class TestSandboxPolicy(unittest.TestCase):

    def test_01_strict_policy_denies_all(self):
        p = policy_strict()
        self.assertFalse(p.allow_network)
        self.assertFalse(p.allow_file_write)
        self.assertFalse(p.allow_subprocess)
        self.assertEqual(p.allowed_paths, ())
        self.assertEqual(p.policy_id, "strict")

    def test_02_isolated_build_allows_file_write(self):
        p = policy_isolated_build()
        self.assertTrue(p.allow_file_write)
        self.assertIn("/tmp/build/", p.allowed_paths)

    def test_03_network_readonly_allows_network(self):
        p = policy_network_readonly()
        self.assertTrue(p.allow_network)
        self.assertFalse(p.allow_file_write)

    def test_04_require_evidence_wrap_always_true(self):
        p = SandboxPolicy(policy_id="test", require_evidence_wrap=False)
        self.assertTrue(p.require_evidence_wrap)

    def test_05_empty_allowed_paths_denies_all(self):
        p = SandboxPolicy(policy_id="test", allowed_paths=())
        self.assertFalse(p.allows_path("/any/path"))

    def test_06_allows_path_whitelist(self):
        p = SandboxPolicy(policy_id="test", allowed_paths=("/tmp/ok/",))
        self.assertTrue(p.allows_path("/tmp/ok/"))
        self.assertFalse(p.allows_path("/tmp/bad/"))

    def test_07_policy_hash_deterministic(self):
        p1 = policy_strict()
        p2 = policy_strict()
        self.assertEqual(p1.policy_hash, p2.policy_hash)

    def test_08_get_policy_returns_correct_type(self):
        p = get_policy("strict")
        self.assertIsNotNone(p)
        self.assertEqual(p.policy_id, "strict")

    def test_09_get_policy_unknown_returns_none(self):
        p = get_policy("nonexistent")
        self.assertIsNone(p)

    def test_10_validate_command_rejects_empty(self):
        p = policy_strict()
        ok, reason = p.validate_command("")
        self.assertFalse(ok)
        self.assertIn("Empty", reason)

    def test_11_all_risk_levels_present(self):
        self.assertEqual(len(ALL_RISK_LEVELS), 4)

    def test_12_all_preset_policies_exist(self):
        for pid in ["strict", "isolated_build", "network_readonly"]:
            self.assertIn(pid, ALL_PRESET_POLICIES)
