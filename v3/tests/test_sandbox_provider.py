"""Sandbox Provider Tests — L1 Sandbox."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.external.sandbox.sandbox_provider import (
    SandboxEnv, SandboxHandle, SandboxResult, SandboxProvider,
    SANDBOX_CREATED, SANDBOX_RUNNING, SANDBOX_DESTROYED,
    is_valid_transition, ALL_SANDBOX_STATES,
)


class TestSandboxProvider(unittest.TestCase):

    def test_01_state_transitions_valid(self):
        self.assertTrue(is_valid_transition(SANDBOX_CREATED, SANDBOX_RUNNING))
        self.assertTrue(is_valid_transition(SANDBOX_CREATED, SANDBOX_DESTROYED))
        self.assertFalse(is_valid_transition(SANDBOX_CREATED, "paused"))

    def test_02_sandbox_env_immutable_with_env(self):
        env = SandboxEnv(env_vars=(("A", "1"),))
        env2 = env.with_env("B", "2")
        self.assertNotEqual(id(env), id(env2))
        self.assertEqual(len(env.env_vars), 1)
        self.assertEqual(len(env2.env_vars), 2)

    def test_03_sandbox_env_with_image(self):
        env = SandboxEnv()
        env2 = env.with_image("alpine:latest")
        self.assertEqual(env2.image, "alpine:latest")

    def test_04_sandbox_result_success(self):
        r = SandboxResult(exit_code=0, stdout="ok")
        self.assertTrue(r.success)
        r2 = SandboxResult(exit_code=1, stderr="err")
        self.assertFalse(r2.success)

    def test_05_sandbox_result_failed_factory(self):
        r = SandboxResult.failed(handle_id="h1", reason="boom")
        self.assertEqual(r.exit_code, 1)
        self.assertEqual(r.stderr, "boom")

    def test_06_evidence_hash_deterministic(self):
        h1 = SandboxResult.compute_evidence_hash("h", "cmd", "out", 0)
        h2 = SandboxResult.compute_evidence_hash("h", "cmd", "out", 0)
        self.assertEqual(h1, h2)
        h3 = SandboxResult.compute_evidence_hash("h", "cmd", "different", 0)
        self.assertNotEqual(h1, h3)

    def test_07_sandbox_handle_initial_state(self):
        h = SandboxHandle(handle_id="test")
        self.assertEqual(h.state, SANDBOX_CREATED)

    def test_08_all_states_defined(self):
        self.assertEqual(len(ALL_SANDBOX_STATES), 4)
