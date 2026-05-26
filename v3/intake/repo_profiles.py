"""
Repo Intake Profiles — Pre-built profiles for 14 known repositories.

Each profile contains:
  - name, url, category_hint, intended_use, known_risks, expected_decision
  - A synthetic file snapshot for signal extraction

Zero network required. Profiles are static data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from v3.intake.repo_intake import (
    DECISION_ARCHITECTURE_REFERENCE,
    DECISION_DIRECT_CLONE,
    DECISION_EXTERNAL_EXTENSION,
    DECISION_REJECT,
    INTENDED_USE_ARCHITECTURE,
    INTENDED_USE_CLAUDE_CODE,
    INTENDED_USE_SYSTEMKERNEL,
    INTENDED_USE_UNKNOWN,
    RepoIntakeInput,
    RepoSignals,
    analyze_repo_snapshot,
)


@dataclass(frozen=True)
class RepoProfile:
    """Pre-built profile for a known repository.

    Fields:
        name: Repository name
        url: GitHub URL
        category_hint: Category for type classification
        intended_use: How the developer intends to use this repo
        known_risks: List of known risk factors
        expected_decision: Expected intake decision
        files: Synthetic file snapshot dict (filename → content)
        known_dependencies: Pre-classified dependencies
    """

    name: str
    url: str
    category_hint: str = ""
    intended_use: str = INTENDED_USE_UNKNOWN
    known_risks: Tuple[str, ...] = ()
    expected_decision: str = DECISION_REJECT
    files: dict = field(default_factory=dict)
    known_dependencies: Tuple[str, ...] = ()

    def to_input(self) -> RepoIntakeInput:
        return RepoIntakeInput(
            name=self.name,
            url=self.url,
            category_hint=self.category_hint,
            intended_use=self.intended_use,
        )

    def analyze(self) -> RepoSignals:
        return analyze_repo_snapshot(
            name=self.name,
            url=self.url,
            files=self.files,
            known_dependencies=list(self.known_dependencies),
        )


# ═══════════════════════════════════════════════════════════════════════
# 14 Pre-built Profiles
# ═══════════════════════════════════════════════════════════════════════

PROFILES: Tuple[RepoProfile, ...] = (

    # 1. LangGraph — Agent framework by LangChain
    RepoProfile(
        name="LangGraph",
        url="https://github.com/langchain-ai/langgraph",
        category_hint="agent_runtime",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Heavy langchain dependency",
            "Agent execution model conflicts with SystemKernel",
            "LLM-driven control flow",
        ),
        expected_decision=DECISION_ARCHITECTURE_REFERENCE,
        files={
            "README.md": "# LangGraph\nBuild stateful, multi-actor agents with LLMs.",
            "LICENSE": "MIT License",
            "pyproject.toml": "[project]\nname = \"langgraph\"\ndependencies = [\"langchain-core\"]",
            "src/langgraph/__init__.py": "",
            "tests/test_graph.py": "",
            "docs/index.md": "# LangGraph Docs",
            "examples/agent.py": "",
        },
        known_dependencies=("langchain-core",),
    ),

    # 2. CrewAI — Multi-agent orchestration
    RepoProfile(
        name="CrewAI",
        url="https://github.com/crewAIInc/crewAI",
        category_hint="agent_runtime",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Multi-agent framework",
            "LLM dependency (openai/anthropic)",
            "Competing execution model",
        ),
        expected_decision=DECISION_ARCHITECTURE_REFERENCE,
        files={
            "README.md": "# CrewAI\nMulti-agent orchestration framework.",
            "LICENSE": "MIT License",
            "pyproject.toml": "[project]\nname = \"crewai\"\ndependencies = [\"openai\", \"langchain\"]",
            "src/crewai/__init__.py": "",
            "tests/test_crew.py": "",
            "docs/intro.md": "# CrewAI Docs",
        },
        known_dependencies=("openai", "langchain"),
    ),

    # 3. OpenAI Swarm — Lightweight agent swarm
    RepoProfile(
        name="OpenAI Swarm",
        url="https://github.com/openai/swarm",
        category_hint="agent_runtime",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "OpenAI API dependency",
            "Experimental agent framework",
        ),
        expected_decision=DECISION_EXTERNAL_EXTENSION,
        files={
            "README.md": "# Swarm\nExperimental framework for multi-agent orchestration.",
            "LICENSE": "MIT License",
            "pyproject.toml": "[project]\nname = \"swarm\"\ndependencies = [\"openai\"]",
            "src/swarm/__init__.py": "",
            "tests/test_swarm.py": "",
        },
        known_dependencies=("openai",),
    ),

    # 4. Anthropic Skills — Skill definitions for Claude Code
    RepoProfile(
        name="Anthropic Skills",
        url="https://github.com/anthropics/skills",
        category_hint="skill_system",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# Anthropic Skills\nSkill definitions for Claude Code.",
            "LICENSE": "MIT License",
            "skills/manifest.json": '{"skills": []}',
            "skills/example/SKILL.md": "# Example Skill",
            "tests/test_skills.py": "",
            "docs/README.md": "# Skills Docs",
        },
        known_dependencies=(),
    ),

    # 5. mem0 — Memory layer for AI
    RepoProfile(
        name="mem0",
        url="https://github.com/mem0ai/mem0",
        category_hint="memory_system",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Vector database dependency",
            "LLM embedding dependency",
            "Memory system conflicts with SK",
        ),
        expected_decision=DECISION_EXTERNAL_EXTENSION,
        files={
            "README.md": "# mem0\nMemory layer for AI applications.",
            "LICENSE": "Apache 2.0",
            "pyproject.toml": "[project]\nname = \"mem0\"\ndependencies = [\"qdrant-client\", \"chromadb\"]",
            "src/mem0/__init__.py": "",
            "tests/test_memory.py": "",
        },
        known_dependencies=("qdrant-client", "chromadb"),
    ),

    # 6. Graphiti — Knowledge graph memory
    RepoProfile(
        name="Graphiti",
        url="https://github.com/getzep/graphiti",
        category_hint="memory_system",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Neo4j/graph database dependency",
            "LLM-based entity extraction",
            "Memory system conflicts with SK",
        ),
        expected_decision=DECISION_EXTERNAL_EXTENSION,
        files={
            "README.md": "# Graphiti\nKnowledge graph-based memory for AI.",
            "LICENSE": "Apache 2.0",
            "pyproject.toml": "[project]\nname = \"graphiti\"\ndependencies = [\"neo4j\", \"openai\"]",
            "src/graphiti/__init__.py": "",
            "tests/test_graph.py": "",
        },
        known_dependencies=("neo4j", "openai"),
    ),

    # 7. Repomix — Repository context packer
    RepoProfile(
        name="Repomix",
        url="https://github.com/yamadashy/repomix",
        category_hint="context_tool",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# Repomix\nPack repository contents for AI context.",
            "LICENSE": "MIT License",
            "package.json": '{"name": "repomix", "dependencies": {"commander": "^11.0"}}',
            "src/cli.ts": "",
            "tests/cli.test.ts": "",
            "docs/README.md": "# Repomix Docs",
        },
        known_dependencies=(),
    ),

    # 8. ccusage — Claude Code usage tracker
    RepoProfile(
        name="ccusage",
        url="https://github.com/anthropics/ccusage",
        category_hint="claude_code_extension",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# ccusage\nTrack Claude Code usage and costs.",
            "LICENSE": "MIT License",
            "pyproject.toml": "[project]\nname = \"ccusage\"\ndependencies = []",
            "src/ccusage/cli.py": "",
            "tests/test_cli.py": "",
        },
        known_dependencies=(),
    ),

    # 9. Continue — IDE extension for AI
    RepoProfile(
        name="Continue",
        url="https://github.com/continuedev/continue",
        category_hint="claude_code_extension",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(
            "IDE-specific integration",
            "LLM API dependencies",
        ),
        expected_decision=DECISION_EXTERNAL_EXTENSION,
        files={
            "README.md": "# Continue\nAI code assistant for IDEs.",
            "LICENSE": "Apache 2.0",
            "package.json": '{"name": "continue", "dependencies": {"openai": "^4.0"}}',
            "src/extension.ts": "",
            "tests/extension.test.ts": "",
        },
        known_dependencies=("openai",),
    ),

    # 10. AppFlowy — Notion alternative
    RepoProfile(
        name="AppFlowy",
        url="https://github.com/AppFlowy-IO/appflowy",
        category_hint="application",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Large Flutter/Rust codebase",
            "Heavy dependency footprint",
        ),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# AppFlowy\nOpen-source Notion alternative.",
            "LICENSE": "AGPL 3.0",
            "Cargo.toml": "[package]\nname = \"appflowy\"",
            "src/main.rs": "",
            "tests/integration.rs": "",
        },
        known_dependencies=(),
    ),

    # 11. JupyterLab — Notebook interface
    RepoProfile(
        name="JupyterLab",
        url="https://github.com/jupyterlab/jupyterlab",
        category_hint="application",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Very large codebase",
            "Heavy extension system",
        ),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# JupyterLab\nWeb-based interactive development environment.",
            "LICENSE": "BSD 3-Clause",
            "pyproject.toml": "[project]\nname = \"jupyterlab\"",
            "package.json": '{"name": "@jupyterlab/application"}',
            "src/__init__.py": "",
            "tests/test_app.py": "",
            "docs/index.rst": "JupyterLab Docs",
            "examples/notebook.ipynb": "",
        },
        known_dependencies=(),
    ),

    # 12. SuperClaude — Claude Code enhancements
    RepoProfile(
        name="SuperClaude",
        url="https://github.com/anthropics/SuperClaude",
        category_hint="claude_code_extension",
        intended_use=INTENDED_USE_CLAUDE_CODE,
        known_risks=(),
        expected_decision=DECISION_DIRECT_CLONE,
        files={
            "README.md": "# SuperClaude\nEnhancements and utilities for Claude Code.",
            "LICENSE": "MIT License",
            "skills/manifest.json": '{"skills": []}',
            "skills/code-review/SKILL.md": "# Code Review Skill",
            "tests/test_skills.py": "",
        },
        known_dependencies=(),
    ),

    # 13. awesome-claude-code — Curated list
    RepoProfile(
        name="awesome-claude-code",
        url="https://github.com/anthropics/awesome-claude-code",
        category_hint="docs_only",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Documentation only, no runnable code",
        ),
        expected_decision=DECISION_ARCHITECTURE_REFERENCE,
        files={
            "README.md": "# Awesome Claude Code\nCurated list of Claude Code resources.",
        },
        known_dependencies=(),
    ),

    # 14. Awesome-Prompt-Engineering — Curated list
    RepoProfile(
        name="Awesome-Prompt-Engineering",
        url="https://github.com/promptslab/Awesome-Prompt-Engineering",
        category_hint="docs_only",
        intended_use=INTENDED_USE_ARCHITECTURE,
        known_risks=(
            "Documentation only, no runnable code",
        ),
        expected_decision=DECISION_ARCHITECTURE_REFERENCE,
        files={
            "README.md": "# Awesome Prompt Engineering\nCurated prompt engineering resources.",
        },
        known_dependencies=(),
    ),
)


# ═══════════════════════════════════════════════════════════════════════
# Profile lookup
# ═══════════════════════════════════════════════════════════════════════

def get_profile(name: str) -> RepoProfile | None:
    """Look up a profile by name (case-insensitive)."""
    name_lower = name.lower()
    for p in PROFILES:
        if p.name.lower() == name_lower:
            return p
    return None


def list_profiles() -> list:
    """List all profile names and URLs."""
    return [{"name": p.name, "url": p.url} for p in PROFILES]


def get_all_profiles() -> Tuple[RepoProfile, ...]:
    """Return all profiles."""
    return PROFILES
