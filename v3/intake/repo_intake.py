"""
Repo Intake Pipeline — Deterministic repository assessment.

Evaluates whether an external repo should be:
  - DIRECT_CLONE — cloned into F:/Claude/Github for active use
  - EXTERNAL_EXTENSION — used as external service/extension
  - ARCHITECTURE_REFERENCE — studied for design patterns only
  - REJECT — not suitable for any integration

Zero network. Zero git clone. Analyzes metadata, signals, and synthetic snapshots.
All scoring is deterministic. Reports carry stable hashes.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Decision constants
# ═══════════════════════════════════════════════════════════════════════

DECISION_DIRECT_CLONE = "DIRECT_CLONE"
DECISION_EXTERNAL_EXTENSION = "EXTERNAL_EXTENSION"
DECISION_ARCHITECTURE_REFERENCE = "ARCHITECTURE_REFERENCE"
DECISION_REJECT = "REJECT"

DECISIONS = (DECISION_DIRECT_CLONE, DECISION_EXTERNAL_EXTENSION,
             DECISION_ARCHITECTURE_REFERENCE, DECISION_REJECT)

PRIORITY_S = "S"
PRIORITY_A = "A"
PRIORITY_B = "B"
PRIORITY_C = "C"
PRIORITY_D = "D"

PRIORITIES = (PRIORITY_S, PRIORITY_A, PRIORITY_B, PRIORITY_C, PRIORITY_D)

INTENDED_USE_CLAUDE_CODE = "claude_code_enhancement"
INTENDED_USE_SYSTEMKERNEL = "systemkernel_extension"
INTENDED_USE_ARCHITECTURE = "architecture_reference"
INTENDED_USE_UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════
# RepoIntakeInput
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RepoIntakeInput:
    """Input for repo intake assessment.

    Fields:
        name: Repository name (e.g. "LangGraph")
        url: GitHub URL or identifier
        local_path: Optional local filesystem path if already cloned
        category_hint: Optional category hint for classification
        intended_use: How the developer intends to use this repo
    """

    name: str = ""
    url: str = ""
    local_path: str = ""
    category_hint: str = ""
    intended_use: str = INTENDED_USE_UNKNOWN

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "local_path": self.local_path,
            "category_hint": self.category_hint,
            "intended_use": self.intended_use,
        }


# ═══════════════════════════════════════════════════════════════════════
# RepoSignals
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RepoSignals:
    """Detected signals from repo metadata / snapshot analysis.

    Fields:
        has_readme: README.md or similar found
        has_license: LICENSE file found
        language_hints: Detected languages (e.g. ["python", "typescript"])
        dependency_files: Found dependency manifests (requirements.txt, package.json, etc.)
        has_cli: CLI entry point detected
        has_mcp: MCP (Model Context Protocol) integration detected
        has_plugin_manifest: Plugin/system manifest found
        has_skill_manifest: Skill definition found
        has_tests: Test directory or test files found
        has_docs: Documentation directory found
        has_examples: Examples directory found
        banned_dependency_hits: Count of banned kernel dependencies
        heavy_dependency_hits: Count of heavy framework dependencies
        llm_dependency_hits: Count of LLM SDK dependencies
        memory_dependency_hits: Count of memory/vector DB dependencies
        framework_dependency_hits: Count of agent framework dependencies
        kernel_risk_flags: List of kernel integrity risk indicators
    """

    has_readme: bool = False
    has_license: bool = False
    language_hints: Tuple[str, ...] = ()
    dependency_files: Tuple[str, ...] = ()
    has_cli: bool = False
    has_mcp: bool = False
    has_plugin_manifest: bool = False
    has_skill_manifest: bool = False
    has_tests: bool = False
    has_docs: bool = False
    has_examples: bool = False
    banned_dependency_hits: int = 0
    heavy_dependency_hits: int = 0
    llm_dependency_hits: int = 0
    memory_dependency_hits: int = 0
    framework_dependency_hits: int = 0
    kernel_risk_flags: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "has_readme": self.has_readme,
            "has_license": self.has_license,
            "language_hints": list(self.language_hints),
            "dependency_files": list(self.dependency_files),
            "has_cli": self.has_cli,
            "has_mcp": self.has_mcp,
            "has_plugin_manifest": self.has_plugin_manifest,
            "has_skill_manifest": self.has_skill_manifest,
            "has_tests": self.has_tests,
            "has_docs": self.has_docs,
            "has_examples": self.has_examples,
            "banned_dependency_hits": self.banned_dependency_hits,
            "heavy_dependency_hits": self.heavy_dependency_hits,
            "llm_dependency_hits": self.llm_dependency_hits,
            "memory_dependency_hits": self.memory_dependency_hits,
            "framework_dependency_hits": self.framework_dependency_hits,
            "kernel_risk_flags": list(self.kernel_risk_flags),
        }


# ═══════════════════════════════════════════════════════════════════════
# RepoIntakeDecision
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RepoIntakeDecision:
    """Decision output of repo intake assessment.

    Fields:
        decision: DIRECT_CLONE | EXTERNAL_EXTENSION | ARCHITECTURE_REFERENCE | REJECT
        priority: S | A | B | C | D
        claude_code_value_score: Value for Claude Code enhancement (0-10)
        systemkernel_value_score: Value for SystemKernel extension (0-10)
        complexity_risk_score: Risk of adding complexity (0-10, lower is better)
        purity_risk_score: Risk to kernel purity (0-10, lower is better)
        maintenance_risk_score: Maintenance burden risk (0-10, lower is better)
        final_score: Composite score (higher = better candidate)
        reasons: Human-readable reasons for the decision
        recommended_target_dir: Where to place the repo if cloned
        allowed_actions: What the developer may do with this repo
        forbidden_actions: What the developer must NOT do with this repo
    """

    decision: str = DECISION_REJECT
    priority: str = PRIORITY_D
    claude_code_value_score: float = 0.0
    systemkernel_value_score: float = 0.0
    complexity_risk_score: float = 10.0
    purity_risk_score: float = 10.0
    maintenance_risk_score: float = 10.0
    final_score: float = 0.0
    reasons: Tuple[str, ...] = ()
    recommended_target_dir: str = ""
    allowed_actions: Tuple[str, ...] = ()
    forbidden_actions: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "priority": self.priority,
            "claude_code_value_score": self.claude_code_value_score,
            "systemkernel_value_score": self.systemkernel_value_score,
            "complexity_risk_score": self.complexity_risk_score,
            "purity_risk_score": self.purity_risk_score,
            "maintenance_risk_score": self.maintenance_risk_score,
            "final_score": round(self.final_score, 2),
            "reasons": list(self.reasons),
            "recommended_target_dir": self.recommended_target_dir,
            "allowed_actions": list(self.allowed_actions),
            "forbidden_actions": list(self.forbidden_actions),
        }

    @property
    def is_direct_clone(self) -> bool:
        return self.decision == DECISION_DIRECT_CLONE

    @property
    def is_external(self) -> bool:
        return self.decision == DECISION_EXTERNAL_EXTENSION

    @property
    def is_reference(self) -> bool:
        return self.decision == DECISION_ARCHITECTURE_REFERENCE

    @property
    def is_rejected(self) -> bool:
        return self.decision == DECISION_REJECT


# ═══════════════════════════════════════════════════════════════════════
# RepoIntakeReport
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RepoIntakeReport:
    """Full intake report combining input, signals, and decision.

    Fields:
        input: Original RepoIntakeInput
        signals: Detected RepoSignals
        decision: Computed RepoIntakeDecision
        report_hash: Deterministic hash of the entire report
    """

    input: RepoIntakeInput = field(default_factory=RepoIntakeInput)
    signals: RepoSignals = field(default_factory=RepoSignals)
    decision: RepoIntakeDecision = field(default_factory=RepoIntakeDecision)
    report_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "input": self.input.to_dict(),
            "signals": self.signals.to_dict(),
            "decision": self.decision.to_dict(),
            "report_hash": self.report_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Analysis: local repo
# ═══════════════════════════════════════════════════════════════════════

def analyze_local_repo(path: str) -> RepoSignals:
    """Analyze a locally-cloned repository and extract signals.

    Does NOT execute any code. Only inspects file structure.
    Deterministic for the same filesystem state.
    """
    if not os.path.isdir(path):
        return RepoSignals()

    files = set()
    for root_dir, dirs, filenames in os.walk(path):
        # Skip hidden dirs and common ignores
        dirs[:] = [d for d in dirs if not d.startswith(".")
                    and d not in ("node_modules", "__pycache__", ".git",
                                  "venv", ".venv", "dist", "build")]
        for fn in filenames:
            files.add(fn.lower())

    has_readme = any(f.startswith("readme") for f in files)
    has_license = any("license" in f for f in files)

    # Language hints
    lang_hints = []
    if any(f.endswith(".py") for f in files):
        lang_hints.append("python")
    if any(f.endswith((".ts", ".tsx")) for f in files):
        lang_hints.append("typescript")
    if any(f.endswith((".js", ".jsx")) for f in files):
        lang_hints.append("javascript")
    if any(f.endswith(".rs") for f in files):
        lang_hints.append("rust")
    if any(f.endswith(".go") for f in files):
        lang_hints.append("go")

    # Dependency files
    dep_files = []
    dep_patterns = [
        "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
        "package.json", "cargo.toml", "go.mod", "pom.xml", "build.gradle",
        "gemfile", "composer.json",
    ]
    for dp in dep_patterns:
        if dp in files:
            dep_files.append(dp)

    # Structural signals
    has_cli = "cli" in set(os.path.basename(root_dir).lower()
                           for root_dir, _, _ in os.walk(path)
                           if root_dir != path) or any("cli" in f for f in files)
    has_mcp = any("mcp" in f for f in files)
    has_plugin = any("manifest" in f for f in files)
    has_skill = any("skill" in f for f in files)

    has_tests = any(d == "tests" or d == "test"
                    for root_dir, dirs, _ in os.walk(path)
                    for d in dirs)
    has_docs = any(d in ("docs", "doc", "documentation")
                   for root_dir, dirs, _ in os.walk(path)
                   for d in dirs)
    has_examples = any(d in ("examples", "example", "demo")
                       for root_dir, dirs, _ in os.walk(path)
                       for d in dirs)

    return RepoSignals(
        has_readme=has_readme,
        has_license=has_license,
        language_hints=tuple(sorted(set(lang_hints))),
        dependency_files=tuple(sorted(set(dep_files))),
        has_cli=has_cli,
        has_mcp=has_mcp,
        has_plugin_manifest=has_plugin,
        has_skill_manifest=has_skill,
        has_tests=has_tests,
        has_docs=has_docs,
        has_examples=has_examples,
    )


# ═══════════════════════════════════════════════════════════════════════
# Analysis: snapshot (synthetic files dict)
# ═══════════════════════════════════════════════════════════════════════

def analyze_repo_snapshot(
    name: str,
    url: str,
    files: dict,
    *,
    known_dependencies: Optional[list] = None,
) -> RepoSignals:
    """Analyze a synthetic repo snapshot from a dict of filename→content.

    Useful for testing and for pre-built profiles without network access.

    Args:
        name: Repo name
        url: Repo URL
        files: Dict mapping relative paths (e.g. "README.md") to file content
        known_dependencies: Optional list of known dependency names

    Returns:
        RepoSignals with all detectable signals.
    """
    file_names = set(f.lower() for f in files.keys())
    dir_names = set()
    for f in files.keys():
        parts = f.lower().replace("\\", "/").split("/")
        for i in range(len(parts) - 1):
            dir_names.add(parts[i])

    # Basic signals
    has_readme = any(f.startswith("readme") for f in file_names)
    has_license = any("license" in f for f in file_names)

    # Language hints from file extensions
    lang_hints = []
    ext_map = {
        ".py": "python", ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
        ".rs": "rust", ".go": "go", ".java": "java",
        ".rb": "ruby", ".php": "php",
    }
    for fn in file_names:
        for ext, lang in ext_map.items():
            if fn.endswith(ext):
                lang_hints.append(lang)
                break

    # Dependency files
    dep_files = []
    dep_patterns = [
        "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
        "package.json", "cargo.toml", "go.mod",
    ]
    for dp in dep_patterns:
        if dp in file_names:
            dep_files.append(dp)

    # Structural signals from directory names
    has_cli = "cli" in dir_names or any("cli" in f for f in file_names)
    has_mcp = "mcp" in dir_names or any("mcp" in f for f in file_names)
    has_plugin = any("manifest" in f for f in file_names)
    has_skill = any("skill" in f for f in file_names)
    has_tests = "tests" in dir_names or "test" in dir_names
    has_docs = "docs" in dir_names or "doc" in dir_names
    has_examples = "examples" in dir_names or "example" in dir_names or "demo" in dir_names

    # Dependency analysis from content
    deps = set(known_dependencies or [])
    # Scan dependency files for well-known packages
    for fn in file_names:
        if fn in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"):
            content = files.get(fn, files.get(list(files.keys())[0], ""))
            deps.update(_extract_python_deps(content))
        elif fn == "package.json":
            content = files.get(fn, "")
            deps.update(_extract_node_deps(content))

    # Classify dependencies
    banned = _classify_dependencies(deps)

    return RepoSignals(
        has_readme=has_readme,
        has_license=has_license,
        language_hints=tuple(sorted(set(lang_hints))),
        dependency_files=tuple(sorted(set(dep_files))),
        has_cli=has_cli,
        has_mcp=has_mcp,
        has_plugin_manifest=has_plugin,
        has_skill_manifest=has_skill,
        has_tests=has_tests,
        has_docs=has_docs,
        has_examples=has_examples,
        banned_dependency_hits=banned["banned"],
        heavy_dependency_hits=banned["heavy"],
        llm_dependency_hits=banned["llm"],
        memory_dependency_hits=banned["memory"],
        framework_dependency_hits=banned["framework"],
        kernel_risk_flags=tuple(banned["flags"]),
    )


def _extract_python_deps(content: str) -> list:
    """Extract python dependency names from requirements.txt / pyproject.toml content."""
    deps = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        # requirements.txt: package==version or package>=version
        pkg = line.split("==")[0].split(">=")[0].split("<")[0].split("~=")[0].strip()
        if pkg and not pkg.startswith("-"):
            deps.append(pkg.lower())
    return deps


def _extract_node_deps(content: str) -> list:
    """Extract node dependency names from package.json content."""
    deps = []
    try:
        data = json.loads(content)
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for pkg in data.get(section, {}):
                deps.append(pkg.lower())
    except (json.JSONDecodeError, TypeError):
        pass
    return deps


def _classify_dependencies(deps: set) -> dict:
    """Classify dependencies into risk categories.

    Returns:
        dict with counts for banned, heavy, llm, memory, framework, and flags.
    """
    banned_kernel = {
        "openai", "anthropic", "langchain", "langchain-core", "langchain-community",
        "llamaindex", "chromadb", "qdrant", "qdrant-client",
        "pinecone", "pinecone-client", "weaviate", "weaviate-client", "milvus",
        "mem0", "graphiti", "sentence_transformers", "transformers",
        "torch", "tensorflow", "scipy", "sklearn",
    }
    heavy = {
        "torch", "tensorflow", "jax", "pyspark", "ray",
        "kubernetes", "docker", "grpcio", "neo4j",
    }
    llm = {
        "openai", "anthropic", "langchain", "langchain-core", "langchain-community",
        "llamaindex", "crewai", "autogen", "semantic-kernel",
        "transformers", "sentence_transformers",
    }
    memory = {
        "chromadb", "qdrant", "qdrant-client", "pinecone", "pinecone-client",
        "weaviate", "weaviate-client", "milvus",
        "mem0", "graphiti", "pgvector", "elasticsearch",
        "redis", "lancedb",
    }
    framework = {
        "langchain", "langchain-core", "langchain-community",
        "crewai", "autogen", "semantic-kernel",
        "dspy", "haystack", "langflow",
    }

    flags = []
    banned_count = 0
    heavy_count = 0
    llm_count = 0
    memory_count = 0
    framework_count = 0

    for dep in deps:
        dep_lower = dep.lower()
        if dep_lower in banned_kernel:
            banned_count += 1
            flags.append(f"BANNED_DEP:{dep_lower}")
        if dep_lower in heavy:
            heavy_count += 1
            flags.append(f"HEAVY_DEP:{dep_lower}")
        if dep_lower in llm:
            llm_count += 1
            flags.append(f"LLM_DEP:{dep_lower}")
        if dep_lower in memory:
            memory_count += 1
            flags.append(f"MEMORY_DEP:{dep_lower}")
        if dep_lower in framework:
            framework_count += 1
            flags.append(f"FRAMEWORK_DEP:{dep_lower}")

    return {
        "banned": banned_count,
        "heavy": heavy_count,
        "llm": llm_count,
        "memory": memory_count,
        "framework": framework_count,
        "flags": tuple(sorted(set(flags))),
    }


# ═══════════════════════════════════════════════════════════════════════
# Scoring Engine
# ═══════════════════════════════════════════════════════════════════════

def decide_repo_intake(
    inp: RepoIntakeInput,
    signals: RepoSignals,
) -> RepoIntakeDecision:
    """Compute intake decision from input and signals.

    Scoring model (deterministic):

    Claude Code value (0-10):
      +2  has_readme
      +2  has_cli
      +2  has_mcp
      +1  has_skill_manifest
      +1  has_examples
      +1  has_tests
      +1  has_docs
      -2  banned_dependency_hits
      -1  heavy_dependency_hits

    SystemKernel value (0-10):
      +2  has_plugin_manifest
      +2  has_tests
      +2  has_license
      +1  has_readme
      +1  has_docs
      +1  has_examples
      -2  llm_dependency_hits
      -2  framework_dependency_hits
      -1  memory_dependency_hits

    Risk scores (0-10, 10 = highest risk, 0 = no risk):
      complexity_risk = heavy_deps*2 + framework_deps*1.5 + (not has_readme)*2
      purity_risk = banned_deps*3 + llm_deps*2 + framework_deps*1
      maintenance_risk = (not has_license)*3 + heavy_deps*1.5 + (not has_tests)*2

    Decision logic:
      - REJECT: banned_deps > 0 AND no license AND no readme
      - ARCHITECTURE_REFERENCE: framework_deps >= 2 OR llm_deps >= 2
      - EXTERNAL_EXTENSION: memory_deps > 0 OR heavy_deps > 0
      - DIRECT_CLONE: low risk + high value + has_readme + has_license
    """
    reasons = []

    # ── Value scores ──
    cc_value = 5.0
    if signals.has_readme:    cc_value += 2.0
    if signals.has_cli:       cc_value += 2.0
    if signals.has_mcp:       cc_value += 2.0
    if signals.has_skill_manifest: cc_value += 1.0
    if signals.has_examples:  cc_value += 1.0
    if signals.has_tests:     cc_value += 1.0
    if signals.has_docs:      cc_value += 1.0
    cc_value -= signals.banned_dependency_hits * 2.0
    cc_value -= signals.heavy_dependency_hits * 1.0
    cc_value = max(0.0, min(10.0, cc_value))

    sk_value = 5.0
    if signals.has_plugin_manifest: sk_value += 2.0
    if signals.has_tests:     sk_value += 2.0
    if signals.has_license:   sk_value += 2.0
    if signals.has_readme:    sk_value += 1.0
    if signals.has_docs:      sk_value += 1.0
    if signals.has_examples:  sk_value += 1.0
    sk_value -= signals.llm_dependency_hits * 2.0
    sk_value -= signals.framework_dependency_hits * 2.0
    sk_value -= signals.memory_dependency_hits * 1.0
    sk_value = max(0.0, min(10.0, sk_value))

    # ── Risk scores (0=best, 10=worst) ──
    complexity_risk = 0.0
    complexity_risk += signals.heavy_dependency_hits * 2.0
    complexity_risk += signals.framework_dependency_hits * 1.5
    if not signals.has_readme:
        complexity_risk += 2.0
    if signals.banned_dependency_hits > 0:
        complexity_risk += 1.0
    complexity_risk = min(10.0, complexity_risk)

    purity_risk = 0.0
    purity_risk += signals.banned_dependency_hits * 3.0
    purity_risk += signals.llm_dependency_hits * 2.0
    purity_risk += signals.framework_dependency_hits * 1.0
    purity_risk = min(10.0, purity_risk)

    maintenance_risk = 0.0
    if not signals.has_license:
        maintenance_risk += 3.0
    maintenance_risk += signals.heavy_dependency_hits * 1.5
    if not signals.has_tests:
        maintenance_risk += 2.0
    if not signals.has_readme:
        maintenance_risk += 1.0
    maintenance_risk = min(10.0, maintenance_risk)

    # ── Decision logic ──
    decision = DECISION_REJECT

    # Auto-reject: banned deps + no license + no readme = too risky
    if signals.banned_dependency_hits >= 2 and not signals.has_license and not signals.has_readme:
        decision = DECISION_REJECT
        reasons.append("HIGH_RISK: multiple banned deps, no license, no readme")

    # Auto-reject: no readme AND no files at all
    if not signals.has_readme and not signals.language_hints and not signals.dependency_files:
        decision = DECISION_REJECT
        reasons.append("NO_CONTENT: no readme, no code signals, no dependency files")

    if decision == DECISION_REJECT and not reasons:
        # Not auto-rejected — evaluate based on dependency signals
        if signals.framework_dependency_hits >= 1:
            decision = DECISION_ARCHITECTURE_REFERENCE
            reasons.append("ARCHITECTURE_REFERENCE: agent framework dependencies detected")
        elif signals.llm_dependency_hits >= 1:
            decision = DECISION_EXTERNAL_EXTENSION
            reasons.append("EXTERNAL_EXTENSION: LLM SDK dependencies detected")
        elif signals.memory_dependency_hits > 0 or signals.heavy_dependency_hits > 0:
            decision = DECISION_EXTERNAL_EXTENSION
            reasons.append("EXTERNAL_EXTENSION: memory/heavy deps require external deployment")
        elif signals.banned_dependency_hits > 0:
            decision = DECISION_ARCHITECTURE_REFERENCE
            reasons.append("ARCHITECTURE_REFERENCE: banned kernel dependencies detected")
        elif (cc_value >= 7.0 or sk_value >= 7.0) and signals.has_readme and signals.has_license:
            decision = DECISION_DIRECT_CLONE
            reasons.append("DIRECT_CLONE: high value, well-documented, low risk")
        elif signals.has_readme and signals.has_license:
            decision = DECISION_EXTERNAL_EXTENSION
            reasons.append("EXTERNAL_EXTENSION: documented but moderate value")
        else:
            decision = DECISION_ARCHITECTURE_REFERENCE
            reasons.append("ARCHITECTURE_REFERENCE: insufficient documentation or value signals")

    # ── Priority ──
    if decision == DECISION_DIRECT_CLONE:
        if cc_value >= 8.0 and sk_value >= 6.0:
            priority = PRIORITY_S
        elif cc_value >= 7.0:
            priority = PRIORITY_A
        else:
            priority = PRIORITY_B
    elif decision == DECISION_EXTERNAL_EXTENSION:
        priority = PRIORITY_B if cc_value >= 5.0 else PRIORITY_C
    elif decision == DECISION_ARCHITECTURE_REFERENCE:
        priority = PRIORITY_C if signals.has_readme else PRIORITY_D
    else:
        priority = PRIORITY_D

    # ── Final score ──
    final_score = (cc_value + sk_value) / 2.0 - (complexity_risk + purity_risk) / 4.0
    final_score = max(0.0, round(final_score, 2))

    # ── Target dir ──
    if decision == DECISION_DIRECT_CLONE:
        target = f"F:/Claude/Github/{inp.name.lower().replace(' ', '-')}"
    elif decision == DECISION_EXTERNAL_EXTENSION:
        target = f"F:/Claude/Github/_extensions/{inp.name.lower().replace(' ', '-')}"
    elif decision == DECISION_ARCHITECTURE_REFERENCE:
        target = f"F:/Claude/Reference/{inp.name.lower().replace(' ', '-')}"
    else:
        target = ""

    # ── Allowed / forbidden actions ──
    allowed = []
    forbidden = []

    if decision == DECISION_DIRECT_CLONE:
        allowed = ("clone_to_github", "import_as_extension", "run_locally", "study_architecture")
        forbidden = ("modify_kernel_for_integration", "embed_as_kernel_module")
    elif decision == DECISION_EXTERNAL_EXTENSION:
        allowed = ("clone_to_github_extensions", "run_as_external_service", "import_via_api", "study_architecture")
        forbidden = ("directly_import_into_kernel", "embed_as_kernel_module", "modify_kernel_boundary")
    elif decision == DECISION_ARCHITECTURE_REFERENCE:
        allowed = ("study_architecture", "extract_design_patterns", "document_findings")
        forbidden = ("clone_to_github", "import_into_project", "run_as_dependency", "embed_as_kernel_module")
    else:
        allowed = ("document_rejection_reason",)
        forbidden = ("clone", "import", "integrate", "reference_as_architecture")

    return RepoIntakeDecision(
        decision=decision,
        priority=priority,
        claude_code_value_score=round(cc_value, 1),
        systemkernel_value_score=round(sk_value, 1),
        complexity_risk_score=round(complexity_risk, 1),
        purity_risk_score=round(purity_risk, 1),
        maintenance_risk_score=round(maintenance_risk, 1),
        final_score=final_score,
        reasons=tuple(reasons),
        recommended_target_dir=target,
        allowed_actions=tuple(allowed),
        forbidden_actions=tuple(forbidden),
    )


# ═══════════════════════════════════════════════════════════════════════
# Report I/O
# ═══════════════════════════════════════════════════════════════════════

def write_report(report: RepoIntakeReport, path: str) -> str:
    """Write an intake report to a JSON file. Returns absolute path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2, sort_keys=True)
    return os.path.abspath(path)


def compute_report_hash(inp: RepoIntakeInput, signals: RepoSignals,
                        decision: RepoIntakeDecision) -> str:
    """Deterministic hash of an intake report."""
    parts = [
        json.dumps(inp.to_dict(), sort_keys=True, ensure_ascii=False),
        json.dumps(signals.to_dict(), sort_keys=True, ensure_ascii=False),
        decision.decision,
        decision.priority,
        str(decision.final_score),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
