"""
Repo Intake Rules — Interpretable classifier rules.

Each rule is a self-contained condition→decision mapping that can be
read and understood independently. Rules are applied in priority order.
The first matching rule wins.

All rules are deterministic — same inputs always produce same outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

from v3.intake.repo_intake import (
    DECISION_ARCHITECTURE_REFERENCE,
    DECISION_DIRECT_CLONE,
    DECISION_EXTERNAL_EXTENSION,
    DECISION_REJECT,
    RepoIntakeDecision,
    RepoIntakeInput,
    RepoSignals,
)


# ═══════════════════════════════════════════════════════════════════════
# Repo type classification
# ═══════════════════════════════════════════════════════════════════════

REPO_TYPE_AGENT_RUNTIME = "agent_runtime"
REPO_TYPE_MEMORY_SYSTEM = "memory_system"
REPO_TYPE_OBSERVABILITY_TOOL = "observability_tool"
REPO_TYPE_CLAUDE_CODE_EXTENSION = "claude_code_extension"
REPO_TYPE_SKILL_SYSTEM = "skill_system"
REPO_TYPE_CONTEXT_TOOL = "context_tool"
REPO_TYPE_DOCS_ONLY = "docs_only"
REPO_TYPE_UNKNOWN = "unknown"

REPO_TYPES = (
    REPO_TYPE_AGENT_RUNTIME,
    REPO_TYPE_MEMORY_SYSTEM,
    REPO_TYPE_OBSERVABILITY_TOOL,
    REPO_TYPE_CLAUDE_CODE_EXTENSION,
    REPO_TYPE_SKILL_SYSTEM,
    REPO_TYPE_CONTEXT_TOOL,
    REPO_TYPE_DOCS_ONLY,
    REPO_TYPE_UNKNOWN,
)


def classify_repo_type(signals: RepoSignals, name: str = "") -> str:
    """Classify a repository into one of 8 types based on signals.

    Classification is deterministic and based on structural signals only.
    No LLM, no network, no semantic analysis.

    Priority order:
      1. agent_runtime — framework deps present
      2. memory_system — memory/vector DB deps present
      3. observability_tool — traces/metrics/logging signals
      4. claude_code_extension — MCP or Claude Code integration
      5. skill_system — skill manifests, plugin manifests
      6. context_tool — CLI tools that process context/files
      7. docs_only — documentation with no code signals
      8. unknown — none of the above
    """
    name_lower = name.lower()

    # 1. Agent runtime: has framework deps
    if signals.framework_dependency_hits > 0:
        return REPO_TYPE_AGENT_RUNTIME

    # 2. Memory system: has memory/vector DB deps
    if signals.memory_dependency_hits > 0:
        return REPO_TYPE_MEMORY_SYSTEM

    # 3. Observability tool: name hints
    obs_keywords = ("trace", "metric", "observe", "monitor", "log", "telemetry")
    if any(kw in name_lower for kw in obs_keywords):
        return REPO_TYPE_OBSERVABILITY_TOOL

    # 4. Claude Code extension: MCP or Claude Code integration
    if signals.has_mcp:
        return REPO_TYPE_CLAUDE_CODE_EXTENSION
    cc_keywords = ("claude", "mcp", "anthropic")
    if any(kw in name_lower for kw in cc_keywords) and not signals.framework_dependency_hits:
        return REPO_TYPE_CLAUDE_CODE_EXTENSION

    # 5. Skill system: skill or plugin manifests
    if signals.has_skill_manifest or signals.has_plugin_manifest:
        return REPO_TYPE_SKILL_SYSTEM

    # 6. Context tool: CLI tool with file processing hints
    if signals.has_cli and signals.language_hints:
        ctx_keywords = ("context", "repo", "pack", "bundle", "parse", "tree")
        if any(kw in name_lower for kw in ctx_keywords):
            return REPO_TYPE_CONTEXT_TOOL

    # 7. Docs only: has readme but no code signals
    if (signals.has_readme and not signals.language_hints
            and not signals.dependency_files and not signals.has_cli):
        return REPO_TYPE_DOCS_ONLY

    return REPO_TYPE_UNKNOWN


# ═══════════════════════════════════════════════════════════════════════
# Interpretable rules
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class IntakeRule:
    """A single interpretable intake rule.

    Fields:
        rule_id: Unique rule identifier
        priority: Application priority (lower = applied first)
        description: Human-readable description of what the rule does
        condition: Short condition description (e.g. "framework_deps >= 1")
        decision: The decision this rule produces
        rationale: Why this decision is made
    """

    rule_id: str
    priority: int
    description: str
    condition: str
    decision: str
    rationale: str


# Priority-ordered rules (lowest priority number = applied first)
INTAKE_RULES: Tuple[IntakeRule, ...] = (
    IntakeRule(
        rule_id="R01",
        priority=1,
        description="Pure CLI tool with documentation and low risk → direct clone",
        condition="has_cli AND has_readme AND has_license AND framework_deps=0 AND llm_deps=0 AND banned_deps=0 AND (cc_value>=7 OR sk_value>=7)",
        decision=DECISION_DIRECT_CLONE,
        rationale="Well-documented CLI tools with no risky dependencies are safe to clone and use directly.",
    ),
    IntakeRule(
        rule_id="R02",
        priority=2,
        description="Agent framework dependency → architecture reference only",
        condition="framework_deps >= 1",
        decision=DECISION_ARCHITECTURE_REFERENCE,
        rationale="Agent frameworks (LangGraph, CrewAI, etc.) embed their own execution models. Study their design but do not integrate into the kernel.",
    ),
    IntakeRule(
        rule_id="R03",
        priority=3,
        description="LLM SDK dependency → external extension",
        condition="llm_deps >= 1",
        decision=DECISION_EXTERNAL_EXTENSION,
        rationale="LLM SDKs must run as external services, never inside the kernel boundary. Use via API only.",
    ),
    IntakeRule(
        rule_id="R04",
        priority=4,
        description="Memory/vector DB dependency → external extension",
        condition="memory_deps > 0 OR heavy_deps > 0",
        decision=DECISION_EXTERNAL_EXTENSION,
        rationale="Memory systems and heavy frameworks require external deployment. Never embed into the kernel.",
    ),
    IntakeRule(
        rule_id="R05",
        priority=5,
        description="Banned kernel dependency → architecture reference",
        condition="banned_deps > 0",
        decision=DECISION_ARCHITECTURE_REFERENCE,
        rationale="Banned dependencies violate kernel purity. Study design from a distance only.",
    ),
    IntakeRule(
        rule_id="R06",
        priority=6,
        description="Documented project with moderate value → external extension",
        condition="has_readme AND has_license AND NOT (R01-R05 matched)",
        decision=DECISION_EXTERNAL_EXTENSION,
        rationale="Documented but not high enough value for direct clone. Use as external service.",
    ),
    IntakeRule(
        rule_id="R07",
        priority=7,
        description="No readme and no code signals → reject",
        condition="NOT has_readme AND NOT language_hints AND NOT dependency_files",
        decision=DECISION_REJECT,
        rationale="Repository has no discoverable content. Cannot assess value or risk.",
    ),
    IntakeRule(
        rule_id="R08",
        priority=8,
        description="High risk: multiple banned deps with no license or readme → reject",
        condition="banned_deps >= 2 AND NOT has_license AND NOT has_readme",
        decision=DECISION_REJECT,
        rationale="Too many purity risks with no documentation or license. Unsafe to integrate.",
    ),
    IntakeRule(
        rule_id="R09",
        priority=9,
        description="Insufficient documentation or value → architecture reference",
        condition="default fallthrough",
        decision=DECISION_ARCHITECTURE_REFERENCE,
        rationale="When in doubt, study architecture but do not integrate. Default conservative position.",
    ),
)


# ═══════════════════════════════════════════════════════════════════════
# Rule-based classification (alternative to scoring engine)
# ═══════════════════════════════════════════════════════════════════════

def apply_rules(
    inp: RepoIntakeInput,
    signals: RepoSignals,
) -> Tuple[str, str]:
    """Apply interpretable rules and return (decision, matched_rule_id).

    This is a rule-based alternative to the numeric scoring engine.
    Produces the same decisions but with explicit rule attribution.

    Returns:
        (decision, rule_id) — rule_id is the matched rule or "" if no match.
    """
    # Rule R08: high risk reject
    if (signals.banned_dependency_hits >= 2
            and not signals.has_license
            and not signals.has_readme):
        return (DECISION_REJECT, "R08")

    # Rule R07: no content reject
    if (not signals.has_readme
            and not signals.language_hints
            and not signals.dependency_files):
        return (DECISION_REJECT, "R07")

    # Rule R02: framework deps → architecture reference
    if signals.framework_dependency_hits >= 1:
        return (DECISION_ARCHITECTURE_REFERENCE, "R02")

    # Rule R03: LLM deps → external extension
    if signals.llm_dependency_hits >= 1:
        return (DECISION_EXTERNAL_EXTENSION, "R03")

    # Rule R04: memory/heavy deps → external extension
    if signals.memory_dependency_hits > 0 or signals.heavy_dependency_hits > 0:
        return (DECISION_EXTERNAL_EXTENSION, "R04")

    # Rule R05: banned deps → architecture reference
    if signals.banned_dependency_hits > 0:
        return (DECISION_ARCHITECTURE_REFERENCE, "R05")

    # Compute cc_value and sk_value for R01 check
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

    # Rule R01: high value documented → direct clone
    if ((cc_value >= 7.0 or sk_value >= 7.0)
            and signals.has_readme
            and signals.has_license):
        return (DECISION_DIRECT_CLONE, "R01")

    # Rule R06: documented but moderate → external extension
    if signals.has_readme and signals.has_license:
        return (DECISION_EXTERNAL_EXTENSION, "R06")

    # Rule R09: default → architecture reference
    return (DECISION_ARCHITECTURE_REFERENCE, "R09")


def get_rules_table() -> list:
    """Return all rules as a list of dicts for display/reporting."""
    return [
        {
            "rule_id": r.rule_id,
            "priority": r.priority,
            "description": r.description,
            "condition": r.condition,
            "decision": r.decision,
        }
        for r in sorted(INTAKE_RULES, key=lambda r: r.priority)
    ]
