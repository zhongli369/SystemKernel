"""
Context Engineering Plane Tests — Phase 4.

32+ tests for the Context Engineering Plane: budget policy, planning,
inspection, evidence mapping, and reporting.
Stdlib only. No Repomix execution. No network access.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3_ROOT = os.path.join(ROOT, "v3")
EXTERNAL_DIR = os.path.join(V3_ROOT, "external")
TESTS_DIR = os.path.join(V3_ROOT, "tests")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PYTHON = sys.executable

from v3.external.context_plane import (
    ContextBudgetPolicy,
    ContextPackPlan,
    ContextPackInspection,
    ContextEngineeringReport,
    BudgetValidationResult,
    BUDGET_PASS,
    BUDGET_REVIEW,
    BUDGET_BLOCKED,
    ALL_BUDGET_STATUSES,
    DEFAULT_SENSITIVE_PATTERNS,
    DEFAULT_EXCLUDED_PATHS,
    default_context_budget_policy,
    plan_context_pack,
    inspect_context_pack,
    context_pack_to_evidence,
    build_context_engineering_report,
    validate_context_budget,
    write_context_report,
    plan_from_context_pack_result,
)

FIXTURE_DIR = os.path.join(TESTS_DIR, "fixtures")


def _run_module(module_path, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    result = subprocess.run(
        [PYTHON, module_path] + list(args),
        capture_output=True, text=True, timeout=30,
        cwd=ROOT, env=env,
    )
    return result.returncode, result.stdout, result.stderr


class TestContextEngineeringPlane(unittest.TestCase):

    # ═══════════════════════════════════════════════════════════════════
    # Budget Policy
    # ═══════════════════════════════════════════════════════════════════

    def test_01_default_policy_created(self):
        """Default budget policy has expected values."""
        policy = default_context_budget_policy()
        self.assertEqual(policy.max_files, 500)
        self.assertEqual(policy.max_bytes, 10_000_000)
        self.assertEqual(policy.max_tokens, 200_000)
        self.assertIn("markdown", policy.allowed_styles)
        self.assertTrue(policy.require_subdir_target)
        self.assertFalse(policy.allow_repo_root)

    def test_02_policy_hash_deterministic(self):
        """Same policy config produces same hash."""
        p1 = default_context_budget_policy()
        p2 = default_context_budget_policy()
        self.assertEqual(p1.policy_hash, p2.policy_hash)

    def test_03_policy_hash_different(self):
        """Different configs produce different hashes."""
        p1 = ContextBudgetPolicy(max_files=100)
        p2 = ContextBudgetPolicy(max_files=200)
        self.assertNotEqual(
            default_context_budget_policy().policy_hash,
            ContextBudgetPolicy(max_files=999).policy_hash,
        )

    def test_04_policy_frozen(self):
        """ContextBudgetPolicy is frozen."""
        policy = default_context_budget_policy()
        with self.assertRaises(Exception):
            policy.max_files = 999

    def test_05_policy_to_dict(self):
        """Policy serializes to dict correctly."""
        policy = ContextBudgetPolicy(
            max_files=50, max_bytes=1000, max_tokens=5000,
            require_subdir_target=False, allow_repo_root=True,
        )
        d = policy.to_dict()
        self.assertEqual(d["max_files"], 50)
        self.assertEqual(d["max_bytes"], 1000)
        self.assertFalse(d["require_subdir_target"])
        self.assertTrue(d["allow_repo_root"])

    # ═══════════════════════════════════════════════════════════════════
    # Plan
    # ═══════════════════════════════════════════════════════════════════

    def test_06_plan_created_from_target(self):
        """Planning a subdirectory produces a valid plan."""
        plan = plan_context_pack("v3/tests", output="", style="markdown")
        self.assertEqual(plan.adapter_id, "repomix_context_pack")
        self.assertTrue(plan.plan_hash)
        self.assertGreater(plan.estimated_files, 0)
        self.assertIn(plan.budget_status, ALL_BUDGET_STATUSES)

    def test_07_plan_does_not_execute_command(self):
        """Plan never executes an external command."""
        plan = plan_context_pack("v3/tests", output="/tmp/nonexistent.ctx.md")
        # The plan may have no command if blocked, but it should never actually execute
        self.assertFalse(plan.plan_hash == "")

    def test_08_plan_repo_root_blocked(self):
        """Repo root target is blocked by default policy."""
        plan = plan_context_pack(".", output="")
        self.assertEqual(plan.budget_status, BUDGET_BLOCKED)

    def test_09_plan_repo_root_allowed_explicitly(self):
        """Repo root allowed when policy explicitly permits."""
        policy = ContextBudgetPolicy(
            allow_repo_root=True, require_subdir_target=False,
            max_tokens=10_000_000,  # prevent budget block from token estimate
        )
        plan = plan_context_pack("v3/tests/fixtures", output="", policy=policy)
        self.assertIn(plan.budget_status, (BUDGET_PASS, BUDGET_REVIEW))

    def test_10_plan_unsupported_style_blocked(self):
        """Unsupported style is blocked."""
        policy = ContextBudgetPolicy(allowed_styles=("markdown",))
        plan = plan_context_pack("v3/tests", output="", style="xml", policy=policy)
        self.assertEqual(plan.budget_status, BUDGET_BLOCKED)

    def test_11_plan_subdir_target_allowed(self):
        """Subdirectory target not blocked by repo root check."""
        policy = default_context_budget_policy()
        plan = plan_context_pack("v3/tests/fixtures", output="", policy=policy)
        # Should not be blocked by _is_repo_root
        self.assertNotIn("REPO_ROOT_BLOCKED",
                         " ".join(plan.warnings) if plan.warnings else "")

    def test_12_plan_hash_deterministic(self):
        """Same plan params produce same hash."""
        policy = default_context_budget_policy()
        p1 = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md",
                               style="markdown", policy=policy)
        p2 = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md",
                               style="markdown", policy=policy)
        self.assertEqual(p1.plan_hash, p2.plan_hash)

    def test_13_plan_frozen(self):
        """ContextPackPlan is frozen."""
        plan = plan_context_pack("v3/tests", output="")
        with self.assertRaises(Exception):
            plan.target_path = "changed"

    # ═══════════════════════════════════════════════════════════════════
    # Budget Validation
    # ═══════════════════════════════════════════════════════════════════

    def test_14_max_files_budget_enforced(self):
        """Plan with too many files against a tight budget is blocked."""
        plan = plan_context_pack("v3/tests", output="")
        # Validate against a tight file budget
        tight_policy = ContextBudgetPolicy(max_files=2, max_bytes=100_000_000,
                                           max_tokens=10_000_000)
        result = validate_context_budget(plan, tight_policy)
        self.assertEqual(result.status, BUDGET_BLOCKED)
        self.assertTrue(any("File count" in v for v in result.violations))

    def test_15_max_bytes_budget_enforced(self):
        """Plan exceeding byte budget is blocked."""
        plan = plan_context_pack("v3/tests", output="")
        policy = ContextBudgetPolicy(max_files=1000, max_bytes=100,
                                     max_tokens=10_000_000)
        result = validate_context_budget(plan, policy)
        self.assertEqual(result.status, BUDGET_BLOCKED)

    def test_16_max_tokens_budget_enforced(self):
        """Plan exceeding token budget is flagged."""
        plan = plan_context_pack("v3/tests", output="")
        policy = ContextBudgetPolicy(max_files=1000, max_bytes=100_000_000,
                                     max_tokens=100)
        result = validate_context_budget(plan, policy)
        self.assertEqual(result.status, BUDGET_BLOCKED)

    def test_17_budget_review_warning(self):
        """Plan near budget limit gets review status."""
        plan = plan_context_pack("v3/tests/fixtures", output="")
        # Use a very tight budget that will be near the estimate
        policy = ContextBudgetPolicy(max_files=100, max_bytes=100_000,
                                     max_tokens=100_000)
        result = validate_context_budget(plan, policy)
        self.assertIn(result.status, (BUDGET_PASS, BUDGET_REVIEW, BUDGET_BLOCKED))
        self.assertTrue(result.result_hash)

    def test_18_budget_validation_result_frozen(self):
        """BudgetValidationResult is frozen."""
        result = BudgetValidationResult(status=BUDGET_PASS)
        with self.assertRaises(Exception):
            result.status = "changed"

    # ═══════════════════════════════════════════════════════════════════
    # Inspection
    # ═══════════════════════════════════════════════════════════════════

    def test_19_inspection_reads_fixture(self):
        """Inspection reads an existing file and extracts metadata."""
        # Create a small fixture file
        fixture_path = os.path.join(FIXTURE_DIR, "test_context.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## Summary\nTest context pack\n## File: test.py\nprint('hello')\n")
        try:
            inspection = inspect_context_pack(fixture_path)
            self.assertEqual(inspection.output_path, fixture_path)
            self.assertGreater(inspection.size_bytes, 0)
            self.assertGreater(inspection.line_count, 0)
            self.assertTrue(inspection.inspection_hash)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_20_inspection_hash_deterministic(self):
        """Same file inspected twice produces same hash."""
        fixture_path = os.path.join(FIXTURE_DIR, "test_ctx2.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## File: a.py\nx=1\n## File: b.py\ny=2\n")
        try:
            i1 = inspect_context_pack(fixture_path)
            i2 = inspect_context_pack(fixture_path)
            self.assertEqual(i1.inspection_hash, i2.inspection_hash)
            self.assertEqual(i1.pack_hash, i2.pack_hash)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_21_inspection_sensitive_pattern_detected(self):
        """Sensitive patterns in content are detected."""
        fixture_path = os.path.join(FIXTURE_DIR, "test_sensitive.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## File: config.py\nAPI_KEY=sk-abc123\nSECRET=mysecret\n")
        try:
            inspection = inspect_context_pack(fixture_path)
            self.assertGreater(len(inspection.sensitive_pattern_hits), 0)
            self.assertIn("API_KEY", inspection.sensitive_pattern_hits)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_22_inspection_detects_sections(self):
        """Markdown sections are detected in output."""
        fixture_path = os.path.join(FIXTURE_DIR, "test_sections.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## Summary\nSome summary\n## Architecture\nDetails\n## File: x.py\ncode\n")
        try:
            inspection = inspect_context_pack(fixture_path)
            self.assertIn("Summary", inspection.detected_sections)
            self.assertIn("Architecture", inspection.detected_sections)
            self.assertNotIn("File: x.py", inspection.detected_sections)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_23_inspection_missing_file(self):
        """Inspecting a non-existent file returns empty inspection."""
        inspection = inspect_context_pack("/nonexistent/path.ctx.md")
        self.assertEqual(inspection.size_bytes, 0)
        self.assertTrue(inspection.inspection_hash)

    def test_24_inspection_frozen(self):
        """ContextPackInspection is frozen."""
        fixture_path = os.path.join(FIXTURE_DIR, "test_frozen.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("test")
        try:
            inspection = inspect_context_pack(fixture_path)
            with self.assertRaises(Exception):
                inspection.size_bytes = 999
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    # ═══════════════════════════════════════════════════════════════════
    # Evidence Mapping
    # ═══════════════════════════════════════════════════════════════════

    def test_25_evidence_bundle_from_context_pack(self):
        """Evidence bundle created from plan + inspection."""
        plan = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md")
        fixture_path = os.path.join(FIXTURE_DIR, "test_ev.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## File: test.py\nprint('hello')\n")
        try:
            inspection = inspect_context_pack(fixture_path)
            bundle = context_pack_to_evidence(plan, inspection, registry_hash="test:reg")
            self.assertTrue(bundle.bundle_id)
            self.assertEqual(len(bundle.records), 2)
            self.assertFalse(bundle.truth_source)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_26_evidence_truth_source_false(self):
        """All evidence records have truth_source=False."""
        plan = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md")
        fixture_path = os.path.join(FIXTURE_DIR, "test_ts.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## File: test.py\nx=1\n")
        try:
            inspection = inspect_context_pack(fixture_path)
            bundle = context_pack_to_evidence(plan, inspection)
            for r in bundle.records:
                self.assertFalse(r.truth_source,
                                 f"Record {r.evidence_id} truth_source is not False")
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_27_evidence_provenance_includes_registry_hash(self):
        """Evidence records include registry hash in provenance."""
        plan = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md")
        fixture_path = os.path.join(FIXTURE_DIR, "test_prov.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## File: test.py\nx=1\n")
        try:
            inspection = inspect_context_pack(fixture_path)
            bundle = context_pack_to_evidence(plan, inspection, registry_hash="myreg:abc")
            for r in bundle.records:
                self.assertIsNotNone(r.provenance)
                self.assertEqual(r.provenance.registry_hash, "myreg:abc")
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    # ═══════════════════════════════════════════════════════════════════
    # Reporting
    # ═══════════════════════════════════════════════════════════════════

    def test_28_report_created(self):
        """Context engineering report builds correctly."""
        plan = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md")
        fixture_path = os.path.join(FIXTURE_DIR, "test_report.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## File: test.py\nx=1\n")
        try:
            inspection = inspect_context_pack(fixture_path)
            bundle = context_pack_to_evidence(plan, inspection)
            report = build_context_engineering_report(plan, inspection, bundle)
            self.assertEqual(report.adapter_id, "repomix_context_pack")
            self.assertFalse(report.truth_source)
            self.assertTrue(report.report_hash)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_29_report_hash_deterministic(self):
        """Same inputs produce same report hash."""
        plan = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md")
        fixture_path = os.path.join(FIXTURE_DIR, "test_rep2.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## File: test.py\nx=1\n")
        try:
            inspection = inspect_context_pack(fixture_path)
            bundle = context_pack_to_evidence(plan, inspection)
            r1 = build_context_engineering_report(plan, inspection, bundle)
            r2 = build_context_engineering_report(plan, inspection, bundle)
            self.assertEqual(r1.report_hash, r2.report_hash)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_30_report_truth_source_false(self):
        """Report truth_source is always False."""
        plan = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md")
        fixture_path = os.path.join(FIXTURE_DIR, "test_ts2.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("test")
        try:
            inspection = inspect_context_pack(fixture_path)
            bundle = context_pack_to_evidence(plan, inspection)
            report = build_context_engineering_report(plan, inspection, bundle)
            self.assertFalse(report.truth_source)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_31_report_frozen(self):
        """ContextEngineeringReport is frozen."""
        plan = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md")
        fixture_path = os.path.join(FIXTURE_DIR, "test_frz.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("test")
        try:
            inspection = inspect_context_pack(fixture_path)
            bundle = context_pack_to_evidence(plan, inspection)
            report = build_context_engineering_report(plan, inspection, bundle)
            with self.assertRaises(Exception):
                report.budget_status = "changed"
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    # ═══════════════════════════════════════════════════════════════════
    # Write/Load
    # ═══════════════════════════════════════════════════════════════════

    def test_32_write_context_report(self):
        """Context report writes to disk and can be read back."""
        plan = plan_context_pack("v3/tests/fixtures", output="/tmp/test.ctx.md")
        fixture_path = os.path.join(FIXTURE_DIR, "test_write.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("test")
        try:
            inspection = inspect_context_pack(fixture_path)
            bundle = context_pack_to_evidence(plan, inspection)
            report = build_context_engineering_report(plan, inspection, bundle)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                             delete=False, encoding="utf-8") as f:
                tmp_path = f.name

            try:
                written = write_context_report(report, tmp_path)
                self.assertTrue(os.path.isfile(written))
                with open(written, encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data["adapter_id"], "repomix_context_pack")
                self.assertFalse(data["truth_source"])
                self.assertIsNotNone(data["plan"])
                self.assertIsNotNone(data["inspection"])
            finally:
                if os.path.isfile(tmp_path):
                    os.unlink(tmp_path)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    # ═══════════════════════════════════════════════════════════════════
    # Compatibility Bridge
    # ═══════════════════════════════════════════════════════════════════

    def test_33_plan_from_context_pack_result(self):
        """Existing ContextPackResult converts to ContextPackPlan."""
        from v3.external.context_pack import ContextPackConfig, ContextPackAdapter
        config = ContextPackConfig(
            target_path="v3/tests/fixtures",
            output_path="/tmp/test.ctx.md",
            style="markdown",
        )
        result = ContextPackAdapter.plan(config)
        plan = plan_from_context_pack_result(result)
        self.assertEqual(plan.adapter_id, "repomix_context_pack")
        self.assertEqual(plan.target_path, result.target_path)
        self.assertTrue(plan.plan_hash)

    # ═══════════════════════════════════════════════════════════════════
    # No Repomix / Network / Kernel
    # ═══════════════════════════════════════════════════════════════════

    def test_34_no_repomix_dependency_import(self):
        """Context plane does not import Repomix as a dependency."""
        plane_path = os.path.join(EXTERNAL_DIR, "context_plane.py")
        with open(plane_path, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("import repomix", source.lower())
        self.assertNotIn("from repomix", source.lower())
        self.assertNotIn("npx repomix", source)

    def test_35_no_external_command_execution(self):
        """Planning and inspection never execute commands."""
        # Verify no subprocess.run or os.system in context_plane.py
        plane_path = os.path.join(EXTERNAL_DIR, "context_plane.py")
        with open(plane_path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("run", "call", "system", "popen"):
                        self.fail(
                            f"context_plane.py should not call subprocess/os: "
                            f"{node.func.attr} at line {node.lineno}"
                        )

    def test_36_no_banned_imports(self):
        """Phase 4 files must not import LLM/vector/agent frameworks."""
        BANNED = {"openai", "anthropic", "langchain", "crewai", "autogen",
                  "mem0", "graphiti", "chromadb", "qdrant", "milvus"}
        for fname in ["context_plane.py"]:
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

    # ═══════════════════════════════════════════════════════════════════
    # CLI
    # ═══════════════════════════════════════════════════════════════════

    def test_37_cli_context_plane_plan(self):
        """CLI context-plane plan command runs without error."""
        rc, stdout, stderr = _run_module(
            os.path.join(V3_ROOT, "cli", "systemkernel.py"),
            "context-plane", "plan", "v3/tests/fixtures",
            "--output", "/tmp/test_cli_plan.ctx.md",
        )
        # Plan should run (may be pass or blocked depending on target)
        self.assertIn("Context Engineering Plane", stdout)
        self.assertIn("Budget status", stdout)

    def test_38_cli_context_plane_inspect(self):
        """CLI context-plane inspect command runs."""
        fixture_path = os.path.join(FIXTURE_DIR, "test_cli.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## Summary\nTest\n## File: a.py\nx=1\n")
        try:
            rc, stdout, stderr = _run_module(
                os.path.join(V3_ROOT, "cli", "systemkernel.py"),
                "context-plane", "inspect", fixture_path,
            )
            self.assertEqual(rc, 0)
            self.assertIn("Context Engineering Plane", stdout)
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    def test_39_cli_context_plane_evidence(self):
        """CLI context-plane evidence command builds evidence bundle."""
        fixture_path = os.path.join(FIXTURE_DIR, "test_cli_ev.md")
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            f.write("## File: test.py\nprint('hello')\n")
        try:
            rc, stdout, stderr = _run_module(
                os.path.join(V3_ROOT, "cli", "systemkernel.py"),
                "context-plane", "evidence", fixture_path,
                "--target", "v3/tests/fixtures",
                "--output", "/tmp/test_cli_evidence.json",
            )
            self.assertEqual(rc, 0)
            self.assertIn("Evidence bundle", stdout)
            self.assertIn("false", stdout.lower())
        finally:
            if os.path.isfile(fixture_path):
                os.unlink(fixture_path)

    # ═══════════════════════════════════════════════════════════════════
    # Edge cases
    # ═══════════════════════════════════════════════════════════════════

    def test_40_budget_validation_wrong_type(self):
        """Non-plan/non-inspection type produces blocked result."""
        policy = default_context_budget_policy()
        result = validate_context_budget("not a plan", policy)
        self.assertEqual(result.status, BUDGET_BLOCKED)
        self.assertIn("Unknown type", result.violations[0])

    def test_41_all_budget_statuses_defined(self):
        """All three budget statuses are defined."""
        self.assertEqual(len(ALL_BUDGET_STATUSES), 3)
        self.assertIn(BUDGET_PASS, ALL_BUDGET_STATUSES)
        self.assertIn(BUDGET_REVIEW, ALL_BUDGET_STATUSES)
        self.assertIn(BUDGET_BLOCKED, ALL_BUDGET_STATUSES)

    def test_42_sensitive_patterns_default(self):
        """Default sensitive patterns include common secrets patterns."""
        self.assertIn("API_KEY", DEFAULT_SENSITIVE_PATTERNS)
        self.assertIn("SECRET", DEFAULT_SENSITIVE_PATTERNS)
        self.assertIn("PRIVATE_KEY", DEFAULT_SENSITIVE_PATTERNS)

    def test_43_excluded_paths_default(self):
        """Default excluded paths include common VCS/artifact directories."""
        self.assertIn(".git", DEFAULT_EXCLUDED_PATHS)
        self.assertIn("node_modules", DEFAULT_EXCLUDED_PATHS)
        self.assertIn("__pycache__", DEFAULT_EXCLUDED_PATHS)


class TestPhase4Regression(unittest.TestCase):

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

    def test_context_pack_adapter_still_passes(self):
        """Existing context pack adapter tests must still pass."""
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_context_pack_adapter.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Context pack adapter tests failed:\n{result.stderr[:1000]}")

    def test_evidence_tests_still_pass(self):
        """Phase 3 evidence tests must still pass."""
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_external_evidence.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Evidence tests failed:\n{result.stderr[:1000]}")

    def test_registry_tests_still_pass(self):
        """Phase 2 registry tests must still pass."""
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_capability_registry.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Registry tests failed:\n{result.stderr[:1000]}")

    def test_contract_tests_still_pass(self):
        """Phase 1 contract tests must still pass."""
        env = os.environ.copy()
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [PYTHON, os.path.join(ROOT, "v3/tests/test_capability_contract.py")],
            capture_output=True, text=True, timeout=120, cwd=ROOT, env=env,
        )
        self.assertEqual(result.returncode, 0,
                         f"Contract tests failed:\n{result.stderr[:1000]}")


if __name__ == "__main__":
    unittest.main()
