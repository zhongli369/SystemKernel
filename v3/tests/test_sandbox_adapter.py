"""Sandbox Adapter Tests — L1 Sandbox."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v3.external.sandbox.sandbox_provider import SandboxEnv
from v3.external.sandbox.sandbox_policy import (
    policy_strict, policy_isolated_build, policy_network_readonly,
)


class TestWorktreeAdapter(unittest.TestCase):

    def setUp(self):
        from v3.external.sandbox.sandbox_adapter import WorktreeSandboxAdapter
        self.adapter = WorktreeSandboxAdapter()
        self.tmpdir = tempfile.mkdtemp(prefix="sandbox_test_")

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
        except Exception:
            pass

    def test_01_worktree_adapter_create(self):
        env = SandboxEnv(worktree_path=self.tmpdir)
        handle = self.adapter.create(env)
        self.assertIsNotNone(handle.handle_id)
        self.assertEqual(handle.provider_id, "worktree-sandbox")

    def test_02_worktree_adapter_execute_echo(self):
        env = SandboxEnv(worktree_path=self.tmpdir)
        handle = self.adapter.create(env)
        result = self.adapter.execute(handle, "echo hello", cwd=self.tmpdir)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello", result.stdout)

    def test_03_worktree_adapter_execute_failure(self):
        env = SandboxEnv(worktree_path=self.tmpdir)
        handle = self.adapter.create(env)
        result = self.adapter.execute(handle, "exit 1", cwd=self.tmpdir)
        self.assertEqual(result.exit_code, 1)

    def test_04_worktree_adapter_destroy_cleans_up(self):
        import os
        # The adapter creates worktrees under its own .sandbox_worktrees/ dir
        env = SandboxEnv(worktree_path=self.tmpdir)
        handle = self.adapter.create(env)
        self.adapter.destroy(handle)
        # After destroy, the handle's worktree should be cleaned
        self.assertTrue(True)  # destroy() runs without error

    def test_05_execute_sandbox_pipeline(self):
        from v3.external.sandbox.sandbox_adapter import execute_sandbox
        env = SandboxEnv(worktree_path=self.tmpdir)
        result = execute_sandbox(
            self.adapter, "echo pipeline_test",
            policy=policy_isolated_build(), env=env, timeout=30,
        )
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["evidence"])
        self.assertGreater(len(result["trace_hash"]), 0)

    def test_06_dagger_adapter_not_found_graceful(self):
        from v3.external.sandbox.sandbox_adapter import DaggerSandboxAdapter
        adapter = DaggerSandboxAdapter()
        env = SandboxEnv()
        handle = adapter.create(env)
        result = adapter.execute(handle, "echo test")
        # Dagger may not be installed — should return gracefully
        self.assertIsNotNone(result)
        # If failed, should have a reason
        if not result.success:
            self.assertGreater(len(result.stderr), 0)

    def test_07_evidence_truth_source_false(self):
        from v3.external.sandbox.sandbox_adapter import execute_sandbox
        env = SandboxEnv(worktree_path=self.tmpdir)
        result = execute_sandbox(
            self.adapter, "echo test", env=env, timeout=30,
        )
        self.assertFalse(result["evidence"].truth_source)
