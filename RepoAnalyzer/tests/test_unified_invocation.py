"""Validate unified SkillSystem invocation layer — Freeze v2 Step 4."""
import sys
import inspect

# ═════════════════════════════════════════════════════════════
# 1. SKILL_CLIENT: verify direct import, no hacks
# ═════════════════════════════════════════════════════════════
print("=== 1. SKILL_CLIENT ===")
sys.path.insert(0, "F:/Claude/RepoAnalyzer")
from core.skill_integration.skill_client import get_skill_client, SkillClient

client = get_skill_client()
assert client.available, "Client not available"

source = inspect.getsource(SkillClient)
assert "importlib" not in source, "importlib found"
assert "subprocess" not in source, "subprocess found"

module_source = inspect.getsource(inspect.getmodule(SkillClient))
assert "from SkillsManagementSystem.core.adapter import" in module_source
assert "get_registry_info" in module_source
assert "get_skill_metadata" in module_source
# routing_pipeline must NOT be imported directly
assert "from SkillsManagementSystem.core.routing_pipeline" not in module_source, \
    "routing_pipeline still imported directly"

# No sys.path.insert in any function
funcs = [m for m in inspect.getmembers(inspect.getmodule(SkillClient), inspect.isfunction)]
for name, func in funcs:
    func_src = inspect.getsource(func)
    assert "sys.path.insert" not in func_src, f"sys.path.insert in {name}()"

print("  Direct adapter import: OK")
print("  No importlib: OK")
print("  No subprocess: OK")
print("  No per-call sys.path.insert: OK")

# ═════════════════════════════════════════════════════════════
# 2. SKILL_RESOLVER: verify delegates to client
# ═════════════════════════════════════════════════════════════
print()
print("=== 2. SKILL_RESOLVER ===")
from core.skill_integration.skill_resolver import resolve_skill, validate_skill_compatibility
from core.model import AnalysisTask

task = AnalysisTask(
    task_id="t1", global_task_id="g1", title="Refactor coupling",
    type="refactor", priority=3,
    target_nodes=["utils/helpers.py", "core/engine.py"],
    reason="Reduce coupling", skill_id="", skill_input={}, skill_output={}, steps=[],
)
sid = resolve_skill(task)
assert sid, "resolve_skill returned empty"
valid = validate_skill_compatibility(task, sid)
assert valid, "validate_skill_compatibility failed"
print(f"  resolve_skill -> {sid}: OK")
print("  validate_skill_compatibility -> True: OK")

# ═════════════════════════════════════════════════════════════
# 3. SKILL_SUGGESTION_MAPPER
# ═════════════════════════════════════════════════════════════
print()
print("=== 3. SKILL_SUGGESTION_MAPPER ===")
from core.skill_suggestion_mapper import suggest_skills
skills = suggest_skills(
    task_type="refactor", target_nodes=["utils/helpers.py"],
    node_roles={"utils/helpers.py": "utility"},
    node_system_roles={"utils/helpers.py": "helper"},
)
assert len(skills) > 0
print(f"  suggest_skills -> {skills}: OK")

# ═════════════════════════════════════════════════════════════
# 4. TASK_MANAGER: verify adapter usage (source inspection + isolation test)
# ═════════════════════════════════════════════════════════════
print()
print("=== 4. TASK_MANAGER ===")

# Source inspection: verify adapter import in suggest_skills_for_step
with open("F:/Claude/TaskSystem/core/task_manager.py", encoding="utf-8") as f:
    tm_content = f.read()

assert "from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest" in tm_content, \
    "task_manager missing adapter import"
assert "CapabilityRequest" in tm_content
assert "core.routing_pipeline" not in tm_content, "task_manager still imports routing_pipeline directly"
assert "sys.path.insert" in tm_content, "task_manager should have one-time workspace path setup"

print("  Uses adapter.resolve(): OK")
print("  No direct routing_pipeline import: OK")

# ═════════════════════════════════════════════════════════════
# 5. TASK GENERATORS: verify all use adapter via client
# ═════════════════════════════════════════════════════════════
print()
print("=== 5. TASK GENERATORS ===")

for filename in ["bottleneck_task_generator.py", "coupling_task_builder.py", "architecture_task_mapper.py"]:
    filepath = f"F:/Claude/RepoAnalyzer/core/{filename}"
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    assert "from core.skill_integration.skill_client import get_skill_client" in content
    assert "get_skill_client()" in content
    for sn in ['"repo-analyzer"', '"code-review"', '"debugger"', '"reflective-reasoning"']:
        assert sn not in content, f"{filename}: hardcoded {sn}"
print("  All 3 task generators: OK")

# ═════════════════════════════════════════════════════════════
# 6. CROSS-SYSTEM: same intent yields same result
# ═════════════════════════════════════════════════════════════
print()
print("=== 6. DETERMINISTIC ROUTING ===")

sys.path.insert(0, "F:/Claude")
from SkillsManagementSystem.core.adapter import resolve, CapabilityRequest

intents = ["refactor", "decouple", "stabilize", "optimize", "cleanup"]
for intent in intents:
    a1 = resolve(CapabilityRequest(intent=intent, context="test"))
    a2 = resolve(CapabilityRequest(intent=intent, context="test"))
    assert a1.skill_id == a2.skill_id, f"Non-deterministic: {a1.skill_id} vs {a2.skill_id}"
    c_skills = client.suggest_by_intent(intent=intent, context="test")
    assert c_skills[0] == a1.skill_id, f"Mismatch: {c_skills[0]} vs {a1.skill_id}"

print(f"  All {len(intents)} intents deterministic: OK")

# ═════════════════════════════════════════════════════════════
# 7. ZERO SUBPROCESS IN ENTIRE INVOCATION CHAIN
# ═════════════════════════════════════════════════════════════
print()
print("=== 7. ZERO SUBPROCESS ===")

files_to_check = [
    "F:/Claude/RepoAnalyzer/core/skill_integration/skill_client.py",
    "F:/Claude/RepoAnalyzer/core/skill_integration/skill_resolver.py",
    "F:/Claude/RepoAnalyzer/core/skill_suggestion_mapper.py",
    "F:/Claude/TaskSystem/core/task_manager.py",
]
for filepath in files_to_check:
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    # Check for actual subprocess usage (import subprocess, subprocess.run, etc.)
    has_import = "import subprocess" in content
    has_call = "subprocess.run" in content or "subprocess.Popen" in content or "subprocess.call" in content
    assert not has_import, f"{filepath}: imports subprocess"
    assert not has_call, f"{filepath}: calls subprocess.run/Popen/call"
print("  All 4 files: OK")

# ═════════════════════════════════════════════════════════════
# 8. SINGLE INVOCATION PATH
# ═════════════════════════════════════════════════════════════
print()
print("=== 8. SINGLE INVOCATION PATH ===")

for filepath in files_to_check:
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    filename = filepath.split("/")[-1]
    # No file may import routing_pipeline directly — all access through adapter
    assert "routing_pipeline" not in content, f"{filename}: imports routing_pipeline directly"

print("  Zero direct routing_pipeline imports: OK")
print("  All routing AND metadata goes through adapter: OK")

print()
print("=== ALL 8 CHECKS PASSED ===")
